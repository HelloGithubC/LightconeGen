# FFT 放置续跑：N=5 到 N=15

日期：2026-11-15。

> 归档说明（2026-11-15）：本文由 `tests/FFT_RESUME_README.md` 移至 `doc/experiments/fft_resume.md`。历史命令和文件清单保留；旧文档路径的当前位置见[迁移清单](../REPOSITORY.md#文档与运行产物分离)。运行产物 `tests/runs/` 未移动。

> 模块重构说明：原五个 Python 文件已原样移到 `tools/legacy/`。本文中的旧源码路径为历史记录，当前可执行入口见[工具说明](../../tools/README.md)。

## 零重叠时如何选择朝向

脚本按以下顺序比较位置和朝向组合：平均已有覆盖最小；并列时最近 observer 的周期距离最大；
仍并列时取 C 顺序网格位置索引最小者；同一位置的并列朝向按候选库顺序选择。
因此，零重叠并不直接确定朝向，也不意味着自动选 base。

本次 N=5 基线中：首个窗口强制使用 base；第二个窗口所有朝向都能在同一个最远位置保持零重叠，最终按库顺序选择 base。
第三个窗口各朝向仍能找到零重叠位置，但最远零重叠位置与已有 observer 的最近距离不同：

| 朝向 | 其零重叠位置中的最大最近 observer 距离 (Mpc/h) |
|---|---:|
| base | 1640.38145165 |
| x_30 | 1673.79936345 |
| y_30 | 1682.73068710 |
| y_60 | 1700.33017767 |

在全部 13 个候选中 y_60 取最大值，所以第三个窗口选择它。第四个窗口也由相同规则选中 y_60。
完整逐候选依据在 N=5 目录的 search_candidates.csv 中。

## 续跑实现与工作流程

入口为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py`，新增 `--resume-from` 调用形式。
续跑从已完成运行的保存结果恢复，不在原目录追加，不回头调整已有窗口：

1. 读取旧 result.json 的全部几何/候选参数和选择记录；要求旧 manifest 状态为 completed。
2. 继承盒长、网格、mask、径向范围、候选策略、最小间距等参数。直接加载旧 library.npz 中的矩阵、标签和角向签名，候选朝向不重新抽样。
3. 基于原 mask 和原始 observer 锚点重建候选模板及内存频谱；核对占据体素数与旧库相同。
4. 读取旧 coverage.npz，以已有窗口重新构建覆盖并核对保存覆盖完全一致；重建最近 observer 的周期距离图。
5. 保留已有选择及 search_candidates.csv 历史。以保存窗口数为下一 observer 编号，只搜索新增窗口。
6. 达到新的总数、没有合法位置或超过继承/指定的平均覆盖阈值时停止。所有窗口的累计指标写入新目录。
7. `total_elapsed_sec` 是本次续跑耗时；`cumulative_elapsed_sec` 是与来源运行累计的耗时；`initial_num_observers` 和 `new_num_observers` 区分恢复与新增数量。

频谱未保存在磁盘，因此续跑需重新计算模板频谱；前五个位置与朝向不会重新搜索。
这不是运行中途 checkpoint 恢复：当前来源必须是已完成且保存了完整结果的目录。

## 参数、依赖与实际运行命令

续跑使用同一 Python 环境 `/home/xiaoliang/.conda/envs/xiaoliang/bin/python`，
依赖 NumPy 2.2.6、SciPy 1.15.2、Astropy 6.1.7、healpy 1.19.0、Matplotlib 3.10.6；本轮未安装或修改环境。
无参数仍输出普通帮助并退出 0，已实际核对；`--resume-from RUN --help` 输出续跑专用帮助，也已核对。
直接调用 Python，未使用 Slurm。

| 参数 | 用途 |
|---|---|
| `--resume-from` | 已完成的来源运行绝对目录，必填 |
| `--num-cones` | 新的目标总数，包含已保存窗口，必须大于当前数量；本次为 15，即新增 10 个 |
| `--output-dir` | 新输出目录，必填；拒绝已存在的路径 |
| `--workers` | 可选覆盖原 FFT worker 数；未给时继承，本次为 8 |
| `--chunk-size` | 可选覆盖原几何分块大小；本次继承 262144 |
| `--max-mean-prior` | 可选覆盖原平均已有覆盖停止阈值；未给时继承，本次未启用阈值 |

几何参数不在续跑命令中重复提供。实际已执行并正常完成的命令：

~~~sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py \
  --resume-from /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115 \
  --num-cones 15 \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115
~~~

继承条件：L=3150 Mpc/h，512^3，z3=0.30–0.40（r=843.49445234–1098.72619455 Mpc/h），
原生 BGS mask 有效值 4，d_min=500 Mpc/h，axes=base 加三轴各 30/60/90/120 度，共 13 个朝向。

## 完整文件清单

以下 `<SOURCE>` 为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115`；
`<RUN>` 为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115`。

| 绝对路径或确定命名规则 | 来源/生成环节、格式和用途 | 状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py` | Python；本轮增加续跑解析、状态恢复、历史继承 | 已修改并用于运行 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_geometry.py` | Python；复用原生 mask 与球壳几何 | 已存在，本轮未修改 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py` | Python；后处理汇总入口 | 已存在，本轮未修改 |
| `/home/xiaoliang/.conda/envs/xiaoliang/bin/python` | 既有解释器和依赖环境 | 已使用，未修改 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` | FITS mask 符号链接，原生 NSIDE8192、NESTED、标签 4 | 已读取 |
| `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` | 上述链接实际目标，FITS | 只读 |
| `<SOURCE>/result.json` | 参数、前五个窗口记录及原累计耗时 | 已读取 |
| `<SOURCE>/manifest.json` | 来源完成状态；后处理另核对完整文件清单 | 已读取 |
| `<SOURCE>/library.npz` | 原朝向矩阵、四元数、角向签名和占据格数 | 已读取 |
| `<SOURCE>/coverage.npz` | 原 512^3 uint32 累计覆盖 | 已读取 |
| `<SOURCE>/search_candidates.csv` | 原 52 条候选搜索历史 | 已读取 |
| `<SOURCE>/**` 的全部 14 个原文件 | 续跑前记录 SHA256，结束后核对不变；包括源日志、缓存及其后处理文件 | 全部 14 个文件 SHA256 核对不变 |
| `<RUN>/run.json` | 启动条件、来源绝对路径、实际命令、依赖和坐标约定 | 已生成 |
| `<RUN>/pipeline.log` | 本次模板重建、状态恢复、新增搜索的 INFO 和捕获异常；同时发往终端 | 已生成 |
| `<RUN>/library.npz` | 新目录内保存相同候选库；不是磁盘频谱缓存 | 已生成，13 个候选 |
| `<RUN>/selections.csv` | 全部 15 个窗口，前五个原记录保留 | 已生成 |
| `<RUN>/search_candidates.csv` | 原 52 条加新增 130 条，正常完成共 182 条 | 已生成 |
| `<RUN>/observer_distances.csv` | 所有无序 observer 对的周期距离，正常完成共 105 对 | 已生成 |
| `<RUN>/coverage.npz` | 全部窗口的最终累计覆盖和几何配置 | 已生成 |
| `<RUN>/coverage_projection.png` | 三个坐标投影与所有 observer 编号 | 已生成 |
| `<RUN>/result.json` | 来源目录、全部参数/选择、累计指标、本次/累计耗时及停止原因 | 已生成 |
| `<RUN>/manifest.json` | 完成/失败状态、来源输入和实际输出清单 | 已生成 |
| `<RUN>/cache/matplotlib/fontlist-v390.json` | 本次受控字体缓存；其他环境为 fontlist-v{version}.json | 已生成，实际名为 fontlist-v390.json |
| `<RUN>/comparison.csv` | 运行完成后由汇总入口导出 | 已生成，后处理产物 |
| `<RUN>/pairwise_overlaps.csv` | 后处理直接统计全部 105 对体素交集/IoU | 已生成，后处理产物 |
| `<RUN>/verification.json` | 后处理核对：来源校验值、前缀不变、候选库、覆盖增量、距离和交集 | 已生成，后处理产物 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/FFT_RESUME_README.md` | 本次流程、参数与完整文件清单，Markdown | 已创建 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/FFT_README.md` | 原 FFT 说明，本轮添加续跑说明链接 | 已修改 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/ToDo.md` | 独立 GPT 开头/结尾包裹本轮说明和续跑交接 | 已修改，其他模型原记录不改 |

模板频谱、覆盖频谱、得分图、最近距离图、旧覆盖重建及后处理占据数组均仅保留在内存中。
不保存完整频谱/得分图，不创建应用临时文件、下载缓存、中途 checkpoint 或 Python 字节码。
标准输出/错误发往终端，无单独 stdout/stderr 文件；INFO 与捕获异常写入 pipeline.log，未捕获的库 warning 可能只在终端 stderr 中出现。
已有来源目录只读，新目录内的结果不自动清理；失败时保留部分产物并写失败 manifest。
本次后处理后已刷新新目录的 manifest 以纳入三个后处理产物；旧实验未覆盖、未清理、未删除。

## 实际运行状态

**已完成并核对通过**：从原 N=5 新增 10 个窗口，达到总数 N=15，停止原因为 target_reached。

| 放置后的总数 N | 新窗口朝向 | 平均已有覆盖 | 累计盒子覆盖比例 |
|---:|---|---:|---:|
| 6 | y_60 | 1.00532243e-06 | 17.785715% |
| 7 | x_30 | 0.00939698551 | 20.722473% |
| 8 | x_30 | 0.00939698551 | 23.659232% |
| 9 | y_60 | 0.0455348227 | 26.488701% |
| 10 | y_60 | 0.0455348227 | 29.318169% |
| 11 | y_60 | 0.077375646 | 32.053246% |
| 12 | y_60 | 0.077375646 | 34.788324% |
| 13 | x_30 | 0.161458964 | 37.278136% |
| 14 | x_30 | 0.161458964 | 39.767948% |
| 15 | y_120 | 0.20502269 | 42.132219% |

最终覆盖盒子 42.132218927%，最小 observer 周期间距 500.0459077741 Mpc/h，满足继承的 500 Mpc/h 下限。
最后一个窗口的平均已有覆盖为 0.2050226896；全部 15 个的平均值为 0.0528371692。该指标是累计覆盖次数的平均，存在多重覆盖时不能直接称为重叠体积百分比。
累计交集计数为 3,153,358 个体素次，最大覆盖次数为 3。

本次续跑耗时 625.949 秒，连同 N=5 来源运行累计 1006.874 秒；本次峰值 RSS 20.7994 GiB，最大整数还原残差 1.86264514923e-09。

核对确认：前五个完整选择记录不变、旧 52 条搜索记录不变、所有候选库数组完全相同、来源全部 14 个文件 SHA256 不变；
以原生 mask 在原锚点重建模板，再用独立的 numpy.roll 平移新增窗口，其逐步计数及最终覆盖与保存结果完全一致；
全部 105 对交集和周期距离已直接统计，旋转矩阵与平均覆盖最低分单调性检查通过。一次性核对耗时 39.628 秒，未保存核对脚本或新建测试套件。

新目录共 14 个实际文件，含字体缓存、日志和三个后处理产物；完整实际路径在 manifest.json 中。原 N=5 目录保持不变。

汇总命令已实际执行并生成 comparison.csv：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115 \
  --show-observers \
  --output-csv /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115/comparison.csv
~~~

该 CSV 已存在；重新查看时省略 --output-csv，再导出时使用新路径。继续增加窗口时可把本次已完成目录作为新的 --resume-from 来源，并指定更大的目标总数及新目录。

这些窗口仍是网格中心采样的几何结果。最小间距与低重叠不等于统计独立；本轮不改变目标函数、原朝向候选或已选窗口，也不进行最终 AP 统计验证。
