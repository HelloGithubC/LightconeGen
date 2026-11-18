# LightconeGen Python 包

本文说明 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/` 中的可导入包。包用于在周期模拟盒中搜索和应用光锥窗口几何：输入角向 survey mask 和一个径向区间，返回 observer 位置、朝向与网格平移。包可以按光锥布局生成用于配对统计的无聚集随机点。

原五个 Python 脚本保持字节级原样，位于 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/`：`orientation_geometry.py`、`orientation_pipeline.py`、`eval_strategy.py`、`eval_fft.py`、`compare_results.py`。它们仍是独立 CLI，沿用旧参数、默认值和输出格式。历史实验文档记录的是这些脚本产生的结果，不是新包的运行结果。

## 安装、依赖与导入

在项目根目录执行以下命令，将包安装到当前 Python 环境：

```sh
cd /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -m pip install -e .
```

这只是使用说明；本次没有执行安装，也没有修改环境或安装依赖。项目已有解释器为 `/home/xiaoliang/.conda/envs/xiaoliang/bin/python`，依赖版本为 NumPy 2.2.6、SciPy 1.15.2、Astropy 6.1.7、healpy 1.19.0、Matplotlib 3.10.6、setuptools 82.0.1。NumPy 提供数组和 NPZ 持久化；SciPy 用于 FFT、旋转和距离积分；Astropy 读取 FITS；healpy 查询 HEALPix mask；Matplotlib 用于显式绘图，healpy 导入也可能加载它；setuptools 用于构建 editable 安装。

公开导出如下：

```python
from lightconegen import (
    Lightcone, LightconeLayout, SearchResult, SkyMask,
    create_random_mock, load_layout, load_result, plot_coverage, rebuild_coverage,
    resume_search, save_result, search_lightcones, select_points,
)
```

