"""
Diavgeia-Watch: Phase 2 Test Suite

Run from the project root with your venv active:
    python -m backend.tests.test_phase2

Tests (in order):
    1. CPV Lookup — does keyword → code resolution work?
    2. Org Resolver — does name → UID resolution work?
    3. LLM Client — can we reach Ollama?
    4. Database — is PostgreSQL up and has data?
    5. SQL Agent — full end-to-end: question → SQL → answer
"""

import sys
import json

# ============================================================
# Colors for terminal output
# ============================================================
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}✓ PASS{RESET} {msg}")

def fail(msg):
    print(f"  {RED}✗ FAIL{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠ WARN{RESET} {msg}")

def header(msg):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")


# ============================================================
# Test 1: CPV Lookup
# ============================================================
def test_cpv_lookup():
    header("Test 1: CPV Lookup")
    from backend.cpv_lookup import CPVLookup

    cpv = CPVLookup()
    passed = 0
    total = 0

    test_cases = [
        ("καθαριότητα", "9091", "Greek: cleaning → 9091x"),
        ("cleaning", "9091", "English: cleaning → 9091x"),
        ("δρόμος", "4523", "Greek: road → 4523x"),
        ("road maintenance", "4523", "English: road maintenance → 4523x"),
        ("τόνερ", "3012", "Greek: toner → 3012x"),
        ("φάρμακα", "33", "Greek: medicine → 33xxxx"),
        ("IT", "72", "English: IT → 72xxxx"),
        ("ασφάλεια", "79710", "Greek: security → 79710"),
    ]

    for query, expected_prefix, description in test_cases:
        total += 1
        results = cpv.search(query, limit=3)
        if results and results[0]["code"].startswith(expected_prefix):
            ok(f"{description} → got {results[0]['code']}")
            passed += 1
        elif results:
            warn(f"{description} → expected {expected_prefix}xxx, got {results[0]['code']}")
        else:
            fail(f"{description} → no results")

    print(f"\n  CPV Lookup: {passed}/{total} passed")
    return passed == total


# ============================================================
# Test 2: Organization Resolver
# ============================================================
def test_org_resolver():
    header("Test 2: Organization Resolver")
    from backend.org_resolver import OrgResolver

    orgs = OrgResolver()  # no DB needed for hardcoded lookup
    passed = 0
    total = 0

    test_cases = [
        ("αθήνα", "6105", "Greek: athens"),
        ("Athens", "6105", "English: Athens"),
        ("δήμος αθηναίων", "6105", "Formal: Dimos Athinaion"),
        ("θεσσαλονίκη", "6127", "Thessaloniki"),
        ("πειραιάς", "6144", "Piraeus"),
        ("υπουργείο υγείας", "100003831", "Ministry of Health"),
        ("ερτ", "100012982", "ERT broadcaster"),
        ("λάρισα", "6164", "Larissa"),
    ]

    for query, expected_uid, description in test_cases:
        total += 1
        result = orgs.resolve(query)
        if result and result["uid"] == expected_uid:
            ok(f"{description} → UID {result['uid']}")
            passed += 1
        elif result:
            warn(f"{description} → expected {expected_uid}, got {result['uid']} ({result['label']})")
        else:
            fail(f"{description} → not found")

    print(f"\n  Org Resolver: {passed}/{total} passed")
    return passed == total


# ============================================================
# Test 3: LLM Client (Ollama connectivity)
# ============================================================
def test_llm_client():
    header("Test 3: LLM Client (Ollama)")
    from backend.llm_client import LLMClient

    llm = LLMClient(backend="ollama")

    # Check connectivity
    if not llm.is_available():
        fail("Cannot connect to Ollama at http://localhost:11434")
        print(f"    → Run: ollama serve")
        return False
    ok("Ollama is reachable")

    # Check models
    models = llm.list_models()
    if not models:
        fail("No models found in Ollama")
        print(f"    → Run: ollama pull llama3.1:8b")
        return False
    ok(f"Available models: {', '.join(models)}")

    if llm.model not in models:
        warn(f"Default model '{llm.model}' not found. Available: {', '.join(models)}")
        print(f"    → Run: ollama pull {llm.model}")
        print(f"    → Or use --model {models[0]} when running the agent")
        return False
    ok(f"Model '{llm.model}' is available")

    # Simple test call
    print(f"  Sending test prompt to {llm.model}...")
    try:
        resp = llm.chat(
            user_message="Reply with exactly: HELLO",
            system_prompt="You are a test bot. Reply with the exact word requested.",
            max_tokens=10,
        )
        if "HELLO" in resp.content.upper():
            ok(f"LLM responded correctly: '{resp.content.strip()}'")
        else:
            warn(f"LLM responded but unexpected: '{resp.content.strip()[:50]}'")
        return True
    except Exception as e:
        fail(f"LLM call failed: {e}")
        return False


