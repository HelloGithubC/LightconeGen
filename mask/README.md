# 本地 mask 数据

本目录的 FITS 数据不进入 Git。程序通过 `--mask` 读取实际文件；可将数据放在本目录，也可用符号链接，或直接传其他绝对路径。

当前几何入口使用 `BGSmask_nside8192_nested.fits`：完整 HEALPix FITS 表、NESTED、NSIDE8192，读取第一字段，有效标签为 **4**。`--angular-nside` 不改变该原生数据分辨率。

当前服务器目录为 `/mnt/xiaodong/xiaoliang/software/LightGen/ForHR4/mask/`，四个已存在的符号链接如下；本次初始化未修改它们或读取/复制其大文件内容：

| 本目录内文件名 | 当前绝对目标路径 | 用途 |
|---|---|---|
| `BGSmask_nside8192_nested.fits` | `/mnt/xiaodong/xiaoliang/DESImocks/source/BGSmask_nside8192_nested.fits` | 当前几何测试的 BGS footprint |
| `BGS_BRIGHT_mean_comp_nside128_nested.fits` | `/mnt/xiaodong/xiaoliang/DESImocks/source/BGS_BRIGHT_mean_comp_nside128_nested.fits` | 已有 BGS completeness，尚未接入几何入口 |
| `LRGmask_nside8192_nested.fits` | `/mnt/xiaodong/xiaoliang/DESImocks/source/LRGmask_nside8192_nested.fits` | 已有 LRG footprint，未用于此次 BGS 基线 |
| `LRG_mean_comp_nside128_nested.fits` | `/mnt/xiaodong/xiaoliang/DESImocks/source/LRG_mean_comp_nside128_nested.fits` | 已有 LRG completeness，未用于此次 BGS 基线 |

其他机器需自行提供数据；这些服务器绝对路径不能直接使用。可从仓库根目录创建链接，下面仅是未执行的示例，须替换数据路径：

```sh
ln -s /absolute/path/to/BGSmask_nside8192_nested.fits mask/BGSmask_nside8192_nested.fits
```

不使用覆盖选项；目标链接已存在时应直接使用现有数据。此步骤只生成一个被 Git 忽略的符号链接，不生成日志、缓存或中间数据。
