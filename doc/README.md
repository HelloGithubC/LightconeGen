# ForHR4 Documentation

本目录存放针对 **Horizon Run 4 (HR4)** 模拟构建 **DESI DR2 BGS** 光锥及系统误差估计的技术文档与策略规范。

## 文档索引

* [MODULE.md](MODULE.md)：可导入 Python 包的接口、两种结果模式、重建/数据点筛选和实际核对清单。

* [REPOSITORY.md](REPOSITORY.md)：独立仓库 LightconeGen 的位置、Git 管理方式、文件清单及维护命令。

* [HR4_BGS_Lightcone_Strategy.md](HR4_BGS_Lightcone_Strategy.md):
  **HR4–BGS 光锥及 tomographic AP 系统误差任务交接文档**。
  - HR4 宇宙学及三个观测红移区间与 snapshot 的对应关系
  - BGS mask、completeness 与各红移区间独立构造光锥的约定
  - 周期边界、observer placement、红移空间和 MCF 边界处理
  - DD、DR、RR 的跨 mock 加权汇总与 `LSS_python.xismu` 分析配置
  - 尚待明确的实现细节和 HR4 数据不可用时的验证安排

* [朝向几何实验](experiments/direct_grid.md):
  直接网格 pipeline 的运行方式、旋转策略、指标、依赖及实际案例文件清单。

* [FFT 联合放置](experiments/fft_placement.md)：联合搜索方法、参数、输入/输出清单和 N=5 实际运行。

* [FFT 续跑](experiments/fft_resume.md)：续跑流程、零重叠选优依据和 N=15 实际运行。

实验报告统一放在 `doc/experiments/`；实际产物继续位于被 Git 忽略的 `tests/runs/`，管理约定见 [tests 索引](../tests/README.md)。

旧五个脚本已原样移到 `tools/legacy/`，当前运行入口见[工具说明](../tools/README.md)。历史报告中的旧源码路径属于当时记录。
