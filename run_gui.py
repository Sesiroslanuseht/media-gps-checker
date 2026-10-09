import sys
from media_gps.gui import main
if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from scripts.frozen_smoke import smoke
        smoke(sys.argv[2])
    else:
        raise SystemExit(main())
