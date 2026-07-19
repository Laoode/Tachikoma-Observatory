"""Deterministic per-scenario scorers for ToolCall-15.

One checker per scenario key, each implementing that scenario's scoring table
from METHODOLOGY.md. Points: 2 = full pass, 1 = half credit, 0 = fail.

Subjective table rows ("explains gracefully", "asks user") are approximated
with documented deterministic heuristics (PRD assumption 6); an optional
LLM-judge may refine these later.
"""

import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass

from observatory.engine.executor import ExecutionTrace, ToolCallRecord

FULL = 2
HALF = 1
FAIL = 0

TAG_INVALID_TOOL = "invalid_tool"
TAG_WRONG_PARAMETER = "wrong_parameter"
TAG_HALLUCINATED_TOOL = "hallucinated_tool"
TAG_JSON_FORMAT_ERROR = "json_format_error"
TAG_LOOP_DETECTED = "loop_detected"
TAG_UNNECESSARY_TOOL = "unnecessary_tool"
TAG_MISSED_CALL = "missed_call"
TAG_OTHER = "other"


@dataclass(frozen=True)
class ScoreResult:
    """Outcome of scoring one execution.

    Args:
        points: 2 full pass, 1 half credit, 0 fail.
        verdict: One-line human-readable explanation.
        error_tags: Error taxonomy tags for the breakdown charts.
    """

    points: int
    verdict: str
    error_tags: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """UI status label: pass / half / fail."""
        return {FULL: "pass", HALF: "half", FAIL: "fail"}[self.points]


def _args(call: ToolCallRecord) -> dict:
    """Parsed arguments of a call, empty dict when parsing failed."""
    return call.arguments or {}


def _arg(call: ToolCallRecord, key: str) -> str:
    """Lowercased string value of one argument, empty when absent."""
    return str(_args(call).get(key, "")).lower()


def _final(trace: ExecutionTrace) -> str:
    """Lowercased final answer text."""
    return trace.final_answer.lower()


def _asks_user(trace: ExecutionTrace) -> bool:
    """Heuristic: the final answer asks the user a question."""
    return "?" in trace.final_answer


def _next_monday(today: datetime.date) -> datetime.date:
    """The Monday of next week ("next Monday" from any weekday).

    Args:
        today: Reference date.

    Returns:
        Next Monday strictly after today (7 days ahead when today is Monday).
    """
    return today + datetime.timedelta(days=(7 - today.weekday()) or 7)


def _check_tc01(t: ExecutionTrace) -> ScoreResult:
    """Weather in Berlin: get_weather, not web_search."""
    weather = [c for c in t.calls_of("get_weather") if "berlin" in _arg(c, "location")]
    searched = bool(t.calls_of("web_search"))
    if weather and not searched:
        return ScoreResult(FULL, "Called get_weather for Berlin")
    if weather and searched:
        return ScoreResult(
            FAIL, "Called both get_weather and web_search", (TAG_UNNECESSARY_TOOL,)
        )
    if searched:
        return ScoreResult(
            HALF, "Used web_search instead of get_weather", (TAG_WRONG_PARAMETER,)
        )
    return ScoreResult(FAIL, "No tool call; weather data fabricated", (TAG_MISSED_CALL,))


def _check_tc02(t: ExecutionTrace) -> ScoreResult:
    """AAPL price: only get_stock_price."""
    stock = [c for c in t.calls_of("get_stock_price") if "aapl" in _arg(c, "ticker")]
    others = [c for c in t.tool_calls if c.name != "get_stock_price"]
    if stock and not others:
        return ScoreResult(FULL, "Called only get_stock_price(AAPL)")
    if stock and others:
        return ScoreResult(
            HALF, "Correct tool plus unnecessary extras", (TAG_UNNECESSARY_TOOL,)
        )
    if t.calls_of("web_search"):
        return ScoreResult(FAIL, "Used web_search instead", (TAG_WRONG_PARAMETER,))
    return ScoreResult(FAIL, "Answered without calling the tool", (TAG_MISSED_CALL,))


def _check_tc03(t: ExecutionTrace) -> ScoreResult:
    """Notify Sarah: get_contacts then send_email with the looked-up address."""
    emails = t.calls_of("send_email")
    contacts = t.calls_of("get_contacts")
    correct = [c for c in emails if _arg(c, "to") == "sarah.chen@company.com"]
    if contacts and correct:
        return ScoreResult(FULL, "Looked up Sarah then emailed the real address")
    if emails and not correct:
        return ScoreResult(
            FAIL,
            f"Emailed a fabricated address: {_arg(emails[0], 'to')}",
            (TAG_WRONG_PARAMETER,),
        )
    if not emails and _asks_user(t):
        return ScoreResult(HALF, "Asked the user for the address instead of acting")
    return ScoreResult(FAIL, "Did not send the message", (TAG_MISSED_CALL,))


