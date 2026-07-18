"""Suite integrity: the transcription must match METHODOLOGY.md invariants."""

from observatory.scoring.checkers import CHECKERS
from observatory.suite.toolcall15 import (
    CATEGORIES,
    GENERIC_MOCKS,
    SCENARIOS,
    SCENARIOS_BY_KEY,
    SCENARIOS_PER_CATEGORY,
    TOOL_NAMES,
    TOOLS,
)


def test_suite_has_15_scenarios_across_5_categories():
    assert len(SCENARIOS) == 15
    for letter in CATEGORIES:
        in_category = [s for s in SCENARIOS if s.category == letter]
        assert len(in_category) == SCENARIOS_PER_CATEGORY, letter


def test_toolkit_has_12_uniquely_named_tools():
    assert len(TOOLS) == 12
    assert len(TOOL_NAMES) == 12


def test_every_tool_has_a_generic_mock():
    assert set(GENERIC_MOCKS) == set(TOOL_NAMES)


def test_every_scenario_mock_references_a_known_tool():
    for scenario in SCENARIOS:
        for tool_name in scenario.mocks:
            assert tool_name in TOOL_NAMES, f"{scenario.key}: {tool_name}"


def test_every_scenario_has_a_checker():
    assert set(CHECKERS) == set(SCENARIOS_BY_KEY)


def test_scenario_keys_are_ordered_and_unique():
    keys = [s.key for s in SCENARIOS]
    assert keys == sorted(set(keys))


def test_difficulties_are_valid():
    for scenario in SCENARIOS:
        assert scenario.difficulty in ("easy", "medium", "hard"), scenario.key
