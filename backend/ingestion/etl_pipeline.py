"""
Diavgeia-Watch: ETL Pipeline

The main harvesting orchestrator. Run this to pull expenditure decisions
from the Diavgeia API and store them in PostgreSQL.

Usage:
    # Harvest the last 7 days
    python -m backend.etl_pipeline

    # Harvest a specific date range
    python -m backend.etl_pipeline --from 2024-01-01 --to 2024-01-31

    # Harvest only a specific organization
    python -m backend.etl_pipeline --org 5001

    # Dry run (fetch but don't save)
    python -m backend.etl_pipeline --dry-run
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from typing import Optional

from backend.ingestion.api_client import DiavgeiaClient, DECISION_TYPES, DiavgeiaAPIError
from backend.db.manager import DatabaseManager

# ============================================================
# Logging Setup
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("harvest.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("etl_pipeline")


# ============================================================
# ETL Pipeline
# ============================================================

class ETLPipeline:
    """
    Orchestrates the full harvest cycle:
    1. Determine date range to fetch
    2. Fetch decisions from Diavgeia API
    3. Parse and store in PostgreSQL
    4. Log harvest status
    """

    def __init__(
        self,
        api_client: Optional[DiavgeiaClient] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.api = api_client or DiavgeiaClient()
        self.db = db_manager or DatabaseManager()

    def run(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        decision_types: Optional[list[str]] = None,
        org_uid: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Execute the ETL pipeline.

        Args:
            from_date: Start date (default: last harvest + 1 day, or 7 days ago)
            to_date: End date (default: yesterday)
            decision_types: List of decision type codes to harvest
            org_uid: Filter by organization
            dry_run: If True, fetch but don't save to DB

        Returns:
            Summary dict with counts
        """
        if not dry_run:
            self.db.connect()

        # Default decision types: expenditure approvals
        if not decision_types:
            decision_types = [DECISION_TYPES["EXPENDITURE_APPROVAL"]]

        # Default date range
        if to_date is None:
            to_date = date.today() - timedelta(days=1)  # yesterday

        if from_date is None:
            if not dry_run:
                last_harvest = self.db.get_last_harvest_date(decision_types[0])
                if last_harvest:
                    from_date = last_harvest + timedelta(days=1)
                    logger.info(f"Resuming from last harvest: {last_harvest}")
            if from_date is None:
                from_date = to_date - timedelta(days=6)  # last 7 days

        logger.info(
            f"=== ETL Pipeline Start ===\n"
            f"  Date range: {from_date} to {to_date}\n"
            f"  Types: {decision_types}\n"
            f"  Org filter: {org_uid or 'ALL'}\n"
            f"  Dry run: {dry_run}"
        )

        total_summary = {
            "from_date": str(from_date),
            "to_date": str(to_date),
            "types_processed": [],
            "total_fetched": 0,
            "total_saved": 0,
            "errors": 0,
        }

        for dtype in decision_types:
            summary = self._harvest_type(
                dtype, from_date, to_date, org_uid, dry_run
            )
            total_summary["types_processed"].append(summary)
            total_summary["total_fetched"] += summary["fetched"]
            total_summary["total_saved"] += summary["saved"]
            total_summary["errors"] += summary["errors"]

        if not dry_run:
            stats = self.db.get_stats()
            logger.info(f"Database stats after harvest: {stats}")
            total_summary["db_stats"] = stats
            self.db.close()

        logger.info(
            f"=== ETL Pipeline Complete ===\n"
            f"  Fetched: {total_summary['total_fetched']}\n"
            f"  Saved: {total_summary['total_saved']}\n"
            f"  Errors: {total_summary['errors']}"
        )

        return total_summary

    def _harvest_type(
        self,
        decision_type: str,
        from_date: date,
        to_date: date,
        org_uid: Optional[str],
        dry_run: bool,
    ) -> dict:
        """Harvest a single decision type over a date range."""
        logger.info(f"Harvesting type={decision_type} from {from_date} to {to_date}")

        summary = {
            "type": decision_type,
            "fetched": 0,
            "saved": 0,
            "errors": 0,
        }

        # Log harvest start
        harvest_id = None
        if not dry_run:
            harvest_id = self.db.start_harvest(from_date, decision_type)

        try:
            # Iterate day by day for better progress tracking and resumability
            current_date = from_date
            while current_date <= to_date:
                day_fetched, day_saved, day_errors = self._harvest_single_day(
                    decision_type, current_date, org_uid, dry_run
                )
                summary["fetched"] += day_fetched
                summary["saved"] += day_saved
                summary["errors"] += day_errors
                current_date += timedelta(days=1)

            # Log harvest completion
            status = "COMPLETED" if summary["errors"] == 0 else "COMPLETED_WITH_ERRORS"
            if not dry_run and harvest_id:
                self.db.finish_harvest(
                    harvest_id, summary["fetched"], summary["saved"], status
                )

        except Exception as e:
            logger.error(f"Harvest failed: {e}", exc_info=True)
            summary["errors"] += 1
            if not dry_run and harvest_id:
                self.db.finish_harvest(
                    harvest_id, summary["fetched"], summary["saved"], "FAILED"
                )

        return summary

    def _harvest_single_day(
        self,
        decision_type: str,
        target_date: date,
        org_uid: Optional[str],
        dry_run: bool,
    ) -> tuple[int, int, int]:
        """Harvest all decisions for a single day. Returns (fetched, saved, errors)."""
        fetched = 0
        saved = 0
        errors = 0

        try:
            decisions = self.api.harvest_day(
                target_date=target_date,
                decision_type=decision_type,
                org_uid=org_uid,
            )
            fetched = len(decisions)

            if dry_run:
                for d in decisions[:3]:  # Print first 3 in dry run
                    logger.info(
                        f"  [DRY RUN] ADA={d.get('ada')} "
                        f"Subject={d.get('subject', '')[:80]}"
                    )
                return fetched, 0, 0

            for decision in decisions:
                try:
                    decision_id = self.db.upsert_decision(decision)
                    if decision_id:
                        saved += 1
                except Exception as e:
                    errors += 1
                    logger.error(
                        f"Error saving decision {decision.get('ada')}: {e}"
                    )

            logger.info(
                f"  {target_date}: fetched={fetched} saved={saved} errors={errors}"
            )

        except DiavgeiaAPIError as e:
            errors += 1
            logger.error(f"  {target_date}: API error: {e}")

        return fetched, saved, errors


