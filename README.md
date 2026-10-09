# Media GPS Checker · 照片与视频 GPS 检查器

Check missing GPS in photos, videos and motion photos. Export daily travel tracks to KML.

Version / 版本：**1.1** · Windows x64 portable / Windows x64 便携版

## 中文

### 下载与运行

从 [v1.1 发行版](../../releases/tag/v1.1) 下载 `MediaGPSChecker_Windows_x64_Portable_v1.1_clean.zip`，**完整解压后**双击 `MediaGPSChecker.exe`。请保留整个解压目录及其子目录，不要只取出 exe，也不要直接在压缩包内运行。便携包包含运行依赖，无需另装 Python 或 ExifTool。GitHub 自动生成的 Source code 压缩包是源码，不是 Windows 便携版。

### GPS 批量检查

1. 选择媒体文件夹，默认使用“全部媒体文件”，递归扫描照片、动态照片和视频。
2. 查看 GPS 完整、缺失、异常和无法判断等结果；可筛选问题并定位原文件。
3. 导出 Excel 检查报告，或导出按拍摄时间排列的每日 KML 行程。

支持 JPG/JPEG、HEIC、PNG、MP4/MOV 等；实际读取能力以 ExifTool 的结果为准。读取失败或不支持的文件不会直接当作“GPS 缺失”。扫描只读，不修改、移动或重命名原媒体，不上传媒体，也没有遥测。

### 动态照片识别边界

动态照片识别依赖可识别的元数据、内容标识和容器结构证据。只有可靠配对才合并计数，不凭同名文件自动合并；无法确认配对时保留独立记录。不保证覆盖所有厂商、手机型号、系统版本或编辑后的文件，结构识别也不等于验证视频可播放性。

每日行程中，已确认配对的动态照片只使用主照片的 GPS 与时间，配对视频不重复计点，也不会用视频数据补齐主照片缺失的信息。

### 按拍摄时间导出每日 KML

扫描后点击“导出每日行程（KML）”。程序按拍摄元数据排序并按所选行程时区分日，每天一个 KML，另附拍摄顺序与跳过清单 Excel。不会用文件复制时间代替拍摄时间。

- 中国旅行默认 `UTC+08:00`；其他地区选择对应固定 UTC 偏移，本版不自动处理夏令时。
- 缺少可靠 GPS 或可解析拍摄时间的条目会记录跳过原因，不强行加入轨迹。
- 一天只有一个有效点时只输出地点标记，不跨天连线。
- 连线仅连接拍摄地点，不代表真实步行或驾驶路线，未拍摄路段无法还原。
- KML 使用 WGS84 坐标；无时区照片按所选时区解释。部分设备的 QuickTime 时间可能有偏差，请核对导出清单。
- “只显示问题”只影响屏幕显示，不缩减行程导出；扫描取消后的导出会标记为部分结果。

详见 [每日行程说明](JOURNEY_GUIDE.md)。报告可能包含本机完整文件路径，KML 含精确位置；分享前请检查。演示截图使用合成数据，不是个人旅行记录。

### 验证状态

据随包记录，v1.1 已在 Linux 云端通过 **50 项自动化测试**，涵盖 GPS、分类与配对去重、Excel、只读扫描、拍摄时间排序、日期分组、KML 和 Qt offscreen 界面测试。本次仓库上传未重新执行这些测试。

**v1.1 尚未完成新版 Windows 实机运行及地图软件导入验证。** 旧版可运行的反馈不等于新版验证；KML 结构测试也不等于地图软件实测。[TEST_REPORT.md](TEST_REPORT.md) 保留 v1.0 的历史记录，其中“没有 Windows exe 成品”等文字描述的是当时状态；v1.1 记录见 [JOURNEY_GUIDE.md](JOURNEY_GUIDE.md)。

## English

### Download and run

Download `MediaGPSChecker_Windows_x64_Portable_v1.1_clean.zip` from the [v1.1 release](../../releases/tag/v1.1), **extract the entire archive**, then run `MediaGPSChecker.exe`. Keep all bundled files and subfolders together. Do not run the executable inside the ZIP or copy it out on its own. The portable package includes its runtime dependencies; no separate Python or ExifTool installation is required. GitHub's automatically generated Source code archives are not the Windows portable application.

