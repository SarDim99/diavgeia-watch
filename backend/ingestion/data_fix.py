"""
Diavgeia-Watch: Data Maintenance Scripts

Fixes missing fields and expands data coverage.

Usage:
    # Fix missing org_name from raw_json
    python -m backend.data_fix --backfill-orgs

    # Show data coverage stats
    python -m backend.data_fix --stats

    # Harvest a full month (all types)
    python -m backend.data_fix --harvest-month 2024-12
"""

import os
import sys
import json
import logging
import argparse
from datetime import date, timedelta

import psycopg2.extras

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.manager import DatabaseManager
from backend.ingestion.api_client import DiavgeiaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def backfill_org_names(db: DatabaseManager):
    """
    Fix missing org_name by:
    1. Trying raw_json fields
    2. Looking up org names from Diavgeia API by organizationId
    """
    print(f"\n{BOLD}{CYAN}Backfilling missing org_name...{RESET}")

    conn = db.pool.getconn()
    cur = conn.cursor()

    # Find unique org_ids with missing names
    cur.execute("""
        SELECT DISTINCT
            COALESCE(org_id, raw_json->>'organizationId') AS oid
        FROM decisions
        WHERE (org_name IS NULL OR org_name = '' OR org_name = 'N/A')
          AND (org_id IS NOT NULL AND org_id != ''
               OR raw_json->>'organizationId' IS NOT NULL)
    """)
    org_ids = [row[0] for row in cur.fetchall() if row[0]]
    print(f"  Found {len(org_ids)} unique org IDs needing name lookup")

    if not org_ids:
        print(f"  {GREEN}✓ No fixes needed{RESET}")
        db.pool.putconn(conn)
        return

    # Look up org names from Diavgeia API
    import requests
    import time

    org_names = {}
    for i, oid in enumerate(org_ids):
        try:
            url = f"https://diavgeia.gov.gr/luminapi/opendata/organizations/{oid}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("label") or data.get("name") or data.get("abbreviation")
                if name:
                    org_names[oid] = name
                    if (i + 1) % 20 == 0:
                        print(f"    Looked up {i+1}/{len(org_ids)} orgs...")
            time.sleep(0.3)  # Rate limit
        except Exception as e:
            logger.warning(f"Failed to look up org {oid}: {e}")

    print(f"  Resolved {len(org_names)} org names from API")

    # Update the database
    fixed = 0
    for oid, name in org_names.items():
        cur.execute("""
            UPDATE decisions
            SET org_name = %s,
                org_id = COALESCE(NULLIF(org_id, ''), %s)
            WHERE (org_name IS NULL OR org_name = '' OR org_name = 'N/A')
              AND (org_id = %s OR raw_json->>'organizationId' = %s)
        """, (name, oid, oid, oid))
        fixed += cur.rowcount

    conn.commit()
    cur.close()
    db.pool.putconn(conn)

    print(f"  {GREEN}✓ Updated {fixed} records with org names{RESET}")


