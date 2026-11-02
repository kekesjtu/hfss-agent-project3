# Project3：5.8 GHz 微带贴片天线阵

课程设计为 FR4 四层板上的 1×2 贴片阵列，单元间距 0.5λ₀，含功分馈电网络和 SMA 外接口。当前交付为 **R3 名义首板候选**：制造文件齐备，中心频点及 150 MHz 匹配窗口名义检查通过；板厂叠层/工艺回签、加工与实测尚未完成。

| 入口 | 内容 |
|---|---|
| [AGENTS.md](AGENTS.md) | 项目规范与工作目录约定 |
| [目标与要求](docs/Project3_目标与要求.md) | 课件指标与验收口径 |
| [最新模型核验报告](docs/Project3_最新模型核验报告.md) | R3 当前结果、限制与待完成项 |
| [R3 交付](output/Project3_fabrication_R3/README_制造状态.md) | HFSS、PCB、Gerber、BOM、叠层与装配资料 |
| [复现说明](output/Project3_fabrication_R3/scripts/REPRODUCE.md) | PCB 构建、HFSS 求解和结果分析 |
| [HFSS 环境](hfss_agent/README.md) | 本机 AEDT/PyAEDT 配置与链路自检 |

`tmp/YYYY-MM-DD-<task-slug>/` 存放临时脚本、调试数据和求解缓存；`achive/` 是本机归档。两者和本地 Python 环境均不纳入 Git。`output/` 仅保留当前审阅交付与其生成脚本。

## 环境恢复

本机 AEDT 2025.2 Student、KiCad 10.0，Python 3.12。依赖使用 `pyproject.toml` 与 `uv.lock`：

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.python'
& 'E:/uv/uv.exe' sync --locked --extra analysis
```

`analysis` 包含方向图、数值分析和 Gerber 回读依赖；仅连接 HFSS 时可省略该选项。复现命令将中间结果写到 `tmp/` 任务目录。
