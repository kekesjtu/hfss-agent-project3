# HFSS 自动化环境

本目录提供本机 Python/PyAEDT 到 AEDT/HFSS 的启动和链路自检。当前环境为 Python 3.12.14、PyAEDT 1.9.0、AEDT 2025.2 Student；AEDT 安装在 `E:/Program Files/ANSYS Student/v252/AnsysEM`，uv 位于 `E:/uv/uv.exe`。

| 文件 | 用途 |
|---|---|
| `run.ps1` | 定位仓库、设置本地缓存与 AEDT 环境、按 uv.lock 运行脚本 |
| `smoke_test.py` | 新建真空腔体、本征模求解、导出与解析频率核对 |
| `../pyproject.toml`、`../uv.lock`、`../.python-version` | 依赖与 Python 版本约束 |

## 运行

在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File hfss_agent/run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File hfss_agent/run.ps1 -Script smoke_test.py --no-solve
powershell -NoProfile -ExecutionPolicy Bypass -File hfss_agent/run.ps1 -Script smoke_test.py --non-graphical
```

自检为 100×80×40 mm 真空 PEC 腔体，单模本征模，2 核、最多 4 次自适应；解析基模约 2.39951 GHz，相对误差超过 5% 判失败。只释放本次启动的 AEDT 会话。

输出在 `tmp/YYYY-MM-DD-hfss-smoke-test/<运行标识>/`，含 `AgentCavity.aedt`、求解缓存、`aedt.log`、`eigenmode.csv` 和 `result.json`；同一任务目录下 `latest_result.json` 为最近一次自检摘要。自检产物不进入 `output/`。

## 环境恢复

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.python'
& 'E:/uv/uv.exe' sync --locked
```

需要 R3 方向图分析与 CAM 检查时使用 `sync --locked --extra analysis`，然后直接调用项目 Python，见 [R3 复现说明](../output/Project3_fabrication_R3/scripts/REPRODUCE.md)。`run.ps1` 可用 `-Script` 指定其他脚本，相对路径按仓库根目录解析。

Python 固定 3.12 系列；移动项目或重建环境时按新位置重新执行 uv sync。Python 导入使用 `from ansys.aedt.core import Desktop, Hfss, settings`。`.venv/`、`.python/`、`.uv-cache/` 不纳入 Git。

## 脚本约定

- 使用 ASCII 代码注释，避免 Windows PowerShell 5.1 的无 BOM 中文解析问题。
- 每次运行先建立 `tmp/YYYY-MM-DD-<task-slug>/` 任务目录；显式设置 `settings.aedt_log_file`，日志和缓存写到任务内。
- 使用 `settings.use_grpc_api=True`、`settings.grpc_secure_mode=False`，结束时释放自己启动的会话。
- 人类审阅的项目交付、生成脚本与原生 HFSS 工程位于 `output/Project3_fabrication_R3/`。
