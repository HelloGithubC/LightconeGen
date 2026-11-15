# 独立仓库与维护

日期：2026-11-15。

## 位置与 Git 关系

- 本地独立仓库根目录：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4`，下文记为 `<ROOT>`。
- GitHub 远程：`https://github.com/HelloGithubC/LightconeGen.git`，默认分支 `main`。
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
| `<ROOT>/tests/runs/**` | 全部既有实验产物，含 NPZ、CSV、JSON、PNG、pipeline.log 和字体缓存；原样保留并排除提交。逐项实际清单见 tests 下三份实验说明和各运行 manifest |

本次不执行几何实验，不生成新的实验结果、Python 字节码、字体缓存、应用临时文件或检查点。完整性核对的基线校验值只保留在执行过程内存中。Git 命令的 stdout/stderr 在终端显示，不另建日志文件；Git 自身的提交/引用日志位于上表 `.git/logs/**`。不清理、不删除本地数据，已有科学记录中的绝对路径保持有效。

推送只上传提交中的代码/文档及所需 Git 对象。clone 不会恢复被忽略的 mask 或实验产物；需另行提供它们，才能运行几何流程或续跑已有结果。上游项目的 MIT 文字用于保留来源记录，不替新工具擅自添加作者或另选许可证。
