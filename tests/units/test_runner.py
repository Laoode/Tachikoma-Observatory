"""Lockstep runner: barrier ordering, events, graceful stop."""

import asyncio

from observatory.engine.runner import RunEvent, run_benchmark
from observatory.suite.toolcall15 import SCENARIOS

from .conftest import assistant_turn


class DelayedClient:
    """Answers instantly for fast models, slowly for slow ones."""

    def __init__(self, delays: dict[str, float]):
        self.delays = delays

    async def chat(self, model, messages, tools):
        await asyncio.sleep(self.delays.get(model, 0))
        return assistant_turn(content="direct answer")


async def _collect(events: list[RunEvent]):
    async def on_event(event: RunEvent):
        events.append(event)

    return on_event


async def test_barrier_all_models_finish_scenario_before_next_starts():
    events: list[RunEvent] = []
    client = DelayedClient({"fast": 0.0, "slow": 0.05})
    scenarios = SCENARIOS[:3]
    completed = await run_benchmark(
        client, ["fast", "slow"], scenarios, await _collect(events)
    )
    assert completed

    # Every execution_started for scenario k+1 must come after the
    # scenario_finished event for scenario k.
    order = [
        (e.kind, e.scenario_key, e.model_id)
        for e in events
        if e.kind in ("execution_started", "scenario_finished")
    ]
    finished_keys: list[str] = []
    for kind, scenario_key, _model in order:
        if kind == "scenario_finished":
            finished_keys.append(scenario_key)
        else:
            # An execution may only start when all prior scenarios finished.
            expected_prior = [s.key for s in scenarios[: scenarios_index(scenario_key)]]
            assert finished_keys == expected_prior, scenario_key


def scenarios_index(key: str) -> int:
    return [s.key for s in SCENARIOS].index(key)


async def test_all_models_execute_every_scenario():
    events: list[RunEvent] = []
    client = DelayedClient({})
    scenarios = SCENARIOS[:2]
    await run_benchmark(client, ["m1", "m2"], scenarios, await _collect(events))
    finished = [
        (e.scenario_key, e.model_id)
        for e in events
        if e.kind == "execution_finished"
    ]
    assert sorted(finished) == sorted(
        (s.key, m) for s in scenarios for m in ("m1", "m2")
    )
    assert all(
        e.trace is not None for e in events if e.kind == "execution_finished"
    )


async def test_stop_flag_aborts_between_scenarios():
    events: list[RunEvent] = []
    client = DelayedClient({})
    stop_after_first = {"stop": False}

    async def on_event(event: RunEvent):
        events.append(event)
        if event.kind == "scenario_finished":
            stop_after_first["stop"] = True

    completed = await run_benchmark(
        client,
        ["m1"],
        SCENARIOS[:3],
        on_event,
        should_stop=lambda: stop_after_first["stop"],
    )
    assert not completed
    assert events[-1].kind == "run_aborted"
    executed = {e.scenario_key for e in events if e.kind == "execution_finished"}
    assert executed == {SCENARIOS[0].key}
