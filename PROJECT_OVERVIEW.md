% Personal Expense Intelligence Agent
% Project Overview & Technical Roadmap
% 2026-10-30

# 1. Executive Summary

The Personal Expense Intelligence Agent is an AI system that turns everyday
household paperwork — receipts, bills, invoices — into structured financial
data, and lets the household ask questions about their own spending in plain
language instead of maintaining a spreadsheet.

The project is organized around three distinct directions: **collecting**
data from documents, **analysing** that data through natural-language
conversation, and **dashboarding** it visually. The first two are built and
working today, powered by a tool-using AI agent and a retrieval-augmented
question-answering flow. The third — a visual dashboard — is a planned
future direction and has not yet been started.

This document describes the aim of the project, how each of the three
directions works, where the system's AI techniques (retrieval-augmented
generation, autonomous tool use) are applied, and the technical path from
today's lightweight prototype to a production-ready data and interface
layer.

---

# 2. Aim and Objectives

## 2.1 The Problem

Individuals and households want to understand their spending, but manually
entering every transaction from receipts, bills, and invoices is tedious,
and most people give up on it. Without structured data, it is hard to
answer even simple questions such as *"Why did I spend more this month?"*
or *"How much did I spend on groceries in September?"*

## 2.2 The Aim

Remove the manual data-entry burden, and replace it with a conversational
interface that can explain spending the way a knowledgeable friend would —
grounded in the household's real transactions, never guessing.

## 2.3 Objectives

- Convert unstructured documents into structured, queryable transaction
  records with minimal manual effort.
- Correctly answer both **exact** questions (totals, comparisons, specific
  charges) and **open-ended** questions (explanations, patterns, anomalies).
- Ground every answer in real transaction data — the system must never
  invent a dollar figure it cannot point back to.
- Keep the system fully observable: what the agent did, which tools it
  used, and what each interaction cost, for every single session.

---

# 3. The Three Directions

The project is organized around three flows. Today, the first two are
implemented, sharing one agent process. The third is a documented future
direction, not yet started.

**Direction 1 — Collection.** A user uploads a receipt, bill, or invoice.
The system reads it, extracts the key fields, checks it isn't a duplicate,
and stores it as a structured record.

**Direction 2 — Analysis.** A user asks a question in natural language. The
system decides which underlying tool best answers it — a semantic search
over transaction text, an exact calculation, or a pattern-detection pass
over recurring charges — and answers grounded in the real data it retrieves.

**Direction 3 — Dashboarding.** A visual, always-available view of the same
underlying spending data: trends by category and month, budget comparisons,
anomaly flags. This complements the conversational interface rather than
replacing it — chat answers a specific question, a dashboard shows the
overall shape of spending at a glance. **Not yet built.**

## 3.1 Direction 1: Collection, in detail

This is the **write-heavy** side of the system — the only flow that
modifies stored data. The flow has four steps:

1. The raw content of the uploaded document is retrieved.
2. **The language model itself extracts the structured fields** — merchant,
   date, category, description, and total — as part of its own reasoning
   over the document text. This is a deliberate design choice: extraction
   is not a separate, rigid pipeline step, but part of the model's
   judgment, the same way a person reading a receipt would identify the
   relevant details.
3. The system checks whether an identical transaction (same merchant, date,
   and amount) already exists, to prevent double-counting a document
   uploaded more than once.
4. Only once extraction is complete and the duplicate check has passed is
   the new record permanently stored.

## 3.2 Direction 2: Analysis, in detail

This is the **read-only** side of the system. When a user asks a question,
the agent chooses between three ways of answering it:

- **Semantic search** over the wording of each transaction (merchant,
  category, description) — used for open-ended or explanatory questions,
  where retrieving the most relevant transactions and reasoning over them
  produces a better answer than a rigid calculation. This is the project's
  **retrieval-augmented generation (RAG)** component: the model is given
  real, retrieved transaction data as context, and answers from that
  context rather than from its own prior knowledge or guesswork.
- **Exact filtering and aggregation** — used whenever the answer needs a
  real, deterministic number: a total, a month-over-month comparison, or a
  check for a specific charge.
- **Recurring-charge detection** — groups transactions by merchant across
  months and flags ones that repeat at a similar amount, to surface
  subscriptions and recurring bills the user may have forgotten about.

## 3.3 Direction 3: Dashboarding, in detail

Not yet scoped or started. The intended purpose is a visual complement to
the chat interface: spending broken down by category and month at a glance,
trend lines over time, budget-versus-actual comparisons, and anomaly
highlights — all drawing on the same underlying data the conversational
agent already reasons over, so the two views never disagree with each
other.

