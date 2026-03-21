# DiavgeiaWatch

**AI-powered analysis of Greek government spending data**

DiavgeiaWatch harvests public expenditure decisions from Greece's [Diavgeia](https://diavgeia.gov.gr) transparency portal, stores them in PostgreSQL, and lets you explore them through natural language queries (in Greek or English) and an interactive dashboard.

---

## What It Does

Ask questions like _"Πόσο κόστισε η καθαριότητα στο Δήμο Αθηναίων;"_ or _"Top 10 contractors by total spending"_ and get answers backed by real government data. The system translates your question into SQL, runs it against the database, and returns a human-readable answer along with the generated query.

The dashboard provides at-a-glance views of total spending, anomaly detection (contract splitting, threshold gaming, vendor concentration), top contractors, spending trends over time, and a force-directed network graph showing org→contractor spending relationships.

---

## What's Implemented

### Data Ingestion

- **Diavgeia API Client** — wraps the public Diavgeia Open Data API with automatic pagination, rate limiting, and retry logic.
- **ETL Pipeline** — orchestrates day-by-day harvesting of government decisions. Supports filtering by date range, decision type, and organization. Tracks harvest state so it can resume from where it left off.
- **Data Maintenance Scripts** — backfill missing organization names (via Diavgeia API lookups), fix decision types from raw JSON, and harvest full months across all major decision types (`Β.2.1` expenditures, `Β.1.3` commitments, `Δ.1` contracts).
- **PostgreSQL Schema** — normalized schema with `decisions`, `expense_items`, `organizations`, and `harvest_log` tables. Includes trigram indexes for fuzzy Greek text search and pre-built views for spending summaries and near-threshold contract detection.

### AI Query Agent

- **Text-to-SQL Agent** — takes a natural language question (Greek or English), uses an LLM to generate a safe read-only SQL query, executes it, and formats the results as a natural language answer. Includes a hallucination guard that strips LLM-invented WHERE clauses the user never asked for, plus retry logic for malformed responses.
- **LLM Client** — unified abstraction over Ollama (local), Groq (cloud, free tier), and any OpenAI-compatible API. Swap backends by changing a single environment variable.
- **CPV Lookup** — resolves natural language spending categories (e.g. "καθαριότητα", "road maintenance") to EU Common Procurement Vocabulary codes using keyword matching with Greek and English support.
- **Organization Resolver** — maps informal organization names ("Αθήνα", "Athens", "ΕΡΤ") to their official Diavgeia UIDs. Combines a hardcoded database of ~50 major organizations with trigram-based fuzzy search against the organizations table.

### Bureaucratic Intelligence

- **Glossary Engine** — recognizes Greek bureaucratic terminology (απευθείας ανάθεση, ανάληψη υποχρέωσης, σύμβαση, etc.) and injects SQL hints and context into the LLM prompt so queries about procurement processes produce correct filters.
- **KAE/ALE Budget Code Detection** — extracts and interprets Greek budget codes from queries.
- **AFM/ADA Detection** — recognizes tax IDs and Diavgeia decision IDs in user questions.
- **Accent-Insensitive Matching** — handles Greek accent variations so that differently accented forms of the same word all match.
- **Procurement Threshold Awareness** — provides context about Greek procurement thresholds (direct award limits, simplified tender limits, EU thresholds) when relevant.

### Dashboard & API

- **FastAPI REST API** with endpoints for:
  - `GET /api/stats` — database overview (total decisions, organizations, contractors, spending)
  - `POST /api/ask` — natural language query endpoint
  - `GET /api/top-spenders` — top organizations by spending
  - `GET /api/top-contractors` — top contractors by amount received
  - `GET /api/spending-by-date` — daily spending totals for chart visualization
  - `GET /api/anomalies` — automated anomaly detection (contract splitting, threshold gaming, vendor concentration)
  - `GET /api/recent-decisions` — most recent decisions with amounts
  - `GET /api/network` — network graph data for org→contractor relationships
  - `GET /api/health` — health check

- **Next.js Frontend Dashboard** with:
  - **Stats Cards** — total spending, decisions processed, organizations, contractors
  - **Chat Panel** — conversational natural language query interface
  - **Spending Chart** — daily spending trends over time
  - **Top Contractors** — ranked list of largest vendors
  - **Anomaly Panel** — filterable anomaly alerts with severity levels
  - **Network Graph** — interactive force-directed SVG visualization of spending relationships with zoom/pan, draggable nodes, and adjustable minimum-amount threshold

---

## What's Planned

### Semantic Search (schema prepared, not yet populated)

