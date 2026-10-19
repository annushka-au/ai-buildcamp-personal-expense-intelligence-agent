"""
The Week 2 tool-calling expenses/extraction agent, extracted from
notebooks/02-rag.ipynb so it can be imported by pytest.

This is a 1:1 port of the notebook's logic (same tools, same instructions,
same manual OpenAI Responses tool-calling loop) with two changes needed for
testability:

1. Data paths are resolved relative to this file, not the current working
   directory, so it works the same whether run from the project root or
   from pytest's rootdir.
2. `run_agent_traced` factors the loop out of `run_agent` so tests can
   inspect which tools were called, with what arguments, and what they
   returned - `run_agent` itself is unchanged for anyone calling it directly.
"""

import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from minsearch import Index

BASE_DIR = Path(__file__).resolve().parent
EXPENSES_PATH = BASE_DIR / "data" / "expenses.json"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"

openai_client = OpenAI()

with open(EXPENSES_PATH) as f:
    documents = json.load(f)

index = Index(
    text_fields=["merchant", "category", "description"],
    keyword_fields=["category"],
    vectorizer_params={"stop_words": "english"},
)
index.fit(documents)


# ---------------------------------------------------------------------
# Expenses tools
# ---------------------------------------------------------------------

def search_expenses(query):
    """Semantic/fuzzy search over merchant, category, and description.
    Use for open-ended or explanatory questions."""
    return index.search(query, num_results=13)


def query_expenses(filters=None, group_by=None, aggregate=None):
    """Exact filter and/or aggregation over the expense table.
    Use when the answer needs a real number or a complete, deterministic match."""
    filters = filters or {}
    merchant = filters.get("merchant")
    category = filters.get("category")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")

    def matches(r):
        if merchant and merchant.lower() not in r["merchant"].lower():
            return False
        if category and r["category"].lower() != category.lower():
            return False
        if date_from and r["date"] < date_from:
            return False
        if date_to and r["date"] > date_to:
            return False
        return True

    rows = [r for r in documents if matches(r)]

    if not group_by and not aggregate:
        return rows

    def group_key(r):
        if group_by == "category":
            return r["category"]
        if group_by == "merchant":
            return r["merchant"]
        if group_by == "month":
            return r["date"][:7]
        return "all"

    groups = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r["total"])

    def apply_aggregate(values):
        if aggregate == "count":
            return len(values)
        if aggregate == "avg":
            return round(sum(values) / len(values), 2)
        return round(sum(values), 2)  # default/"sum"

    return [{"group": k, "value": apply_aggregate(v)} for k, v in sorted(groups.items())]


def find_recurring_charges(min_occurrences=2, amount_tolerance_pct=10, category=None):
    """Groups transactions by merchant and flags ones that repeat at a similar
    amount, to catch recurring bills/subscriptions even outside the
    'subscriptions' category."""
    by_merchant = {}
    for r in documents:
        if category and r["category"].lower() != category.lower():
            continue
        by_merchant.setdefault(r["merchant"], []).append(r)

    results = []
    for merchant, txns in by_merchant.items():
        if len(txns) < min_occurrences:
            continue
        avg = sum(t["total"] for t in txns) / len(txns)
        tolerance = avg * (amount_tolerance_pct / 100)
        close = sorted(
            (t for t in txns if abs(t["total"] - avg) <= tolerance),
            key=lambda t: t["date"],
        )
        if len(close) < min_occurrences:
            continue
        results.append({
            "merchant": merchant,
            "category": close[0]["category"],
            "occurrences": [{"date": t["date"], "total": t["total"]} for t in close],
            "avg_amount": round(sum(t["total"] for t in close) / len(close), 2),
            "total_amount": round(sum(t["total"] for t in close), 2),
        })
    return results


# ---------------------------------------------------------------------
# Extraction tools
# ---------------------------------------------------------------------

