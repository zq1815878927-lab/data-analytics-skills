"""Rule-based RFM groups and an illustrative K-means model on synthetic data.

The snapshot supplies recency/frequency/observed monetary totals directly. It
cannot establish customer lifetime value, declining activity, or actual churn.
Only main() exports files; analysis functions are reusable from notebooks.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

PROJECT_DIR = Path(__file__).resolve().parents[1]
FEATURE_COLUMNS = ("recency_days", "frequency", "monetary")
REQUIRED_COLUMNS = ("customer_id", *FEATURE_COLUMNS)
SEGMENT_ORDER = ("Champions", "Loyal", "At-Risk", "New/Leads", "Others")


def prepare_data(df):
    """Validate a one-row-per-customer, nonnegative RFM snapshot."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    data = df.copy()
    if data.empty or data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Customer data must be nonempty with no missing required values.")
    if data["customer_id"].duplicated().any():
        raise ValueError("Each customer_id must have one RFM snapshot row.")
    for column in FEATURE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column].to_numpy(dtype=float)).all() or data[column].lt(0).any():
            raise ValueError(f"{column} must be finite and nonnegative.")
    if data["frequency"].mod(1).ne(0).any():
        raise ValueError("frequency must be an integer count.")
    data["frequency"] = data["frequency"].astype("int64")
    return data.sort_values("customer_id", kind="mergesort").reset_index(drop=True)


def load_data(path=None):
    """Load the supplied snapshot without creating any output files."""
    path = Path(path) if path is not None else PROJECT_DIR / "data" / "customer_data.csv"
    return prepare_data(pd.read_csv(path))


def quantile_score(values, higher_is_better=True, bins=5):
    """Tie-preserving qcut scores; never split equal values by row order.

    Repeated quantile edges are dropped. When at least two intervals remain,
    interval positions are rescaled monotonically to 1..bins with half-up
    rounding. A constant series or a single remaining interval receives the
    neutral midpoint score. Consequently group sizes need not be equal, some
    scores may be absent, and the five business-rule segments need not appear.
    """
    if not isinstance(bins, (int, np.integer)) or bins < 2:
        raise ValueError("bins must be an integer >= 2.")
    numeric = pd.to_numeric(pd.Series(values), errors="raise").copy()
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Scores require finite, non-missing values.")
    if numeric.empty:
        return pd.Series(index=numeric.index, dtype="int64", name=numeric.name)
    neutral = (bins + 1) // 2
    if numeric.nunique() == 1:
        return pd.Series(neutral, index=numeric.index, dtype="int64", name=numeric.name)
    codes, edges = pd.qcut(numeric, q=bins, labels=False, retbins=True, duplicates="drop")
    interval_count = len(edges) - 1
    if interval_count <= 1:
        return pd.Series(neutral, index=numeric.index, dtype="int64", name=numeric.name)
    scores = pd.Series(
        np.floor(codes.to_numpy(dtype=float) * (bins - 1) / (interval_count - 1) + 0.5).astype("int64") + 1,
        index=numeric.index,
        name=numeric.name,
    )
    return scores if higher_is_better else bins + 1 - scores


def rfm_score(values, col=None, ascending=True):
    """Compatibility alias for the old helper; col is unused, ties stay equal."""
    return quantile_score(values, higher_is_better=ascending)


def segment_customers(row):
    """Apply an explicitly illustrative rule, not a learned churn/CLV outcome."""
    r, f, m = int(row["r_score"]), int(row["f_score"]), int(row["m_score"])
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3 and m >= 3:
        return "Loyal"
    if r <= 2 and f >= 3:
        return "At-Risk"
    if r >= 4 and f <= 2:
        return "New/Leads"
    return "Others"


def assign_rfm_scores(df):
    """Return the validated snapshot plus 1..5 scores and business-rule labels."""
    data = prepare_data(df)
    data["r_score"] = quantile_score(data["recency_days"], higher_is_better=False)
    data["f_score"] = quantile_score(data["frequency"])
    data["m_score"] = quantile_score(data["monetary"])
    data["rfm_score"] = data[["r_score", "f_score", "m_score"]].astype(str).agg("".join, axis=1)
    data["segment"] = data.apply(segment_customers, axis=1)
    return data


def summarize_segments(data):
    """Summarize only observed rule labels, not five promised customer personas."""
    summary = data.groupby("segment", sort=True).agg(
        count=("customer_id", "nunique"),
        avg_recency=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
        total_monetary=("monetary", "sum"),
    )
    present = [segment for segment in SEGMENT_ORDER if segment in summary.index]
    summary = summary.reindex(present).reset_index()
    summary["customer_share_pct"] = summary["count"] / len(data) * 100
    total = data["monetary"].sum()
    summary["monetary_share_pct"] = summary["total_monetary"] / total * 100 if total else np.nan
    return summary