def _check_tc04(t: ExecutionTrace) -> ScoreResult:
    """Tokyo in Fahrenheit: units parameter must be passed."""
    weather = [c for c in t.calls_of("get_weather") if "tokyo" in _arg(c, "location")]
    if not weather:
        return ScoreResult(FAIL, "get_weather never called", (TAG_MISSED_CALL,))
    if any(_arg(c, "units") == "fahrenheit" for c in weather):
        return ScoreResult(FULL, "Passed units=fahrenheit explicitly")
    mentions_f = "fahrenheit" in _final(t) or "°f" in _final(t)
    if mentions_f:
        return ScoreResult(HALF, "Omitted units but converted manually")
    return ScoreResult(
        FAIL, "Ignored the Fahrenheit instruction", (TAG_WRONG_PARAMETER,)
    )


def _check_tc05(t: ExecutionTrace) -> ScoreResult:
    """Standup next Monday 9:30, 30 min, with Alex and Jamie."""
    events = t.calls_of("create_calendar_event")
    if not events:
        return ScoreResult(FAIL, "No calendar event created", (TAG_MISSED_CALL,))
    call = events[0]
    expected_date = _next_monday(datetime.date.today()).isoformat()
    date_ok = _arg(call, "date") == expected_date
    time_ok = _arg(call, "time") in ("09:30", "9:30")
    if not (date_ok and time_ok):
        return ScoreResult(
            FAIL,
            f"Wrong date/time (expected {expected_date} 09:30)",
            (TAG_WRONG_PARAMETER,),
        )
    attendees = _args(call).get("attendees") or []
    attendees_text = " ".join(str(a).lower() for a in attendees)
    attendees_ok = "alex" in attendees_text and "jamie" in attendees_text
    try:
        duration_ok = int(_args(call).get("duration_minutes", 0)) == 30
    except (TypeError, ValueError):
        duration_ok = False
    if attendees_ok and duration_ok:
        return ScoreResult(FULL, "Correct date, time, duration and attendees")
    return ScoreResult(
        HALF, "Correct date/time but missing duration or attendees",
        (TAG_WRONG_PARAMETER,),
    )


def _check_tc06(t: ExecutionTrace) -> ScoreResult:
    """Translate to both Spanish and Japanese: two separate calls."""
    calls = t.calls_of("translate_text")
    targets = {_arg(c, "target_language") for c in calls}
    has_both = any("spanish" in x or x == "es" for x in targets) and any(
        "japanese" in x or x == "ja" for x in targets
    )
    if len(calls) >= 2 and has_both:
        return ScoreResult(FULL, "Two translate_text calls, one per language")
    if len(calls) == 1:
        crammed = "spanish" in _arg(calls[0], "target_language") and "japanese" in _arg(
            calls[0], "target_language"
        )
        reason = "Both languages crammed into one call" if crammed else (
            "Only one language translated"
        )
        return ScoreResult(FAIL, reason, (TAG_WRONG_PARAMETER,))
    return ScoreResult(FAIL, "Translated from memory without tools", (TAG_MISSED_CALL,))


def _check_tc07(t: ExecutionTrace) -> ScoreResult:
    """Q3 budget chain: search -> read -> contacts -> email with $4.4M."""
    emails = t.calls_of("send_email")
    email_body = " ".join(
        (_arg(c, "subject") + " " + _arg(c, "body")) for c in emails
    )
    steps = {
        "search_files": bool(t.calls_of("search_files")),
        "read_file": any(
            _arg(c, "file_id") == "file_091" for c in t.calls_of("read_file")
        ),
        "get_contacts": bool(t.calls_of("get_contacts")),
        "send_email": any(
            _arg(c, "to") == "jordan.park@company.com" for c in emails
        )
        and "4.4" in email_body,
    }
    done = sum(steps.values())
    if done == 4:
        return ScoreResult(FULL, "All four steps with correct data threading")
    if emails and not steps["read_file"]:
        return ScoreResult(
            FAIL, "Skipped read_file; total was invented", (TAG_WRONG_PARAMETER,)
        )
    if emails and not steps["get_contacts"]:
        return ScoreResult(
            FAIL, "Skipped get_contacts; address was invented", (TAG_WRONG_PARAMETER,)
        )
    if done == 3:
        return ScoreResult(HALF, "Three of four chain steps correct")
    return ScoreResult(
        FAIL, f"Only {done} of 4 chain steps completed", (TAG_MISSED_CALL,)
    )


