# Architecture & Vision

## Aim

Help a household turn messy, manual expense tracking into something they can
just ask questions about. Instead of maintaining a spreadsheet or remembering
every transaction, the user uploads whatever paperwork they already have
(receipts, bills, invoices) and asks questions in plain language: *"Why was
September expensive?"*, *"How much do I spend on groceries?"*, *"Am I paying
for any subscriptions I forgot about?"*

## Objectives

- Turn unstructured documents (receipts, bills, invoices) into structured,
  queryable transaction records, with minimal manual data entry.
- Answer both exact questions (totals, comparisons, specific charges) and
  open-ended questions (explanations, patterns, anomalies) correctly and
  without hallucinating numbers.
- Make every answer traceable back to real transaction data - never a
  fabricated figure.
- Keep the system observable: know what the agent did, which tools it used,
  and what it cost, for every interaction.

## The three directions

The project has three distinct flows. Today, only the first two are
implemented (behind one combined agent); the third is not yet built.

```
 1. COLLECTION                2. ANALYSIS                 3. DASHBOARDING
 ──────────────              ───────────────              ───────────────
 receipt/bill/invoice   →    structured records     →     visual trends,
 upload                      + natural-language            budgets, alerts
      │                      Q&A over them                      │
      │                           │                              │
  Extraction Agent          Expenses/Q&A Agent              (not built -
  (write-heavy)             (read-only)                      future work)
```

### 1. Collection - turning a document into a record

**Status: implemented**, as part of the combined agent in `agent.py`.

A user uploads a receipt/bill/invoice. The flow is:

1. `read_uploaded_document` tool fetches the raw document content.
2. **The LLM itself** extracts the structured fields (merchant, date,
   category, description, total) as part of its own reasoning - this is
   deliberately *not* a separate tool call. The model reads the document the
   same way a person would, rather than running a fixed extraction pipeline.
3. `check_duplicate_expense` checks whether this exact transaction (same
   merchant/date/total) already exists, to avoid double-counting a receipt
   uploaded twice.
4. `write_expense_record` persists the new structured record, only once
   extraction and the duplicate check are both done.

This is the **write-heavy** side of the system - the only flow that mutates
data.

### 2. Analysis - answering questions about the data

**Status: implemented**, in the same `agent.py` / exposed via `app.py`.

A user asks a question in natural language. The agent (a tool-calling loop
over the OpenAI Responses API) picks the right tool for the question:

