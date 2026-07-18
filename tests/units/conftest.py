"""Shared test helpers: fake LLM client and trace builders."""

import json

import pytest

from observatory.engine.executor import ExecutionTrace, ToolCallRecord
from observatory.llm.client import ChatResult


def tool_call(name: str, arguments: dict | str, call_id: str = "call_1") -> dict:
    """Build an OpenAI-shaped tool call dict.

    Args:
        name: Function name.
        arguments: Arguments dict, or a raw string to simulate bad JSON.
        call_id: Tool call ID.

    Returns:
        Tool call dict as it appears on an assistant message.
    """
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": raw},
    }


def assistant_turn(
    content: str | None = None, tool_calls: list[dict] | None = None
) -> ChatResult:
    """Build a scripted assistant reply."""
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return ChatResult(
        message=message, latency_ms=5, prompt_tokens=10, completion_tokens=5
    )


class FakeClient:
    """Scripted chat client: pops one reply per call from a per-model queue."""

    def __init__(self, script: dict[str, list[ChatResult]] | list[ChatResult]):
        """Store the reply script.

        Args:
            script: Per-model reply queues, or a single queue used for the
                only model under test.
        """
        self.script = script
        self.calls: list[tuple[str, list[dict]]] = []

    async def chat(self, model: str, messages: list[dict], tools) -> ChatResult:
        """Return the next scripted reply for the model."""
        self.calls.append((model, list(messages)))
        queue = self.script[model] if isinstance(self.script, dict) else self.script
        if not queue:
            return assistant_turn(content="(script exhausted)")
        return queue.pop(0)


def make_trace(
    scenario_key: str,
    calls: list[tuple[str, dict | None]] = (),
    final: str = "Done.",
    loop_detected: bool = False,
    transport_error: str = "",
) -> ExecutionTrace:
    """Build an ExecutionTrace directly for checker tests.

    Args:
        scenario_key: Scenario under test.
        calls: (tool_name, parsed_arguments) pairs; None arguments simulate
            a JSON parse failure.
        final: The model's final text.
        loop_detected: Simulate hitting the turn cap.
        transport_error: Simulate a transport failure.

    Returns:
        A trace equivalent to what the executor would produce.
    """
    trace = ExecutionTrace(scenario_key=scenario_key, model_id="fake-model")
    from observatory.suite.toolcall15 import TOOL_NAMES

    for index, (name, arguments) in enumerate(calls):
        trace.tool_calls.append(
            ToolCallRecord(
                turn=index + 1,
                name=name,
                arguments_raw="" if arguments is None else json.dumps(arguments),
                arguments=arguments,
                is_known_tool=name in TOOL_NAMES,
                mock_result={},
            )
        )
    trace.final_answer = final
    trace.loop_detected = loop_detected
    trace.transport_error = transport_error
    return trace


@pytest.fixture
def fake_client_factory():
    """Factory fixture for FakeClient."""
    return FakeClient
