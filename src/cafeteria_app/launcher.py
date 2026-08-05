"""アプリ起動用のコンソールスクリプト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Streamlitアプリを起動する。"""
    app_file = Path(__file__).with_name("app.py")
    command = [sys.executable, "-m", "streamlit", "run", str(app_file)]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