The database schema already includes a `decision_embeddings` table with a pgvector column (`vector(384)`, matching `all-MiniLM-L6-v2`) and an IVFFlat index. The `DatabaseManager` has `store_embedding()` and `semantic_search()` methods ready. What remains is building the embedding pipeline that chunks decision text, generates embeddings, and populates this table,  enabling similarity-based queries alongside the current keyword/SQL approach.

### Additional Planned Features

- **Scheduled Harvesting** — automated daily/weekly data ingestion via cron or a task queue
- **User Authentication** — role-based access for the dashboard
- **Export & Reporting** — downloadable CSV/PDF reports of query results
- **Historical Trend Analysis** — year-over-year comparisons and spending trajectory visualization
- **Alerting System** — notifications when anomalies are detected in newly harvested data
- **Multi-language Dashboard UI** — Greek and English interface toggle (backend already supports both languages for queries)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 16, pgvector, pg_trgm |
| Backend | Python, FastAPI, psycopg2 |
| AI / NLP | Groq (default) or Ollama or any OpenAI-compatible LLM |
| Frontend | Next.js 14, React, Tailwind CSS, Recharts, Lucide icons |
| Data Source | [Diavgeia Open Data API](https://diavgeia.gov.gr/luminapi/opendata) |
| Infrastructure | Docker Compose |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- An LLM backend: either a [Groq API key](https://console.groq.com) (free tier available) or [Ollama](https://ollama.ai) running locally

### 1. Start the Database

```bash
docker compose up -d
```

This launches PostgreSQL 16 with pgvector and automatically runs the schema initialization.

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — set GROQ_API_KEY if using Groq, or configure Ollama
```

### 3. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 4. Harvest Data

```bash
# Harvest the last 7 days of expenditure decisions
python -m backend.ingestion.etl_pipeline

# Or harvest a specific month (all decision types)
python -m backend.ingestion.data_fix --harvest-month 2024-12

# Check data coverage
python -m backend.ingestion.data_fix --stats
```

### 5. Run the Application

```bash
# Start the API server
uvicorn backend.api.server:app --reload --port 8000

# In another terminal, start the frontend
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to access the dashboard.

### 6. CLI Agent (optional)

For a terminal-based interactive REPL:

```bash
# With Groq
python -m backend.cli.run_agent --backend groq --api-key gsk_...

# With Ollama
python -m backend.cli.run_agent --backend ollama --model llama3.1:8b

# Single question
python -m backend.cli.run_agent -q "Top 5 contractors by spending"
```

---

## Project Structure

```
diavgeia-watch/
├── backend/
│   ├── agent/              # AI query layer
│   │   ├── sql_agent.py        # NL → SQL → answer pipeline
│   │   ├── llm_client.py       # Unified LLM abstraction (Groq/Ollama/OpenAI)
│   │   ├── cpv_lookup.py       # CPV code keyword matching
│   │   ├── org_resolver.py     # Organization name → UID resolution
│   │   └── bureaucracy.py      # Greek bureaucratic glossary & threshold context
│   ├── api/
│   │   └── server.py           # FastAPI REST API
│   ├── db/
│   │   ├── manager.py          # PostgreSQL connection pool & CRUD operations
│   │   └── init.sql            # Database schema (tables, indexes, views)
│   ├── ingestion/
│   │   ├── api_client.py       # Diavgeia Open Data API wrapper
│   │   ├── etl_pipeline.py     # ETL orchestrator (harvest → parse → store)
│   │   └── data_fix.py         # Backfill & maintenance scripts
│   ├── cli/
│   │   └── run_agent.py        # Interactive terminal REPL
│   └── tests/
│       ├── test_phase2.py      # CPV, org resolver, LLM, agent tests
│       └── test_phase3.py      # Bureaucratic intelligence tests
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx            # Main dashboard page
│   ├── components/
│   │   ├── ChatPanel.tsx       # NL query interface
│   │   ├── StatsCards.tsx      # Overview statistics
│   │   ├── SpendingChart.tsx   # Daily spending chart
│   │   ├── TopContractors.tsx  # Contractor ranking
│   │   ├── AnomalyPanel.tsx    # Anomaly detection alerts
│   │   └── NetworkGraph.tsx    # Force-directed spending network
│   └── lib/
│       └── api.ts              # API client & formatters
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Running Tests

```bash
# Phase 2: CPV lookup, org resolver, LLM connectivity, DB, end-to-end agent
python -m backend.tests.test_phase2

# Phase 3: Bureaucratic glossary, KAE detection, accent handling, agent integration
python -m backend.tests.test_phase3
```

---

## License

This project is for research and educational purposes. Data sourced from [Diavgeia](https://diavgeia.gov.gr) under Greece's open government data provisions.