# ============================================================
# Test 4: Database Connection & Data
# ============================================================
def test_database():
    header("Test 4: Database Connection")
    from backend.db_manager import DatabaseManager

    db = DatabaseManager()
    try:
        db.connect()
        ok("Connected to PostgreSQL")
    except Exception as e:
        fail(f"Cannot connect: {e}")
        print(f"    → Run: docker compose up -d")
        return False, db

    try:
        stats = db.get_stats()
        ok(f"Decisions: {stats['total_decisions']}")
        ok(f"Expense items: {stats['total_expense_items']}")
        ok(f"Organizations: {stats['unique_organizations']}")
        ok(f"Contractors: {stats['unique_contractors']}")
        ok(f"Total amount: €{stats['total_amount']:,.2f}")

        if stats['total_decisions'] == 0:
            warn("Database is EMPTY — agent will return no results")
            print(f"    → Run: python -m backend.etl_pipeline --from 2024-12-01 --to 2024-12-07")
            return True, db  # connection works, just no data

        if stats.get('date_range'):
            dr = stats['date_range']
            ok(f"Date range: {dr['from']} to {dr['to']}")

        return True, db

    except Exception as e:
        fail(f"Stats query failed: {e}")
        return False, db


# ============================================================
# Test 5: SQL Agent (End-to-End)
# ============================================================
def test_agent(db):
    header("Test 5: SQL Agent (End-to-End)")
    from backend.llm_client import LLMClient
    from backend.agent_sql import SQLAgent, is_safe_sql
    from backend.cpv_lookup import CPVLookup
    from backend.org_resolver import OrgResolver

    # Test SQL safety checker first
    print(f"\n  {BOLD}5a. SQL Safety Checker{RESET}")
    safety_tests = [
        ("SELECT COUNT(*) FROM decisions", True, "Simple SELECT"),
        ("SELECT * FROM decisions LIMIT 10", True, "SELECT with LIMIT"),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", True, "CTE query"),
        ("DROP TABLE decisions", False, "DROP blocked"),
        ("DELETE FROM decisions", False, "DELETE blocked"),
        ("INSERT INTO decisions VALUES (1)", False, "INSERT blocked"),
        ("SELECT 1; DROP TABLE decisions", False, "Multi-statement blocked"),
        ("UPDATE decisions SET status='x'", False, "UPDATE blocked"),
    ]
    safety_passed = 0
    for sql, expected_safe, desc in safety_tests:
        result = is_safe_sql(sql)
        if result == expected_safe:
            ok(f"{desc}")
            safety_passed += 1
        else:
            fail(f"{desc} — expected safe={expected_safe}, got {result}")
    print(f"\n  Safety checker: {safety_passed}/{len(safety_tests)} passed")

    # Test full agent
    print(f"\n  {BOLD}5b. Full Agent Test{RESET}")
    llm = LLMClient(backend="ollama")
    if not llm.is_available():
        warn("Skipping agent test — Ollama not available")
        return False

    agent = SQLAgent(
        llm=llm,
        db=db,
        cpv_lookup=CPVLookup(),
        org_resolver=OrgResolver(db_manager=db),
    )

    test_questions = [
        "How many decisions are in the database?",
        "Show top 5 organizations by total spending",
        "Πόσες αποφάσεις υπάρχουν στη βάση;",
    ]

    agent_passed = 0
    for question in test_questions:
        print(f"\n  📝 Question: {question}")
        result = agent.ask(question)
        if result.success and result.sql:
            ok(f"Generated SQL: {result.sql[:80]}...")
            ok(f"Answer: {result.answer[:100]}...")
            agent_passed += 1
        else:
            fail(f"Error: {result.error or 'No SQL generated'}")
            if result.thinking:
                print(f"    Thinking: {result.thinking[:100]}")

    print(f"\n  Agent: {agent_passed}/{len(test_questions)} passed")
    return agent_passed > 0


# ============================================================
# Main
# ============================================================
def main():
    print(f"\n{BOLD}🔍 Diavgeia-Watch: Phase 2 Test Suite{RESET}")
    print(f"{'='*60}")

    results = {}

    # Test 1: CPV
    results["cpv"] = test_cpv_lookup()

    # Test 2: Orgs
    results["orgs"] = test_org_resolver()

    # Test 3: LLM
    results["llm"] = test_llm_client()

    # Test 4: DB
    db_ok, db = test_database()
    results["db"] = db_ok

    # Test 5: Agent (only if LLM and DB are available)
    if results["llm"] and results["db"]:
        results["agent"] = test_agent(db)
    else:
        header("Test 5: SQL Agent (SKIPPED)")
        warn("Skipped — requires both LLM and DB to be available")
        results["agent"] = None

    if db:
        try:
            db.close()
        except Exception:
            pass

    # Summary
    header("SUMMARY")
    for name, passed in results.items():
        if passed is True:
            print(f"  {GREEN}✓{RESET} {name}")
        elif passed is False:
            print(f"  {RED}✗{RESET} {name}")
        else:
            print(f"  {YELLOW}⊘{RESET} {name} (skipped)")

    all_critical = all(v is not False for v in results.values())
    if all_critical:
        print(f"\n  {GREEN}{BOLD}All critical tests passed! Phase 2 is ready.{RESET}")
    else:
        print(f"\n  {RED}{BOLD}Some tests failed. Fix the issues above and re-run.{RESET}")

    return 0 if all_critical else 1


if __name__ == "__main__":
    sys.exit(main())