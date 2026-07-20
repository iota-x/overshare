"""Entry point — launches the right app for this OS."""

import sys

if sys.platform.startswith("win"):
    from in_detail.app_win import main
else:
    from in_detail.app import main

if __name__ == "__main__":
    main()
