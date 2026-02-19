"""
Diavgeia-Watch: Text-to-SQL Agent

The brain of the system. Takes natural language queries (Greek or English),
uses an LLM to translate them into SQL, executes against PostgreSQL,
and returns human-readable answers.

Architecture:
    User Query (Greek/English)
        → LLM interprets intent
        → Resolves organizations (name → UID)
        → Resolves CPV codes (concept → code)
        → Generates safe, read-only SQL
        → Executes against PostgreSQL
        → Formats results as natural language

Usage:
    from backend.agent_sql import SQLAgent
    from backend.llm_client import LLMClient
    from backend.db_manager import DatabaseManager

    agent = SQLAgent(
        llm=LLMClient(backend="ollama", model="llama3.1:8b"),
        db=DatabaseManager()
    )
    agent.db.connect()

    result = agent.ask("Πόσο κόστισε η καθαριότητα στο Δήμο Αθηναίων το 2024;")
    print(result["answer"])
    print(result["sql"])
"""

import re
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from backend.llm_client import LLMClient, LLMResponse, LLMClientError
from backend.db_manager import DatabaseManager
from backend.cpv_lookup import CPVLookup
from backend.org_resolver import OrgResolver
from backend.bureaucracy import BureaucracyLayer

logger = logging.getLogger(__name__)


# ============================================================
# System Prompt — teaches the LLM about our schema
# ============================================================

SYSTEM_PROMPT = """You generate PostgreSQL SELECT queries for a Greek government spending database (Diavgeia/Δι@ύγεια).

SCHEMA:
  decisions(id, ada TEXT UNIQUE, subject TEXT, decision_type TEXT, status TEXT, issue_date DATE, org_id TEXT, org_name TEXT, org_afm TEXT, document_url TEXT)
  expense_items(id, decision_id BIGINT FK->decisions.id, ada TEXT, contractor_afm TEXT, contractor_name TEXT, amount NUMERIC, currency TEXT, cpv_code TEXT, kae_code TEXT)

JOIN: decisions d JOIN expense_items e ON e.decision_id = d.id
NOTE: Not all decisions have expense_items. For queries about decision subjects/counts (not amounts), use decisions table alone or LEFT JOIN.

KEY FIELDS:
- subject: Greek text describing the decision (use ILIKE for keyword search)
- decision_type: 'Β.2.1' (expenditure), 'Β.1.3' (commitment), 'Δ.1' (contract), etc.
- cpv_code: EU procurement category code (use LIKE prefix match)
- kae_code: Greek budget code KAE/ALE (use LIKE prefix match)
- contractor_afm: contractor tax ID (9 digits)
- org_afm: organization tax ID

RULES:
- ONLY SELECT. Never INSERT/UPDATE/DELETE/DROP.
- CRITICAL: Do NOT add WHERE clauses unless the user EXPLICITLY mentions a filter. General questions like "top contractors" or "total spending" must have NO WHERE clause.
- Use SUM(e.amount) for "how much/πόσο" questions.
- Use COUNT(DISTINCT d.ada) for "how many/πόσες" questions.
- CPV codes: use LIKE prefix match ONLY when user mentions a specific spending category.
- For Greek bureaucratic terms in the subject, use: subject ILIKE '%TERM%'
- Org filter: use org_id = 'UID' ONLY when a UID is provided in context hints.
- Dates: EXTRACT(YEAR FROM d.issue_date) = YYYY
- Always add LIMIT (default 20).
- Use context hints provided in [Context hints: ...] to inform your query.

EXAMPLES:
Q: "Top 5 organizations by spending"
SQL: SELECT d.org_name, SUM(e.amount) AS total FROM decisions d JOIN expense_items e ON e.decision_id = d.id GROUP BY d.org_name ORDER BY total DESC LIMIT 5

Q: "Top 10 contractors by total amount"
SQL: SELECT e.contractor_name, SUM(e.amount) AS total FROM decisions d JOIN expense_items e ON e.decision_id = d.id GROUP BY e.contractor_name ORDER BY total DESC LIMIT 10

Q: "How much was spent on cleaning in Athens?"
SQL: SELECT SUM(e.amount) FROM decisions d JOIN expense_items e ON e.decision_id = d.id WHERE e.cpv_code LIKE '9091%' AND d.org_id = '6105'

Q: "Show me all direct awards (απευθείας αναθέσεις)"
SQL: SELECT d.ada, d.org_name, d.subject, SUM(e.amount) AS total FROM decisions d JOIN expense_items e ON e.decision_id = d.id WHERE d.subject ILIKE '%ΑΠΕΥΘΕΙΑΣ%ΑΝΑΘΕΣ%' GROUP BY d.ada, d.org_name, d.subject ORDER BY total DESC LIMIT 20

Q: "Find decisions for contractor with AFM 094270233"
SQL: SELECT d.ada, d.org_name, d.subject, e.amount FROM decisions d JOIN expense_items e ON e.decision_id = d.id WHERE e.contractor_afm = '094270233' ORDER BY e.amount DESC LIMIT 20

Q: "Spending on fuel (καύσιμα) by organization"
SQL: SELECT d.org_name, SUM(e.amount) AS total FROM decisions d JOIN expense_items e ON e.decision_id = d.id WHERE e.cpv_code LIKE '091%' OR d.subject ILIKE '%ΚΑΥΣΙΜ%' GROUP BY d.org_name ORDER BY total DESC LIMIT 20

Q: "Show budget commitments (αναλήψεις υποχρεώσεων)"
SQL: SELECT d.ada, d.org_name, d.subject, d.issue_date FROM decisions d WHERE d.subject ILIKE '%ΑΝΑΛΗΨ%ΥΠΟΧΡΕΩΣ%' ORDER BY d.issue_date DESC LIMIT 20

Q: "How many direct awards exist?"
SQL: SELECT COUNT(*) FROM decisions d WHERE d.subject ILIKE '%ΑΠΕΥΘΕΙΑΣ%ΑΝΑΘΕΣ%' LIMIT 1

OUTPUT: Only a JSON object, no markdown, no backticks:
{{"thinking":"...","resolved_org":"UID or null","resolved_cpv":"code or null","sql":"SELECT ...","explanation":"..."}}"""


