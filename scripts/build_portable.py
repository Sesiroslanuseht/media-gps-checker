"""Assemble official Windows binaries + Windows wheels. Run on Linux or Windows.
First download the inputs listed in WINDOWS_PORTABLE_BUILD.md; compile launcher with Zig 0.13.0.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
RUNTIME = OUT / '_runtime'
RUNTIME.mkdir()
with zipfile.ZipFile(DOWNLOADS / 'python-3.12.10-embed-amd64.zip') as z:
    z.extractall(RUNTIME)
site = RUNTIME / 'Lib' / 'site-packages'
site.mkdir(parents=True)
for filename in ('PySide6_Essentials-6.8.3-cp39-abi3-win_amd64.whl', 'shiboken6-6.8.3-cp39-abi3-win_amd64.whl', 'openpyxl-3.1.5-py2.py3-none-any.whl', 'et_xmlfile-2.0.0-py3-none-any.whl'):
    with zipfile.ZipFile(DOWNLOADS / filename) as z:
        z.extractall(site)
(RUNTIME / 'python312._pth').write_text('python312.zip\n.\nLib\\site-packages\n..\nimport site\n', encoding='utf-8')
with zipfile.ZipFile(DOWNLOADS / 'exiftool-13.59_64.zip') as z:
    for info in z.infolist():
        relative = Path(*Path(info.filename).parts[1:])
        if not relative.parts:
            continue
        dest = OUT / 'exiftool' / relative
        if info.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))
(OUT / 'exiftool' / 'exiftool(-k).exe').rename(OUT / 'exiftool' / 'exiftool.exe')
for name in ('media_gps', 'scripts', 'tests', '.github'):
    shutil.copytree(ROOT / name, OUT / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for pattern in ('*.py', '*.md', '*.txt', 'LICENSE'):
    for path in ROOT.glob(pattern):
        if path.name != 'SHA256SUMS.txt':
            shutil.copy2(path, OUT / path.name)
subprocess.run([sys.executable, '-m', 'ziglang', 'cc', '-target', 'x86_64-windows-gnu', '-O2', '-municode', '-Wl,--subsystem,windows', str(ROOT / 'scripts' / 'windows_launcher.c'), '-o', str(OUT / 'MediaGPSChecker.exe')], check=True)
# Debug symbols are unnecessary for running the launcher and expose build paths.
(OUT / 'MediaGPSChecker.pdb').unlink(missing_ok=True)
(OUT / '启动诊断.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\n_runtime\\python.exe -B run_gui.py\r\npause\r\n', encoding='ascii')
inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DOWNLOADS.iterdir() if p.suffix in ('.whl', '.zip')}
(OUT / 'build-inputs-sha256.json').write_text(json.dumps(inputs, indent=2), encoding='utf-8')
print(OUT)
