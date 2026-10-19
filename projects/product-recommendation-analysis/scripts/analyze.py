"""Exhaustive market-basket rules and item co-purchase similarity on tiny data.

This is NOT Apriori: all subsets within each basket are enumerated. There is
no train/test evaluation or precision@5 estimate. Only main() exports files;
functions use their own inputs rather than any global transaction counts.
"""

from collections import Counter
from itertools import combinations
import json
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_DIR = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = ("transaction_id", "customer_id", "product_id", "product_name", "category", "price")
ITEMSET_COLUMNS = ("itemset", "support_count", "support")
RULE_COLUMNS = (
    "antecedents", "consequents", "support_count", "antecedent_count",
    "consequent_count", "support", "confidence", "lift",
)


def prepare_data(df):
    """Validate transactions; product_name is the explicit analytical item key.

    The supplied catalog has two product_ids named Phone Case. They are merged
    for this demonstration by name, rather than silently treating them as two
    independent co-purchases. This is a declared simplification, not a SKU fix.
    """
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    data = df.copy()
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Required transaction fields cannot be missing.")
    data["price"] = pd.to_numeric(data["price"], errors="raise")
    if not np.isfinite(data["price"].to_numpy(dtype=float)).all() or data["price"].lt(0).any():
        raise ValueError("price must be finite and nonnegative.")
    if data.groupby("transaction_id", sort=True)["customer_id"].nunique().gt(1).any():
        raise ValueError("Each transaction_id must belong to one customer.")
    data["product_name"] = data["product_name"].astype(str)
    return data.sort_values(
        ["transaction_id", "product_name", "product_id", "customer_id"], kind="mergesort"
    ).reset_index(drop=True)


def load_data(path=None):
    """Read transactions without generating output files."""
    path = Path(path) if path is not None else PROJECT_DIR / "data" / "transactions.csv"
    return prepare_data(pd.read_csv(path))


def normalize_transactions(transactions):
    """Return local immutable baskets; repeated items count once per basket."""
    return tuple(frozenset(str(item) for item in transaction) for transaction in transactions)


def build_transactions(df):
    """Return sorted-name baskets, ordered deterministically by transaction_id."""
    data = prepare_data(df)
    return data.groupby("transaction_id", sort=True)["product_name"].agg(
        lambda values: tuple(sorted(set(values)))
    ).tolist()


def empty_itemsets():
    """A stable schema, including numeric dtypes, even when no itemsets qualify."""
    return pd.DataFrame({
        "itemset": pd.Series(dtype=object),
        "support_count": pd.Series(dtype="int64"),
        "support": pd.Series(dtype=float),
    })


def empty_rules():
    """A stable rule schema prevents KeyErrors for empty or high-threshold data."""
    return pd.DataFrame({
        "antecedents": pd.Series(dtype=object),
        "consequents": pd.Series(dtype=object),
        "support_count": pd.Series(dtype="int64"),
        "antecedent_count": pd.Series(dtype="int64"),
        "consequent_count": pd.Series(dtype="int64"),
        "support": pd.Series(dtype=float),
        "confidence": pd.Series(dtype=float),
        "lift": pd.Series(dtype=float),
    })


def get_frequent_itemsets(transactions, min_support=0.1):
    """Enumerate ALL basket subsets, not Apriori candidate pruning.

    Support is baskets containing the itemset / all supplied baskets (including
    empty baskets). Exponential basket-size cost makes this a tiny-data demo.
    All transaction counts are local; empty input has a stable empty schema.
    """
    if not 0 < min_support <= 1:
        raise ValueError("min_support must be in (0, 1].")
    baskets = normalize_transactions(transactions)
    if not baskets:
        return empty_itemsets()
    counts = Counter()
    for basket in baskets:
        items = sorted(basket)
        for size in range(1, len(items) + 1):
            counts.update(combinations(items, size))
    rows = [
        {"itemset": itemset, "support_count": count, "support": count / len(baskets)}
        for itemset, count in counts.items() if count / len(baskets) >= min_support
    ]
    if not rows:
        return empty_itemsets()
    rows.sort(key=lambda row: (-row["support"], row["itemset"]))
    return pd.DataFrame(rows, columns=list(ITEMSET_COLUMNS))


