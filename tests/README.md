# BGS mask 朝向探索：直接网格测试

## 目的与当前范围

入口为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py`，
几何实现为同目录的 `orientation_geometry.py`。它们是无需安装到 LightGen 包的独立 Python 实验 pipeline。
本目录保存实验说明与运行结果，不是新增的 pytest 单元测试套件。

本轮仅使用二值天区选择。在用户给定的 observer 序列、盒长、红移/距离范围及网格分辨率下，
比较不同旋转候选的空间占据、重叠和累计覆盖。不搜索 observer 位置，不使用 FFT，
不读取 snapshot，不处理速度、RSD、completeness、径向数密度、KDTree、DD/DR/RR 或 MCF。
snapshot 红移不进入几何选择。

## 输入和依赖

依赖为 NumPy、SciPy、Astropy、healpy、Matplotlib；当前已在以下 Python 环境确认可用：

`/home/xiaoliang/.conda/envs/xiaoliang/bin/python`

无需安装新依赖或启动外部服务。也可在已加载上述依赖的 zsh/conda 环境使用 `python -B`。
无参数运行会显示完整帮助并以状态 0 退出，不创建运行目录：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py
~~~

默认 BGS 输入：

| 绝对路径 | 来源、内容及状态 |
|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` | 已存在的符号链接；HEALPix NESTED、NSIDE 8192；读取第一张表的第一个字段 `T` |
| `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` | 上述链接的已存在目标；仅像素值 `4` 选为天区 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py` | 本次创建的入口，负责参数、实验循环、日志及输出 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_geometry.py` | 本次创建的实现，负责 mask 查询、旋转、周期壳层及直接重叠计算 |

有效值 `4` 和赤道坐标 RA/DEC 查询约定来自现有
`/mnt/xiaodong/xiaoliang/DESImocks/src/method.py` 和 `/mnt/xiaodong/xiaoliang/DESImocks/src/generate_random.py`。
这些旧脚本只用于核对约定，运行新 pipeline 不会导入它们。
读取原始 mask 并逐块统计得到天区面积 `12562.35062330 deg^2`，未乘 completeness。
其他 mask 可通过 `--mask` 和 `--mask-values` 明确指定有效标签；坐标轴按其自身参考系解释。

## 处理步骤与旋转策略

1. 内存映射读取原始 HEALPix FITS；按指定有效标签查询，不对高分辨率 mask 重采样或写回。
2. 创建旋转候选库。所有策略都包含相同的基准朝向：
   - `axes`：绕 box 的 x/y/z 轴按给定角度扫描，去掉完全相同的旋转矩阵。
   - `random`：使用固定种子生成 Haar 均匀三维旋转。
   - `mask-diverse`：在随机候选池中，保留基准，并逐次选择与已选集合的最大角向 IoU 最小的候选。
3. 角向候选筛选使用 `--angular-nside` 的等面积 HEALPix 中心作为采样方向，但每个方向都查询原始 mask。
   它与三维 `--nmesh` 是两个独立参数，也不改变输入 mask 的 NSIDE。
4. 将 box 划分为 `nmesh^3` 个体素，采用体素中心。相对 observer 做 minimum-image 周期折叠，
   按 `rmin <= r < rmax` 选择壳层，再按旋转后的天空方向查询 mask，得到 0/1 占据。
5. 对每个 observer，评估策略候选库中的所有朝向：保存体素数、体积、相对解析体积误差、
   与该 observer 基准方向的 IoU，以及相对于此前已选光锥的累计覆盖分数。
6. 选择候选内部的平均已有覆盖次数最小者，随后可作局部微调；将选定光锥加入该策略自己的累计覆盖图。
   observer 的输入顺序就是累计覆盖顺序。各策略和各个网格/壳层维护独立覆盖图。
