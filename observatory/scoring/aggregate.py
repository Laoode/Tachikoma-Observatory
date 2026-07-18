"""Run-level aggregation: category scores, final score, tiers, error rates."""

from dataclasses import dataclass, field

from observatory.suite.toolcall15 import (
    CATEGORIES,
    MAX_POINTS_PER_SCENARIO,
    SCENARIOS_BY_KEY,
)

TIERS = [
    (90, "Excellent", 5),
    (75, "Good", 4),
    (60, "Adequate", 3),
    (40, "Weak", 2),
    (0, "Poor", 1),
]


@dataclass(frozen=True)
class ExecutionSummary:
    """Minimal scored-execution facts needed for aggregation.

    Args:
        scenario_key: e.g. "TC-01".
        points: 0..2.
        error_tags: Tags from the scorer.
        tool_call_count: Tool calls emitted.
        prompt_tokens: Prompt tokens used.
        completion_tokens: Completion tokens used.
        latency_ms: Total model latency.
    """

    scenario_key: str
    points: int
    error_tags: tuple[str, ...] = ()
    tool_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class ModelAggregate:
    """Aggregated benchmark results for one model in one run."""

    executed: int = 0
    passed: int = 0
    half: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    tier_label: str = ""
    tier_stars: int = 0
    avg_tool_calls: float = 0.0
    hallucinated_rate: float = 0.0
    invalid_json_rate: float = 0.0
    loop_rate: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    avg_latency_ms: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


def aggregate_model(summaries: list[ExecutionSummary]) -> ModelAggregate:
    """Aggregate one model's scored executions.

    Args:
        summaries: Scored executions for a single model in a single run.

    Returns:
        The aggregate. Category scores use METHODOLOGY's points/max formula;
        the final score is the mean over categories that have executions,
        so partial runs stay meaningful.
    """
    agg = ModelAggregate()
    agg.executed = len(summaries)
    if not summaries:
        return agg

    per_category: dict[str, list[int]] = {}
    for s in summaries:
        agg.passed += s.points == 2
        agg.half += s.points == 1
        agg.failed += s.points == 0
        category = SCENARIOS_BY_KEY[s.scenario_key].category
        per_category.setdefault(category, []).append(s.points)
        for tag in s.error_tags:
            agg.error_counts[tag] = agg.error_counts.get(tag, 0) + 1
        agg.prompt_tokens += s.prompt_tokens
        agg.completion_tokens += s.completion_tokens

    points = sum(s.points for s in summaries)
    max_points = len(summaries) * MAX_POINTS_PER_SCENARIO
    agg.pass_rate = round(points / max_points * 100, 1)

    for letter in CATEGORIES:
        scores = per_category.get(letter)
        if scores:
            agg.category_scores[letter] = round(
                sum(scores) / (len(scores) * MAX_POINTS_PER_SCENARIO) * 100, 1
            )
    if agg.category_scores:
        agg.final_score = round(
            sum(agg.category_scores.values()) / len(agg.category_scores), 1
        )
    for threshold, label, stars in TIERS:
        if agg.final_score >= threshold:
            agg.tier_label, agg.tier_stars = label, stars
            break

    agg.avg_tool_calls = round(
        sum(s.tool_call_count for s in summaries) / len(summaries), 1
    )
    agg.hallucinated_rate = _tag_rate(summaries, "hallucinated_tool")
    agg.invalid_json_rate = _tag_rate(summaries, "json_format_error")
    agg.loop_rate = _tag_rate(summaries, "loop_detected")
    agg.total_tokens = agg.prompt_tokens + agg.completion_tokens
    agg.avg_latency_ms = int(sum(s.latency_ms for s in summaries) / len(summaries))
    return agg


def _tag_rate(summaries: list[ExecutionSummary], tag: str) -> float:
    """Percentage of executions carrying a tag."""
    hits = sum(1 for s in summaries if tag in s.error_tags)
    return round(hits / len(summaries) * 100, 1)
