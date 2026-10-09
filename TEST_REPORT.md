# 实际测试记录

执行日期：2026-10-09。源码版本：1.0.0。

## 已执行

在 Linux x86_64 云端、Python 3.12.14 的**新建独立虚拟环境**中安装 `requirements-dev.txt` 的固定依赖后执行：

```bash
QT_QPA_PLATFORM=offscreen EXIFTOOL_TEST_PATH=/tmp/exiftool-13.40/exiftool \
/tmp/media-gps-test-env/bin/python -m unittest discover -s tests -v
```

结果：**35 项测试，全部通过，无 skipped，2.266 秒**。这是本次生成的小型夹具测试耗时，不代表上千张真实照片的扫描速度。原始日志见 `test-results.txt`，实际 Python 依赖见 `test-environment.txt`。

验证范围：

- GPS 完整、缺失、异常、未知；EXIF 半球、负数、边界、NaN、无穷、单侧坐标、0,0、多源冲突、ISO 6709 和不支持类型。
- MicroVideoOffset、新版 XMP 容器目录、内嵌 MP4 box 结构、残留标记、错误偏移、截断视频、关闭的动态标记。
- 内容 ID 唯一配对、成员独立 GPS、不自动合并同名/歧义配对、四种范围和配对后去重。
- 递归、中文/空格/# 路径、未知扩展名签名、损坏 HEIC 夹具、符号链接跳过、1200 个文件的批处理（后者使用模拟读取器，不是 1200 张真实媒体性能测试）。
- 取消后部分结果、读取超时、JSON 错误、缺失返回、stderr、换行路径注入拒绝。
- Excel 三张表、字段写入、公式注入防护、拒绝覆盖已有文件。
- 真实 ExifTool **13.40**（官方 GitHub 仓库 tag 13.40 的 Perl 版）读取人工生成的 JPEG/PNG/无扩展名 JPEG、损坏媒体及含位置 MP4。
- 用 FFmpeg 生成实际视频，写入测试位置元数据，再组合 JPEG+MP4 进行动态识别测试；同时验证新版 XMP 容器的实际 ExifTool 字段名。
- 扫描前后比较生成媒体的 SHA-256、修改时间和文件集合，确认没有改写/增删媒体。所有写入元数据动作仅在临时测试夹具准备阶段，生产扫描没有写参数。
- Linux offscreen Qt 界面实例化、定时器在扫描期间继续响应、取消、问题筛选、详情与后台 Excel 导出。
- 源码 `run_gui.py --self-test` 启动检查、Python compileall 语法检查。
- Linux 上固定打包依赖的 pip dry-run 解析通过；这不是 Windows 打包。

`docs/gui-preview.png` 是 Linux offscreen 中用示例记录生成的真实 Qt 窗口截图；不是 Windows 实机截图，也不是对用户媒体的扫描。云端缺少系统中文字体，截图进程额外加载了 Noto Sans CJK 字体；该字体没有随程序分发。Windows 使用系统字体。

## 尚未执行

- Windows 10/11 实机 GUI、资源管理器选中文件、Windows ExifTool 进程树取消、Windows junction、长路径/网络盘权限等系统行为。
- Windows PyInstaller 打包、打包后 exe 运行、GitHub Actions 实际构建和未安装 Python 的干净 Windows 测试。**没有 Windows exe 成品。**
- 真实小米手机原始 Moving Photo、所有型号和系统版本、实际 HEIC/AVIF 文件；当前有元数据/容器夹具与损坏 HEIC 测试，不可等同真实 HEIC 全覆盖。
- 大型真实素材库速度/峰值内存、所有私有 GPS 格式、视频可播放性、内嵌视频单独 GPS。

## 复现注意

ExiftTool 的 JSON 实际输出包含实例分组和 `ContainerDirectory`；代码及集成测试已针对这些输出修正。读取参数使用单个 `-q` 抑制批次摘要，保留错误/警告，防止正常摘要被误作读取错误。测试不是只对手写元数据字典的自洽验证。

没有 ExifTool 环境变量或 PATH 工具时，真实集成测试明确 skipped；没有 FFmpeg 时视频夹具测试 skipped；Windows 下 POSIX 慢进程及符号链接夹具测试 skipped。需查看完整日志中的 skipped，不能只看最后 OK。