def backfill_org_ids(db: DatabaseManager):
    """Fix missing org_id from raw_json."""
    conn = db.pool.getconn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, raw_json
        FROM decisions
        WHERE (org_id IS NULL OR org_id = '') AND raw_json IS NOT NULL
    """)
    rows = cur.fetchall()

    fixed = 0
    for row_id, raw_json in rows:
        raw = raw_json if isinstance(raw_json, dict) else json.loads(raw_json)
        org_id = raw.get("organizationId") or raw.get("organizationUid")
        if org_id:
            cur.execute(
                "UPDATE decisions SET org_id = %s WHERE id = %s",
                (str(org_id), row_id)
            )
            fixed += 1

    conn.commit()
    cur.close()
    db.pool.putconn(conn)

    if fixed:
        print(f"  {GREEN}✓ Also fixed {fixed} missing org_id values{RESET}")


def backfill_decision_types(db: DatabaseManager):
    """Fix decision_type from raw_json."""
    print(f"\n{BOLD}{CYAN}Backfilling decision_type from raw_json...{RESET}")

    conn = db.pool.getconn()
    cur = conn.cursor()

    # The API uses 'decisionTypeId' (e.g. "Δ.1", "Β.1.3")
    cur.execute("""
        UPDATE decisions
        SET decision_type = raw_json->>'decisionTypeId'
        WHERE raw_json->>'decisionTypeId' IS NOT NULL
          AND raw_json->>'decisionTypeId' != ''
          AND decision_type != raw_json->>'decisionTypeId'
    """)
    fixed = cur.rowcount

    conn.commit()
    cur.close()
    db.pool.putconn(conn)

    print(f"  {GREEN}✓ Fixed {fixed} decision_type values{RESET}")


def show_stats(db: DatabaseManager):
    """Show detailed data coverage stats."""
    print(f"\n{BOLD}{CYAN}Database Coverage Stats{RESET}")
    print("=" * 60)

    conn = db.pool.getconn()
    cur = conn.cursor()

    # Overall stats
    stats = db.get_stats()
    print(f"  Total decisions:     {stats['total_decisions']:,}")
    print(f"  Total expense items: {stats['total_expense_items']:,}")
    print(f"  Organizations:       {stats['unique_organizations']:,}")
    print(f"  Contractors:         {stats['unique_contractors']:,}")
    print(f"  Total amount:        €{stats['total_amount']:,.2f}")
    date_range = stats.get("date_range", {})
    print(f"  Date range:          {date_range.get('from', '?')} to {date_range.get('to', '?')}")

    # By decision type
    print(f"\n  {BOLD}By Decision Type:{RESET}")
    cur.execute("""
        SELECT decision_type, COUNT(*) AS cnt
        FROM decisions
        GROUP BY decision_type
        ORDER BY cnt DESC
    """)
    for dt, cnt in cur.fetchall():
        print(f"    {dt}: {cnt:,}")

    # Records with/without expense items
    print(f"\n  {BOLD}Expense Item Coverage:{RESET}")
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN e.id IS NOT NULL THEN 1 END) AS with_items,
            COUNT(CASE WHEN e.id IS NULL THEN 1 END) AS without_items
        FROM decisions d
        LEFT JOIN expense_items e ON e.decision_id = d.id
    """)
    total, with_items, without_items = cur.fetchone()
    print(f"    With expense items:    {with_items:,}")
    print(f"    Without expense items: {without_items:,}")

    # Records with/without org_name
    print(f"\n  {BOLD}Org Name Coverage:{RESET}")
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN org_name IS NOT NULL AND org_name != '' THEN 1 END) AS has_name,
            COUNT(CASE WHEN org_name IS NULL OR org_name = '' THEN 1 END) AS missing
        FROM decisions
    """)
    total, has_name, missing = cur.fetchone()
    print(f"    Has org_name:     {has_name:,}")
    print(f"    Missing org_name: {missing:,}")

    # Top search terms in subjects
    print(f"\n  {BOLD}Common Subject Patterns:{RESET}")
    patterns = [
        ("ΑΝΑΛΗΨΗ ΥΠΟΧΡΕΩΣ", "Budget commitments"),
        ("ΧΡΗΜΑΤΙΚ%ΕΝΤΑΛΜ", "Payment warrants"),
        ("ΠΡΟΜΗΘΕΙ", "Procurements"),
        ("ΑΠΕΥΘΕΙΑΣ%ΑΝΑΘΕΣ", "Direct awards"),
        ("ΣΥΝΤΗΡΗΣ", "Maintenance"),
        ("ΜΙΣΘΩΣ", "Rentals"),
        ("ΣΥΜΒΑΣ", "Contracts"),
        ("ΥΠΗΡΕΣΙ", "Services"),
    ]
    for pattern, label in patterns:
        cur.execute(
            f"SELECT COUNT(*) FROM decisions WHERE subject ILIKE '%{pattern}%'"
        )
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f"    {label}: {cnt:,}")

    cur.close()
    db.pool.putconn(conn)


def harvest_month(db: DatabaseManager, year_month: str):
    """
    Harvest a full month of decisions across all major types.

    Usage: python -m backend.data_fix --harvest-month 2024-12
    """
    year, month = map(int, year_month.split("-"))
    start = date(year, month, 1)

    # Calculate end of month
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)

    types = ["Β.2.1", "Β.1.3", "Δ.1"]

    print(f"\n{BOLD}{CYAN}Harvesting full month: {year_month}{RESET}")
    print(f"  Date range: {start} to {end}")
    print(f"  Types: {types}")
    print(f"  This may take several minutes...\n")

    from backend.ingestion.api_client import DiavgeiaClient
    from backend.ingestion.etl_pipeline import ETLPipeline

    # ETLPipeline.run() manages its own DB connection, so give it a fresh manager
    client = DiavgeiaClient()
    pipeline = ETLPipeline(api_client=client, db_manager=DatabaseManager())

    result = pipeline.run(
        from_date=start,
        to_date=end,
        decision_types=types,
    )

    fetched = result.get("total_fetched", 0)
    saved = result.get("total_saved", 0)
    print(f"\n{GREEN}✓ Month harvest complete: {fetched} fetched, {saved} saved{RESET}")

    # Reconnect the main db (pipeline.run closes its own)
    db.connect()


def main():
    parser = argparse.ArgumentParser(description="Diavgeia-Watch Data Maintenance")
    parser.add_argument("--backfill-orgs", action="store_true",
                        help="Fix missing org_name from raw_json")
    parser.add_argument("--backfill-types", action="store_true",
                        help="Fix decision_type from raw_json")
    parser.add_argument("--stats", action="store_true",
                        help="Show data coverage stats")
    parser.add_argument("--harvest-month", type=str,
                        help="Harvest full month (e.g. 2024-12)")
    parser.add_argument("--backfill-all", action="store_true",
                        help="Run all backfill operations")

    args = parser.parse_args()

    if not any([args.backfill_orgs, args.backfill_types, args.stats,
                args.harvest_month, args.backfill_all]):
        parser.print_help()
        return

    db = DatabaseManager()
    db.connect()

    try:
        if args.backfill_all or args.backfill_orgs:
            backfill_org_names(db)

        if args.backfill_all or args.backfill_types:
            backfill_decision_types(db)

        if args.stats:
            show_stats(db)

        if args.harvest_month:
            harvest_month(db, args.harvest_month)
            # Auto-backfill after harvest
            backfill_org_names(db)
            backfill_decision_types(db)
            show_stats(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()