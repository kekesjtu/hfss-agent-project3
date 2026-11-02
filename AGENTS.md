# AGENTS

Project3：Patch antennas array 微带贴片天线阵，AI 协作开发指南。本文档为 AI Agent 提供项目结构、规范说明。

## 目标

1. 参考 [课件 PDF](<docs/04 RF circuit design - projects 2026.pdf>)，[md](docs/Project3_目标与要求.md) 中 Project3 的建模与仿真要求，达到相关指标并留有一定余量；
2. 给出嘉立创商城的 PCB 以及零件的订购所需清单。
3. 指标口径与验收争议点见 [md](docs/Project3_目标与要求.md) 第 5 节。

## 目录结构

| 路径 | 说明 |
|---|---|
| `README.md` | 当前交付、文档与运行入口 |
| `docs/` | 课件 PDF、目标与要求、当前 R3 模型核验报告 |
| `hfss_agent/` | 本机 AEDT/HFSS 环境与链路自检，见 `hfss_agent/README.md` |
| `output/Project3_fabrication_R3/` | 当前审阅交付：PCB、HFSS、制造资料、采购清单与自包含生成脚本 |
| `tmp/YYYY-MM-DD-<task-slug>/` | 任务工作目录、临时脚本、调试数据、日志和求解缓存，不纳入 Git |
| `achive/` | 本机历史归档，不纳入 Git，无须在意 |

## 脚本化运行 HFSS

参考：[hfss_agent](hfss_agent/README.md)。

## 文档规范

- **文档即现状，Git即历史**：历史是 Git 的职责。文档不描述过程或者历史。设计变更时，直接**原地覆写**旧内容，不留历史痕迹。严禁出现“已将 A 替换为 B”、“由于之前存在问题，现重构为…”、“旧逻辑已废弃”等时间轴叙事；

## 工作区整洁规范

### tmp/

作为work目录，一次工作先在这个目录开始。用于存放临时脚本、调试文件和中间产物。所有临时文件必须存放在任务专属子目录中，不得直接放置于 tmp/ 根目录。

目录命名规范 tmp/YYYY-MM-DD-<task-slug>/：

- YYYY-MM-DD：任务目录的创建日期
- task-slug：简短、明确的英文任务标识

### output/

人类最终审阅的，结构干净的最终交付物。包含生成交付物的脚本，HFSS 项目文件夹；不含多余 comment，logs，哈希等等。

## Git 管理

- 跟踪当前规范、文档、依赖锁定、正式生成脚本与 `output/` 交付源文件。
- 本地解释器、虚拟环境、缓存、`tmp/`、`achive/`、AEDT 求解缓存及 KiCad 本机状态由 `.gitignore` 排除。
- 设计变更在当前文件中表达现状，提交记录承担版本历史；不在交付目录堆叠多版压缩包或过程报告。
