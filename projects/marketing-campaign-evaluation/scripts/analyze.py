"""Descriptive campaign and variant comparisons, not a randomized A/B test.

Ratios are calculated from summed numerators/denominators. ROAS and an
explicit advertising-spend return proxy are not net-profit ROI. Only main()
reads/exports by default; notebook callers can use the individual functions.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_DIR = Path(__file__).resolve().parents[1]
AMOUNT_COLUMNS = ("impressions", "clicks", "spend", "revenue", "conversions")
COMPARISON_KEYS = ("channel", "campaign_type", "start_date", "end_date", "age_group")
REQUIRED_COLUMNS = ("campaign_id", *COMPARISON_KEYS, *AMOUNT_COLUMNS, "variant")


def safe_ratio(numerator, denominator):
    """Elementwise ratio with NaN for zero denominators, preserving the index."""
    return numerator.div(denominator.where(denominator.ne(0)))


def prepare_data(df):
    """Validate the synthetic one-row-per-campaign summary schema."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    data = df.copy()
    if data.empty or data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Campaign data must be nonempty with no missing required fields.")
    if data["campaign_id"].duplicated().any():
        raise ValueError("campaign_id must identify a single aggregated campaign row.")
    for column in ("start_date", "end_date"):
        data[column] = pd.to_datetime(data[column], errors="raise")
        if data[column].isna().any():
            raise ValueError(f"{column} cannot be NaT.")
    if data["end_date"].lt(data["start_date"]).any():
        raise ValueError("Campaign end_date must not precede start_date.")
    for column in AMOUNT_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column].to_numpy(dtype=float)).all() or data[column].lt(0).any():
            raise ValueError(f"{column} must be finite and nonnegative.")
    for column in ("impressions", "clicks", "conversions"):
        if data[column].mod(1).ne(0).any():
            raise ValueError(f"{column} must be an integer count.")
        data[column] = data[column].astype("int64")
    if data["clicks"].gt(data["impressions"]).any() or data["conversions"].gt(data["clicks"]).any():
        raise ValueError("This demo assumes conversions <= clicks <= impressions.")
    return data.sort_values([*COMPARISON_KEYS, "variant", "campaign_id"], kind="mergesort").reset_index(drop=True)


def load_data(path=None):
    """Read validated campaign rows without generating any output files."""
    path = Path(path) if path is not None else PROJECT_DIR / "data" / "campaign_data.csv"
    return prepare_data(pd.read_csv(path))


def add_metrics(table):
    """Add metrics to raw or aggregated totals; undefined denominators stay NaN.

    ad_spend_return_proxy_pct = (revenue - spend) / spend * 100. It subtracts
    advertising spend ONLY, omitting goods, labor, returns, tax, and other costs.
    """
    result = table.copy()
    result["ctr_pct"] = safe_ratio(result["clicks"], result["impressions"]) * 100
    result["cvr_pct"] = safe_ratio(result["conversions"], result["clicks"]) * 100
    result["cpc"] = safe_ratio(result["spend"], result["clicks"])
    result["cpm"] = safe_ratio(result["spend"], result["impressions"]) * 1000
    result["cpa"] = safe_ratio(result["spend"], result["conversions"])
    result["roas"] = safe_ratio(result["revenue"], result["spend"])
    result["revenue_minus_ad_spend"] = result["revenue"] - result["spend"]
    result["ad_spend_return_proxy_pct"] = safe_ratio(result["revenue_minus_ad_spend"], result["spend"]) * 100
    return result


def aggregate_metrics(data, group_columns):
    """Sum volumes first, rather than taking unweighted averages of row ratios."""
    grouped = data.groupby(list(group_columns), sort=True, observed=True)
    amounts = grouped[list(AMOUNT_COLUMNS)].sum()
    amounts["campaign_count"] = grouped.size()
    return add_metrics(amounts.reset_index()).sort_values(list(group_columns), kind="mergesort").reset_index(drop=True)


def compare_variants(df):
    """Compare variants only within the same observed channel/type/dates/age.

    campaign_id is NOT a comparison key because every ID has only one variant.
    No random assignment, independence, causal lift, or significance is assumed.
    CVR changes are descriptive percentage-point/relative differences from the
    available Control row in the same observed group.
    """
    data = prepare_data(df)
    comparison = aggregate_metrics(data, (*COMPARISON_KEYS, "variant"))
    variant_counts = comparison.groupby(list(COMPARISON_KEYS), sort=True)["variant"].transform("nunique")
    comparison["variants_in_group"] = variant_counts
    controls = comparison.loc[
        comparison["variant"].eq("Control"), [*COMPARISON_KEYS, "cvr_pct", "roas"]
    ].rename(columns={"cvr_pct": "control_cvr_pct", "roas": "control_roas"})
    controls["has_control"] = True
    comparison = comparison.merge(controls, on=list(COMPARISON_KEYS), how="left", validate="many_to_one")
    comparison["has_control"] = comparison["has_control"].eq(True)
    comparison["comparable_group"] = comparison["has_control"] & comparison["variants_in_group"].ge(2)
    comparison["cvr_delta_pp_vs_control"] = (
        comparison["cvr_pct"] - comparison["control_cvr_pct"]
    ).where(comparison["comparable_group"])
    comparison["relative_cvr_change_pct_vs_control"] = (
        safe_ratio(comparison["cvr_pct"], comparison["control_cvr_pct"]) - 1
    ).mul(100).where(comparison["comparable_group"])
    comparison["roas_delta_vs_control"] = (
        comparison["roas"] - comparison["control_roas"]
    ).where(comparison["comparable_group"])
    return comparison.sort_values([*COMPARISON_KEYS, "variant"], kind="mergesort").reset_index(drop=True)


