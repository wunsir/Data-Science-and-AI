"""Remove known legacy credentials embedded in tracked notebooks.

This is intentionally narrow: it replaces BOSS Cookie header literals containing
known session-cookie markers and OpenAI-style API-key assignments. Other notebook
content is preserved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


COOKIE_MARKERS = ("wt2=", "zp_at=", "__zp_stoken__=")
NOTEBOOKS = (
    Path("boss/boss.ipynb"),
    Path("boss/boss03.ipynb"),
    Path("boss直聘分析.ipynb"),
)
REPLACEMENT = '            "Cookie": os.getenv("BOSS_COOKIE", "")\n'
API_KEY_PATTERN = re.compile(r'API_KEY\s*=\s*["\']sk-[A-Za-z0-9_-]{8,}["\']')
API_KEY_REPLACEMENT = 'API_KEY = os.getenv("OPENAI_API_KEY", "")'


def scrub(path: Path) -> int:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for cell in notebook.get("cells", []):
        source = cell.get("source", [])
        for index, line in enumerate(source):
            if '"Cookie"' in line and any(marker in line for marker in COOKIE_MARKERS):
                source[index] = REPLACEMENT
                changed += 1
            elif API_KEY_PATTERN.search(line):
                source[index] = API_KEY_PATTERN.sub(API_KEY_REPLACEMENT, line)
                changed += 1
    if changed:
        path.write_text(
            json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    return changed


if __name__ == "__main__":
    total = sum(scrub(path) for path in NOTEBOOKS)
    print(f"Scrubbed {total} embedded credential literal(s).")
