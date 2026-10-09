"""Entry for the self-contained Windows distribution. No network or media writes."""
import sys

if __name__ == '__main__':
    try:
        from media_gps.gui import main
        raise SystemExit(main())
    except Exception:
        import traceback
        error = traceback.format_exc()
        if sys.stderr:
            print(error, file=sys.stderr)
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, '启动错误：\n' + error[-2500:], '媒体 GPS 检查器', 0x10)
        raise SystemExit(1)
