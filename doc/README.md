# ForHR4 Documentation

本目录存放针对 **Horizon Run 4 (HR4)** 模拟构建 **DESI DR2 BGS** 光锥及系统误差估计的技术文档与策略规范。

## 文档索引

* [REPOSITORY.md](REPOSITORY.md)：独立仓库 LightconeGen 的位置、Git 管理方式、文件清单及维护命令。

* [HR4_BGS_Lightcone_Strategy.md](HR4_BGS_Lightcone_Strategy.md):
  **HR4–BGS 光锥及 tomographic AP 系统误差任务交接文档**。
  - HR4 宇宙学及三个观测红移区间与 snapshot 的对应关系
  - BGS mask、completeness 与各红移区间独立构造光锥的约定
  - 周期边界、observer placement、红移空间和 MCF 边界处理
  - DD、DR、RR 的跨 mock 加权汇总与 `LSS_python.xismu` 分析配置
  - 尚待明确的实现细节和 HR4 数据不可用时的验证安排

* [朝向几何实验](../tests/README.md):
  直接网格 pipeline 的运行方式、旋转策略、指标、依赖及实际案例文件清单。
