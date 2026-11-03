
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SKU = "MK2G4QL/A"
STATE_FILE = Path("stock_state.json")

TARGETS = {
    "carosello": "Apple Store Carosello - Carugate",
    "liberty": "Apple Piazza Liberty - Milano",
}


def get_stock():
    params = urllib.parse.urlencode({
        "pl": "true",
        "mts.0": "regular",
        "location": "20061",
        "parts.0": SKU,
    })

    url = "https://www.apple.com/it/shop/retail/pickup-message?" + params
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })

    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)

    stores = data["body"]["stores"]
    result = {}

    for store in stores:
        name = store.get("storeName", "")
        for key in TARGETS:
            if key not in name.lower():
                continue

            stock = store.get("partsAvailability", {}).get(SKU)
            if not isinstance(stock, dict):
                raise ValueError(f"SKU mancante per {name}")

            pickup = stock.get("pickupDisplay")
            if pickup not in ("available", "unavailable"):
                raise ValueError(f"Stato non riconosciuto: {pickup}")

            result[key] = {
                "name": name,
                "pickup": pickup,
                "quote": stock.get("pickupSearchQuote", ""),
            }

    if set(result) != set(TARGETS):
        raise ValueError("Non sono stati trovati entrambi gli Apple Store")

    return result


def notify(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    if not token or not chat_id:
        raise ValueError("Credenziali Telegram mancanti")

    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        reply = json.load(response)

    if not reply.get("ok"):
        raise RuntimeError("Telegram non ha confermato l'invio")


def main():
    current = get_stock()

    previous = {}
    if STATE_FILE.exists():
        previous = json.loads(STATE_FILE.read_text())

    new_state = {}

    for key, info in current.items():
        available = info["pickup"] == "available"
        new_state[key] = available

        if available and not previous.get(key, False):
            message = (
                "IPHONE DISPONIBILE - VERIFICARE SUBITO\n\n"
                "iPhone Duo 512 GB Cielo Notturno\n"
                f"Negozio: {TARGETS[key]}\n"
                f"Stato Apple: {info['pickup']}\n"
                f"Indicazioni ritiro: {info['quote']}\n\n"
                "Prezzo indicativo di catalogo: 2.619 EUR\n"
                "Prezzo finale e ritiro da riconfermare.\n"
                "https://www.apple.com/it/shop/buy-iphone/iphone-duo"
            )
            notify(message)
            print(f"NOTIFICA INVIATA: {key}")
        else:
            print(f"{TARGETS[key]}: {info['pickup']}")

    STATE_FILE.write_text(
        json.dumps(new_state, indent=2) + "\n"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRORE TECNICO: {exc}", file=sys.stderr)
        sys.exit(2)
