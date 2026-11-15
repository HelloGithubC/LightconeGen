> **模型 / Model**: Gemini  
> **日期 / Date**: 2026-11-13  

# `src/` 模块化更新摘要与协作 ToDo

本文档记录 `ForHR4/src/` 目录下 BGS mask 朝向探索脚本的模块化拆分结果与后续待办事项，便于在探索与开发阶段跨模型/跨会话接力协作。

## 当前约定与进展（2026-11-13，后续讨论）

- `orientation_pipeline.py` 有意冻结保留；本轮仅调整 `eval_strategy.py` 和 `compare_results.py`。
- 不以计算成本相同作为比较要求；初步案例将三种策略设为各 13 个候选。当前只运行了一个 seed，尚不能视为完整稳定性实验。
- 随机候选池不要求统一：`random` 和 `mask-diverse` 继续使用原有的独立候选池。
- 现阶段保留多种几何指标用于探索，仍按 `mean_prior_coverage` 选择，不将其他指标设为已确认目标函数。
- 每个比较组使用一个目录，组内每次实验位于单独子目录；汇总脚本展示各结果的完整参数。比较组本身不要求所有参数一致，具体差异由使用者根据实验目标判断。
- 小规模网格对照已运行 `32^3` 与 `64^3` 并保存每个候选旋转矩阵；更高网格和独立精查尚未执行。
- 比较组目录：
  `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113`。
  运行方法、实际输入及输出清单见
  `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/doc/experiments/direct_grid.md` 的“单策略实验与比较组”。

---

## 一、本次更新摘要（2026-11-13）

为解决原一体化脚本 [orientation_pipeline.py](../tools/legacy/orientation_pipeline.py) 多层嵌套（`shell × nmesh × strategy × observer`）导致单次验证冗杂的问题，在保留原有文件不变的前提下，新增了两个轻量化分块脚本：

### 当前 `src/` 文件结构

| 文件 | 状态 | 职责说明 |
|---|---|---|
| `orientation_geometry.py` | 未修改（复用） | 底层几何与 mask 原语：`SkyMask`（memmap 查询原始 FITS）、`comoving_distance`、旋转库生成 `make_library`、周期性球壳提取 `shell_geometry`、窗口打分 `evaluate_window` 等。 |
| `orientation_pipeline.py` | 未修改（保留） | 原全量对比流水线：一次跑多 shell / 多网格 / 多策略，附带全候选 `overlap.npz`、`windows.npz`（可选）、PNG 绘图及 `manifest.json`。 |
| `eval_strategy.py` | **新增** | **单一策略快速测试脚本**：每次只测 1 种策略（`axes` / `random` / `mask-diverse`）、1 个 `nmesh`、1 个径向区间（`--z-range` 或 `--r-range`）。去掉多轮大循环、两两交集矩阵和绘图依赖；默认终端打印逐 observer 摘要并写出轻量 `result.json` 与 `selections.csv`（可选 `--save-candidates`、`--save-coverage`）。 |
| `compare_results.py` | **新增** | **多结果纯汇总对比脚本**：不重算几何，递归扫描指定目录下的 `result.json`（含配置、指标与选择记录），按指定指标排行打印对比表，支持 `--sort-by`、`--show-observers` 和 `--output-csv`。 |

### 关键实现细节（供协作 LLM 对齐约定）

1. **可复现性对齐**：`eval_strategy.py` 使用与 `orientation_pipeline.py` 相同的 `SeedSequence([args.seed, ["axes", "random", "mask-diverse"].index(args.strategy)])`，同一参数下候选库完全一致。
2. **选优准则**：各 observer 按输入顺序贪心选择使 `mean_prior_coverage`（当前候选占用体素内的已有平均覆盖次数）最小的旋转，并列时按候选顺序稳定选取；可选 `--refine-steps` 在 6 邻域（盒子 `±x/±y/±z` 轴）做严格改善的局部微调。
3. **JSON 严格序列化**：`eval_strategy.py` 通过 `json_safe()` 将 `nan`/`inf`（如 `base`/`random` 候选的 `axis_angle_deg`）转为 JSON `null`，保持 `allow_nan=False`。
4. **运行环境与无参数约定**：
   - Python：`/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B`
   - 两个新增脚本均设置 `sys.dont_write_bytecode = True`，且无参数运行均打印 help 并以退出码 `0` 退出。

