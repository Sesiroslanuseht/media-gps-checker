# 扫描规则与源码启动说明

个人使用的极简中文桌面工具。Python + PySide6，扫描在后台进行，媒体不上传。

本文保留源码启动及扫描规则；当前版本为 1.1，每日行程功能见 JOURNEY_GUIDE.md。TEST_REPORT.md 是初版的历史测试记录，当前测试摘要见 README.md。

## Windows 使用（源码版）

1. 安装 **Python 3.12 64 位**（建议 3.12.10；保留 Python Launcher）。官方下载：<https://www.python.org/downloads/windows/>。
2. 解压整个本项目到一个文件夹，双击 `start_windows.cmd`。首次启动会联网安装固定版本的 Python 依赖；以后检查媒体不需要网络。
3. 从 **ExifTool 官方网站** <https://exiftool.org/> 下载 Windows 64 位压缩包，完整解压。把 `exiftool(-k).exe` 改名为 `exiftool.exe`，**保留旁边整个 `exiftool_files` 文件夹及附带文件**。本程序不自动下载或更新 ExifTool。
4. 界面点“选择 ExifTool”，选择刚才的 `exiftool.exe`。也可以把完整工具包放到项目下 `exiftool` 文件夹，程序会自动查找。
5. 选择电脑上的媒体文件夹，保留默认“全部媒体文件”，点“开始扫描”。包含子文件夹。
6. 勾选“只显示问题／待核实”，点击一行查看详情；“定位选中文件”在 Windows 资源管理器中选中主文件。配对视频的完整路径在详情和报告中。
7. 点“导出全部结果 Excel”，使用**新的文件名**。导出当前扫描范围内全部条目，不受问题筛选开关影响。程序拒绝覆盖已有文件。

