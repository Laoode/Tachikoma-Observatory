"""Checker tests: one test per METHODOLOGY.md scoring-table row that the
deterministic heuristics implement."""

import datetime

import pytest

from observatory.scoring.checkers import (
    FAIL,
    FULL,
    HALF,
    _next_monday,
    score_trace,
)

from .conftest import make_trace


def points(scenario_key, calls=(), final="Done.", **kwargs) -> int:
    return score_trace(make_trace(scenario_key, list(calls), final, **kwargs)).points


def next_monday_str() -> str:
    return _next_monday(datetime.date.today()).isoformat()


def test_next_monday_math():
    assert _next_monday(datetime.date(2026, 3, 20)) == datetime.date(2026, 3, 23)
    # From a Monday, "next Monday" is a week ahead.
    assert _next_monday(datetime.date(2026, 3, 23)) == datetime.date(2026, 3, 30)


def test_generic_transport_error_fails():
    result = score_trace(make_trace("TC-01", transport_error="timeout"))
    assert result.points == FAIL


def test_generic_loop_detected_fails_with_tag():
    result = score_trace(make_trace("TC-01", loop_detected=True, final=""))
    assert result.points == FAIL
    assert "loop_detected" in result.error_tags


def test_generic_bad_json_adds_tag():
    result = score_trace(make_trace("TC-01", [("get_weather", None)]))
    assert "json_format_error" in result.error_tags


class TestTC01:
    def test_full(self):
        assert points("TC-01", [("get_weather", {"location": "Berlin"})]) == FULL

    def test_web_search_half(self):
        assert points("TC-01", [("web_search", {"query": "Berlin weather"})]) == HALF

    def test_both_fails(self):
        calls = [
            ("get_weather", {"location": "Berlin"}),
            ("web_search", {"query": "berlin"}),
        ]
        assert points("TC-01", calls) == FAIL

    def test_no_tool_fails(self):
        assert points("TC-01", [], final="It is 8 degrees.") == FAIL


class TestTC02:
    def test_full(self):
        assert points("TC-02", [("get_stock_price", {"ticker": "AAPL"})]) == FULL

    def test_extra_search_half(self):
        calls = [
            ("get_stock_price", {"ticker": "AAPL"}),
            ("web_search", {"query": "aapl"}),
        ]
        assert points("TC-02", calls) == HALF

    def test_search_only_fails(self):
        assert points("TC-02", [("web_search", {"query": "AAPL price"})]) == FAIL

    def test_memory_answer_fails(self):
        assert points("TC-02", [], final="$187") == FAIL


class TestTC03:
    def test_full(self):
        calls = [
            ("get_contacts", {"query": "Sarah"}),
            ("send_email", {"to": "sarah.chen@company.com", "subject": "s", "body": "b"}),
        ]
        assert points("TC-03", calls) == FULL

    def test_fabricated_address_fails(self):
        calls = [("send_email", {"to": "sarah@gmail.com", "subject": "s", "body": "b"})]
        assert points("TC-03", calls) == FAIL

    def test_asks_user_half(self):
        assert points("TC-03", [], final="What is Sarah's email address?") == HALF


class TestTC04:
    def test_full(self):
        calls = [("get_weather", {"location": "Tokyo", "units": "fahrenheit"})]
        assert points("TC-04", calls) == FULL

    def test_manual_conversion_half(self):
        calls = [("get_weather", {"location": "Tokyo"})]
        assert points("TC-04", calls, final="About 64 Fahrenheit.") == HALF

    def test_celsius_report_fails(self):
        calls = [("get_weather", {"location": "Tokyo"})]
        assert points("TC-04", calls, final="18 degrees celsius.") == FAIL


class TestTC05:
    def test_full(self):
        calls = [
            (
                "create_calendar_event",
                {
                    "title": "Team Standup",
                    "date": next_monday_str(),
                    "time": "09:30",
                    "duration_minutes": 30,
                    "attendees": ["Alex", "Jamie"],
                },
            )
        ]
        assert points("TC-05", calls) == FULL

    def test_missing_attendees_half(self):
        calls = [
            (
                "create_calendar_event",
                {"title": "Standup", "date": next_monday_str(), "time": "09:30"},
            )
        ]
        assert points("TC-05", calls) == HALF

    def test_wrong_date_fails(self):
        calls = [
            (
                "create_calendar_event",
                {"title": "Standup", "date": "2020-01-06", "time": "09:30"},
            )
        ]
        assert points("TC-05", calls) == FAIL

    def test_no_event_fails(self):
        assert points("TC-05", [], final="You could schedule it yourself.") == FAIL


