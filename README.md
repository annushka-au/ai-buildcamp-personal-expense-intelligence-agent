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

3. Create a `.env` file from the template and add your API key:

       cp .env.example .env

4. Install dependencies:

       uv sync

5. Start Jupyter:

       uv run jupyter notebook

## Notebooks

- `notebooks/01-setup.ipynb` - smoke test that confirms your environment works
- `notebooks/02-rag.ipynb` - a minimal RAG baseline you can adapt to your own data

## Data

Put your project data in the `data/` folder. See `notebooks/02-rag.ipynb` for how to load it.
