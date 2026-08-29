from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from finding_jobs.pipeline import build_database, parse_salary
from finding_jobs.taxonomy import classify_job, extract_skills, primary_city


class SalaryParsingTests(unittest.TestCase):
    def test_supported_monthly_equivalents(self) -> None:
        cases = {
            "6-8K": (6_000.0, 8_000.0, 7_000.0),
            "1-1.6万·13薪": (10_833.333333333332, 17_333.333333333332, 14_083.333333333332),
            "8千-1.2万·14薪": (9_333.333333333334, 14_000.0, 11_666.666666666668),
            "20-35万/年": (16_666.666666666668, 29_166.666666666668, 22_916.666666666668),
            "5000-8000元/月": (5_000.0, 8_000.0, 6_500.0),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                parsed = parse_salary(raw)
                self.assertEqual(parsed.status, "success")
                self.assertAlmostEqual(parsed.minimum or 0, expected[0])
                self.assertAlmostEqual(parsed.maximum or 0, expected[1])
                self.assertAlmostEqual(parsed.midpoint or 0, expected[2])

    def test_unsupported_values_are_not_imputed(self) -> None:
        for raw, expected_status, expected_reason in (
            ("面议", "unsupported", "negotiable"),
            ("200-300元/天", "unsupported", "unsupported_daily"),
            ("8千及以下", "unsupported", "one_sided_bound"),
            (None, "missing", "missing"),
        ):
            with self.subTest(raw=raw):
                parsed = parse_salary(raw)
                self.assertEqual(parsed.status, expected_status)
                self.assertEqual(parsed.reason, expected_reason)
                self.assertIsNone(parsed.midpoint)

    def test_implicit_period_ambiguity_is_not_silently_monthly(self) -> None:
        for raw, reason in (
            ("70-100万", "implicit_period_high_wan"),
            ("120-150元", "implicit_period_low_rmb"),
        ):
            with self.subTest(raw=raw):
                parsed = parse_salary(raw)
                self.assertEqual(parsed.status, "ambiguous")
                self.assertEqual(parsed.reason, reason)
                self.assertIsNone(parsed.midpoint)
                self.assertIsNotNone(parsed.minimum_raw)
                self.assertIsNotNone(parsed.maximum_raw)

    def test_explicit_or_platform_monthly_extremes_remain_parseable(self) -> None:
        explicit = parse_salary("250000-260000元/月")
        platform_k = parse_salary("100-200K")
        self.assertEqual(explicit.status, "success")
        self.assertEqual(explicit.period, "monthly")
        self.assertEqual(platform_k.status, "success")
        self.assertEqual(platform_k.period, "monthly")


class TaxonomyTests(unittest.TestCase):
    def test_fixed_category_and_skill_rules(self) -> None:
        self.assertEqual(classify_job("高级商业分析师", "数据分析"), "business_analysis")
        self.assertEqual(classify_job("区域负责人", "银行"), "finance")
        self.assertEqual(classify_job("产品经理"), "product")
        self.assertEqual(extract_skills(["熟练使用 Python、SQL 与 Tableau"]), ["python", "sql", "tableau"])
        self.assertEqual(primary_city("上海·浦东·张江"), "上海")

    def test_bumper_title_is_not_misclassified_as_insurance(self) -> None:
        self.assertEqual(classify_job("保险杠系统工程师", "保险"), "other")
        self.assertEqual(classify_job("保险杠公司财务经理", "保险"), "finance")


class DatabaseBuildTests(unittest.TestCase):
    def _make_fixture(self, root: Path) -> None:
        (root / "boss").mkdir(parents=True)
        (root / "qianchengwuyou" / "data").mkdir(parents=True)
        (root / "zlzp" / "上海").mkdir(parents=True)

        boss = pd.DataFrame(
            [
                {
                    "职位": "数据分析师",
                    "公司": "甲公司",
                    "薪资": "10-15K",
                    "地区": "上海",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "100-499人",
                    "行业": "互联网",
                    "福利标签": "",
                    "技能标签": "Python,SQL",
                    "职位描述": "短描述",
                    "job_id": "boss-1",
                },
                {
                    "职位": "数据分析师",
                    "公司": "甲公司",
                    "薪资": "10-15K",
                    "地区": "上海",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "100-499人",
                    "行业": "互联网",
                    "福利标签": "五险一金",
                    "技能标签": "Python,SQL,Tableau",
                    "职位描述": "更完整的岗位描述" * 20,
                    "job_id": "boss-1",
                },
                {
                    "职位": "运营专员",
                    "公司": "乙公司",
                    "薪资": "面议",
                    "地区": "南京",
                    "经验": "不限",
                    "学历": "大专",
                    "公司规模": "20-99人",
                    "行业": "零售",
                    "福利标签": "",
                    "技能标签": "用户运营",
                    "职位描述": "",
                    "job_id": "",
                },
                {
                    "职位": "运营专员",
                    "公司": "乙公司",
                    "薪资": "面议",
                    "地区": "南京",
                    "经验": "不限",
                    "学历": "大专",
                    "公司规模": "20-99人",
                    "行业": "零售",
                    "福利标签": "",
                    "技能标签": "用户运营",
                    "职位描述": "",
                    "job_id": "",
                },
            ]
        )
        boss.to_excel(root / "boss" / "joblist_1.xlsx", index=False)
        boss_bridge_and_ambiguity = pd.DataFrame(
            [
                {
                    "职位": "数据分析师",
                    "公司": "甲公司",
                    "薪资": "10-15K",
                    "地区": "上海",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "100-499人",
                    "行业": "互联网",
                    "福利标签": "",
                    "技能标签": "Python,SQL",
                    "职位描述": "无ID但指纹唯一命中boss-1",
                    "job_id": "",
                },
                {
                    "职位": "分析师",
                    "公司": "歧义公司",
                    "薪资": "9-12K",
                    "地区": "北京",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "20-99人",
                    "行业": "咨询",
                    "福利标签": "",
                    "技能标签": "SQL",
                    "职位描述": "",
                    "job_id": "amb-1",
                },
                {
                    "职位": "分析师",
                    "公司": "歧义公司",
                    "薪资": "9-12K",
                    "地区": "北京",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "20-99人",
                    "行业": "咨询",
                    "福利标签": "",
                    "技能标签": "SQL",
                    "职位描述": "",
                    "job_id": "amb-2",
                },
                {
                    "职位": "分析师",
                    "公司": "歧义公司",
                    "薪资": "9-12K",
                    "地区": "北京",
                    "经验": "1-3年",
                    "学历": "本科",
                    "公司规模": "20-99人",
                    "行业": "咨询",
                    "福利标签": "",
                    "技能标签": "SQL",
                    "职位描述": "无ID且同时命中两个不同ID，因此不能猜测合并",
                    "job_id": "",
                },
            ]
        )
        boss_bridge_and_ambiguity.to_excel(root / "boss" / "joblist_2.xlsx", index=False)

        qcwy = pd.DataFrame(
            [
                {
                    "职位": "产品经理",
                    "薪资": "1-1.6万·13薪",
                    "城市": "深圳·南山区",
                    "经验": "3年及以上",
                    "学历": "本科",
                    "公司": "丙公司",
                    "公司领域": "软件",
                    "公司性质": "民营",
                    "公司规模": "100-500人",
                    "福利标签": "",
                    "技能标签": "需求分析;产品规划",
                    "岗位描述": "",
                },
                {
                    "职位": "产品经理",
                    "薪资": "1-1.6万·13薪",
                    "城市": "深圳·南山区",
                    "经验": "3年及以上",
                    "学历": "本科",
                    "公司": "丙公司",
                    "公司领域": "软件",
                    "公司性质": "民营",
                    "公司规模": "100-500人",
                    "福利标签": "",
                    "技能标签": "需求分析;产品规划",
                    "岗位描述": "",
                },
            ]
        )
        qcwy.to_csv(root / "qianchengwuyou" / "data" / "产品.csv", index=False, encoding="utf-8-sig")

        zlzp = pd.DataFrame(
            [
                {
                    "岗位名称": "商业分析师",
                    "公司名称": "丁公司",
                    "岗位薪资": "20-35万/年",
                    "岗位要求": "3-5年,本科",
                    "公司位置": "上海·徐汇·漕河泾",
                    "技术要求": "SQL,统计分析",
                    "企业信息": "民营,100-299人,咨询",
                },
                {
                    "岗位名称": "财务实习生",
                    "公司名称": "戊公司",
                    "岗位薪资": "200-300元/天",
                    "岗位要求": "经验不限,本科",
                    "公司位置": "上海",
                    "技术要求": "Excel",
                    "企业信息": "国企,1000-9999人,金融",
                },
            ]
        )
        zlzp.to_excel(root / "zlzp" / "上海" / "商业分析_上海.xlsx", index=False)

    def test_build_reconciles_rows_and_preserves_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._make_fixture(root)
            database = root / "out" / "jobs.sqlite"
            report = build_database(root, database)

            self.assertEqual(report["counts"]["raw_rows"], 12)
            self.assertEqual(report["counts"]["unique_jobs"], 8)
            self.assertEqual(report["counts"]["duplicate_rows_removed"], 4)
            self.assertEqual(report["deduplication"]["no_id_rows_bridged_to_id_group"], 1)
            self.assertEqual(report["deduplication"]["ambiguous_no_id_rows_not_bridged"], 1)
            self.assertFalse(report["salary_policy"]["imputation"])

            connection = sqlite3.connect(database)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                    )
                }
                self.assertTrue({"jobs", "provenance", "crawl_runs", "dataset_versions", "jobs_analytics"} <= tables)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM provenance").fetchone()[0], 12)
                selected = connection.execute(
                    "SELECT description FROM jobs WHERE source_job_id = 'boss-1'"
                ).fetchone()[0]
                self.assertGreater(len(selected), 100)
                bridged_rows = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM provenance
                    WHERE job_key = (SELECT job_key FROM jobs WHERE source_job_id = 'boss-1')
                    """
                ).fetchone()[0]
                self.assertEqual(bridged_rows, 3)
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM jobs WHERE company = '歧义公司'"
                    ).fetchone()[0],
                    3,
                )
                unsupported = connection.execute(
                    "SELECT salary_mid_monthly, salary_parse_status, salary_parse_reason, salary_period "
                    "FROM jobs WHERE salary_raw LIKE '%/天'"
                ).fetchone()
                self.assertEqual(unsupported, (None, "unsupported", "unsupported_daily", "daily"))
                annual = connection.execute(
                    "SELECT salary_period, salary_min_raw, salary_max_raw, salary_pay_months "
                    "FROM jobs WHERE salary_raw = '20-35万/年'"
                ).fetchone()
                self.assertEqual(annual, ("annual", 200000.0, 350000.0, None))
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM jobs WHERE observed_at IS NOT NULL"
                    ).fetchone()[0],
                    0,
                )
                public_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(jobs_analytics)")
                }
                self.assertNotIn("description", public_columns)
                self.assertNotIn("raw_json", public_columns)
                self.assertIn("description_available", public_columns)
                self.assertIn("salary_period", public_columns)
                self.assertIn("salary_parse_reason", public_columns)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
