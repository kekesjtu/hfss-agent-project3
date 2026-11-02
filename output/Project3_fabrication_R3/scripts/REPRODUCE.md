# R3 交付复现

在仓库根目录执行，使用 Python 3.12、AEDT 2025.2 Student 和 KiCad 10.0。脚本资源位于本目录 `assets/`，无需 `continuation`、本机归档或历史试算目录。

## Python 依赖

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.python'
& 'E:/uv/uv.exe' sync --locked --extra analysis
```

HFSS 与分析使用 `.venv/Scripts/python.exe`；PCB 建模使用 KiCad 自带 Python，不能混用 `pcbnew` 环境。`hfss_agent/run.ps1` 的默认环境只含 HFSS 依赖，分析命令按本页直接调用项目 Python。

## PCB、制造文件与核验

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File output/Project3_fabrication_R3/scripts/rebuild_pcb.ps1
```

默认将候选及检查数据写入 `tmp/YYYY-MM-DD-r3-pcb/<运行标识>/`；可用 `-BuildDirectory` 指定仓库 `tmp/` 下不存在的任务子目录，用 `-KiCadBin` 指定 KiCad 的 bin 目录。

流程包含原生板/封装/规则生成、DRC、Gerber/钻孔/坐标/电测网表/STEP 导出、官方 SMA 封装比较、普通铜板边规则负向对照、四铜层和钻孔 CAM 回读、HFSS 顶面 RF 铜形配准，以及裸板 ZIP 生成。负向对照板故意违规，仅存 `diagnostics/`，不用于加工。候选检查通过后仍需审阅工艺和放行状态；脚本不自动替换当前交付。

`package_gerber.py <候选目录>` 可单独生成根目录含 10 个制造文件的 ZIP。BOM、叠层和装配文件由 `build_pcb.py` 生成；核对结果不代表板厂回签或实测。

## HFSS 模型与分析

```powershell
.venv/Scripts/python.exe output/Project3_fabrication_R3/scripts/run_hfss.py --show-command
.venv/Scripts/python.exe output/Project3_fabrication_R3/scripts/run_hfss.py
```

`r3_hfss.json` 保存名义参数，`hfss_model.py` 含展开后的实际几何和官方 SMA 组件插入逻辑。运行写入 `tmp/YYYY-MM-DD-r3-hfss/<运行标识>/`，日志固定在该任务目录，独立 AEDT 会话在结束时释放。网格/收敛要求为 ΔS≤0.015、连续两次；Student 许可可能限制进一步加密。

对命令末尾 `RUN=` 给出的实际运行目录执行：

```powershell
$runDirectory = 'tmp/YYYY-MM-DD-r3-hfss/实际运行标识'
.venv/Scripts/python.exe output/Project3_fabrication_R3/scripts/summarize_full_sma.py $runDirectory
.venv/Scripts/python.exe output/Project3_fabrication_R3/scripts/inspect_mainbeam.py $runDirectory
```

分析将终端参数的列名归一为 P1，保留数值与原始终端文件，生成 `metrics.json` 和三频点方向图诊断。完整求解缓存留在本次 `tmp/` 目录。当前交付中的 `.aedt` 可直接打开，导出 CSV/Touchstone 可直接审阅；交付不包含完整场缓存，重新提取场需运行求解。

模型范围见 [MODEL_SCOPE.md](../HFSS_full_SMA/MODEL_SCOPE.md)，官方 CAD 来源与使用条件见 [CAD_MODEL_SOURCES.md](../CAD_MODEL_SOURCES.md)。制造候选以当前 `FABRICATION_NOTES.md` 为工艺依据。
