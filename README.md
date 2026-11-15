# LightconeGen

面向 HR4 / DESI BGS 的光锥几何测试工具：用实际角向 mask 和观测径向范围，在周期模拟盒中比较、搜索 observer 的位置与朝向。

## 当前功能

- 直接网格计算：给定 observer，比较 axes、random、mask-diverse 朝向，并可局部微调。
- 周期 FFT 联合搜索：逐个放置窗口，约束最小 observer 间距，记录重叠及覆盖。
- 完成结果续跑：保留已有位置、朝向和搜索历史，只增加新窗口，写入新目录。
- 结果汇总：按比较组目录查看配置、指标及逐窗口选择，可导出 CSV。

几何基线已完成：盒长 3150 Mpc/h、BGS z3=[0.30,0.40)、512³ 网格、axes 13 朝向、最小 observer 间距 500 Mpc/h，从 N=5 续跑至 N=15；最终非重复覆盖盒子 42.1322189%。详见 [N=5 记录](tests/FFT_README.md)和 [N=15 续跑记录](tests/FFT_RESUME_README.md)。

## 使用

依赖 Python、NumPy、SciPy、Astropy、healpy、Matplotlib；已验证版本见 [src 使用说明](src/Readme.md)。无需安装为 Python 包，也无需安装父目录的 LightGen。

在仓库根目录执行；四个命令行入口不带参数时均显示帮助：

```sh
python -B src/eval_fft.py
python -B src/eval_strategy.py
python -B src/orientation_pipeline.py
python -B src/compare_results.py
```

先按 [mask 说明](mask/README.md)提供 BGS FITS 数据。下列是新运行示例，**本次仓库初始化没有执行此实验**；输出目录必须不存在：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B src/eval_fft.py 1575 1575 1575 3150 \
  --mask mask/BGSmask_nside8192_nested.fits \
  --nmesh 512 --z-range 0.30 0.40 --strategy axes \
  --angles-deg 30 60 90 120 --num-cones 5 --min-observer-distance 500 \
  --output-dir tests/runs/fft_axes_z3_n512_N5_new
```

512³、13 朝向的既有运行峰值内存约 20.8 GiB。续跑需先在本地具有完整来源结果：

```sh
python -B src/eval_fft.py \
  --resume-from tests/runs/fft_axes_z3_n512_N5_new \
  --num-cones 15 --output-dir tests/runs/fft_axes_z3_n512_N15_new
```

上面的两个 `_new` 目录均未在此次初始化中创建。已有服务器运行及其绝对路径保留在实验记录中，实验数据本身不随仓库发布。

## 文档与数据

| 路径 | 内容 |
|---|---|
| [src/Readme.md](src/Readme.md) | 所有入口、流程、参数、依赖及输入/中间/输出清单 |
| [src/ToDo.md](src/ToDo.md) | 各模型的讨论、待办与完成情况 |
| [doc/HR4_BGS_Lightcone_Strategy.md](doc/HR4_BGS_Lightcone_Strategy.md) | 科学约定与后续系统误差任务 |
| [tests/README.md](tests/README.md) | 原直接计算 pipeline 和比较组记录 |
| [tests/FFT_README.md](tests/FFT_README.md) | FFT 工作流程、参数及 N=5 实际运行 |
| [tests/FFT_RESUME_README.md](tests/FFT_RESUME_README.md) | 续跑实现及 N=15 实际运行 |
| [mask/README.md](mask/README.md) | 本地数据要求和符号链接说明 |
| [doc/REPOSITORY.md](doc/REPOSITORY.md) | 仓库独立化方式、维护命令及文件清单 |

Git 跟踪代码和文档；`tests/runs/`、`mask/*.fits`、Python/编辑器缓存由 `.gitignore` 排除。它们仍保留在当前服务器上。其他机器 clone 后需自行提供 mask，恢复完整结果后才能续跑已有实验。

## 来源与当前范围

本项目从 [SoumyaShreeram/LightGen](https://github.com/SoumyaShreeram/LightGen) checkout 中的 ForHR4 目录独立建立；只导入该目录的代码和文档。来源及原 MIT 许可证全文保留在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

当前只实现几何窗口放置；completeness、真实 snapshot、速度/RSD 和相关函数/AP 分析尚未接入。网格和朝向库有限，逐个放置采用贪心选择；低重叠与 observer 间距不代表 mock 统计独立。
