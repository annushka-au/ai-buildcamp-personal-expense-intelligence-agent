# Personal Expense Intelligence Agent

An AI Engineering Buildcamp capstone project.

## The Problem

Individuals and households want to understand their spending, but manually entering every transaction from receipts, bills, and invoices is tedious and most people give up on it. Without structured data, it's hard to answer simple questions like "why did I spend more this month?" or "how much did I spend on groceries in September?".

## What It Does

Users upload receipts, bills, and invoices as images or PDFs. The system extracts key information — merchant, date, line items, categories, and amounts — and stores it as structured data. Users can then ask questions about their spending in natural language, such as "Why did I spend more this month?" or "How much did I spend on groceries in September?"

To answer, the system combines structured database queries (for totals, trends, and category breakdowns) with RAG over the original receipts and documents, returning an accurate explanation backed by the underlying transactions.

The MVP focuses on:

- Document extraction (receipts, bills, invoices → structured fields)
- Structured storage of transactions
- Natural-language querying over spending data
- RAG over original receipt/document text
- Basic spending analytics (totals, categories, monthly comparisons)

Later versions could add dashboards, trend analysis, anomaly detection, and expense forecasting.

## Setup

1. Install uv if you don't have it yet: https://docs.astral.sh/uv/getting-started/installation/

2. Clone this repository (or download the zip and extract it).

3. Create a `.env` file from the template and add your API keys:

       cp .env.example .env

   You need `OPENAI_API_KEY`, and `LOGFIRE_TOKEN` (a Logfire project's
   write token, "Send telemetry" capability) - `agent.py` calls
   `logfire.configure()` unconditionally, so it won't start without one
   (or without running `uv run logfire auth` locally instead).

4. Install dependencies:

       uv sync

5. Start Jupyter:

       uv run jupyter notebook

## Try the Agent

Run the interactive chat interface to test the agent:

    uv run streamlit run app.py

This opens at `http://localhost:8501` in your browser. Type a question about
your spending (e.g. "Why were my expenses unusually high in September?") and
the agent's answer appears below, along with an expandable panel showing
which tools it called, with what arguments, and what they returned.

Every interaction is automatically traced in Logfire - `agent.py` is
instrumented with `logfire.instrument_openai()` plus a span per session and
per tool call, so each question's full LLM calls, tool calls, and token
usage/cost are visible in your Logfire dashboard with no extra setup in the
app itself.

## Notebooks

- `notebooks/01-setup.ipynb` - smoke test that confirms your environment works
- `notebooks/02-rag.ipynb` - a minimal RAG baseline you can adapt to your own data

## Testing

`agent.py` is an importable copy of the Week 2 tool-calling agent from `notebooks/02-rag.ipynb`, extracted so pytest can run it directly.

Run the test suite:

    uv run pytest -v -s

This is currently just a dry prototype - a single simple test (`tests/test_agent.py`) covering one scenario (the agent must not hallucinate a dollar figure when asked about a category, like "entertainment", that doesn't exist in the data), as a first step before building out a fuller test suite.

### LLM Judge

`tests/judge.py` provides `assert_criteria(answer, tool_calls, criteria)` - a plain-OpenAI port of the course reference project's judge pattern (structured JSON output instead of PydanticAI, since `agent.py` doesn't use PydanticAI). It sends a judge model the agent's final answer, its tool-call trace, and a list of natural-language criteria, and fails the test with the judge's own explanation if any criterion isn't satisfied.

`tests/test_judge.py` applies it to the September-spike "why" question with 3 specific criteria:

- the agent called `search_expenses` rather than `query_expenses`, since this is an open-ended question, not one needing an exact calculation
- the answer explicitly names both the Qantas flight and the Bunnings washing machine as reasons for the September increase
- the answer ties at least one real dollar amount to a named transaction, not just merchant names with no figures

Each test run makes two live OpenAI calls, nothing mocked: one for the agent under test, one for the judge evaluating it. Running it (`uv run pytest -v -s tests/test_judge.py`) passed all 3 criteria, with the judge's explanation citing the real `$389.00` Qantas flight and `$648.00` washing machine as evidence.

## Data

Put your project data in the `data/` folder. See `notebooks/02-rag.ipynb` for how to load it.
