"""
Diavgeia-Watch: FastAPI Server (Phase 4)

REST API that wraps the existing SQL agent and database
for the Next.js frontend dashboard.

Run:
    uvicorn backend.api_server:app --reload --port 8000

Or:
    python -m backend.api_server
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db.manager import DatabaseManager
from backend.agent.llm_client import LLMClient
from backend.agent.sql_agent import SQLAgent
from backend.agent.cpv_lookup import CPVLookup
from backend.agent.org_resolver import OrgResolver
logger = logging.getLogger(__name__)

# ============================================================
# Globals (initialized on startup)
# ============================================================
db: Optional[DatabaseManager] = None
agent: Optional[SQLAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and agent on startup, clean up on shutdown."""
    global db, agent

    # Database
    db = DatabaseManager()
    db.connect()
    logger.info("Database connected")

    # LLM
    backend = os.getenv("LLM_BACKEND", "groq")
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")

    kwargs = {"backend": backend}
    if api_key:
        kwargs["api_key"] = api_key
    if model:
        kwargs["model"] = model

    llm = LLMClient(**kwargs)
    if not llm.is_available():
        logger.warning(f"LLM backend '{backend}' is not available!")
    else:
        logger.info(f"LLM connected: {backend} / {llm.model}")

    # Agent
    agent = SQLAgent(
        llm=llm,
        db=db,
        cpv_lookup=CPVLookup(),
        org_resolver=OrgResolver(db_manager=db),
    )

    yield

    # Shutdown
    if db:
        db.close()
        logger.info("Database closed")


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Diavgeia-Watch API",
    description="Greek government spending intelligence",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request/Response Models
# ============================================================

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    thinking: Optional[str] = None
    explanation: Optional[str] = None
    data: Optional[list] = None
    success: bool = True
    error: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def get_stats():
    """Database overview statistics."""
    stats = db.get_stats()
    return stats


