# iPhone Stock Monitor

## Stato: progetto concluso e archiviato

Monitoraggio interrotto l'11 novembre 2026 dopo il raggiungimento dell'obiettivo.
Nessun file o configurazione è stato cancellato.

- Job cron-job.org 8784981: disattivato, configurazione conservata.
- Workflow `.github/workflows/stock-monitor.yml`: disabilitato.
- Nessun controllo ricorrente o avviso Telegram automatico attivo.

## Funzionamento conservato

Controllo disponibilità Apple per MK2F4QL/A (512 GB Bianco Stellare) e
MK2G4QL/A (512 GB Cielo Notturno), presso Carosello, Piazza Liberty e Fiordaliso.
Il pianificatore esterno richiamava workflow_dispatch ogni minuto.
Gli avvisi Telegram venivano inviati al passaggio da non disponibile a disponibile.
I riepiloghi orari sono disattivati. Il monitor non effettua acquisti.

## Riutilizzo

1. Rimuovere l'archiviazione del repository, oppure copiarlo in un nuovo progetto.
2. Aggiornare codici prodotto, nomi e negozi in `monitor.py`.
3. Preparare lo stato iniziale in `stock_state.json` per il nuovo monitoraggio.
4. Verificare i segreti GitHub `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`, senza pubblicarne i valori.
5. Verificare/rinnovare il token GitHub usato da cron-job.org (scadenza originaria: 3 dicembre 2026).
6. Abilitare il workflow e riattivare il job cron-job.org, aggiornandone la destinazione se cambia repository.
7. Verificare una run automatica e i suoi log.

Repository: https://github.com/19skorpion86/iphone-stock-monitor
Job conservato: https://console.cron-job.org/jobs/8784981

