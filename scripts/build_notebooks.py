"""Build the five showcase notebooks from shared, tested analysis modules.

This generator only replaces the five named notebooks below. Execute notebooks
separately with scripts/validate_portfolio.py; generation is not execution.
"""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    {
        "slug": "ecommerce-sales-analysis",
        "notebook": "sales_analysis.ipynb",
        "title": "电商销售分析",
        "question": "销售额、客单价、月份、类别和地区的表现如何？",
        "method": "订单销售额 = quantity × unit_price；总销售额按订单金额求和；客单价 = 总销售额 / 去重订单数。这里只描述样本，不把一年数据中的波动当作已经证实的季节性。",
        "check": """orders = df.assign(revenue=df['quantity'] * df['unit_price'])
summary = pd.DataFrame([{
    'orders': orders['order_id'].nunique(),
    'revenue': orders['revenue'].sum(),
    'average_order_value': orders['revenue'].sum() / orders['order_id'].nunique(),
}])
display(summary.round(2))
category_check = orders.groupby('product_category')['revenue'].sum().sort_values(ascending=False)
display(category_check.to_frame())""",
        "interpretation": "当前合成样本共 50 单，总销售额 80,860 元；Electronics 高于 Home，Fashion 排第三。11 月销售额较高只是样本描述。没有成本、退货和流量数据，不能由销售额直接推断利润、营销效果或因果关系。下一步应接入更大规模真实数据、补齐退货/成本口径，并在建议落地后衡量结果。",
    },
    {
        "slug": "user-behavior-analysis",
        "notebook": "behavior_analysis.ipynb",
        "title": "用户行为与会话漏斗",
        "question": "从浏览到购买的同一会话有序转化是多少？重复事件会怎样影响指标？",
        "method": "业务漏斗按同一 session_id 内的时间顺序依次匹配 page_view → add_to_cart → checkout → purchase，每个阶段每个会话最多计一次。下方事件覆盖表仅用于对照，不是有序漏斗。",
        "check": """event_coverage = df.groupby('event_type', sort=True).agg(
    event_count=('session_id', 'size'),
    unique_sessions=('session_id', 'nunique'),
    unique_users=('user_id', 'nunique'),
)
display(event_coverage)
print('Distinct sessions:', df['session_id'].nunique())
print('Distinct users:', df['user_id'].nunique())""",
        "interpretation": "样本只有 10 个会话、10 位用户。重复浏览或加购不能当作更多用户；应将事件次数与会话漏斗分开报告。没有跨期回访、订单金额或用户注册数据，不能声称已完成留存分析、复购分析或消费能力比较。建议先完善埋点和会话口径，再按设备定位流失环节，并用更大样本验证。",
    },
    {
        "slug": "marketing-campaign-evaluation",
        "notebook": "campaign_analysis.ipynb",
        "title": "营销渠道效果与变体描述性比较",
        "question": "各渠道的 CTR、CPA、ROAS 怎样？同渠道内不同变体的观测表现如何？",
        "method": "CTR = 点击数 / 曝光数；CVR = 转化数 / 点击数；CPA = 广告支出 / 转化数；ROAS = 营收 / 广告支出。聚合后使用分子分母的总和相除，而非简单平均各行比率。仅凭变体标签不能认定随机 A/B 实验，更不能宣称统计显著。",
        "check": """channel_check = df.groupby('channel')[['impressions', 'clicks', 'spend', 'revenue', 'conversions']].sum()
channel_check['ctr_pct'] = channel_check['clicks'] / channel_check['impressions'] * 100
channel_check['cpa'] = channel_check['spend'] / channel_check['conversions']
channel_check['roas'] = channel_check['revenue'] / channel_check['spend']
display(channel_check.round(3))""",
        "interpretation": "Email 在这份合成样本中的 CTR 约为 9.83%、CPA 为 19.20、ROAS 约为 6.04。广告支出回报代理不等同于净利润 ROI，也没有新客户信息支持 CAC。渠道和年龄段存在混杂，不能把差异归因于年龄；变体比较只报告观测差异，不生成无依据的显著性结论。",
    },
    {
        "slug": "customer-segmentation",
        "notebook": "segmentation_analysis.ipynb",
        "title": "RFM 客户细分与聚类画像",
        "question": "如何用消费最近度、频次和金额形成可解释分层，并对照聚类画像？",
        "method": "R 越小越好，F/M 越大越好。RFM 分数和业务规则分层与 K-Means 聚类是两种不同方法；重复值应同分，不能为了凑等人数强行拆开。聚类前标准化，固定随机种子，k=4 是演示选择而非已经验证的最优值。",
        "check": """rfm_columns = ['recency_days', 'frequency', 'monetary']
display(df[rfm_columns].describe().round(2))
print('Customers:', df['customer_id'].nunique())
print('Observed monetary total:', df['monetary'].sum())""",
        "interpretation": "这 20 位合成客户只用于演示分析流程，规则可能使某些分组为空，不应预先承诺每组占比。Champions 等名称是业务标签，不是已验证的真实用户类型。现有数据没有未来价值目标或流失标签，因此没有完成 CLV 预测或流失预测。建议用真实订单计算窗口化 RFM，并用后续实验衡量分层运营收益。",
    },
    {
        "slug": "product-recommendation-analysis",
        "notebook": "recommendation_analysis.ipynb",
        "title": "购物篮关联规则与商品相似度",
        "question": "哪些商品在购物篮内共同出现？高 lift 规则和相似商品如何解释？",
        "method": "Support 是项集出现的购物篮占比；Confidence(A→B) = support(A∪B) / support(A)；Lift = confidence / support(B)。演示代码穷举小购物篮子集，不冒称 Apriori；商品余弦相似度基于二值用户—商品矩阵，不等同于经过离线评估的推荐系统。",
        "check": """baskets = df.groupby('transaction_id')['product_name'].agg(lambda values: sorted(set(values)))
print('Baskets:', len(baskets))
print('Distinct product names:', df['product_name'].nunique())
display(baskets.to_frame('items').head())
display(baskets.map(len).value_counts().sort_index().to_frame('basket_count'))""",
        "interpretation": "样本有 15 个购物篮。Smartphone → Phone Case 的 confidence 为 1，lift 约为 2.14，但小样本的高 lift 不是销售提升保证。按 product_name 合并同名商品是演示口径；上线前必须清理商品主数据、核对同名不同 ID。没有训练/测试集划分或离线评估，不声称 precision@5、线上转化提升或已实现生产推荐。",
    },
]


