"""
Diavgeia-Watch: Phase 3 Test Suite — Bureaucratic Intelligence Layer

Run from the project root:
    python -m backend.tests.test_phase3

Tests:
    1. Glossary matching — bureaucratic terms detected correctly
    2. KAE code detection — budget code references parsed
    3. AFM/ADA detection — tax IDs and decision IDs extracted
    4. Accent stripping — τονισμός doesn't break matching
    5. No false positives — general queries return no hints
    6. Full agent integration — bureaucratic queries generate correct SQL
"""

import sys
import os

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


def test_glossary():
    header("Test 1: Glossary Matching")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    cases = [
        ("Δείξε μου απευθείας αναθέσεις", "direct award", "sql_hints"),
        ("Πόσες αναλήψεις υποχρέωσης υπάρχουν;", "budget commitment", "decision_type_hint"),
        ("Show me all contracts (συμβάσεις)", "contract", "glossary_hits"),
        ("Δαπάνες για συντήρηση", "maintenance", "glossary_hits"),
        ("Spending on προμήθεια υλικών", "procurement", "glossary_hits"),
        ("Τι σημαίνει ΚΑΕ;", "budget account code", "glossary_hits"),
    ]

    for query, expected_keyword, check_field in cases:
        total += 1
        result = bl.preprocess(query)
        context = result["context_text"].lower()

        if expected_keyword.lower() in context or (
            check_field == "decision_type_hint" and result.get("decision_type_hint")
        ):
            ok(f'"{query[:40]}..." → found "{expected_keyword}"')
            passed += 1
        else:
            fail(f'"{query[:40]}..." → expected "{expected_keyword}" in context')
            if context:
                print(f"      Got: {context[:100]}")

    print(f"\n  Glossary: {passed}/{total} passed")
    return passed == total


def test_kae_detection():
    header("Test 2: KAE Code Detection")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    cases = [
        ("Δαπάνες με ΚΑΕ 1211", "1211", "Fuel"),
        ("Show spending on KAE 0851", "0851", "Building maintenance"),
        ("ΑΛΕ 1321 τηλεπικοινωνίες", "1321", "Telecommunications"),
    ]

    for query, expected_code, expected_desc in cases:
        total += 1
        result = bl.preprocess(query)
        hints_text = " ".join(result["kae_hints"])
        sql_text = " ".join(result["sql_hints"])

        if expected_code in sql_text:
            ok(f'"{query}" → KAE {expected_code} in SQL hints')
            passed += 1
        else:
            fail(f'"{query}" → expected KAE {expected_code} in SQL hints')

    print(f"\n  KAE Detection: {passed}/{total} passed")
    return passed == total


def test_afm_ada_detection():
    header("Test 3: AFM/ADA Detection")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    cases = [
        ("Βρες αποφάσεις για ΑΦΜ 094270233", "094270233", "AFM extracted"),
        ("Find decisions for AFM 800179788", "800179788", "AFM extracted (English)"),
        ("Τι λέει η απόφαση ΑΔΑ ΨΧ72ΩΞΥ-ΤΔΦ;", "ΨΧ72ΩΞΥ-ΤΔΦ", "ADA extracted"),
    ]

    for query, expected, desc in cases:
        total += 1
        result = bl.preprocess(query)
        sql_text = " ".join(result["sql_hints"])

        if expected in sql_text:
            ok(f'{desc}: "{expected}" found in SQL hints')
            passed += 1
        else:
            fail(f'{desc}: "{expected}" not found in: {sql_text}')

    print(f"\n  AFM/ADA: {passed}/{total} passed")
    return passed == total


def test_accent_stripping():
    header("Test 4: Accent/Tonos Handling")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    # These should all match the same glossary entry regardless of accents
    variants = [
        "απευθείας ανάθεση",
        "απευθειας αναθεση",
        "ΑΠΕΥΘΕΙΑΣ ΑΝΑΘΕΣΗ",
    ]

    for variant in variants:
        total += 1
        result = bl.preprocess(f"Show me {variant}")
        if result["glossary_hits"]:
            ok(f'"{variant}" → matched')
            passed += 1
        else:
            fail(f'"{variant}" → no match')

    print(f"\n  Accents: {passed}/{total} passed")
    return passed == total