如果启动失败，打开终端进入项目目录，执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run_gui.py
```

无需激活虚拟环境。安装依赖可能下载约 100 MB；没有缩略图、地图或视频解码组件。

## 结果是什么意思

| 状态 | 判断规则 |
|---|---|
| GPS 完整 | 至少一组可解析经纬度，范围合理，已读取的坐标来源不冲突；不代表拍摄地点一定真实 |
| GPS 缺失 | 受支持类型成功读取、没有错误/警告，且没有发现可识别 GPS 字段；不能证明是传输丢失 |
| GPS 异常 | 只有纬度或经度、数值越界/非法、EXIF 半球缺失/冲突、来源冲突，或 0,0 待核实 |
| 无法判断 | 不支持类型、读取失败、超时、损坏警告、JSON 解析失败，或仅有不能解读的 GPS 相关字段 |

经纬度 0,0 在地球上确实存在，本工具为排查常见占位值将其列为异常待核实；纬度为 0 或经度为 0 单独出现仍可完整。多来源坐标差异阈值为 0.0001°，可能把有舍入差异的记录列为待核实。

拍摄时间来自元数据；缺失时留空，不拿电脑文件修改时间冒充。1.1 的排序、时区和跨日规则见 JOURNEY_GUIDE.md。报告主表纬度/经度来自主照片；确认配对后 GPS 总状态按“异常 > 无法判断 > 缺失 > 完整”汇总，成员明细保留各文件结果，不拿视频 GPS 补齐照片 GPS。

## 四种扫描范围

- 全部媒体文件（默认）：普通照片、已识别/疑似动态照片、视频及待判断媒体。
- 仅普通照片：未发现可识别动态标记/配对证据的照片，**不保证它过去不是动态照片**。
- 仅动态照片：已识别的动态照片和有依据的疑似项。
- 仅视频：独立视频；已确认属于动态照片的配对视频不再重复列出。

所有范围先读取同一目录中的媒体候选文件，再配对和筛选，避免仅看后缀造成漏配。扫描完成后显示结果；扫描中显示进度。取消会保留已完成批次中的结果，并在报告明确标记“不完整”；被取消的在读批次可能不会纳入。

## 文件识别和动态照片边界

- 支持常见 JPG/JPEG、HEIC/HEIF、PNG、WEBP、TIFF、AVIF，以及 MP4/MOV 等候选类型；具体由 ExifTool 成功识别决定。已知 RAW 等后缀仍会扫描，不支持时保留“无法判断”。
- 对未知后缀/无后缀文件读取最多 64 字节，识别常见 JPEG、PNG、GIF、TIFF、BMP、WEBP、ISO BMFF、AVI 和 Matroska 签名；无法识别的其他文件不列为媒体，跳过数量写入报告。不是任意格式的万能识别器。压缩包内文件不扫描。
- 小米采用的通用 Motion Photo / MicroVideo 标记可以识别。旧版 `MicroVideoOffset` 和新版 XMP 容器目录用于定位动态视频；再只读检查 `ftyp/moov/mdat` 及 box 边界。标记存在但结构不通过，显示“异常或无法确认”，**不直接宣称动态部分已丢失**。
- 私有 LivePhoto/MotionPhoto 等字段仅作为线索；ExifTool 报出二进制内嵌视频但未提供可验证位置，也保留不确定性。**不保证支持所有小米型号、系统版本、私有封装及编辑/社交软件处理后的文件。** 未读到动态标记不等于证明它是普通照片。
- 结构检查不是解码，不能保证视频可播放；本版本不提取内嵌视频另查其 GPS。照片及独立配对视频的 GPS 分别检查。也不解析视频每帧 GPS 轨迹或所有私有数据。
- 只有扫描集合中“一个照片 + 一个视频”共享唯一内容标识时才自动合并。相同文件名只是疑似配对依据，不自动合并；有歧义的记录保留独立计数。无可靠关联元数据时仍可能重复统计，这比误合并无关媒体更稳妥。
- “全部媒体”统计为合并确认配对后的条目数，另显示实际读取文件数。不做内容哈希重复照片清理。

## 只读和运行行为

应用仅以只读方式打开媒体，ExifTool 只使用读取参数，并禁用用户自定义 ExifTool 配置。不会写入 GPS、重命名、移动、删除或复制媒体；用户输出是新建 Excel 和每日 KML。应用没有网络上传、遥测、地图或联网检查代码。安装依赖/下载 ExifTool 是用户单独进行的联网步骤。

操作系统可能自动更新文件“最后访问时间”；这不属于程序修改媒体内容。测试验证内容 SHA-256、修改时间及文件集合没有改变。请避免扫描期间由其他程序编辑源文件。

每批最多 16 个候选文件，默认每批 60 秒超时；取消会终止 ExifTool 子进程（Windows 尝试终止进程树）。大视频读取慢或警告时宁可标成无法判断。跳过目录符号链接、Windows junction 和文件符号链接，避免递归环路；无法访问目录会记入报告提示。网络盘、离线文件、极长路径及挂起的系统 I/O 仍可能导致延迟。

Excel 包含“扫描说明”“媒体结果”“成员明细”三张表，包括路径、类型、拍摄时间、坐标、状态、原因、动态依据和配对成员。元数据作为文本写入，避免以等号开头的内容被 Excel 当作公式。报告含位置和文件路径，分享前自行检查。

## 测试与打包

- 实际执行结果：`TEST_REPORT.md`（历史记录）。
- Windows 可复现流程和云端自动构建：`WINDOWS_BUILD.md`。
- 核心依赖：`requirements.txt`；测试依赖：`requirements-dev.txt`；打包依赖：`requirements-build.txt`。

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:EXIFTOOL_TEST_PATH = 'C:\Tools\exiftool\exiftool.exe'
$env:QT_QPA_PLATFORM = 'offscreen'
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

真实视频测试还需要 FFmpeg 在 PATH 中；未提供 ExifTool/FFmpeg 时，相应测试明确 skipped。测试只生成并修改临时夹具，不修改用户媒体。

可选命令行（便于诊断，无需打开 GUI）：

```powershell
.venv\Scripts\python.exe -m media_gps.cli 'D:\照片' --exiftool 'C:\Tools\exiftool\exiftool.exe' --output 'D:\检查报告.xlsx'
```

技术参考：

- ExifTool 安装及 Windows Unicode 参数：<https://exiftool.org/install.html>、<https://exiftool.org/exiftool_pod.html>
- Google 标记：<https://exiftool.org/TagNames/Google.html>
- Motion Photo 标记可残留，需确认视频实际存在：<https://developer.android.com/media/platform/motion-photo-format>
- PyInstaller 需在目标系统构建：<https://pyinstaller.org/en/stable/>