def read_uploaded_document(document_id):
    """Retrieves the raw content of an uploaded receipt/bill/invoice so the
    LLM can read and extract fields from it directly."""
    path = UPLOADS_DIR / f"{document_id}.txt"
    if not path.exists():
        return {"error": f"document '{document_id}' not found"}

    stat = path.stat()
    return {
        "content": path.read_text(),
        "filename": path.name,
        "mime_type": "text/plain",
        "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def check_duplicate_expense(merchant, date, total):
    """Checks whether a near-identical expense already exists, to avoid
    double-counting a receipt that was uploaded more than once."""
    for r in documents:
        if (
            r["merchant"].lower() == merchant.lower()
            and r["date"] == date
            and abs(r["total"] - total) < 0.01
        ):
            return {"is_duplicate": True, "existing_record": r}
    return {"is_duplicate": False}


def write_expense_record(id, date, merchant, category, description, total):
    """Persists a structured expense record extracted from a document.
    Stores to data/expenses.json for now; may move to Postgres later."""
    existing_ids = {r["id"] for r in documents}
    if id in existing_ids:
        id = f"{id}-{len(documents) + 1}"

    record = {
        "id": id,
        "date": date,
        "merchant": merchant,
        "category": category,
        "description": description,
        "total": total,
    }
    documents.append(record)
    EXPENSES_PATH.write_text(json.dumps(documents, indent=2))
    index.fit(documents)  # rebuild so the new record is searchable immediately

    return {"id": id, "status": "stored"}


# ---------------------------------------------------------------------
# Tool schemas and dispatch table
# ---------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "search_expenses",
        "description": (
            "Semantic search over expense merchant/category/description. Use "
            "for open-ended or explanatory questions (e.g. 'why was spending "
            "high in September?')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "query_expenses",
        "description": (
            "Exact filtering and/or aggregation over the expense table. Use "
            "when the answer needs a real number or a complete, deterministic "
            "match (totals, comparisons, exact merchant/date checks)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "merchant": {"type": "string"},
                        "category": {"type": "string"},
                        "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                        "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                },
                "group_by": {"type": "string", "enum": ["category", "month", "merchant"]},
                "aggregate": {"type": "string", "enum": ["sum", "count", "avg"]},
            },
        },
    },
    {
        "type": "function",
        "name": "find_recurring_charges",
        "description": (
            "Groups transactions by merchant across months and flags ones "
            "repeating at a similar amount. Use for subscriptions and "
            "recurring-bill questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_occurrences": {"type": "integer", "default": 2},
                "amount_tolerance_pct": {"type": "number", "default": 10},
                "category": {"type": "string"},
            },
        },
    },
    {
        "type": "function",
        "name": "read_uploaded_document",
        "description": (
            "Retrieves the raw content of an uploaded receipt/bill/invoice by "
            "document id, so it can be read and analysed."
        ),
        "parameters": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
    {
        "type": "function",
        "name": "check_duplicate_expense",
        "description": (
            "Checks whether a near-identical expense already exists (same "
            "merchant, date, and total). Call before writing a newly "
            "extracted expense."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "merchant": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "total": {"type": "number"},
            },
            "required": ["merchant", "date", "total"],
        },
    },
    {
        "type": "function",
        "name": "write_expense_record",
        "description": (
            "Persists a structured expense record. Call only after the "
            "record has been extracted from a document and confirmed not to "
            "be a duplicate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "merchant": {"type": "string"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "total": {"type": "number"},
            },
            "required": ["id", "date", "merchant", "category", "description", "total"],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_expenses": search_expenses,
    "query_expenses": query_expenses,
    "find_recurring_charges": find_recurring_charges,
    "read_uploaded_document": read_uploaded_document,
    "check_duplicate_expense": check_duplicate_expense,
    "write_expense_record": write_expense_record,
}


# ---------------------------------------------------------------------
# Agent instructions
# ---------------------------------------------------------------------

AGENT_INSTRUCTIONS = """
You're a personal expense agent for an Australian household. You have two
jobs, and you must choose the right tools for whichever one the user is
asking about:

1. ANSWERING QUESTIONS about existing spending (merchant, category,
   description, date, total).
2. PROCESSING AN UPLOADED DOCUMENT (a receipt, bill, or invoice) into a new
   structured expense record.

All expense records are dated 2026. When a question names a month without a
year (e.g. "September"), use that month in 2026 for `date_from`/`date_to` -
do not assume any other year.

Tool selection rules - follow these exactly:
- Use `search_expenses` for open-ended or explanatory questions where the
  wording matters more than an exact number (e.g. "why was spending high in
  September?", "what did I buy at Bunnings?").
- Use `query_expenses` whenever the answer needs an exact calculation or a
  complete, deterministic match: totals, month-over-month comparisons,
  category breakdowns, or checking for a specific charge.
- Use `find_recurring_charges` for questions about subscriptions or
  repeated/recurring bills, including ones that might not be labelled
  "subscriptions". Call it once without a `category` filter first - it
  already checks every merchant - and only narrow by category if the user
  asked about a specific one.
- Use `read_uploaded_document` whenever the user refers to an uploaded
  receipt, bill, or invoice (by its document id) that needs to be read and
  analysed.
- When processing an uploaded document: read it with `read_uploaded_document`,
  then do the field extraction yourself as part of your reasoning - identify
  the merchant, date (YYYY-MM-DD), category (one of: groceries, utilities,
  transport, dining, household, health, subscriptions), a short description,
  and the total. Do NOT call a separate tool to do the extraction - that is
  your job as the model.
- Before writing a newly extracted expense, call `check_duplicate_expense`
  with the merchant, date, and total. Only call `write_expense_record` if it
  is not a duplicate; if it is, tell the user instead of writing it again.
- Call `write_expense_record` only after the record has been extracted and
  checked - never call it speculatively or before you have real values for
  every field.

General rules:
- Ground every answer in the data returned by your tools. Cite the specific
  merchants, dates, and amounts that support your answer.
- If a tool's results don't contain enough information to answer
  confidently, say so clearly instead of guessing.
- When you've successfully stored a new expense record, confirm back to the
  user what was stored (merchant, date, category, total) and its id.
""".strip()


# ---------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------

def run_agent_traced(question, max_iterations=8, model="gpt-4o-mini"):
    """Same loop as run_agent, but also returns the list of tool calls made
    (name, args, result) so tests can assert on tool usage, not just the
    final text."""
    messages = [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
        {"role": "user", "content": question},
    ]
    tool_calls_trace = []

    for _ in range(max_iterations):
        response = openai_client.responses.create(
            model=model,
            input=messages,
            tools=TOOL_SCHEMAS,
        )

        function_calls = [item for item in response.output if item.type == "function_call"]

        if not function_calls:
            return response.output_text, tool_calls_trace

        for call in function_calls:
            args = json.loads(call.arguments)
            result = TOOL_FUNCTIONS[call.name](**args)
            tool_calls_trace.append({"name": call.name, "args": args, "result": result})

            messages.append({
                "type": "function_call",
                "call_id": call.call_id,
                "name": call.name,
                "arguments": call.arguments,
            })
            messages.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, default=str),
            })

    return "Reached the maximum number of tool calls without a final answer.", tool_calls_trace


def run_agent(question, max_iterations=8, model="gpt-4o-mini"):
    answer, _ = run_agent_traced(question, max_iterations=max_iterations, model=model)
    return answer
