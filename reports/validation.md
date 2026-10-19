# 运行验证报告

- 执行时间（UTC）：2026-10-19T10:35:36+00:00
- Python：3.11.5；平台：Windows
- 所有子脚本及笔记本均使用启动验证器的同一个 Python 环境。
- `passed` 表示本次实际执行通过，不代表真实商业效果或统计有效性。

| 项目 | 分析脚本 | Jupyter 全单元执行 |
|---|---|---|
| ecommerce-sales-analysis | passed | passed |
| user-behavior-analysis | passed | passed |
| marketing-campaign-evaluation | passed | passed |
| customer-segmentation | passed | passed |
| product-recommendation-analysis | passed | passed |

## 环境依赖

```text
numpy==1.26.4
pandas==3.0.3
matplotlib==3.10.9
seaborn==0.13.2
scipy==1.15.2
scikit-learn==1.6.1
jupyter==1.1.1
notebook==7.5.6
nbformat==5.10.4
nbclient==0.10.4
nbconvert==7.17.1
ipykernel==7.2.0
```

## 复现

```bash
python -m unittest discover -s tests -v
python scripts/validate_portfolio.py
```

各输入数据及分析脚本的 SHA-256、耗时和生成文件清单见 [JSON 记录](validation.json)。
详细日志保存在本地 `reports/logs/`（不纳入 Git）。
