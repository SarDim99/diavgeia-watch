"""
Diavgeia Open Data API Client
Wrapper for https://diavgeia.gov.gr/luminapi/opendata

Handles: searching decisions, fetching details, pagination, and rate limiting.
No API key needed — Diavgeia is fully public.
"""

import time
import logging
from typing import Optional, Iterator
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

BASE_URL = "https://diavgeia.gov.gr/luminapi/opendata"

# Decision types relevant to spending
DECISION_TYPES = {
    "EXPENDITURE_APPROVAL": "Β.2.1",   # ΕΓΚΡΙΣΗ ΔΑΠΑΝΗΣ
    "EXPENDITURE_COMMIT":   "Β.1.3",   # ΑΝΑΛΗΨΗ ΥΠΟΧΡΕΩΣΗΣ
    "CONTRACT":             "Δ.1",     # ΣΥΜΒΑΣΗ
    "AWARD":                "Δ.2.1",   # ΑΝΑΘΕΣΗ ΕΡΓΩΝ / ΠΡΟΜΗΘΕΙΩΝ / ΥΠΗΡΕΣΙΩΝ
    "BUDGET":               "Α.3",     # ΠΡΟΫΠΟΛΟΓΙΣΜΟΣ
}

# Diavgeia API paginates with max 500 per page
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 100

# Be polite to the API
REQUEST_DELAY_SECONDS = 0.5


class DiavgeiaAPIError(Exception):
    """Raised when the Diavgeia API returns an error."""
    pass