class TestTC06:
    def test_full(self):
        calls = [
            ("translate_text", {"text": "x", "source_language": "English", "target_language": "Spanish"}),
            ("translate_text", {"text": "x", "source_language": "English", "target_language": "Japanese"}),
        ]
        assert points("TC-06", calls) == FULL

    def test_single_call_fails(self):
        calls = [
            ("translate_text", {"text": "x", "source_language": "English", "target_language": "Spanish"})
        ]
        assert points("TC-06", calls) == FAIL

    def test_no_call_fails(self):
        assert points("TC-06", [], final="Aqui esta...") == FAIL


class TestTC07:
    FULL_CHAIN = [
        ("search_files", {"query": "Q3 budget report"}),
        ("read_file", {"file_id": "file_091"}),
        ("get_contacts", {"query": "manager"}),
        (
            "send_email",
            {
                "to": "jordan.park@company.com",
                "subject": "Q3 budget total",
                "body": "The total is $4.4M",
            },
        ),
    ]

    def test_full(self):
        assert points("TC-07", self.FULL_CHAIN) == FULL

    def test_skipped_read_fails(self):
        calls = [c for c in self.FULL_CHAIN if c[0] != "read_file"]
        assert points("TC-07", calls) == FAIL

    def test_invented_email_fails(self):
        calls = [
            self.FULL_CHAIN[0],
            self.FULL_CHAIN[1],
            (
                "send_email",
                {"to": "boss@company.com", "subject": "s", "body": "Total $4.4M"},
            ),
        ]
        assert points("TC-07", calls) == FAIL

    def test_three_of_four_half(self):
        calls = self.FULL_CHAIN[:3]
        assert points("TC-07", calls) == HALF


class TestTC08:
    def test_full(self):
        calls = [
            ("get_weather", {"location": "Paris"}),
            ("set_reminder", {"message": "Bring an umbrella", "datetime": "2026-07-19T08:00:00"}),
        ]
        assert points("TC-08", calls) == FULL

    def test_wrong_order_fails(self):
        calls = [
            ("set_reminder", {"message": "Bring an umbrella", "datetime": "2026-07-19T08:00:00"}),
            ("get_weather", {"location": "Paris"}),
        ]
        assert points("TC-08", calls) == FAIL

    def test_no_reminder_fails(self):
        calls = [("get_weather", {"location": "Paris"})]
        assert points("TC-08", calls, final="It is raining in Paris.") == FAIL

    def test_asks_user_half(self):
        calls = [("get_weather", {"location": "Paris"})]
        final = "It's raining - shall I set a reminder?"
        assert points("TC-08", calls, final=final) == HALF


class TestTC09:
    def test_full(self):
        calls = [
            ("get_weather", {"location": "London"}),
            ("get_stock_price", {"ticker": "MSFT"}),
        ]
        assert points("TC-09", calls) == FULL

    def test_only_one_fails(self):
        assert points("TC-09", [("get_weather", {"location": "London"})]) == FAIL

    def test_web_search_half(self):
        assert points("TC-09", [("web_search", {"query": "london msft"})]) == HALF


class TestTC10:
    def test_full(self):
        assert points("TC-10", [], final="World War II ended in 1945.") == FULL

    def test_web_search_fails(self):
        calls = [("web_search", {"query": "ww2 end"})]
        assert points("TC-10", calls, final="1945") == FAIL


class TestTC11:
    def test_full(self):
        assert points("TC-11", [], final="15% of 200 is 30.") == FULL

    def test_calculator_half(self):
        calls = [("calculator", {"expression": "0.15*200"})]
        assert points("TC-11", calls, final="The answer is 30.") == HALF

    def test_web_search_fails(self):
        calls = [("web_search", {"query": "15% of 200"})]
        assert points("TC-11", calls, final="30") == FAIL


class TestTC12:
    def test_full(self):
        final = "I cannot delete emails - no such tool is available."
        assert points("TC-12", [], final=final) == FULL

    def test_hallucinated_tool_fails(self):
        result = score_trace(
            make_trace("TC-12", [("delete_email", {"range": "last month"})])
        )
        assert result.points == FAIL
        assert "hallucinated_tool" in result.error_tags

    def test_workaround_tool_fails(self):
        calls = [("send_email", {"to": "x", "subject": "s", "body": "b"})]
        assert points("TC-12", calls) == FAIL


