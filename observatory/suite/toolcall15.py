"""ToolCall-15 v1.0 suite data, transcribed from METHODOLOGY.md.

This module is the executable form of the frozen methodology: the shared
system prompt, the 12-tool universal toolkit (OpenAI function-calling format),
per-scenario mocked tool responses, and scenario metadata. Scoring rules live
in observatory/scoring/checkers.py, one checker per scenario key.

Mock resolution: when a model calls tool T during scenario S, the executor
pops the next response from S's queue for T; an exhausted queue repeats its
last entry. Tools without a scenario-specific queue fall back to
GENERIC_MOCKS so conversations stay natural and deterministic.
"""

import ast
import datetime
import operator
from dataclasses import dataclass, field

SUITE_VERSION = "toolcall15-v1.0"

SYSTEM_PROMPT = """You are a helpful assistant with access to the tools provided.

Rules:
- Use a tool ONLY when it is necessary to fulfill the user's request.
- If you can answer directly from your own knowledge, do so without calling a tool.
- If a tool call fails, explain the failure and suggest an alternative approach.
- Never invent information that a tool should provide."""


def system_prompt_with_context(now: datetime.datetime) -> str:
    """The shared system prompt plus runtime date context.

    METHODOLOGY.md scenarios assume the model knows today's date (TC-05
    "next Monday", TC-08 "tomorrow at 8am") but the frozen prompt never
    states it. Real tool-calling deployments always provide the current
    date, so the harness injects it here; without it, models correctly
    refuse to guess and every date-relative scenario fails on all models.

    Args:
        now: The execution start time.

    Returns:
        System prompt with a trailing current-date line.
    """
    return f"{SYSTEM_PROMPT}\n\nCurrent date and time: {now:%A, %Y-%m-%d %H:%M}."

CATEGORIES = {
    "A": "Tool Selection",
    "B": "Parameter Precision",
    "C": "Multi-Step Chains",
    "D": "Restraint & Refusal",
    "E": "Error Recovery",
}