### 已完成的验证基线

在 `tests/runs/modular_smoke_20261113/` 下使用 `nmesh=32`、2 个 observer、`--z-range 0.025 0.15`、`--refine-steps 3 1 --refine-rounds 1 --seed 20261112` 验证了三种策略与汇总脚本：
- `axes` / `random` / `mask_diverse` 单次运行耗时均约 **3.0s**（其中大部分时间用于全图扫描计算 `mask.area()`，每个 observer 几何计算约 0.03s）。
- `modular_smoke_20261113/axes/selections.csv` 与旧流水线基线 `tests/runs/cli_positional_check_20261113/shell_00/nmesh_0032/axes/selections.csv` 数值逐项一致。
- `compare_results.py` 已验证 `--sort-by avg_prior`、`--show-observers` 与 `--output-csv`（生成 `comparison.csv`）。

---

## 二、ToDo（后续探索与开发待办）

### A. 探索阶段对比实验（短期）
- [ ] **三类策略对比**：可先对齐候选数，例如 `axes` 采用 4 个扫描角度和基准朝向，其余策略设置 `--candidate-count 13`；进一步检查不同 seed 和 observer 配置下的表现。
- [ ] **多 observer 与边界测试**：增加更多 observer（含靠近周期边界的 observer），覆盖 3 个典型红移壳层（`0.025-0.15`、`0.15-0.30`、`0.30-0.40`），并用 `compare_results.py` 汇总结果。
- [ ] **超参数敏感性检查**：测试不同 `--nmesh`（如 `32` vs `64` vs `128`）、`--angular-nside`（`16` / `32` / `64`）、`--pool-size` 及 `--refine-steps` 对选优结果和离散体积误差 `volume_relative_error` 的影响。

### B. 脚本体验与性能优化（中期）
- [ ] **跳过或缓存 `mask.area()` 扫描**：当前每次启动 `eval_strategy.py` 都会扫一遍 `NSIDE=8192`（$12 \times 8192^2$ 像素）的 FITS 计算解析面积（约占 ~3s 总耗时的大头）；若只是快速试参数，可考虑增加 `--skip-area` 或基于 mask 路径+mtime+values 的轻量缓存（需注意避免隐式全局状态污染）。
- [ ] **从文件批量传入 observer**：为 `eval_strategy.py` 增加可选 `--observers-file`（支持多行 `X Y Z` 文本/CSV），方便测试几十个 observer 时不再手工拼接长命令行。
- [ ] **批处理 runner / 矩阵扫描辅助**：如需一次批量提交多组 `(strategy, seed, nmesh)` 独立调用 `eval_strategy.py`，可写一个极简 shell/Python 启动器，再用 `compare_results.py` 统一收口。
- [ ] **兼容读取旧目录（可选）**：若需要把早期 `orientation_pipeline.py` 的产出纳入对比，可扩展 `compare_results.py` 兼容解析 `run.json` + `selections.csv`。

### C. 物理接入与下游验证（长期 / 确定方案后）
- [ ] **确认最终目标函数**：评估当前 `mean_prior_coverage`（一阶平均重叠）与最小化覆盖平方和增量（`coverage_square_increment`）或惩罚高多重覆盖区域（`coverage >= 2`）之间的差异；候选窗口的离散体素数相同时，比较平方和才与比较覆盖方差直接等价。
- [ ] **导出供 HR4 Lightcone 使用的朝向配置**：基于 `result.json` 中的 `selections[*].matrix_sky_to_box` / `quaternion_xyzw` 对接实际 snapshot 粒子/星系光锥生成脚本。
- [ ] **物理级验证**：在真实 HR4 snapshot 上验证几何低重叠朝向是否改善多 observer 间相关性以及 AP 系统误差估计的不确定度（并纳入径向数密度 $n(z)$、completeness 与 RSD 影响）。

---

> **模型 / Model**: Gemini  
> **日期 / Date**: 2026-11-13  

---

> **模型 / Model**: GPT 
> **日期 / Date**: 2026-11-15  

# GPT补充：最新讨论与 FFT 衔接