@app.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    """Ask a natural language question about government spending."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = agent.ask(req.question)
    return AskResponse(
        answer=result.answer,
        sql=result.sql,
        thinking=result.thinking,
        explanation=result.explanation,
        data=result.data,
        success=result.success,
        error=result.error,
    )


@app.get("/api/top-spenders")
def top_spenders(limit: int = 10):
    """Top organizations by total spending."""
    sql = """
        SELECT d.org_name, SUM(e.amount) AS total, COUNT(DISTINCT d.ada) AS decisions
        FROM decisions d
        JOIN expense_items e ON e.decision_id = d.id
        GROUP BY d.org_name
        ORDER BY total DESC
        LIMIT %s
    """
    try:
        with db.get_cursor(commit=False) as cur:
            cur.execute(sql, (limit,))
            rows = [dict(row) for row in cur.fetchall()]
        return {"data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/top-contractors")
def top_contractors(limit: int = 10):
    """Top contractors by total amount received."""
    sql = """
        SELECT e.contractor_name, e.contractor_afm,
               SUM(e.amount) AS total, COUNT(DISTINCT e.ada) AS contracts
        FROM expense_items e
        WHERE e.contractor_name IS NOT NULL AND e.contractor_name != ''
        GROUP BY e.contractor_name, e.contractor_afm
        ORDER BY total DESC
        LIMIT %s
    """
    try:
        with db.get_cursor(commit=False) as cur:
            cur.execute(sql, (limit,))
            rows = [dict(row) for row in cur.fetchall()]
        return {"data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spending-by-date")
def spending_by_date():
    """Daily spending totals for chart visualization."""
    sql = """
        SELECT d.issue_date, SUM(e.amount) AS total, COUNT(DISTINCT d.ada) AS decisions
        FROM decisions d
        JOIN expense_items e ON e.decision_id = d.id
        WHERE d.issue_date IS NOT NULL
        GROUP BY d.issue_date
        ORDER BY d.issue_date
    """
    try:
        with db.get_cursor(commit=False) as cur:
            cur.execute(sql)
            rows = []
            for row in cur.fetchall():
                d = dict(row)
                d["issue_date"] = d["issue_date"].isoformat() if d["issue_date"] else None
                d["total"] = float(d["total"]) if d["total"] else 0
                rows.append(d)
        return {"data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/anomalies")
def detect_anomalies():
    """Detect potential anomalies in spending."""
    anomalies = []
    try:
        with db.get_cursor(commit=False) as cur:
            # 1. Contract splitting
            cur.execute("""
                SELECT d.org_name, e.contractor_name, COUNT(*) AS contract_count,
                       SUM(e.amount) AS total, AVG(e.amount) AS avg_amount,
                       MAX(e.amount) AS max_amount
                FROM decisions d
                JOIN expense_items e ON e.decision_id = d.id
                WHERE e.contractor_name IS NOT NULL AND e.contractor_name != ''
                GROUP BY d.org_name, e.contractor_name
                HAVING COUNT(*) >= 3 AND MAX(e.amount) < 20000
                ORDER BY COUNT(*) DESC
                LIMIT 20
            """)
            for row in cur.fetchall():
                d = dict(row)
                d["total"] = float(d["total"])
                d["avg_amount"] = float(d["avg_amount"])
                d["max_amount"] = float(d["max_amount"])
                anomalies.append({
                    "type": "contract_splitting",
                    "severity": "high" if d["contract_count"] >= 5 else "medium",
                    "title": f"Possible contract splitting: {d['contractor_name'][:40]}",
                    "description": f"{d['contract_count']} contracts with {d['org_name'][:30]}, avg €{d['avg_amount']:,.0f}, total €{d['total']:,.0f}",
                    "data": d,
                })

            # 2. Threshold gaming
            cur.execute("""
                SELECT d.org_name, e.contractor_name, e.amount, d.ada, d.subject
                FROM decisions d
                JOIN expense_items e ON e.decision_id = d.id
                WHERE e.amount BETWEEN 19000 AND 20000
                ORDER BY e.amount DESC
                LIMIT 20
            """)
            for row in cur.fetchall():
                d = dict(row)
                d["amount"] = float(d["amount"])
                anomalies.append({
                    "type": "threshold_gaming",
                    "severity": "medium",
                    "title": f"Near-threshold: €{d['amount']:,.0f}",
                    "description": f"{d['contractor_name'][:30]} → {d['org_name'][:30]}, ADA: {d['ada']}",
                    "data": d,
                })

            # 3. Concentration
            cur.execute("""
                WITH org_totals AS (
                    SELECT d.org_name, SUM(e.amount) AS org_total
                    FROM decisions d JOIN expense_items e ON e.decision_id = d.id
                    GROUP BY d.org_name
                    HAVING SUM(e.amount) > 50000
                ),
                contractor_by_org AS (
                    SELECT d.org_name, e.contractor_name, SUM(e.amount) AS contractor_total
                    FROM decisions d JOIN expense_items e ON e.decision_id = d.id
                    WHERE e.contractor_name IS NOT NULL AND e.contractor_name != ''
                    GROUP BY d.org_name, e.contractor_name
                )
                SELECT c.org_name, c.contractor_name, c.contractor_total, o.org_total,
                       ROUND(100.0 * c.contractor_total / o.org_total, 1) AS pct
                FROM contractor_by_org c
                JOIN org_totals o ON o.org_name = c.org_name
                WHERE c.contractor_total > 0.5 * o.org_total
                ORDER BY pct DESC
                LIMIT 15
            """)
            for row in cur.fetchall():
                d = dict(row)
                d["contractor_total"] = float(d["contractor_total"])
                d["org_total"] = float(d["org_total"])
                d["pct"] = float(d["pct"])
                anomalies.append({
                    "type": "concentration",
                    "severity": "high" if d["pct"] > 70 else "medium",
                    "title": f"{d['pct']}% concentration",
                    "description": f"{d['contractor_name'][:30]} gets {d['pct']}% of {d['org_name'][:30]}'s spending (€{d['contractor_total']:,.0f} / €{d['org_total']:,.0f})",
                    "data": d,
                })

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    anomalies.sort(key=lambda a: severity_order.get(a["severity"], 2))
    return {"anomalies": anomalies, "count": len(anomalies)}


@app.get("/api/recent-decisions")
def recent_decisions(limit: int = 20):
    """Most recent decisions with amounts."""
    sql = """
        SELECT d.ada, d.subject, d.org_name, d.issue_date,
               SUM(e.amount) AS total_amount
        FROM decisions d
        JOIN expense_items e ON e.decision_id = d.id
        WHERE d.issue_date IS NOT NULL
        GROUP BY d.ada, d.subject, d.org_name, d.issue_date
        ORDER BY d.issue_date DESC
        LIMIT %s
    """
    try:
        with db.get_cursor(commit=False) as cur:
            cur.execute(sql, (limit,))
            rows = []
            for row in cur.fetchall():
                d = dict(row)
                d["issue_date"] = d["issue_date"].isoformat() if d["issue_date"] else None
                d["total_amount"] = float(d["total_amount"]) if d["total_amount"] else 0
                rows.append(d)
        return {"data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/network")
def get_network(min_amount: float = 10000, max_edges: int = 80):
    """
    Network graph data: org → contractor spending relationships.
    Returns nodes and edges for a force-directed graph.
    """
    sql = """
        WITH edges AS (
            SELECT
                d.org_name,
                e.contractor_name,
                SUM(e.amount) AS total,
                COUNT(DISTINCT d.ada) AS contracts
            FROM decisions d
            JOIN expense_items e ON e.decision_id = d.id
            WHERE e.contractor_name IS NOT NULL AND e.contractor_name != ''
              AND d.org_name IS NOT NULL AND d.org_name != ''
              AND e.amount > 0
            GROUP BY d.org_name, e.contractor_name
            HAVING SUM(e.amount) >= %s
            ORDER BY total DESC
            LIMIT %s
        )
        SELECT * FROM edges
    """
    try:
        conn = db.pool.getconn()
        cur = conn.cursor()
        cur.execute(sql, (min_amount, max_edges))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        db.pool.putconn(conn)

        # Build unique nodes and edges
        orgs = set()
        contractors = set()
        edges = []

        for row in rows:
            org = row["org_name"]
            con = row["contractor_name"]
            orgs.add(org)
            contractors.add(con)
            edges.append({
                "source": org,
                "target": con,
                "amount": float(row["total"]),
                "contracts": row["contracts"],
            })

        nodes = []
        # Calculate total for sizing
        org_totals = {}
        con_totals = {}
        for e in edges:
            org_totals[e["source"]] = org_totals.get(e["source"], 0) + e["amount"]
            con_totals[e["target"]] = con_totals.get(e["target"], 0) + e["amount"]

        for org in orgs:
            nodes.append({
                "id": org,
                "type": "org",
                "total": org_totals.get(org, 0),
            })
        for con in contractors:
            nodes.append({
                "id": con,
                "type": "contractor",
                "total": con_totals.get(con, 0),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "org_count": len(orgs),
                "contractor_count": len(contractors),
                "edge_count": len(edges),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Run directly
# ============================================================
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "backend.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )