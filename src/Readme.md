# 光锥几何测试工具

更新：2026-11-15。当前完成到 **BGS z3、512³ 网格、axes 模式的 N=15 几何窗口放置**，支持从已完成结果继续增加窗口。

该目录现作为独立仓库 **LightconeGen** 管理，见[仓库首页](../README.md)和[维护说明](../doc/REPOSITORY.md)。文档导航已使用仓库相对链接；下文的服务器绝对路径和历史运行记录保留。mask 与实验数据不随 Git 发布。

## 功能与入口

当前用真实角向 mask 与观测径向范围，在周期模拟盒内比较或搜索 observer 的位置和朝向。所有长度单位为 Mpc/h；红移距离换算采用 HR4 平直宇宙学 Ωm=0.26。BGS mask 为 NESTED、NSIDE8192，接受标签默认 **4**；`--angular-nside` 仅控制候选库的角向采样，不降低实际占据计算的 mask 分辨率。

| 文件（均位于 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/`） | 用途 |
|---|---|
| `orientation_geometry.py` | 共用库：mask 查询、距离换算、周期球壳体素、旋转候选及重叠指标；不是命令行入口 |
| `orientation_pipeline.py` | 原完整 pipeline，按约定冻结保留；一次比较多壳层、多网格、多策略和人为给定的 observer，可局部微调朝向 |
| `eval_strategy.py` | 单壳层、单网格、单策略的直接计算；按给定 observer 顺序逐个选朝向，可局部微调；不搜索 observer 位置 |
| `eval_fft.py` | 单壳层、单网格的周期 FFT 位置/朝向联合搜索；支持最小间距、停止阈值及完成结果续跑 |
| `compare_results.py` | 递归读取比较组内的 `result.json`，展示参数/指标并可导出 CSV；兼容两个 eval 入口，不读取旧 pipeline 的 `run.json` |
| `ToDo.md` | 各模型独立头尾包裹的讨论、待办和实现记录；最新完成状态位于末尾 GPT 块 |
| `Readme.md` | 本使用说明；本轮新增 |

三个观测壳层为 z1=[0.025,0.15)、z2=[0.15,0.30)、z3=[0.30,0.40)，分别独立处理。几何裁剪不使用 snapshot 自身红移。

## 放置流程与策略区别

直接计算入口先建立候选库，再依次在给定 observer 处计算窗口，用接受该窗口前的累计覆盖图选择最优朝向，最后汇总；observer 列表结束即停止。`--observer X Y Z` 可重复追加到前三个位置参数指定的首个 observer 之后。直接计算中平均已有覆盖并列时保留先出现的候选。

FFT 入口的处理顺序是：

1. 在首个 observer `O0` 建立各候选朝向的原生 mask 球壳模板；首个窗口强制采用基准朝向。
2. 每轮以累计覆盖 `C` 与模板 `W_R` 做周期互相关：`IFFT(FFT(C) × conj(FFT(W_R)))`，一次获得该朝向所有整数格平移的已有覆盖计数。
3. 还原整数计数、记录舍入残差，以模板格数归一化得到 `H=Σ(C×W_R)/ΣW_R`，屏蔽与已有 observer 周期间距小于 `d_min` 的位置。H 是平均已有覆盖次数，可大于 1。
4. 按 **H 最小 → 最近 observer 距离最大 → C 顺序位置索引最小 → 朝向库索引最小** 选优；零重叠也遵守此顺序。直接重算选中窗口计数并核对后加入 C，继续下一轮。
5. 达到目标总数、没有合法位置，或下一窗口的最小 H 超过可选阈值时停止；目标数包含首个窗口。输出累计覆盖、逐轮记录和投影图。

体素中心为 `(i+0.5)*L/nmesh`，数组轴为 x,y,z；FFT 平移 k 对应 observer `(O0+k*L/nmesh) mod L`，不要求 O0 本身位于体素中心。使用最小镜像周期距离，要求 `0≤rmin<rmax≤L/2`，球壳取 `rmin≤r<rmax`。朝向矩阵采用列向量 `v_box=Q@v_sky`；查询天空 mask 时盒子方向行向量使用 `directions@Q`。

| 策略 | 候选来源 |
|---|---|
| `base` | 只有 `--base-euler` 指定的一个朝向；仅 FFT 入口提供 |
| `axes` | base 加绕盒子 x/y/z 轴的固定角度候选；FFT 默认 30/60/90/120 度，共 13 个；旧直接入口默认另含 150/180 度，共 19 个 |
| `random` | base 加均匀随机旋转；FFT 从共享有序池取前 `candidate-count` 个 |
| `mask-diverse` | base 加从随机池中按角向 mask IoU 筛选的差异朝向；角向差异用于建库，最终放置仍最小化 H |

**共享池只在 FFT 入口实现**：相同 seed、base、pool-size 对应相同初始池，两个策略可分开运行。旧直接入口按策略派生不同种子，即使输入 seed 相同也不是共享池。FFT 不做局部角度/位置微调；直接入口可用 `--refine-steps`、`--refine-rounds` 微调朝向，默认不启用。

## 环境、运行与主要参数

使用已运行成功的 `/home/xiaoliang/.conda/envs/xiaoliang/bin/python`，依赖 NumPy 2.2.6、SciPy 1.15.2、Astropy 6.1.7、healpy 1.19.0、Matplotlib 3.10.6；汇总入口仅依赖 Python 标准库。直接调用 Python，当前没有 Slurm 提交脚本。四个命令行入口均支持无参数显示帮助并以状态 0 退出。

以下新建和续跑命令均是**尚未执行的示例**，示例输出目录未创建；已有正式运行见后文。输出目录必须是新路径。

```sh
# Fresh axes run: 5 windows in the z3 shell.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 512 --z-range 0.30 0.40 --strategy axes \
  --angles-deg 30 60 90 120 --num-cones 5 --min-observer-distance 500 \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_example

