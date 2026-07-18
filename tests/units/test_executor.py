"""Executor conversation-loop behavior with a scripted fake client."""

import json

from observatory.engine.executor import MAX_TURNS, execute_scenario
from observatory.suite.toolcall15 import SCENARIOS_BY_KEY

from .conftest import FakeClient, assistant_turn, tool_call


async def test_direct_final_answer_records_no_tool_calls():
    client = FakeClient([assistant_turn(content="It ended in 1945.")])
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-10"])
    assert trace.final_answer == "It ended in 1945."
    assert trace.tool_calls == []
    assert trace.turn_count == 1
    assert not trace.loop_detected


async def test_tool_call_gets_scenario_mock_injected():
    client = FakeClient(
        [
            assistant_turn(
                tool_calls=[tool_call("get_weather", {"location": "Berlin"})]
            ),
            assistant_turn(content="8°C and overcast in Berlin."),
        ]
    )
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-01"])
    assert trace.tool_calls[0].mock_result["condition"] == "Overcast"
    # The mocked result must have been sent back as a tool message.
    final_request_messages = client.calls[-1][1]
    tool_messages = [m for m in final_request_messages if m.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"])["condition"] == "Overcast"


async def test_mock_queue_advances_then_repeats_last():
    scenario = SCENARIOS_BY_KEY["TC-13"]
    client = FakeClient(
        [
            assistant_turn(
                tool_calls=[tool_call("search_files", {"query": "Johnson proposal"})]
            ),
            assistant_turn(
                tool_calls=[tool_call("search_files", {"query": "Johnson"})]
            ),
            assistant_turn(
                tool_calls=[tool_call("search_files", {"query": "Johnson v2"})]
            ),
            assistant_turn(content="Found Johnson_Project_Proposal_v2.docx"),
        ]
    )
    trace = await execute_scenario(client, "m1", scenario)
    results = [c.mock_result for c in trace.tool_calls]
    assert results[0] == {"results": []}
    assert results[1]["results"][0]["file_id"] == "file_117"
    assert results[2] == results[1]


async def test_unscripted_tool_falls_back_to_generic_mock():
    client = FakeClient(
        [
            assistant_turn(tool_calls=[tool_call("web_search", {"query": "berlin"})]),
            assistant_turn(content="done"),
        ]
    )
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-01"])
    assert "results" in trace.tool_calls[0].mock_result


async def test_invalid_json_arguments_are_recorded_not_raised():
    client = FakeClient(
        [
            assistant_turn(tool_calls=[tool_call("get_weather", "{not json")]),
            assistant_turn(content="done"),
        ]
    )
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-01"])
    assert trace.tool_calls[0].arguments is None
    assert trace.tool_calls[0].arguments_raw == "{not json"


async def test_unknown_tool_name_is_flagged():
    client = FakeClient(
        [
            assistant_turn(tool_calls=[tool_call("delete_email", {"range": "all"})]),
            assistant_turn(content="done"),
        ]
    )
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-12"])
    assert not trace.tool_calls[0].is_known_tool
    assert "error" in trace.tool_calls[0].mock_result


async def test_turn_cap_sets_loop_detected():
    endless = [
        assistant_turn(tool_calls=[tool_call("get_weather", {"location": "Berlin"})])
        for _ in range(MAX_TURNS + 2)
    ]
    client = FakeClient(endless)
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-01"])
    assert trace.loop_detected
    assert trace.turn_count == MAX_TURNS
    assert trace.final_answer == ""


async def test_transport_error_is_captured_on_trace():
    class ExplodingClient:
        async def chat(self, model, messages, tools):
            raise ConnectionError("proxy unreachable")

    trace = await execute_scenario(ExplodingClient(), "m1", SCENARIOS_BY_KEY["TC-01"])
    assert "proxy unreachable" in trace.transport_error


async def test_token_and_latency_accumulation():
    client = FakeClient(
        [
            assistant_turn(
                tool_calls=[tool_call("get_weather", {"location": "Berlin"})]
            ),
            assistant_turn(content="done"),
        ]
    )
    trace = await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-01"])
    assert trace.prompt_tokens == 20
    assert trace.completion_tokens == 10
    assert trace.latency_ms == 10


async def test_system_prompt_includes_current_date():
    client = FakeClient([assistant_turn(content="ok")])
    await execute_scenario(client, "m1", SCENARIOS_BY_KEY["TC-05"])
    system_message = client.calls[0][1][0]
    assert system_message["role"] == "system"
    import datetime

    today = datetime.date.today().isoformat()
    assert f"Current date and time: {datetime.date.today():%A}, {today}" in (
        system_message["content"]
    )