本节交接近期讨论的理解与方案。本轮只更新本文档，未修改脚本、运行新实验或生成新结果；共享候选池、FFT 位置搜索和自动放置均尚未实现。

### 1. `random`、`mask-diverse` 与共享候选池

两种策略的区别发生在候选库构建阶段，后续都在 observer 位置逐一评估候选，并按 `mean_prior_coverage` 选择最终朝向：

- `random`：保留 `base`，其余候选直接随机生成；最终选中的朝向仍由网格重叠得分确定。
- `mask-diverse`：先生成包含 `base` 的较大随机池，再根据旋转后 mask 的角向 IoU 筛选候选。以 `base` 开始，每轮选择与已选集合的最大 IoU 最小的朝向，直到达到候选数。
- mask 的角向差异用于构建候选库，并不保证不同 observer 位置下的三维光锥重叠最小。

**当前实现并未共享池。** `eval_strategy.py` 使用 `SeedSequence([seed, strategy_idx])`，其中 `random` 和 `mask-diverse` 的策略编号不同；`make_library` 又分别生成 `candidate_count` 和 `pool_size` 个朝向。因此，仅在命令中设置相同 `--seed`，不能视为共享池。已有比较结果仍应按独立池实验理解。

**已讨论的最小改法（尚未实施）**：两个策略都以相同的种子、`base-euler`、`pool-size` 和生成规则，先生成同一份有序随机池；池大小与最终候选数均包含 `base`。例如，先生成 64 个朝向：

1. `random` 保留池中前 13 个，其中第一个为 `base`。
2. `mask-diverse` 从同一池中按现有 mask 差异规则筛选 13 个，并保留 `base`。
3. 两次运行仍可分别执行：每次重新生成相同的有序候选池即可，不要求同时运行、共享内存或新增候选池文件。

对应代码调整点是候选池种子不再依赖策略编号，以及两个分支先统一生成 `pool_size` 个候选再分别取用。是否采用这一方案及如何兼容旧实验，留待后续实现时确定；本轮没有变更原有随机行为。

### 2. 当前工作链与停止条件

目前每次 `eval_strategy.py` 运行只处理一种策略、一个径向壳层和一种网格。observer 坐标及顺序由输入指定，候选库在循环前生成一次，工作链如下：

1. 初始化累计覆盖次数图 `C=0`。
2. 在第一个 observer 位置评估候选。有效候选的已有覆盖得分均为零，稳定并列规则使排在第一位的 `base` 被选中，然后把该窗口加入 `C`。
3. 在下一个 observer 位置，用同一候选库评估相对于当前 `C` 的得分，选择一个朝向；如指定了局部微调，则在加入 `C` 前执行微调。
4. 将选中窗口加入 `C`，继续下一个 observer，直到输入列表处理完毕。

总光锥数等于 `1 + --observer 的出现次数`：位置参数 `X Y Z` 给出第一个位置，每个追加的 `--observer X Y Z` 再提供一个位置。`candidate-count` 是每个位置用于评估的候选朝向数，每个 observer 最终只保留一个光锥。