CATEGORY_WEIGHT = 0.20
MAX_POINTS_PER_SCENARIO = 2
SCENARIOS_PER_CATEGORY = 3


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    """Build one OpenAI-format tool definition.

    Args:
        name: Function name.
        description: What the tool does.
        properties: JSON-schema properties for the parameters object.
        required: Names of required parameters.

    Returns:
        Tool definition dict for the chat completions `tools` array.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOLS: list[dict] = [
    _tool(
        "web_search",
        "Search the web for current information",
        {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        },
        ["query"],
    ),
    _tool(
        "get_weather",
        "Get current weather for a specific location",
        {
            "location": {"type": "string"},
            "units": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "default": "celsius",
            },
        },
        ["location"],
    ),
    _tool(
        "calculator",
        "Perform mathematical calculations",
        {"expression": {"type": "string"}},
        ["expression"],
    ),
    _tool(
        "send_email",
        "Send an email to a recipient",
        {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "attachments": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
        },
        ["to", "subject", "body"],
    ),
    _tool(
        "search_files",
        "Search for files by name or content",
        {
            "query": {"type": "string"},
            "file_type": {
                "type": "string",
                "enum": ["pdf", "docx", "xlsx", "any"],
                "default": "any",
            },
        },
        ["query"],
    ),
    _tool(
        "read_file",
        "Read the contents of a specific file",
        {"file_id": {"type": "string"}},
        ["file_id"],
    ),
    _tool(
        "create_calendar_event",
        "Create a new calendar event",
        {
            "title": {"type": "string"},
            "date": {"type": "string", "description": "Format: YYYY-MM-DD"},
            "time": {"type": "string", "description": "Format: HH:MM"},
            "duration_minutes": {"type": "integer", "default": 60},
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
        },
        ["title", "date", "time"],
    ),
    _tool(
        "get_contacts",
        "Look up contacts by name or group",
        {"query": {"type": "string"}},
        ["query"],
    ),
    _tool(
        "translate_text",
        "Translate text from one language to another",
        {
            "text": {"type": "string"},
            "source_language": {"type": "string"},
            "target_language": {"type": "string"},
        },
        ["text", "source_language", "target_language"],
    ),
    _tool(
        "get_stock_price",
        "Get the current stock price for a ticker symbol",
        {"ticker": {"type": "string"}},
        ["ticker"],
    ),
    _tool(
        "set_reminder",
        "Set a reminder for a future time",
        {
            "message": {"type": "string"},
            "datetime": {"type": "string", "description": "ISO 8601"},
        },
        ["message", "datetime"],
    ),
    _tool(
        "run_code",
        "Execute a code snippet and return the output",
        {
            "language": {"type": "string", "enum": ["python", "javascript"]},
            "code": {"type": "string"},
        },
        ["language", "code"],
    ),
]

TOOL_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in TOOLS
)

_CALC_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_arithmetic(node) -> float:
    """Evaluate a numeric AST node using only whitelisted operators.

    Raises:
        ValueError: For any non-arithmetic construct.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _CALC_OPS:
        return _CALC_OPS[type(node.op)](
            _eval_arithmetic(node.left), _eval_arithmetic(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _CALC_OPS:
        return _CALC_OPS[type(node.op)](_eval_arithmetic(node.operand))
    raise ValueError("unsupported expression")


def calculator_result(expression: str) -> dict:
    """Real arithmetic for unscripted calculator calls.

    A static mock (previously {"result": 0}) contradicts the expression the
    model sent and punishes models that trust their tools; evaluating keeps
    the environment deterministic AND truthful.

    Args:
        expression: The expression argument from the tool call.

    Returns:
        {"result": value} or an error payload for non-arithmetic input.
    """
    try:
        node = ast.parse(expression.replace(",", ""), mode="eval").body
        return {"result": round(_eval_arithmetic(node), 6)}
    except Exception:
        return {"error": f"Could not evaluate expression: {expression!r}"}


# Deterministic fallbacks for tools called outside their scenario's script.
# The calculator is special-cased in the executor via calculator_result().
GENERIC_MOCKS: dict[str, dict] = {
    "web_search": {
        "results": [
            {"snippet": "Generic search result. No specific data available."}
        ]
    },
    "get_weather": {
        "location": "Unknown",
        "temperature": 15,
        "units": "celsius",
        "condition": "Clear",
    },
    "calculator": {"result": 0},
    "send_email": {"status": "sent", "message_id": "msg_0000"},
    "search_files": {"results": []},
    "read_file": {"error": "File not found."},
    "create_calendar_event": {"event_id": "evt_0000", "status": "created"},
    "get_contacts": {"results": []},
    "translate_text": {"translated": "(mock translation)"},
    "get_stock_price": {"ticker": "UNKNOWN", "price": 100.0, "currency": "USD"},
    "set_reminder": {"reminder_id": "rem_0000", "status": "set"},
    "run_code": {"output": ""},
}


@dataclass(frozen=True)
class Scenario:
    """One benchmark scenario.

    Args:
        key: Stable identifier, e.g. "TC-01".
        name: Short display name.
        category: Category letter A..E (see CATEGORIES).
        difficulty: One of easy / medium / hard.
        user_message: The user turn sent to the model.
        expected_behavior: Human-readable pass criteria from METHODOLOGY.md.
        mocks: Per-tool queues of mocked responses, consumed in call order.
    """

    key: str
    name: str
    category: str
    difficulty: str
    user_message: str
    expected_behavior: str
    mocks: dict[str, list[dict]] = field(default_factory=dict)


SCENARIOS: list[Scenario] = [
    Scenario(
        key="TC-01",
        name="Direct Specialist Match",
        category="A",
        difficulty="easy",
        user_message="What's the weather like in Berlin right now?",
        expected_behavior=(
            "Call get_weather with location Berlin. Do NOT call web_search."
        ),
        mocks={
            "get_weather": [
                {
                    "location": "Berlin",
                    "temperature": 8,
                    "units": "celsius",
                    "condition": "Overcast",
                    "humidity": 72,
                }
            ]
        },
    ),
    Scenario(
        key="TC-02",
        name="Distractor Resistance",
        category="A",
        difficulty="easy",
        user_message="What is the current price of AAPL stock?",
        expected_behavior=(
            "Call get_stock_price with ticker AAPL and no other tool."
        ),
        mocks={
            "get_stock_price": [
                {
                    "ticker": "AAPL",
                    "price": 187.42,
                    "currency": "USD",
                    "change": "+1.23",
                    "change_percent": "+0.66%",
                }
            ]
        },
    ),
    Scenario(
        key="TC-03",
        name="Implicit Tool Need",
        category="A",
        difficulty="medium",
        user_message="I need to let Sarah know the meeting moved to 3pm.",
        expected_behavior=(
            "Call get_contacts for Sarah first, then send_email to the "
            "looked-up address. Never fabricate the address."
        ),
        mocks={
            "get_contacts": [
                {
                    "results": [
                        {"name": "Sarah Chen", "email": "sarah.chen@company.com"}
                    ]
                }
            ],
            "send_email": [{"status": "sent", "message_id": "msg_8821"}],
        },
    ),
    Scenario(
        key="TC-04",
        name="Unit Handling",
        category="B",
        difficulty="easy",
        user_message="What's the temperature in Tokyo in Fahrenheit?",
        expected_behavior=(
            "Call get_weather with location Tokyo AND units fahrenheit."
        ),
        mocks={
            "get_weather": [
                {
                    "location": "Tokyo",
                    "temperature": 64,
                    "units": "fahrenheit",
                    "condition": "Clear",
                }
            ]
        },
    ),
    Scenario(
        key="TC-05",
        name="Date and Time Parsing",
        category="B",
        difficulty="medium",
        user_message=(
            "Schedule a team standup for next Monday at 9:30am, 30 minutes, "
            "with Alex and Jamie."
        ),
        expected_behavior=(
            "create_calendar_event with the correct next-Monday date, time "
            "09:30, duration 30, and attendees including Alex and Jamie."
        ),
        mocks={
            "create_calendar_event": [
                {
                    "event_id": "evt_4412",
                    "status": "created",
                    "title": "Team Standup",
                }
            ],
            "get_contacts": [
                {
                    "results": [
                        {"name": "Alex Rivera", "email": "alex.rivera@company.com"},
                        {"name": "Jamie Wu", "email": "jamie.wu@company.com"},
                    ]
                }
            ],
        },
    ),
    Scenario(
        key="TC-06",
        name="Multi-Value Extraction",
        category="B",
        difficulty="medium",
        user_message=(
            "Translate 'Where is the nearest hospital?' from English to both "
            "Spanish and Japanese."
        ),
        expected_behavior=(
            "Two separate translate_text calls, one per target language."
        ),
        mocks={
            "translate_text": [
                {"translated": "¿Dónde está el hospital más cercano?"},
                {"translated": "最寄りの病院はどこですか？"},
            ]
        },
    ),
    Scenario(
        key="TC-07",
        name="Search, Read, Act",
        category="C",
        difficulty="hard",
        user_message=(
            "Find the Q3 budget report and email the total to my manager."
        ),
        expected_behavior=(
            "Chain search_files -> read_file(file_091) -> get_contacts "
            "-> send_email with the $4.4M total, threading data across steps."
        ),
        mocks={
            "search_files": [
                {
                    "results": [
                        {
                            "file_id": "file_091",
                            "name": "Q3_Budget_Report_2025.xlsx",
                        }
                    ]
                }
            ],
            "read_file": [
                {
                    "content": (
                        "Department budgets: Engineering $2.1M, Marketing "
                        "$800K, Sales $1.5M. Total: $4.4M"
                    )
                }
            ],
            "get_contacts": [
                {
                    "results": [
                        {
                            "name": "Jordan Park",
                            "email": "jordan.park@company.com",
                            "role": "manager",
                        }
                    ]
                }
            ],
            "send_email": [{"status": "sent"}],
        },
    ),
    Scenario(
        key="TC-08",
        name="Conditional Branching",
        category="C",
        difficulty="hard",
        user_message=(
            "Check the weather in Paris. If it's raining, remind me to bring "
            "an umbrella tomorrow at 8am."
        ),
        expected_behavior=(
            "get_weather first; the mock reports rain, so set_reminder for "
            "tomorrow 08:00 must follow."
        ),
        mocks={
            "get_weather": [
                {
                    "location": "Paris",
                    "temperature": 11,
                    "condition": "Light rain",
                    "humidity": 89,
                }
            ],
            "set_reminder": [{"reminder_id": "rem_553", "status": "set"}],
        },
    ),
    Scenario(
        key="TC-09",
        name="Parallel Independence",
        category="C",
        difficulty="medium",
        user_message=(
            "What's the weather in London and the stock price of MSFT?"
        ),
        expected_behavior=(
            "Both get_weather(London) and get_stock_price(MSFT) must be "
            "called; parallel is ideal."
        ),
        mocks={
            "get_weather": [
                {"location": "London", "temperature": 12, "condition": "Cloudy"}
            ],
            "get_stock_price": [
                {"ticker": "MSFT", "price": 412.78, "currency": "USD"}
            ],
        },
    ),
    Scenario(
        key="TC-10",
        name="Trivial Knowledge",
        category="D",
        difficulty="easy",
        user_message="What year did World War II end?",
        expected_behavior="Answer 1945 directly with no tool call.",
    ),
    Scenario(
        key="TC-11",
        name="Simple Math",
        category="D",
        difficulty="easy",
        user_message="What is 15% of 200?",
        expected_behavior="Answer 30 directly without the calculator.",
    ),
    Scenario(
        key="TC-12",
        name="Impossible Request",
        category="D",
        difficulty="medium",
        user_message="Delete all my emails from last month.",
        expected_behavior=(
            "No delete tool exists: explain the limitation, call nothing, "
            "and never hallucinate a delete_email tool."
        ),
    ),
    Scenario(
        key="TC-13",
        name="Empty Results Recovery",
        category="E",
        difficulty="medium",
        user_message="Find the Johnson proposal document.",
        expected_behavior=(
            "First search returns nothing: retry with a broader query OR ask "
            "the user for clarification. Never invent a file."
        ),
        mocks={
            "search_files": [
                {"results": []},
                {
                    "results": [
                        {
                            "file_id": "file_117",
                            "name": "Johnson_Project_Proposal_v2.docx",
                        }
                    ]
                },
            ]
        },
    ),
    Scenario(
        key="TC-14",
        name="Malformed Response Handling",
        category="E",
        difficulty="medium",
        user_message="What's Apple's stock price?",
        expected_behavior=(
            "The tool errors: surface the failure honestly, optionally retry "
            "or fall back. Never fabricate a price."
        ),
        mocks={
            "get_stock_price": [
                {"error": "Service temporarily unavailable. Rate limit exceeded."}
            ]
        },
    ),
    Scenario(
        key="TC-15",
        name="Data Integrity Under Pressure",
        category="E",
        difficulty="hard",
        user_message=(
            "Search for the population of Iceland and calculate what 2% of "
            "it would be."
        ),
        expected_behavior=(
            "web_search first, then calculator using the exact 372520 figure "
            "from the search result."
        ),
        mocks={
            "web_search": [
                {
                    "results": [
                        {
                            "snippet": (
                                "Iceland has a population of approximately "
                                "372,520 as of 2025."
                            )
                        }
                    ]
                }
            ],
            "calculator": [{"result": 7450.4}],
        },
    ),
]

SCENARIOS_BY_KEY: dict[str, Scenario] = {s.key: s for s in SCENARIOS}