也可以把 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src` 放进 `PYTHONPATH` 后直接导入。导入 `lightconegen` 本身不读取输入数据、不创建目录或文件、不写缓存、不设置环境变量、不安装日志处理器，也不导入 `pyplot`。普通 Python 运行时可能生成 `__pycache__`；用 `-B` 或设置 `PYTHONDONTWRITEBYTECODE` 可禁止字节码写入。healpy 查询或显式绘图可能使 Matplotlib 创建字体缓存；缓存目录由调用方的 `MPLCONFIGDIR` 决定。包不负责清理这些 Python/Matplotlib 运行时文件。

## 坐标约定与算法流程

所有长度为 Mpc/h。盒长记作 `L`，网格边长为 `nmesh`；体素中心为 `(i + 0.5) * L / nmesh`，坐标轴为 x、y、z，数组采用 C-order。边界条件为三维周期边界。观测者 `observer` 是 xyz 盒坐标；`observer=None` 时使用盒子中心 `(L/2, L/2, L/2)`。首个 observer 是锚点，后续位置由锚点加整数网格移位并按周期边界折回。朝向以外禀 xyz 欧拉角（度）描述。

`z_range` 使用 HR4 平直宇宙学 Ωm=0.26、ΩΛ=0.74。红移到共动距离的积分由 SciPy `quad` 计算；Astropy 用于读取 FITS，不负责此距离积分。`r_range` 直接给出 Mpc/h 距离。球壳采用内边界包含、外边界不包含的约定。mask 使用 FITS 路径时由 Astropy 读取；也可传入调用者创建的 `SkyMask`。BGS mask 标签默认固定为 4。若需其他标签，可创建 `SkyMask(path, values=...)` 并传入；紧凑布局不保存此标签设置。调用者传入的 SkyMask 仍由调用者持有，包会缓存其面积信息，不关闭该对象。

搜索按以下步骤执行：

1. 读取/接收角向 mask，按 `z_range` 或 `r_range` 建立径向壳层，并按 `nmesh` 生成网格几何。
2. 按策略生成有限朝向候选。`base` 只用基准朝向；`axes` 加入绕盒轴的固定角度；`random` 从固定随机种子的池中取候选；`mask-diverse` 从池中按 mask 角向差异选候选。
3. 在锚点建立窗口模板，首个窗口作为后续整数平移的基准。
4. 逐个增加窗口，计算覆盖重叠并按候选评分选择移位和朝向；可同时施加周期 observer 最小距离与平均先验重叠停止阈值。
5. 返回内存中的 `SearchResult`。`result_mode="layout"` 不保留覆盖及诊断；`result_mode="full"` 保留覆盖、候选库和搜索记录。两者搜索过程都需要临时内存；任何结果都不会仅因调用搜索而写入磁盘。

此算法在有限网格与有限朝向候选上逐窗搜索。覆盖率和 observer 间距描述几何性质，不表示 mock 的统计独立性。

## 搜索接口和参数

```python
search_lightcones(
    boxsize, mask, *, z_range=None, r_range=None, observer=None,
    nmesh=64, num_cones=5, strategy="axes", angles_deg=(30, 60, 90, 120),
    base_euler=(0, 0, 0), candidate_count=13, pool_size=64,
    angular_nside=32, seed=20261115, min_observer_distance=0,
    max_mean_prior=None, workers=8, chunk_size=262144,
    result_mode="layout", cosmology="HR4",
)
```

| 参数 | 用途 |
|---|---|
| `boxsize` | 周期立方盒边长，单位 Mpc/h。 |
| `mask` | FITS 路径或 `SkyMask` 实例。BGS 默认接受标签 4；需用其他标签时自行构造 `SkyMask(path, values=...)`。 |
| `z_range`、`r_range` | 红移上下限，或径向距离上下限（Mpc/h）；两者恰选其一。HR4 是当前唯一支持的宇宙学。 |
| `observer` | 首个锚点 observer 的 xyz 位置；省略或为 `None` 时取盒子中心。 |
| `nmesh` | 每条盒边的网格数；决定体素中心、可选移位和离散几何精度。 |
| `num_cones` | 窗口总数，包含锚点处首个窗口。 |
| `strategy` | `base`、`axes`、`random` 或 `mask-diverse` 朝向候选策略。 |
| `angles_deg` | `axes` 策略使用的固定角度。 |
| `base_euler` | 基准外禀 xyz 欧拉角，单位度。 |
| `candidate_count` | 池策略请求的候选数，含基准朝向；不决定 `axes` 策略候选数。 |
| `pool_size` | `random` / `mask-diverse` 使用的随机候选池大小。 |
| `angular_nside` | HEALPix 角向候选签名/多样性采样分辨率，不降低占据计算所用原始 mask 分辨率。 |
| `seed` | 随机候选生成种子。 |
| `min_observer_distance` | observer 间最小周期距离，单位 Mpc/h；0 表示不限制。 |
| `max_mean_prior` | 可选的下一窗口最小平均先验重叠停止阈值；`None` 表示不启用。 |
| `workers` | 并行计算 worker 数。 |
| `chunk_size` | 每批处理的网格位置数，控制计算分块。 |
| `result_mode` | `layout` 或 `full`。前者返回紧凑几何；后者附带完整覆盖和搜索诊断。 |
| `cosmology` | 红移到距离的模型名；当前只支持 `HR4`，Ωm=0.26、ΩΛ=0.74。 |

默认 BGS mask 输入为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits`，其数据链接目标为 `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits`。这两个是本机输入路径，不由包生成。

## 结果类型、读写和应用

`SearchResult` 提供 `layout`、`mode`、`selections`、`candidates`、`arguments`、`final_metrics` 和 `mask_info`。`LightconeLayout`、`Lightcone` 是布局数据类型；按属性访问，例如 `layout.lightcones[i].observer`，不是用字典键访问。

紧凑 `layout.json` 只包含 `boxsize`、`z_range` 或 `r_range`、`cosmology: "HR4"`、mask basename、`nmesh` 和 `lightcones`。每个窗口记录 `observer: [x,y,z]`、`orientation: [三个外禀 xyz 欧拉角，单位度]`、`shift: [整数 kx,ky,kz]`。按约定文件不保存旋转矩阵、RA/DEC、哈希、格式/来源版本或 mask 标签。

`save_result(result, output_dir)` 要求目标目录不存在。布局模式只写 `layout.json`，没有 manifest。full 模式写八个必需文件：`layout.json`、`coverage.npz`、`library.npz`、`selections.csv`、`search_candidates.csv`、`observer_distances.csv`、`result.json`、`manifest.json`。manifest 仅在完整保存成功后写入；若中途异常，异常向调用者传播，已写入的部分文件保留，不保证生成失败 manifest。

