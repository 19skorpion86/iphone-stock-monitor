
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


def run_with_hourly_report():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    report = state.get("_hourly_report", {
        "since": now_iso, "checks": [], "last_sent_hour": now.strftime("%Y-%m-%dT%H")
    })
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
                message = (
                    "IPHONE DISPONIBILE - VERIFICARE SUBITO\n\n"
                    f"{product}\nCodice: {sku}\n"
                    f"Negozio: {TARGETS[store]}\n"
                    f"Stato Apple: {info['pickup']}\n"
                    f"Indicazioni ritiro: {info['quote']}\n\n"
                    "Prezzo finale e ritiro da riconfermare.\n"
                    "https://www.apple.com/it/shop/buy-iphone/iphone-duo"
                )
                try:
                    notify(message)
                    print(f"NOTIFICA INVIATA: {sku} {store}")
                except Exception as exc:
                    record["ok"] = False
                    record["errors"].append(f"Telegram {sku} {store}: {type(exc).__name__}")
                    # Keep previous state to retry the alert at the next check.
                    continue
            state[key] = available
            print(f"{sku} | {TARGETS[store]}: {info['pickup']}")
    report["checks"].append(record)
    hour = now.strftime("%Y-%m-%dT%H")
    if hour != report["last_sent_hour"]:
        checks = report["checks"]
        successful = sum(item["ok"] for item in checks)
        local = ZoneInfo("Europe/Rome")
        start = datetime.fromisoformat(report["since"]).astimezone(local)
        end = now.astimezone(local)
        from html import escape
        lines = [
            f"Periodo: {start:%d/%m %H:%M} - {end:%H:%M}" if start.date() == end.date() else f"Periodo: {start:%d/%m %H:%M} - {end:%d/%m %H:%M}",
            f"Verifiche effettuate: {len(checks)} - Riuscite: {successful} | Errori: {len(checks) - successful}",
        ]
        for store, name in TARGETS.items():
            lines.extend(["", f"<b>{escape(name)}</b>"])
            for sku, product in PRODUCTS.items():
                key = stock_key(sku, store)
                values = []
                for item in checks:
                    stock = item.get("stock", {})
                    if key in stock:
                        values.append(stock[key])
                    elif sku == "MK2G4QL/A" and store in stock:
                        values.append(stock[store])
                latest = ("disponibile" if values[-1] else "non disponibile") if values else "non verificabile"
                colour = product.removeprefix("iPhone Duo 512 GB ")
                lines.append(f"{escape(colour)} - {escape(sku)}: {sum(values)} rilevazioni disponibili; ultimo esito {latest}.")
        try:
            notify("\n".join(lines), parse_mode="HTML")
            report = {"since": now_iso, "checks": [], "last_sent_hour": hour}
            print("RIEPILOGO ORARIO INVIATO")
        except Exception as exc:
            record["ok"] = False
            record["errors"].append(f"Riepilogo Telegram: {type(exc).__name__}")
            print(f"Invio riepilogo non riuscito: {type(exc).__name__}", file=sys.stderr)
    state["_hourly_report"] = report
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    if not record["ok"]:
        raise RuntimeError("Una o piu verifiche/notifiche non sono riuscite; dettagli non sensibili nei log")


if __name__ == "__main__":
    try:
        run_with_hourly_report()
    except Exception as exc:
        print(f"ERRORE TECNICO: {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)

