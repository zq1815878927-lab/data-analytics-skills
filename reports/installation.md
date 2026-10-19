# 隔离环境安装验证

验证日期：2026-10-19；平台：Windows；Python：3.11.5。

本次使用新建虚拟环境，`include-system-site-packages = false`，从包仓库安装根目录 `requirements.txt`，没有复用系统 Python 的已安装包。

| 检查 | 结果 |
|---|---|
| `python -m pip install -r requirements.txt` | 成功 |
| `python -m pip check` | 无依赖冲突 |
| `python -m unittest discover -s tests -v` | 29 项通过 |
| `python scripts/validate_portfolio.py` | 5 个脚本及 5 本笔记本全部通过 |

本次执行生成的版本、时间及输入/源码哈希见 [验证记录](validation.json)，汇总见 [运行报告](validation.md)。测试环境位于被 Git 忽略的 `.tools/release-venv/`；新电脑按首页说明创建自己的 `.venv` 即可。

这是 Windows 本地验证记录。GitHub Actions 的 Windows/Linux 运行结果需在首次推送后单独检查。
