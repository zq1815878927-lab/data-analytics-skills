# 用户行为：同会话有序漏斗

使用 [user_events.csv](<./data/user_events.csv>) 的**合成演示数据**：35 条事件、10 位用户、10 个会话，日期为 2024-01-05 至 2024-01-13。用于展示事件清洗、会话漏斗及日活口径，不代表真实平台表现；小样本结论不可外推。

## 漏斗与可复算示例

漏斗阶段：`page_view → add_to_cart → checkout → purchase`。

1. 先移除六个输入字段完全相同的重复事件；一个 `session_id` 必须只属于同一用户、设备和区域。
2. 每个会话从第一个阶段开始，依次匹配该阶段最早的合格事件；后一步时间必须**严格晚于**前一步。同一时刻无法证明顺序，不推进阶段；不同会话不拼接。
3. 每个会话每阶段最多计一次；重复浏览、重复加购不能当成新增用户或新增会话。漏斗单位为**会话数，不是事件数或人数**。

| 阶段 | 完成有序前缀的会话数 | 相对上一步转化率 |
|---|---:|---:|
| 浏览 | 10 | 10 / 全部 10 会话 = 100% |
| 加购 | 9 | 9 / 10 = 90% |
| 结账 | 7 | 7 / 9 ≈ 77.78% |
| 购买 | 5 | 5 / 7 ≈ 71.43% |

整体转化率为 **5 / 10 = 50%**，不是事件数 `5 / 13`。Mobile 为 3/5=60%，Desktop 为 2/5=40%，均为购买前缀会话数 / 浏览前缀会话数，只描述本样本。分母为零时导出空值/NaN，不编造 0% 或无穷大。

- 日活：按事件自然日去重 `user_id`；不等于会话数。
- 观测时长：`(末事件时间 - 首事件时间).total_seconds() / 60`，支持跨日。S003 为 65 分钟；单事件会话的观测跨度为 0，不代表真实停留时长为 0。
- 数据没有留存观察窗、新老用户标记、复购历史或订单金额，**不输出留存、复购、消费能力、确定的弃购率或设备因果效应**。

## 运行

从仓库根目录进入本项目目录后执行：

```bash
cd projects/user-behavior-analysis
python -m pip install -r requirements.txt
python scripts/analyze.py
```

仅依赖 pandas、numpy、matplotlib、seaborn；使用 Agg 无 GUI 后端及英文标题。运行后向 `output/` 写入会话漏斗、设备转化、日活、会话匹配与时长等 CSV，并仍导出 `output/behavior_dashboard.png`。事件次数另存为独立表，不与漏斗计数混淆。以上数值为可复算示例，不是运行测试通过声明。

## Notebook 复用

[analyze.py](<./scripts/analyze.py>) 导入时不读写文件：`load_data(path=None)` 读取；`analyze(df)` 返回表字典。可单独复用 `prepare_data(df)`、`match_ordered_funnel(df, stages=FUNNEL_STAGES)`、`summarize_funnel(sessions)`、`safe_ratio(numerator, denominator)`。`plot_dashboard(results)` 返回 Figure；仅 `main(data_path=None, output_dir=None)` 导出文件。
