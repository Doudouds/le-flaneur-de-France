"""Unmodified scoring functions extracted from Le Flâneur de Paris. See docs/ANALYSE.md."""
from __future__ import annotations
import re, unicodedata, math, datetime as dt

def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def parse_years(text: str) -> list[int]:
    years: list[int] = []
    for match in re.finditer(r"(?<!\d)(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})(?!\d)", text):
        year = int(match.group(1))
        if 1000 <= year <= dt.date.today().year + 1:
            years.append(year)
    return years

def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))

def protection_components(
    resolver: ColumnResolver,
    row: list[str],
    pop_description: str = "",
    pop_interest: str = "",
    wikidata_flags: dict[str, bool] | None = None,
) -> dict[str, int | str | list[str]]:
    """Score the historical/architectural importance from local protection tags."""

    heritage_values = resolver.values(row, "heritage")
    heritage_text = " ".join(heritage_values)
    operator = normalize(resolver.joined(row, "heritage_operator"))
    protection_text = " ".join(resolver.values(row, "protection_title"))
    criteria_text = " ".join(resolver.values(row, "criteria"))
    all_protection = normalize(f"{heritage_text} {protection_text} {operator}")

    # In the French OSM convention, 2 = classé MH and 3 = inscrit MH.
    # Textual formulations are also accepted for POP-derived exports.
    is_classed = bool(re.search(r"\bclass(?:e|ee|es|ees|ement)?\b|\bclassement\b", all_protection))
    is_inscribed = bool(re.search(r"\binscrit(?:e|es)?\b|\binscription\b", all_protection))
    numeric_heritage = set(re.findall(r"(?<!\d)([123456789])(?!\d)", heritage_text))
    if "2" in numeric_heritage and (not operator or "mhs" in operator):
        is_classed = True
    if "3" in numeric_heritage and (not operator or "mhs" in operator):
        is_inscribed = True

    partial_markers = (
        "partiel",
        "partielle",
        "facade",
        "toiture",
        "elevation",
        "escalier",
        "portail",
        "decor interieur",
        "chevet",
        "nef",
        "clocher",
        "vestiges",
        "parcelle",
    )
    explicitly_total = bool(re.search(r"en totalite|totalite|total", all_protection))
    is_partial = not explicitly_total and any(marker in normalize(criteria_text + " " + protection_text) for marker in partial_markers)

    if is_classed and is_inscribed:
        protection_score = 42 if is_partial else 45
    elif is_classed:
        protection_score = 42 if is_partial else 50
    elif is_inscribed:
        protection_score = 25 if is_partial else 32
    else:
        protection_score = 0

    date_text = " ".join(resolver.values(row, "protection_dates"))
    if re.search(r"liste\s+de\s+1840|liste\s+1840", normalize(date_text + " " + protection_text)):
        first_year = 1840
    else:
        years = parse_years(date_text)
        first_year = min(years) if years else None
    if first_year is None:
        antiquity_score = 0
    elif first_year <= 1840:
        antiquity_score = 15
    elif first_year < 1900:
        antiquity_score = 12
    elif first_year <= 1945:
        antiquity_score = 9
    elif first_year <= 1980:
        antiquity_score = 6
    else:
        antiquity_score = 3

    interest_text = normalize(" ".join(resolver.values(row, "criteria")) + " " + pop_description + " " + pop_interest)
    if any(term in interest_text for term in ("interet exceptionnel", "interet national", "importance nationale", "chef d oeuvre")):
        exceptional_score = 10
    elif any(term in interest_text for term in ("a signaler", "monument majeur", "site majeur", "interet majeur")):
        exceptional_score = 7
    elif "interet" in interest_text or "remarquable" in interest_text:
        exceptional_score = 4
    else:
        exceptional_score = 0

    unesco_text = normalize(resolver.joined(row, "unesco"))
    # A dedicated ref:whc, a WHC operator, or an explicit WHC/UNESCO field is
    # required. Coordinates in a broad UNESCO area are never enough.
    ref_whc = bool(resolver.values(row, "ref_whc"))
    operator_whc = any(normalize(value) in {"whc", "unesco", "world heritage"} for value in resolver.values(row, "heritage_operator"))
    whc_reference = ref_whc or operator_whc or bool(
        re.search(r"\b(?:whc|unesco)\b", unesco_text)
        and any(resolver.values(row, field) for field in ("ref_whc", "protection_dates"))
    )
    unesco_score = 15 if whc_reference else 0

    other_text = normalize(resolver.joined(row, "other_protection"))
    if "domaine national" in other_text or "domain national" in other_text:
        other_score = 10
    elif any(term in other_text for term in ("grand site de france", "monument national", "label national")):
        other_score = 7
    elif any(term in other_text for term in ("jardin remarquable", "site classe", "protected")):
        other_score = 4
    else:
        other_score = 0

    architecture_values = resolver.values(row, "architecture")
    architecture_text = normalize(" ".join(architecture_values))
    flags = wikidata_flags or {}
    has_authorship = bool(architecture_values) or flags.get("P84", False) or flags.get("P170", False)
    has_style = bool(architecture_text) or flags.get("P149", False) or flags.get("P186", False)
    authorship_score = (2 if has_authorship else 0) + (1 if has_style else 0)

    description_length = len(pop_description.strip())
    if description_length >= 1200:
        documentation_score = 4
    elif description_length >= 700:
        documentation_score = 3
    elif description_length >= 300:
        documentation_score = 2
    elif description_length >= 100:
        documentation_score = 1
    else:
        documentation_score = 0
    if any(term in interest_text for term in ("rare", "unique", "premier", "seul", "oeuvre majeure", "chef d oeuvre", "remarquable")):
        documentation_score = min(4, documentation_score + 1)

    context_score = min(
        3,
        sum(
            1
            for key in ("P793", "P138", "P527", "P166")
            if flags.get(key, False)
        ),
    )
    documented_interest_score = min(8, authorship_score + documentation_score + context_score)

    return {
        "score_protection": protection_score,
        "score_anciennete": antiquity_score,
        "score_exceptionnel": exceptional_score,
        "score_unesco": unesco_score,
        "score_autres_protections": other_score,
        "score_interet_documente": documented_interest_score,
        "score_auteur_style": authorship_score,
        "premiere_annee_protection": first_year or "",
        "protection_partielle_detectee": "oui" if is_partial else "non",
    }

def physical_score(visitors: int | None) -> int | None:
    """Convert annual attendance to a roughly logarithmic 0-100 score."""

    if visitors is None or visitors <= 0:
        return None
    anchors = [
        (10_000, 20),
        (50_000, 50),
        (100_000, 60),
        (200_000, 70),
        (500_000, 80),
        (1_000_000, 90),
        (2_000_000, 95),
        (5_000_000, 100),
    ]
    if visitors < anchors[0][0]:
        return 20
    if visitors >= anchors[-1][0]:
        return 100
    log_value = math.log10(visitors)
    for (low_value, low_score), (high_value, high_score) in zip(anchors, anchors[1:]):
        if low_value <= visitors <= high_value:
            fraction = (log_value - math.log10(low_value)) / (math.log10(high_value) - math.log10(low_value))
            return round_half_up(low_score + fraction * (high_score - low_score))
    return 20

def pageviews_score(views: int | None) -> int | None:
    if views is None or views <= 0:
        return None
    return min(100, round_half_up(100 * math.log1p(views) / math.log1p(5_000_000)))

def sitelinks_score(sitelinks: int | None) -> int | None:
    if sitelinks is None:
        return None
    return min(100, round_half_up(100 * math.log1p(max(0, sitelinks)) / math.log1p(60)))
