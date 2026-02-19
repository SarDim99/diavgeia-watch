"""
Diavgeia-Watch: Greek Bureaucratic Intelligence Layer (Phase 3)

Translates Greek bureaucracy-speak into structured context that helps
the LLM generate accurate SQL queries. Handles:

- Bureaucratic terminology (ΕΓΚΡΙΣΗ ΔΑΠΑΝΗΣ, ΑΠΕΥΘΕΙΑΣ ΑΝΑΘΕΣΗ, etc.)
- KAE/ALE budget codes
- Decision type classification
- Procurement method detection
- Amount threshold awareness (Greek procurement law thresholds)

This replaces the need for fine-tuning by acting as a domain-specific
preprocessor between the user's question and the LLM.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Greek Bureaucratic Glossary
# ============================================================
# Maps Greek bureaucratic terms to structured metadata that helps
# the LLM understand what the user is asking about.

GLOSSARY = {
    # --- Decision Types ---
    "έγκριση δαπάνης": {
        "meaning": "expenditure approval decision",
        "sql_hint": "subject ILIKE '%ΕΓΚΡΙΣ%ΔΑΠΑΝ%'",
    },
    "εγκριση δαπανης": {
        "meaning": "expenditure approval decision",
        "sql_hint": "subject ILIKE '%ΕΓΚΡΙΣ%ΔΑΠΑΝ%'",
    },
    "ανάληψη υποχρέωσης": {
        "meaning": "budget commitment / obligation",
        "sql_hint": "subject ILIKE '%ΑΝΑΛΗΨ%ΥΠΟΧΡΕΩΣ%'",
    },
    "αναληψη υποχρεωσης": {
        "meaning": "budget commitment / obligation",
        "sql_hint": "subject ILIKE '%ΑΝΑΛΗΨ%ΥΠΟΧΡΕΩΣ%'",
    },
    "σύμβαση": {
        "meaning": "contract / agreement",
        "sql_hint": "subject ILIKE '%ΣΥΜΒΑΣ%'",
    },
    "διακήρυξη": {
        "meaning": "procurement notice / tender announcement",
        "sql_hint": "subject ILIKE '%ΔΙΑΚΗΡΥΞ%'",
    },
    "κατακύρωση": {
        "meaning": "contract award decision",
        "sql_hint": "subject ILIKE '%ΚΑΤΑΚΥΡΩΣ%'",
    },
    "χρηματικό ένταλμα": {
        "meaning": "payment warrant / payment order",
        "sql_hint": "subject ILIKE '%ΧΡΗΜΑΤΙΚ%ΕΝΤΑΛΜ%'",
    },
    "προϋπολογισμός": {
        "meaning": "budget",
        "sql_hint": None,
    },

    # --- Procurement Methods ---
    "απευθείας ανάθεση": {
        "meaning": "direct award without competitive tender",
        "sql_hint": "subject ILIKE '%ΑΠΕΥΘΕΙΑΣ%ΑΝΑΘΕΣ%'",
    },
    "απευθειας αναθεση": {
        "meaning": "direct award without competitive tender",
        "sql_hint": "subject ILIKE '%ΑΠΕΥΘΕΙΑΣ%ΑΝΑΘΕΣ%'",
    },
    "ανοιχτός διαγωνισμός": {
        "meaning": "open tender / competitive procurement",
        "sql_hint": "subject ILIKE '%ΑΝΟΙΧΤ%ΔΙΑΓΩΝΙΣΜ%'",
    },
    "συνοπτικός διαγωνισμός": {
        "meaning": "simplified tender (€30k-€60k range)",
        "sql_hint": "subject ILIKE '%ΣΥΝΟΠΤΙΚ%ΔΙΑΓΩΝΙΣΜ%'",
    },
    "πρόχειρος διαγωνισμός": {
        "meaning": "simplified tender (older term)",
        "sql_hint": "subject ILIKE '%ΠΡΟΧΕΙΡ%ΔΙΑΓΩΝΙΣΜ%'",
    },

    # --- Common Spending Categories (Greek) ---
    "μίσθωση": {
        "meaning": "rental / lease",
        "sql_hint": "subject ILIKE '%ΜΙΣΘΩΣ%'",
    },
    "προμήθεια": {
        "meaning": "procurement / supply of goods",
        "sql_hint": "subject ILIKE '%ΠΡΟΜΗΘΕΙ%'",
    },
    "υπηρεσία": {
        "meaning": "service provision",
        "sql_hint": "subject ILIKE '%ΥΠΗΡΕΣΙ%'",
    },
    "έργο": {
        "meaning": "public works / construction project",
        "sql_hint": "subject ILIKE '%ΕΡΓΟ%' OR subject ILIKE '%ΕΡΓΑΣΙ%'",
    },
    "μελέτη": {
        "meaning": "study / consultancy",
        "sql_hint": "subject ILIKE '%ΜΕΛΕΤ%'",
    },
    "συντήρηση": {
        "meaning": "maintenance",
        "sql_hint": "subject ILIKE '%ΣΥΝΤΗΡΗΣ%'",
    },
    "φύλαξη": {
        "meaning": "security / guarding services",
        "sql_hint": "subject ILIKE '%ΦΥΛΑΞ%'",
    },
    "μεταφορά": {
        "meaning": "transport / transfer",
        "sql_hint": "subject ILIKE '%ΜΕΤΑΦΟΡ%'",
    },

    # --- Budget Codes ---
    "καε": {
        "meaning": "KAE = budget account code (Κωδικός Αριθμός Εξόδων)",
        "sql_hint": "kae_code is the budget classification field in expense_items",
    },
    "αλε": {
        "meaning": "ALE = revenue/expense classification code (Αναλυτική Λογιστική Εξόδων)",
        "sql_hint": "kae_code field (ALE codes are stored in the same field)",
    },
    "αφμ": {
        "meaning": "AFM = Tax ID number (Αριθμός Φορολογικού Μητρώου)",
        "sql_hint": "contractor_afm or org_afm field",
    },
    "αδα": {
        "meaning": "ADA = unique decision ID on Diavgeia (Αριθμός Διαδικτυακής Ανάρτησης)",
        "sql_hint": "ada field in decisions table",
    },
}


# ============================================================
# KAE Budget Code Categories (most common)
# ============================================================

KAE_DATABASE = [
    # Format: (code_prefix, description_gr, description_en, keywords)
    ("0200", "Αμοιβές υπαλλήλων", "Employee salaries", "μισθοί αμοιβές υπάλληλοι προσωπικό"),
    ("0400", "Εργοδοτικές εισφορές", "Employer contributions", "εισφορές ασφάλιση εργοδοτικές"),
    ("0800", "Πληρωμές για υπηρεσίες", "Service payments", "υπηρεσίες αμοιβές τρίτων"),
    ("0831", "Μεταφορές", "Transport services", "μεταφορά μεταφορές"),
    ("0851", "Συντήρηση κτιρίων", "Building maintenance", "συντήρηση κτίρια επισκευή"),
    ("0861", "Συντήρηση οχημάτων", "Vehicle maintenance", "οχήματα αυτοκίνητα συντήρηση"),
    ("0869", "Συντήρηση λοιπού εξοπλισμού", "Equipment maintenance", "εξοπλισμός συντήρηση"),
    ("1000", "Προμήθειες", "Supplies/procurement", "προμήθεια αγορά υλικά"),
    ("1111", "Γραφική ύλη", "Office supplies", "γραφική ύλη χαρτί τόνερ"),
    ("1211", "Καύσιμα", "Fuel", "καύσιμα βενζίνη πετρέλαιο"),
    ("1311", "Ηλεκτρικό ρεύμα", "Electricity", "ηλεκτρικό ρεύμα ΔΕΗ"),
    ("1321", "Τηλεπικοινωνίες", "Telecommunications", "τηλέφωνο internet τηλεπικοινωνίες"),
    ("1511", "Ιατροφαρμακευτική περίθαλψη", "Medical care", "ιατρικά φάρμακα νοσοκομείο"),
    ("1700", "Μισθώματα", "Rental payments", "ενοίκιο μίσθωμα μίσθωση"),
    ("5000", "Δαπάνες δημοσίων επενδύσεων", "Public investment spending", "επένδυση δημόσια έργα"),
    ("6000", "Πληρωμές δανείων", "Loan payments", "δάνειο τόκοι αποπληρωμή"),
    ("7000", "Αποθεματικά", "Reserves", "αποθεματικό έκτακτα"),
]


# ============================================================
# Greek Procurement Thresholds
# ============================================================

PROCUREMENT_THRESHOLDS = {
    "direct_award": {
        "limit_eur": 30000,
        "greek": "ΑΠΕΥΘΕΙΑΣ ΑΝΑΘΕΣΗ",
        "description": "Direct award without tender (< €30,000 excl. VAT)",
    },
    "simplified_tender": {
        "limit_eur": 60000,
        "greek": "ΣΥΝΟΠΤΙΚΟΣ ΔΙΑΓΩΝΙΣΜΟΣ",
        "description": "Simplified tender (€30,000 - €60,000)",
    },
    "open_tender_supplies": {
        "limit_eur": 140000,
        "greek": "ΑΝΟΙΧΤΟΣ ΔΙΑΓΩΝΙΣΜΟΣ",
        "description": "Open tender for supplies/services (> €140,000 EU threshold)",
    },
    "open_tender_works": {
        "limit_eur": 5382000,
        "greek": "ΑΝΟΙΧΤΟΣ ΔΙΑΓΩΝΙΣΜΟΣ ΕΡΓΩΝ",
        "description": "Open tender for public works (> €5,382,000 EU threshold)",
    },
}

# Decision types supported by Diavgeia
DECISION_TYPES = {
    "Β.1.3": "Ανάληψη Υποχρέωσης (Budget Commitment)",
    "Β.2.1": "Έγκριση Δαπάνης (Expenditure Approval)",
    "Β.2.2": "Εντολή Πληρωμής (Payment Order)",
    "Δ.1": "Σύμβαση (Contract)",
    "Δ.2": "Διακήρυξη (Tender Notice)",
    "Δ.3": "Κατακύρωση (Contract Award)",
}


# ============================================================
# Bureaucratic Query Preprocessor
# ============================================================

class BureaucracyLayer:
    """
    Preprocesses natural language queries to detect Greek bureaucratic
    terms and enrich the LLM context with structured hints.
    """

    def __init__(self):
        self.glossary = GLOSSARY
        self.kae_db = KAE_DATABASE
        self.thresholds = PROCUREMENT_THRESHOLDS
        self.decision_types = DECISION_TYPES

    def preprocess(self, question: str) -> dict:
        """
        Analyze a question and return structured context.

        Returns:
            {
                "glossary_hits": [...],     # matched bureaucratic terms
                "kae_hints": [...],         # matched budget codes
                "procurement_method": ...,  # detected procurement method
                "decision_type_hint": ...,  # detected decision type
                "sql_hints": [...],         # SQL WHERE clause suggestions
                "context_text": "...",      # Formatted text for the LLM
            }
        """
        q_lower = question.lower()
        q_lower_no_accent = self._strip_accents(q_lower)

        result = {
            "glossary_hits": [],
            "kae_hints": [],
            "procurement_method": None,
            "decision_type_hint": None,
            "sql_hints": [],
            "context_text": "",
        }

        # 1. Match glossary terms (with prefix matching for Greek word forms)
        for term, info in self.glossary.items():
            term_no_accent = self._strip_accents(term)
            term_words = term_no_accent.split()

            # Check if ALL words from the term appear in the query
            # Using prefix matching (first 4+ chars) to handle Greek inflections
            # e.g. "ανάθεση" matches "αναθέσεις", "αναθέσεων", etc.
            all_words_match = True
            for tw in term_words:
                prefix = tw[:min(5, len(tw))]  # first 5 chars as prefix
                if prefix not in q_lower_no_accent:
                    all_words_match = False
                    break

            if all_words_match and len(term_words) >= 1:
                hit = {"term": term, **info}
                result["glossary_hits"].append(hit)
                if info.get("sql_hint"):
                    result["sql_hints"].append(info["sql_hint"])
                if info.get("decision_type"):
                    result["decision_type_hint"] = info["decision_type"]
                if info.get("threshold_info"):
                    result["procurement_method"] = info

        # 2. Match KAE codes
        kae_match = re.search(r'(?:καε|kae|αλε|ale)\s*[:\s]?\s*(\d{4})', q_lower)
        if kae_match:
            code = kae_match.group(1)
            result["sql_hints"].append(f"kae_code LIKE '{code}%'")
            # Find matching category
            for prefix, desc_gr, desc_en, _ in self.kae_db:
                if code.startswith(prefix[:2]):
                    result["kae_hints"].append(f"KAE {code}: {desc_en} ({desc_gr})")
                    break

        # Also do keyword matching for KAE categories
        for prefix, desc_gr, desc_en, keywords in self.kae_db:
            for kw in keywords.split():
                if len(kw) >= 4 and kw in q_lower:
                    result["kae_hints"].append(
                        f"Possibly related to KAE {prefix}: {desc_en} ({desc_gr})"
                    )
                    break

        # 3. Detect AFM references
        afm_match = re.search(r'(?:αφμ|afm)\s*[:\s]?\s*(\d{9})', q_lower)
        if afm_match:
            afm = afm_match.group(1)
            result["sql_hints"].append(
                f"contractor_afm = '{afm}' OR org_afm = '{afm}'"
            )

        # 4. Detect ADA references (Greek uppercase + digits + dash)
        ada_match = re.search(r'(?:αδα|ada|ΑΔΑ)\s*[:\s]?\s*([A-ZΑ-Ω0-9]{4,}-[A-ZΑ-Ω0-9]+)', question, re.IGNORECASE)
        if ada_match:
            ada = ada_match.group(1)
            result["sql_hints"].append(f"ada = '{ada}'")

        # 5. Build context text for the LLM
        context_parts = []

        if result["glossary_hits"]:
            for hit in result["glossary_hits"]:
                context_parts.append(
                    f"'{hit['term']}' means: {hit['meaning']}"
                )
                if hit.get("sql_hint"):
                    context_parts.append(f"  SQL filter: {hit['sql_hint']}")

        if result["kae_hints"]:
            for hint in result["kae_hints"][:2]:  # max 2
                context_parts.append(hint)

        if result["procurement_method"]:
            pass  # Threshold info available but NOT injected to avoid false filters

        result["context_text"] = "\n".join(context_parts) if context_parts else ""

        if result["context_text"]:
            logger.info(f"Bureaucracy layer found context: {result['context_text'][:100]}...")

        return result

    def get_threshold_context(self, amount: float) -> Optional[str]:
        """Given an amount, explain which procurement threshold it falls under."""
        if amount < 30000:
            return "This amount falls under the direct award threshold (< €30,000)"
        elif amount < 60000:
            return "This amount falls in the simplified tender range (€30,000 - €60,000)"
        elif amount < 140000:
            return "This amount is above simplified tender but below EU threshold"
        else:
            return "This amount is above the EU procurement threshold (> €140,000)"

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Remove Greek accents/tonos for fuzzy matching."""
        accent_map = {
            'ά': 'α', 'έ': 'ε', 'ή': 'η', 'ί': 'ι', 'ό': 'ο', 'ύ': 'υ', 'ώ': 'ω',
            'ΐ': 'ι', 'ΰ': 'υ', 'ϊ': 'ι', 'ϋ': 'υ',
        }
        return ''.join(accent_map.get(c, c) for c in text)