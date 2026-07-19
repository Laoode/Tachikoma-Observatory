"""Single scenario x model execution: the mocked-tool conversation loop.

No Reflex imports here — this module must stay UI-agnostic (PRD section 8).
"""

import asyncio
import datetime
import json
import time
from dataclasses import dataclass, field

from observatory.suite.toolcall15 import (
    GENERIC_MOCKS,
    TOOL_NAMES,
    TOOLS,
    Scenario,
    calculator_result,
    system_prompt_with_context,
)

MAX_TURNS = 8
EXECUTION_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call emitted by the model.

    Args:
        turn: 1-based assistant turn index the call appeared in.
        name: Function name the model requested.
        arguments_raw: Raw JSON string of arguments as sent by the model.
        arguments: Parsed arguments, or None when parsing failed.
        is_known_tool: Whether the name is in the 12-tool toolkit.
        mock_result: The mocked result injected back into the conversation.
    """

    turn: int
    name: str
    arguments_raw: str
    arguments: dict | None
    is_known_tool: bool
    mock_result: dict


@dataclass(frozen=True)
class TraceEvent:
    """One timeline entry for the UI trace view.

    Args:
        seq: Order within the execution.
        kind: user_prompt | assistant_text | tool_call | tool_result |
            final_answer | error.
        title: Short label (tool name, "User Prompt", ...).
        payload: Structured detail for the expandable view.
        is_ok: False when this entry represents a failure.
        error_text: Present when is_ok is False.
        ts: Unix timestamp.
    """

    seq: int
    kind: str
    title: str
    payload: dict
    is_ok: bool
    error_text: str
    ts: float


@dataclass
class ExecutionTrace:
    """Full record of one scenario x model execution."""

    scenario_key: str
    model_id: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    events: list[TraceEvent] = field(default_factory=list)
    final_answer: str = ""
    turn_count: int = 0
    loop_detected: bool = False
    transport_error: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens

    def calls_of(self, name: str) -> list[ToolCallRecord]:
        """All calls to a given tool, in order."""
        return [c for c in self.tool_calls if c.name == name]

    def called_names(self) -> list[str]:
        """Tool names in call order (with repeats)."""
        return [c.name for c in self.tool_calls]

    def to_json(self) -> dict:
        """Serialize for DB storage / UI rendering."""
        return {
            "scenario_key": self.scenario_key,
            "model_id": self.model_id,
            "final_answer": self.final_answer,
            "turn_count": self.turn_count,
            "loop_detected": self.loop_detected,
            "transport_error": self.transport_error,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "tool_calls": [
                {
                    "turn": c.turn,
                    "name": c.name,
                    "arguments_raw": c.arguments_raw,
                    "is_known_tool": c.is_known_tool,
                    "mock_result": c.mock_result,
                }
                for c in self.tool_calls
            ],
            "events": [
                {
                    "seq": e.seq,
                    "kind": e.kind,
                    "title": e.title,
                    "payload": e.payload,
                    "is_ok": e.is_ok,
                    "error_text": e.error_text,
                    "ts": e.ts,
                }
                for e in self.events
            ],
        }


class _MockDispenser:
    """Serves mocked tool results for one execution, consuming scenario queues."""

    def __init__(self, scenario: Scenario):
        """Copy the scenario's mock queues so executions never share state.

        Args:
            scenario: The scenario whose mocks to serve.
        """
        self._queues = {name: list(queue) for name, queue in scenario.mocks.items()}

    def next_result(self, tool_name: str, arguments: dict | None) -> dict:
        """Mocked result for a tool call.

        Args:
            tool_name: The tool the model called.
            arguments: Parsed call arguments (None when JSON parsing failed).

        Returns:
            Next queued response (exhausted queues repeat the last entry);
            generic fallback for unscripted tools (the calculator evaluates
            its expression for real); an error payload for unknown tools.
        """
        queue = self._queues.get(tool_name)
        if queue:
            return queue.pop(0) if len(queue) > 1 else queue[0]
        if tool_name == "calculator":
            return calculator_result(str((arguments or {}).get("expression", "")))
        if tool_name in GENERIC_MOCKS:
            return GENERIC_MOCKS[tool_name]
        return {"error": f"Unknown tool: {tool_name}"}


async def execute_scenario(
    client, model_id: str, scenario: Scenario
) -> ExecutionTrace:
    """Run one scenario against one model with mocked tools.

    Args:
        client: LLMClient (or any object with a compatible async `chat`).
        model_id: Model to benchmark.
        scenario: Scenario to execute.

    Returns:
        The full execution trace. Transport errors and timeouts are recorded
        on the trace, never raised.
    """
    trace = ExecutionTrace(scenario_key=scenario.key, model_id=model_id)
    try:
        await asyncio.wait_for(
            _run_conversation(client, model_id, scenario, trace),
            timeout=EXECUTION_TIMEOUT_S,
        )
    except TimeoutError:
        trace.transport_error = f"Execution timed out after {EXECUTION_TIMEOUT_S:.0f}s"
    except Exception as exc:
        trace.transport_error = f"{type(exc).__name__}: {exc}"
    if trace.transport_error:
        _add_event(trace, "error", "Execution Error", {}, False, trace.transport_error)
    return trace


async def _run_conversation(
    client, model_id: str, scenario: Scenario, trace: ExecutionTrace
) -> None:
    """Drive the tool-call loop until a final answer or the turn cap."""
    dispenser = _MockDispenser(scenario)
    messages: list[dict] = [
        {
            "role": "system",
            "content": system_prompt_with_context(datetime.datetime.now()),
        },
        {"role": "user", "content": scenario.user_message},
    ]
    _add_event(
        trace, "user_prompt", "User Prompt", {"text": scenario.user_message}, True, ""
    )

    for turn in range(1, MAX_TURNS + 1):
        result = await client.chat(model_id, messages, TOOLS)
        trace.turn_count = turn
        trace.prompt_tokens += result.prompt_tokens
        trace.completion_tokens += result.completion_tokens
        trace.latency_ms += result.latency_ms

        if not result.tool_calls:
            trace.final_answer = result.message.get("content") or ""
            _add_event(
                trace,
                "final_answer",
                "Final Answer",
                {"text": trace.final_answer},
                True,
                "",
            )
            return

        messages.append(result.message)
        for call in result.tool_calls:
            record = _record_tool_call(trace, call, dispenser)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(record.mock_result),
                }
            )

    trace.loop_detected = True
    _add_event(
        trace,
        "error",
        "Loop Detected",
        {},
        False,
        f"No final answer within {MAX_TURNS} turns",
    )


def _record_tool_call(
    trace: ExecutionTrace, call: dict, dispenser: _MockDispenser
) -> ToolCallRecord:
    """Parse, mock, and log one tool call from an assistant message."""
    function = call.get("function", {})
    name = function.get("name", "")
    arguments_raw = function.get("arguments", "")
    try:
        arguments = json.loads(arguments_raw) if arguments_raw else {}
        parse_error = ""
    except json.JSONDecodeError as exc:
        arguments = None
        parse_error = f"Invalid JSON arguments: {exc}"

    is_known = name in TOOL_NAMES
    mock_result = dispenser.next_result(name, arguments)
    record = ToolCallRecord(
        turn=trace.turn_count,
        name=name,
        arguments_raw=arguments_raw,
        arguments=arguments,
        is_known_tool=is_known,
        mock_result=mock_result,
    )
    trace.tool_calls.append(record)

    error_text = parse_error if parse_error else (
        "" if is_known else f"Unknown tool: {name}"
    )
    _add_event(
        trace,
        "tool_call",
        name or "(unnamed tool)",
        {"arguments": arguments if arguments is not None else arguments_raw},
        not error_text,
        error_text,
    )
    _add_event(trace, "tool_result", name, {"result": mock_result}, True, "")
    return record


def _add_event(
    trace: ExecutionTrace,
    kind: str,
    title: str,
    payload: dict,
    is_ok: bool,
    error_text: str,
) -> None:
    """Append a timeline event to the trace."""
    trace.events.append(
        TraceEvent(
            seq=len(trace.events),
            kind=kind,
            title=title,
            payload=payload,
            is_ok=is_ok,
            error_text=error_text,
            ts=time.time(),
        )
    )