# ============================================================
# SQL Safety
# ============================================================

FORBIDDEN_SQL_PATTERNS = [
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b',
    r'\b(INTO|SET)\b\s',
    r';\s*\w',             # multiple statements
    r'--',                 # SQL comments (could hide injection)
    r'/\*',                # block comments
    r'\bEXEC\b',
    r'\bEXECUTE\b',
    r'\bxp_\w+',           # SQL Server extended procedures
    r'\bpg_\w+\s*\(',      # PostgreSQL system functions
]


def is_safe_sql(sql: str) -> bool:
    """Check if a SQL query is safe (read-only, single statement)."""
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (CTE)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Check for forbidden patterns
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, sql_upper):
            return False

    return True


# ============================================================
# Agent Result
# ============================================================

@dataclass
class AgentResult:
    """Structured result from the SQL agent."""
    answer: str                          # Human-readable answer
    sql: str = ""                        # Generated SQL query
    data: list = field(default_factory=list)  # Raw query results
    thinking: str = ""                   # LLM's reasoning
    explanation: str = ""                # What the query does
    resolved_org: Optional[str] = None   # Resolved org UID
    resolved_cpv: Optional[str] = None   # Resolved CPV code
    error: Optional[str] = None          # Error message if failed
    success: bool = True


# ============================================================
# SQL Agent
# ============================================================