7. 可选局部微调按 `--refine-steps` 的输入顺序执行：在当前最优朝向附近，绕三条 box 轴分别试正负角度；
   一轮取最优者，无改进则停止该步长，否则最多执行 `--refine-rounds` 轮。
8. 保存数值结果、图像、参数、日志与逐文件清单。

第一位 observer 之前的覆盖图为零，所有非空候选分数同为零，因此稳定地选择候选库中的基准朝向。
后续也按候选顺序处理并列最优。局部调整仅接受严格改善；候选占据为空时不参与选择。

旋转矩阵 Q 使用列向量约定 `v_box = Q @ v_sky`；查询 mask 时，单位方向行向量使用 `sky = box @ Q`。
`--base-euler` 为 SciPy 的小写 `xyz` 外禀 Euler 角，单位为度。局部 box 轴旋转采用 `Q_new = D_axis @ Q`。
输出四元数顺序为 `x,y,z,w`。南北天始终作为同一个 mask 整体旋转。

## 指标定义

- `angular_iou_with_base`：固定 observer 下，两种朝向的角向 mask 交集/并集，使用角向采样估计。
- `reference_iou`：在当前三维网格、当前 observer 下，候选和基准占据的交集/并集。
- `reference_overlap_fraction`：候选与基准的交集体素数/基准占据体素数。
- `prior_coverage_sum`：候选占据体素内，之前累计覆盖次数的总和，即直接计算的重叠分数。
- `mean_prior_coverage`：上述总和/候选占据体素数；本轮选优使用此量，减弱不同朝向离散体积差异对原始分数的影响。
- `coverage_square_increment`：若接受候选，累计覆盖平方和增加 `2 * prior_coverage_sum + occupied_voxels`。
- `new_voxels`：候选中之前未被覆盖的体素数。
- `box_covered_fraction`：接受候选后，至少覆盖一次的体素数/整个 box 体素数。
- `volume_relative_error`：离散体积/真实 mask 面积乘连续球壳体积得到的解析体积 − 1。

归一化选择分数是本次初步实验的明确约定，不等同于直接最小化累计覆盖平方和；
原始分数、自身占据数和平方和增量全部保留，便于后续改变规则。

## 当前参数及最简用法

前四个位置参数依次是首个 observer 的 `X Y Z` 和周期盒边长 `BOXSIZE`，单位均为 `Mpc/h`。
再用可重复的 `--observer X Y Z` 添加后续 observer；第一个位置参数对应的 observer 总是最先放置。
全部坐标按周期边界折回盒内。其余参数仍以选项方式给出：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 32 --z-range 0.025 0.15 \
  --observer 1715.5 1530.2 1600.1 \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/bgs_orientation_new_example
~~~

以上为当前接口的示例命令，目标目录 `bgs_orientation_new_example` 尚未通过此命令生成。
实际运行时请确认输出目录不存在。只给前四个位置参数时也可以运行，但只有一个 observer 时，
各非空候选对已有覆盖的分数都为零，程序按并列顺序选择基准朝向；仍可查看候选与基准的重叠。

