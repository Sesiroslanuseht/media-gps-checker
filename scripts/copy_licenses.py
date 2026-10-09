"""Preserve installed distribution metadata (including shipped license texts)."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

out = Path(sys.argv[1]) / 'third-party-licenses'
out.mkdir(exist_ok=True)
for name in ('PySide6-Essentials', 'shiboken6', 'openpyxl', 'et_xmlfile'):
    dist = importlib.metadata.distribution(name)
    for entry in dist.files or []:
        p = Path(str(entry))
        if '.dist-info' in str(p) and ('license' in str(p).lower() or p.name in ('METADATA', 'COPYING', 'NOTICE')):
            source = Path(dist.locate_file(entry))
            target = out / name / p
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
print('Copied installed license and distribution metadata to', out)
