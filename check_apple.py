
import json
import os
import sys
import urllib.parse
import urllib.request

PART_NUMBER = os.environ.get("APPLE_PART_NUMBER", "").strip()

if not PART_NUMBER:
    sys.exit(
        "CONFIG ERROR: manca il codice prodotto Apple. "
        "Nessun controllo disponibilita eseguito."
    )

params = urllib.parse.urlencode({
    "pl": "true",
    "mts.0": "regular",
    "location": "20061",
    "parts.0": PART_NUMBER,
})

url = (
    "https://www.apple.com/it/shop/retail/pickup-message?"
    + params
)

request = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    },
)

try:
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)

    stores = data["body"]["stores"]

    if not stores:
        raise ValueError("Nessun negozio restituito")

    for store in stores:
        name = store.get("storeName", "")
        print("Negozio:", name)

        if not any(
            term in name.lower()
            for term in ("carosello", "carugate", "liberty")
        ):
            continue

        stock = store.get(
            "partsAvailability", {}
        ).get(PART_NUMBER)

        if not isinstance(stock, dict):
            raise ValueError(
                "Disponibilita SKU non presente nella risposta"
            )

        print("TARGET:", name)
        print("Pickup:", stock.get("pickupDisplay"))

except Exception as error:
    print(
        "ERRORE TECNICO, NON ESAURIMENTO:",
        str(error),
        file=sys.stderr,
    )
    sys.exit(2)
