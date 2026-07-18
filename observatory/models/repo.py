"""Persistence helpers. All DB access for states and the run controller."""

import datetime

import reflex as rx
from sqlmodel import select

from observatory.engine.executor import ExecutionTrace
from observatory.models.tables import BenchRun, Execution, ModelEntry
from observatory.scoring.checkers import ScoreResult
from observatory.suite.toolcall15 import SUITE_VERSION
from observatory.theme.tokens import model_color


def _now() -> str:
    """Current local time as an ISO string (seconds precision)."""
    return datetime.datetime.now().isoformat(timespec="seconds")


def sync_models(model_ids: list[str]) -> int:
    """Upsert the proxy's model list into the registry.

    Args:
        model_ids: IDs returned by GET /v1/models.

    Returns:
        Number of newly added models. Models missing upstream are marked
        inactive but never deleted (history must keep rendering).
    """
    added = 0
    with rx.session() as session:
        existing = {m.model_id: m for m in session.exec(select(ModelEntry)).all()}
        for index, model_id in enumerate(model_ids):
            if model_id in existing:
                existing[model_id].is_active = True
                session.add(existing[model_id])
            else:
                session.add(
                    ModelEntry(
                        model_id=model_id,
                        display_name=model_id.split("/")[-1],
                        color=model_color(len(existing) + added),
                        created_at=_now(),
                    )
                )
                added += 1
        for model_id, entry in existing.items():
            if model_id not in model_ids:
                entry.is_active = False
                session.add(entry)
        session.commit()
    return added


def list_models(enabled_only: bool = False) -> list[ModelEntry]:
    """Registry entries, active first, in creation order."""
    with rx.session() as session:
        query = select(ModelEntry).order_by(ModelEntry.id)
        entries = list(session.exec(query).all())
    if enabled_only:
        entries = [e for e in entries if e.is_enabled and e.is_active]
    return entries


def set_model_enabled(entry_id: int, is_enabled: bool) -> None:
    """Toggle a model's participation in "all models" runs."""
    with rx.session() as session:
        entry = session.get(ModelEntry, entry_id)
        if entry is not None:
            entry.is_enabled = is_enabled
            session.add(entry)
            session.commit()


def create_run(model_ids: list[str]) -> int:
    """Insert a new running BenchRun and return its ID."""
    with rx.session() as session:
        run = BenchRun(
            started_at=_now(),
            status="running",
            suite_version=SUITE_VERSION,
            model_ids=model_ids,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


def finish_run(run_id: int, status: str) -> None:
    """Mark a run complete/aborted/error with its finish time."""
    with rx.session() as session:
        run = session.get(BenchRun, run_id)
        if run is not None:
            run.status = status
            run.finished_at = _now()
            session.add(run)
            session.commit()


def record_execution(
    run_id: int, trace: ExecutionTrace, score: ScoreResult
) -> None:
    """Persist one scored execution as the next attempt for its cell."""
    with rx.session() as session:
        prior = session.exec(
            select(Execution)
            .where(Execution.run_id == run_id)
            .where(Execution.model_id == trace.model_id)
            .where(Execution.scenario_key == trace.scenario_key)
        ).all()
        session.add(
            Execution(
                run_id=run_id,
                model_id=trace.model_id,
                scenario_key=trace.scenario_key,
                attempt=len(prior) + 1,
                status="error" if trace.transport_error else "complete",
                points=score.points,
                verdict=score.verdict,
                error_tags=list(score.error_tags),
                latency_ms=trace.latency_ms,
                prompt_tokens=trace.prompt_tokens,
                completion_tokens=trace.completion_tokens,
                total_tokens=trace.total_tokens,
                turns=trace.turn_count,
                tool_call_count=len(trace.tool_calls),
                trace=trace.to_json(),
                finished_at=_now(),
            )
        )
        session.commit()


def latest_executions(run_id: int) -> list[Execution]:
    """Latest attempt per (model, scenario) cell for a run."""
    with rx.session() as session:
        rows = session.exec(
            select(Execution)
            .where(Execution.run_id == run_id)
            .order_by(Execution.attempt)
        ).all()
    latest: dict[tuple[str, str], Execution] = {}
    for row in rows:
        latest[(row.model_id, row.scenario_key)] = row
    return list(latest.values())


def list_runs(limit: int = 50) -> list[BenchRun]:
    """Most recent runs, newest first."""
    with rx.session() as session:
        rows = session.exec(
            select(BenchRun).order_by(BenchRun.id.desc()).limit(limit)
        ).all()
    return list(rows)


def latest_run() -> BenchRun | None:
    """The most recent run, if any."""
    runs = list_runs(limit=1)
    return runs[0] if runs else None