`coverage.npz` 包含 `coverage`（`uint32` xyz 三维数组）、`box_size`、`observers`、`shifts`、`rmin`、`rmax`。`library.npz` 包含 `matrices_sky_to_box`、`quaternions_xyzw`、`labels`、`occupied_voxels`、`angular_signatures`。其余 CSV 分别记录被接受窗口、搜索候选诊断及 observer 成对周期距离；`result.json` 保存完整结果配置和指标；`manifest.json` 记录成功保存的清单。

`load_layout(path)` 读取紧凑布局或旧 `result.json`，对旧格式中的旋转矩阵转换为欧拉角。`load_result(full_dir)` 读取新 full 存档，也兼容旧已完成 FFT 结果。`resume_search(full_result_or_directory, num_cones, *, mask=None, result_mode="full", workers=None, chunk_size=None, max_mean_prior=None)` 续跑完整结果；可选 mask 覆盖来源 mask，其余三个可选计算/停止参数若未指定则继承原结果。续跑保留已有选择与原候选库。包不调用旧脚本，不通过 subprocess 导入旧实现。

`rebuild_coverage(layout, *, mask=None, mask_dir=".", chunk_size=262144)` 返回 `uint32` 覆盖立方体，使用锚点模板及整数移位重建。`select_points(positions, layout, cone_id=0, *, mask=None, mask_dir=".", chunk_size=262144)` 返回输入位置数组中位于指定窗口的行索引。它不解析文件格式、不假设 velocity 列、不计算 RSD、不写回或裁剪原始目录。`plot_coverage(coverage, path, *, boxsize, observers=())` 接受覆盖 ndarray，不接受 `SearchResult`；将图写入指定路径，拒绝已有文件，并创建所需父目录。绘图是显式调用，不会在搜索时自动生成。

## 生成随机目录

`create_random_mock(layout, number_density, cone_id=0, *, mask=None, mask_dir=".", seed=None, frame="box", chunk_size=262144)` 为一个已有光锥生成供 `DR`、`RR` 使用的随机点。使用现有 NumPy 随机数生成器、HR4 距离换算及 Astropy/healpy FITS mask 接口。

1. 从 `layout` 取壳层径向范围和第 `cone_id` 个光锥，编号从 0 开始。用原生二值 mask 算有效立体角 `Ω`，从而得到共动体积 `V = Ω * (rmax³ - rmin³) / 3`。按 `round(number_density * V)` 确定点数。数密度单位为 `(h/Mpc)^3`，接受 0，结果此时为 `(0, 3)` 数组。
2. 分批在球面均匀抽 `RA` 与 `sin(DEC)`，按原生 mask 筛选方向。对每个通过的方向独立均匀抽 `r³` 得到共动距离。`chunk_size` 是每批角向候选点数上限。传固定整数 `seed` 可复现相同参数下的结果，也可传入一个 NumPy `Generator` 连续生成不同目录。
3. 返回 `float64` 的 `(N, 3)` 笛卡尔数组，单位 Mpc/h。默认 `frame="box"` 按光锥朝向旋转，平移至 observer 并按周期边界折回，与 `select_points` 的输入一致。`frame="sky"` 以 observer 为原点，沿 mask 天球轴输出，适用于同样坐标下的观测式配对。点的位置独立于 FFT 搜索网格的 `nmesh`。

`mask` 接受 FITS 路径或已有的 `SkyMask`。省略时通过 `mask_dir / layout.mask` 查找；循环处理多个光锥时可以重用一个打开的 `SkyMask`，它会缓存掩膜面积。以下示例可在现有 Python 环境导入包后执行，也可通过 `PYTHONPATH=/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src` 和 `python -B` 从源码调用：

```python
from lightconegen import create_random_mock, load_layout

layout = load_layout(
    "/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/"
    "module_refactor_20261115/without_mask/compact_n15/layout.json"
)
random_xyz = create_random_mock(
    layout, number_density=1e-5, cone_id=2,
    mask_dir="/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask",
    seed=41, frame="sky", chunk_size=2048,
)
```