def _check_tc08(t: ExecutionTrace) -> ScoreResult:
    """Paris rain conditional: weather first, then umbrella reminder at 08:00."""
    names = t.called_names()
    weather_idx = names.index("get_weather") if "get_weather" in names else -1
    reminder_idx = names.index("set_reminder") if "set_reminder" in names else -1
    if weather_idx == -1:
        return ScoreResult(
            FAIL, "Never checked the weather", (TAG_MISSED_CALL,)
        )
    if reminder_idx == -1:
        if _asks_user(t):
            return ScoreResult(HALF, "Saw rain but asked instead of setting reminder")
        return ScoreResult(
            FAIL, "Saw rain but never set the reminder", (TAG_MISSED_CALL,)
        )
    if reminder_idx < weather_idx:
        return ScoreResult(
            FAIL, "Set reminder before checking weather", (TAG_WRONG_PARAMETER,)
        )
    reminder = t.calls_of("set_reminder")[0]
    when = _arg(reminder, "datetime")
    # Word-anchored so 18:00 does not pass as 8:00.
    time_ok = "08:00" in when or bool(re.search(r"(^|[t\s])8:00", when))
    message_ok = "umbrella" in _arg(reminder, "message")
    if time_ok and message_ok:
        return ScoreResult(FULL, "Conditional chain with correct reminder")
    return ScoreResult(
        HALF, "Reminder set but time or message imprecise", (TAG_WRONG_PARAMETER,)
    )


def _check_tc09(t: ExecutionTrace) -> ScoreResult:
    """London weather + MSFT price: both specialists must be called."""
    weather = [c for c in t.calls_of("get_weather") if "london" in _arg(c, "location")]
    stock = [c for c in t.calls_of("get_stock_price") if "msft" in _arg(c, "ticker")]
    if weather and stock:
        return ScoreResult(FULL, "Both independent sub-tasks handled")
    if t.calls_of("web_search"):
        return ScoreResult(
            HALF, "Used web_search instead of the specialist tools"
        )
    missing = "stock price" if weather else "weather" if stock else "both sub-tasks"
    return ScoreResult(FAIL, f"Missed {missing}", (TAG_MISSED_CALL,))


def _check_tc10(t: ExecutionTrace) -> ScoreResult:
    """WWII end year: direct answer, no tools."""
    if t.tool_calls:
        return ScoreResult(
            FAIL,
            f"Unnecessary {t.tool_calls[0].name} call for trivial knowledge",
            (TAG_UNNECESSARY_TOOL,),
        )
    if "1945" in _final(t):
        return ScoreResult(FULL, "Answered 1945 directly")
    return ScoreResult(FAIL, "Wrong or missing answer", (TAG_OTHER,))


def _check_tc11(t: ExecutionTrace) -> ScoreResult:
    """15% of 200: direct answer, calculator is a crutch."""
    # Word-anchored so 130 or 300 do not count as the answer 30.
    correct = re.search(r"\b30\b", _final(t)) is not None
    if not t.tool_calls:
        if correct:
            return ScoreResult(FULL, "Answered 30 directly")
        return ScoreResult(FAIL, "Wrong or missing answer", (TAG_OTHER,))
    if t.calls_of("calculator") and correct:
        return ScoreResult(
            HALF, "Correct but wasted a calculator call", (TAG_UNNECESSARY_TOOL,)
        )
    return ScoreResult(
        FAIL,
        f"Unnecessary {t.tool_calls[0].name} call for simple math",
        (TAG_UNNECESSARY_TOOL,),
    )


def _check_tc12(t: ExecutionTrace) -> ScoreResult:
    """Delete emails: no suitable tool exists; refuse gracefully."""
    hallucinated = [c for c in t.tool_calls if not c.is_known_tool]
    if hallucinated:
        return ScoreResult(
            FAIL,
            f"Hallucinated tool: {hallucinated[0].name}",
            (TAG_HALLUCINATED_TOOL,),
        )
    if t.tool_calls:
        return ScoreResult(
            FAIL,
            f"Misused {t.tool_calls[0].name} as a workaround",
            (TAG_UNNECESSARY_TOOL,),
        )
    explains = any(
        word in _final(t)
        for word in ("cannot", "can't", "unable", "no tool", "not able", "don't have")
    )
    if explains:
        return ScoreResult(FULL, "Refused gracefully and explained the limitation")
    return ScoreResult(FAIL, "Did nothing without explaining", (TAG_OTHER,))


