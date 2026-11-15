# HR4–DESI BGS 光锥与 tomographic AP 系统误差估计：交接文档

> **文档状态**：设计、任务交接与初步几何实验，尚未完成 HR4 snapshot 验证  
> **更新日期**：2026-11-12  
> **项目目录**：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/`  
> **科学方法参考**：[Tomographic Alcock-Paczynski Test with Marked Correlation Functions](https://arxiv.org/abs/2504.20478)

本文记录目前已经确定的科学目标、数据和处理约定，并区分尚待决定的实现细节。它替代原文档中将三个 snapshot 拼为完整光锥、固定生成 32 个 mock 以及宣称重叠采样严格无偏等方案。

## 1. 科学目标和最终统计量

利用 Horizon Run 4（HR4）模拟，为 DESI DR2 BGS 分别构造三个红移区间的 survey-like mock 光锥片段，以估计 tomographic Alcock–Paczynski（AP）检验中的系统误差。目标量是模拟中**不同红移区间的 2PCF 或 MCF 角向函数的红移演化**，并用于后续的系统误差扣除。

每个区间生成多个 mock，使用不同的 observer 位置及天空方向，尽可能充分利用模拟盒。不同 mock 允许空间重叠。目标是降低系统误差估计的不确定度并控制偏差，不将这些 mock 当作相互独立的宇宙实现。

已确定的统计顺序为：

1. 每个红移区间、每个 mock 分别计算普通 2PCF 和所需 MCF 对应的 DD、DR、RR。
2. 在同一红移区间内，**对 DD、DR、RR 分别进行加权平均**，再由汇总后的 pair counts 计算 2PCF 或 MCF。权重如何确定、应用于原始还是归一化 pair counts，以及与 pair-count 归一化的配合留待后续确定。
3. 对关联函数在 $s=6\text{–}40\,h^{-1}\mathrm{Mpc}$ 上计算 $\mu$ 方向函数，使用 $\mu_{\max}=0.97$，并按既定方法归一化。
4. 计算不同红移区间的角向函数差，得到系统误差向量；差值顺序须与数据分析保持一致。

不得改成先分别计算每个 mock 的 2PCF/MCF 再对关联函数平均。MCF 的 density mark 是星系或 halo 的权重；不同 mock 的汇总权重是另一层含义，两者不可混淆。

## 2. 宇宙学、模拟盒与三个红移区间

- 统一使用 HR4 自身的 WMAP5 宇宙学：$\Omega_m=0.26$、$\Omega_\Lambda=0.74$、$h=0.72$、$\sigma_8=0.794$，平直 $\Lambda$CDM。
- 周期性模拟盒边长 $L=3150\,h^{-1}\mathrm{Mpc}$，体积 $L^3\simeq31.256\,(h^{-1}\mathrm{Gpc})^3$。
- 以下三个 snapshot 分别代表对应的观测红移区间；三个区间独立构造和分析，**不需要拼接成跨红移的完整光锥**。

| 观测红移范围 | 对应 HR4 snapshot 红移 | 共动距离范围（约） | 几何体积（约） |
|---|---:|---:|---:|
| $0.025\text{–}0.150$ | 0.114175 | $74.58\text{–}436.06\,h^{-1}\mathrm{Mpc}$ | $0.126\,(h^{-1}\mathrm{Gpc})^3$ |
| $0.150\text{–}0.300$ | 0.230957 | $436.06\text{–}843.49\,h^{-1}\mathrm{Mpc}$ | $0.788\,(h^{-1}\mathrm{Gpc})^3$ |
| $0.300\text{–}0.400$ | 0.347565 | $843.49\text{–}1098.73\,h^{-1}\mathrm{Mpc}$ | $1.106\,(h^{-1}\mathrm{Gpc})^3$ |

距离采用上述 HR4 平直 $\Lambda$CDM 参数计算。体积是将天区暂按 $15000\,\mathrm{deg}^2$ 二值 footprint 估算的几何值，未应用实际 mask 的细节、completeness 或径向选择函数；实际面积与有效选择须以输入数据和分析约定为准。

**snapshot 红移仅用于最初确定它代表哪个观测红移区间。** 随后选择光锥时，以该区间的观测红移范围、observer 位置和天区选择确定光锥；不再用 snapshot 红移筛选对象或调整光锥的径向范围。单个 snapshot 代表整个区间是一项建模近似。

## 3. Mask 和 completeness

使用现有 BGS version 1 mask 进行当前工作；它与后续正式使用的版本接近。目录中与 BGS 直接相关的文件为：

| 输入路径 | 已确认内容 | 当前状态和用途 |
|---|---|---|
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits` | HEALPix，NSIDE 8192，NESTED，约 1.6 GB；FITS 字段名为 `T` | 已存在，为指向 `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` 的符号链接；用于 BGS 角向 footprint |
| `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGS_BRIGHT_mean_comp_nside128_nested.fits` | HEALPix，NSIDE 128，NESTED；FITS 字段名为 `T` | 已存在，为指向 `/mnt/xiaodong/xiaoliang/DESImocks/source/BGS_BRIGHT_mean_comp_nside128_nested.fits` 的符号链接；提供 completeness 信息 |