### Batch GPS checks

Select a media folder and scan recursively using the all-media scope. Review complete, missing, abnormal or undetermined GPS results, filter problems, locate original files and export an Excel report. Supported formats include JPG/JPEG, HEIC, PNG and MP4/MOV, subject to ExifTool's actual reading capabilities. Unsupported or unreadable files are not automatically classified as missing GPS.

Scanning is read-only: it does not modify, move or rename source media, upload media or collect telemetry.

### Motion-photo detection limits

Detection relies on recognizable metadata, content identifiers and container structure. Only confidently matched photo/video pairs are counted together; matching filenames alone are insufficient. Unconfirmed files remain separate records. Detection does not guarantee coverage of every vendor, device, operating-system version or edited file, and does not verify video playback.

For daily journeys, a confirmed pair contributes only the primary photo's location and capture time. Its paired video is not counted again and is not used to fill missing data in the photo.

### Daily KML journeys by capture time

Export one KML per day, ordered by capture metadata and grouped in the selected journey timezone, plus an Excel list of capture order and skipped items. File-copy timestamps are not used as capture times.

- The default offset is `UTC+08:00`. Choose the trip's fixed UTC offset; automatic daylight-saving adjustment is not supported.
- Items without reliable GPS or a parseable capture time are skipped with a reason.
- A day with one valid point contains a placemark only. Lines never join different days.
- Straight lines connect capture locations; they are not reconstructed walking or driving routes.
- KML uses WGS84 coordinates. Photos without timezone metadata are interpreted in the selected timezone. Some devices write nonstandard QuickTime times, so check the exported list.
- The problem-only display filter does not reduce journey export. Exports after a cancelled scan are marked as partial.

See the [journey guide (Chinese)](JOURNEY_GUIDE.md) for detailed rules. Reports can contain full local paths and KML files contain precise locations; review them before sharing. Preview images use synthetic data.

### Validation status

The supplied records report **50 automated tests passing on Linux in the cloud for v1.1**, covering GPS, classification, pair deduplication, Excel, read-only scanning, capture-time sorting, date grouping, KML and Qt offscreen GUI behavior. These tests were not rerun as part of this repository upload.

**The updated v1.1 package has not completed Windows device testing or import testing in mapping applications.** Reports that an earlier version ran successfully do not validate this release. KML structure tests are not map-import tests. [TEST_REPORT.md](TEST_REPORT.md) is the historical v1.0 report; its statement that no Windows executable existed describes that earlier stage. See [JOURNEY_GUIDE.md](JOURNEY_GUIDE.md) for the v1.1 record.

## Development / 开发

Python 3.12; pinned dependencies are listed in `requirements*.txt`.

```sh
python -m pip install -r requirements-dev.txt
python run_gui.py
python -m unittest discover -s tests -v
```

Real-metadata integration tests require ExifTool and `EXIFTOOL_TEST_PATH`; video fixtures require FFmpeg. Headless Linux GUI tests use `QT_QPA_PLATFORM=offscreen`. Tests explicitly skip when required tools are unavailable; inspect skipped results as well as the final status.

真实元数据集成测试需要 ExifTool 并设置 `EXIFTOOL_TEST_PATH`；视频夹具需要 FFmpeg。Linux 无显示环境使用 `QT_QPA_PLATFORM=offscreen`，缺少工具时测试会明确跳过。

[技术说明 / Technical guide](TECHNICAL_GUIDE.md) · [Windows 构建 / Windows build](WINDOWS_BUILD.md) · [便携包组装 / Portable packaging](WINDOWS_PORTABLE_BUILD.md)

The included Windows GitHub Actions workflow has not been validated on GitHub in the supplied records. It does not bundle ExifTool by default; follow the build documentation. 随包 Windows 工作流尚无 GitHub 执行验证记录，默认不捆绑 ExifTool，需按构建说明配置。

## License / 许可证

Project source code is licensed under [MIT](LICENSE). Third-party components retain their own licenses; the project's MIT license does not replace them. Keep bundled license and copyright notices when redistributing. See [THIRD_PARTY.md](THIRD_PARTY.md).

自有源码使用 [MIT](LICENSE)，第三方依赖保持各自许可；再分发时应保留随包许可和版权文件，详见 [第三方说明](THIRD_PARTY.md)。