def build(project):
    slug = project['slug']
    setup = f"""from pathlib import Path
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Image
from io import BytesIO

# Works when Jupyter starts at the repo root, project directory or notebook directory.
start = Path.cwd().resolve()
root = next((p for p in (start, *start.parents)
             if (p / 'projects' / {slug!r} / 'scripts' / 'analyze.py').is_file()), None)
if root is None:
    raise FileNotFoundError('请在本仓库内启动 Jupyter，或先切换到仓库根目录。')
project_dir = root / 'projects' / {slug!r}
module_path = project_dir / 'scripts' / 'analyze.py'
spec = importlib.util.spec_from_file_location({slug.replace('-', '_')!r}, module_path)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
df = analysis.load_data()
assert not df.empty
print('Input rows:', len(df))
display(df.head())
"""
    cells = [
        nbf.v4.new_markdown_cell(f"# {project['title']}\n\n**业务问题：** {project['question']}\n\n> 本项目使用仓库内的合成教学数据，不代表真实企业业绩。笔记本复用同目录分析模块，确保脚本、结果表与图表口径一致。请使用 Python 3.11 并从仓库内部启动 Jupyter。"),
        nbf.v4.new_markdown_cell("## 1. 读取数据\n\n根据当前目录向上定位仓库，不在 notebook 中依赖 `__file__`，也不硬编码电脑路径。"),
        nbf.v4.new_code_cell(setup),
        nbf.v4.new_markdown_cell("## 2. 数据质量检查\n\n报告缺失与整行重复。重复事件可能是真实行为，不应未经业务判断直接删除。分析模块进一步校验必要字段和数值范围。"),
        nbf.v4.new_code_cell("display(df.isna().sum().to_frame('missing_count'))\nprint('Exact duplicate rows:', int(df.duplicated().sum()))"),
        nbf.v4.new_markdown_cell("## 3. 指标定义与独立复算\n\n" + project['method']),
        nbf.v4.new_code_cell(project['check']),
        nbf.v4.new_markdown_cell("## 4. 完整分析结果\n\n下面调用可复用的 `analyze(df)`，展示结果表；业务口径详见相邻项目说明和脚本。"),
        nbf.v4.new_code_cell("results = analysis.analyze(df)\nassert isinstance(results, dict) and results\nfor name, table in results.items():\n    print(f'--- {name} ---')\n    with pd.option_context('display.max_rows', 50, 'display.max_columns', 20):\n        display(table)"),
        nbf.v4.new_markdown_cell("## 5. 可视化\n\n图表与脚本使用同一结果字典，不另写一套计算逻辑。"),
        nbf.v4.new_code_cell("fig = analysis.plot_dashboard(results)\n# Explicit PNG display also works with the headless Agg backend.\nimage = BytesIO()\nfig.savefig(image, format='png', dpi=110, bbox_inches='tight')\ndisplay(Image(data=image.getvalue()))\nplt.close(fig)"),
        nbf.v4.new_markdown_cell("## 6. 结论、建议与边界\n\n" + project['interpretation'] + "\n\n**复现检查：** 从首个代码单元开始运行全部单元；仓库统一验证命令为 `python scripts/validate_portfolio.py`。生成笔记本和实际执行笔记本是两个不同步骤，执行结果以验证报告为准。"),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    path = ROOT / 'projects' / slug / 'notebooks' / project['notebook']
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.validate(notebook)
    nbf.write(notebook, path)
    print('Generated:', path.relative_to(ROOT).as_posix())


if __name__ == '__main__':
    for project in PROJECTS:
        build(project)