class DiavgeiaClient:
    """
    Client for the Diavgeia Open Data API.

    Usage:
        client = DiavgeiaClient()

        # Search expenditure decisions for a specific date
        for decision in client.search_decisions(
            decision_type="Β.2.1",
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 31)
        ):
            print(decision['ada'], decision.get('subject'))

        # Get full details of a specific decision
        details = client.get_decision("Ψ4Ε2ΟΡΗ8-ΦΒ7")
    """

    def __init__(self, base_url: str = BASE_URL, delay: float = REQUEST_DELAY_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.delay = delay

        # Set up session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "DiavgeiaWatch/1.0 (research project)",
        })

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the API with rate limiting."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        time.sleep(self.delay)

        logger.debug(f"GET {url} params={params}")
        try:
            resp = self.session.get(url, params=params, timeout=30)
            logger.info(f"API call: {resp.url} → {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {resp.status_code}: {resp.text[:500]}")
            raise DiavgeiaAPIError(f"API returned {resp.status_code}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise DiavgeiaAPIError(f"Request failed: {e}") from e

    # -----------------------------------------------------------
    # Decision Types & Organizations
    # -----------------------------------------------------------

    def get_decision_types(self) -> list:
        """Fetch all available decision types."""
        return self._get("types")

    def get_decision_type_details(self, type_uid: str) -> dict:
        """Fetch field definitions for a specific decision type."""
        encoded = quote(type_uid, safe="")
        return self._get(f"types/{encoded}/details")

    def get_organizations(self) -> list:
        """Fetch all registered organizations."""
        return self._get("organizations")

    def get_organization(self, org_uid: str) -> dict:
        """Fetch details for a specific organization."""
        return self._get(f"organizations/{org_uid}")

    # -----------------------------------------------------------
    # Search Decisions (the core harvesting method)
    # -----------------------------------------------------------

    def search_decisions(
        self,
        decision_type: str = "Β.2.1",
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        org_uid: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Search for decisions with pagination.

        Yields individual decision dicts, handling pagination automatically.

        Args:
            decision_type: Diavgeia type code (default: "Β.2.1" = expenditure approval)
            from_date: Start date for issue date filter
            to_date: End date for issue date filter
            org_uid: Filter by organization UID
            page_size: Results per page (max 500)
            max_pages: Stop after N pages (None = fetch all)
        """
        page_size = min(page_size, MAX_PAGE_SIZE)
        page = 0
        total_fetched = 0

        while True:
            params = {
                "type": decision_type,
                "size": page_size,
                "page": page,
                "status": "all",
            }

            # Add date range filter
            if from_date:
                params["from_issue_date"] = from_date.isoformat()
            if to_date:
                params["to_issue_date"] = to_date.isoformat()

            # Add organization filter
            if org_uid:
                params["org"] = org_uid

            try:
                data = self._get("search", params=params)
            except DiavgeiaAPIError as e:
                logger.error(f"Search failed on page {page}: {e}")
                break

            # The response contains a 'decisions' array
            decisions = data.get("decisions", [])
            if not decisions:
                logger.info(f"No more decisions found. Total fetched: {total_fetched}")
                break

            for decision in decisions:
                total_fetched += 1
                yield decision

            # Check if we've reached the end
            total_results = data.get("info", {}).get("total", 0)
            logger.info(
                f"Page {page}: got {len(decisions)} decisions "
                f"({total_fetched}/{total_results} total)"
            )

            if total_fetched >= total_results:
                break

            if max_pages and page >= max_pages - 1:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break

            page += 1

    # -----------------------------------------------------------
    # Advanced Search (Lucene/Solr syntax)
    # -----------------------------------------------------------

    def advanced_search(
        self,
        query: str,
        filter_query: Optional[str] = None,
        page: int = 0,
        size: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Advanced search using Lucene/Solr query syntax.

        Examples:
            # All expenditure approvals for a specific org
            client.advanced_search(
                query='decisionTypeUid:"Β.2.1" AND organizationUid:"100015966"'
            )

            # Search by contractor AFM
            client.advanced_search(query='receiverAFM:"123456789"')

            # Search by CPV code
            client.advanced_search(query='cpv:"90910000"')

        Args:
            query: Lucene query string
            filter_query: Additional filter (Solr fq parameter)
            page: Page number (0-based)
            size: Results per page
        """
        params = {
            "q": query,
            "page": page,
            "size": min(size, MAX_PAGE_SIZE),
        }
        if filter_query:
            params["fq"] = filter_query

        return self._get("search/advanced", params=params)

    # -----------------------------------------------------------
    # Individual Decision
    # -----------------------------------------------------------

    def get_decision(self, ada: str) -> dict:
        """
        Fetch full details of a single decision by its ADA.

        Args:
            ada: The unique decision identifier (e.g. "Ψ4Ε2ΟΡΗ8-ΦΒ7")
        """
        encoded_ada = quote(ada, safe="")
        return self._get(f"decisions/{encoded_ada}")

    # -----------------------------------------------------------
    # Dictionaries (CPV codes, currencies, etc.)
    # -----------------------------------------------------------

    def get_dictionaries(self) -> list:
        """Fetch available data dictionaries."""
        return self._get("dictionaries")

    def get_dictionary(self, name: str) -> dict:
        """
        Fetch a specific dictionary (e.g. CPV codes).

        Args:
            name: Dictionary name (e.g. "CPV", "CURRENCY", "VAT_TYPE")
        """
        return self._get(f"dictionaries/{name}")

    # -----------------------------------------------------------
    # Convenience: Daily Harvest
    # -----------------------------------------------------------

    def harvest_day(
        self,
        target_date: date,
        decision_type: str = "Β.2.1",
        org_uid: Optional[str] = None,
    ) -> list[dict]:
        """
        Convenience method: fetch all decisions for a single day.

        Args:
            target_date: The date to harvest
            decision_type: Type code
            org_uid: Optional organization filter

        Returns:
            List of decision dicts
        """
        results = list(self.search_decisions(
            decision_type=decision_type,
            from_date=target_date,
            to_date=target_date,
            org_uid=org_uid,
        ))
        logger.info(
            f"Harvested {len(results)} decisions for "
            f"{target_date.isoformat()} type={decision_type}"
        )
        return results

    def harvest_date_range(
        self,
        start_date: date,
        end_date: date,
        decision_type: str = "Β.2.1",
        org_uid: Optional[str] = None,
        chunk_days: int = 7,
    ) -> Iterator[dict]:
        """
        Harvest decisions over a date range, chunked into smaller windows
        to avoid overwhelming the API.

        Args:
            start_date: First day
            end_date: Last day (inclusive)
            decision_type: Type code
            org_uid: Optional organization filter
            chunk_days: Days per API request window
        """
        current = start_date
        while current <= end_date:
            chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
            logger.info(f"Harvesting chunk: {current} to {chunk_end}")

            yield from self.search_decisions(
                decision_type=decision_type,
                from_date=current,
                to_date=chunk_end,
                org_uid=org_uid,
            )

            current = chunk_end + timedelta(days=1)