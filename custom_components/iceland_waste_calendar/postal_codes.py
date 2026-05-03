# Maps Icelandic postal codes to municipality identifiers.
# Municipalities not yet supported are mapped but will be rejected at setup time.
POSTAL_CODE_MAP: dict[str, str] = {
    # Reykjavík
    "101": "reykjavik",
    "102": "reykjavik",
    "103": "reykjavik",
    "104": "reykjavik",
    "105": "reykjavik",
    "106": "reykjavik",
    "107": "reykjavik",
    "108": "reykjavik",
    "109": "reykjavik",
    "110": "reykjavik",
    "111": "reykjavik",
    "112": "reykjavik",
    "113": "reykjavik",
    "116": "reykjavik",  # Kjalarnes
    "162": "reykjavik",  # Grafarholt og Úlfarsárdalur
    # Kópavogur
    "200": "kopavogur",
    "201": "kopavogur",
    "202": "kopavogur",
    "203": "kopavogur",
    # Garðabær (not yet supported)
    "210": "gardabaer",
    "212": "gardabaer",
    "225": "gardabaer",  # Álftanes
    # Hafnarfjörður
    "220": "hafnarfjordur",
    "221": "hafnarfjordur",
    "222": "hafnarfjordur",
    # Mosfellsbær (not yet supported)
    "270": "mosfellsbaer",
    # Árborg (not yet supported)
    "800": "arborg",
    "801": "arborg",
    "802": "arborg",
    "803": "arborg",
    "804": "arborg",
    "805": "arborg",
}
