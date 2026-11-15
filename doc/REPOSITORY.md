# 独立仓库与维护

日期：2026-11-15。

## 位置与 Git 关系

- 本地独立仓库根目录：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4`，下文记为 `<ROOT>`。
- GitHub 远程：`https://github.com/HelloGithubC/LightconeGen.git`，默认分支 `main`。
- 实际 origin 使用服务器已配置的 SSH 认证：`git@github.com:HelloGithubC/LightconeGen.git`；日常 `git push` 沿用此设置，无需修改全局身份或保存 HTTPS token。
- 沿用既有 Git 身份 `HelloGithubC <xiaoliangms@outlook.com>`，不修改全局配置。
- 父目录仍为原 LightGen checkout，其 origin 和历史保留；父目录 `.git/info/exclude` 加入 `/ForHR4/`，仅在本地忽略子仓库。
- LightconeGen 在 `<ROOT>/.git/` 建立独立历史，首次提交只包含 ForHR4 代码、文档和本次仓库说明，不包含父仓库历史。

## 初始化与日常流程

初始化按顺序完成：核对父仓库/远程/身份 → 在 ForHR4 执行 `git init -b main` → 配置父目录本地忽略规则及本仓库 `.gitignore` → 添加首页、mask/来源说明并转换文档链接 → 检查暂存清单 → 首次提交 → 设置 origin → 推送 main。实际提交与是否已推送以 `git log`、`git status` 和远程引用为准；本文件不预填提交哈希。

维护时进入 `<ROOT>`，按需要暂存代码或文档并检查差异，再提交、推送。以下是维护命令说明，不能把 `git add` 的文件清单原样套用于所有后续改动：

```sh
git status --short
git diff
git add README.md src doc tests mask/README.md .gitignore THIRD_PARTY_NOTICES.md
git diff --cached --stat
git commit -m "Describe the change"
git push
```

依赖 Git；推送另需网络和 GitHub 认证。程序运行依赖及参数见 [src 说明](../src/Readme.md)。无 Slurm、安装或部署步骤。

新增文档导航使用仓库相对链接；历史实验命令、数据位置和文件清单中的服务器绝对路径保留为实际记录。换机器时从 [首页](../README.md)的相对路径命令开始，按 [mask 说明](../mask/README.md)提供数据。

## 输入、输出和本地保留文件

本次输入包括既有 ForHR4 内容、父仓库 LICENSE、全局 Git 身份与用户创建的空远程。下表列出文件来源、用途和初始化后的落盘范围；所有 `<ROOT>/...` 均可展开为上面的确定绝对路径。

