from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time


class Cancelled(Exception):
    pass


def locate_exiftool(explicit=''):
    if explicit:
        p = Path(explicit).absolute()
        if not p.is_file():
            raise FileNotFoundError('所选 ExifTool 文件不存在')
        if p.name.lower() == 'exiftool(-k).exe':
            raise ValueError('请先将 exiftool(-k).exe 改名为 exiftool.exe，保留旁边的 exiftool_files 文件夹')
        return str(p)
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    for p in (base / 'exiftool' / 'exiftool.exe', base / 'exiftool.exe', base / 'vendor' / 'exiftool' / 'exiftool.exe'):
        if p.is_file():
            return str(p)
    exe = shutil.which('exiftool')
    if exe:
        return exe
    raise FileNotFoundError('未找到 ExifTool。请选择 exiftool.exe，或将其放入程序旁的 exiftool 文件夹。')


def stop_process(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        # The Windows ExifTool launcher starts a Perl child. Stop the complete process tree.
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
    else:
        proc.kill()
    proc.communicate()


class ExifTool:
    def __init__(self, executable='', timeout=60):
        self.executable = locate_exiftool(executable)
        self.timeout = timeout
        self.version = ''

    def _run(self, arguments, data, cancel, timeout=None):
        if cancel.is_set():
            raise Cancelled()
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        # Disable user .ExifTool_config. No shell, no writing/copying/renaming flags.
        proc = subprocess.Popen([self.executable, '-config', '', *arguments], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        start = time.monotonic()
        initial = True
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() - start > (timeout or self.timeout):
                    raise TimeoutError('ExifTool 读取超时')
                try:
                    out, err = proc.communicate(input=data if initial else None, timeout=0.1)
                    return proc.returncode, out, err
                except subprocess.TimeoutExpired:
                    initial = False
        finally:
            if proc.poll() is None:
                stop_process(proc)

    def check(self, cancel=None):
        code, out, err = self._run(['-ver'], None, cancel or threading.Event(), 15)
        if code != 0:
            raise RuntimeError('ExifTool 启动失败：' + err.decode('utf-8', 'replace'))
        self.version = out.decode('utf-8', 'replace').strip()
        if not self.version or not self.version[0].isdigit():
            raise RuntimeError('ExifTool 版本响应无效')
        return self.version

    def read(self, paths, cancel):
        results = {}
        safe = []
        for p in paths:
            # UTF-8 argument file, one absolute file name per line. Reject line injection.
            p = str(Path(p).absolute())
            if any(c in p for c in '\r\n\x00'):
                results[p] = ({}, '路径包含换行或 NUL，无法安全传递给 ExifTool')
            else:
                safe.append(p)
        if not safe:
            return results
        args = ['-q', '-j', '-n', '-G1:4', '-a', '-s', '-struct', '-charset', 'filename=UTF8',
                '-api', 'LargeFileSupport=1', '-@', '-']
        try:
            code, out, err = self._run(args, ('\n'.join(safe) + '\n').encode('utf-8'), cancel)
            parsed = json.loads(out.decode('utf-8-sig'))
            if not isinstance(parsed, list):
                raise ValueError('JSON 顶层不是数组')
            by_path = {os.path.normcase(os.path.abspath(p)): p for p in safe}
            for row in parsed:
                if not isinstance(row, dict):
                    raise ValueError('JSON 文件记录不是对象')
                source = row.get('SourceFile')
                if not isinstance(source, str):
                    raise ValueError('JSON 缺少 SourceFile')
                p = by_path.get(os.path.normcase(os.path.abspath(source)))
                if p is not None:
                    results[p] = (row, '')
            # Non-zero exit without a row-specific diagnostic cannot be declared successful.
            has_specific_error = any(any(k.rsplit(':', 1)[-1] == 'Error' for k in m) for m, _ in results.values())
            global_error = ''
            if code != 0 and not has_specific_error:
                global_error = f'ExifTool 退出码 {code}: {err.decode("utf-8", "replace")[:2000]}'
            elif err.strip():
                # Conservative: stderr not attributed to a file might apply to any row.
                global_error = 'ExifTool stderr: ' + err.decode('utf-8', 'replace')[:2000]
            for p in safe:
                if p not in results:
                    results[p] = ({}, global_error or 'ExifTool 未返回此文件')
                elif global_error:
                    results[p] = (results[p][0], global_error)
        except Cancelled:
            return results
        except (OSError, TimeoutError, ValueError, UnicodeError) as exc:
            for p in safe:
                results[p] = ({}, f'读取或 JSON 解析失败：{exc}')
        return results
