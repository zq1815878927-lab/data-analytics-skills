"""Descriptive sales analysis of a small, synthetic, one-year order sample.

Importing this module does not read data or write outputs. Use load_data(),
analyze(), and plot_dashboard() from notebooks; main() performs file exports.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_DIR = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = (
    "order_id", "order_date", "customer_id", "product_category",
    "product_name", "quantity", "unit_price", "region", "payment_method",
)


def prepare_data(df):
    """Validate the one-row-per-order schema and return an independent copy."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    data = df.copy()
    if data.empty or data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Sales data must be nonempty and contain no missing required values.")
    if data["order_id"].duplicated().any():
        raise ValueError("This sample assumes exactly one row per order_id.")
    data["order_date"] = pd.to_datetime(data["order_date"], errors="raise")
    if data["order_date"].isna().any():
        raise ValueError("order_date cannot be NaT.")
    for column in ("quantity", "unit_price"):
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{column} must be finite.")
    if (data["quantity"] <= 0).any() or (data["quantity"] % 1 != 0).any():
        raise ValueError("quantity must be a positive integer.")
    if (data["unit_price"] < 0).any():
        raise ValueError("unit_price must be nonnegative.")
    data["quantity"] = data["quantity"].astype("int64")
    data["revenue"] = data["quantity"] * data["unit_price"]
    if not np.isfinite(data["revenue"].to_numpy(dtype=float)).all():
        raise ValueError("Calculated order value must be finite.")
    # Nominal order value only: no discounts, refunds, costs, or tax adjustments.
    data["month"] = data["order_date"].dt.to_period("M").astype(str)
    return data.sort_values(["order_date", "order_id"], kind="mergesort").reset_index(drop=True)


def load_data(path=None):
    """Read the bundled CSV, or an explicitly supplied file, without exporting."""
    path = Path(path) if path is not None else PROJECT_DIR / "data" / "sales_data.csv"
    return prepare_data(pd.read_csv(path))


def summarize_sales(data, group_column):
    """Aggregate order counts, units, and nominal order value; break ties by name."""
    summary = data.groupby(group_column, sort=True, observed=True).agg(
        orders=("order_id", "nunique"),
        units=("quantity", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    total = data["revenue"].sum()
    summary["revenue_share_pct"] = summary["revenue"] / total * 100 if total else np.nan
    return summary.sort_values(
        ["revenue", group_column], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)


def analyze(df):
    """Return reproducible descriptive tables; do not infer recurring seasonality."""
    data = prepare_data(df)
    total_revenue = data["revenue"].sum()
    order_count = data["order_id"].nunique()
    q4_revenue = data.loc[data["order_date"].dt.quarter.eq(4), "revenue"].sum()
    overview = pd.DataFrame([{
        "order_count": order_count,
        "customer_count": data["customer_id"].nunique(),
        "units": data["quantity"].sum(),
        "revenue": total_revenue,
        "average_order_value": total_revenue / order_count,
        "first_order_date": data["order_date"].min().strftime("%Y-%m-%d"),
        "last_order_date": data["order_date"].max().strftime("%Y-%m-%d"),
        "q4_revenue": q4_revenue,
        "q4_revenue_share_pct": q4_revenue / total_revenue * 100 if total_revenue else np.nan,
    }])
    monthly = summarize_sales(data, "month").sort_values("month").reset_index(drop=True)
    monthly["average_order_value"] = monthly["revenue"] / monthly["orders"]
    payments = data.groupby("payment_method", sort=True).agg(
        orders=("order_id", "nunique")
    ).reset_index()
    payments["order_share_pct"] = payments["orders"] / order_count * 100
    payments = payments.sort_values(
        ["orders", "payment_method"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    return {
        "overview": overview,
        "monthly_sales": monthly,
        "category_sales": summarize_sales(data, "product_category"),
        "region_sales": summarize_sales(data, "region"),
        "top_products": summarize_sales(data, "product_name").head(5).reset_index(drop=True),
        "payment_methods": payments,
    }


def plot_dashboard(results):
    """Return an Agg-backed figure; display it in a notebook or save it explicitly."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    monthly = results["monthly_sales"]
    axes[0, 0].plot(monthly["month"], monthly["revenue"], marker="o", color="steelblue")
    axes[0, 0].set(title="Monthly order value (observed sample)", xlabel="Month", ylabel="Order value")
    axes[0, 0].tick_params(axis="x", rotation=45)

    categories = results["category_sales"]
    axes[0, 1].bar(categories["product_category"], categories["revenue"], color="coral")
    axes[0, 1].set(title="Category order value", xlabel="Category", ylabel="Order value")

    regions = results["region_sales"]
    axes[1, 0].bar(regions["region"], regions["revenue"], color="seagreen")
    axes[1, 0].set(title="Regional order value", xlabel="Region", ylabel="Order value")

    payments = results["payment_methods"]
    axes[1, 1].bar(payments["payment_method"], payments["orders"], color="mediumpurple")
    axes[1, 1].set(title="Payment methods (orders, not revenue)", xlabel="Payment method", ylabel="Orders")
    for ax in axes.flat:
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    fig.suptitle("E-commerce sales | synthetic demonstration data", fontsize=15)
    fig.text(0.5, 0.01, "One small yearly sample cannot establish recurring seasonality or market performance.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    return fig


def main(data_path=None, output_dir=None):
    """Run the standalone analysis and export tables plus sales_dashboard.png."""
    results = analyze(load_data(data_path))
    destination = Path(output_dir) if output_dir is not None else PROJECT_DIR / "output"
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        table.to_csv(destination / f"{name}.csv", index=False, float_format="%.6f", encoding="utf-8", lineterminator="\n")
    figure = plot_dashboard(results)
    figure.savefig(destination / "sales_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    for name in ("overview", "monthly_sales", "category_sales", "region_sales", "top_products"):
        print(f"\n=== {name} ===\n{results[name].to_string(index=False)}")
    print("\nSynthetic sample only; no seasonal or causal claim is made.")
    print(f"Outputs saved to {destination}")
    return results


if __name__ == "__main__":
    main()
