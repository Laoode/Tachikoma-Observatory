"""Database tables. Timestamps are stored as ISO-8601 strings for direct
JSON/UI use; SQLite is the only target engine (PRD section 5)."""

import reflex as rx
from sqlmodel import JSON, Column, Field


class ModelEntry(rx.Model, table=True):
    """One benchmarkable model from the LiteLLM proxy."""

    model_id: str = Field(index=True, unique=True)
    display_name: str = ""
    provider: str = ""
    context_window: str = ""
    color: str = ""
    is_enabled: bool = True
    is_active: bool = True
    created_at: str = ""


class BenchRun(rx.Model, table=True):
    """One benchmark run (any number of participating models)."""

    started_at: str = ""
    finished_at: str = ""
    status: str = "running"
    suite_version: str = ""
    model_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class Execution(rx.Model, table=True):
    """One scored scenario x model execution within a run.

    The full conversation record lives in `trace` (executor's to_json shape);
    scalar columns are denormalized for fast aggregation and table rendering.
    """

    run_id: int = Field(index=True)
    model_id: str = Field(index=True)
    scenario_key: str = Field(index=True)
    attempt: int = 1
    status: str = "complete"
    points: int = 0
    verdict: str = ""
    error_tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    turns: int = 0
    tool_call_count: int = 0
    trace: dict = Field(default_factory=dict, sa_column=Column(JSON))
    finished_at: str = ""