# Resume the existing N=5 result to a new total of 15.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py \
  --resume-from /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115 \
  --num-cones 15 \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_example
```

查看现有 N=15 结果的只读命令（本轮未重新执行）：

```sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115 \
  --show-observers
```

| 参数组 | 含义 |
|---|---|
| `X Y Z BOXSIZE`、`--mask`、`--mask-values` | 新运行的首个 observer、盒长和 mask；接受值默认 4 |
| `--nmesh`、`--z-range ZMIN ZMAX` / `--r-range RMIN RMAX` | 网格与径向范围；两类范围必须二选一。旧 pipeline 可一次给多个网格和重复范围 |
| `--strategy` / `--strategies`、`--base-euler`、`--angles-deg` | eval 入口使用单数 strategy，旧 pipeline 使用复数；基准外禀 xyz 欧拉角默认 0 0 0，角度单位为度 |
| `--candidate-count`、`--pool-size`、`--angular-nside`、`--seed` | FFT 默认分别为 13、64、32、20261115；旧直接入口默认 12、64、32、0。count/pool 包含 base，不控制 axes 的候选数 |
| `--num-cones`、`--min-observer-distance`、`--max-mean-prior` | FFT 的目标总数、物理最小周期间距、可选 H 停止阈值；前两者必填，阈值默认关闭 |
| `--workers`、`--chunk-size` | FFT 默认 8 个 worker；几何分块默认 262144 个格点 |
| `--resume-from` | 继承完成目录的几何条件、原候选矩阵、覆盖及历史，只搜索新增窗口；不重复提供位置和几何参数。新总数须大于原数量，可覆盖 workers/chunk-size/max-mean-prior，其余继承 |
| `--output-dir`、`--save-coverage`、`--save-candidates` | 新输出目录；后两者只属于 eval_strategy，分别保存完整覆盖和逐 observer 候选详情 |
| `GROUP_DIRECTORY`、`--sort-by`、`--show-observers`、`--output-csv` | 汇总时按目录划定比较组，递归纳入所有 result.json，默认按名称排序；可展示选择和导出新 CSV。参数一致性需查看记录，不自动强制 |

旧 pipeline/直接入口的完整命令、微调和绘图参数见[原工具说明](../doc/experiments/direct_grid.md)；FFT 全参数及实际命令见 [FFT 说明](../doc/experiments/fft_placement.md)与[续跑说明](../doc/experiments/fft_resume.md)。各入口 `--help` 给出对应参数，续跑帮助用 `--resume-from SOURCE --help`。

## 输入、中间量与输出清单

路径缩写：`<ROOT>` 为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4`；`<OUT>` 为 `--output-dir` 指定的绝对目录；`<SOURCE>` 为 `--resume-from` 指定的绝对目录；`<GROUP>` 为汇总命令的绝对比较组目录。下列规则可据此展开为绝对路径。

