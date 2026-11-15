# 测试与本地运行产物

实验方法、参数、报告和完整文件清单已归档到 `doc/experiments/`：

| 文档 | 内容 |
|---|---|
| [直接网格实验](../doc/experiments/direct_grid.md) | 原 pipeline、单策略入口与低分辨率比较组 |
| [FFT 联合放置](../doc/experiments/fft_placement.md) | 搜索流程、参数及 N=5 实际运行 |
| [FFT 续跑](../doc/experiments/fft_resume.md) | 续跑流程、选优解释及 N=15 实际运行 |

`runs/<运行名>/` 保存本地实验产物，包括覆盖数组、候选明细、配置、投影图、日志和缓存。已有运行目录保持原位，完整清单见实验报告和各运行的 `manifest.json`。

仓库根目录的 `.gitignore` 排除了 `/tests/runs/`。后续从根目录运行时，请将 `--output-dir` 统一指向 `tests/runs/<新运行名>`；输出目录须不存在。程序允许其他输出路径，使用其他位置时需另行配置忽略规则。

当前没有独立的 pytest 单元测试套件。之前的文档整理只移动说明文档并更新索引，其迁移路径和文件清单见[仓库维护说明](../doc/REPOSITORY.md#文档与运行产物分离)。

模块重构的核对产物位于 `runs/module_refactor_20261115/`，完整实际清单和已运行/未运行状态见[模块说明](../doc/MODULE.md)。该目录同样被 Git 忽略；没有新增测试脚本或测试套件。
