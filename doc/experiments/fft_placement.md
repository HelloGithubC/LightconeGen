# FFT 光锥几何放置：工作流程与运行清单

更新日期：2026-11-15。

> 归档说明（2026-11-15）：本文由 `tests/FFT_README.md` 移至 `doc/experiments/fft_placement.md`。历史命令和文件清单保留；旧文档路径的当前位置见[迁移清单](../REPOSITORY.md#文档与运行产物分离)。运行产物 `tests/runs/` 未移动。

> 模块重构说明：原五个 Python 文件已原样移到 `tools/legacy/`。本文中的旧源码路径为历史记录，当前可执行入口见[工具说明](../../tools/README.md)。

## 目的与入口

入口为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py`。
在一个周期盒、一个径向壳层和一个候选朝向库上，通过 FFT 联合搜索 observer 位置与朝向，
逐个放置几何窗口。当前只使用实际 BGS footprint，不接入 completeness、snapshot、速度、RSD 或相关函数。
旧的 `orientation_pipeline.py`、`eval_strategy.py` 和 `orientation_geometry.py` 保留原有行为。

## 处理步骤与坐标约定

1. 前四个位置参数为 `X Y Z BOXSIZE`。首个 observer 是输入坐标按盒长取模后的 `O0`，首个朝向固定为 `base-euler`。
2. 体素中心为 `(i+0.5)*L/nmesh`，数组按 x,y,z 轴、C 顺序存储。在首个 observer 处构建每个朝向的原生 mask 球壳模板。
3. FFT 索引 `k=(kx,ky,kz)` 表示整格周期平移，对应 observer 为 `(O0+k*L/nmesh) modulo L`；模板和 observer 同时移动。
4. 每轮对累计整数覆盖图 `C` 与各个二值模板做周期互相关：`irfftn(rfftn(C)*conj(rfftn(W)), s=C.shape)`。
5. 按块四舍五入还原非负整数计数，记录最大舍入残差，再以模板占据格数归一化。残差达到 0.25 时停止并报错，避免无法可靠还原计数时继续选择。
6. 屏蔽与任一已放置 observer 周期间距小于 `DMIN` 的位置。距离图以整数格距平方保存，因此同距判定不依赖浮点舍入。
7. 最小化平均已有覆盖；精确并列时最大化最近 observer 的距离；仍并列时取最小 C 顺序位置索引；同点朝向按库顺序选择。不同朝向的平均值用整数比交叉比较对应的精确有理数。
8. 将选中窗口加入 `C`，更新最近距离图，然后继续。达到目标总数、没有合法位置，或下一窗口的最小平均已有覆盖超过可选阈值时停止。目标总数包含首个窗口；阈值不约束强制放置的首个窗口。
9. 写出最终覆盖、observer 配置、逐朝向搜索摘要、投影图和 manifest。每个被接受窗口的计数都从实际移位窗口重算，并与选中的 FFT 计数核对。

朝向矩阵约定为列向量 `v_box = Q @ v_sky`；对盒子方向的行向量查询原生天空 mask 时使用 `directions @ Q`。
距离与盒长均以 Mpc/h 为单位。壳层要求 `0 <= rmin < rmax <= L/2`，采用 HR4 平直宇宙学 `Omega_m=0.26`。

## 参数

| 参数 | 含义及默认值 |
|---|---|
| `X Y Z BOXSIZE` | 首个 observer、搜索网格锚点及周期盒长；均必填 |
| `--mask`、`--mask-values` | 原始 HEALPix FITS 路径；接受值默认 `4` |
| `--nmesh` | 每轴格数，必填；实际总格数为其三次方 |
| `--z-range ZMIN ZMAX` 或 `--r-range RMIN RMAX` | 一个观测红移区间或直接径向范围，必须二选一 |
| `--strategy` | 必填；`base` 是单一固定朝向，`axes` 是绕盒子三轴的预设角度库；另支持 `random`、`mask-diverse` |
| `--angles-deg` | 仅 axes 使用，默认 `30 60 90 120`；加上 base 共 13 个候选 |
| `--base-euler X Y Z` | 基准外禀 xyz 欧拉角，单位度，默认 `0 0 0` |
| `--candidate-count`、`--pool-size` | 新 FFT 入口的 random/mask-diverse 共享初始池；最终默认 13 个、初始默认 64 个，均包含 base；axes/base 不使用这两个数控制候选数量 |
| `--angular-nside` | 候选库角向签名采样，默认 32；不改变输入 mask 的 NSIDE |
| `--seed` | 两种随机策略的共同池种子，默认 20261115；不影响 axes/base |
| `--num-cones` | 目标窗口总数，必填，包含首个窗口 |
| `--min-observer-distance DMIN` | 最小周期 observer 间距，必填；允许 0 |
| `--max-mean-prior` | 可选停止阈值，默认不启用；平均已有覆盖次数可以大于 1 |
| `--workers` | SciPy FFT 并行线程数，默认 8 |
| `--chunk-size` | 球壳几何分块格数，默认 262144 |
| `--output-dir` | 必填的新目录；已有路径一律拒绝 |

新 FFT 入口中，random 取共同有序随机池的前 `candidate-count` 项，mask-diverse 从同一池中按角向 mask 差异筛选。
相同 seed、base 和 pool-size 对应相同池；旧的直接计算入口仍采用原来的独立池种子规则。
第一版 FFT 入口不做局部位置或角度微调，完整搜索的是给定平移网格与候选朝向库。

## 依赖与运行方式

使用已有环境 `/home/xiaoliang/.conda/envs/xiaoliang/bin/python`。
已核对依赖版本：NumPy 2.2.6、SciPy 1.15.2、Astropy 6.1.7、healpy 1.19.0、Matplotlib 3.10.6；未安装或升级依赖。
运行方式为直接调用 Python，不需要 Slurm 提交文件。

无参数调用已实际执行，输出帮助并以状态 0 退出：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py
~~~

正式运行命令和结果见本页末尾。用户已确认采用 axes 和 z3，即 `0.30 <= z < 0.40`；
规模为盒长 3150、网格 512、窗口总数 5。本轮选择 `DMIN=500 Mpc/h` 作为防扎堆的探索门槛。

## 输入、输出与内存中间量清单

本次 `<RUN>` 为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115`。
其他运行由 `--output-dir` 指定新的绝对路径。下表为本次完整输入与输出清单。

| 绝对路径或确定命名规则 | 来源、格式和用途 | 当前状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py` | 新 FFT 入口，Python 源码 | 已创建 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_geometry.py` | 复用 mask、距离、球壳和候选库函数，Python 源码 | 已存在，未修改 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py` | 读取最终结果并导出汇总；本轮将极小非零平均覆盖的终端显示改为有效数字格式 | 已存在，本轮修改并实际运行 |
| `/home/xiaoliang/.conda/envs/xiaoliang/bin/python` | 既有 Python 解释器和依赖环境 | 已用于正式运行、汇总与核对，未修改环境 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` | BGS 原生 mask，FITS、NESTED NSIDE8192，有效标签 4 | 已读取 |
| `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` | 上述 mask 符号链接实际目标 | 已存在，只读 |
| `<RUN>/run.json` | 开始阶段写入：参数、执行命令、依赖版本、坐标与平局规则；异常发生在此之前时可能没有该文件 | 已生成 |
| `<RUN>/library.npz` | 构建模板后写入：候选标签、完整旋转矩阵、xyzw 四元数、占据格数、角向二值签名 | 已生成，13 个候选 |
| `<RUN>/search_candidates.csv` | 每轮每个朝向的最优位置移位索引、合法格数、计数、平均覆盖、最近距离、最大舍入残差和选中标记；如因阈值停止，也包含未接受的最后一轮 | 已生成，52 行 |
| `<RUN>/selections.csv` | 每个已接受窗口的位置、移位索引、朝向标签、体积与重叠指标、逐步覆盖统计 | 已生成，5 行 |
| `<RUN>/observer_distances.csv` | 所有已接受 observer 的无序对及周期距离 | 已生成，10 行 |
| `<RUN>/coverage.npz` | 最终 uint32 三维累计覆盖、盒长、observer 坐标、移位索引和径向范围 | 已生成 |
| `<RUN>/coverage_projection.png` | 最终累计覆盖的三个笛卡尔投影；红色加号和编号标记 observer | 已生成并查看 |
| `<RUN>/result.json` | 完整参数、mask 信息、最终指标、停止原因、所有选中矩阵/四元数；兼容 compare_results.py | 已生成 |
| `<RUN>/pipeline.log` | INFO 进度与被捕获的异常 traceback，同时发到终端 | 已生成，本次正常完成 |
| `<RUN>/manifest.json` | 完成或失败状态、输入路径及实际输出文件清单；本次核对结束后更新以纳入三个后处理产物 | 已生成并更新 |
| `<RUN>/cache/matplotlib/fontlist-v390.json` | healpy/Matplotlib 自动生成的字体缓存；脚本设置 MPLCONFIGDIR 将其限制在 RUN 内；其他环境命名为 fontlist-v{version}.json | 已生成 |
| `<RUN>/comparison.csv` | compare_results.py 导出的单次实验汇总，含完整参数；浮点值按原精度保存 | 已生成，后处理产物 |
| `<RUN>/pairwise_overlaps.csv` | 一次性核对中直接统计的两两窗口交集与 IoU | 已生成，10 行，后处理产物 |
| `<RUN>/verification.json` | 一次性核对记录：原生 mask 全窗口验证、覆盖重建、周期距离、两两交集、源码 SHA256、小网格核对摘要 | 已生成，全部通过，后处理产物 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/FFT_README.md` | 本说明及实际运行清单，Markdown | 已创建 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/README.md` | 原实验说明，新增 FFT 说明入口链接 | 已修改 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/ToDo.md` | 协作交接，本轮进展位于独立 GPT 开头/结尾记录内 | 已修改，其他模型记录未改 |

模板球壳索引/方向、各朝向占据索引、共轭 complex128 模板频谱、当前覆盖频谱、乘积、逆变换得分、合法位置掩码与最近距离平方图均仅保留在内存中。
不持久化完整 FFT 得分图或模板频谱，不创建磁盘 FFT 缓存、应用临时文件或检查点；进程结束后由系统回收内存。
512 网格下单个模板频谱约 1.004 GiB，13 个约 13.05 GiB；加上距离图、覆盖图、工作数组和 FFT scratch，峰值预计超过 17.5 GiB，实际峰值在 result.json 中记录。

标准输出/标准错误发往调用终端，不另建 stdout/stderr 文件；INFO 和主流程捕获的异常另存 pipeline.log。
未被捕获的库 warning 可能只出现在终端 stderr。入口禁止主动写 Python 字节码，正式命令也使用 `-B`。
结果目录不自动清理；异常时保留已生成文件并尽可能写入失败 manifest。拒绝已有输出目录，正式运行内各结果文件各写一次。
本次后处理生成 comparison.csv、pairwise_overlaps.csv 和 verification.json 后，更新了本次 manifest.json 的文件清单与后处理状态；未覆盖其他结果、旧实验或删除文件。

## 已完成的轻量核对与解释边界

已在内存中用 7 和 8 两种小网格，对所有整数平移逐一比较 FFT 与直接求和；同时核对稀疏索引平移、最近周期距离图、最低分与 maximin 平局选择。
两种网格均通过；最大整数还原残差分别为 `5.684341886080802e-14` 和 `0`。该核对仅输出终端，没有新增测试脚本、测试套件、缓存或结果目录。

最小间距用于约束 observer 分散，不表示 mock 统计独立。低红移少量窗口可能全部零重叠并都选择 base，不能据此判断候选策略等价。
网格中心采样与有限朝向库仍有离散化；逐个放置是贪心优化。当前没有实际 HR4 天体目录，也没有进行最终 AP 统计验证。

## 2026-11-15：z3、axes、512 网格、N=5 实际运行

输出目录 `<RUN>` 为：

`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115`

本次采用 z3，即观测红移 `0.30–0.40`，HR4 宇宙学径向范围为 `843.49445234–1098.72619455 Mpc/h`。
首个 observer 为 `(1575,1575,1575)`，base 欧拉角为 `(0,0,0)`。
候选为 base 加绕 x/y/z 轴分别旋转 30、60、90、120 度，共 13 个；本次未运行随机策略。
格间距为 `6.15234375 Mpc/h`；最小 observer 周期间距 500 Mpc/h；目标数量 5；未启用平均覆盖停止阈值。
实际命令如下，已启动执行：

~~~sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 512 --z-range 0.30 0.40 \
  --strategy axes --angles-deg 30 60 90 120 \
  --num-cones 5 --min-observer-distance 500 --workers 8 \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115
~~~

运行状态：**已完成且核对通过**。正常达到 5 个窗口，停止原因为 `target_reached`。

| observer 编号 | 坐标 (Mpc/h) | 朝向 | 与此前累计覆盖的交集体素数 |
|---|---|---|---:|
| 0 | (1575, 1575, 1575) | base | 0 |
| 1 | (0, 0, 0) | base | 0 |
| 2 | (3020.80078125, 627.5390625, 1575) | y_60 | 0 |
| 3 | (1445.80078125, 2202.5390625, 0) | y_60 | 0 |
| 4 | (2836.23046875, 55.37109375, 701.3671875) | y_60 | 4 |

前四个窗口没有体素交集。最后一个与 observer 1 的窗口交集为 4 个体素，其余 9 对交集均为 0；
最后一个窗口的平均已有覆盖为 `1.0053224283e-6`，五个窗口该指标的平均值为 `2.0106448565e-7`。
总占据计数为 19,892,767，非重复覆盖为 19,892,763 个体素，占盒子 `14.8212634027%`；最大覆盖次数为 2。
最小 observer 周期间距为 `770.3461614531 Mpc/h`，满足所选 500 Mpc/h 门槛。
选择朝向的最大绝对体积相对误差为 `0.0198319584%`，平均绝对误差为 `0.0130547414%`。

正式运行耗时 `380.925 s`，峰值进程 RSS 为 `20.6669 GiB`，13 个模板频谱占 `13.0508 GiB`。
全程最大整数还原残差为 `1.8626451492e-9`，因此文档中不能把舍入误差量级固定为 `1e-15–1e-12`。

正式运行后，以实际 observer 坐标重新计算每个窗口的全部 13,063,944 个径向球壳体素方向，并查询原始 mask；
逐项核对其与移位模板的角向选择，重建最终覆盖，直接计数所有 10 对窗口交集，并检查旋转矩阵和周期距离，全部通过。
该一次性核对用时 `49.622 s`，没有保存核对脚本或新建测试套件，仅保存上表中的两个核对产物。

汇总命令已实际执行并生成 comparison.csv：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115 \
  --show-observers \
  --output-csv /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115/comparison.csv
~~~

comparison.csv 已存在，重新查看时应去掉 `--output-csv`；若要再次导出须使用新路径。
本轮还将汇总表的平均已有覆盖显示改为有效数字格式，避免把非零的 `1e-6` 量级显示成 `0.00000`；已用本次结果核对终端显示，CSV 原数值没有改写。
本次运行目录共 14 个文件，含字体缓存、日志和三个后处理产物，完整实际路径均列于 manifest.json。

这些交集结论仅针对 512 网格的体素中心采样；不能由 4 个重叠体素推出连续几何中的精确重叠体积，也不代表 5 个 mock 在统计上独立。

## 从已完成结果续跑

已新增 `--resume-from` 入口，可从本次 N=5 继续增加窗口，保留已有窗口与原候选库，结果写入新目录。
续跑流程、参数、来源文件与新输出清单见
[FFT_RESUME_README.md](fft_resume.md)。
