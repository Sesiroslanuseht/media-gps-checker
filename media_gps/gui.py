from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                              QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
                              QTableView, QTextEdit, QVBoxLayout, QWidget)

from .core import SCOPES, scan
from .exiftool import ExifTool, Cancelled
from .export import export_xlsx
from .capture_time import asset_time_key, capture_time, fixed_timezone
from .journey import export_journeys


class ScanWorker(QThread):
    progress = Signal(str, int, int)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, folder, executable, scope):
        super().__init__()
        self.folder, self.executable, self.scope = folder, executable, scope
        self.cancel = threading.Event()

    def run(self):
        try:
            reader = ExifTool(self.executable)
            reader.check(self.cancel)
            self.result.emit(scan(self.folder, reader, self.cancel, self.progress.emit, self.scope))
        except Cancelled:
            self.failed.emit('已取消启动。')
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    result = Signal(str)
    failed = Signal(str)

    def __init__(self, result, path, journey=False, offset="+08:00"):
        super().__init__()
        self.scan_result, self.path = result, path
        self.journey, self.offset = journey, offset

    def run(self):
        try:
            if self.journey:
                path, days, points, skipped = export_journeys(self.scan_result, self.path, self.offset)
                self.result.emit(f"{path}（{days} 天，{points} 个地点，跳过 {skipped} 项）")
            else:
                self.result.emit(export_xlsx(self.scan_result, self.path))
        except Exception as exc:
            self.failed.emit(str(exc))