最近的比较组 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/comparison_group_20261113/` 中，六次运行均使用两个 observer：`(1575,1575,1575)` 和 `(1715.5,1530.2,1600.1)`，每种策略各有 13 个候选，未启用局部微调。因此，每次运行放置两个几何窗口，主要检验第一个窗口取 `base` 后第二个窗口的朝向选择。

当前没有自动搜索 observer 位置、自动决定光锥数量、按重叠阈值提前结束或回头调整已选窗口的步骤。这里的光锥仍指网格几何窗口，尚未提取实际天体目录。

### 3. FFT 与朝向候选库的联合搜索

固定当前累计覆盖图 `C` 后，对每个候选朝向 `R`，根据实际 BGS mask 与径向范围构建周期网格模板 `W_R`。模板为二值占据图，`C` 则保留累计覆盖次数，不转成二值并集。

周期互相关给出该朝向下所有离散 observer 平移位置的累计重叠得分：

\[
G_R(O)=\sum_x C(x)W_R(x-O)
=\mathcal{F}^{-1}\!\left[\mathcal{F}(C)\,\overline{\mathcal{F}(W_R)}\right](O).
\]

若沿用当前选择指标，则使用

\[
H_R(O)=\frac{G_R(O)}{\sum_x W_R(x)}.
\]

这与当前 `mean_prior_coverage` 对应；归一化也保留了不同朝向在离散网格上占据格数可能略有差异的处理。

每个候选朝向得到一张三维得分图；所有图合起来，提供给定朝向库与平移网格上的位置、朝向联合得分。可以先找每张图的最低点，再比较各图最低点，等价于

\[
(O_*,R_*)=\arg\min_{O,R}H_R(O).
\]

选定后更新 \(C(x)\leftarrow C(x)+W_{R_*}(x-O_*)\)，再针对更新后的 `C` 计算下一轮得分。FFT 输出本身是候选位置的得分图，不是加入新光锥后的覆盖图。

首个窗口仍需指定一个起点与朝向，因为 `C=0` 时所有有效组合得分相同。后续可由 FFT 搜索位置、由候选库提供朝向，并联合选择每轮新增窗口。

### 4. 分层精化的作用与待明确边界

- **联合搜索不依赖额外分层**：逐朝向计算全位置得分图，已能完成给定离散候选范围内的联合搜索。
- **分层精化是后续可选方案**：先用粗网格与候选朝向库找出少量较好的位置、朝向组合，再围绕这些组合细化位置和角度；细化参数尚未确定。
- **平移网格约定待落实**：FFT 的周期平移对应整数格移动。当前脚本允许任意 observer 坐标，任意坐标相对网格的偏移不能直接当成同一个模板的整数格平移；后续实现须明确模板锚点和 observer 搜索格点的对应关系。
- **得分的范围**：上述结果是新窗口相对于当前 `C` 的累计重叠标量；多个已有窗口覆盖同一格时会按次数计入。它不是逐一保存的两两重叠图，也不等于与已有覆盖并集的交集体积。
- **优化的范围**：每轮只选择一个新窗口，是逐步贪心搜索；有限朝向库与网格上的最优不代表连续位置、连续朝向或最终整组窗口的全局最优。
- **停止条件待后续确定**：现有程序按输入 observer 数停止；未来自动放置时的数量或停止规则尚未讨论确定。

---

> **模型 / Model**: GPT 
> **日期 / Date**: 2026-11-15  

---

> **模型 / Model**: Gemini  
> **日期 / Date**: 2026-11-15  

# Gemini 补充：FFT 放置的最小间距、数值去噪与平局处理

本节在上面 GPT 讨论（[ToDo.md](#gpt补充最新讨论与-fft-衔接)）的基础上，补充后续实现 FFT 联合搜索时必须考虑的约束权衡与数值/平局处理规则；本轮仅更新文档，未修改脚本。

### 1. 最小周期间距约束（$d_{\min}$）的定位与权衡

- **支持加入物理单位 $d_{\min}$ 屏蔽**：BGS mask 仅占全天约 30%（$12562.35\,\mathrm{deg}^2$），若不限制观测者间距，两个相距很近甚至重合的观测者仅靠旋转 90°–180° 即可使体素重叠接近零，导致观测者扎堆并共享紧邻边界的大尺度密度涨落。因此支持在 FFT 得分图上对所有已放置观测者施加周期距离约束 $d_{\text{periodic}}(O, O_i) \ge d_{\min}$（以 $\mathrm{Mpc}/h$ 定义并映射到当前搜索网格，屏蔽区域设为 $+\infty$）。
- **并非越大越好**：$d_{\min}$ 应视为“防贴脸/防扎堆”的下限门槛，而不是越大越好。在低红移小壳层（如 $r \in [74.58, 436.06)\,\mathrm{Mpc}/h$）盒子很空，较大 $d_{\min}$ 容易满足；但在高红移大壳层且目标光锥数较多时，过大的 $d_{\min}$ 会显著压缩可用空间或迫使大球壳迎面相交，反而限制了靠旋转 30% mask 错开视线的自由度。具体 $d_{\min}$ 需结合目标红移段与光锥数量通过实验确定，并将“无满足 $d_{\min}$ 的剩余格点”纳入自动放置停止条件。

### 2. FFT 交集的整数还原（消除浮点舍入误差）

- 累计覆盖图 $C(x)$ 为非负整数、朝向模板 $W_R(x)$ 为 $0/1$ 二值数组，因此周期互相关交集和 $G_R(O)=\sum_x C(x)W_R(x-O)$ 在数学上必为**非负整数**。
- `float64` 精度的 `rfftn`/`irfftn` 会在真实值为 `0` 的海量无重叠格点上留下 $\sim 10^{-15}\text{–}10^{-12}$ 量级的舍入噪音。若直接对浮点得分取 `argmin`，程序实际上会按随机的负舍入误差挑中某一个格点。
- **实现约定**：计算 `irfftn` 后应先还原整数并截断数值误差，例如 `G_int = np.maximum(0, np.rint(G_raw)).astype(np.int64)`（可顺带检查 `np.max(np.abs(G_raw - G_int))` 是否远小于 `1e-3` 作为数值健壮性断言），再计算 $H_R(O) = G_{\text{int}}(O) / \sum_x W_R(x)$。

### 3. 零重叠 / 并列最低分时的平局打破规则（Tie-breaking）

- 在低红移小壳层（如 $z \in [0.025, 0.15]$ 单个光锥仅占 $3150^3$ 盒子的约 `0.336%`）放置前几个光锥时，即便扣除 $d_{\min}$ 禁放区，盒内仍存在大片精确为 $G_{\text{int}} = 0$ 的合法位置。
- **实现约定**：当多个合法候选 $(O, R)$ 并列达到最小得分 $H_{\min}$ 时，建议增加两级确定性平局规则，避免贴着禁放圈边界或按数组扫描顺序随意落点：
  1. **位置优先分散（Maximin）**：在所有达到 $H_{\min}$ 的候选格点中，优先选择离所有已放置观测者最近周期距离最大的位置，即最大化 $\min_{i} d_{\text{periodic}}(O, O_i)$（使得前几个观测者自然均匀铺开）。
  2. **朝向顺序稳定**：在同一最优点仍有多个朝向并列时，按候选库顺序稳定选择排在前面的朝向（例如重叠同为 0 时优先保留 `base`）。

### 4. 对应实现待办（衔接 FFT 阶段）

- [ ] **FFT 得分整数化校验**：在未来的 FFT 搜索实现中对 `irfftn` 输出执行整数四舍五入与最大残差检查，杜绝浮点噪音决定 `argmin`。
- [ ] **周期最小间距 + Maximin 平局规则**：实现按 $\mathrm{Mpc}/h$ 计算的周期距离屏蔽（$d_{\text{periodic}} < d_{\min}$ 置 $+\infty$），并在最低分并列时启用 Maximin 距离打破平局。
- [ ] **停止条件联动**：明确“无合法位置（全图均被 $d_{\min}$ 屏蔽）”、“达到目标光锥数”或“最低重叠分超过阈值”的停止优先级。

---

> **模型 / Model**: Gemini  
> **日期 / Date**: 2026-11-15  

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15  

# GPT 实现进展：FFT 联合放置入口

- 已新增 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/eval_fft.py`；旧 pipeline、直接计算入口及几何模块未修改。
- 已实现周期 FFT 位置/朝向联合搜索、非负整数计数还原与残差记录、物理最小 observer 间距、最近距离 maximin 平局规则。最终位置仍并列时按 C 顺序索引选择，同点朝向按库顺序选择。
- 以输入首个 observer 为模板锚点：FFT 整数位移 `k` 对应 `(O0+k*L/nmesh) modulo L`，无需舍入输入坐标。
- 停止规则为：达到目标总数即完成；否则若没有合法格点则停止；搜索后的最低平均已有覆盖超过可选阈值时不接受该窗口并停止。阈值默认不启用，目标数量包含首个固定窗口。
- 新 FFT 入口的 random/mask-diverse 已使用共享初始池；旧直接计算入口保留原来的独立池行为。
- 已完成无参数 help/退出码 0 核对，以及内存中 7/8 网格全部平移的直接计数、稀疏移位、周期距离和平局顺序核对。没有新建测试套件或安装依赖。
- 用户已确认 axes 与 z3（0.30–0.40）。已实际完成 3150 Mpc/h、BGS mask、512^3、N=5、d_min=500 Mpc/h 的运行，候选为 base 加三轴各 30/60/90/120 度，共 13 个。正常达到目标数量。
- 结果目录：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115`。选中朝向依次为 base、base、y_60、y_60、y_60；前四个窗口无体素交集，最后一个与 observer 1 的窗口有 4 个交集体素。非重复覆盖占盒子 14.8212634%，最小 observer 周期间距 770.3461615 Mpc/h。
- 正式运行耗时 380.925 秒、峰值 RSS 20.6669 GiB；最大 FFT 整数还原残差 1.8626451492e-9。已逐窗口按实际 observer 坐标重新查询原始 mask、重建覆盖并计数全部 10 对交集，核对通过；保存 verification.json 和 pairwise_overlaps.csv，未新建核对脚本或测试套件。
- compare_results.py 已实际读取本次结果并生成 comparison.csv；仅将终端的平均已有覆盖显示改为有效数字，避免微小非零值被显示成零。正式结果目录含日志、字体缓存、三个后处理文件共 14 个文件；manifest.json 已更新完整清单。
- 实现流程、全部参数、依赖与输入/输出/内存中间量清单见 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/doc/experiments/fft_placement.md`。

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15  

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15  

