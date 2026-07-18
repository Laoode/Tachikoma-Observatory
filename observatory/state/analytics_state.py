"""Analytics page state: historical performance and the leaderboard."""

import dataclasses

import reflex as rx

from observatory.models import repo
from observatory.scoring.aggregate import ExecutionSummary, aggregate_model
from observatory.state.structs import LeaderRow, ModelCol, fmt_compact


class AnalyticsState(rx.State):
    """Cross-run history chart and model leaderboard."""

    history_data: list[dict] = []
    history_series: list[ModelCol] = []
    leaderboard: list[LeaderRow] = []
    rank_by: str = "Latest run"

    @rx.event
    def set_rank_by(self, value: str):
        """Toggle leaderboard ranking between latest and best run."""
        self.rank_by = value
        self._rebuild()

    @rx.event
    def load_analytics(self):
        """Page on_load."""
        self._rebuild()

    def _rebuild(self):
        """Aggregate every finished run per model."""
        registry = {e.model_id: e for e in repo.list_models()}
        runs = [r for r in repo.list_runs() if r.status in ("complete", "aborted")]
        runs.reverse()

        per_model_runs: dict[str, list[tuple[str, object]]] = {}
        history: list[dict] = []
        seen_models: dict[str, str] = {}
        for run in runs:
            executions = repo.latest_executions(run.id)
            label = run.started_at[5:16].replace("T", " ")
            point: dict = {"run": label}
            for model_id in run.model_ids:
                summaries = [
                    ExecutionSummary(
                        scenario_key=e.scenario_key,
                        points=e.points,
                        error_tags=tuple(e.error_tags),
                        tool_call_count=e.tool_call_count,
                        prompt_tokens=e.prompt_tokens,
                        completion_tokens=e.completion_tokens,
                        latency_ms=e.latency_ms,
                    )
                    for e in executions
                    if e.model_id == model_id
                ]
                if not summaries:
                    continue
                agg = aggregate_model(summaries)
                entry = registry.get(model_id)
                name = entry.display_name if entry else model_id
                seen_models[model_id] = name
                point[name] = agg.final_score
                per_model_runs.setdefault(model_id, []).append((label, agg))
            if len(point) > 1:
                history.append(point)

        self.history_data = history
        self.history_series = [
            ModelCol(
                model_id=model_id,
                name=name,
                color=registry[model_id].color if model_id in registry else "#4ADE80",
            )
            for model_id, name in seen_models.items()
        ]

        rows: list[LeaderRow] = []
        for model_id, run_aggs in per_model_runs.items():
            if self.rank_by == "Best run":
                label, agg = max(run_aggs, key=lambda x: x[1].final_score)
            else:
                label, agg = run_aggs[-1]
            entry = registry.get(model_id)
            rows.append(
                LeaderRow(
                    name=entry.display_name if entry else model_id,
                    color=entry.color if entry else "#4ADE80",
                    final_score=agg.final_score,
                    pass_rate=agg.pass_rate,
                    stars="★" * agg.tier_stars + "☆" * (5 - agg.tier_stars),
                    tier=agg.tier_label,
                    halluc_rate=f"{agg.hallucinated_rate}%",
                    tokens=fmt_compact(agg.total_tokens),
                    latency=f"{agg.avg_latency_ms / 1000:.1f}s",
                    run_label=label,
                )
            )
        rows.sort(key=lambda r: (-r.final_score, -r.pass_rate))
        self.leaderboard = [
            dataclasses.replace(row, rank=index + 1)
            for index, row in enumerate(rows)
        ]