| 绝对路径或命名规则 | 来源、用途、格式及落盘情况 |
|---|---|
| `<ROOT>/src/orientation_geometry.py` | 既有几何共用库；Python；原样纳入首次提交 |
| `<ROOT>/src/orientation_pipeline.py` | 既有冻结 pipeline；Python；原样纳入首次提交 |
| `<ROOT>/src/eval_strategy.py` | 既有单策略入口；Python；原样纳入首次提交 |
| `<ROOT>/src/eval_fft.py` | 既有 FFT/续跑入口；Python；原样纳入首次提交 |
| `<ROOT>/src/compare_results.py` | 既有汇总入口；Python；原样纳入首次提交 |
| `<ROOT>/src/Readme.md` | 既有完整使用说明；Markdown；转换导航链接，补仓库说明入口 |
| `<ROOT>/src/ToDo.md` | 既有协作记录；Markdown；转换文件链接并保留各模型独立头尾 |
| `<ROOT>/doc/README.md` | 既有文档索引；Markdown；转换链接并增加本说明入口 |
| `<ROOT>/doc/HR4_BGS_Lightcone_Strategy.md` | 既有科学交接；Markdown；只转换文件导航链接 |
| `<ROOT>/tests/README.md` | 既有直接计算/比较组实际记录；Markdown；只转换文件导航链接 |
| `<ROOT>/tests/FFT_README.md` | 既有 FFT/N=5 实际记录；Markdown；只转换文件导航链接 |
| `<ROOT>/tests/FFT_RESUME_README.md` | 既有续跑/N=15 实际记录；Markdown；内容原样纳入首次提交 |
| `<ROOT>/.gitignore` | 本次新建；Git 忽略规则，排除结果、FITS、Python/编辑器缓存 |
| `<ROOT>/README.md` | 本次新建；Markdown 首页、功能、运行示例与导航 |
| `<ROOT>/mask/README.md` | 本次新建；Markdown，四个现有数据链接及数据提供方式 |
| `<ROOT>/THIRD_PARTY_NOTICES.md` | 本次新建；Markdown 来源说明及父仓库 MIT 声明全文 |
| `<ROOT>/doc/REPOSITORY.md` | 本次新建；即本维护流程及完整文件清单 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/LICENSE` | 输入；父仓库既有 MIT 文本，只读，原文保留到来源说明 |
| `/home/xiaoliang/.gitconfig` | 输入；沿用既有身份，只读；不是新仓库内容 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/.git/info/exclude` | 既有父仓库元数据；仅追加 `/ForHR4/`，不提交到任何仓库 |
| `<ROOT>/.git/**` | 本次生成的 Git 元数据；不作为代码文件上传。包括 HEAD、config、description、index、COMMIT_EDITMSG、hooks/*.sample、info/exclude、refs/heads/main、refs/remotes/origin/main、logs/HEAD、logs/refs/** 及 objects/{两位前缀}/{38位十六进制对象名}；推送更新远程跟踪引用/日志 |
| `<ROOT>/mask/*.fits` | 四个既有符号链接；具体绝对目标和用途见 mask/README.md；原样保留并排除提交 |
| `<ROOT>/tests/runs/**` | 全部既有实验产物，含 NPZ、CSV、JSON、PNG、pipeline.log 和字体缓存；原样保留并排除提交。逐项实际清单现见 doc/experiments 下三份实验说明和各运行 manifest |

本次不执行几何实验，不生成新的实验结果、Python 字节码、字体缓存、应用临时文件或检查点。完整性核对的基线校验值只保留在执行过程内存中。Git 命令的 stdout/stderr 在终端显示，不另建日志文件；Git 自身的提交/引用日志位于上表 `.git/logs/**`。不清理、不删除本地数据，已有科学记录中的绝对路径保持有效。

推送只上传提交中的代码/文档及所需 Git 对象。clone 不会恢复被忽略的 mask 或实验产物；需另行提供它们，才能运行几何流程或续跑已有结果。上游项目的 MIT 文字用于保留来源记录，不替新工具擅自添加作者或另选许可证。

## 文档与运行产物分离

2026-11-15 将三份实验说明整体移入 `doc/experiments/`，更新导航，并在 `tests/README.md` 留下短索引。上节首次导入清单中的旧文档路径是历史记录；当前位置以本节为准。运行命令、实验数据路径和已有结果文件保持原样。

以下 `<ROOT>` 仍为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4`，路径规则可展开为确定绝对路径。所有文件均为 Markdown；本次实际变更清单如下：

| 输入旧路径 | 最终路径 | 来源、用途与实际状态 |
|---|---|---|
| `<ROOT>/tests/README.md` 原内容 | `<ROOT>/doc/experiments/direct_grid.md` | 已移动；保留直接计算流程、比较组和文件清单，更新跨文档链接并加归档说明 |
| `<ROOT>/tests/FFT_README.md` | `<ROOT>/doc/experiments/fft_placement.md` | 已移动；保留 FFT 方法与 N=5 记录，更新跨文档链接并加归档说明；旧位置不保留副本 |
| `<ROOT>/tests/FFT_RESUME_README.md` | `<ROOT>/doc/experiments/fft_resume.md` | 已移动；保留续跑与 N=15 记录并加归档说明；旧位置不保留副本 |
| 原说明已移出 | `<ROOT>/tests/README.md` | 已重新写为简短索引，说明本地产物与输出目录约定 |
| `<ROOT>/README.md` | 同路径 | 已修改首页链接和文档表 |
| `<ROOT>/src/Readme.md` | 同路径 | 已修改实验说明导航链接 |
| `<ROOT>/src/ToDo.md` | 同路径 | 已更新文档引用路径，保留各模型开头/结尾标记及讨论内容 |
| `<ROOT>/doc/README.md` | 同路径 | 已修改文档索引，补齐 FFT 与续跑入口 |
| `<ROOT>/doc/HR4_BGS_Lightcone_Strategy.md` | 同路径 | 已更新直接网格实验说明链接 |
| `<ROOT>/doc/REPOSITORY.md` | 同路径 | 已补充本次迁移流程与清单 |

本次使用 Git 记录文档移动并建立本地提交，不执行几何程序或提交新的测试套件。既有五个 Python 文件、201 个运行产物和四个 mask 符号链接保持原样；`.gitignore` 的 `/tests/runs/` 规则不变。核对校验值只存于执行过程内存，标准输出/错误仅在终端显示，无新实验文件、应用临时文件、缓存、日志或检查点。Git 自身的索引、对象和提交日志更新于 `<ROOT>/.git/`。不清理或删除实验产物；本次未执行推送。

## Python 模块重构

2026-11-15 将光锥几何搜索拆成可导入的 `lightconegen` 包。工作顺序为：保存原文件校验值 → 原样移动五个旧 Python 文件 → 提取数据类型、几何、FFT 搜索、重建/点筛选与读写接口 → 分离搜索和落盘 → 核对旧存档及小网格新旧结果 → 更新说明。新包不会调用旧脚本，原 CLI 仍可独立运行。下面路径以当前布局为准；上文 `src/*.py` 是初始化时的位置。

`layout` 保存模式只生成一个精简 `layout.json`；`full` 保存覆盖、候选库和搜索记录供分析及续跑。流程、完整 API 参数、依赖、运行/安装方式以及实际输入和全部中间/最终输出见 [MODULE.md](MODULE.md)。本次通过 `PYTHONPATH=<ROOT>/src` 和现有 Python 环境核对，没有执行安装、构建、提交、推送或 Slurm 作业。

| 绝对路径或确定规则 | 来源、用途、格式与实际状态 |
|---|---|
| `<ROOT>/src/orientation_geometry.py` → `<ROOT>/tools/legacy/orientation_geometry.py` | 既有几何库，已原样移动；Python |
| `<ROOT>/src/orientation_pipeline.py` → `<ROOT>/tools/legacy/orientation_pipeline.py` | 既有冻结 pipeline，已原样移动；Python |
| `<ROOT>/src/eval_strategy.py` → `<ROOT>/tools/legacy/eval_strategy.py` | 既有直接搜索入口，已原样移动；Python |
| `<ROOT>/src/eval_fft.py` → `<ROOT>/tools/legacy/eval_fft.py` | 既有 FFT/续跑入口，已原样移动；Python |
| `<ROOT>/src/compare_results.py` → `<ROOT>/tools/legacy/compare_results.py` | 既有汇总入口，已原样移动；Python |
| `<ROOT>/src/lightconegen/__init__.py` | 新增，公开导入接口；Python |
| `<ROOT>/src/lightconegen/models.py` | 新增，布局和结果数据类型；Python |
| `<ROOT>/src/lightconegen/geometry.py` | 从原几何库提取，原生 mask 查询、旋转、周期网格及距离；Python |
| `<ROOT>/src/lightconegen/search.py` | 从原 FFT 流程提取，联合搜索与续跑；Python |
| `<ROOT>/src/lightconegen/reconstruct.py` | 新增，按布局重建覆盖及筛选位置行索引；Python |
| `<ROOT>/src/lightconegen/io.py` | 新增，显式读写和可选绘图；Python |
| `<ROOT>/pyproject.toml` | 新增，构建元数据和依赖；TOML；尚未执行安装或构建 |
| `<ROOT>/.gitignore` | 已补构建/包元数据忽略规则；仍排除运行产物和 FITS |
| `<ROOT>/README.md` | 已重写为包首页；Markdown |
| `<ROOT>/src/Readme.md` | 已重写为简短 API 使用导航；Markdown |
| `<ROOT>/src/ToDo.md` | 已补独立 GPT 头尾的重构状态块；Markdown；原讨论保留 |
| `<ROOT>/doc/MODULE.md` | 新增，完整模块流程、参数和逐项文件清单；Markdown |
| `<ROOT>/tools/README.md` | 新增，五个保留工具的运行和输出说明；Markdown |
| `<ROOT>/doc/README.md` | 已加新模块和工具导航；Markdown |
| `<ROOT>/doc/HR4_BGS_Lightcone_Strategy.md` | 已更新当前实现入口；Markdown；科学配置不变 |
| `<ROOT>/doc/experiments/direct_grid.md` | 已加旧工具迁移说明；Markdown；历史实验记录保留 |
| `<ROOT>/doc/experiments/fft_placement.md` | 已加旧工具迁移说明；Markdown；历史实验记录保留 |
| `<ROOT>/doc/experiments/fft_resume.md` | 已加旧工具迁移说明；Markdown；历史实验记录保留 |
| `<ROOT>/tests/README.md` | 已补本轮模块核对目录导航；Markdown |
| `<ROOT>/mask/README.md` | 已更新四个软链接的当前绝对目标和修复说明；Markdown |
| `<ROOT>/doc/REPOSITORY.md` | 已追加本节；Markdown |
| `<ROOT>/mask/*.fits` | 四个既有软链接已按用户授权重建，目标从 `/mnt/xiaodong/xiaoliang/DESImocks/source/<同名文件>` 改为 `/mnt/xiaodong/xiaoliang/DESImocks_old/source/<同名文件>`；逐项路径见 mask/README.md；已读取 FITS 头，没有修改数据内容 |
| `<ROOT>/tests/runs/module_refactor_20261115/**` | 本轮定向核对实际生成；含派生 mask、JSON/NPZ/CSV/PNG、旧工具日志和字体缓存；逐项绝对路径、来源、用途及状态见 MODULE.md；被 Git 忽略 |
| `<ROOT>/tests/runs/` 中其余既有 201 个文件 | 本轮只读输入，原位保留；包括旧 N=5 和 N=15 结果、日志、缓存；不修改或清理 |
| `<ROOT>/.git/index` | `git mv` 记录五个脚本移动而更新；本轮没有新建提交或推送 |

FFT 频谱、模板体素索引、最近距离图、重建数组及选点行索引均只在内存中存在；没有新增磁盘 FFT 缓存、检查点或临时脚本。核对使用 `python -B`，不写 Python 字节码。标准输出/错误在终端显示；旧 CLI 的运行日志位于核对输出的 `legacy_axes/pipeline.log`，原生 mask 对照所捕获的 stdout/stderr 还保留在该次 `verification.json` 内；字体缓存位于对应 `cache/matplotlib/fontlist-v390.json`。首次失效链接记录及首次误比较计时字段的记录均保留，没有覆盖、删除或清理核对产物。新 API 拒绝已有输出目录或图片路径；完整保存异常可能留下部分文件。