2026-11-18 定向核对使用上述布局和参数，通过已打开的原生 BGS `SkyMask` 分别生成两种坐标。每种得到 9,264 点，盒坐标全部通过 `select_points`，包含跨周期边界的点。两种坐标的相互转换与输出一致。径向的四个等体积区间分别得到 2,326、2,275、2,330、2,333 点。零数密度和舍入后为零的情况均返回空数组。

| 输入或输出路径 | 来源、内容和实际状态 |
|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/compact_n15/layout.json` | 既有 N=15 布局 JSON，提供壳层、朝向与 observer。已读取。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` → `/mnt/xiaodong/xiaoliang/DESImocks_old/source/BGSmask_nside8192_nested.fits` | 原生 NESTED FITS，标签 4 定义有效天区。已读取。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/randoms.py`、`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/__init__.py` | 前者新增 Python 采样实现，后者新增公开导出。已写入。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/README.md`、`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/Readme.md`、`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/doc/MODULE.md` | Markdown 入口、接口说明与本次实测清单。已更新。 |
| 内存中的 `random_xyz` 和采样中间量 | 核对实际生成两份 `float64` xyz 数组、候选方向、半径与验证索引，均随进程结束释放。函数的返回数组由调用者决定如何保存和使用。 |
| `/tmp/lightconegen-random-we3izg8_/fontlist-v390.json` | 核对时 healpy/Matplotlib 实际生成的字体缓存。核对用临时目录，结束时整体删除。 |
| 终端 stdout/stderr、字节码、日志、检查点 | 核对结果只打印到终端。使用 `python -B`，没有生成字节码、本地随机数据文件、独立日志、临时脚本或检查点。 |

当前随机目录采用二值 mask 和恒定共动数密度。随红移变化的 `dN/dz`、completeness 权重及 RSD 处理留在实际观测选择流程中。验证使用既有布局与原生 mask，没有读取真实 snapshot 或运行配对统计。

## 文件与副作用

以下区分输入、程序源文件、运行输出与可能由解释器/依赖创建的文件。文档中的 `package_example` 和 512³ 示范搜索尚未执行；本次实际核对包括旧存档读写、派生 mask 的 16³ 搜索与原生 mask 的 32³ 搜索。安装命令未执行。

### 输入和程序文件

| 绝对路径或规则 | 来源、用途、格式 | 状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/__init__.py` | 定义公开 API 和导出。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/models.py` | 布局、lightcone、搜索结果等数据类型。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/geometry.py` | `SkyMask`、网格、周期边界和窗口几何运算。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/search.py` | 候选朝向与 observer 搜索。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/reconstruct.py` | 覆盖重建与点位置选择。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/io.py` | 布局/完整结果读写及绘图。 | 仓库源文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/pyproject.toml` | 包构建元数据和依赖配置，editable 安装读取。 | 仓库配置文件；本次未安装。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/.gitignore` | 忽略规则。 | 仓库配置文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/orientation_geometry.py` | 旧几何共享库。 | 原脚本保留。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/orientation_pipeline.py` | 旧综合直接计算入口。 | 原脚本保留。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/eval_strategy.py` | 旧单策略入口。 | 原脚本保留。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/eval_fft.py` | 旧 FFT 搜索入口。 | 原脚本保留。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/compare_results.py` | 旧结果汇总入口。 | 原脚本保留。 |
| `/home/xiaoliang/.conda/envs/xiaoliang/bin/python` | 示例使用的项目解释器。 | 已有环境。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/*.fits` | 本地 mask 符号链接，是旧实验/新包读取 FITS mask 的输入入口。 | 四个链接已重建，目标位于 `/mnt/xiaodong/xiaoliang/DESImocks_old/source/`，当前均存在。 |
| `/mnt/xiaodong/xiaoliang/DESImocks_old/source/BGSmask_nside8192_nested.fits` | 原生 BGS NESTED NSIDE8192 mask 的当前链接目标。 | 已实际读取，用于 32³ 核对。另三份 FITS 仅核对表头，四份逐项路径见 [mask 清单](../mask/README.md)。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115/` | 旧 N=5 完整结果，供加载/保存核对；`library.npz` 的首个角向签名还用于生成派生 mask。 | 已只读使用；全部原文件校验值不变，逐项内容见 [N=5 记录](experiments/fft_placement.md)。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115/result.json` | 旧 N=15 完整结果 JSON，转换为精简布局的输入。 | 已只读使用；原存档各文件均未改动，见 [N=15 记录](experiments/fft_resume.md)。 |
| 调用者给定的 `mask` 路径或 `SkyMask` | 搜索、重建、点选择使用的 mask。 | 外部输入；传入的 SkyMask 由调用者持有。 |
| 调用者给定的 `positions` ndarray | `select_points` 的点坐标。返回值是其行索引。 | 内存输入，不保存、不修改。 |
| `load_layout` / `load_result` 的路径参数 | 紧凑 `layout.json`、旧 `result.json` 或 full 结果目录。 | 外部只读输入。 |