def get_association_rules(frequent_df, transactions, min_confidence=0.3):
    """Generate directed rules with local support counts and deterministic ties.

    For A -> B: support=P(A and B), confidence=P(A and B)/P(A), and
    lift=P(A and B)/(P(A)*P(B)). The supplied baskets are authoritative, so
    no external num_transactions or stale precomputed support is used.
    """
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be in [0, 1].")
    if "itemset" not in frequent_df.columns:
        raise ValueError("frequent_df must contain an itemset column.")
    baskets = normalize_transactions(transactions)
    if not baskets or frequent_df.empty:
        return empty_rules()
    count_cache = {}

    def count_containing(items):
        key = frozenset(items)
        if key not in count_cache:
            count_cache[key] = sum(key.issubset(basket) for basket in baskets)
        return count_cache[key]

    full_itemsets = sorted({tuple(sorted(set(items))) for items in frequent_df["itemset"]})
    rows = []
    for itemset in full_itemsets:
        if len(itemset) < 2:
            continue
        full_count = count_containing(itemset)
        if not full_count:
            continue
        for size in range(1, len(itemset)):
            for antecedents in combinations(itemset, size):
                consequents = tuple(sorted(set(itemset) - set(antecedents)))
                antecedent_count = count_containing(antecedents)
                consequent_count = count_containing(consequents)
                confidence = full_count / antecedent_count
                if confidence < min_confidence:
                    continue
                rows.append({
                    "antecedents": tuple(antecedents),
                    "consequents": consequents,
                    "support_count": full_count,
                    "antecedent_count": antecedent_count,
                    "consequent_count": consequent_count,
                    "support": full_count / len(baskets),
                    "confidence": confidence,
                    "lift": confidence / (consequent_count / len(baskets)),
                })
    if not rows:
        return empty_rules()
    rows.sort(key=lambda row: (
        -row["lift"], -row["confidence"], -row["support"], row["antecedents"], row["consequents"],
    ))
    return pd.DataFrame(rows, columns=list(RULE_COLUMNS))


def build_item_similarity(df):
    """Cosine similarity of binary customer x item purchase-presence columns."""
    data = prepare_data(df)
    if data.empty:
        return pd.DataFrame(dtype=float)
    binary = pd.crosstab(data["customer_id"], data["product_name"]).gt(0).astype(int)
    binary = binary.sort_index().sort_index(axis=1)
    similarity = cosine_similarity(binary.T)
    return pd.DataFrame(similarity, index=binary.columns, columns=binary.columns)


def get_similar_items(item_sim_df, item, top_n=3):
    """Drop self BEFORE ranking; ties sort by name, and zero similarities are omitted."""
    if not isinstance(top_n, (int, np.integer)) or top_n < 0:
        raise ValueError("top_n must be a nonnegative integer.")
    if item not in item_sim_df.index:
        raise KeyError(item)
    candidates = item_sim_df.loc[item].drop(labels=[item], errors="ignore")
    ranking = pd.DataFrame({
        "product_name": candidates.index,
        "similarity": candidates.to_numpy(dtype=float),
    })
    return ranking.loc[ranking["similarity"].gt(0)].sort_values(
        ["similarity", "product_name"], ascending=[False, True], kind="mergesort"
    ).head(top_n).reset_index(drop=True)


def serialize_sequences(table, columns):
    """CSV-safe sorted JSON arrays, never nondeterministic set/frozenset reprs."""
    result = table.copy()
    for column in columns:
        result[column] = result[column].map(
            lambda values: json.dumps(sorted(values), ensure_ascii=False, separators=(",", ":"))
        )
    return result


def analyze(df, min_support=0.1, min_confidence=0.3, top_n=3):
    """Return co-occurrence descriptions, not a held-out recommendation score."""
    data = prepare_data(df)
    transactions = build_transactions(data)
    frequent = get_frequent_itemsets(transactions, min_support=min_support)
    rules = get_association_rules(frequent, transactions, min_confidence=min_confidence)
    similarity = build_item_similarity(data)
    recommendation_rows = []
    for item in similarity.index:
        for candidate in get_similar_items(similarity, item, top_n=top_n).itertuples(index=False):
            recommendation_rows.append({
                "source_item": item,
                "recommended_item": candidate.product_name,
                "similarity": candidate.similarity,
            })
    recommendations = pd.DataFrame(recommendation_rows, columns=["source_item", "recommended_item", "similarity"])
    popularity_counts = Counter(item for basket in transactions for item in basket)
    popularity_rows = [
        {"product_name": item, "transactions": count, "support": count / len(transactions)}
        for item, count in popularity_counts.items()
    ]
    popularity_rows.sort(key=lambda row: (-row["transactions"], row["product_name"]))
    popularity = pd.DataFrame(popularity_rows, columns=["product_name", "transactions", "support"])
    return {
        "overview": pd.DataFrame([{
            "input_rows": len(data),
            "transactions": len(transactions),
            "customers": data["customer_id"].nunique(),
            "analytical_items_by_name": data["product_name"].nunique(),
            "catalog_product_ids": data["product_id"].nunique(),
        }]),
        "frequent_itemsets": frequent,
        "association_rules": rules,
        "item_similarity": similarity,
        "similar_items": recommendations,
        "product_popularity": popularity,
    }


