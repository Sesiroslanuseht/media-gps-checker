# 1.0.1 Windows x64 便携包构建

此版本新增 Windows GUI exe 启动器、官方 Python 嵌入式运行时、Windows Qt 库和完整 ExifTool。用户无需自行安装组件。**这是 Linux 中组装的 Windows 便携包；不是在 Windows 上运行 PyInstaller 构建。**

## 构建输入

- Python 3.12.10 Windows x64 embedded：<https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip>
- ExifTool 13.59 Windows x64：<https://sourceforge.net/projects/exiftool/files/exiftool-13.59_64.zip/download>
- PyPI Windows wheels：PySide6-Essentials 6.8.3、shiboken6 6.8.3、openpyxl 3.1.5、et_xmlfile 2.0.0。
- Zig 0.13.0（通过 PyPI ziglang 0.13.0，Linux x64）交叉编译纯 WinAPI 启动器；只负责启动随包 Python，不改媒体。

本次下载输入的 SHA-256 见 `build-inputs-sha256.json`，便携包文件 SHA-256 见 `SHA256SUMS.txt`。记录哈希用于后续复现比较，不是代码签名。

## 复现

先将上述两个官方 zip 下载到 downloads 文件夹，然后：

```bash
python -m pip install ziglang==0.13.0
python -m pip download --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp --abi cp312 -r requirements.txt --dest downloads
python scripts/build_portable.py downloads dist/MediaGPSChecker
```

输出目录必须不存在。构建脚本保留 Windows 官方运行库及第三方包元数据，修改嵌入式 Python 的 `python312._pth`，使其只使用随包代码。ExifTool 完整目录保留，只把官方 `exiftool(-k).exe` 改名为 `exiftool.exe`。

启动器编译命令：

```bash
python -m ziglang cc -target x86_64-windows-gnu -O2 -municode -Wl,--subsystem,windows scripts/windows_launcher.c -o MediaGPSChecker.exe
```

## 本次实际验证

- 成功生成 `PE32+ x86-64 Windows GUI` 类型的 exe（不是把 Linux 文件改后缀）。
- 已检查 Python、QtCore/QtGui/QtWidgets、Shiboken 和 Windows 平台插件的静态导入依赖；所需第三方运行库在包内，其余为 Windows 系统 DLL。
- Python/Qt/ExifTool 均采用官方 Windows 二进制，未修改二进制内容；仅重命名 ExifTool 启动文件。
- 1.0 核心 35 项 Linux 测试结果保留在 `TEST_REPORT.md`；打包没有改动扫描核心。
- **未完成 Windows 实际启动及扫描测试。** 已尝试本地解包 Wine 9.0 运行这些 Windows 程序，但云端禁止 wineserver 创建 socket，无法启动测试。没有绕过这项限制。
- 这里的静态检查不能代替 Windows 实机测试。解压路径、权限、杀毒软件、资源管理器定位等仍待实机验证。

Qt / PySide 对应源码与许可：

- <https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.8.3>
- <https://download.qt.io/archive/qt/6.8/6.8.3/single/>
- LGPL/GPL 文本保留在 `third-party-licenses`；Python 和 ExifTool 许可保留在各自目录。

便携包中 Qt 为独立动态库，未加密或限制替换，应用源码与启动器 C 源码一并提供。第三方组件保持其各自许可。不要删掉 `_runtime`、`exiftool` 或只单独拷贝 exe。
