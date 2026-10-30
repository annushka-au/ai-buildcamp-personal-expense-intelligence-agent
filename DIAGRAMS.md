# System Diagrams

Mermaid source for the five diagrams in `PROJECT_OVERVIEW.md` / `ARCHITECTURE.md`.
Renders natively on GitHub and in VS Code's Markdown preview. For a styled,
rendered version (ledger-exhibit treatment, RAG steps highlighted in red),
see the published artifact version of this page.

## 1. Context Diagram

What crosses the system boundary, and in which direction.

```mermaid
graph TD
    User[Household User]
    System[["Expense Agent<br/>(agent.py · app.py)"]]
    LLM[OpenAI API<br/>gpt-4o-mini]
    Logfire[Logfire]
    Store[(Data Store<br/>today: flat file)]

    User <-->|"upload / ask ⇄ answer"| System
    System <-->|"prompt + tools ⇄ completion"| LLM
    System -->|"trace + cost event"| Logfire
    System <-->|"read / write ⇄ records"| Store
```

## 2. Data Flow Diagram

Collection only writes; analysis only reads. Both touch one store.

```mermaid
flowchart TB
    subgraph Collection
        U1[User] -->|upload| Extract[Extract fields<br/>LLM reasoning]
        Extract --> Dedupe[Check duplicate]
    end

    subgraph Analysis
        U2[User] -->|question| Select[Select &amp; run tool<br/>search · query · recurring]
        Select --> Compose[Compose answer]
        Compose -->|answer| U2
    end

    DataStore[(Data Store<br/>expenses.json)]

    Dedupe -->|"write record (if new)"| DataStore
    Select <-->|"read / records"| DataStore
```

## 3. Data Structure Diagram (today vs. planned)

Same six fields either way — the real change is splitting source of truth
from search copy.

```mermaid
flowchart LR
    subgraph Today
        J["expenses.json<br/>id, date, merchant,<br/>category, description, total"]
        I[("in-memory TF-IDF index<br/>(minsearch)")]
        J -.->|built from| I
    end

    subgraph Planned
        PG["PostgreSQL · expenses<br/>id (PK), date, merchant,<br/>category, description, total"]
        ES["Elasticsearch · expenses_search<br/>id, merchant_text, category_text,<br/>description_text, embedding"]
        PG <-->|"joined by id ·<br/>indexed after write"| ES
    end
```

## 4. User Behaviour Diagram

The routing decision: document vs. question, then which kind of question.
The `search_expenses` path is the RAG path.

```mermaid
flowchart TD
    Start([User sends a message]) --> Doc{Document<br/>attached?}

    Doc -->|yes| Read[Read &amp; extract fields]
    Read --> Dup[Check duplicate]
    Dup --> Write[Store record]
    Write --> Confirm([Confirmation shown])

    Doc -->|no| Kind{What kind of<br/>question?}
    Kind -->|"open-ended / why"| Search[search_expenses<br/>RAG retrieval]
    Kind -->|exact number| Query[query_expenses]
    Kind -->|subscriptions / recurring| Recur[find_recurring_charges]

    Search --> Answer([Answer grounded in data])
    Query --> Answer
    Recur --> Answer

    style Search fill:#A23A28,color:#fff,stroke:#7a2a1e
```

## 5. Business Flow Diagram — with RAG

One open-ended question, end to end. The RAG hop (retrieve, then assemble
context) sits between two separate model calls — the first never sees the
data, the second never searches.

```mermaid
flowchart LR
    U[User asks question] --> A1["Agent: choose tool<br/>(LLM call 1)"]
    A1 --> S["search_expenses:<br/>retrieve matches<br/>(tool call)"]
    S --> C["Context assembled<br/>from retrieved rows"]
    C --> A2["Agent: generate answer<br/>(LLM call 2)"]
    A2 --> U

    style S fill:#A23A28,color:#fff,stroke:#7a2a1e
    style C fill:#A23A28,color:#fff,stroke:#7a2a1e
```

Every step above (both LLM calls and the tool call) is captured as its own
span inside one Logfire trace per session, with a `session_cost` event
totalling token usage across both LLM calls.
