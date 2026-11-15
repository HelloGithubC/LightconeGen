# Python 包使用说明

可导入包位于 `src/lightconegen/`，从仓库根目录安装到当前环境：

```sh
cd /mnt/xiaodong/xiaoliang/software/LightGen/ForHR4
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -m pip install -e .
```

安装命令尚未执行。项目环境已有 NumPy 2.2.6、SciPy 1.15.2、Astropy 6.1.7、healpy 1.19.0、Matplotlib 3.10.6 和 setuptools 82.0.1。包 API、算法、参数、示例和输入/中间/输出文件完整清单见[模块指南](../doc/MODULE.md)。

主要接口从 `lightconegen` 导入：

```python
from lightconegen import (
    Lightcone, LightconeLayout, SearchResult, SkyMask,
    load_layout, load_result, plot_coverage, rebuild_coverage,
    resume_search, save_result, search_lightcones, select_points,
)
```

`search_lightcones` 返回 `SearchResult`；`save_result` 将结果写入新目录。布局模式只保存 `layout.json`，完整模式还保存覆盖图、候选库、选择记录、搜索诊断、observer 距离、结果配置和 manifest。`load_layout` 可读取紧凑布局及旧 `result.json`；`load_result` 可读取新完整结果和旧 FFT 完成结果。`resume_search` 可从完整结果续跑。`rebuild_coverage` 返回 `uint32` 覆盖数组；`select_points` 返回调用者输入位置数组中的行索引。`plot_coverage` 接受覆盖 ndarray 和输出路径。

旧五个脚本逐字节保存在 `tools/legacy/`，仍作为独立 CLI 使用，不是新包的运行依赖。其原入口、运行记录和文件格式见[历史实验文档](../doc/experiments/)及[旧使用说明](../doc/README.md)。

长度单位为 Mpc/h。红移区间按 HR4（Ωm=0.26、ΩΛ=0.74）换算，距离区间直接使用 Mpc/h。包不读取或修改星系目录，不解释速度，也不施加 RSD。导入 `lightconegen` 不写文件、不设置环境变量、不安装日志处理器，也不导入 pyplot；Python 自身可能生成 `__pycache__`，可用 `-B` 或 `PYTHONDONTWRITEBYTECODE` 禁止。healpy 查询或显式绘图可能触发 Matplotlib 字体缓存，`MPLCONFIGDIR` 由调用者控制。此次验证的实际结果、路径和范围见[模块指南末尾](../doc/MODULE.md#本次验证记录)。本机 FITS 链接已修复，NSIDE32 派生 mask 的 nmesh16 核验与原生 NSIDE8192 mask 的 nmesh32 核验均已完成。