def analyze(df):
    """Return descriptive tables, including observed-group variant comparisons."""
    data = prepare_data(df)
    overview = pd.DataFrame([{
        "campaign_count": len(data),
        **{column: data[column].sum() for column in AMOUNT_COLUMNS},
    }])
    return {
        "overview": add_metrics(overview),
        "campaign_metrics": add_metrics(data),
        "channel_performance": aggregate_metrics(data, ("channel",)),
        "variant_comparison": compare_variants(data),
        "age_group_performance": aggregate_metrics(data, ("age_group",)),
    }


def plot_dashboard(results):
    """Create a headless figure with neutral descriptive labels."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    channel = results["channel_performance"]
    axes[0, 0].bar(channel["channel"], channel["ctr_pct"], color="steelblue")
    axes[0, 0].set(title="Channel CTR (total clicks / impressions)", ylabel="CTR (%)")
    axes[0, 0].tick_params(axis="x", rotation=15)
    axes[0, 1].bar(channel["channel"], channel["roas"], color="coral")
    axes[0, 1].set(title="Channel ROAS (revenue / advertising spend)", ylabel="ROAS (x)")
    axes[0, 1].tick_params(axis="x", rotation=15)

    age = results["age_group_performance"]
    axes[1, 0].bar(age["age_group"], age["cvr_pct"], color="seagreen")
    axes[1, 0].set(title="Age-group CVR (confounded with channel)", xlabel="Age group", ylabel="CVR (%)")

    comparison = results["variant_comparison"]
    comparable = comparison.loc[comparison["comparable_group"]].copy()
    if comparable.empty:
        axes[1, 1].text(0.5, 0.5, "No observed groups with Control and another variant", ha="center", va="center", wrap=True, transform=axes[1, 1].transAxes)
    else:
        wide = comparable.pivot(index=list(COMPARISON_KEYS), columns="variant", values="cvr_pct").sort_index()
        positions = np.arange(len(wide))
        width = 0.8 / max(len(wide.columns), 1)
        colors = sns.color_palette("muted", n_colors=len(wide.columns))
        for number, variant in enumerate(wide.columns):
            offset = (number - (len(wide.columns) - 1) / 2) * width
            axes[1, 1].bar(positions + offset, wide[variant], width=width, label=variant, color=colors[number])
        labels = [f"{key[0]}\n{key[1]}, {key[4]}\n{key[2]:%m/%d}-{key[3]:%m/%d}" for key in wide.index]
        axes[1, 1].set_xticks(positions)
        axes[1, 1].set_xticklabels(labels, fontsize=8)
        axes[1, 1].legend(title="Observed variant", fontsize=8)
    axes[1, 1].set(title="Within-group variant CVR (descriptive only)", ylabel="CVR (%)")
    fig.suptitle("Marketing campaigns | synthetic demonstration data", fontsize=15)
    fig.text(0.5, 0.01, "No randomized experiment or net-profit ROI; channel, age, targeting, and campaign periods are not independent.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    return fig


def main(data_path=None, output_dir=None):
    """Export corrected tables and campaign_dashboard.png.

    The legacy ab_test_results.csv filename is retained for compatibility; its
    contents are descriptive variant comparisons, NOT experimental test results.
    """
    results = analyze(load_data(data_path))
    destination = Path(output_dir) if output_dir is not None else PROJECT_DIR / "output"
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        filename = "ab_test_results.csv" if name == "variant_comparison" else f"{name}.csv"
        table.to_csv(destination / filename, index=False, float_format="%.6f", date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n")
    figure = plot_dashboard(results)
    figure.savefig(destination / "campaign_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    for name in ("channel_performance", "variant_comparison", "age_group_performance"):
        print(f"\n=== {name} (descriptive) ===\n{results[name].to_string(index=False)}")
    print("\nROAS is revenue/spend. ad_spend_return_proxy_pct excludes all non-advertising costs.")
    print("Age and channel are confounded; CPA is cost per conversion, not proven new-customer CAC.")
    print(f"Outputs saved to {destination}")
    return results


if __name__ == "__main__":
    main()
