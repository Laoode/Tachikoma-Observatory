"""Lockstep multi-model benchmark orchestration.

Hard requirement (PRD FR-3): scenarios run strictly in suite order; for each
scenario all selected models execute concurrently and the run only advances
once every model has finished that scenario (barrier semantics).

No Reflex imports — progress is reported through an async callback.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from observatory.engine.executor import ExecutionTrace, execute_scenario
from observatory.suite.toolcall15 import Scenario


@dataclass(frozen=True)
class RunEvent:
    """Progress notification from the runner.

    Args:
        kind: run_started | execution_started | execution_finished |
            scenario_finished | run_finished | run_aborted.
        scenario_key: Present for scenario/execution events.
        model_id: Present for execution events.
        trace: Present on execution_finished.
    """

    kind: str
    scenario_key: str = ""
    model_id: str = ""
    trace: ExecutionTrace | None = None


OnEvent = Callable[[RunEvent], Awaitable[None]]


async def run_benchmark(
    client,
    model_ids: list[str],
    scenarios: list[Scenario],
    on_event: OnEvent,
    should_stop: Callable[[], bool] = lambda: False,
) -> bool:
    """Execute the suite for the given models with lockstep barriers.

    Args:
        client: LLMClient (or compatible fake in tests).
        model_ids: Models participating in this run.
        scenarios: Scenarios in execution order.
        on_event: Async callback invoked for every progress event.
        should_stop: Polled between scenarios; True aborts gracefully after
            the current scenario row completes.

    Returns:
        True if the run completed, False if it was aborted.
    """
    await on_event(RunEvent(kind="run_started"))
    for scenario in scenarios:
        if should_stop():
            await on_event(RunEvent(kind="run_aborted"))
            return False
        await asyncio.gather(
            *(
                _execute_one(client, model_id, scenario, on_event)
                for model_id in model_ids
            )
        )
        await on_event(RunEvent(kind="scenario_finished", scenario_key=scenario.key))
    await on_event(RunEvent(kind="run_finished"))
    return True


async def _execute_one(
    client, model_id: str, scenario: Scenario, on_event: OnEvent
) -> None:
    """Run one scenario x model execution and emit start/finish events."""
    await on_event(
        RunEvent(
            kind="execution_started",
            scenario_key=scenario.key,
            model_id=model_id,
        )
    )
    trace = await execute_scenario(client, model_id, scenario)
    await on_event(
        RunEvent(
            kind="execution_finished",
            scenario_key=scenario.key,
            model_id=model_id,
            trace=trace,
        )
    )