当前几何实验仅使用 BGS mask，不使用 completeness。已从现有 DESImocks 代码确认 BGS mask 的有效像素值为 4，按赤道坐标 RA/DEC 查询；直接统计的天区面积为 $12562.35062330\,\mathrm{deg}^2$。第 2 节的体积表仍为按 $15000\,\mathrm{deg}^2$ 给出的设计阶段估算，实验的解析体积使用实际 mask 面积。

两个文件分辨率不同。后续若使用 completeness，查询时需分别使用各自的 NSIDE；completeness 文件包含 HEALPix 风格的无效值，具体应用规则仍待与数据分析对齐。

单个 mock 的南北天使用同一个 observer 和同一个天空方向变换，以保持同一观测者下的巡天几何。具体南北天划分应按实际输入 mask 和数据分析约定执行。

## 4. 光锥几何、周期边界和速度

### 4.1 无需为当前几何进行 box remap

按 HR4 宇宙学，最大观测红移 $z=0.4$ 对应的距离约为 $R_{\max}=1098.73\,h^{-1}\mathrm{Mpc}$，满足

$$
2R_{\max}\simeq2197.45 < L=3150
\quad (h^{-1}\mathrm{Mpc}).
$$

因此，以任意 observer 为球心、半径不超过该值的实空间球体，在周期盒中不会同时包含同一对象的两个周期镜像。可直接使用原始立方周期盒和最小像约定，无需为了容纳当前几何而做 box remap。

对于盒内位置 $\mathbf{x}$ 与 observer $\mathbf{O}$，可采用

$$
\mathbf{r}
=\left[(\mathbf{x}-\mathbf{O}+L/2)\bmod L\right]-L/2.
$$

不同 mock 的窗口仍然可以覆盖盒中的同一结构；单个 mock 无周期镜像重复并不意味着多个 mock 互相独立。

### 4.2 真实空间、红移空间和窗口选择

输入模拟包含真实空间三维位置与三维速度。构造红移空间 mock 时，使用相对 observer 的视线方向计算特殊速度投影；若在旋转后的坐标系内计算投影，位置与速度应施加同一旋转。也可以在模拟坐标系先计算 $\mathbf v\cdot\hat{\mathbf r}$，再旋转位置；关键是点积两端使用相同坐标系。

在常见的一阶近似及一致的单位约定下，沿视线的红移空间位移可表示为

$$
s_{\parallel}\simeq r+\frac{v_{\rm los}}{aH}.
$$

观测红移范围用于最终选样。若实现先在真实空间预选候选对象再计算 RSD，应在边界外留出足够候选范围，避免遗漏因视向速度进入观测红移区间的对象；余量和速度单位须依据实际数据确定。snapshot 红移不作为光锥范围或对象筛选条件。RSD 的具体速度约定和 $aH$ 的实现细节尚待与输入数据及现有分析对齐。

先按原周期晶格计算最小像位移，再将相对方向变换至天空坐标；任意旋转后的周期晶格不能直接当作仍沿原坐标轴的立方晶格取模。

## 5. MCF 与边界约定

MCF 使用论文中的局域数密度 mark 方案：以局域密度的幂定义 mark，密度由近邻和核函数估计。论文使用第 30 近邻确定核尺度；具体 mark 参数及数据处理配置按本项目实际分析设置。

对于光锥转到 box 坐标、使用 KDTree 计算局域密度时的边界问题，研究者已与博导讨论并确定：**数据和 mock 采用相同方式，当前不对该边界效应额外修正。** 实现和比较时应保证双方的处理一致。mask/completeness、选样及局域密度计算的具体衔接顺序仍需与现有数据分析对齐。

