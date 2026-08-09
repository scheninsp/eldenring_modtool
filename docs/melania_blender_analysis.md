Malenia.blend 文件分析报告
基本信息
项目	内容
Blender 版本	2.83 (64-bit, Little-endian)
文件格式	gzip 压缩包裹的 DNA 二进制格式
文件大小	57.2 MB (解压后 88.9 MB)
总数据块	120,893 个
数据实例	3,306,006 个
数据类型	90 种
数据内容概览

TYPE                    COUNT      说明
ColorMapping            1,244,245   颜色映射 (曲线点等)
Stereo3dFormat           408,064   立体 3D 格式
Lamp                     408,060   灯光数据
ushort                   408,060   无符号短整型数组
MovieCache                240,936   视频缓存
CurveMapping             228,193   曲线映射 (FCurve)
ColorManaged...Settings  136,021   色彩管理
ImageTile                109,702   图像瓦片
bNodeTree                109,698   节点树
ScrVert                    2,782   屏幕布局顶点
...                          ...   (共 90 种类型)
插件依赖检测结果
这个文件使用 Blender 2.83 保存，90 种数据类型全部为 Blender 2.83 原生类型，没有发现需要外部插件的迹象。文件包含的主要数据是：

色彩管理/颜色映射数据 (大量 ColorMapping、ColorManagedColorspaceSettings)
灯光 (Lamp 类型，408K 实例 — 这很奇怪，可能是 UV face 级别的数据或粒子系统)
节点树 (bNodeTree，约 110K)
图像相关 (ImageTile，约 110K)
屏幕/UI 布局数据