# GPT 补充：零重叠选优与 N=5 到 N=15 续跑

- 零重叠时，先最大化最近 observer 的周期距离，再以网格位置索引和朝向库顺序确定平局结果。N=5 基线的第三个窗口选择 y_60，是因为其零重叠位置可达到最近间距 1700.33 Mpc/h，而 base 只能达到 1640.38 Mpc/h；并非零重叠就自动选 base。
- 已为 eval_fft.py 增加 `--resume-from` 形式：从已完成运行继承参数、朝向库、累计覆盖、已有窗口和搜索历史，重建最近距离图及内存频谱，只优化新增窗口；新结果写入新目录。
- 用户已指定续跑到总数 N=15，即从原 N=5 新增 10 个，沿用全部几何条件和 d_min=500 Mpc/h。
- 来源目录：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N5_20261115`。续跑前后已核对其全部 14 个文件 SHA256 不变；前五个完整选择记录、原 52 条候选历史及候选库数组均原样保留。
- 新输出目录：`/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/fft_axes_z3_n512_N15_fromN5_20261115`。已正常达到 N=15；覆盖盒子 42.1322189%，最小 observer 周期间距 500.0459078 Mpc/h，最大覆盖次数 3。最后一个窗口平均已有覆盖 0.2050226896，全部窗口该指标平均为 0.0528371692。
- 本次续跑耗时 625.949 秒、峰值 RSS 20.7994 GiB；与来源运行累计 1006.874 秒。原覆盖加 10 个新增原生 mask 模板（独立 numpy.roll 平移）的重建结果与保存覆盖完全一致；105 对交集与周期距离、旋转矩阵和最低分单调性核对通过。新目录含日志、缓存及三个后处理产物共 14 个文件，manifest 已更新；未新建测试套件。
- 续跑工作流程、参数、实际命令及完整文件清单见 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/doc/experiments/fft_resume.md`。

