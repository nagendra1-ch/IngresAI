import re

DISTRICT_NORMALIZATION_MAP = {
    "anantapur": "Ananthapuramu",
    "ananthapuramu": "Ananthapuramu",
    "ysr": "YSR Kadapa",
    "ysrkadapa": "YSR Kadapa",
    "kadapa": "YSR Kadapa",
    "y.s.r. kadapa": "YSR Kadapa",
    "sripottisriramulunellore": "SPS Nellore",
    "nellore": "SPS Nellore",
    "spsnellore": "SPS Nellore",
    "srisatyasai": "Sri Sathya Sai",
    "srisathyasai": "Sri Sathya Sai",
    "drbrambedkarkonaseema": "Dr. B.R. Ambedkar Konaseema",
    "drbrambedkarkonaseemi": "Dr. B.R. Ambedkar Konaseema",
    "drbrambedkarkonaseem": "Dr. B.R. Ambedkar Konaseema",
    "parvathipurammanyam": "Parvathipuram Manyam",
    "allurisitharamaraju": "Alluri Sitharama Raju",
    "anakapalli": "Anakapalli",
    "kakinada": "Kakinada",
    "visakhapatnam": "Visakhapatnam",
    "vizianagaram": "Vizianagaram",
    "srikakulam": "Srikakulam",
    "guntur": "Guntur",
    "palnadu": "Palnadu",
    "krishna": "Krishna",
    "tirupati": "Tirupati",
    "chittoor": "Chittoor",
    "annamayya": "Annamayya",
    "eastgodavari": "East Godavari",
    "westgodavari": "West Godavari",
    "prakasam": "Prakasam",
    "eluru": "Eluru",
    "ntr": "NTR",
    "bapatla": "Bapatla",
    "nandyal": "Nandyal",
    "kurnool": "Kurnool",
}

def normalize_state(name: str) -> str:
    """
    Standardizes state names to Title Case with consistent spacing.
    """
    if not name:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(name)).strip()
    return cleaned.title()

def normalize_district(name: str) -> str:
    """
    Standardizes district names by stripping spaces, symbols, and checking canonical mappings.
    """
    if not name:
        return ""
    
    # Strip spaces and non-word characters for mapping key
    raw_str = str(name).strip()
    key = raw_str.lower().replace(".", "").replace(" ", "").replace("-", "")
    
    if key in DISTRICT_NORMALIZATION_MAP:
        return DISTRICT_NORMALIZATION_MAP[key]
        
    # Default fallback formatting: Title Case
    cleaned = re.sub(r'\s+', ' ', raw_str).strip()
    return cleaned.title()

def split_concatenated_geography(district_raw: str, block_raw: str = None, mandal_raw: str = None):
    """
    Splits concatenated district + mandal name strings (e.g. 'Dr. B.R. Ambedkar KonaseemaAmalapuram')
    to prevent geographical mapping errors.
    """
    district_clean = str(district_raw).strip()
    unit_name = block_raw or mandal_raw
    if unit_name:
        unit_name = str(unit_name).strip()
    else:
        unit_name = "Unknown"
        
    dist_lower = district_clean.lower()
    prefix = "dr. b.r. ambedkar konaseem"
    
    if dist_lower.startswith(prefix):
        district_clean = "Dr. B.R. Ambedkar Konaseema"
        suffix = dist_lower[len(prefix):].strip()
        if suffix.startswith("a") or suffix.startswith("i"):
            if suffix.startswith("amalapuram"):
                unit_name = "Amalapuram"
            elif suffix.startswith("ainavilli"):
                unit_name = "Ainavilli"
            elif suffix.startswith("atreyapuram"):
                unit_name = "Atreyapuram"
            elif suffix.startswith("i. polavaram") or suffix.startswith("i.polavaram"):
                unit_name = "I. Polavaram"
            elif suffix.startswith("malikipuram"):
                unit_name = "Malikipuram"
            elif suffix.startswith("mamidikuduru"):
                unit_name = "Mamidikuduru"
            elif suffix.startswith("mummidivaram"):
                unit_name = "Mummidivaram"
            elif suffix.startswith("ravulapalem"):
                unit_name = "Ravulapalem"
            elif suffix.startswith("sakhinetipalle"):
                unit_name = "Sakhinetipalle"
            elif suffix.startswith("p.gannavaram") or suffix.startswith("p. gannavaram"):
                unit_name = "P. Gannavaram"
            elif suffix.startswith("uppalaguptam"):
                unit_name = "Uppalaguptam"
            else:
                if suffix.startswith("a"):
                    suffix = suffix[1:].strip()
                unit_name = suffix.title()
        else:
            if suffix:
                unit_name = suffix.title()
                
    return district_clean, unit_name