| 参数 | 用途及默认值 |
|---|---|
| `X Y Z BOXSIZE` | **必填**。首个 observer 坐标和盒长，单位 Mpc/h。 |
| `--mask PATH` | **必填**。输入 HEALPix FITS mask；BGS 文件见上表。 |
| `--nmesh N [N ...]` | **必填**。每个坐标轴的体素数；如 `32 64` 分别运行两种网格。 |
| `--z-range ZMIN ZMAX` | 观测红移范围；可重复，每个范围分别运行。使用 HR4 宇宙学换算距离。 |
| `--r-range RMIN RMAX` | 直接指定距离范围，单位 Mpc/h；可重复。与 `--z-range` 二选一且必须指定一种。 |
| `--output-dir PATH` | **必填**。新的输出目录；已存在的路径会被拒绝，避免覆盖。 |
| `--observer X Y Z` | 可选。追加一个 observer，可重复；追加顺序影响累计覆盖。 |
| `--mask-values V [V ...]` | mask 中哪些整数像素值属于有效天区；默认 `4`，对应现有 BGS mask。 |
| `--strategies ...` | 默认同时运行 `axes random mask-diverse`。也可只选其中一个或多个。 |
| `--angles-deg A [A ...]` | `axes` 策略绕各 box 轴试验的角度；默认 `30 60 90 120 150 180` 度，基准朝向自动包含。 |
| `--candidate-count N` | `random` 和 `mask-diverse` 各保留的候选总数，含基准；默认 `12`。`axes` 数量由角度及去重决定。 |
| `--pool-size N` | `mask-diverse` 筛选前的随机候选池大小，含基准；默认 `64`，须不小于 `--candidate-count`。 |
| `--angular-nside N` | 比较 mask 朝向相似度时的 HEALPix 采样分辨率，默认 `32`，须为 2 的幂；不改变原始 mask 分辨率。 |
| `--base-euler X Y Z` | 基准朝向的外禀 xyz Euler 角，单位度；默认 `0 0 0`。 |
| `--refine-steps A [A ...]` | 局部微调角度，单位度；默认不微调。每个步长分别尝试 box 各轴正负旋转。 |
| `--refine-rounds N` | 每个微调步长最多重复搜索的轮数；默认 `2`，只有指定 `--refine-steps` 时生效。 |
| `--seed N` | 随机候选种子，默认 `0`，相同输入和环境下用于复现候选库。 |
| `--chunk-size N` | 每批生成多少个三维网格中心，默认 `262144`；用于控制部分中间内存。 |
| `--save-windows` | 可选开关；保存所有被评估候选的压缩体素占据，默认不保存。 |
| `--no-plots` | 可选开关；不生成 PNG，默认生成。 |
| `-h`、`--help` | 显示帮助后退出；不传任何参数时也显示帮助。 |

## 已实际运行的低分辨率案例

以下**历史命令**已于 2026-11-12、旧参数接口下成功运行。它比较两个网格、三个 observer、
三类候选策略，并启用局部调整与候选占据保存。第三个 observer 靠近周期边界。
原始参数保留用于追溯历史结果；旧的 `--box-size` 和首个 `--observer` 写法不适用于当前接口。

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py \
  --box-size 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 32 64 \
  --observer 1575 1575 1575 \
  --observer 1715.5 1530.2 1600.1 \
  --observer 40 60 80 \
  --z-range 0.025 0.15 \
  --angles-deg 60 120 180 \
  --candidate-count 6 --pool-size 16 --angular-nside 32 \
  --refine-steps 3 1 --refine-rounds 1 --seed 20261112 \
  --save-windows \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/bgs_orientation_smoke_20261112
~~~

该结果目录已经存在；使用当前接口复跑时，须将 `1575 1575 1575 3150` 放在脚本后面，
删去旧的 `--box-size 3150` 和首个 `--observer 1575 1575 1575`，其余两个
`--observer` 保留，并更换 `--output-dir`。
`axes` 此例有 10 个候选，其他两类各有 6 个，因此这个小案例用于流程可行性，
不能据此宣称某策略在等成本条件下更优。

## 2026-11-13 位置参数验证

使用同一 BGS mask 和 32³ 网格，实际执行了以下两个新接口案例：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 32 --observer 1715.5 1530.2 1600.1 --z-range 0.025 0.15 \
  --strategies axes --angles-deg 60 120 180 --candidate-count 6 \
  --pool-size 16 --angular-nside 32 --refine-steps 3 1 \
  --refine-rounds 1 --seed 20261112 --no-plots \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/cli_positional_check_20261113

/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 32 --z-range 0.025 0.15 --strategies axes --angles-deg 90 \
  --angular-nside 8 --no-plots \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/cli_single_observer_check_20261113
~~~