下面 full 模式的八条输出规则，分别实际生成于三个绝对目录：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5`：旧结果重新保存。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full`：派生 mask 的新搜索。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/full`：原生 mask 的新搜索。

将任一目录代入 `<OUTPUT_DIR>`，即得到每项文件的确定绝对路径。下表状态中的旧 N=5 路径只描述第一组；后两组的全部文件也已实际生成，来源为对应的小网格搜索。

### 新包输出和运行时文件

| 绝对路径或确定规则 | 生成环节、用途、格式 | 当前状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/package_example/` | README 示例传给 `save_result` 的新输出目录。 | 示例路径，尚未创建。 |
| `<OUTPUT_DIR>/layout.json` | `save_result` 的 compact 模式唯一输出；记录几何布局。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/layout.json`（从已有 N=5 完整结果加载/保存）及 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/compact_n15/layout.json`（15 个 lightcone，由已有结果转换保存）；均不是新搜索。README 示例目录仍未创建。 |
| `<OUTPUT_DIR>/coverage.npz` | full 模式覆盖和几何参数归档；包含 `coverage:uint32`、`box_size`、`observers`、`shifts`、`rmin`、`rmax`。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/coverage.npz`；从已有完整结果加载/保存，不是新搜索。 |
| `<OUTPUT_DIR>/library.npz` | full 模式候选库归档；包含 `matrices_sky_to_box`、`quaternions_xyzw`、`labels`、`occupied_voxels`、`angular_signatures`。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/library.npz`；从已有完整结果加载/保存，不是新搜索。 |
| `<OUTPUT_DIR>/selections.csv` | full 模式已接受窗口和选择记录。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/selections.csv`；从已有完整结果加载/保存。 |
| `<OUTPUT_DIR>/search_candidates.csv` | full 模式候选搜索与诊断记录。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/search_candidates.csv`；从已有完整结果加载/保存。 |
| `<OUTPUT_DIR>/observer_distances.csv` | full 模式 observer 成对周期距离。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/observer_distances.csv`；从已有完整结果加载/保存。 |
| `<OUTPUT_DIR>/result.json` | full 模式完整结果参数和指标；供载入、续跑和分析。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/result.json`；从已有完整结果加载/保存。 |
| `<OUTPUT_DIR>/manifest.json` | full 保存成功后写入的文件清单。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/manifest.json`；full 保存成功。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/comparison.csv` | 旧比较器读取新 full archive 后生成的比较表。 | 已生成；不是搜索产物。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/verification.json` | 不依赖 mask 的定向核验汇总。 | 已生成；核验通过，耗时 9.376592 s。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/verification.json` | 首次尝试加载本地真实 mask 的失败记录。 | 已生成；因 FITS 符号链接目标缺失而立即失败，未执行 mask 检查。 |
| 调用者传给 `plot_coverage` 的绝对 `path` | 显式绘图的图片文件。该函数拒绝覆盖已有文件并创建父目录。 | 已生成 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/coverage_projection.png`；另有两幅 legacy 图，见后面的实际清单。 |
| 进程 stdout/stderr | 函数返回信息或 Python 异常由调用进程处理。 | 核对输出显示于终端；原生对照旧 CLI 的 stdout/stderr 另捕获到 `with_native_mask/verification.json` 对应字段，无独立重定向文件。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/__pycache__/` 和 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/__pycache__/` 下的 `*.pyc` | 普通 Python 导入可能生成字节码；`python -B` 或 `PYTHONDONTWRITEBYTECODE` 可禁用。 | 本轮使用 `-B`，最终检查两目录均不存在。 |
| `$MPLCONFIGDIR/fontlist-v*.json`（未设置时由 Matplotlib 选择用户缓存路径） | healpy mask 查询或显式 Matplotlib 绘图可能触发字体缓存。 | 本轮将缓存限制在核对目录；四个实际 `fontlist-v390.json` 的绝对路径见后文，均保留。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/build/` | 本地构建工具可能创建的构建中间目录。 | editable 安装/构建前的可能产物；本次没有执行安装。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen.egg-info/` 或 setuptools 选择的对应 egg-info 目录 | editable 安装产生的包元数据。 | 安装/构建前的可能产物；本次没有执行安装。 |
| 临时文件、FFT 磁盘缓存、检查点、独立日志 | 包的搜索/保存流程没有定义这些自动输出。 | 包不创建；没有自动清理或删除步骤。 |

`<OUTPUT_DIR>` 代表传给 `save_result` 的绝对新目录，例如示例对应 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/package_example`。现存目标目录会被拒绝，不会覆盖。compact 保存仅创建 `layout.json`；full 保存成功时创建表中八个文件。保存中途异常时已写部分文件保留，且不保证有 manifest。`plot_coverage` 的输出路径由调用者逐次指定；已有文件会被拒绝。

