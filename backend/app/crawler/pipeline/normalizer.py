import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List

_IT_CPV_PREFIXES = ("72", "48", "73", "64", "79", "50332", "32")
_IT_KEYWORDS = [
    "software", "it-", " it ", "edv", "digital", "cloud", "cyber",
    "sicherheit", "infrastruktur", "entwicklung", "netzwerk", "server",
    "hosting", "datacenter", "rechenzentrum", "portal", "plattform",
]

_DT_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S GMT",
)


def parse_dt(s: str | None) -> datetime | None:
    """Parse a datetime string in any common format, always returning UTC."""
    if not s:
        return None
    s = s.strip()
    for fmt in _DT_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_it_relevant(title: str, description: str | None = None, cpv_codes: list | None = None) -> bool:
    """Return True if the tender appears IT-related by CPV or keywords."""
    if cpv_codes and any(c.startswith(p) for c in cpv_codes for p in _IT_CPV_PREFIXES):
        return True
    combined = f"{title} {description or ''}".lower()
    return any(k in combined for k in _IT_KEYWORDS)

# IT category detection: CPV prefix → category
CPV_MAP = {
    "72": "Software Dev",
    "48": "Software Dev",
    "73": "Software Dev",
    "64": "Cybersecurity",
    "79": "IT Consulting",
    "50": "IT-Infrastruktur",
    "51": "IT-Infrastruktur",
    "32": "IT-Infrastruktur",
}

KEYWORD_CATS = {
    "Software Dev": ["software", "entwicklung", "programmierung", "app", "api", "backend", "frontend", "web", "mobile"],
    "Cybersecurity": ["security", "sicherheit", "soc", "siem", "xdr", "mdr", "pentest", "firewall", "endpoint", "nis2"],
    "Cloud Services": ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "saas", "iaas", "paas"],
    "Data / AI": ["data", "daten", "ki", "ai", "machine learning", "analytics", "bi ", "business intelligence", "llm"],
    "IT-Infrastruktur": ["infrastruktur", "netzwerk", "server", "hardware", "rechenzentrum", "hosting", "datacenter"],
    "IT Consulting": ["beratung", "consulting", "projektmanagement", "it-strategie", "digitalisierung"],
}

_KW_CACHE: dict = {}


def _kw_pattern(kw: str) -> re.Pattern:
    if kw not in _KW_CACHE:
        _KW_CACHE[kw] = re.compile(r"\b" + re.escape(kw.strip()) + r"\b", re.IGNORECASE)
    return _KW_CACHE[kw]


def detect_it_category(title: str, description: str | None, cpv_codes: List[str] | None) -> str | None:
    if cpv_codes:
        for code in cpv_codes:
            prefix = code[:2]
            if prefix in CPV_MAP:
                return CPV_MAP[prefix]

    combined = f"{title} {description or ''}"
    for cat, keywords in KEYWORD_CATS.items():
        if any(_kw_pattern(kw).search(combined) for kw in keywords):
            return cat
    return None


def extract_cpv_codes(text: str) -> List[str]:
    return re.findall(r"\b\d{8}(?:-\d)?\b", text)


def parse_value(text: str | None) -> int | None:
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".").strip()
    match = re.search(r"([\d.]+)\s*(Mio|Mrd)?", text, re.IGNORECASE)
    if not match:
        return None
    try:
        val = float(match.group(1))
        if match.group(2):
            mul = 1_000_000 if "mio" in match.group(2).lower() else 1_000_000_000
            val *= mul
        return int(val * 100)  # cents
    except (ValueError, AttributeError):
        return None


def content_hash(*parts: str | None) -> str:
    combined = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class NormalizedTender:
    title: str
    source_slug: str
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None
    contracting_authority: Optional[str] = None
    authority_address: Optional[str] = None
    authority_email: Optional[str] = None
    authority_phone: Optional[str] = None
    deadline: Optional[datetime] = None
    publication_date: Optional[datetime] = None
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    currency: str = "EUR"
    cpv_codes: List[str] = field(default_factory=list)
    it_category: Optional[str] = None
    region: Optional[str] = None
    country: str = "DE"
    procedure_type: Optional[str] = None
    fulfillment_location: Optional[str] = None
    lots: List[dict] = field(default_factory=list)
    platform_name: Optional[str] = None
    raw_data: Optional[dict] = None

    def __post_init__(self):
        if not self.it_category:
            self.it_category = detect_it_category(self.title, self.description, self.cpv_codes)
        self._hash = content_hash(self.title, self.contracting_authority, str(self.deadline))

    @property
    def hash(self) -> str:
        return self._hash
