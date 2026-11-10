"""Ländernamen (deutsch) zu ISO-3166-1-Codes, für Rapporte sortiert nach Alphabet."""
NAMEN = {
    "AD": "Andorra", "AE": "Vereinigte Arabische Emirate", "AL": "Albanien", "AM": "Armenien", "AR": "Argentinien",
    "AT": "Österreich", "AU": "Australien", "AZ": "Aserbaidschan", "BA": "Bosnien und Herzegowina", "BE": "Belgien",
    "BG": "Bulgarien", "BR": "Brasilien", "BY": "Belarus", "CA": "Kanada", "CH": "Schweiz", "CL": "Chile", "CN": "China",
    "CO": "Kolumbien", "CY": "Zypern", "CZ": "Tschechien", "DE": "Deutschland", "DK": "Dänemark", "DZ": "Algerien",
    "EE": "Estland", "EG": "Ägypten", "ES": "Spanien", "FI": "Finnland", "FR": "Frankreich", "GB": "Vereinigtes Königreich",
    "GE": "Georgien", "GR": "Griechenland", "HK": "Hongkong", "HR": "Kroatien", "HU": "Ungarn", "ID": "Indonesien",
    "IE": "Irland", "IL": "Israel", "IN": "Indien", "IR": "Iran", "IS": "Island", "IT": "Italien", "JP": "Japan",
    "KR": "Südkorea", "KZ": "Kasachstan", "LI": "Liechtenstein", "LT": "Litauen", "LU": "Luxemburg", "LV": "Lettland",
    "MA": "Marokko", "MC": "Monaco", "MD": "Moldau", "ME": "Montenegro", "MK": "Nordmazedonien", "MT": "Malta",
    "MX": "Mexiko", "MY": "Malaysia", "NL": "Niederlande", "NO": "Norwegen", "NZ": "Neuseeland", "PE": "Peru",
    "PH": "Philippinen", "PK": "Pakistan", "PL": "Polen", "PT": "Portugal", "QA": "Katar", "RO": "Rumänien",
    "RS": "Serbien", "RU": "Russland", "SA": "Saudi-Arabien", "SE": "Schweden", "SG": "Singapur", "SI": "Slowenien",
    "SK": "Slowakei", "SM": "San Marino", "TH": "Thailand", "TN": "Tunesien", "TR": "Türkei", "TW": "Taiwan",
    "UA": "Ukraine", "US": "Vereinigte Staaten", "UY": "Uruguay", "VA": "Vatikanstadt", "VN": "Vietnam",
    "XK": "Kosovo", "ZA": "Südafrika",
}


def name(code: str | None) -> str:
    code = (code or "").upper()
    return NAMEN.get(code, code or "Unbekannt")


def sortierschluessel(code: str | None) -> str:
    """Alphabetisch nach deutschem Namen, Umlaute wie Grundbuchstaben (Ö nach O)."""
    n = name(code).lower()
    return n.translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u"}))
