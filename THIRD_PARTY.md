# 第三方依赖与分发说明

本项目自有源码使用 MIT 许可，见 LICENSE。依赖保持各自许可，不受本项目 MIT 许可替代。

- PySide6 Essentials / Qt / Shiboken：Qt for Python 官方发行。请保留发行包中的许可证和版权说明，参考 <https://doc.qt.io/qtforpython-6/licenses.html>。本项目选择 onedir，Qt 以动态库随目录分发；打包脚本保存已安装发行物的许可/元数据。若再次对外分发，应核对所用模块的 LGPL/GPL/商业许可要求及对应源代码提供要求。
- openpyxl：MIT；et_xmlfile：MIT。脚本复制安装分发中的许可和元数据。
- PyInstaller：仅用于构建。官方许可与分发例外见 <https://pyinstaller.org/en/stable/license.html>。
- ExifTool：独立的第三方工具，本源码包不包含其程序。请从 <https://exiftool.org/> 获取，遵守其随包许可（与 Perl 相同的许可条款），保留官方附带的许可/版权文件。新版 Windows 包需要 exe 和完整 exiftool_files 目录一起分发；其中包含的 Perl 及其他组件也保留各自许可。
- Pillow：仅生成测试素材，非应用运行依赖。
- FFmpeg：仅可选地生成测试视频，不随应用分发，也不是扫描运行依赖。

不要从不明下载站获取 ExifTool，不要只拷贝 exiftool.exe 而遗漏运行文件夹。程序不会要求管理员权限，也不会替用户关闭安全软件。