### 安装和检查相关文件

| 绝对路径或规则 | 来源与用途 | 当前状态 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/` 下的包安装元数据、editable link | `python -m pip install -e .` 可能在环境或源码树写入。 | 命令尚未执行，因此未确认生成；安装后以 pip/setuptools 实际行为为准。 |
| Python/依赖的安装缓存目录 | 仅安装依赖时可能由 pip 使用。 | 本任务未安装依赖，未生成新安装缓存。 |
| 历史运行目录 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/` 下旧实验文件 | 由 legacy CLI 和后处理产生，具体清单/哈希见实验记录。 | 历史文件状态见旧记录；不是新包输出，不在本次删除或覆盖范围。 |

## 两种保存模式及 API 示例

以下搜索示例和目标目录均未执行/创建。它使用已保存实验的几何条件作为示范，保存布局模式只会产生指定的一个 JSON 文件：

```python
from lightconegen import save_result, search_lightcones

result = search_lightcones(
    boxsize=3150.0,
    mask="/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits",
    z_range=(0.30, 0.40),
    observer=(1575.0, 1575.0, 1575.0),
    nmesh=512,
    num_cones=5,
    strategy="axes",
    angles_deg=(30, 60, 90, 120),
    min_observer_distance=500,
    result_mode="layout",
)
save_result(
    result,
    "/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/package_example",
)
```

续跑需要保存 `result_mode="full"`。跨设备重建覆盖和筛选点只需精简的 `layout.json` 及接收设备上的同一 mask。下面是独立的调用示例，路径须由调用者提供，尚未执行：

```python
import numpy as np
from lightconegen import (
    load_layout, load_result, rebuild_coverage, resume_search, select_points,
)

full = load_result("/absolute/path/to/full_result")
continued = resume_search(full, num_cones=15)
layout = load_layout("/absolute/path/to/layout.json")
coverage = rebuild_coverage(layout, mask_dir="/absolute/path/to/mask")
positions = np.asarray([[100.0, 200.0, 300.0]])
row_indices = select_points(
    positions, layout, cone_id=0, mask_dir="/absolute/path/to/mask",
)
```

调用者输入的 `positions` 只在内存中处理，输出 `row_indices` 也是内存数组。以上示例不隐含创建目录、日志、checkpoint 或其他未列文件。

## 旧实验文档

以下文档保留旧 CLI 的命令、实测产物、路径及核验记录。它们不作为新包的运行证据：

- [旧直接计算与比较组](experiments/direct_grid.md)
- [旧 FFT 放置实验](experiments/fft_placement.md)
- [旧 FFT 续跑实验](experiments/fft_resume.md)
- [历史使用说明](README.md)
- [仓库维护与文件记录](REPOSITORY.md)

