"""
Diavgeia-Watch: Organization Resolver

Maps colloquial Greek organization names to Diavgeia organization UIDs.
Includes the most commonly queried municipalities, ministries, and public bodies.

This module provides:
1. A hardcoded lookup of the ~100 most important orgs (fast, no DB needed)
2. A database-backed fuzzy search for everything else
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Top Greek Government Organizations
# ============================================================
# Source: Diavgeia organization directory
# Format: (uid, label, aliases)

ORG_DATABASE = [
    # --- MUNICIPALITIES (ΔΗΜΟΙ) ---
    ("6105", "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ", [
        "δήμος αθηναίων", "δήμος αθήνας", "athens municipality",
        "αθήνα", "athens", "δήμος αθηνών"
    ]),
    ("6127", "ΔΗΜΟΣ ΘΕΣΣΑΛΟΝΙΚΗΣ", [
        "δήμος θεσσαλονίκης", "thessaloniki municipality",
        "θεσσαλονίκη", "thessaloniki", "σαλονίκη"
    ]),
    ("6144", "ΔΗΜΟΣ ΠΕΙΡΑΙΩΣ", [
        "δήμος πειραιά", "δήμος πειραιώς", "piraeus municipality",
        "πειραιάς", "piraeus"
    ]),
    ("6154", "ΔΗΜΟΣ ΠΑΤΡΕΩΝ", [
        "δήμος πατρέων", "δήμος πάτρας", "patras municipality",
        "πάτρα", "patras"
    ]),
    ("6148", "ΔΗΜΟΣ ΗΡΑΚΛΕΙΟΥ ΚΡΗΤΗΣ", [
        "δήμος ηρακλείου", "heraklion municipality",
        "ηράκλειο", "heraklion"
    ]),
    ("6164", "ΔΗΜΟΣ ΛΑΡΙΣΑΙΩΝ", [
        "δήμος λαρισαίων", "δήμος λάρισας", "larissa municipality",
        "λάρισα", "larissa"
    ]),
    ("6184", "ΔΗΜΟΣ ΒΟΛΟΥ", [
        "δήμος βόλου", "volos municipality", "βόλος", "volos"
    ]),
    ("6137", "ΔΗΜΟΣ ΙΩΑΝΝΙΤΩΝ", [
        "δήμος ιωαννιτών", "δήμος ιωαννίνων", "ioannina municipality",
        "ιωάννινα", "γιάννενα", "ioannina"
    ]),
    ("6183", "ΔΗΜΟΣ ΤΡΙΚΚΑΙΩΝ", [
        "δήμος τρικκαίων", "δήμος τρικάλων", "trikala municipality",
        "τρίκαλα", "trikala"
    ]),
    ("6156", "ΔΗΜΟΣ ΧΑΝΙΩΝ", [
        "δήμος χανίων", "chania municipality", "χανιά", "chania"
    ]),
    ("6174", "ΔΗΜΟΣ ΚΑΒΑΛΑΣ", [
        "δήμος καβάλας", "kavala municipality", "καβάλα", "kavala"
    ]),
    ("6169", "ΔΗΜΟΣ ΚΑΛΑΜΑΤΑΣ", [
        "δήμος καλαμάτας", "kalamata municipality", "καλαμάτα", "kalamata"
    ]),
    ("6115", "ΔΗΜΟΣ ΚΗΦΙΣΙΑΣ", [
        "δήμος κηφισιάς", "kifisia municipality", "κηφισιά", "kifisia"
    ]),
    ("6110", "ΔΗΜΟΣ ΜΑΡΟΥΣΙΟΥ", [
        "δήμος αμαρουσίου", "δήμος μαρουσίου", "marousi municipality",
        "μαρούσι", "αμαρούσιο", "marousi"
    ]),
    ("6120", "ΔΗΜΟΣ ΓΛΥΦΑΔΑΣ", [
        "δήμος γλυφάδας", "glyfada municipality", "γλυφάδα", "glyfada"
    ]),
    ("6158", "ΔΗΜΟΣ ΡΟΔΟΥ", [
        "δήμος ρόδου", "rhodes municipality", "ρόδος", "rhodes"
    ]),
    ("6175", "ΔΗΜΟΣ ΚΕΡΚΥΡΑΣ", [
        "δήμος κέρκυρας", "corfu municipality", "κέρκυρα", "corfu"
    ]),

    # --- MINISTRIES (ΥΠΟΥΡΓΕΙΑ) ---
    ("100015966", "ΥΠΟΥΡΓΕΙΟ ΠΟΛΙΤΙΣΜΟΥ ΚΑΙ ΑΘΛΗΤΙΣΜΟΥ", [
        "υπουργείο πολιτισμού", "ministry of culture",
        "πολιτισμός", "αθλητισμός"
    ]),
    ("100003788", "ΥΠΟΥΡΓΕΙΟ ΠΑΙΔΕΙΑΣ", [
        "υπουργείο παιδείας", "ministry of education",
        "παιδεία", "εκπαίδευση", "education"
    ]),
    ("100003831", "ΥΠΟΥΡΓΕΙΟ ΥΓΕΙΑΣ", [
        "υπουργείο υγείας", "ministry of health",
        "υγεία", "health"
    ]),
    ("100003836", "ΥΠΟΥΡΓΕΙΟ ΟΙΚΟΝΟΜΙΚΩΝ", [
        "υπουργείο οικονομικών", "ministry of finance",
        "οικονομικά", "finance"
    ]),
    ("100003839", "ΥΠΟΥΡΓΕΙΟ ΕΣΩΤΕΡΙΚΩΝ", [
        "υπουργείο εσωτερικών", "ministry of interior",
        "εσωτερικά", "interior"
    ]),
    ("100003846", "ΥΠΟΥΡΓΕΙΟ ΕΘΝΙΚΗΣ ΑΜΥΝΑΣ", [
        "υπουργείο εθνικής άμυνας", "ministry of defense",
        "άμυνα", "στρατός", "defense"
    ]),

    # --- REGIONS (ΠΕΡΙΦΕΡΕΙΕΣ) ---
    ("100005747", "ΠΕΡΙΦΕΡΕΙΑ ΑΤΤΙΚΗΣ", [
        "περιφέρεια αττικής", "attica region",
        "αττική", "attica"
    ]),
    ("100005752", "ΠΕΡΙΦΕΡΕΙΑ ΚΕΝΤΡΙΚΗΣ ΜΑΚΕΔΟΝΙΑΣ", [
        "περιφέρεια κεντρικής μακεδονίας", "central macedonia region",
        "κεντρική μακεδονία"
    ]),
    ("100005760", "ΠΕΡΙΦΕΡΕΙΑ ΚΡΗΤΗΣ", [
        "περιφέρεια κρήτης", "crete region", "κρήτη", "crete"
    ]),

    # --- PUBLIC ENTITIES ---
    ("99222376", "ΕΦΚΑ", [
        "εφκα", "efka", "ασφαλιστικό ταμείο",
        "κοινωνική ασφάλιση", "social insurance"
    ]),
    ("100012982", "ΕΡΤ Α.Ε.", [
        "ερτ", "ert", "ελληνική ραδιοφωνία τηλεόραση",
        "greek broadcasting"
    ]),
    ("99206919", "ΟΑΕΔ / ΔΥΠΑ", [
        "οαεδ", "δυπα", "dypa", "oaed",
        "δημόσια υπηρεσία απασχόλησης", "employment agency"
    ]),
]


class OrgResolver:
    """
    Resolve organization names to Diavgeia UIDs.

    Combines a hardcoded lookup of major organizations
    with optional database-backed fuzzy search.
    """

    def __init__(self, db_manager=None):
        """
        Args:
            db_manager: Optional DatabaseManager for DB-backed fuzzy search.
                        If None, only the hardcoded lookup is used.
        """
        self.db = db_manager
        self._build_index()

    def _build_index(self):
        """Build the search index from the hardcoded database."""
        self._by_uid = {}
        self._by_alias = {}

        for uid, label, aliases in ORG_DATABASE:
            self._by_uid[uid] = {"uid": uid, "label": label}
            # Index all aliases (lowercase)
            for alias in aliases:
                self._by_alias[alias.lower().strip()] = uid
            # Also index the official label
            self._by_alias[label.lower().strip()] = uid

    def resolve(self, query: str) -> Optional[dict]:
        """
        Resolve a query string to an organization.

        Tries exact match first, then fuzzy matching.

        Args:
            query: Organization name or UID (Greek or English)

        Returns:
            {"uid": "...", "label": "..."} or None
        """
        query_clean = query.lower().strip()

        # 1. Direct UID match
        if query_clean in self._by_uid:
            return self._by_uid[query_clean]

        # 2. Exact alias match
        if query_clean in self._by_alias:
            uid = self._by_alias[query_clean]
            return self._by_uid[uid]

        # 3. Substring match in aliases
        best_match = None
        best_score = 0
        for alias, uid in self._by_alias.items():
            if query_clean in alias or alias in query_clean:
                score = len(alias)  # longer match = better
                if score > best_score:
                    best_score = score
                    best_match = uid

        if best_match:
            return self._by_uid[best_match]

        # 4. DB fuzzy search (if available)
        if self.db:
            return self._db_search(query_clean)

        return None

    def _db_search(self, query: str) -> Optional[dict]:
        """Search the organizations table using trigram similarity."""
        try:
            with self.db.get_cursor(commit=False) as cur:
                cur.execute("""
                    SELECT uid, label,
                           similarity(lower(label), %(q)s) AS sim
                    FROM organizations
                    WHERE lower(label) %% %(q)s
                    ORDER BY sim DESC
                    LIMIT 1
                """, {"q": query})
                row = cur.fetchone()
                if row and row["sim"] > 0.2:
                    return {"uid": row["uid"], "label": row["label"]}
        except Exception as e:
            logger.warning(f"DB org search failed: {e}")
        return None

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search for organizations matching a query. Returns multiple results.

        Used by the agent when it's not sure which org the user means.
        """
        query_clean = query.lower().strip()
        results = []
        seen = set()

        for alias, uid in self._by_alias.items():
            if query_clean in alias or alias in query_clean:
                if uid not in seen:
                    seen.add(uid)
                    results.append(self._by_uid[uid])

        # Sort by label length (shorter = more specific = probably better)
        results.sort(key=lambda x: len(x["label"]))
        return results[:limit]

    def get_all_for_prompt(self) -> str:
        """
        Generate a compact org reference table for the LLM system prompt.
        Only includes the most important orgs to save tokens.
        """
        lines = ["UID | Organization"]
        lines.append("-" * 50)
        for uid, label, aliases in ORG_DATABASE[:30]:  # top 30 to save tokens
            short_aliases = ", ".join(aliases[:2])
            lines.append(f"{uid} | {label} (aka: {short_aliases})")
        return "\n".join(lines)