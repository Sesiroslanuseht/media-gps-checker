# Kept in the same codebase so both source and frozen program use the same smoke check.
from pathlib import Path
import os

def smoke(destination):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from media_gps.gui import Window
    from media_gps.exiftool import ExifTool
    app = QApplication.instance() or QApplication([])
    w = Window()
    w.show()
    app.processEvents()
    w.close()
    with Path(destination).open('x', encoding='utf-8') as f:
        f.write('Qt offscreen startup: OK\n')
        try:
            reader = ExifTool()
            f.write('ExifTool: ' + reader.check() + '\n')
        except FileNotFoundError:
            f.write('ExifTool: external installation required\n')