---

# 4. Where the AI Techniques Are Used

| Technique | Role in this project |
|---|---|
| **Autonomous agent** | A tool-using agent loop decides, per user message, which action to take next — search, calculate, or write — rather than following a fixed script. The same underlying loop currently serves both the Collection and Analysis directions, which are conceptually two separate agent roles sharing one process today. |
| **Tools** | Each agent action is a discrete, named tool with a defined input and output, grouped into three kinds: tools that *search* unstructured text, tools that *fetch and read* structured data, and the one tool that *writes* new data. Keeping these separate and explicit is what allows the agent's reasoning to stay auditable — every action it takes is a visible, named step, not a hidden side effect. |
| **Retrieval-augmented generation (RAG)** | The semantic-search tool retrieves the transactions most relevant to a question and gives them to the model as grounding context before it answers — the model is reasoning over real retrieved data, not recalling facts from its own training. |
| **Observability / monitoring** | Every single interaction — every model call, every tool call, and the full conversation session — is captured as a structured trace, along with the exact token usage and cost for that session. Nothing the system does is a black box; every answer can be traced back to exactly what the agent did to produce it. |

---

# 5. Current State vs. Planned Architecture

## 5.1 Data Layer

**Current state.** There is, today, no real database. All transaction
records live in a single flat data file, loaded entirely into memory and
indexed for search at startup. This is adequate for a small synthetic
dataset and a single-user prototype, but it will not scale: it has no real
schema or constraints, no safe concurrent writes, and a search quality
ceiling well below a proper retrieval system.

**Planned.** The data layer is intended to move to **PostgreSQL** as the
system of record for structured transaction data — replacing today's flat
file with real schema, constraints, and the ability to run true SQL
aggregation instead of looping over records in application code.

For the semantic-search side of the system, two complementary paths are
under consideration, and they are not mutually exclusive:

- **pgvector**, a PostgreSQL extension that stores vector embeddings
  directly alongside the structured row they describe. This keeps the
  entire system on one engine, with one connection and one transactional
  boundary — operationally the simplest path.
- **Elasticsearch**, a dedicated search and vector engine, better suited if
  retrieval needs grow beyond simple similarity search — richer full-text
  search, filtering, and relevance tuning at scale.

**How PostgreSQL and Elasticsearch would work together**, if both are
used: PostgreSQL remains the single source of truth for every transaction —
its identifier, date, merchant, category, amount, and so on. Elasticsearch
holds a search-optimized *copy* of the text fields (and, eventually, raw
receipt text) plus their embeddings, indexed by that same transaction
identifier. The semantic-search tool would query Elasticsearch first to get
back a ranked list of candidate transaction identifiers, then join back to
PostgreSQL for the authoritative structured fields behind each one. New
writes flow to PostgreSQL first, and the corresponding search document is
then indexed or updated in Elasticsearch — the same "database plus search
index" split used in most production retrieval systems, rather than asking
a single database to serve both roles well.

## 5.2 Interface Layer

**Current state.** A minimal chat interface, built specifically to be just
enough to interact with the agent and start collecting real usage data for
evaluation — not intended as a production interface.

**Planned.** A **React** front end, sitting in front of a proper API layer
rather than calling the agent's internal functions directly. A dedicated
frontend framework is needed to support real styling, reusable components,
and multiple coordinated views — in particular, a chat view and the future
dashboard (Direction 3) living side by side, which becomes awkward in a
rapid-prototyping tool once a project outgrows the prototype stage.

---

# 6. Summary Status

| Direction | Core logic | Data store | Search backend | Interface | Monitoring |
|---|---|---|---|---|---|
| 1. Collection | Built | Flat file (planned: PostgreSQL) | — | Chat prototype (planned: React) | Built |
| 2. Analysis | Built | Flat file (planned: PostgreSQL) | In-memory keyword index (planned: pgvector / Elasticsearch) | Chat prototype (planned: React) | Built |
| 3. Dashboarding | Not started | — | — | Not started | — |

---

# 7. Roadmap at a Glance

1. **Today**: both agent flows working end to end against a small synthetic
   dataset, fully instrumented, with a minimal chat interface for testing
   and real-usage data collection.
2. **Next**: migrate the data layer to PostgreSQL; introduce semantic
   search via pgvector or Elasticsearch in place of the in-memory index.
3. **Then**: build the dashboard direction, surfacing the same underlying
   data visually.
4. **Then**: replace the prototype chat interface with a React front end
   serving both the chat and dashboard views through a proper API layer.