两个输出目录均已存在，上述命令重新运行时须换成新的输出路径。
第一个案例的两个 observer 的选择记录和最终覆盖，与 2026-11-12 旧接口案例的相同配置逐项一致；
第二个案例核实了只使用位置参数时的单 observer 行为。无参数帮助也已核实。

两个 pipeline 案例的实际输入是上表已列的两个 Python 文件和 BGS FITS mask；未读取 snapshot。
对旧结果的独立比较还读取了：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/bgs_orientation_smoke_20261112/shell_00/nmesh_0032/axes/selections.csv`；
- 同一绝对目录下的 `observer_000/windows.npz`、`observer_000/overlap.npz`、
  `observer_001/windows.npz` 和 `observer_001/overlap.npz`。

上述均为已存在的旧案例输出，只读用于比较；本轮没有修改。
本轮生成的完整文件清单可直接读取：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/cli_positional_check_20261113/manifest.json`：
  已生成的 12 个文件的绝对路径，包括参数、日志、axes 候选库、两个 observer 的
  `candidates.csv` 与 `overlap.npz`、选择与覆盖结果、汇总及字体缓存。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/cli_single_observer_check_20261113/manifest.json`：
  已生成的 10 个文件的绝对路径，包括参数、日志、axes 候选库、单个 observer 的候选与交集、
  选择与覆盖结果、汇总及字体缓存。

这两个案例均指定 `--no-plots` 且未启用 `--save-windows`，因此未生成 PNG 或 `windows.npz`。
标准输出发往调用终端，日志同时记录在各自的 `pipeline.log`；没有单独的 stdout/stderr、
应用临时文件或检查点。Matplotlib 的字体缓存分别保存在两个运行目录的 `cache/matplotlib/`。
验证比较本身只在内存中运行并输出到终端，没有额外保存检查脚本或检查文件；
本轮没有覆盖、清理或删除任何已有结果。

进一步实验可逐项改变 `--nmesh`、observer、策略候选数和微调步长。
三个观测区间可重复传入：

~~~text
--z-range 0.025 0.15 --z-range 0.15 0.30 --z-range 0.30 0.40
~~~

也可用 `--r-range RMIN RMAX` 直接输入距离，适合其他盒长。两种范围模式互斥。
要求 `0 <= rmin < rmax <= box_size/2`；距离单位统一为 Mpc/h。
`--z-range` 使用 HR4 平直 LambdaCDM 的 Omega_m=0.26，不考虑辐射，不接收 snapshot 红移。

关键资源参数：

- `--chunk-size` 只控制生成网格中心时的分块；壳层索引和方向、候选压缩占据仍驻留内存。
- `--save-windows` 保存所有被评估候选的 bit-packed 占据；未启用时这些数组只在内存中存在。
- `--no-plots` 关闭 PNG 输出；healpy 导入仍可能触发 Matplotlib 的字体缓存。
- `--output-dir` 必须是新目录，不支持覆盖、续跑或检查点。

## 最终输出、中间输出、日志及缓存清单

以下将 `<RUN>` 定义为绝对路径
`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/{run_name}`。
本次实际的 `{run_name}` 为 `bgs_orientation_smoke_20261112`。
`ss` 为输入范围从 0 开始的两位编号，`nnnn` 为四位网格数，
`strategy` 为策略名，`ooo` 为 observer 从 0 开始的三位编号。

| 绝对路径或确定的命名规则 | 生成环节、格式及用途 | 本次是否生成 |
|---|---|---|
| `<RUN>/run.json` | 运行配置：绝对输入路径、mask 元数据/面积、单位、坐标约定、种子、版本、壳层距离 | 已生成 |
| `<RUN>/pipeline.log` | 运行 INFO、捕获的 Python warnings 和失败时的 traceback；同时向终端输出日志 | 已生成 |
| `<RUN>/libraries/{strategy}.npz` | 候选库：矩阵、xyzw 四元数、标签、角向二值采样签名和候选间角向 IoU | 三类策略均已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/observer_{ooo}/candidates.csv` | 每个候选的指标、来源、转角和最终选择标记；包含被评估的局部候选 | 已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/observer_{ooo}/overlap.npz` | 所有候选之间的三维交集体素数和 IoU；完整旋转矩阵/四元数、标签、selected_index | 已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/observer_{ooo}/windows.npz` | 可选中间占据：候选二维数组 `packed`，按全 box 扁平 0/1 数组打包；用于独立复算 | 本次启用并生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/observer_{ooo}/orientation_scan.png` | 左图为与该 observer 基准方向的体素 IoU；右图为平均已有覆盖；星号标出选定朝向 | 已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/selections.csv` | 各 observer 的最终选择和逐步覆盖诊断，引用该 observer 的候选编号 | 已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/coverage.npz` | 最终累计覆盖三维数组、盒长、observer 列表和壳层距离 | 已生成 |
| `<RUN>/shell_{ss}/nmesh_{nnnn}/{strategy}/coverage_projection.png` | 最终覆盖沿三条轴求和的投影；红色加号标记给定 observer | 已生成 |
| `<RUN>/summary.csv` | 所有壳层/网格/策略/observer 的选择与覆盖指标合表 | 已生成 |
| `<RUN>/manifest.json` | 运行完成/失败状态、绝对输入路径及实际输出文件逐项清单，含日志和缓存 | 已生成 |
| `<RUN>/cache/matplotlib/fontlist-v{version}.json` | Matplotlib 首次导入生成的字体缓存；此环境文件名为 `fontlist-v390.json` | 已生成 |
| `<RUN>/verification.json` | 本次交付时额外进行的轻量核对记录；不是 pipeline 自动输出 | 已生成，7 项检查均通过 |

NPZ 文件均可用 `numpy.load(path, allow_pickle=False)` 读取。
`coverage` 的轴顺序是 x,y,z，体素中心为 `(i+0.5)*L/nmesh`。
解包候选窗口使用：

~~~python
occupied = np.unpackbits(archive["packed"][candidate_id], count=nmesh**3)
occupied = occupied.reshape((nmesh, nmesh, nmesh))
~~~

这里使用 NumPy 默认的 big bit order 和 C 数组顺序。超出 `nmesh**3` 的填充位不能算入体素。
每个 observer 的所有候选都在同一份“接受该 observer 之前”的累计覆盖图上比较。
角向签名、三维占据和 mask-diverse 初始池等还存在内存中的中间量；初始池未单独持久化，
可按已记录的种子、参数、依赖版本及输入 mask 重新生成。

标准输出发往调用终端，日志消息也写入 `pipeline.log`；未创建独立 stdout/stderr 文件。
Python warnings 和捕获的运行异常写入日志。无应用级临时文件、检查点或下载缓存。
入口设置 `sys.dont_write_bytecode=True`，不主动生成 Python 字节码缓存。
Matplotlib 缓存被限制在 `<RUN>/cache/matplotlib/`，结果目录不会自动清理；
失败时保留已产生文件并尽可能写入失败 manifest。现有输出目录一律拒绝，不会覆盖或删除。

本次依赖探测曾由 Matplotlib 自动创建 `/tmp/matplotlib-4k6g6cvp`；
探测进程退出后核查该目录已不存在。正式案例的字体缓存位于上表的运行目录内。

该案例实际检查了 18 个“网格/策略/observer”组合、348 个候选朝向。
轻量核对包括 observer 平移一个盒长后的周期一致性、平移一个体素后的数组滚动一致性、
旋转 360 度的一致性、旋转矩阵的正交性和行列式、解包后直接重算全部候选交集、
累计重叠分数及平方和增量，以及从选定候选重建最终覆盖图。
无参数帮助已实际运行；未进行全仓回归测试。

## 解释结果时的边界

这是粗体素中心采样的几何实验。32/64 网格不足以解析原始 mask 的全部边界，
体积相对误差和朝向排序会受离散化影响；它们正是本轮需要观察的量。
角向候选筛选使用独立的粗角向样本，同样需要比较采样分辨率和种子。
不同朝向可以具有相同的相对旋转角，因此图上横坐标相同并不表示相同的三维朝向；
应结合 NPZ 中的完整旋转矩阵解释结果。
当前选择目标是几何重复覆盖，尚未验证其对最终 AP 系统误差估计的改善，也未运行 HR4 snapshot 流程。

## 单策略实验与比较组

本节说明另外两个脚本：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_strategy.py`：
  复用 `orientation_geometry.py`，每次在一个网格、一个壳层和一种策略上，
  按 observer 顺序直接计算候选窗口、选择朝向并累计覆盖。它不调用 FFT，不依赖原 pipeline 入口。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py`：
  递归读取**一个比较组目录**内所有 `result.json`，展示每次运行的参数及多个指标，
  可选导出 CSV。它不读取 mask、不重新计算几何。

依赖和运行环境与上文一致；两个入口无参数时均打印帮助并以状态 0 退出。
`eval_strategy.py` 的位置参数同样是 `X Y Z BOXSIZE`，其他 observer 用 `--observer` 追加；
它使用 `--strategy` 指定单个策略，`--nmesh` 接受单个整数，`--z-range` 或 `--r-range` 各接受一个区间。
`--save-candidates` 生成每个 observer 的候选 CSV 和包含完整旋转矩阵的 NPZ；
`--save-coverage` 生成最终覆盖 NPZ。其他几何/候选参数与上文同名参数含义一致。

`compare_results.py` 的位置参数是比较组目录，`--sort-by` 可指定排序指标，默认按运行名排序；
`--show-observers` 附带每个 observer 的指标。`--output-csv` 可选指定新的 CSV 输出路径。
脚本不自动判断哪些条件应该相同：由使用者通过目录选择待对比结果，每个结果的完整参数会在终端及 CSV 中列出。
输出路径已存在时导出会失败，不会覆盖原文件。

保留的对比量包括累计覆盖比例、覆盖均值/方差、最大覆盖次数、平均已有覆盖、
累计已有覆盖体素数、覆盖平方和增量之和，以及选定光锥体积相对误差的平均值和绝对值均值/最大值。
`--show-observers` 还显示每个 observer 的原始重叠、平方和增量、新覆盖体素数、基准 IoU 和体积误差。
原始体素数随网格分辨率变化；不同网格的体素计数应结合体素大小解释。
第一个 observer 前没有已有覆盖，因此其平均已有覆盖为零；汇总平均值包含该 observer。

## 2026-11-13 比较组：实际执行

比较组的绝对路径为：

`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113`

该组已运行三个策略和 32、64 两种网格，低红移范围为 0.025–0.15，两个 observer 和 seed 均相同。
`axes` 使用 `30 60 90 120` 度及基准方向，共 13 个候选；其他两种策略也保留 13 个候选。
未启用局部微调，启用了 `--save-candidates` 和 `--save-coverage`。六次运行之一的实际命令为：

~~~sh
MPLCONFIGDIR=/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113/_matplotlib_cache \
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_strategy.py \
  1575 1575 1575 3150 \
  --mask /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits \
  --nmesh 32 --observer 1715.5 1530.2 1600.1 --z-range 0.025 0.15 \
  --strategy axes --angles-deg 30 60 90 120 \
  --candidate-count 13 --pool-size 26 --angular-nside 32 --seed 20261112 \
  --save-candidates --save-coverage \
  --output-dir /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113/axes_n32
~~~

其余五次改变 `--strategy` 为 `axes`、`random`、`mask-diverse` 和 `--nmesh` 为 `32`、`64` 的组合，
并将输出目录改为下表对应的 `{strategy}_n{nmesh}`；其余参数相同。
所有六个输出目录已存在，重新运行时须使用新的比较组和输出目录。

查看现有组、打印逐 observer 指标：

~~~sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py \
  /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113 \
  --show-observers
~~~

本次另使用 `--output-csv` 生成了 `comparison_metrics.csv`。同目录的 `comparison.csv` 是较早一次
汇总生成的版本，保留用于追溯；它不含后加的 `total_coverage_square_increment` 字段。
两个文件均已生成，未覆盖。旧比较组
`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/modular_smoke_20261113`
也已只读验证：脚本读取其中 `axes/result.json`、`random/result.json`、
`mask_diverse/result.json` 并在终端显示，未在旧目录写新文件。

本次新比较组的输入与完整输出清单如下。`<GROUP>` 指上述比较组的绝对路径；
`{strategy}` 为 `axes`、`random`、`mask-diverse`，`{nmesh}` 为 `32`、`64`，
`{obs}` 为 `000`、`001`。六种策略/网格组合均已运行：

| 绝对路径或确定命名规则 | 生成环节、格式与用途 | 本次状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_strategy.py` | 单策略实验入口，Python 源码 | 已存在并用于运行 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_geometry.py` | HEALPix、周期几何与候选评估实现 | 已存在，只读导入 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/compare_results.py` | 读取组内结果并输出汇总，Python 源码 | 已存在并用于汇总 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` | HEALPix BGS 输入，符号链接 | 已读取；目标为 `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` |
| `<GROUP>/{strategy}_n{nmesh}/result.json` | 参数条件、每个 observer 的选择及汇总指标 | 六个已生成 |
| `<GROUP>/{strategy}_n{nmesh}/selections.csv` | 每个 observer 的选择和指标 | 六个已生成 |
| `<GROUP>/{strategy}_n{nmesh}/candidates_observer_{obs}.csv` | 每个候选的体积和重叠指标 | 十二个已生成 |
| `<GROUP>/{strategy}_n{nmesh}/candidates_observer_{obs}.npz` | 候选矩阵、四元数、标签、选中索引 | 十二个已生成 |
| `<GROUP>/{strategy}_n{nmesh}/coverage.npz` | 最终三维累计覆盖数组及几何条件 | 六个已生成 |
| `<GROUP>/comparison.csv` | 初次生成的汇总 CSV，含完整参数 | 已生成并保留 |
| `<GROUP>/comparison_metrics.csv` | 加入覆盖平方和指标后的汇总 CSV，含完整参数 | 已生成 |
| `<GROUP>/_matplotlib_cache/fontlist-v390.json` | 本次显式设置 `MPLCONFIGDIR` 后的字体缓存 | 已生成 |

本次比较组共 45 个文件。逐项验证时读取了上述运行结果、候选 NPZ/CSV 和汇总 CSV；
直接数值核对结果只输出终端，未保存额外检查脚本或文件。标准输出/错误发往终端，
没有单独的 stdout、stderr 或运行日志文件；应用未写入临时文件或检查点。
运行过程保留已有文件，没有覆盖、清理或删除。后续若未设置 `MPLCONFIGDIR`，
healpy 导入时 Matplotlib 缓存位置由当时环境决定。

已核对每种策略在 32/64 两个网格上的 13 个候选矩阵完全一致，并核对选中索引、结果参数、
绝对体积误差及覆盖比例。三个策略的随机生成方式未改动；同一数字 seed 下的 `random`
和 `mask-diverse` 仍使用各自的候选池。此组是小规模几何探索，不代表策略性能结论。

## FFT 联合放置

新入口 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py` 将 FFT 位置搜索与候选朝向库结合，
支持周期最小 observer 间距和确定性的 maximin 平局规则。
完整工作流程、参数、依赖、输入输出清单和实际运行记录见
[FFT_README.md](FFT_README.md)。