class ResultsModel(QAbstractTableModel):
    headers = ['文件', '拍摄时间（行程时区）', '类型', 'GPS 状态', '纬度', '经度', '动态部分', '原因']

    def __init__(self):
        super().__init__()
        self.assets = []
        self.offset = "+08:00"

    def set_assets(self, assets):
        self.beginResetModel()
        self.assets = assets
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.assets)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.headers[section] if orientation == Qt.Horizontal else str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        a = self.assets[index.row()]
        r = a.members[0]
        if role == Qt.ToolTipRole:
            return '\n'.join(m.path for m in a.members) + '\n' + a.evidence
        if role == Qt.DisplayRole:
            t = capture_time(r, self.offset)
            return [Path(r.path).name, t.local.isoformat(sep=" ") if t.local else "无法确定（排在末尾）", a.kind, a.gps_status,
                    '' if r.gps.latitude is None else str(r.gps.latitude),
                    '' if r.gps.longitude is None else str(r.gps.longitude), a.motion,
                    '; '.join(m.gps.reason for m in a.members)][index.column()]


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('媒体 GPS 检查器 1.1 · 每日行程 · 只读')
        self.resize(1150, 720)
        self.worker = self.export_worker = self.result = None
        main = QWidget()
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)
        layout.addWidget(QLabel('仅在本机读取，不上传媒体。GPS 缺失 ≠ 证明传输丢失。动态结构检查不保证可播放。'))
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('选择包含照片和视频的文件夹（递归扫描）')
        self.choose = QPushButton('选择文件夹')
        self.choose.clicked.connect(self.choose_folder)
        line = QHBoxLayout()
        line.addWidget(self.folder)
        line.addWidget(self.choose)
        layout.addLayout(line)
        line = QHBoxLayout()
        self.executable = QLineEdit()
        self.executable.setPlaceholderText('ExifTool 路径（留空自动查找）')
        self.choose_exe = QPushButton('选择 ExifTool')
        self.choose_exe.clicked.connect(self.select_executable)
        line.addWidget(self.executable)
        line.addWidget(self.choose_exe)
        layout.addLayout(line)
        line = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItems(SCOPES)
        self.start = QPushButton('开始扫描')
        self.start.clicked.connect(self.start_scan)
        self.cancel = QPushButton('取消')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_scan)
        self.filter = QCheckBox('只显示问题／待核实')
        self.filter.toggled.connect(self.refresh)
        self.export = QPushButton('导出全部结果 Excel')
        self.export.setEnabled(False)
        self.export.clicked.connect(self.export_result)
        self.locate = QPushButton('定位选中文件')
        self.locate.clicked.connect(self.locate_file)
        for widget in (self.scope, self.start, self.cancel, self.filter, self.locate, self.export):
            line.addWidget(widget)
        layout.addLayout(line)
        journey_line = QHBoxLayout()
        journey_line.addWidget(QLabel('行程时区 UTC'))
        self.timezone_offset = QLineEdit('+08:00')
        self.timezone_offset.setMaximumWidth(85)
        self.timezone_offset.setToolTip('中国 +08:00，日本 +09:00；统一用此时区排序和分日。无时区照片也按此解释。')
        self.timezone_offset.editingFinished.connect(self.refresh)
        journey_line.addWidget(self.timezone_offset)
        journey_line.addWidget(QLabel('默认北京时间；按拍摄时间排列，未知时间排在末尾'))
        journey_line.addStretch()
        self.journeys = QPushButton('导出每日行程（KML）')
        self.journeys.setEnabled(False)
        self.journeys.clicked.connect(self.export_journey)
        journey_line.addWidget(self.journeys)
        layout.addLayout(journey_line)
        self.bar = QProgressBar()
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.status = QLabel('就绪。四种范围都先读取媒体候选文件，再按识别及配对结果筛选。')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.model = ResultsModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 240)
        self.table.setColumnWidth(2, 165)
        self.table.setColumnWidth(6, 280)
        self.table.setColumnWidth(7, 380)
        self.table.selectionModel().selectionChanged.connect(self.show_detail)
        self.table.doubleClicked.connect(self.locate_file)
        layout.addWidget(self.table, 1)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(145)
        layout.addWidget(self.detail)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, '选择媒体目录')
        if path:
            self.folder.setText(path)

    def select_executable(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 exiftool.exe（不是 -k 版本）')
        if path:
            self.executable.setText(path)

    def set_busy(self, busy):
        for w in (self.start, self.folder, self.choose, self.executable, self.choose_exe, self.scope, self.timezone_offset, self.filter):
            w.setEnabled(not busy)
        self.cancel.setEnabled(busy and bool(self.worker and self.worker.isRunning()))
        self.export.setEnabled(not busy and self.result is not None)
        self.journeys.setEnabled(not busy and self.result is not None)

    def start_scan(self):
        if self.worker and self.worker.isRunning():
            return
        if not Path(self.folder.text()).is_dir() or not self.folder.text().strip():
            QMessageBox.warning(self, '目录无效', '请选择可访问的文件夹。')
            return
        self.result = None
        self.model.set_assets([])
        self.detail.clear()
        self.worker = ScanWorker(self.folder.text(), self.executable.text().strip(), self.scope.currentText())
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(self.on_result)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(lambda: self.set_busy(False))
        self.worker.start()
        self.set_busy(True)
        self.cancel.setEnabled(True)
        self.bar.setRange(0, 0)
        self.status.setText('启动 ExifTool…')

    def cancel_scan(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel.setEnabled(False)
            self.status.setText('正在取消，保留已完成部分…')

    def on_progress(self, phase, done, total):
        self.bar.setRange(0, total or 0)
        self.bar.setValue(done)
        self.status.setText(f'{phase}：{done}' + (f' / {total}' if total else ''))

    def on_result(self, result):
        self.result = result
        self.bar.setRange(0, max(result.discovered, 1))
        self.bar.setValue(len(result.records))
        self.refresh()
        self.detail.setPlainText('\n'.join(result.notices) or '点击一行查看路径、拍摄时间、GPS 原始字段及动态识别依据。')

    def on_error(self, message):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.status.setText(message)
        QMessageBox.warning(self, '提示', message)

    def refresh(self):
        if self.result is None:
            return
        try:
            offset = self.timezone_offset.text().strip()
            fixed_timezone(offset)
            self.result.assets.sort(key=lambda a: asset_time_key(a, offset))
            self.model.offset = offset
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        assets = [a for a in self.result.assets if not self.filter.isChecked() or a.problem]
        self.model.set_assets(assets)
        from collections import Counter
        counts = Counter(a.gps_status for a in self.result.assets)
        self.status.setText(('已取消（部分结果）' if self.result.cancelled else '已完成') +
                            f' | 已读取 {len(self.result.records)}/{self.result.discovered} 个文件 | 范围内 {len(self.result.assets)} 条，显示 {len(assets)} 条 | ' +
                            '，'.join(f'{k} {v}' for k, v in counts.items()) + f' | 提示 {len(self.result.notices)} 条（见报告）')

    def current_asset(self):
        index = self.table.currentIndex()
        return self.model.assets[index.row()] if index.isValid() and index.row() < len(self.model.assets) else None

    def show_detail(self, *args):
        a = self.current_asset()
        if a:
            text = [a.motion, a.evidence]
            for m in a.members:
                text.extend([m.path, f'拍摄时间：{m.taken or "未读到"}', f'{m.gps.status}：{m.gps.reason}', m.gps.evidence])
            self.detail.setPlainText('\n'.join(text))

    def locate_file(self, *args):
        a = self.current_asset()
        if not a:
            return
        p = Path(a.members[0].path)
        try:
            if os.name == 'nt':
                subprocess.Popen(['explorer.exe', '/select,', str(p)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
        except OSError as exc:
            QMessageBox.warning(self, '定位失败', str(exc))

    def export_result(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出报告（请选择新文件名）', '媒体GPS检查报告.xlsx', 'Excel (*.xlsx)')
        if not path:
            return
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'
        if Path(path).exists():
            QMessageBox.warning(self, '文件已存在', '为避免覆盖文件，请使用新的报告文件名。')
            return
        self.export_worker = ExportWorker(self.result, path)
        self.export_worker.result.connect(lambda p: self.status.setText('报告已导出：' + p))
        self.export_worker.failed.connect(self.on_error)
        self.export_worker.finished.connect(lambda: self.set_busy(False))
        self.set_busy(True)
        self.cancel.setEnabled(False)
        self.status.setText('正在导出报告…')
        self.export_worker.start()

    def export_journey(self):
        if self.result is None:
            return
        try:
            offset = self.timezone_offset.text().strip()
            fixed_timezone(offset)
        except ValueError as exc:
            QMessageBox.warning(self, '时区格式', str(exc))
            return
        parent = QFileDialog.getExistingDirectory(self, '选择保存行程的位置（将新建行程文件夹）')
        if not parent:
            return
        self.export_worker = ExportWorker(self.result, parent, journey=True, offset=offset)
        self.export_worker.result.connect(lambda p: self.status.setText('每日行程已导出：' + p))
        self.export_worker.failed.connect(self.on_error)
        self.export_worker.finished.connect(lambda: self.set_busy(False))
        self.set_busy(True)
        self.cancel.setEnabled(False)
        self.status.setText('正在按日期生成 KML 和拍摄顺序清单…')
        self.export_worker.start()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_scan()
            self.status.setText('正在取消扫描；任务结束后可关闭窗口。')
            event.ignore()
        elif self.export_worker and self.export_worker.isRunning():
            self.status.setText('正在保存报告；保存完成后可关闭窗口。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    return app.exec()