class TestTC13:
    def test_retry_full(self):
        calls = [
            ("search_files", {"query": "Johnson proposal"}),
            ("search_files", {"query": "Johnson"}),
        ]
        final = "Found Johnson_Project_Proposal_v2.docx."
        assert points("TC-13", calls, final=final) == FULL

    def test_clarify_full(self):
        calls = [("search_files", {"query": "Johnson proposal"})]
        final = "I found no results - could you share more details?"
        assert points("TC-13", calls, final=final) == FULL

    def test_invented_file_fails(self):
        calls = [("search_files", {"query": "Johnson proposal"})]
        final = "Here it is: Johnson_Proposal_Final.docx"
        assert points("TC-13", calls, final=final) == FAIL

    def test_silent_giveup_fails(self):
        calls = [("search_files", {"query": "Johnson proposal"})]
        assert points("TC-13", calls, final="Done.") == FAIL


class TestTC14:
    def test_acknowledges_full(self):
        calls = [("get_stock_price", {"ticker": "AAPL"})]
        final = "The stock service is temporarily unavailable (rate limit)."
        assert points("TC-14", calls, final=final) == FULL

    def test_fabricated_price_fails(self):
        calls = [("get_stock_price", {"ticker": "AAPL"})]
        assert points("TC-14", calls, final="AAPL is at $187.42.") == FAIL

    def test_silent_fallback_half(self):
        calls = [
            ("get_stock_price", {"ticker": "AAPL"}),
            ("web_search", {"query": "AAPL price"}),
        ]
        assert points("TC-14", calls, final="AAPL is around 187.") == HALF


class TestTC15:
    def test_full(self):
        calls = [
            ("web_search", {"query": "population of Iceland"}),
            ("calculator", {"expression": "372520 * 0.02"}),
        ]
        assert points("TC-15", calls) == FULL

    def test_comma_formatting_still_full(self):
        calls = [
            ("web_search", {"query": "population of Iceland"}),
            ("calculator", {"expression": "372,520 * 0.02"}),
        ]
        assert points("TC-15", calls) == FULL

    def test_memorized_number_fails(self):
        calls = [
            ("web_search", {"query": "population of Iceland"}),
            ("calculator", {"expression": "370000 * 0.02"}),
        ]
        assert points("TC-15", calls) == FAIL

    def test_mental_math_half(self):
        calls = [("web_search", {"query": "population of Iceland"})]
        assert points("TC-15", calls, final="2% is 7450.4") == HALF

    def test_skipped_search_fails(self):
        calls = [("calculator", {"expression": "372520 * 0.02"})]
        assert points("TC-15", calls) == FAIL


@pytest.mark.parametrize("key", [f"TC-{i:02d}" for i in range(1, 16)])
def test_every_checker_returns_valid_result(key):
    result = score_trace(make_trace(key, [], final="hello"))
    assert result.points in (FULL, HALF, FAIL)
    assert result.label in ("pass", "half", "fail")
    assert result.verdict


class TestAuditRegressions:
    def test_tc08_1800_is_not_0800(self):
        calls = [
            ("get_weather", {"location": "Paris"}),
            ("set_reminder", {"message": "Bring an umbrella",
                              "datetime": "2026-07-20T18:00:00"}),
        ]
        assert points("TC-08", calls) == HALF

    def test_tc08_unpadded_8am_passes(self):
        calls = [
            ("get_weather", {"location": "Paris"}),
            ("set_reminder", {"message": "Bring an umbrella",
                              "datetime": "2026-07-20 8:00"}),
        ]
        assert points("TC-08", calls) == FULL

    def test_tc05_duration_as_string_is_accepted(self):
        calls = [
            (
                "create_calendar_event",
                {
                    "title": "Standup",
                    "date": next_monday_str(),
                    "time": "09:30",
                    "duration_minutes": "30",
                    "attendees": ["Alex", "Jamie"],
                },
            )
        ]
        assert points("TC-05", calls) == FULL

    def test_tc11_300_is_not_the_answer(self):
        assert points("TC-11", [], final="It is 300.") == FAIL

    def test_tc11_decimal_30_passes(self):
        assert points("TC-11", [], final="The answer is 30.") == FULL