def cluster_customers(df, n_clusters=4, random_state=42):
    """Standardize R/F/M and fit an illustrative, fixed-k K-means model.

    Return (assigned_snapshot, cluster_profile, inertia_diagnostic). Four is a
    configurable example, NOT a verified optimal number. Numeric cluster IDs
    are renamed by mean recency, then frequency/monetary, for stable display.
    """
    data = prepare_data(df)
    distinct_points = len(data[list(FEATURE_COLUMNS)].drop_duplicates())
    if not isinstance(n_clusters, (int, np.integer)) or not 1 <= n_clusters <= distinct_points:
        raise ValueError("n_clusters must be an integer between 1 and the number of distinct RFM points.")
    scaled = StandardScaler().fit_transform(data[list(FEATURE_COLUMNS)])
    inertia_rows = []
    for k in range(2, min(7, distinct_points) + 1):
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        model.fit(scaled)
        inertia_rows.append({"k": k, "inertia": model.inertia_})
    inertia = pd.DataFrame(inertia_rows, columns=["k", "inertia"])
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    data["cluster"] = model.fit_predict(scaled)
    means = data.groupby("cluster", sort=True)[list(FEATURE_COLUMNS)].mean().reset_index()
    ordered_ids = means.sort_values(
        ["recency_days", "frequency", "monetary", "cluster"],
        ascending=[True, False, False, True], kind="mergesort",
    )["cluster"].tolist()
    rename = {old: new for new, old in enumerate(ordered_ids)}
    data["cluster"] = data["cluster"].map(rename).astype("int64")
    profile = data.groupby("cluster", sort=True).agg(
        count=("customer_id", "nunique"),
        avg_recency=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()
    return data, profile, inertia


def analyze(df, n_clusters=4):
    """Return rule/cluster tables without inferring customer future behavior."""
    rfm = assign_rfm_scores(df)
    customers, profile, inertia = cluster_customers(rfm, n_clusters=n_clusters)
    return {
        "overview": pd.DataFrame([{
            "customers": len(customers),
            "observed_monetary_total": customers["monetary"].sum(),
            "observed_rule_groups": customers["segment"].nunique(),
            "example_cluster_count": n_clusters,
        }]),
        "rfm_segments": summarize_segments(customers),
        "kmeans_clusters": profile,
        "customer_segments": customers,
        "kmeans_inertia": inertia,
    }


def plot_dashboard(results):
    """Return a headless figure distinguishing rule labels from fitted clusters."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    segments = results["rfm_segments"]
    axes[0, 0].bar(segments["segment"], segments["count"], color="steelblue")
    axes[0, 0].set(title="RFM rule groups (only observed labels)", ylabel="Customers")
    axes[0, 0].tick_params(axis="x", rotation=20)
    axes[0, 1].bar(segments["segment"], segments["total_monetary"], color="coral")
    axes[0, 1].set(title="Observed monetary totals by rule group", ylabel="Snapshot amount (not CLV)")
    axes[0, 1].tick_params(axis="x", rotation=20)

    customers = results["customer_segments"]
    cluster_ids = sorted(customers["cluster"].unique())
    colors = sns.color_palette("tab10", n_colors=len(cluster_ids))
    for cluster_id, color in zip(cluster_ids, colors):
        group = customers.loc[customers["cluster"].eq(cluster_id)]
        axes[1, 0].scatter(group["frequency"], group["monetary"], color=color, label=f"Cluster {cluster_id}", s=70, alpha=0.8)
        axes[1, 1].scatter(group["recency_days"], group["frequency"], color=color, label=f"Cluster {cluster_id}", s=70, alpha=0.8)
    axes[1, 0].set(title="Illustrative K-means: frequency vs. amount", xlabel="Observed frequency", ylabel="Observed monetary total")
    axes[1, 1].set(title="Illustrative K-means: recency vs. frequency", xlabel="Days since last purchase", ylabel="Observed frequency")
    axes[1, 0].legend(fontsize=8)
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("Customer segmentation | synthetic snapshot", fontsize=15)
    fig.text(0.5, 0.01, f"Rule labels are not verified churn/new-customer facts; fixed k={len(cluster_ids)} is an example, not proven optimal.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    return fig


def main(data_path=None, output_dir=None):
    """Export segment tables and segmentation_dashboard.png for the default k=4."""
    results = analyze(load_data(data_path))
    destination = Path(output_dir) if output_dir is not None else PROJECT_DIR / "output"
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        table.to_csv(destination / f"{name}.csv", index=False, float_format="%.6f", encoding="utf-8", lineterminator="\n")
    figure = plot_dashboard(results)
    figure.savefig(destination / "segmentation_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    for name in ("overview", "rfm_segments", "kmeans_clusters", "kmeans_inertia"):
        print(f"\n=== {name} ===\n{results[name].to_string(index=False)}")
    print("\nBusiness-rule labels are illustrative. No CLV, observed churn, or optimal-k claim is made.")
    print(f"Outputs saved to {destination}")
    return results


if __name__ == "__main__":
    main()
