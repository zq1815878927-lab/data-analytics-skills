"""Execute every analysis and notebook using this Python interpreter.

Run from any directory:
    python scripts/validate_portfolio.py
    python scripts/validate_portfolio.py --scripts-only

Logs are local/ignored. The JSON and Markdown reports omit host-specific paths.
Notebook execution uses a project-private kernelspec, never an unrelated default
Python kernel. Existing notebook outputs are replaced only after a successful run.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    ('ecommerce-sales-analysis', 'sales_analysis.ipynb', 'sales_dashboard.png'),
    ('user-behavior-analysis', 'behavior_analysis.ipynb', 'behavior_dashboard.png'),
    ('marketing-campaign-evaluation', 'campaign_analysis.ipynb', 'campaign_dashboard.png'),
    ('customer-segmentation', 'segmentation_analysis.ipynb', 'segmentation_dashboard.png'),
    ('product-recommendation-analysis', 'recommendation_analysis.ipynb', 'recommendation_dashboard.png'),
]
PACKAGES = ['numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy', 'scikit-learn',
            'jupyter', 'notebook', 'nbformat', 'nbclient', 'nbconvert', 'ipykernel']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short_error(error):
    return str(error).replace(str(ROOT), '<repo>').replace(str(Path.home()), '<home>')[-3000:]


def run_script(project, dashboard, log_dir):
    path = project / 'scripts' / 'analyze.py'
    started = time.time()
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'MPLBACKEND': 'Agg'}
    completed = subprocess.run(
        [sys.executable, str(path)], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180,
    )
    log = log_dir / f'{project.name}.log'
    log.write_text(completed.stdout + '\n' + completed.stderr, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError(f'Exit code {completed.returncode}; see reports/logs/{log.name}')
    output = project / 'output'
    png = output / dashboard
    if not png.is_file() or png.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        raise AssertionError(f'Missing or invalid PNG: {dashboard}')
    if png.stat().st_mtime < started - 1:
        raise AssertionError(f'Dashboard was not regenerated: {dashboard}')
    csvs = sorted(output.glob('*.csv'))
    if not csvs or any(p.stat().st_size == 0 for p in csvs):
        raise AssertionError('Missing or empty CSV output')
    return {
        'status': 'passed', 'seconds': round(time.time() - started, 2),
        'dashboard': png.relative_to(ROOT).as_posix(),
        'csv_files': [p.relative_to(ROOT).as_posix() for p in csvs],
        'source_sha256': digest(path),
        'data_sha256': {p.name: digest(p) for p in sorted((project / 'data').glob('*.csv'))},
    }


def execute_notebook(path, kernel_root):
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager

    nb = nbformat.read(path, as_version=4)
    nbformat.validate(nb)
    for cell in nb.cells:
        if cell.cell_type == 'code':
            cell.outputs = []
            cell.execution_count = None
    manager = KernelSpecManager(kernel_dirs=[str(kernel_root)])
    km = KernelManager(kernel_name='portfolio-validation', kernel_spec_manager=manager)
    client = NotebookClient(
        nb, km=km, timeout=180, allow_errors=False,
        resources={'metadata': {'path': str(path.parent)}},
    )
    started = time.time()
    client.execute(cleanup_kc=True)
    code_cells = [c for c in nb.cells if c.cell_type == 'code']
    if not code_cells or any(c.execution_count is None for c in code_cells):
        raise AssertionError('Some code cells were not executed')
    if any(o.output_type == 'error' for c in code_cells for o in c.outputs):
        raise AssertionError('Notebook contains an error output')
    image_count = sum('image/png' in o.get('data', {}) for c in code_cells for o in c.outputs)
    if image_count < 1:
        raise AssertionError('Notebook contains no rendered dashboard')
    for cell in code_cells:
        cell.metadata.pop('execution', None)
    nbformat.validate(nb)
    nbformat.write(nb, path)
    return {
        'status': 'passed', 'seconds': round(time.time() - started, 2),
        'executed_code_cells': len(code_cells), 'embedded_png_outputs': image_count,
    }


def write_reports(report):
    report_dir = ROOT / 'reports'
    report_dir.mkdir(exist_ok=True)
    (report_dir / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 运行验证报告', '', f"- 执行时间（UTC）：{report['executed_at_utc']}",
        f"- Python：{report['python']}；平台：{report['platform']}",
        '- 所有子脚本及笔记本均使用启动验证器的同一个 Python 环境。',
        '- `passed` 表示本次实际执行通过，不代表真实商业效果或统计有效性。', '',
        '| 项目 | 分析脚本 | Jupyter 全单元执行 |', '|---|---|---|',
    ]
    for result in report['projects']:
        lines.append(f"| {result['project']} | {result['script']['status']} | {result['notebook']['status']} |")
    lines += ['', '## 环境依赖', '', '```text']
    lines += [f'{name}=={version}' for name, version in report['packages'].items()]
    lines += ['```', '', '## 复现', '', '```bash', 'python -m unittest discover -s tests -v',
              'python scripts/validate_portfolio.py', '```', '',
              '各输入数据及分析脚本的 SHA-256、耗时和生成文件清单见 [JSON 记录](validation.json)。',
              '详细日志保存在本地 `reports/logs/`（不纳入 Git）。']
    for result in report['projects']:
        for kind in ['script', 'notebook']:
            if result[kind]['status'] == 'failed':
                lines += ['', f"### {result['project']} / {kind} 错误", '', '```text', result[kind]['error'], '```']
    (report_dir / 'validation.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scripts-only', action='store_true', help='Skip Jupyter execution for a quick script smoke test')
    args = parser.parse_args()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    log_dir = ROOT / 'reports' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    kernel_root = ROOT / '.tools' / 'kernels'
    kernel = kernel_root / 'portfolio-validation'
    kernel.mkdir(parents=True, exist_ok=True)
    (kernel / 'kernel.json').write_text(json.dumps({
        'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
        'display_name': 'Portfolio validation', 'language': 'python',
        'env': {'PYTHONIOENCODING': 'utf-8', 'MPLBACKEND': 'Agg'},
    }), encoding='utf-8')
    report = {
        'executed_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'python': platform.python_version(), 'platform': platform.system(),
        'packages': {name: importlib.metadata.version(name) for name in PACKAGES},
        'projects': [],
    }
    failed = False
    for slug, notebook, dashboard in PROJECTS:
        project = ROOT / 'projects' / slug
        result = {'project': slug}
        print(f'[{slug}] executing script', flush=True)
        try:
            result['script'] = run_script(project, dashboard, log_dir)
            print('  script: passed', flush=True)
        except Exception as error:
            failed = True
            result['script'] = {'status': 'failed', 'error': short_error(error)}
            print(f'  script: failed: {short_error(error)}', flush=True)
        if args.scripts_only:
            result['notebook'] = {'status': 'skipped'}
        else:
            print(f'[{slug}] executing notebook', flush=True)
            try:
                result['notebook'] = execute_notebook(project / 'notebooks' / notebook, kernel_root)
                print('  notebook: passed', flush=True)
            except Exception as error:
                failed = True
                result['notebook'] = {'status': 'failed', 'error': short_error(error)}
                print(f'  notebook: failed: {short_error(error)}', flush=True)
        report['projects'].append(result)
    report['status'] = 'failed' if failed else 'passed'
    report['notebooks_executed'] = not args.scripts_only
    write_reports(report)
    print('Reports: reports/validation.md and reports/validation.json', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