| 输入路径或规则 | 来源、格式与用途 | 状态 |
|---|---|---|
| `<ROOT>/src/{orientation_geometry,orientation_pipeline,eval_strategy,eval_fft,compare_results}.py` | 上表列出的五个 Python 源文件 | 均已存在；本轮未修改 |
| `/home/xiaoliang/.conda/envs/xiaoliang/bin/python` | 已有解释器和依赖环境 | 已用于正式运行 |
| `<ROOT>/mask/BGSmask_nside8192_nested.fits` | 原生 BGS FITS mask，读取第一表字段，有效值 4 | 已存在、已读取 |
| `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` | 上述 mask 符号链接的实际目标 | 已存在，只读 |
| `<SOURCE>/result.json` | 续跑读取旧配置、选择和耗时 | N=5→15 已读取 |
| `<SOURCE>/library.npz` | 续跑读取原候选矩阵、标签、签名和体素数 | N=5→15 已读取 |
| `<SOURCE>/coverage.npz` | 续跑读取原累计覆盖，并与重建结果核对 | N=5→15 已读取 |
| `<SOURCE>/search_candidates.csv` | 续跑继承原候选搜索历史 | N=5→15 已读取 |
| `<SOURCE>/manifest.json` | 续跑确认来源已完成 | N=5→15 已读取 |
| `<GROUP>/**/result.json` | 汇总入口递归读取；只使用保存结果，不重算 mask/几何 | 已在正式结果及比较组使用 |

**FFT 自动输出**如下；N=5、N=15 两个正式目录中均已实际生成。示例目录尚未生成任何文件。

| 路径或命名规则 | 生成环节、格式和用途 |
|---|---|
| `<OUT>/run.json` | 启动配置、实际命令、版本、坐标及平局规则 |
| `<OUT>/library.npz` | 模板建成后保存候选矩阵、xyzw 四元数、标签、角向签名和占据体素数 |
| `<OUT>/search_candidates.csv` | 每轮每朝向的最佳位置、重叠计数、最近距离、残差及选择标记；续跑含旧历史 |
| `<OUT>/selections.csv` | 全部已接受窗口的位置、移位、朝向及逐步指标 |
| `<OUT>/observer_distances.csv` | 最终所有无序 observer 对的周期距离 |
| `<OUT>/coverage.npz` | 最终 uint32 三维累计覆盖、observer、移位及几何范围 |
| `<OUT>/coverage_projection.png` | 三个笛卡尔累计覆盖投影及 observer 编号 |
| `<OUT>/result.json` | 完整参数、选择矩阵、最终指标、停止原因、本次及累计耗时；供汇总使用 |
| `<OUT>/pipeline.log` | 运行进度和捕获的异常；同时输出到终端 |
| `<OUT>/manifest.json` | 完成/失败状态、输入及实际输出清单 |
| `<OUT>/cache/matplotlib/fontlist-v{version}.json` | Matplotlib 按需生成字体缓存；两次正式运行实际文件名均为 fontlist-v390.json |

