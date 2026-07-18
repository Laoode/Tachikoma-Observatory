"""Aggregation math: category scores, final score, tiers, rates."""

from observatory.scoring.aggregate import ExecutionSummary, aggregate_model
from observatory.suite.toolcall15 import SCENARIOS


def summaries_with_points(points_by_key: dict[str, int]) -> list[ExecutionSummary]:
    return [
        ExecutionSummary(
            scenario_key=key,
            points=points,
            tool_call_count=2,
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1000,
        )
        for key, points in points_by_key.items()
    ]


def test_perfect_run_scores_100_and_five_stars():
    agg = aggregate_model(summaries_with_points({s.key: 2 for s in SCENARIOS}))
    assert agg.pass_rate == 100.0
    assert agg.final_score == 100.0
    assert agg.tier_stars == 5
    assert agg.tier_label == "Excellent"
    assert agg.passed == 15
    assert set(agg.category_scores) == {"A", "B", "C", "D", "E"}


def test_methodology_example_math():
    # Category A: 2+1+0 = 3/6 = 50%; all other categories full = 100%.
    points = {s.key: 2 for s in SCENARIOS}
    points["TC-01"], points["TC-02"], points["TC-03"] = 2, 1, 0
    agg = aggregate_model(summaries_with_points(points))
    assert agg.category_scores["A"] == 50.0
    assert agg.final_score == 90.0
    assert agg.tier_stars == 5


def test_partial_run_uses_only_executed_categories():
    agg = aggregate_model(summaries_with_points({"TC-01": 2, "TC-02": 0}))
    assert agg.executed == 2
    assert agg.category_scores == {"A": 50.0}
    assert agg.final_score == 50.0
    assert agg.tier_label == "Weak"


def test_zero_run_is_poor_tier():
    agg = aggregate_model(summaries_with_points({s.key: 0 for s in SCENARIOS}))
    assert agg.final_score == 0.0
    assert agg.tier_stars == 1


def test_error_rates_and_tokens():
    summaries = [
        ExecutionSummary("TC-01", 0, ("hallucinated_tool",), 1, 100, 50, 500),
        ExecutionSummary("TC-02", 2, (), 1, 100, 50, 1500),
        ExecutionSummary("TC-04", 0, ("json_format_error", "loop_detected"), 3, 100, 50, 1000),
        ExecutionSummary("TC-05", 2, (), 1, 100, 50, 1000),
    ]
    agg = aggregate_model(summaries)
    assert agg.hallucinated_rate == 25.0
    assert agg.invalid_json_rate == 25.0
    assert agg.loop_rate == 25.0
    assert agg.total_tokens == 600
    assert agg.avg_latency_ms == 1000
    assert agg.error_counts == {
        "hallucinated_tool": 1,
        "json_format_error": 1,
        "loop_detected": 1,
    }


def test_empty_aggregate_is_safe():
    agg = aggregate_model([])
    assert agg.executed == 0
    assert agg.final_score == 0.0
