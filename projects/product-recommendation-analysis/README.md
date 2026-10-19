# 购物篮关联规则与商品相似候选

使用 [transactions.csv](<./data/transactions.csv>) 的**合成演示数据**：35 行、15 个购物篮、15 位客户。按 `product_name` 作为分析商品键，得到 11 种商品；原始目录有 12 个商品 ID，其中 P002 / P008 同名 Phone Case 在本演示中合并。该简化已明确声明，不修改原始 CSV，也不代表真实 SKU 清洗策略。小样本结论不可外推。

## 算法与指标

- 每个购物篮内按商品名去重，商品是否出现只记一次；分母是购物篮总数，不是商品行数或销量。
- **穷举每个购物篮的全部非空子集，不是 Apriori**，没有候选剪枝。单篮含 m 个商品时有 `2^m−1` 个子集，仅适合本项目的小购物篮演示。
- 默认 support≥0.1、confidence≥0.3。对不相交的 A→B：`support=P(A∩B)`，`confidence=P(A∩B)/P(A)`，`lift=confidence/P(B)`。
- 用二值“客户×商品购买出现”矩阵计算余弦相似度。输出的是某商品的相似候选，**不是经过验证的用户推荐系统**；先排除自己，再按相似度降序、名称升序取最多 3 项，只保留正相似度。
- 频繁项集和规则函数只依赖自身参数，不使用外部 `num_transactions`。空输入或无符合阈值规则时，返回字段与数值类型稳定的空表；CSV 中项集按名称排序并序列化为 JSON 数组。

## 可复算示例

- Smartphone 出现在 5 篮，Phone Case 出现在 7 篮，两者共现 5 篮：Smartphone→Phone Case 的 support=`5/15≈0.3333`，confidence=`5/5=1`，lift=`1/(7/15)≈2.1429`，不是 3.2。
- Tablet Case→Tablet 共现 2 篮，前件出现 2 篮，后件出现 3 篮：support=`2/15`、confidence=1、lift=5。
- Laptop→Laptop Bag 共现 3 篮，Laptop 出现 4 篮：confidence=0.75、lift=3.75；两者二值购买余弦相似度=`3/√(4×3)≈0.8660`。

这些只是当前合成样本的共现关系，不能证明因果互补或交叉销售增量。**没有训练/测试拆分、precision@5、召回率或线上效果验证**，不声称“72% precision@5”或“40% 交叉销售机会”。以上示例不是运行测试通过声明。

## 运行

从仓库根目录进入本项目目录后执行：

```bash
cd projects/product-recommendation-analysis
python -m pip install -r requirements.txt
python scripts/analyze.py
```

依赖 pandas、numpy、matplotlib、seaborn、scikit-learn，不依赖 mlxtend。Agg 后端与英文标题支持无 GUI 环境。运行后向 `output/` 写入频繁项集、规则、商品相似矩阵及候选列表等 CSV，并仍导出 `output/recommendation_dashboard.png`。

## Notebook 复用

[analyze.py](<./scripts/analyze.py>) 可安全导入：`load_data(path=None)`、`analyze(df, min_support=0.1, min_confidence=0.3, top_n=3)`；可单用 `build_transactions(df)`、`get_frequent_itemsets(transactions, min_support)`、`get_association_rules(frequent_df, transactions, min_confidence)`、`build_item_similarity(df)`、`get_similar_items(item_sim_df, item, top_n=3)`、`serialize_sequences(table, columns)`。`plot_dashboard(results)` 返回 Figure，仅 `main(data_path=None, output_dir=None)` 负责导出。
