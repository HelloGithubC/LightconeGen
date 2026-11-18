# LightconeGen

LightconeGen 是用于周期模拟盒中光锥窗口几何搜索和应用的 Python 包。它根据角向 survey mask 与径向范围选择 observer 位置和朝向。包 API 位于 `src/lightconegen/`，详细流程、参数、依赖、运行方式和文件清单见[模块指南](doc/MODULE.md)。

已知光锥布局后，可以用 `create_random_mock` 按指定共动数密度生成供 `DR`、`RR` 使用的随机点。调用示例见[随机目录生成](doc/MODULE.md#生成随机目录)。

原有五个独立脚本按字节保存在 `tools/legacy/`：`orientation_geometry.py`、`orientation_pipeline.py`、`eval_strategy.py`、`eval_fft.py` 和 `compare_results.py`。它们保留原命令行入口、默认值和输出格式；历史实验记录仍描述这些旧脚本的实际运行，不代表新包运行。

从本目录安装到当前 Python 环境（此命令尚未执行）：

```sh
python -m pip install -e .
```

主要入口从 `lightconegen` 导入：

```python
from lightconegen import search_lightcones, save_result

result = search_lightcones(
    boxsize=3150.0,
    mask="/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/BGSmask_nside8192_nested.fits",
    z_range=(0.30, 0.40),
    nmesh=512,
    num_cones=5,
    strategy="axes",
    min_observer_distance=500,
    result_mode="layout",
)
save_result(result, "/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/tests/runs/package_example")
```

示例未执行，目录也未创建。默认 `observer=None` 使用盒子中心。`layout` 模式只写 `layout.json`；`full` 模式写完整搜索结果。包使用 Mpc/h、周期边界、网格中心 `(i + 0.5) * L / nmesh` 和 xyz C-order。HR4 红移距离采用 Ωm=0.26、ΩΛ=0.74；窗口只描述几何，不处理速度或 RSD。导入包不会读写文件或初始化绘图；Python 字节码及运行时字体缓存行为见[文件与副作用清单](doc/MODULE.md#文件与副作用)。

旧实验方法和绝对路径记录见 [`doc/experiments/`](doc/experiments/)，mask 数据要求见 [`mask/README.md`](mask/README.md)。本次验证的实际文件及各项结果见[模块指南末尾](doc/MODULE.md#本次验证记录)。四个本地 mask 链接已修复并指向 `DESImocks_old/source/`；派生 NSIDE32 mask 的 nmesh16 核验和原生 NSIDE8192 mask 的 nmesh32 核验均已完成，验证报告状态和范围见模块指南。
