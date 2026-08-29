from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from finding_jobs.analysis import analyze_database, fit_salary_model
from finding_jobs.visual_data import major_city_salary


class AnalysisTests(unittest.TestCase):
    def _make_database(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE dataset_versions (
                    dataset_version TEXT PRIMARY KEY,
                    scope_label TEXT NOT NULL,
                    built_at TEXT NOT NULL
                );
                INSERT INTO dataset_versions VALUES (
                    'historical-test', '2025年末采集样本', '2026-08-27T00:00:00+00:00'
                );
                CREATE TABLE jobs_analytics (
                    job_key TEXT PRIMARY KEY,
                    data_scope TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT,
                    company TEXT,
                    city TEXT,
                    search_category TEXT,
                    job_category TEXT,
                    salary_raw TEXT,
                    salary_min_monthly REAL,
                    salary_max_monthly REAL,
                    salary_mid_monthly REAL,
                    salary_parse_status TEXT,
                    education TEXT,
                    experience TEXT,
                    company_size TEXT,
                    skills TEXT,
                    observed_at TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT
                );
                """
            )
            rows = []
            categories = ["finance", "product", "operations", "business_analysis", "data"]
            cities = ["北京", "上海", "深圳", "南京"]
            skills = ["python", "sql", "excel", "tableau"]
            for index in range(80):
                base = 8_000 + (index % 10) * 850
                category = categories[index % len(categories)]
                skill = skills[index % len(skills)]
                midpoint = base + (2_000 if skill == "python" else 0) + (1_500 if category == "data" else 0)
                rows.append(
                    (
                        f"job-{index}",
                        "historical",
                        "boss" if index % 2 == 0 else "zlzp",
                        f"职位{index}",
                        f"公司{index % 12}",
                        cities[index % len(cities)],
                        category,
                        category,
                        f"{int(midpoint * 0.8)}-{int(midpoint * 1.2)}元",
                        midpoint * 0.8,
                        midpoint * 1.2,
                        midpoint,
                        "success",
                        "本科" if index % 3 else "硕士",
                        "1-3年" if index % 2 else "3-5年",
                        "100-499人" if index % 2 else "500-999人",
                        json.dumps([skill], ensure_ascii=False),
                        None,
                        None,
                        None,
                    )
                )
            connection.executemany(
                "INSERT INTO jobs_analytics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
            )
            connection.commit()
        finally:
            connection.close()

    def test_model_uses_declared_controls_and_hc3(self) -> None:
        frame = pd.DataFrame(
            {
                "salary_mid_monthly": [8_000 + index * 200 for index in range(30)],
                "source": ["boss" if index % 2 else "zlzp" for index in range(30)],
                "job_category": ["data" if index % 3 else "product" for index in range(30)],
                "city": ["上海" if index % 2 else "北京" for index in range(30)],
                "education": ["本科" if index % 2 else "硕士" for index in range(30)],
                "experience": ["1-3年" if index % 2 else "3-5年" for index in range(30)],
                "company_size": ["100-499人" if index % 2 else "500-999人" for index in range(30)],
                "skills": [json.dumps(["python"] if index % 2 else ["sql"]) for index in range(30)],
            }
        )
        result = fit_salary_model(frame)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["covariance"], "HC3")
        self.assertTrue(result["source_fixed_effects"])
        terms = [item["term"] for item in result["coefficients"]]
        self.assertFalse(any(term.startswith("salary_") for term in terms))
        self.assertIn("predefined_skills", result["controls"])

    def test_major_city_salary_selects_cities_by_sample_size(self) -> None:
        rows = []
        for index, city in enumerate(["上海", "深圳", "北京", "广州", "南京", "杭州"]):
            rows.extend(
                {"city": city, "salary_mid_monthly": 10_000 + index * 1_000}
                for _ in range(36 - index)
            )
        rows.extend(
            {"city": "芜湖", "salary_mid_monthly": 50_000}
            for _ in range(30)
        )

        result = major_city_salary(pd.DataFrame(rows), limit=6)

        self.assertEqual({item["label"] for item in result}, {"上海", "深圳", "北京", "广州", "南京", "杭州"})
        self.assertNotIn("芜湖", {item["label"] for item in result})

    def test_analysis_writes_complete_visual_story(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            database = output / "jobs.sqlite"
            self._make_database(database)
            quality = {"counts": {"raw_rows": 90, "duplicate_rows_removed": 10}}
            summary = analyze_database(database, output, quality_report=quality)

            self.assertEqual(summary["dataset_version"], "historical-test")
            self.assertEqual(summary["coverage"]["unique_jobs"], 80)
            self.assertEqual(len(summary["charts"]), 29)
            self.assertEqual(len(summary["compatibility_charts"]), 11)
            self.assertEqual(summary["regression"]["main"]["status"], "ok")
            self.assertEqual(
                sum(chart["page"] == "macro" for chart in summary["charts"]), 8
            )
            self.assertEqual(
                sum(chart["page"] == "micro" for chart in summary["charts"]), 21
            )
            self.assertEqual(
                sum(chart["kind"] == "image" for chart in summary["charts"]), 21
            )
            self.assertEqual(
                sum(chart["kind"] == "interactive" for chart in summary["charts"]), 8
            )
            self.assertEqual(len({chart["id"] for chart in summary["charts"]}), 29)
            for chart in summary["charts"]:
                if chart["kind"] == "image":
                    self.assertTrue(chart["file"].startswith("charts/"))
                    chart_path = output / chart["file"]
                    self.assertTrue(chart_path.is_file())
                    self.assertIn("<svg", chart_path.read_text(encoding="utf-8"))
                else:
                    self.assertTrue(chart["file"].startswith("chart.html?id="))
            joined_warnings = "".join(summary["warnings"])
            self.assertNotIn("导致", joined_warnings)
            self.assertNotIn("提升了", joined_warnings)


if __name__ == "__main__":
    unittest.main()