- **`search_expenses`** - semantic/fuzzy search over merchant, category, and
  description. Used for open-ended or explanatory questions ("why was
  spending high in September?"). This is the project's **RAG** component:
  it retrieves the relevant transaction records as context, which the model
  then reasons over and cites in its answer, rather than answering from
  memory. Currently backed by `minsearch` (an in-memory TF-IDF index) as a
  lightweight stand-in for a real retrieval backend - see "Data layer"
  below.
- **`query_expenses`** - exact filtering and aggregation (sum/count/avg,
  grouped by category/month/merchant). Used whenever the answer needs a
  real, deterministic number rather than a retrieved/ranked result.
- **`find_recurring_charges`** - groups transactions by merchant and flags
  similar-amount repeats, to catch subscriptions and recurring bills.

This is the **read-only** side of the system - it never writes data.

### 3. Dashboarding - visual, not conversational, access to the same data

**Status: not built.** Planned as a future direction, not yet scoped or
started. The idea: a visual view of the same underlying data the agent
already reasons over (spending by category/month, trend lines, budget vs.
actual, anomaly flags) - complementary to the chat interface, not a
replacement for it. Chat answers a specific question; a dashboard shows the
shape of spending at a glance.

## Where RAG, Agents, and Tools show up

| Concept | Where |
|---|---|
| **Agent** | `agent.py`'s `run_agent_traced` loop - a manual OpenAI Responses-API tool-calling loop. Conceptually two agent *roles* (extraction, read-only Q&A) that currently live in one process/one set of `AGENT_INSTRUCTIONS`, not two separate deployed agents yet. |
| **Tools** | Six functions in `agent.py`, split by the course's own Search / Fetch-Read / Write-Update framing: **Search** - `search_expenses`. **Fetch/Read** - `query_expenses`, `find_recurring_charges`, `read_uploaded_document`, `check_duplicate_expense`. **Write/Update** - `write_expense_record`. |
| **RAG** | `search_expenses`: retrieves relevant expense records as context, the model answers grounded in that retrieved context rather than from its own training data or guesswork. |
| **Monitoring** | `logfire.instrument_openai()` + a `logfire.span("agent_session")` per interaction, a nested `tool_call` span per tool dispatch, and a `session_cost` event with accumulated token usage - every LLM call, tool call, and cost is traceable per session. |

## Data layer - current state vs. planned

**Current state: no real database.** All expense records live in a single
flat file, `data/expenses.json`, loaded into memory and indexed with
`minsearch` (TF-IDF) at process startup. This is fine for a 20-30 record
synthetic dataset and a single-user prototype; it will not scale to real
usage (multiple users, hundreds/thousands of transactions, concurrent
writes, real semantic search quality).

**Planned: PostgreSQL + either pgvector or Elasticsearch.**

- **PostgreSQL** becomes the system of record for structured transaction
  data - the equivalent of today's `expenses.json`, but with real schema,
  constraints, concurrent writes, and the ability to do `query_expenses`-
  style aggregation with actual SQL instead of looping over a Python list.
- For the semantic-search side (what `search_expenses` does today via
  `minsearch`), there are two reasonable paths, and the two are not
  mutually exclusive:
  - **pgvector** (a Postgres extension): store embeddings as a column
    alongside the structured row, query with one engine, one connection,
    one transaction boundary. Simplest operationally - no second system to
    run.
  - **Elasticsearch**: a dedicated search/vector engine, better suited if
    retrieval needs grow beyond simple vector similarity (full-text search,
    filtering, aggregations, relevance tuning at scale).
  - **How they'd work together**: Postgres stays the source of truth for
    every transaction (id, date, merchant, category, total, etc.).
    Elasticsearch holds a *search-optimized copy* of the text fields
    (merchant/category/description, and eventually raw receipt/document
    text) plus their embeddings, indexed by the same transaction `id`.
    `search_expenses` would query Elasticsearch to get back ranked
    candidate `id`s, then (if needed) join back to Postgres for the
    authoritative structured fields. Writes go to Postgres first (the
    `write_expense_record` flow), then the corresponding document is
    indexed/updated in Elasticsearch - the same "database + search index"
    split used in most production RAG systems, rather than asking one
    database to do both jobs well.

Neither is implemented yet - this is a documented direction, not current
behavior.

## UI layer - current state vs. planned

**Current state:** `app.py`, a minimal Streamlit chat interface - type a
question, see the answer, expand a panel to see which tools were called.
Built to be just enough to interact with the agent and collect real usage
data (see `SESSION_LOG.md`), not a production interface.

**Planned:** a React frontend. Streamlit is fast to build with but not
meant for a real product UI (styling, componentization, and multi-view
layouts - chat plus a future dashboard - get awkward fast in Streamlit).
React would sit in front of a proper API layer (not yet built either) that
wraps `agent.py`'s logic, rather than calling the agent functions directly
the way `app.py` does today.

## Summary: what's real today vs. what's planned

| | Collection | Analysis | Dashboarding |
|---|---|---|---|
| Logic | ✅ built (3 tools) | ✅ built (3 tools) | ❌ not started |
| Data store | ❌ flat JSON file, not Postgres | ❌ flat JSON file, not Postgres | ❌ not started |
| Search | ❌ `minsearch` (TF-IDF), not pgvector/Elasticsearch | ❌ `minsearch` (TF-IDF), not pgvector/Elasticsearch | n/a |
| UI | ✅ via Streamlit chat (`app.py`) | ✅ via Streamlit chat (`app.py`) | ❌ not started |
| Monitoring | ✅ Logfire | ✅ Logfire | n/a |
