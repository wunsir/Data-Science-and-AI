from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from finding_jobs.agent import semantic_scope, unsupported_question_reason


QUESTIONS = Path(__file__).with_name("eval_questions.json")


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
