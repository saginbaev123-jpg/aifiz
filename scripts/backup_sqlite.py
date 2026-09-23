from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Physics KZ SQLite backup")
    parser.add_argument("--output-dir", default="backups")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = output_dir / f"ai_physics_{stamp}.db"
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    print(target.resolve())


if __name__ == "__main__":
    main()
