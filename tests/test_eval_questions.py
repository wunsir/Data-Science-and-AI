from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from finding_jobs.agent import semantic_scope, unsupported_question_reason


QUESTIONS = Path(__file__).with_name("eval_questions.json")
HOLDOUT = Path(__file__).with_name("eval_holdout_questions.json")
EXPECTATIONS = Path(__file__).with_name("eval_expectations.json")


def test_fixed_evaluation_set_has_locked_composition_and_routes() -> None:
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    assert len(cases) == 18
    assert Counter(case["id"][0] for case in cases) == {
        "h": 8,
        "l": 5,
        "c": 3,
        "u": 2,
    }
    assert len({case["id"] for case in cases}) == 18

    for case in cases:
        if case["id"].startswith("u"):
            assert unsupported_question_reason(case["question"])
        else:
            assert semantic_scope(case["question"]) == case["scope"]


def test_holdout_set_is_bounded_and_all_cases_have_expectations() -> None:
    fixed = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    holdout = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    expectations = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))

    assert len(holdout) == 5
    assert len({case["id"] for case in fixed + holdout}) == 23
    assert all(case["id"] in expectations for case in fixed + holdout)
    assert sum(case["expect"].startswith("reject_") for case in holdout) == 1
    for case in holdout:
        if case["expect"].startswith("reject_"):
            assert unsupported_question_reason(case["question"])
        else:
            assert semantic_scope(case["question"]) == case["scope"]