**其他入口及后处理文件**如下；可选文件是否实际生成须查对应运行配置/manifest，不能据文件规则推定已经生成。

| 入口及路径规则 | 来源、用途和已生成情况 |
|---|---|
| eval_strategy：`<OUT>/result.json` | 最终配置和指标；已在旧比较组生成 |
| eval_strategy：`<OUT>/selections.csv` | 每个输入 observer 的朝向选择；已在旧比较组生成 |
| eval_strategy：`<OUT>/coverage.npz` | `--save-coverage` 时保存累计覆盖；旧比较组已启用并生成 |
| eval_strategy：`<OUT>/candidates_observer_{ooo}.csv` | `--save-candidates` 时保存逐候选指标；旧比较组已生成 |
| eval_strategy：`<OUT>/candidates_observer_{ooo}.npz` | 同开关保存矩阵、四元数、标签和选择索引；旧比较组已生成 |
| compare_results：`--output-csv` 指定的绝对路径 | 可选汇总 CSV，含参数和指标，拒绝覆盖已有文件；两次 FFT 后处理实际路径为各正式目录的 comparison.csv |
| 额外核对：`<OUT>/pairwise_overlaps.csv` | 直接统计两两交集与 IoU；两个正式 FFT 目录均已生成，分别 10/105 对；不是脚本自动输出 |
| 额外核对：`<OUT>/verification.json` | 覆盖重建、距离、矩阵及来源不变等核对记录；两个正式 FFT 目录均已生成；不是脚本自动输出 |
| 旧 pipeline：`<OUT>/run.json` | 配置、mask 元数据与坐标约定；旧 smoke 运行已生成 |
| 旧 pipeline：`<OUT>/libraries/{strategy}.npz` | 候选库矩阵、签名和角向 IoU；旧 smoke 已生成 |
| 旧 pipeline：`<P>/observer_{ooo}/candidates.csv` | 每 observer 候选指标，含实际评估的局部候选；旧 smoke 已生成 |
| 旧 pipeline：`<P>/observer_{ooo}/overlap.npz` | 候选间三维交集/IoU、矩阵与选择索引；旧 smoke 已生成 |
| 旧 pipeline：`<P>/observer_{ooo}/windows.npz` | `--save-windows` 时保存按位打包的候选占据；旧 smoke 已启用并生成 |
| 旧 pipeline：`<P>/observer_{ooo}/orientation_scan.png` | 候选朝向诊断图；旧 smoke 已生成，`--no-plots` 可关闭 |
| 旧 pipeline：`<P>/selections.csv` | 各 observer 选择和逐步覆盖指标；旧 smoke 已生成 |
| 旧 pipeline：`<P>/coverage.npz` | 最终累计覆盖和几何条件；旧 smoke 已生成 |
| 旧 pipeline：`<P>/coverage_projection.png` | 覆盖投影；旧 smoke 已生成，`--no-plots` 可关闭 |
| 旧 pipeline：`<OUT>/summary.csv` | 所有壳层/网格/策略/observer 合表；旧 smoke 已生成 |
| 旧 pipeline：`<OUT>/pipeline.log` | 进度、捕获 warning 和异常；旧 smoke 已生成 |
| 旧 pipeline：`<OUT>/manifest.json` | 实际输入/输出及完成状态；旧 smoke 已生成 |
| 旧 pipeline：`<OUT>/cache/matplotlib/fontlist-v{version}.json` | 受控字体缓存；旧 smoke 已生成 fontlist-v390.json |

