# 客户分组：RFM 规则与示例聚类

使用 [customer_data.csv](<./data/customer_data.csv>) 的**合成演示快照**：20 位客户，已给定最近购买天数、购买频次、累计金额。没有快照日期、完整交易历史或后续结果，不能重新验证观察窗口、估计 CLV 或确认真实流失。小样本结论不可外推。

## RFM 评分与规则

- R 越小越好，F/M 越大越好；使用 `qcut(..., duplicates="drop")`，直接按值分箱，**不按行号拆分重复值，同值始终同分**。
- 原本目标为 1–5 分。重复分位点导致区间减少时，把区间位置单调映射到 1–5；常量列或只剩一个有效区间时给中性 3 分。分数或分组不保证等人数，也不保证每个分数出现。
- 依次应用下列示例规则，前面的规则优先：

| 规则标签 | 条件 |
|---|---|
| Champions | R≥4、F≥4、M≥4 |
| Loyal | R≥3、F≥3、M≥3 |
| At-Risk | R≤2、F≥3 |
| New/Leads | R≥4、F≤2 |
| Others | 其余 |

这些只是业务规则标签，**不是已验证的流失风险、新客身份或未来价值事实**；五种规则标签不保证都会出现。

## 可复算示例与聚类限制

- 当前输入金额合计 **596,800**。按上述规则：Champions **8** 人、Loyal **3** 人、Others **9** 人；At-Risk 与 New/Leads 没有触发。
- Champions 给定累计金额合计 **491,000**；这不是未来收入或 CLV。C006 的 R/F/M 分数为 `555`。
- 对 R/F/M 使用 `StandardScaler` 后做 K-means，`random_state=42`、`n_init=10`。默认 **k=4 只是可配置示例，不是已证明最优**；额外导出 k=2…7 的惯性值供检查，但不自动宣称找到了“肘点”。
- 聚类 ID 仅为显示标签，按均值画像重排；规则分组与聚类是两套不同方法。没有依据声称频次正在下降、客户已经流失或营销动作能产生增益。

## 运行

从仓库根目录进入本项目目录后执行：

```bash
cd projects/customer-segmentation
python -m pip install -r requirements.txt
python scripts/analyze.py
```

依赖 pandas、numpy、matplotlib、seaborn、scikit-learn；无新外部依赖。Agg 无 GUI 后端与英文标题避免系统中文字体要求。运行后向 `output/` 写入客户评分、规则汇总、聚类画像、惯性诊断等 CSV，并仍导出 `output/segmentation_dashboard.png`。上述示例不是运行测试通过声明。

## Notebook 复用

[analyze.py](<./scripts/analyze.py>) 导入时不读写文件：`load_data(path=None)`；`analyze(df, n_clusters=4)` 返回结果表字典；`quantile_score(values, higher_is_better=True, bins=5)`、`assign_rfm_scores(df)`、`segment_customers(row)` 可单独复用。`cluster_customers(df, n_clusters=4, random_state=42)` 返回客户表、画像、惯性表。`plot_dashboard(results)` 返回 Figure，仅 `main(data_path=None, output_dir=None)` 落盘。
