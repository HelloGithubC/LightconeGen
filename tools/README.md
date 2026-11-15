# 保留的独立工具

原有五个 Python 文件已从 `src/` 原样移到 `tools/legacy/`，不依赖新的 `lightconegen` 包。新项目优先使用[模块 API](../doc/MODULE.md)；本目录保留原实验流程和对照入口。

| 绝对路径（根目录为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4`） | 用途 |
|---|---|
| `<ROOT>/tools/legacy/orientation_geometry.py` | 原 mask、距离、旋转与占据几何共用库 |
| `<ROOT>/tools/legacy/orientation_pipeline.py` | 原完整多壳层/多网格/多策略直接计算 pipeline |
| `<ROOT>/tools/legacy/eval_strategy.py` | 原单策略、给定 observer 的直接朝向比较 |
| `<ROOT>/tools/legacy/eval_fft.py` | 原 FFT 联合搜索及完成结果续跑 |
| `<ROOT>/tools/legacy/compare_results.py` | 原结果汇总和 CSV 导出 |

四个命令行入口不带参数均显示帮助并以状态 0 退出；共用几何库不提供 CLI。从仓库根目录直接运行，例如：

```sh
/home/xiaoliang/.conda/envs/xiaoliang/bin/python -B tools/legacy/eval_fft.py
```

完整参数、流程、依赖和实际输入/中间/最终输出清单见[直接网格实验](../doc/experiments/direct_grid.md)、[FFT 放置](../doc/experiments/fft_placement.md)和[FFT 续跑](../doc/experiments/fft_resume.md)。历史命令中的 `src/脚本名.py` 现应替换为 `tools/legacy/脚本名.py`；历史报告保留当时的绝对路径记录。

默认 BGS 数据链接位于 `<ROOT>/mask/BGSmask_nside8192_nested.fits`，数据不会随工具移动。正式运行均需指定新输出目录，建议使用 `<ROOT>/tests/runs/<新运行名>`；已有结果不覆盖，失败时保留部分产物。FFT 与完整 pipeline 自动写日志/manifest，并把字体缓存放在输出目录；单策略入口及汇总入口的差异以各自实验说明为准。stdout/stderr 仍发往终端，没有新的 Slurm 提交步骤或应用临时文件。

此次重构未修改这五个文件，也未移动已有运行目录。四个 FITS 链接已按用户给出的目录名修复为 `DESImocks_old/source/`，实际数据状态见[mask 说明](../mask/README.md)。旧 FFT 工具已在小网格上实际运行，与新包进行覆盖和选择结果对照。