## 本次验证记录

不依赖 mask 的定向核验通过，耗时 9.376592 秒。报告为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/verification.json`。纯数组 FFT 与直接 roll 计数在 7³ 和 8³ 网格所有移位上相等；距离图及平局选择也一致，最大舍入残差分别约 `2.84e-14` 和 0。旧 N=5 full 结果的保存/载入保持 coverage、candidate library、selections 和 search history 相等；紧凑 N=15 布局 round-trip 相等、字段符合约定，欧拉角往返矩阵最大绝对误差约 `3.33e-16`。已有输出目录冲突会被拒绝。四个迁移后的 CLI 不带参数时帮助检查通过；旧比较器可以读取新 full archive。检查使用 `-B`，未安装包或依赖、未创建测试文件，也未导入 pyplot。

这次验证生成的实际文件逐项如下，来源都是已有结果的读写/比较与核验，不是新的 BGS 搜索：

| 绝对路径 | 来源和用途 |
|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/layout.json` | 加载既有 N=5 完整结果并保存的紧凑布局。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/coverage.npz` | 同次 full round-trip 的覆盖及几何信息。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/library.npz` | 同次 full round-trip 的候选库。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/selections.csv` | 同次 full round-trip 的窗口选择记录。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/search_candidates.csv` | 同次 full round-trip 的候选搜索记录。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/observer_distances.csv` | 同次 full round-trip 的 observer 距离记录。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/result.json` | 同次 full round-trip 的结果配置。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/full_n5/manifest.json` | full 保存成功后生成的文件清单。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/compact_n15/layout.json` | 既有 N=15 结果转换并保存的紧凑布局，15 个窗口。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/comparison.csv` | 旧比较器读取新包 full archive 后导出的比较记录。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/without_mask/verification.json` | 上述通过项和未运行项的核验报告。 |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/verification.json` | 首次真实 mask 检查立即失败的报告，错误为 `FileNotFoundError`，耗时约 0.00026 秒。 |

此前真实 mask 验证失败的原因是本地四个 FITS 链接指向已改名的数据目录。用户确认数据目录已改名为 `DESImocks_old` 后，四个链接均已重建，目标现已存在。初始失败记录仍保留在 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/verification.json`。链接修复前使用派生 NSIDE32 mask 完成独立核验，修复后又完成原生 NSIDE8192 BGS mask 核验。

### 派生 mask 核验

使用的 mask 输入是 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/derived_mask/BGS_signature_nside32_nested.fits`。它由既有 N=5 full 结果的 `base angular_signatures[0]` 派生为 NSIDE32 NESTED、标签 4 的 FITS mask，共 3760 个有效像素；它不是原始 NSIDE8192 BGS mask。搜索使用 3150 Mpc/h、z3、16³ 网格、N=5、同原生核对的任意锚点、d_min=500、seed=41、angular_nside=8、candidate_count=4、pool_size=12、1 个 worker 和 chunk_size=1024；停止条件及标签检查另使用更小网格。核验报告为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/verification.json`，耗时 5.741711 秒，报告状态为 passed。

该核验通过了 `base`、`axes`、`random`、`mask-diverse` 四种策略的 N=5 布局；compact/full 布局一致；覆盖重建与搜索覆盖一致；基于已有 N=5 结果续跑到 N=7 与 fresh 搜索结果一致，旧选择和搜索历史未变；4096 个点的选择索引与网格覆盖统计一致，并覆盖周期边界、空输入和 mask basename 解析；无合法位置、重叠阈值及 z/r 范围等价检查通过；自定义 mask 标签续跑继承通过。旧 axes CLI 和新包的覆盖及选择字段一致。显式绘图和目标文件冲突检查通过。