## 当前完成情况汇总与使用入口

以下是截至 2026-11-15 的实现状态；前文各模型的讨论和待办保留为历史记录，是否已经完成以本节和上述实际运行记录为准。

- [x] **基础几何与直接计算**：原生 BGS mask 查询、HR4 距离换算、周期球壳占据、axes/random/mask-diverse 候选、固定 observer 的朝向比较及可选局部角度微调均已有实现。`orientation_pipeline.py` 按约定冻结保留；`eval_strategy.py` 为单策略直接计算入口。
- [x] **FFT 联合搜索**：`eval_fft.py` 搜索候选朝向和全部整数格平移，含整数计数还原、最小周期间距、零重叠时的确定性平局规则和三类停止条件。这里 `base` 表示单一固定朝向，实际基线采用的是 `axes`，两者应区分。
- [x] **共享随机池**：新 FFT 入口的 random/mask-diverse 在相同 seed、base 和 pool-size 下共享初始候选池；旧直接计算入口仍保留独立池行为。共享池实现不等于已完成正式策略比较。
- [x] **结果续跑**：已完成目录可作为 `--resume-from` 来源，保留原窗口及搜索历史，只搜索新增窗口；输出写入新目录。当前支持的是完成结果续跑，不是中途检查点恢复。
- [x] **正式几何基线与核对**：3150 Mpc/h、BGS z3、512^3、axes 13 朝向、d_min=500 Mpc/h 的 N=5 及续跑至 N=15 均已完成，原 N=5 结果保持不变；N=15 非重复覆盖为 42.1322189%，具体核对方式见本块前述记录。
- [x] **汇总与使用文档**：`compare_results.py` 可按比较组目录读取直接计算/FFT 的 `result.json`，显示参数并导出汇总；已新增 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/Readme.md`，说明各入口、流程、依赖、参数、运行方式及输入/中间/最终输出。

尚未完成正式 512^3 的 random/mask-diverse 对比、其他壳层或网格收敛研究；completeness、真实 snapshot/速度/RSD 及后续相关函数/AP 分析不属于当前几何实现。保留原待办，本轮不扩展这些工作。

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15  

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15  

# GPT 实现进展：可导入模块与两种保存模式

- [x] 新包位于 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/src/lightconegen/`，公开搜索、结果读写、续跑、覆盖重建及数据点行索引筛选接口。搜索过程不自动写文件或绘图，保存和绘图由调用者显式执行。
- [x] 五个旧 Python 文件已从 `src/` 原样移至 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tools/legacy/`，独立命令行入口、默认值和格式保留。新包不调用这些旧脚本。
- [x] `layout` 模式只保存 `layout.json`；内容为盒长、红移范围或距离范围、HR4 宇宙学、mask 文件名、网格数及各窗口的 observer、三个外禀 xyz 欧拉角（度）、整数网格 shift。首个 observer 为模板锚点；不保存旋转矩阵、RA/DEC、哈希或格式/来源版本。
- [x] `full` 模式另保存覆盖、候选库、选择与搜索记录、observer 距离及参数指标，可从完成结果继续搜索。两种模式使用同一优化过程，精简模式减少保留和传输内容，搜索时仍需 FFT 内存。
- [x] `rebuild_coverage` 用精简布局、原 mask、锚点模板及整数平移重建网格覆盖；`select_points` 接收调用者提供的 xyz 位置数组，返回指定窗口内的行索引。均采用 HR4、Mpc/h 和周期边界；不假定星系文件格式或速度列。
- [x] 按用户确认，将 `mask/` 四个失效链接的目标从 `DESImocks/source/` 改为 `DESImocks_old/source/`，四份 FITS 表头均可读，数据内容未修改。
- [x] 已完成数组 FFT/距离/平局核对、旧 N=5 完整存档读写、旧 N=15 精简布局导出、四个旧 CLI 无参数帮助及旧比较器兼容核对。另以派生 NSIDE32 mask 验证四种策略、两种模式、重建、点筛选、续跑、停止规则及自定义标签继承。
- [x] 原生 NSIDE8192 BGS mask 的 `3150 Mpc/h、z3、32^3、axes、N=5、d_min=500 Mpc/h` 核对已完成：两种模式布局一致，重建与覆盖一致，32768 个网格中心的点筛选一致，续跑至 N=7 与重新搜索 N=7 一致，旧 FFT 工具与新包的覆盖完全相同、全部非计时选择字段相等。
- [x] 206 个原文件校验值保持不变（五个旧脚本、201 个原运行文件）。本轮实际生成 60 个核对文件，均位于 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/module_refactor_20261115/`，继续被 Git 忽略；没有新增测试脚本或测试套件。
- [x] 首页、`src/Readme.md`、`tools/README.md` 和 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/doc/MODULE.md` 已更新。完整处理流程、参数、依赖、安装/调用方式和输入/中间/最终输出、日志、缓存清单见模块说明。

本轮尚未执行包安装或构建，没有重跑 512^3 搜索，也未处理真实 snapshot、速度/RSD、completeness 或聚类统计；现有大网格结果仅用于存档读写/布局导出。首次失效链接报告和原生核对误比较 `elapsed_sec` 的报告均保留；排除计时字段后的对照结果另存为 `with_native_mask/legacy_comparison.json`。本轮改动未提交、未推送。

---

> **模型 / Model**: GPT  
> **日期 / Date**: 2026-11-15