## 6. `LSS_python.xismu` 的分析配置

当前环境可通过 zsh 加载的 conda 环境引入 `LSS_python.xismu`。已检查的模块路径为：

`/mnt/xiaodong/xiaoliang/software/LSS_python/src/LSS_python/xismu.py`

- 使用 `get_diff_array` 计算两个红移区间角向函数之差，输出顺序由 `snap_ids` 决定。
- 当前沿用 $s_{\min}=6$、$s_{\max}=40\,h^{-1}\mathrm{Mpc}$ 和 `mumax=0.97`。
- 保留 `norm_method="regu"`，当前代码默认 `eta=0.2`。该方法用于处理特定 MCF 在某些 $w_0w_a$ 参数点附近角向平均值接近零的问题；研究者已验证其在其他情形下对参数限制的影响很小。
- **采用 `intximu_new=False`**，这也是论文分析实际采用的路径。`intximu_new=True` 是以前其他测试使用的路径，本任务不使用。
- `intximu_new=False` 且 `mupack>1` 时，先在 $\mu$ 方向合并 DD、DR、RR，再计算关联函数、对 $s$ 求平均、进行角向归一化，并按配置删除最后一个粗 $\mu$ bin。具体 `mupack`、`remove_last_one`、差值顺序及数据与 mock 所用配置须保持一致。

`intximu_new=True` 的另一条路径先计算细 $\mu$ bin 的关联函数和角度曲线，再归一化、删除最后一个细 bin 并打包；其数值和向量长度可能不同。两者不能仅凭参数名称互换。上述 $\mu$ bin 打包也不同于第 1 节中**跨 mock 分别加权平均 DD、DR、RR**的操作。

## 7. Observer placement 与重叠

每个红移区间可以分别设计一组 observer 位置和天空方向，不要求三个 snapshot 使用相同配置。允许不同 mock 体积重叠；不因重叠本身自动对星系或 pair 施加反重叠次数权重。

placement 的具体数量、位置、旋转、mock 汇总权重及优化算法尚未定型。体积覆盖、覆盖次数分布、pair coverage 和天空方向覆盖可用作候选方案的诊断；最终应比较不同配置和 mock 数量下 **2PCF/MCF 角向演化及系统误差向量的稳定性**。几何覆盖均匀并不自动保证系统误差无偏或方差最小。

同一 box 的 mock 共享结构和大尺度模式；空间重叠、有效样本数及最终统计量的相关性不能仅由 observer 个数推断。不存在已验证的固定 32 个 mock、$N_{\rm eff}=15\text{–}20$ 或指定误差下降比例。

## 8. 后续工作与当前数据状态

1. 后续确认 completeness 的应用方式，以及与数据一致的径向选择和 random catalog；当前几何实验只使用已确认的 mask 天区。
2. 确定输入 catalog 的字段、位置和速度单位、RSD 与局域密度计算的具体约定，以及 MCF mark 参数。
3. 设计并比较 observer placement；在各红移区间分别生成候选 mock，用覆盖指标及最终系统误差向量检验稳定性。
4. 确定 DD、DR、RR 跨 mock 加权平均的权重及其归一化规则，接入现有 `xismu` 分析流程。
5. HR4 snapshot 数据目前不在此服务器；可先用其他 simulation box 验证程序和流程。其他模拟的结果仅用于可行性验证，不作为 HR4 最终系统误差结果。

当前未确认本项目已有 HR4 光锥、pair-count 文件或系统误差输出；任何未来脚本的输入、输出、中间文件及运行方式应在脚本实现时单独记录。

## 9. 已建立的直接网格朝向实验

入口为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/orientation_pipeline.py`，
几何实现在同目录的 `orientation_geometry.py`。它接受盒长、原始 HEALPix mask、网格数、
observer 序列和观测红移/距离范围，比较轴向扫描、随机三维旋转及 mask 重叠筛选的候选库，
并可在候选朝向附近执行小角度调整。位置由用户指定，本轮不采用 FFT 或位置搜索。

已使用原始 BGS mask，在低红移区间、32/64 两种网格和三个 observer 上跑通初步案例。
代码用途、处理顺序、参数、依赖、运行命令、指标定义及输入/中间/最终输出完整清单见
[朝向实验说明](experiments/direct_grid.md)。
实际结果保存在 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/bgs_orientation_smoke_20261112/`，
该目录的 `manifest.json` 列出本次实际生成的文件。