# ============================================================
# CLI Entry Point
# ============================================================

def parse_date(s: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        parts = s.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(f"Invalid date: {s}. Use YYYY-MM-DD format.")


def main():
    parser = argparse.ArgumentParser(
        description="Diavgeia-Watch ETL Pipeline: Harvest government spending data"
    )
    parser.add_argument(
        "--from", dest="from_date", type=parse_date, default=None,
        help="Start date (YYYY-MM-DD). Default: resume from last harvest or 7 days ago"
    )
    parser.add_argument(
        "--to", dest="to_date", type=parse_date, default=None,
        help="End date (YYYY-MM-DD). Default: yesterday"
    )
    parser.add_argument(
        "--org", dest="org_uid", default=None,
        help="Filter by organization UID (e.g. '5001' for Athens Municipality)"
    )
    parser.add_argument(
        "--types", nargs="+", default=None,
        help="Decision types to harvest (e.g. 'Β.2.1' 'Δ.1'). Default: Β.2.1"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch from API but don't save to database"
    )
    parser.add_argument(
        "--db-host", default="localhost",
        help="PostgreSQL host (default: localhost)"
    )
    parser.add_argument(
        "--db-port", type=int, default=5432,
        help="PostgreSQL port (default: 5432)"
    )

    args = parser.parse_args()

    # Build DB config
    db_config = {
        "host": args.db_host,
        "port": args.db_port,
        "dbname": "diavgeia",
        "user": "diavgeia",
        "password": "diavgeia_dev_2024",
    }

    # Run pipeline
    pipeline = ETLPipeline(
        api_client=DiavgeiaClient(),
        db_manager=DatabaseManager(config=db_config),
    )

    summary = pipeline.run(
        from_date=args.from_date,
        to_date=args.to_date,
        decision_types=args.types,
        org_uid=args.org_uid,
        dry_run=args.dry_run,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("HARVEST SUMMARY")
    print("=" * 60)
    print(f"Date range:  {summary['from_date']} to {summary['to_date']}")
    print(f"Fetched:     {summary['total_fetched']}")
    print(f"Saved:       {summary['total_saved']}")
    print(f"Errors:      {summary['errors']}")
    if "db_stats" in summary:
        stats = summary["db_stats"]
        print(f"\nDatabase totals:")
        print(f"  Decisions:     {stats['total_decisions']}")
        print(f"  Expense items: {stats['total_expense_items']}")
        print(f"  Organizations: {stats['unique_organizations']}")
        print(f"  Contractors:   {stats['unique_contractors']}")
        print(f"  Total amount:  €{stats['total_amount']:,.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()