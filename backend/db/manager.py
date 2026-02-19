"""
Diavgeia-Watch: Database Manager

Handles all PostgreSQL + pgvector operations:
- Inserting/upserting decisions and expense items
- Querying spending data
- Managing harvest state
- Storing embeddings for semantic search
"""

import logging
from typing import Optional
from datetime import date, datetime
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "diavgeia",
    "user": "diavgeia",
    "password": "diavgeia_dev_2024",
}


class DatabaseManager:
    """
    Manages all database operations for Diavgeia-Watch.

    Usage:
        db = DatabaseManager()
        db.connect()

        # Insert a decision
        db.upsert_decision(decision_dict)

        # Query spending
        results = db.query_spending(org_id="5001", year=2024)

        db.close()
    """

    def __init__(self, config: Optional[dict] = None, pool_size: int = 5):
        self.config = config or DEFAULT_DB_CONFIG
        self.pool: Optional[ThreadedConnectionPool] = None
        self.pool_size = pool_size

    def connect(self):
        """Initialize connection pool."""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                **self.config,
            )
            logger.info("Database connection pool created")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Close all connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connections closed")

    @contextmanager
    def get_cursor(self, commit: bool = True):
        """Context manager for database operations."""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
                if commit:
                    conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    # -----------------------------------------------------------
    # Decision CRUD
    # -----------------------------------------------------------

    def upsert_decision(self, decision: dict) -> Optional[int]:
        """
        Insert or update a decision from the Diavgeia API response.

        Expected dict structure (from api_client.search_decisions):
        {
            "ada": "Ψ4Ε2ΟΡΗ8-ΦΒ7",
            "subject": "Έγκριση δαπάνης...",
            "decisionTypeUid": "Β.2.1",
            "status": "PUBLISHED",
            "issueDate": "2024-01-15+02:00",
            "submissionTimestamp": "2024-01-15T10:30:00.000+02:00",
            "publishTimestamp": "2024-01-15T10:30:00.000+02:00",
            "organizationId": "5001",
            "url": "https://diavgeia.gov.gr/doc/...",
            "extraFieldValues": { ... }
        }

        Returns the decision ID, or None if skipped.
        """
        ada = decision.get("ada")
        if not ada:
            logger.warning("Decision missing ADA, skipping")
            return None

        # Parse dates safely
        issue_date = self._parse_date(decision.get("issueDate"))
        submission_ts = self._parse_timestamp(decision.get("submissionTimestamp"))
        publish_ts = self._parse_timestamp(decision.get("publishTimestamp"))

        # Extract organization info from extraFieldValues
        extra = decision.get("extraFieldValues", {})
        org_afm = None
        org_name_extra = None
        if isinstance(extra, dict):
            org_field = extra.get("org", {})
            if isinstance(org_field, dict):
                org_afm = org_field.get("afm")
                org_name_extra = org_field.get("name")

        with self.get_cursor() as cur:
            # Upsert the decision
            cur.execute("""
                INSERT INTO decisions (
                    ada, subject, decision_type, status,
                    issue_date, submission_ts, publish_ts,
                    org_id, org_name, org_afm,
                    document_url, raw_json
                ) VALUES (
                    %(ada)s, %(subject)s, %(decision_type)s, %(status)s,
                    %(issue_date)s, %(submission_ts)s, %(publish_ts)s,
                    %(org_id)s, %(org_name)s, %(org_afm)s,
                    %(document_url)s, %(raw_json)s
                )
                ON CONFLICT (ada) DO UPDATE SET
                    subject = EXCLUDED.subject,
                    status = EXCLUDED.status,
                    issue_date = EXCLUDED.issue_date,
                    submission_ts = EXCLUDED.submission_ts,
                    publish_ts = EXCLUDED.publish_ts,
                    org_name = EXCLUDED.org_name,
                    raw_json = EXCLUDED.raw_json,
                    updated_at = NOW()
                RETURNING id
            """, {
                "ada": ada,
                "subject": decision.get("subject"),
                "decision_type": decision.get("decisionTypeId") or decision.get("decisionTypeUid", "Β.2.1"),
                "status": decision.get("status"),
                "issue_date": issue_date,
                "submission_ts": submission_ts,
                "publish_ts": publish_ts,
                "org_id": str(decision.get("organizationId", "")),
                "org_name": org_name_extra or decision.get("organizationLabel"),
                "org_afm": org_afm,
                "document_url": decision.get("documentUrl") or decision.get("url"),
                "raw_json": psycopg2.extras.Json(decision),
            })

            row = cur.fetchone()
            decision_id = row["id"] if row else None

            # Parse and insert expense items (sponsors)
            if decision_id and isinstance(extra, dict):
                sponsors = extra.get("sponsor", [])
                if isinstance(sponsors, dict):
                    sponsors = [sponsors]  # single sponsor case

                # Delete existing expense items for this decision (for re-harvest)
                cur.execute(
                    "DELETE FROM expense_items WHERE decision_id = %s",
                    (decision_id,)
                )

                for sponsor in sponsors:
                    if not isinstance(sponsor, dict):
                        continue
                    self._insert_expense_item(cur, decision_id, ada, sponsor)

            return decision_id

    def _insert_expense_item(self, cur, decision_id: int, ada: str, sponsor: dict):
        """Insert a single expense item from a sponsor entry."""
        # Extract contractor info
        afm_name = sponsor.get("sponsorAFMName", {})
        if not isinstance(afm_name, dict):
            afm_name = {}

        contractor_afm = afm_name.get("afm")
        contractor_name = afm_name.get("name")

        # Extract amount
        expense = sponsor.get("expenseAmount", {})
        if not isinstance(expense, dict):
            expense = {}

        amount = expense.get("amount")
        currency = expense.get("currency", "EUR")

        # Extract CPV and KAE
        cpv_code = sponsor.get("cpv")
        kae_code = sponsor.get("kae")

        if amount is not None:
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                amount = None

        cur.execute("""
            INSERT INTO expense_items (
                decision_id, ada,
                contractor_afm, contractor_name,
                amount, currency,
                cpv_code, kae_code
            ) VALUES (
                %(decision_id)s, %(ada)s,
                %(contractor_afm)s, %(contractor_name)s,
                %(amount)s, %(currency)s,
                %(cpv_code)s, %(kae_code)s
            )
        """, {
            "decision_id": decision_id,
            "ada": ada,
            "contractor_afm": contractor_afm,
            "contractor_name": contractor_name,
            "amount": amount,
            "currency": currency,
            "cpv_code": cpv_code,
            "kae_code": kae_code,
        })

    # -----------------------------------------------------------
    # Organization Cache
    # -----------------------------------------------------------

    def upsert_organization(self, org: dict):
        """Cache an organization from the API."""
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO organizations (uid, label, abbreviation, parent_uid, category)
                VALUES (%(uid)s, %(label)s, %(abbreviation)s, %(parent_uid)s, %(category)s)
                ON CONFLICT (uid) DO UPDATE SET
                    label = EXCLUDED.label,
                    abbreviation = EXCLUDED.abbreviation,
                    updated_at = NOW()
            """, {
                "uid": str(org.get("uid", "")),
                "label": org.get("label"),
                "abbreviation": org.get("abbreviation"),
                "parent_uid": str(org.get("parentId", "")) or None,
                "category": org.get("category"),
            })

    # -----------------------------------------------------------
    # Harvest Log
    # -----------------------------------------------------------

    def start_harvest(self, harvest_date: date, decision_type: str) -> int:
        """Record the start of a harvest run. Returns harvest log ID."""
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO harvest_log (harvest_date, decision_type, status)
                VALUES (%s, %s, 'RUNNING')
                RETURNING id
            """, (harvest_date, decision_type))
            return cur.fetchone()["id"]

    def finish_harvest(
        self, harvest_id: int, found: int, saved: int, status: str = "COMPLETED"
    ):
        """Record the end of a harvest run."""
        with self.get_cursor() as cur:
            cur.execute("""
                UPDATE harvest_log
                SET decisions_found = %s, decisions_saved = %s,
                    status = %s, finished_at = NOW()
                WHERE id = %s
            """, (found, saved, status, harvest_id))

    def get_last_harvest_date(self, decision_type: str = "Β.2.1") -> Optional[date]:
        """Get the most recent successfully harvested date."""
        with self.get_cursor() as cur:
            cur.execute("""
                SELECT MAX(harvest_date) as last_date
                FROM harvest_log
                WHERE decision_type = %s AND status = 'COMPLETED'
            """, (decision_type,))
            row = cur.fetchone()
            return row["last_date"] if row else None

    # -----------------------------------------------------------
    # Query Methods (for the agent / dashboard)
    # -----------------------------------------------------------

    def query_spending(
        self,
        org_id: Optional[str] = None,
        year: Optional[int] = None,
        cpv_prefix: Optional[str] = None,
        contractor_afm: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Flexible spending query for the dashboard and agent.

        Returns aggregated spending data matching the filters.
        """
        conditions = []
        params = {}

        if org_id:
            conditions.append("d.org_id = %(org_id)s")
            params["org_id"] = org_id
        if year:
            conditions.append("EXTRACT(YEAR FROM d.issue_date) = %(year)s")
            params["year"] = year
        if cpv_prefix:
            conditions.append("e.cpv_code LIKE %(cpv_prefix)s")
            params["cpv_prefix"] = f"{cpv_prefix}%"
        if contractor_afm:
            conditions.append("e.contractor_afm = %(contractor_afm)s")
            params["contractor_afm"] = contractor_afm
        if min_amount is not None:
            conditions.append("e.amount >= %(min_amount)s")
            params["min_amount"] = min_amount
        if max_amount is not None:
            conditions.append("e.amount <= %(max_amount)s")
            params["max_amount"] = max_amount

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params["limit"] = limit

        query = f"""
            SELECT
                d.org_id, d.org_name,
                e.contractor_afm, e.contractor_name,
                e.cpv_code,
                COUNT(DISTINCT d.ada) AS num_decisions,
                SUM(e.amount) AS total_amount,
                MIN(d.issue_date) AS first_date,
                MAX(d.issue_date) AS last_date
            FROM decisions d
            JOIN expense_items e ON e.decision_id = d.id
            {where}
            GROUP BY d.org_id, d.org_name,
                     e.contractor_afm, e.contractor_name, e.cpv_code
            ORDER BY total_amount DESC NULLS LAST
            LIMIT %(limit)s
        """

        with self.get_cursor(commit=False) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def get_total_spending_by_org(self, year: Optional[int] = None) -> list[dict]:
        """Get total spending per organization."""
        params = {}
        where = ""
        if year:
            where = "WHERE EXTRACT(YEAR FROM d.issue_date) = %(year)s"
            params["year"] = year

        query = f"""
            SELECT
                d.org_id, d.org_name,
                COUNT(DISTINCT d.ada) AS num_decisions,
                SUM(e.amount) AS total_amount
            FROM decisions d
            JOIN expense_items e ON e.decision_id = d.id
            {where}
            GROUP BY d.org_id, d.org_name
            ORDER BY total_amount DESC NULLS LAST
            LIMIT 50
        """

        with self.get_cursor(commit=False) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def get_stats(self) -> dict:
        """Get basic database statistics."""
        with self.get_cursor(commit=False) as cur:
            stats = {}

            cur.execute("SELECT COUNT(*) as count FROM decisions")
            stats["total_decisions"] = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM expense_items")
            stats["total_expense_items"] = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(DISTINCT org_id) as count FROM decisions"
            )
            stats["unique_organizations"] = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(DISTINCT contractor_afm) as count "
                "FROM expense_items WHERE contractor_afm IS NOT NULL"
            )
            stats["unique_contractors"] = cur.fetchone()["count"]

            cur.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expense_items"
            )
            stats["total_amount"] = float(cur.fetchone()["total"])

            cur.execute(
                "SELECT MIN(issue_date) as min_date, MAX(issue_date) as max_date "
                "FROM decisions"
            )
            row = cur.fetchone()
            stats["date_range"] = {
                "from": str(row["min_date"]) if row["min_date"] else None,
                "to": str(row["max_date"]) if row["max_date"] else None,
            }

            return stats

    # -----------------------------------------------------------
    # Embeddings (prep for Phase 2)
    # -----------------------------------------------------------

    def store_embedding(self, decision_id: int, ada: str, text: str, embedding: list):
        """Store a text embedding for semantic search."""
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO decision_embeddings (decision_id, ada, text_chunk, embedding)
                VALUES (%s, %s, %s, %s)
            """, (decision_id, ada, text, embedding))

    def semantic_search(self, query_embedding: list, limit: int = 10) -> list[dict]:
        """Find decisions most similar to a query embedding."""
        with self.get_cursor(commit=False) as cur:
            cur.execute("""
                SELECT
                    de.ada,
                    de.text_chunk,
                    d.subject,
                    d.org_name,
                    1 - (de.embedding <=> %s::vector) AS similarity
                FROM decision_embeddings de
                JOIN decisions d ON d.id = de.decision_id
                ORDER BY de.embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, limit))
            return cur.fetchall()

    # -----------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------

    @staticmethod
    def _parse_date(date_str) -> Optional[date]:
        """Parse Diavgeia date formats: epoch millis (1733436000000) or ISO '2024-01-15+02:00'."""
        if not date_str:
            return None
        try:
            # Epoch milliseconds (number or numeric string)
            if isinstance(date_str, (int, float)) or (isinstance(date_str, str) and date_str.isdigit()):
                ts = int(date_str) / 1000.0
                return datetime.fromtimestamp(ts).date()
            # ISO date string
            clean = str(date_str).split("+")[0].split("T")[0]
            return datetime.strptime(clean, "%Y-%m-%d").date()
        except (ValueError, AttributeError, OSError):
            logger.warning(f"Could not parse date: {date_str}")
            return None

    @staticmethod
    def _parse_timestamp(ts_str) -> Optional[datetime]:
        """Parse Diavgeia timestamp: epoch millis or ISO '2024-01-15T10:30:00.000+02:00'."""
        if not ts_str:
            return None
        try:
            # Epoch milliseconds (number or numeric string)
            if isinstance(ts_str, (int, float)) or (isinstance(ts_str, str) and ts_str.isdigit()):
                ts = int(ts_str) / 1000.0
                return datetime.fromtimestamp(ts)
            # ISO timestamp string
            clean = str(ts_str).replace("+02:00", "+0200").replace("+03:00", "+0300")
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
            ]:
                try:
                    return datetime.strptime(clean, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, AttributeError, OSError):
            logger.warning(f"Could not parse timestamp: {ts_str}")
            return None