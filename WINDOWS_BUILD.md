# Windows 打包与云端构建

目标：Windows 10/11 x64，Python **3.12.10 x64**。使用固定版本依赖和 PyInstaller **6.12.0**。输出为整个便携文件夹，而非单独一个 exe；必须一起保留 `_internal` 中的 Qt 库。本流程是可复现操作说明，不承诺不同系统生成逐字节相同的二进制。

当前交付在 Linux 云端完成，**未执行 Windows 打包或 Windows 实机测试，也未产生 Windows exe**。PyInstaller 不是跨平台编译器，不能把 Linux 构建产物标成 Windows 程序。

## 本地 Windows 打包

在解压的项目目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

这只对本次 PowerShell 进程放行项目脚本。脚本会建立 `.venv-build`、安装锁定依赖、运行测试、打包、执行 offscreen 启动检查并生成：

```
dist\MediaGPSChecker-Windows-x64.zip
```

解压后运行其中 `MediaGPSChecker.exe`。默认包**不包含 ExifTool**，第一次使用要另下载官方 ExifTool，在界面选择它。无需安装 Python。

如需把 ExifTool 随程序一起带走，先下载官方 Windows x64 包，完整解压并把 exe 改名为 `exiftool.exe`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -ExifToolDirectory 'C:\Tools\exiftool'
```

该目录必须同时包含 `exiftool.exe`、`exiftool_files` 和官方附带文件。脚本复制整个目录，不修改下载的来源目录，并用它执行真实 ExifTool 测试。不要传入包含私人文件的目录。

为重现自己的分发版本，保留官方 ExifTool 原始 zip，记录版本及 SHA-256：

```powershell
Get-FileHash 'C:\Downloads\exiftool-version_64.zip' -Algorithm SHA256
```

本云端真实测试所用版本为官方仓库 tag **13.40** 的 Perl 版；没有核验对应 Windows 分发包的哈希。本交付不内置未经核验的 Windows 下载地址或可执行文件。不应把工具自动更新到不可追溯版本后仍声称构建完全一致。

## 不依赖本地电脑的 GitHub Actions

项目已附 `.github/workflows/windows-build.yml`。把**源码文件夹内容**放入你自己的 GitHub 仓库（可以是私有仓库，不需要上传照片），在 Actions 选择 **Windows x64 build → Run workflow**。工作在 GitHub 的 Windows 云端机器执行，本地电脑可以关闭。

构建完成后下载 Artifacts 中的 `MediaGPSChecker-Windows-x64`。默认生成需要外置 ExifTool 的应用；工作流不会下载或上传你的媒体。

可选：把完整官方 ExifTool 放进仓库 `vendor/exiftool`（`.gitignore` 默认排除此目录；如决定分发需显式加入并保留许可文件），工作流会一并打包。未提供时真实 ExifTool 测试 skipped；FFmpeg 不在 PATH 时真实视频夹具测试 skipped。CI 不把跳过的测试视为已验证。

当前没有代你创建 GitHub 仓库、推送代码或触发构建。配置文件已经交付，不能将它的存在当成构建成功。发布前仍需 Windows 人工检查：启动、中文/emoji 路径、资源管理器定位、取消和关闭、长路径、HEIC/真实小米动态照片、导出及杀毒误报。生成的 exe 未签名。

工作流固定 Windows 2022 和 Python 3.12.10，Python 依赖固定版本；GitHub Actions 本身使用官方主版本标签（非 commit SHA），因此这是依赖/步骤可复现方案，而非供应链完全冻结或字节级可复现构建。