这里 `<P>=<OUT>/shell_{ss}/nmesh_{nnnn}/{strategy}`；ss 为从 0 开始的两位壳层编号，nnnn 为四位网格数，ooo 为从 0 开始的三位 observer 编号。旧 smoke 的 OUT 为 `<ROOT>/tests/runs/bgs_orientation_smoke_20261112`；旧直接比较组为 `<ROOT>/tests/runs/comparison_group_20261113/{strategy}_n{nmesh}`，包含三策略、32/64 两种网格。

FFT 的模板索引、complex128 模板频谱、覆盖频谱、得分图及最近距离图只在内存中，不保存完整得分图或磁盘 FFT 缓存；旧入口的占据计算和候选初始池也有内存中间量。512³、13 个朝向的频谱合计约 13.05 GiB。

所有入口的 stdout/stderr 发往终端，不自动创建独立输出/错误文件。FFT 和旧 pipeline 另写日志；eval_strategy/compare_results 不自动写日志或 manifest。eval_strategy 可由 healpy/Matplotlib 触发字体缓存，建议显式设置 `MPLCONFIGDIR`；旧比较组实际为 `<ROOT>/tests/runs/comparison_group_20261113/_matplotlib_cache/fontlist-v390.json`，汇总入口自身不导入绘图库。

入口禁止主动生成 Python 字节码，命令示例也使用 `-B`。工具不创建应用临时文件、中途检查点或下载缓存；没有自动清理步骤。三个运行入口拒绝已有输出目录，续跑来源只读；失败时已写出的部分结果保留，FFT/旧 pipeline 尽可能写失败 manifest。正式核对曾更新各自 manifest 以纳入后处理文件；上一次功能文档整理仅更新 ToDo.md 并新增 Readme.md。本次仓库独立化的文件清单见[维护说明](../doc/REPOSITORY.md)，没有修改程序或重跑实验。

## 已完成运行与核对

共同条件：L=3150 Mpc/h、BGS z3=[0.30,0.40)、512³、首个 observer=(1575,1575,1575)、axes 13 朝向、d_min=500 Mpc/h，未启用 H 停止阈值。

| 已完成目录（前缀均为 `<ROOT>/tests/runs/`） | 窗口数 | 非重复覆盖盒子比例 | 最小 observer 周期间距 | 本次耗时 / 峰值 RSS |
|---|---:|---:|---:|---:|
| `fft_axes_z3_n512_N5_20261115` | 5 | 14.8212634% | 770.3461615 Mpc/h | 380.925 s / 20.6669 GiB |
| `fft_axes_z3_n512_N15_fromN5_20261115` | 15（新增 10） | 42.1322189% | 500.0459078 Mpc/h | 625.949 s / 20.7994 GiB |

两目录各有 **14 个实际文件**：11 个自动/库缓存文件加 comparison.csv、pairwise_overlaps.csv、verification.json。N=5 对全部窗口按实际 observer 坐标重新查询原生 mask；N=15 对原覆盖加新增模板做独立 numpy.roll 重建，核对 105 对交集、距离和矩阵。前五个选择、原搜索历史及候选库保留，原 N=5 全部 14 文件 SHA256 不变。小网格全平移 FFT/直接计数也已核对；未新增测试套件。

完整的逐项实际文件清单、命令和验证依据分别见[旧入口/比较组说明](../doc/experiments/direct_grid.md)、[N=5 说明](../doc/experiments/fft_placement.md)与 [N=15 续跑说明](../doc/experiments/fft_resume.md)。科学约定见[光锥策略交接](../doc/HR4_BGS_Lightcone_Strategy.md)。

## 当前边界与未完成事项

目前是有限网格、有限朝向库的逐个贪心几何放置；observer 间距和低重叠不等于 mock 统计独立。续跑要求来源运行已完成，不支持中途检查点恢复。正式 512³ 的 random/mask-diverse 对比、其他壳层和网格收敛尚未完成；completeness、真实 snapshot、速度/RSD、密度标记、DD/DR/RR 及 AP 系统误差分析尚未接入。更早讨论中的后续方向不代表已经实现。
