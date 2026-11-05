
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
    "fiordaliso": "Apple Fiordaliso - Rozzano",
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
        raise ValueError("Non sono stati trovati tutti gli Apple Store monitorati")

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


def run_with_hourly_report():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    saved = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    report = saved.get("_hourly_report", {
        "since": now_iso, "checks": [], "last_sent_hour": now.strftime("%Y-%m-%dT%H")
    })
    error = None
    try:
        main()
        state = json.loads(STATE_FILE.read_text())
        record = {"at": now_iso, "ok": True,
                  "stock": {key: state[key] for key in TARGETS}}
    except Exception as exc:
        error = exc
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else saved
        # Do not persist exception text: HTTP errors can include credential-bearing URLs.
        record = {"at": now_iso, "ok": False, "error": type(exc).__name__}

    report["checks"].append(record)
    hour = now.strftime("%Y-%m-%dT%H")
    if hour != report["last_sent_hour"]:
        checks = report["checks"]
        successful = [item for item in checks if item["ok"]]
        failed = len(checks) - len(successful)
        local = ZoneInfo("Europe/Rome")
        start = datetime.fromisoformat(report["since"]).astimezone(local)
        end = now.astimezone(local)
        lines = [
            "RIEPILOGO ORARIO VERIFICHE IPHONE",
            "",
            f"Periodo: {start:%d/%m %H:%M} – {end:%d/%m %H:%M} (Italia)",
            f"Verifiche effettuate: {len(checks)}",
            f"Riuscite: {len(successful)} | Errori: {failed}",
        ]
        for key, name in TARGETS.items():
            store_checks = [item for item in successful if key in item["stock"]]
            available = sum(item["stock"][key] for item in store_checks)
            latest = ("disponibile" if store_checks[-1]["stock"][key] else "non disponibile") if store_checks else "non verificabile"
            lines.append("")
            lines.append(f"{name}: {available} rilevazioni disponibili; ultimo esito {latest}.")
        lines.append("")
        lines.append("Conteggi delle esecuzioni registrate; eventuali mancati avvii non sono verifiche effettuate.")
        try:
            notify("\n".join(lines))
            report = {"since": now_iso, "checks": [], "last_sent_hour": hour}
            print("RIEPILOGO ORARIO INVIATO")
        except Exception as exc:
            # Keep unsent checks for retry at the next execution.
            print(f"Invio riepilogo non riuscito: {type(exc).__name__}", file=sys.stderr)
            if error is None:
                error = RuntimeError("Invio riepilogo Telegram non riuscito")
    state["_hourly_report"] = report
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    if error is not None:
        raise error


if __name__ == "__main__":
    try:
        run_with_hourly_report()
    except Exception as exc:
        print(f"ERRORE TECNICO: {exc}", file=sys.stderr)
        sys.exit(2)
