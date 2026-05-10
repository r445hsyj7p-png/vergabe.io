import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import dateparser

_KW_CACHE: dict = {}


def _keyword_pattern(keyword: str) -> re.Pattern:
    if keyword not in _KW_CACHE:
        _KW_CACHE[keyword] = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
    return _KW_CACHE[keyword]


# IT category mapping: CPV prefix → category
CPV_CATEGORY_MAP = {
    "7220": "Cybersecurity",
    "7221": "Software Dev",
    "7222": "Cybersecurity",
    "7223": "IT Consulting",
    "7224": "IT Consulting",
    "7225": "Software Dev",
    "7226": "Software Dev",
    "7227": "Software Dev",
    "7228": "IT Consulting",
    "7230": "Data / AI",
    "7231": "Data / AI",
    "7232": "IT-Infrastruktur",
    "7233": "IT-Infrastruktur",
    "7242": "Cloud Services",
    "7243": "Cloud Services",
    "7244": "Cloud Services",
    "7245": "IT-Infrastruktur",
    "7246": "IT-Infrastruktur",
    "7247": "IT-Infrastruktur",
    "3242": "IT-Infrastruktur",
    "4882": "IT-Infrastruktur",
}

KEYWORD_CATEGORY_MAP = {
    "Cybersecurity": ["siem", "soc", "mdr", "xdr", "edr", "cybersecurity", "sicherheit", "firewall", "penetration", "ztna", "iam", "identity"],
    "Cloud Services": ["cloud", "iaas", "paas", "saas", "azure", "aws", "kubernetes", "docker", "migration"],
    "Data / AI": ["data", "daten", "ki", "ai", "machine learning", "analytics", "bi", "business intelligence", "datenbank"],
    "Software Dev": ["entwicklung", "softwareentwicklung", "portal", "plattform", "anwendung", "app", "api", "agile", "devops"],
    "IT Consulting": ["beratung", "consulting", "strategie", "digitalisierung", "transformation", "konzept"],
    "IT-Infrastruktur": ["infrastruktur", "netzwerk", "server", "hardware", "datacenter", "rechenzentrum", "backup"],
}


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        parsed = dateparser.parse(
            date_str,
            languages=["de", "en", "fr"],
            settings={"RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DAY_OF_MONTH": "first"},
        )
        return parsed
    except Exception:
        return None


def parse_value_cents(value_str: Optional[str]) -> Optional[int]:
    if not value_str:
        return None
    # Remove currency symbols and words
    clean = re.sub(r"[€$£CHF EUR\s]", "", str(value_str))
    # Handle Mio / Mrd
    mio_match = re.search(r"(\d+[.,]?\d*)\s*(Mio|mio|M\b)", str(value_str))
    if mio_match:
        val = float(mio_match.group(1).replace(",", "."))
        return int(val * 1_000_000 * 100)
    mrd_match = re.search(r"(\d+[.,]?\d*)\s*(Mrd|mrd|B\b)", str(value_str))
    if mrd_match:
        val = float(mrd_match.group(1).replace(",", "."))
        return int(val * 1_000_000_000 * 100)
    # Standard number
    clean = re.sub(r"[^\d.,]", "", clean)
    clean = clean.replace(".", "").replace(",", ".")
    try:
        return int(float(clean) * 100)
    except (ValueError, OverflowError):
        return None


def detect_it_category(title: str, description: str, cpv_codes: List[str]) -> Optional[str]:
    # CPV-based detection first
    for cpv in (cpv_codes or []):
        prefix = cpv[:4]
        if prefix in CPV_CATEGORY_MAP:
            return CPV_CATEGORY_MAP[prefix]

    # Keyword-based (word-boundary match, case-insensitive)
    combined = f"{title} {description or ''}"
    for category, keywords in KEYWORD_CATEGORY_MAP.items():
        for kw in keywords:
            if _keyword_pattern(kw).search(combined):
                return category

    return None


def extract_cpv_from_text(text: str) -> List[str]:
    """Extract CPV codes from free text."""
    pattern = r'\b\d{8}(?:-\d)?\b'
    return list(set(re.findall(pattern, text or "")))


class NormalizedTender:
    def __init__(self):
        self.title: str = ""
        self.description: Optional[str] = None
        self.contracting_authority: Optional[str] = None
        self.authority_address: Optional[str] = None
        self.authority_email: Optional[str] = None
        self.authority_phone: Optional[str] = None
        self.deadline: Optional[datetime] = None
        self.publication_date: Optional[datetime] = None
        self.value_min: Optional[int] = None
        self.value_max: Optional[int] = None
        self.currency: str = "EUR"
        self.cpv_codes: List[str] = []
        self.it_category: Optional[str] = None
        self.region: Optional[str] = None
        self.country: str = "DE"
        self.procedure_type: Optional[str] = None
        self.fulfillment_location: Optional[str] = None
        self.external_id: Optional[str] = None
        self.source_url: Optional[str] = None
        self.content_hash: Optional[str] = None
        self.raw_data: Optional[Dict] = None
        self.lots: List[Dict] = []
        self.platform_name: Optional[str] = None

    def finalize(self):
        """Post-process: detect category, hash, etc."""
        self.it_category = detect_it_category(
            self.title, self.description or "", self.cpv_codes
        )
        content = f"{self.title}|{self.contracting_authority}|{self.source_url}"
        self.content_hash = compute_hash(content)

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
