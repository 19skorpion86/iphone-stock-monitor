
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PRODUCTS = {
    "MK2F4QL/A": "iPhone Duo 512 GB Bianco Stellare",
    "MK2G4QL/A": "iPhone Duo 512 GB Cielo Notturno",
}
STATE_FILE = Path("stock_state.json")

TARGETS = {
    "carosello": "Apple Store Carosello - Carugate",
    "liberty": "Apple Piazza Liberty - Milano",
    "fiordaliso": "Apple Fiordaliso - Rozzano",
}


def get_stock(sku):
    params = urllib.parse.urlencode({
        "pl": "true",
        "mts.0": "regular",
        "location": "20061",
        "parts.0": sku,
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

            stock = store.get("partsAvailability", {}).get(sku)
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
        raise ValueError("Non sono stati trovati tutti gli Apple Store monitorati")

    return result


def notify(message, parse_mode=None):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    if not token or not chat_id:
        raise ValueError("Credenziali Telegram mancanti")

    payload_data = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true",
    }
    if parse_mode:
        payload_data["parse_mode"] = parse_mode
    payload = urllib.parse.urlencode(payload_data).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        reply = json.load(response)

    if not reply.get("ok"):
        raise RuntimeError("Telegram non ha confermato l'invio")


def stock_key(sku, store):
    return f"{sku}:{store}"


def order_url(sku):
    # Apple requires a session-bound CSRF token for bag/add.
    # Use the official exact-product link instead of an unreliable cart URL.
    return "https://www.apple.com/it/shop/product/" + urllib.parse.quote(sku.lower(), safe="/")


def availability_message(sku, product, store_name):
    return (
        f"{product} - {sku} è DISPONIBILE a {store_name}.\n"
        f"Clicca qui per ordinare: {order_url(sku)}"
    )


def run_monitor():
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    state.pop("_hourly_report", None)
    record = {"at": now_iso, "ok": True, "stock": {}, "errors": []}
    for sku, product in PRODUCTS.items():
        try:
            current = get_stock(sku)
        except Exception as exc:
            record["ok"] = False
            record["errors"].append(f"{sku}: {type(exc).__name__}")
            print(f"ERRORE CONTROLLO {sku}: {type(exc).__name__}", file=sys.stderr)
            continue
        for store, info in current.items():
            key = stock_key(sku, store)
            available = info["pickup"] == "available"
            record["stock"][key] = available
            previous = state.get(key, state.get(store, False) if sku == "MK2G4QL/A" else False)
            if available and not previous:
                try:
                    notify(availability_message(sku, product, TARGETS[store]))
                    print(f"NOTIFICA INVIATA: {sku} {store}")
                except Exception as exc:
                    record["ok"] = False
                    record["errors"].append(f"Telegram {sku} {store}: {type(exc).__name__}")
                    # Retry the notification at the next check.
                    continue
            state[key] = available
            print(f"{sku} | {TARGETS[store]}: {info['pickup']}")
    state["_last_check"] = record
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    if not record["ok"]:
        raise RuntimeError("Una o piu verifiche/notifiche non sono riuscite; dettagli non sensibili nei log")


if __name__ == "__main__":
    try:
        run_monitor()
    except Exception as exc:
        print(f"ERRORE TECNICO: {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)

