"""Rebuild the deterministic seed database and analysis artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from finding_jobs.pipeline import build_artifacts  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild jobs_seed.sqlite, quality_report.json and the 29-chart analysis story."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository containing boss/, qianchengwuyou/data/ and zlzp/ (default: repository root).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "artifacts",
        help="Artifact destination (default: <repo>/artifacts).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_artifacts(args.repo_root, args.output_dir)
    summary = {
        "database_path": report["database_path"],
        "quality_report_path": report["quality_report_path"],
        "analysis_summary_path": report["analysis_summary_path"],
        "charts_dir": report["charts_dir"],
        "raw_rows": report["quality"]["counts"]["raw_rows"],
        "unique_jobs": report["quality"]["counts"]["unique_jobs"],
        "charts": len(report["analysis"]["charts"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
