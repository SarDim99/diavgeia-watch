"""
Diavgeia-Watch: CPV Code Lookup

Maps colloquial Greek and English terms to CPV (Common Procurement Vocabulary)
codes used in Greek government spending decisions.

The CPV is a standardized EU classification system. Each code is 8 digits + check digit.
First 2 digits = division, next 1 = group, next 1 = class, next 1 = category.

This module provides a curated lookup of the most common spending categories
found in Diavgeia, plus fuzzy matching for the agent.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# CPV Code Database (most common in Greek public spending)
# ============================================================
# Format: (cpv_code, description_en, description_gr, keywords_gr, keywords_en)

CPV_DATABASE = [
    # -- CLEANING & MAINTENANCE --
    ("90910000", "Cleaning services", "Υπηρεσίες καθαρισμού",
     "καθαριότητα καθαρισμός σκούπισμα",
     "cleaning janitorial sweeping"),
    ("90911000", "Housing and building cleaning", "Καθαρισμός κατοικιών και κτιρίων",
     "καθαρισμός κτιρίων γραφείων",
     "building cleaning office cleaning"),
    ("90919000", "Office and school cleaning", "Καθαρισμός γραφείων και σχολείων",
     "καθαρισμός σχολείων γραφείων",
     "school cleaning office cleaning"),
    ("90500000", "Refuse and waste services", "Υπηρεσίες σχετιζόμενες με απορρίμματα",
     "απορρίμματα σκουπίδια ανακύκλωση αποκομιδή",
     "waste garbage recycling refuse collection"),
    ("90600000", "Street cleaning", "Υπηρεσίες καθαρισμού οδών",
     "καθαρισμός δρόμων οδών πλατειών",
     "street cleaning road cleaning"),

    # -- ROAD WORKS & CONSTRUCTION --
    ("45233141", "Road-maintenance works", "Εργασίες συντήρησης οδών",
     "συντήρηση δρόμων οδών επισκευή δρόμου ασφαλτόστρωση",
     "road maintenance road repair asphalt paving"),
    ("45233142", "Road-repair works", "Εργασίες επισκευής οδών",
     "επισκευή δρόμου αποκατάσταση οδού",
     "road repair road restoration"),
    ("45233120", "Road construction", "Κατασκευή οδών",
     "κατασκευή δρόμου νέος δρόμος",
     "road construction new road building"),
    ("45000000", "Construction work", "Κατασκευαστικές εργασίες",
     "κατασκευή οικοδομή εργοτάξιο",
     "construction building works"),
    ("45454000", "Restructuring work", "Εργασίες αναδιάρθρωσης",
     "ανακαίνιση αναδιάρθρωση μετατροπή",
     "renovation restructuring conversion"),

    # -- IT & TECHNOLOGY --
    ("72000000", "IT services", "Υπηρεσίες τεχνολογίας πληροφοριών",
     "πληροφορική IT τεχνολογία λογισμικό",
     "IT technology software computing"),
    ("72200000", "Software programming", "Προγραμματισμός λογισμικού",
     "προγραμματισμός λογισμικό ανάπτυξη εφαρμογών",
     "programming software development applications"),
    ("72400000", "Internet services", "Υπηρεσίες διαδικτύου",
     "διαδίκτυο internet ιστοσελίδα website",
     "internet web website hosting"),
    ("30200000", "Computer equipment", "Εξοπλισμός ηλεκτρονικών υπολογιστών",
     "υπολογιστές laptop εκτυπωτής οθόνη",
     "computers laptop printer monitor hardware"),
    ("48000000", "Software packages", "Πακέτα λογισμικού",
     "λογισμικό πρόγραμμα άδεια license",
     "software package license"),

    # -- CONSULTING & PROFESSIONAL SERVICES --
    ("79400000", "Business consulting", "Υπηρεσίες παροχής επιχειρηματικών συμβουλών",
     "σύμβουλος συμβουλευτική μελέτη consulting",
     "consulting advisory study business"),
    ("79200000", "Accounting services", "Λογιστικές υπηρεσίες",
     "λογιστής λογιστικά λογιστικές υπηρεσίες",
     "accounting accountant bookkeeping"),
    ("79100000", "Legal services", "Νομικές υπηρεσίες",
     "νομικός δικηγόρος νομική υπηρεσία",
     "legal lawyer attorney law"),
    ("79340000", "Advertising services", "Υπηρεσίες διαφήμισης",
     "διαφήμιση προβολή μάρκετινγκ",
     "advertising marketing promotion"),

    # -- FUEL & ENERGY --
    ("09100000", "Fuels", "Καύσιμα",
     "καύσιμα βενζίνη πετρέλαιο diesel",
     "fuel petrol diesel gasoline"),
    ("09300000", "Electricity and heating", "Ηλεκτρισμός και θέρμανση",
     "ηλεκτρικό ρεύμα θέρμανση ενέργεια ΔΕΗ",
     "electricity heating energy power"),
    ("65100000", "Water distribution", "Διανομή νερού",
     "νερό ύδρευση ΕΥΔΑΠ",
     "water supply distribution"),

    # -- MEDICAL & HEALTH --
    ("33000000", "Medical equipment", "Ιατρικά είδη",
     "ιατρικά υγειονομικά νοσοκομείο φάρμακα",
     "medical health hospital pharmaceutical"),
    ("33600000", "Pharmaceutical products", "Φαρμακευτικά προϊόντα",
     "φάρμακα φαρμακευτικά",
     "pharmaceutical drugs medicine"),
    ("85100000", "Health services", "Υπηρεσίες υγείας",
     "υγεία υγειονομικές υπηρεσίες ιατρικές",
     "health services medical care"),

    # -- OFFICE SUPPLIES --
    ("30190000", "Office equipment", "Εξοπλισμός γραφείου",
     "γραφείο αναλώσιμα γραφική ύλη",
     "office supplies stationery equipment"),
    ("22000000", "Printed matter", "Έντυπα",
     "εκτύπωση έντυπα βιβλία τυπογραφείο",
     "printing publications books print"),
    ("30125110", "Toner for printers", "Τόνερ εκτυπωτών",
     "τόνερ μελάνι εκτυπωτής αναλώσιμα εκτύπωσης",
     "toner ink printer consumables cartridge"),

    # -- TRANSPORT --
    ("60000000", "Transport services", "Υπηρεσίες μεταφορών",
     "μεταφορά μεταφορές δρομολόγια",
     "transport transportation logistics"),
    ("34000000", "Motor vehicles", "Μηχανοκίνητα οχήματα",
     "αυτοκίνητο όχημα αγορά οχήματος",
     "vehicle car motor purchase"),
    ("50100000", "Vehicle repair", "Επισκευή οχημάτων",
     "επισκευή οχήματος συντήρηση αυτοκινήτου",
     "vehicle repair car maintenance"),

    # -- FOOD & CATERING --
    ("55300000", "Restaurant and catering", "Υπηρεσίες εστιατορίου και σίτισης",
     "σίτιση τροφοδοσία catering γεύματα",
     "catering meals food service restaurant"),
    ("15000000", "Food products", "Τρόφιμα",
     "τρόφιμα φαγητό τροφοδοσία",
     "food products provisions"),

    # -- SECURITY --
    ("79710000", "Security services", "Υπηρεσίες ασφαλείας",
     "ασφάλεια φύλαξη security φρουρά",
     "security guard protection surveillance"),

    # -- TELECOMMUNICATIONS --
    ("64200000", "Telecommunications", "Τηλεπικοινωνίες",
     "τηλεπικοινωνίες τηλέφωνο κινητό internet",
     "telecommunications telephone mobile phone"),

    # -- EDUCATION & TRAINING --
    ("80000000", "Education services", "Υπηρεσίες εκπαίδευσης",
     "εκπαίδευση κατάρτιση σεμινάριο μάθημα",
     "education training seminar course"),

    # -- GREEN / ENVIRONMENTAL --
    ("77300000", "Horticultural services", "Υπηρεσίες κηπουρικής",
     "πράσινο κηπουρική δέντρα φυτά συντήρηση πρασίνου",
     "gardening horticulture trees plants green maintenance"),
    ("77310000", "Planting and maintenance", "Φύτευση και συντήρηση χώρων πρασίνου",
     "φύτευση πάρκα πράσινο",
     "planting parks green spaces"),

    # -- INSURANCE --
    ("66500000", "Insurance services", "Ασφαλιστικές υπηρεσίες",
     "ασφάλεια ασφάλιση ασφαλιστήριο",
     "insurance coverage policy"),

    # -- RENT --
    ("70000000", "Real estate services", "Υπηρεσίες ακίνητης περιουσίας",
     "ενοίκιο μίσθωμα ακίνητο κτίριο στέγαση",
     "rent lease real estate building housing"),

    # -- EVENTS & CULTURE --
    ("92000000", "Recreational and cultural services", "Υπηρεσίες αναψυχής και πολιτισμού",
     "πολιτισμός εκδήλωση φεστιβάλ συναυλία θέατρο",
     "culture events festival concert theatre"),
]


class CPVLookup:
    """
    Look up CPV codes from natural language queries.

    Provides both exact matching and keyword-based fuzzy search
    for the SQL agent to resolve user queries to CPV codes.
    """

    def __init__(self):
        self._entries = []
        for row in CPV_DATABASE:
            code, desc_en, desc_gr, kw_gr, kw_en = row
            self._entries.append({
                "code": code,
                "description_en": desc_en,
                "description_gr": desc_gr,
                "keywords_gr": kw_gr.lower().split(),
                "keywords_en": kw_en.lower().split(),
                "all_text": f"{desc_en} {desc_gr} {kw_gr} {kw_en}".lower(),
            })

    def search(self, query: str, limit: int = 5, min_score: int = 10) -> list[dict]:
        """
        Search for CPV codes matching a query string.

        Args:
            query: Natural language search term (Greek or English)
            limit: Max results to return
            min_score: Minimum relevance score to include

        Returns:
            List of matching CPV entries with relevance scores
        """
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        results = []

        # Stopwords: common words that cause false CPV matches
        stopwords = {
            "show", "top", "by", "total", "amount", "the", "a", "an", "in",
            "on", "of", "to", "for", "and", "or", "is", "are", "was", "how",
            "many", "much", "what", "which", "who", "from", "with", "all",
            "list", "give", "me", "find", "get", "display", "results",
            "contractors", "organizations", "decisions", "spending", "database",
            "ποιοι", "πόσο", "πόσες", "ποια", "τι", "από", "στο", "στη",
            "στον", "στην", "και", "για", "με", "τον", "την", "της", "του",
            "είναι", "δαπάνη", "δαπάνες", "αποφάσεις", "οργανισμοί",
            "ανάδοχοι", "εργολάβοι", "σύνολο", "συνολική", "βάση",
        }
        query_words = [w for w in query_words if w not in stopwords and len(w) >= 3]

        for entry in self._entries:
            score = 0

            # Exact code match
            if query_lower.replace("-", "").startswith(entry["code"][:4]):
                score += 100

            # Word-level matching
            for word in query_words:
                if word in entry["all_text"]:
                    score += 10
                # Partial match (prefix) — require at least 4 chars
                if len(word) >= 4:
                    for kw in entry["keywords_gr"] + entry["keywords_en"]:
                        if kw.startswith(word) or word.startswith(kw):
                            score += 5

            if score >= min_score:
                results.append({
                    "code": entry["code"],
                    "description_en": entry["description_en"],
                    "description_gr": entry["description_gr"],
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_code(self, code: str) -> Optional[dict]:
        """Get details for a specific CPV code."""
        code_clean = code.replace("-", "").strip()
        for entry in self._entries:
            if entry["code"] == code_clean or code_clean.startswith(entry["code"]):
                return {
                    "code": entry["code"],
                    "description_en": entry["description_en"],
                    "description_gr": entry["description_gr"],
                }
        return None

    def get_all_for_prompt(self) -> str:
        """
        Generate a compact CPV reference table for the LLM system prompt.
        """
        lines = ["CPV Code | English | Greek"]
        lines.append("-" * 60)
        for entry in self._entries:
            lines.append(
                f"{entry['code']} | {entry['description_en']} | {entry['description_gr']}"
            )
        return "\n".join(lines)

    def get_categories_summary(self) -> str:
        """Get a shorter summary of main categories for the LLM."""
        categories = {}
        for entry in self._entries:
            prefix = entry["code"][:2]
            if prefix not in categories:
                categories[prefix] = entry["description_en"]
        lines = [f"{k}xxxxxx = {v}" for k, v in sorted(categories.items())]
        return "\n".join(lines)