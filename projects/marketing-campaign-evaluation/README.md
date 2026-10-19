# 营销活动：渠道指标与描述性变体比较

使用 [campaign_data.csv](<./data/campaign_data.csv>) 的**合成演示数据**：15 条活动汇总、5 个渠道，各渠道有 Control / VariantA / VariantB。每个 `campaign_id` 只有一行，不能用它把三种变体分为同一个实验。小样本结论不可外推。

## 指标口径

所有汇总指标均**先合计分子分母再相除**，不平均各行比率；分母为零时保留空值/NaN。

| 字段 | 公式与限制 |
|---|---|
| `ctr_pct` | 点击 / 曝光 × 100 |
| `cvr_pct` | 转化 / 点击 × 100 |
| `cpc` / `cpm` | 支出 / 点击；支出 / 曝光 × 1000 |
| `cpa` | 支出 / 转化；没有新客标记，不能声称是新客 CAC |
| `roas` | 给定收入 / 广告支出，单位为倍数 |
| `ad_spend_return_proxy_pct` | (给定收入 − 广告支出) / 广告支出 × 100；**广告支出收益代理指标，不是净利润 ROI** |

给定收入没有可验证的增量归因；未扣商品、履约、人工、退款、税费等非广告成本，不能据此推断净利润或投放因果收益。

## 比较方式与可复算示例

按**相同渠道、活动类型、开始日、结束日和年龄组**分组，再比较组内 variant，包含 Control。列出 CVR 相对 Control 的百分点差与相对百分比差；不把不同渠道直接合并为“变体胜率”。这些观察属性一致仍不等于随机分配，**没有随机实验、独立性检验或统计显著性结论**。

- Email：曝光 30,000、点击 2,950、支出 2,400、收入 14,500、转化 125；CTR≈**9.83%**、CPA=**19.20**、ROAS≈**6.04 倍**、广告支出收益代理≈**504.17%**。本样本 Email 的 CTR 最高，并非 Social Media。
- Email 的 Control CVR=`38/950=4.00%`，VariantB=`45/1020≈4.41%`，差约 **+0.41 个百分点**；这不是显著性或因果提升证明。
- Social Media 的 VariantA CVR≈2.17%，VariantB≈2.04%，不存在“B 在所有渠道胜出”。
- 35–44 岁合计 CVR=`125/2950≈4.24%`，但该年龄组只出现于 Email；年龄、渠道、定向与投放时段混杂，无法分离独立年龄效应。

## 运行

从仓库根目录进入本项目目录后执行：

```bash
cd projects/marketing-campaign-evaluation
python -m pip install -r requirements.txt
python scripts/analyze.py
```

仅依赖 pandas、numpy、matplotlib、seaborn，无需 scipy 统计检验依赖。Agg 后端支持无 GUI；图表使用英文标题。运行后向 `output/` 写入活动/渠道/年龄汇总及变体比较 CSV，并仍导出 `output/campaign_dashboard.png`。兼容旧文件名 `output/ab_test_results.csv`，其内容现在是**描述性比较，不是 A/B 检验结果**。以上示例不是运行测试通过声明。

## Notebook 复用

[analyze.py](<./scripts/analyze.py>) 可安全导入：`load_data(path=None)`、`analyze(df)`、`add_metrics(table)`、`aggregate_metrics(data, group_columns)`、`compare_variants(df)`；结果中的 `variant_comparison` 即修正后的组内比较表。`plot_dashboard(results)` 返回 Figure，仅 `main(data_path=None, output_dir=None)` 导出文件。
