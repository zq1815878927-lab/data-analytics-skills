# 电商销售描述性分析

使用 [sales_data.csv](<./data/sales_data.csv>) 的**合成演示数据**练习分组汇总与可视化：2024 年 50 行订单，一行一单。没有折扣、退款或成本字段，不能把订单金额解释为净收入或利润。小样本结论不可外推。

## 指标口径与可复算示例

- `revenue = quantity × unit_price`：名义订单金额；订单数按唯一 `order_id` 计数，脚本拒绝重复订单 ID。
- 当前样本共 **50 单、60 件，订单金额 80,860.00**；客单金额为 `80860 / 50 = 1617.20`。
- 类别金额排序为 **Electronics 54,778 > Home 17,313 > Fashion 8,769**，并非 Electronics / Fashion 前二。
- 11 月金额 20,651，12 月 14,289；第四季度合计 36,525，占全年样本约 **45.17%**。这只是观察到的月份差异：**仅一年、50 单，不能证明节假日效应或重复季节性**。
- West 金额为 22,824，样本只有 4 个区域，不存在“Top 5 区域贡献 60%”的结论。

金额占比的分母是全部样本订单金额；若总金额为零，占比保留为缺失值，而不是无穷大。表格按日期或“指标降序、名称升序”确定性排序。

## 运行

从仓库根目录进入本项目目录后执行：

```bash
cd projects/ecommerce-sales-analysis
python -m pip install -r requirements.txt
python scripts/analyze.py
```

仅依赖 pandas、numpy、matplotlib、seaborn。绘图使用无 GUI 的 Agg 后端、内置 DejaVu Sans 字体和英文标题。

脚本运行后向 `output/` 写入月度、类别、区域、商品与支付方式汇总、总览 CSV，并仍导出 `output/sales_dashboard.png`；本说明列出的数值是输入数据与公式的核对示例，不是运行测试通过声明。

## Notebook 复用

[analyze.py](<./scripts/analyze.py>) 可安全导入，不会在导入时读取 CSV 或写文件：

- `load_data(path=None)`：读取并校验订单。
- `analyze(df)`：返回 `overview`、`monthly_sales`、`category_sales`、`region_sales`、`top_products`、`payment_methods` 表。
- `summarize_sales(data, group_column)`：复用分组汇总，传入 `prepare_data(df)` 的结果。
- `plot_dashboard(results)`：返回 Figure；`main(data_path=None, output_dir=None)` 才负责落盘。

下一步若使用真实业务数据，需要更长时间跨度、完整订单明细和退款/成本定义，才能讨论季节性及经营收益。