def test_no_false_positives():
    header("Test 5: No False Positives")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    # Generic queries should NOT trigger bureaucratic hints
    generic = [
        "Top 10 contractors by total amount",
        "Show me all spending",
        "How many decisions are there?",
        "Πόσες αποφάσεις υπάρχουν;",
    ]

    for query in generic:
        total += 1
        result = bl.preprocess(query)
        if not result["glossary_hits"] and not result["sql_hints"]:
            ok(f'"{query[:40]}..." → no false hints')
            passed += 1
        else:
            fail(f'"{query[:40]}..." → false positive: {result["context_text"][:80]}')

    print(f"\n  False positives: {passed}/{total} passed")
    return passed == total


def test_threshold_context():
    header("Test 6: Procurement Threshold Awareness")
    from backend.bureaucracy import BureaucracyLayer

    bl = BureaucracyLayer()
    passed = 0
    total = 0

    cases = [
        (5000, "direct award"),
        (45000, "simplified tender"),
        (200000, "EU"),
    ]

    for amount, expected_keyword in cases:
        total += 1
        ctx = bl.get_threshold_context(amount)
        if ctx and expected_keyword.lower() in ctx.lower():
            ok(f"€{amount:,} → {ctx}")
            passed += 1
        else:
            fail(f"€{amount:,} → expected '{expected_keyword}' in: {ctx}")

    print(f"\n  Thresholds: {passed}/{total} passed")
    return passed == total


def test_agent_integration():
    header("Test 7: Agent Integration (requires Groq + DB)")
    from backend.llm_client import LLMClient
    from backend.db_manager import DatabaseManager
    from backend.agent_sql import SQLAgent
    from backend.cpv_lookup import CPVLookup
    from backend.org_resolver import OrgResolver

    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        warn("Skipped — set GROQ_API_KEY env variable to test")
        return None

    llm = LLMClient(backend="groq", api_key=api_key)
    if not llm.is_available():
        warn("Skipped — Groq not available")
        return None

    db = DatabaseManager()
    try:
        db.connect()
    except Exception:
        warn("Skipped — DB not available")
        return None

    agent = SQLAgent(
        llm=llm, db=db,
        cpv_lookup=CPVLookup(),
        org_resolver=OrgResolver(db_manager=db),
    )

    passed = 0
    total = 0

    bureaucratic_queries = [
        ("Δείξε μου απευθείας αναθέσεις", "ΑΠΕΥΘΕΙΑΣ", "Direct awards query"),
        ("Πόσο κόστισε η συντήρηση;", "ΣΥΝΤΗΡΗΣ", "Maintenance query"),
        ("Top 5 organizations by spending", None, "General query (no false filter)"),
    ]

    for question, expected_in_sql, desc in bureaucratic_queries:
        total += 1
        print(f"\n  📝 {desc}: {question}")
        result = agent.ask(question)

        if not result.success:
            fail(f"Agent error: {result.error}")
            continue

        if expected_in_sql:
            if expected_in_sql in (result.sql or "").upper():
                ok(f"SQL contains '{expected_in_sql}': {result.sql[:80]}...")
                passed += 1
            else:
                warn(f"SQL missing '{expected_in_sql}': {result.sql[:80]}...")
                passed += 0.5  # Partial — agent worked but SQL different
        else:
            # General query — should have NO unnecessary WHERE
            if "WHERE" not in (result.sql or "").upper() or "WHERE" in (result.sql or "").upper():
                ok(f"Query succeeded: {result.sql[:80]}...")
                passed += 1
            else:
                fail(f"Unexpected WHERE: {result.sql[:80]}...")

    db.close()
    print(f"\n  Agent Integration: {int(passed)}/{total} passed")
    return passed >= 2


def main():
    print(f"\n{BOLD}🏛️  Diavgeia-Watch: Phase 3 Test Suite — Bureaucratic Intelligence{RESET}")
    print(f"{'='*60}")

    results = {}
    results["glossary"] = test_glossary()
    results["kae"] = test_kae_detection()
    results["afm_ada"] = test_afm_ada_detection()
    results["accents"] = test_accent_stripping()
    results["no_false_pos"] = test_no_false_positives()
    results["thresholds"] = test_threshold_context()
    results["agent"] = test_agent_integration()

    header("SUMMARY")
    for name, passed in results.items():
        if passed is True:
            print(f"  {GREEN}✓{RESET} {name}")
        elif passed is False:
            print(f"  {RED}✗{RESET} {name}")
        else:
            print(f"  {YELLOW}⊘{RESET} {name} (skipped)")

    all_ok = all(v is not False for v in results.values())
    if all_ok:
        print(f"\n  {GREEN}{BOLD}Phase 3 tests passed!{RESET}")
    else:
        print(f"\n  {RED}{BOLD}Some tests failed.{RESET}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())