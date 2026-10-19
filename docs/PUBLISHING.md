# 发布到 GitHub

## 当前准备内容与边界

本地项目包含合成数据、5 个分析脚本、5 本可执行笔记本、结果表/看板和验证工具。**本地 Git 提交不是远端发布完成。** 只有推送成功且核对远端 `main` 与本地提交一致，才能确认发布。

便携 Git 与 GitHub CLI 如已下载，位于被忽略的 `.tools/`；不需要管理员权限、不加入全局 PATH，也不会被提交。新电脑可自行安装官方 Git 与 GitHub CLI。

## 1. 本地复核

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/validate_portfolio.py
```

检查 [验证报告](../reports/validation.md) 和 [首页](../README.md)。确认没有真实客户信息、密钥、个人历史记录或不愿公开的内容。已配置 [.gitignore](../.gitignore)；它不是自动安全审计的替代品。

本项目使用 [MIT License](../LICENSE)，适用于仓库内代码、文档和合成示例数据。发布时一并提交许可证。

验证会更新报告、结果表和笔记本。先检查改动，再将要发布的内容提交；发布辅助脚本要求工作区干净：

```powershell
git status --short
git diff
git add README.md LICENSE docs projects reports scripts tests requirements.txt .github .gitignore .gitattributes
git diff --cached --check
git diff --cached --stat
git commit -m "Prepare analytics portfolio for publication"
```

首次提交前应配置 Git 作者（见第 3 节）。如果已经提交且没有新改动，可跳过上述提交步骤。脚本或输入数据有修改时，必须重新验证并提交对应报告。

## 2. GitHub 账号授权

发布辅助脚本会使用已安装工具，或回退到本地便携工具。它可以沿用 Windows 已配置的系统代理，但不禁用 TLS 验证。

```powershell
.\scripts\publish_github.ps1 -Login -Visibility Private
```

浏览器授权时，由你在 GitHub 官方设备授权页面输入终端显示的一次性代码。脚本会申请 `workflow` 权限，以便提交随仓库提供的 GitHub Actions 配置。不要向聊天窗口发送密码、访问令牌或恢复代码。ChatGPT/Codex 登录不能替代 GitHub 登录。

如果已有登录但推送提示缺少 `workflow` scope，可在项目根目录按下面命令补充官方授权，然后重新运行发布辅助脚本：

```powershell
.\.tools\gh\bin\gh.exe auth refresh --hostname github.com --scopes workflow
```

如当前系统网络需要代理，请在同一终端设置与你已配置的系统代理一致的 `HTTPS_PROXY`，不要用禁用证书校验来绕过错误。

上面的命令默认建为私有仓库。**如果你明确希望用于公开求职展示**，可改为：

```powershell
.\scripts\publish_github.ps1 -Login -Visibility Public
```

脚本会：

1. 核对 GitHub 当前登录账号。
2. 要求本地已有 `main` 提交且工作区干净，不自动暂存文件。
3. 在该账号下创建 `data-analytics-skills`，设置 `origin`，不覆盖已有远端地址。
4. 正常推送（不用 `--force`），并核对远端 `main` 的提交 SHA。
5. 输出真实仓库 URL、公开范围和核验后的提交号。

如果同名仓库已存在且没有配置 `origin`，它会停止，不会擅自合并或覆盖。确认正确仓库及历史后再手动配置远端。脚本也不会自动改变已存在仓库的公开范围。

## 3. Git 提交作者

原始环境没有 Git 作者配置时，本地初始提交可以使用中性的自动化作者 `Portfolio Setup <portfolio-setup@localhost>`；它不冒充你的姓名、邮箱或 GitHub 身份。

授权后如需让初始提交关联你的 GitHub 账号，可在**首次推送前**按 GitHub 设置页提供的真实姓名和 noreply 邮箱配置，再明确决定是否修改作者：

```powershell
$git = '.\.tools\git\cmd\git.exe'
& $git config --local user.name 'YOUR_GITHUB_NAME'
& $git config --local user.email 'YOUR_VERIFIED_NOREPLY_EMAIL'
# 只有在确认尚未发布且确实需要修改作者时执行下一行：
& $git commit --amend --reset-author --no-edit
```

不要照抄占位符，也不需要把私人邮箱交给助手。发布后不要为了修改作者擅自强制推送历史。

## 4. 发布后检查

- 打开脚本输出的真实 GitHub URL，确认首页、笔记本结果与图片能显示。
- 查看 Actions 中的 `Validate analytics portfolio`。配置已存在不代表 CI 已成功，必须看到实际运行结果。
- 若用于求职，确认仓库可供招聘方访问，再加入简历并置顶。
- 介绍为“合成电商数据分析练习”，不写成真实公司项目、统计显著增长或未实现的 SQL/预测成果。

## 网络或登录失败

若设备授权接口超时，先检查网络/系统代理是否能访问 GitHub；本地验证和提交仍然保留。辅助脚本不会在未授权时创建仓库或上传内容。
