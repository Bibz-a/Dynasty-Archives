"""
Dev entrypoint.

This file is intentionally runnable via:
- `python -m app.run` (recommended)
- `python app\\run.py` (works when executed directly)
"""

from __future__ import annotations

import os
import sys


def _ensure_project_root_on_path() -> None:
    # When executed as `python app\run.py`, sys.path[0] becomes `...\app`,
    # which breaks `import app`. Add the project root back onto sys.path.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_on_path()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)