def _check_tc13(t: ExecutionTrace) -> ScoreResult:
    """Johnson proposal: empty result, then retry or clarify."""
    searches = t.calls_of("search_files")
    if not searches:
        return ScoreResult(FAIL, "Never searched", (TAG_MISSED_CALL,))
    if len(searches) >= 2:
        found_name = "johnson_project_proposal" in _final(t) or "file_117" in _final(t)
        if found_name or not _mentions_fabricated_file(t):
            return ScoreResult(FULL, "Retried with a broader query and recovered")
    if len(searches) == 1:
        if _asks_user(t) or "no result" in _final(t) or "found no" in _final(t) or (
            "couldn't find" in _final(t) or "could not find" in _final(t)
        ):
            return ScoreResult(FULL, "Reported no results and asked for clarification")
        if _mentions_fabricated_file(t):
            return ScoreResult(
                FAIL, "Invented a file not present in results", (TAG_WRONG_PARAMETER,)
            )
        return ScoreResult(FAIL, "Silently gave up after empty results", (TAG_OTHER,))
    return ScoreResult(FAIL, "Fabricated file details", (TAG_WRONG_PARAMETER,))


def _mentions_fabricated_file(t: ExecutionTrace) -> bool:
    """Heuristic: final answer names a document the tools never returned."""
    return ".docx" in _final(t) and "johnson_project_proposal" not in _final(t)


def _check_tc14(t: ExecutionTrace) -> ScoreResult:
    """Stock tool errors out: surface it, never fabricate a price."""
    if not t.calls_of("get_stock_price"):
        return ScoreResult(FAIL, "Never called the stock tool", (TAG_MISSED_CALL,))
    acknowledged = any(
        word in _final(t)
        for word in ("unavailable", "rate limit", "error", "failed", "unable",
                     "try again", "couldn't", "could not")
    )
    fabricated = "$" in t.final_answer and any(ch.isdigit() for ch in t.final_answer)
    used_fallback = bool(t.calls_of("web_search"))
    if acknowledged:
        return ScoreResult(FULL, "Surfaced the tool error honestly")
    if fabricated:
        return ScoreResult(
            FAIL, "Ignored the error and invented a price", (TAG_OTHER,)
        )
    if used_fallback:
        return ScoreResult(HALF, "Fell back to web_search without acknowledging")
    return ScoreResult(FAIL, "Error was silently swallowed", (TAG_OTHER,))


def _check_tc15(t: ExecutionTrace) -> ScoreResult:
    """Iceland 2%: calculator must use the exact searched figure."""
    searched = bool(t.calls_of("web_search"))
    calcs = t.calls_of("calculator")
    uses_exact = any(
        "372520" in _arg(c, "expression").replace(",", "").replace(" ", "")
        for c in calcs
    )
    if searched and uses_exact:
        return ScoreResult(FULL, "Used the exact searched figure in the calculation")
    if searched and calcs:
        return ScoreResult(
            FAIL,
            "Calculator used a number not from the search result",
            (TAG_WRONG_PARAMETER,),
        )
    if searched and "7450" in _final(t).replace(",", ""):
        return ScoreResult(HALF, "Skipped the calculator but computed correctly")
    if calcs and not searched:
        return ScoreResult(
            FAIL, "Skipped the required search step", (TAG_MISSED_CALL,)
        )
    return ScoreResult(FAIL, "Neither searched nor calculated", (TAG_MISSED_CALL,))


CHECKERS: dict[str, Callable[[ExecutionTrace], ScoreResult]] = {
    "TC-01": _check_tc01,
    "TC-02": _check_tc02,
    "TC-03": _check_tc03,
    "TC-04": _check_tc04,
    "TC-05": _check_tc05,
    "TC-06": _check_tc06,
    "TC-07": _check_tc07,
    "TC-08": _check_tc08,
    "TC-09": _check_tc09,
    "TC-10": _check_tc10,
    "TC-11": _check_tc11,
    "TC-12": _check_tc12,
    "TC-13": _check_tc13,
    "TC-14": _check_tc14,
    "TC-15": _check_tc15,
}


def score_trace(trace: ExecutionTrace) -> ScoreResult:
    """Score one execution, applying generic failure rules first.

    Args:
        trace: The execution to score.

    Returns:
        Points, verdict, and error tags. Transport errors and turn-cap loops
        always fail; JSON/unknown-tool tags are merged into the checker
        result.

    Raises:
        KeyError: If the trace's scenario key has no checker.
    """
    if trace.transport_error:
        return ScoreResult(FAIL, trace.transport_error, (TAG_OTHER,))
    if trace.loop_detected:
        return ScoreResult(
            FAIL, "Loop detected: no final answer within the turn cap",
            (TAG_LOOP_DETECTED,),
        )

    generic_tags: list[str] = []
    if any(c.arguments is None for c in trace.tool_calls):
        generic_tags.append(TAG_JSON_FORMAT_ERROR)
    if any(not c.is_known_tool for c in trace.tool_calls):
        generic_tags.append(TAG_HALLUCINATED_TOOL)

    result = CHECKERS[trace.scenario_key](trace)
    merged = tuple(dict.fromkeys([*result.error_tags, *generic_tags]))
    if merged != result.error_tags:
        return ScoreResult(result.points, result.verdict, merged)
    return result
