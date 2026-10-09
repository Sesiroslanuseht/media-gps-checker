"""Optional headless entrypoint for automation and diagnostics."""
import argparse
import signal
import threading
from .core import SCOPES, scan
from .exiftool import ExifTool
from .export import export_xlsx


def main():
    parser = argparse.ArgumentParser(description='只读媒体 GPS 检查器')
    parser.add_argument('folder')
    parser.add_argument('--exiftool', default='')
    parser.add_argument('--output', required=True)
    parser.add_argument('--scope', choices=SCOPES, default=SCOPES[0])
    args = parser.parse_args()
    cancel = threading.Event()
    signal.signal(signal.SIGINT, lambda *a: cancel.set())
    reader = ExifTool(args.exiftool)
    reader.check(cancel)
    result = scan(args.folder, reader, cancel, lambda p, d, t: print(f'{p}: {d}/{t}', flush=True), args.scope)
    print(export_xlsx(result, args.output))
    return 130 if result.cancelled else 0

if __name__ == '__main__':
    raise SystemExit(main())