def plot_dashboard(results):
    """Return a headless figure that remains valid for empty rule/itemset tables."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    popularity = results["product_popularity"].head(10)
    if not popularity.empty:
        axes[0, 0].barh(popularity["product_name"], popularity["support"], color="steelblue")
        axes[0, 0].invert_yaxis()
    else:
        axes[0, 0].text(0.5, 0.5, "No items", ha="center", transform=axes[0, 0].transAxes)
    axes[0, 0].set(title="Item support (basket presence)", xlabel="Fraction of baskets")

    rules = results["association_rules"]
    if not rules.empty:
        scatter = axes[0, 1].scatter(rules["confidence"], rules["lift"], c=rules["support"], cmap="viridis", alpha=0.75, s=70)
        fig.colorbar(scatter, ax=axes[0, 1], label="Support")
        top = rules.head(8)
        labels = [fill(f"{' + '.join(a)} -> {' + '.join(b)}", width=35) for a, b in zip(top["antecedents"], top["consequents"])]
        axes[1, 0].barh(np.arange(len(top)), top["lift"], color="coral")
        axes[1, 0].set_yticks(np.arange(len(top)))
        axes[1, 0].set_yticklabels(labels, fontsize=8)
        axes[1, 0].invert_yaxis()
    else:
        for ax in (axes[0, 1], axes[1, 0]):
            ax.text(0.5, 0.5, "No rules meet the thresholds", ha="center", va="center", transform=ax.transAxes)
    axes[0, 1].set(title="Association rules (descriptive)", xlabel="Confidence", ylabel="Lift")
    axes[1, 0].set(title="Top rules by lift (deterministic ties)", xlabel="Lift")

    similarity = results["item_similarity"]
    if not similarity.empty and not popularity.empty:
        items = popularity["product_name"].tolist()
        sns.heatmap(similarity.loc[items, items], annot=True, fmt=".2f", cmap="YlOrRd", vmin=0, vmax=1, ax=axes[1, 1], annot_kws={"fontsize": 7})
        axes[1, 1].tick_params(axis="x", rotation=45, labelsize=8)
        axes[1, 1].tick_params(axis="y", labelsize=8)
    else:
        axes[1, 1].text(0.5, 0.5, "No item similarities", ha="center", transform=axes[1, 1].transAxes)
    axes[1, 1].set_title("Binary customer-purchase cosine similarity")
    fig.suptitle("Basket analysis | synthetic demonstration data", fontsize=15)
    fig.text(0.5, 0.01, "Exhaustive subset enumeration, not Apriori. No held-out precision@5 or incremental sales estimate.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    return fig


def main(data_path=None, output_dir=None):
    """Export stable sorted JSON itemsets/rules and recommendation_dashboard.png."""
    results = analyze(load_data(data_path))
    destination = Path(output_dir) if output_dir is not None else PROJECT_DIR / "output"
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        export = table
        if name == "frequent_itemsets":
            export = serialize_sequences(table, ("itemset",))
        elif name == "association_rules":
            export = serialize_sequences(table, ("antecedents", "consequents"))
        export.to_csv(
            destination / f"{name}.csv", index=(name == "item_similarity"),
            index_label="product_name" if name == "item_similarity" else None,
            float_format="%.6f", encoding="utf-8", lineterminator="\n",
        )
    figure = plot_dashboard(results)
    figure.savefig(destination / "recommendation_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"\n=== overview ===\n{results['overview'].to_string(index=False)}")
    display_rules = serialize_sequences(results["association_rules"], ("antecedents", "consequents"))
    print(f"\n=== association rules (descriptive) ===\n{display_rules.to_string(index=False)}")
    print(f"\n=== similar items (not evaluated predictions) ===\n{results['similar_items'].to_string(index=False)}")
    print("\nNo recommendation test metric is estimated from this synthetic sample.")
    print(f"Outputs saved to {destination}")
    return results


if __name__ == "__main__":
    main()