class SQLAgent:
    """
    The main text-to-SQL agent.

    Takes natural language, uses an LLM to generate SQL,
    executes it safely, and returns formatted results.
    """

    def __init__(
        self,
        llm: LLMClient,
        db: DatabaseManager,
        cpv_lookup: Optional[CPVLookup] = None,
        org_resolver: Optional[OrgResolver] = None,
        max_retries: int = 2,
    ):
        self.llm = llm
        self.db = db
        self.cpv = cpv_lookup or CPVLookup()
        self.orgs = org_resolver or OrgResolver(db_manager=db)
        self.bureau = BureaucracyLayer()
        self.max_retries = max_retries

        # The system prompt is compact — entity resolution
        # happens via pre-resolve hints in the user message
        self.system_prompt = SYSTEM_PROMPT

    def ask(self, question: str) -> AgentResult:
        """
        Answer a natural language question about Greek government spending.

        Args:
            question: Question in Greek or English

        Returns:
            AgentResult with answer, SQL, data, and metadata
        """
        logger.info(f"Agent received question: {question}")

        # Step 1: Pre-resolve entities to help the LLM
        pre_context = self._pre_resolve(question)

        # Step 2: Build the full prompt
        user_prompt = question
        if pre_context:
            user_prompt = f"{question}\n\n[Context hints: {pre_context}]"

        # Step 3: Ask the LLM to generate SQL
        for attempt in range(self.max_retries + 1):
            try:
                llm_response = self.llm.chat(
                    user_message=user_prompt,
                    system_prompt=self.system_prompt,
                    temperature=0.1,
                    json_mode=True,
                )

                # Parse LLM output
                parsed = self._parse_llm_response(llm_response.content)
                sql = parsed.get("sql", "").strip()
                thinking = parsed.get("thinking", "")
                explanation = parsed.get("explanation", "")
                resolved_org = parsed.get("resolved_org")
                resolved_cpv = parsed.get("resolved_cpv")

                if not sql:
                    if attempt < self.max_retries:
                        logger.warning(f"LLM returned no SQL (attempt {attempt + 1}), retrying...")
                        continue
                    return AgentResult(
                        answer="I couldn't generate a query for that question. Could you rephrase it?",
                        thinking=thinking,
                        success=False,
                        error="No SQL generated",
                    )

                # Step 4: Safety check
                if not is_safe_sql(sql):
                    logger.warning(f"Unsafe SQL blocked: {sql[:200]}")
                    if attempt < self.max_retries:
                        user_prompt = (
                            f"{question}\n\n"
                            f"[IMPORTANT: Only generate SELECT queries. "
                            f"Your previous attempt was blocked for safety. Try again.]"
                        )
                        continue
                    return AgentResult(
                        answer="I generated an unsafe query and blocked it for safety.",
                        sql=sql,
                        thinking=thinking,
                        success=False,
                        error="Unsafe SQL blocked",
                    )

                # Step 4b: Strip hallucinated filters
                sql = self._strip_hallucinated_filters(sql, pre_context, resolved_cpv, resolved_org)

                # Step 5: Execute the query
                try:
                    data = self._execute_sql(sql)
                except Exception as e:
                    error_msg = str(e)
                    logger.warning(f"SQL execution failed (attempt {attempt + 1}): {error_msg}")
                    if attempt < self.max_retries:
                        user_prompt = (
                            f"{question}\n\n"
                            f"[Your previous SQL had an error: {error_msg[:200]}. "
                            f"Please fix it and try again.]"
                        )
                        continue
                    return AgentResult(
                        answer=f"The query failed to execute: {error_msg[:200]}",
                        sql=sql,
                        thinking=thinking,
                        success=False,
                        error=error_msg,
                    )

                # Step 6: Format the answer
                answer = self._format_answer(question, data, explanation)

                return AgentResult(
                    answer=answer,
                    sql=sql,
                    data=data,
                    thinking=thinking,
                    explanation=explanation,
                    resolved_org=resolved_org,
                    resolved_cpv=resolved_cpv,
                    success=True,
                )

            except LLMClientError as e:
                logger.error(f"LLM error: {e}")
                return AgentResult(
                    answer=f"LLM communication error: {e}",
                    success=False,
                    error=str(e),
                )

        return AgentResult(
            answer="I couldn't answer after multiple attempts. Please try rephrasing.",
            success=False,
            error="Max retries exhausted",
        )

    # -----------------------------------------------------------
    # Hallucination guard: strip filters the user didn't ask for
    # -----------------------------------------------------------

    def _strip_hallucinated_filters(
        self, sql: str, pre_context: str, resolved_cpv, resolved_org
    ) -> str:
        """
        If the pre-resolver found NO CPV code but the LLM inserted a
        cpv_code WHERE clause, strip it out. Same for org_id filters.
        """
        import re

        original_sql = sql

        # If no CPV was pre-resolved, remove any cpv_code filter
        if not resolved_cpv and "cpv_code" not in pre_context:
            # Remove patterns like: AND e.cpv_code LIKE '...'  or  WHERE e.cpv_code LIKE '...'
            sql = re.sub(
                r"\s+AND\s+e\.cpv_code\s+(?:I?LIKE|=)\s+'[^']*'",
                "", sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                r"\s+WHERE\s+e\.cpv_code\s+(?:I?LIKE|=)\s+'[^']*'",
                "", sql, flags=re.IGNORECASE
            )

        # If no org was pre-resolved, remove any org_id filter
        if not resolved_org and "org_id" not in pre_context:
            sql = re.sub(
                r"\s+AND\s+d\.org_id\s*=\s*'[^']*'",
                "", sql, flags=re.IGNORECASE
            )
            sql = re.sub(
                r"\s+WHERE\s+d\.org_id\s*=\s*'[^']*'",
                "", sql, flags=re.IGNORECASE
            )

        if sql != original_sql:
            logger.info(f"Stripped hallucinated filter: {original_sql} → {sql}")

        return sql

    # -----------------------------------------------------------
    # Pre-resolution: help the LLM by resolving entities first
    # -----------------------------------------------------------

    def _pre_resolve(self, question: str) -> str:
        """
        Pre-resolve organizations, CPV codes, and bureaucratic terms
        from the question to give the LLM concrete hints.
        """
        hints = []

        # Try to resolve organization names
        org = self.orgs.resolve(question)
        if org:
            hints.append(f"Organization '{org['label']}' has UID={org['uid']}")

        # Try to match CPV codes (only high-confidence matches)
        cpv_results = self.cpv.search(question, limit=2, min_score=10)
        if cpv_results:
            for r in cpv_results:
                if r["score"] >= 10:
                    hints.append(
                        f"CPV match: '{r['description_en']}' = code {r['code']}"
                    )

        # Bureaucratic intelligence layer
        bureau_result = self.bureau.preprocess(question)
        if bureau_result["context_text"]:
            hints.append(bureau_result["context_text"])

        return "; ".join(hints) if hints else ""

    # -----------------------------------------------------------
    # Parse LLM Response
    # -----------------------------------------------------------

    def _parse_llm_response(self, content: str) -> dict:
        """Parse the LLM's JSON response, handling common formatting issues."""
        content = content.strip()

        # Remove markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        # Try to find JSON in the response
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from surrounding text
        json_match = re.search(r'\{[^{}]*"sql"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Last resort: try to extract just the SQL
        sql_match = re.search(r'(SELECT\s.+?)(?:;|\Z)', content, re.IGNORECASE | re.DOTALL)
        if sql_match:
            return {
                "sql": sql_match.group(1).strip(),
                "thinking": "Extracted SQL from non-JSON response",
                "explanation": "",
            }

        logger.warning(f"Could not parse LLM response: {content[:300]}")
        return {}

    # -----------------------------------------------------------
    # Execute SQL
    # -----------------------------------------------------------

    def _execute_sql(self, sql: str) -> list[dict]:
        """Execute a read-only SQL query and return results as dicts."""
        # Add safety: force statement timeout
        safe_sql = f"SET statement_timeout = '10s'; {sql}"

        with self.db.get_cursor(commit=False) as cur:
            # Set timeout for this query
            cur.execute("SET statement_timeout = '10s'")
            cur.execute(sql)
            rows = cur.fetchall()
            # Convert RealDictRow to regular dicts
            return [dict(row) for row in rows]

    # -----------------------------------------------------------
    # Format Answer
    # -----------------------------------------------------------

    def _format_answer(self, question: str, data: list[dict], explanation: str) -> str:
        """Format query results into a human-readable answer."""
        if not data:
            return "Δεν βρέθηκαν αποτελέσματα. (No results found.)"

        # Single aggregate result (e.g. SUM, COUNT)
        if len(data) == 1 and len(data[0]) <= 3:
            row = data[0]
            parts = []
            for key, value in row.items():
                formatted = self._format_value(key, value)
                parts.append(f"**{key}**: {formatted}")
            return " | ".join(parts)

        # Multiple rows — build a compact table
        if len(data) <= 20:
            return self._format_table(data)

        # Too many rows — summarize
        return (
            f"Found {len(data)} results. Here are the top entries:\n\n"
            + self._format_table(data[:10])
            + f"\n\n... and {len(data) - 10} more rows."
        )

    def _format_value(self, key: str, value) -> str:
        """Format a single value based on its likely type."""
        if value is None:
            return "N/A"
        if isinstance(value, (int, float)):
            if "amount" in key.lower() or "total" in key.lower() or "sum" in key.lower():
                return f"€{value:,.2f}"
            if isinstance(value, float) and value == int(value):
                return str(int(value))
            return f"{value:,}"
        return str(value)

    def _format_table(self, data: list[dict]) -> str:
        """Format results as a readable text table."""
        if not data:
            return ""

        keys = list(data[0].keys())

        # Calculate column widths
        widths = {}
        for key in keys:
            values = [self._format_value(key, row.get(key, "")) for row in data]
            widths[key] = max(len(key), max(len(v) for v in values))

        # Build header
        header = " | ".join(key.ljust(widths[key]) for key in keys)
        separator = "-+-".join("-" * widths[key] for key in keys)

        # Build rows
        rows = []
        for row in data:
            formatted = " | ".join(
                self._format_value(key, row.get(key, "")).ljust(widths[key])
                for key in keys
            )
            rows.append(formatted)

        return f"{header}\n{separator}\n" + "\n".join(rows)

    # -----------------------------------------------------------
    # Convenience: Interactive REPL
    # -----------------------------------------------------------

    def repl(self):
        """
        Start an interactive question-answering loop.

        Type questions in Greek or English, get SQL + results.
        Type 'quit' or 'exit' to stop.
        """
        print("=" * 60)
        print("  Diavgeia-Watch: Public Spending Query Agent")
        print("  Type questions in Greek or English.")
        print("  Type 'quit' to exit, 'stats' for DB stats.")
        print("=" * 60)

        while True:
            try:
                question = input("\n🔍 Ask: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nΑντίο! (Goodbye!)")
                break

            if not question:
                continue
            if question.lower() in ("quit", "exit", "q"):
                print("Αντίο! (Goodbye!)")
                break
            if question.lower() == "stats":
                stats = self.db.get_stats()
                for k, v in stats.items():
                    print(f"  {k}: {v}")
                continue

            result = self.ask(question)

            print(f"\n💭 Thinking: {result.thinking}")
            if result.sql:
                print(f"\n📝 SQL:\n{result.sql}")
            print(f"\n📊 Answer:\n{result.answer}")
            if result.error:
                print(f"\n⚠️ Error: {result.error}")