此核验实际产生 23 个文件，路径按报告 `files` 中的相对名展开到目录 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/`。`full/` 下的八个文件均为 full 保存结果；`compact/layout.json` 是紧凑布局；根目录的 `coverage_projection.png` 是显式绘图；两个字体缓存由绘图/HEALPix 路径触发；`legacy_axes/` 下文件来自旧 CLI 比较运行，包含其日志与投影图；核验报告记录检查结果。逐项路径为：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/cache/matplotlib/fontlist-v390.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/compact/layout.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/coverage_projection.png`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/coverage.npz`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/layout.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/library.npz`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/manifest.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/observer_distances.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/result.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/search_candidates.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/full/selections.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/cache/matplotlib/fontlist-v390.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/coverage.npz`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/coverage_projection.png`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/library.npz`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/manifest.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/observer_distances.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/pipeline.log`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/result.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/run.json`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/search_candidates.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/legacy_axes/selections.csv`
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_derived_mask/verification.json`

另一个输入文件 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/derived_mask/BGS_signature_nside32_nested.fits` 是上述派生 mask 本身，不计入这 23 个 `with_derived_mask` 核验目录文件。

### 原生 BGS mask 核验

原生 mask 输入为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits`，符号链接目标是 `/mnt/xiaodong/xiaoliang/DESImocks_old/source/BGSmask_nside8192_nested.fits`。核验使用 `boxsize=3150`、`z_range=(0.30,0.40)`、`nmesh=32`、`num_cones=5`、`strategy="axes"`、13 个朝向、observer `(1512.3,1366.7,1755.2)`、最小 observer 距离 500 Mpc/h、seed 41、`angular_nside=8`、1 个 worker。报告和输出目录为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/`。

原始报告 `verification.json` 的 status 是 `failed`，因为验证器把运行时间字段 `elapsed_sec` 纳入了科学结果相等比较；抛出的差异仅为独立运行的墙钟时间不同。报告中的产品检查仍记录 `mode_equivalence_and_rebuild=true`、N=5 到 N=7 的续跑与 fresh 结果一致，以及 32,768 个网格点、5 个窗口的点筛选检查通过。随后将独立运行结果的覆盖图及除计时字段外的选择字段进行比较，`legacy_comparison.json` 报告 `coverage_identical=true`、`all_non_timing_selection_fields_equal=true`。没有修改产品代码，也没有重跑搜索。首次失败报告保留，后续排除计时字段的比较报告也保留；因此应理解为产品结果比较通过，但原始验证报告状态仍为 failed。

`with_native_mask/` 下实际生成 23 个文件。full 模式的八个文件与前文 full 文件表一致，具体位于 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/full/`；compact 文件位于 `.../compact/layout.json`。其余文件完整路径如下：

- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/cache/matplotlib/fontlist-v390.json`：Matplotlib 字体缓存。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/compact/layout.json`：一份紧凑布局。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/cache/matplotlib/fontlist-v390.json`：legacy CLI 使用的 Matplotlib 字体缓存。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/coverage.npz`：旧 CLI 覆盖归档。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/coverage_projection.png`：旧 CLI 覆盖图。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/library.npz`：旧 CLI 候选库归档。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/manifest.json`：旧 CLI 成功运行清单。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/observer_distances.csv`：旧 CLI observer 距离。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/pipeline.log`：旧 CLI 运行日志；CLI stdout/stderr 也记录在首次验证 JSON 中。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/result.json`：旧 CLI 结果参数与指标。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/run.json`：旧 CLI 运行配置。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/search_candidates.csv`：旧 CLI 搜索候选记录。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_axes/selections.csv`：旧 CLI 选择记录。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/legacy_comparison.json`：排除非确定性 `elapsed_sec` 后的比较结果，覆盖相同且其余选择字段相等。
- `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/with_native_mask/verification.json`：首次核验报告；保留 `failed` 状态及计时差异。

最终完整性记录为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/integrity.json`，状态 PASS。它从内存基线核对 206 个原文件的 SHA256 均未改变，覆盖 tools/legacy 下五个旧脚本映射及 201 个既有运行文件，并核实四个 mask 链接按用户授权指向 `DESImocks_old` 中对应目标且目标存在。此次验证记录共 60 个文件：without_mask 目录 11 个、派生 FITS 1 个、with_derived_mask 23 个、with_native_mask 23 个、初始失败报告 1 个、integrity.json 1 个；没有新增其他核对产物。

此处的原生 mask 搜索网格是 nmesh32，不能代表已验证 nmesh512 搜索。新包尚未实际安装到环境，当前验证使用源码导入；没有实际 snapshot，也未验证真实目录读取或速度/RSD 处理。
