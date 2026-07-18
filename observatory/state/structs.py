"""Immutable view models passed from states to components."""

from dataclasses import dataclass, field


def fmt_compact(n: int) -> str:
    """Compact number formatting: 1234567 -> '1.2M'.

    Args:
        n: The number to format.

    Returns:
        Human-compact string with K/M suffix.
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}K"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


@dataclass
class ModelCol:
    """One model column in the matrix / one chart series."""

    model_id: str = ""
    name: str = ""
    color: str = ""


@dataclass
class Cell:
    """One scenario x model result cell."""

    model_id: str = ""
    status: str = "pending"


@dataclass
class Row:
    """One scenario row in the matrix."""

    key: str = ""
    name: str = ""
    category: str = ""
    difficulty: str = ""
    cells: list[Cell] = field(default_factory=list)


@dataclass
class Kpi:
    """KPI card values for the focused model."""

    model_name: str = "—"
    provider: str = "—"
    context: str = "—"
    pass_rate: float = 0.0
    has_data: bool = False
    done: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    prompt_tokens: str = "0"
    completion_tokens: str = "0"
    total_tokens: str = "0"
    avg_tool_calls: str = "0"
    halluc_rate: str = "0%"
    invalid_json_rate: str = "0%"
    loop_rate: str = "0%"


@dataclass
class TraceRow:
    """One node in the tool-call trace timeline."""

    title: str = ""
    kind: str = ""
    is_ok: bool = True
    error_text: str = ""
    time_str: str = ""
    payload: str = ""


@dataclass
class Detail:
    """Scenario Detail panel contents for a selected cell."""

    visible: bool = False
    scenario_key: str = ""
    name: str = ""
    category: str = ""
    difficulty: str = ""
    model_name: str = ""
    status: str = "pending"
    status_label: str = ""
    verdict: str = ""
    user_prompt: str = ""
    expected: str = ""
    final_answer: str = ""
    latency: str = "—"
    tokens: str = "—"
    tool_calls: str = "—"
    points: str = "—"
    events: list[TraceRow] = field(default_factory=list)
    logs_json: str = ""


@dataclass
class LeaderRow:
    """One leaderboard entry."""

    rank: int = 0
    name: str = ""
    color: str = ""
    final_score: float = 0.0
    pass_rate: float = 0.0
    stars: str = ""
    tier: str = ""
    halluc_rate: str = ""
    tokens: str = ""
    latency: str = ""
    run_label: str = ""


@dataclass
class RegistryRow:
    """One model registry row on the settings page."""

    entry_id: int = 0
    model_id: str = ""
    name: str = ""
    color: str = ""
    is_enabled: bool = True
    is_active: bool = True
