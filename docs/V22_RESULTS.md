# EVENTLY V2.2 — risultati e consegna

Data: 7 novembre 2026. Base v2.1.0/0782247, branch feat/evently-v2.2. Milestone A–F in commit separati; integrazione e QA nella release unificata. Nessuna modifica al database del Mac o agli allegati personali: prove esclusivamente su database sintetici temporanei.

## Cosa è integrato

Segmenti dinamici con soglie configurabili e definizioni salvate; VIP manuali, candidati trasparenti, tag normalizzati, note versionate, campagne/premi con duplicati e deroghe motivate. Selezione oltre pagina, esclusioni, preview, conferma e undo protetti da snapshot. Metadati conservati per origine attraverso merge/split; dati aggiunti al gruppo diventano da riassegnare, senza duplicare note/premi. Cronologia paginata, controllo revisioni e audit locale.

Performance evento, confronto a coppie/categoria/edizioni, Community Insights e ritorno30/60/90/180. Date uguali non sono ordinate per ID. Report PDF/XLSX generati da un'unica transazione di lettura; liste strategiche complete con campi/filtri e protezione formule, note opt-in. Valore attribuito, spesa riportata e costo separati; nessun incasso verificato o ROI inventato. Costo mancante distinto da zero esplicito, anche per fonti legacy.

## Matrice di accettazione

| # | Scenario | Evidenza automatica |
|---|---|---|
|1|Quinta presenza → Super Fedeli|test_1_2_3_17, browser segmenti|
|2|Modifica presenza → ricalcolo|test_1_2_3_17|
|3|VIP manuale resta dopo inattività|test_1_2_3_17|
|4|Tag a100 oltre pagina|test_4_5; browser120/all-filtered ed esclusione119|
|5|Undo sicuro|test_4_5, test_post_merge; browser119 undo|
|6|Merge tag differenti|test_6_7|
|7|Split e riassegnazione note/premi|test_6_7; browser merge→nota→split→riassegna|
|8|Premi duplicati avvisati|test_8_9, test_post_merge; browser preview0|
|9|Tipi/campagne diversi consentiti|test_8_9|
|10|Storico2025 → ricorrente2026|test_10_11_12|
|11|Evento recente senza tasso90 definitivo|test_10_11_12; browser confronto|
|12|Nessuna occasione → insufficiente|test_10_11_12|
|13|Gratuito distinto da non definito|test_13_14_15_16_18, suite export/analytics; UI grafici|
|14|PDF coerente con evento|test_13_14_15_16_18; download reale PDF/XLSX, testo e cover ispezionati|
|15|Export intero insieme|test_13_14_15_16_18, test_20; browser120 e10.000|
|16|Note private escluse|test_13_14_15_16_18; XLSX/PDF reali ispezionati|
|17|Import aggiorna segmenti e conserva CRM|test_1_2_3_17 e regressioni import/profili|
|18|Report senza servizi esterni|generazione ReportLab/openpyxl locale nei test e browser|
|19|Migrazione V2.1 preserva dati|test_crm_migration; verify_v2_update --base v2.1.0|
|20|Regressioni import/identità/ranking/backup|suite backend completa; browser v2, profiles, v21, charts, sorting, performance|

File: backend/tests/test_v22.py, test_crm_migration.py, frontend/e2e/v22.cjs e v22-large.cjs. Test aggiuntivi: FK e origini, modifica metadati parziale, backup fallito, ripristino CRM, storico note oltre50 righe, duplicati dopo merge, formula injection e preview presenze invalidata da modifiche CRM.

## Prove e prestazioni

Build TypeScript/Vite riuscita. Backend: **111 test passati** (un avviso di deprecazione interno Starlette/AnyIO, nessun errore). Suite backend e browser eseguiti contro server HTTP locali e Chromium reale. E2E V2.2 copre desktop e viewport390×844; nessun errore JavaScript o overflow orizzontale nelle sei aree provate. I flussi preesistenti includono importazione a7 passi, revisione identità, anagrafica/alias, CSV/XLSX, backup, grafici e ordinamento su intero insieme.

Prova10.000 profili: tabella50 righe, ricerca Persona9999, anteprimaVIP10.000, export10.000 con5.000 email presenti e5.000 mancanti. Tempi dell'ultima esecuzione locale (include browser/rete, singola misura, NON p95): Overview984ms, partecipanti1009ms, ricerca874ms, previewVIP900ms, XLSX2027ms, segmenti852ms. Database e browser sintetici su macchina condivisa; nessuna promessa di tempi identici sul Mac.

Contrasto automatico WCAG AA del testo visibile:700 coppie controllate nelle pagine V2.2 e1.293 nel dataset di regressione, nessun errore nei campioni. Non equivale a una certificazione completa di accessibilità.

I file realmente scaricati sono stati aperti:120 e10.000 righe esportate, nessuna formula attiva o nota privata; report con8 fogli e PDF con font incorporati, presenze coerenti. I PDF sono vettoriali e impaginati, senza screenshot del sito.

## Sicurezza aggiornamento

Updater senza rete per la copia del pacchetto, manifesto SHA256, backup codice/database e migrazione4→5 con integrity_check/FK; dipendenze gratuite possono richiedere internet all'installazione. Il collaudo updater usa un'installazione temporanea V2.1 con persone, eventi, importazioni e decisioni; confronta tutte le colonne/righe precedenti e verifica backup/integrità. La prova V2.1→V2.2 ha conservato tutte le21 tabelle preesistenti e verificato entrambi i backup. Anche le prove da V1.2/schema3 e V2.0.1/schema4 sono riuscite. Lo schema5 aggiunge soltanto entità CRM e disponibilità costo. Nessuna pulizia o reimportazione richiesta.

## Limiti espliciti

- Non osserviamo eventi esterni o dati mancanti. Ritorni definitivi solo su finestra matura con occasioni note; variazioni di segmenti ricostruite dalla storia attualmente conosciuta, non snapshot passati della conoscenza.
- VIP e premi sono decisioni manuali; suggerimenti e correlazioni non provano causalità. Segmenti si sovrappongono. L'archivio mantiene lo storico; esclusione statistiche è diversa.
- Autore locale dichiarato, non autenticazione multiutente. Nessuna comunicazione automatica, invito, RSVP o check-in introdotti.
- I PDF mostrano le prime12 classi di frequenza; dati completi in XLSX e scheda. Nuovi/ricorrenti hanno granularità giornaliera. Costi legacyzero senza conferma risultano non definiti.
- Finder, Gatekeeper e il comportamento del Mac fisico non sono riproducibili su Linux: launcher/rilevatore sono verificati automaticamente e la procedura updater è provata su copie temporanee. GitHub Actions è configurato, non confuso con esecuzioni locali.
- Un ritorno al codice V2.1 richiede anche il backup DB schema4 abbinato. Non aprire schema5 con codice precedente. Fusioni distruttive V1 non sono ricostruibili senza fonti/backup.

## Una sola cartella sul Mac

1. Mentre la vecchia copia mostra i dati, apri TROVA_EVENTLY.command dal pacchettoV2.2; il Finder evidenzia la cartella in uso. Crea un alias di AVVIA_EVENTLY.command sulla Scrivania e usa sempre quello.
2. Ferma EVENTLY con Ctrl+C nel suo Terminale.
3. Dal pacchetto nuovo apri AGGIORNA_EVENTLY.command e seleziona la vecchia cartella appena individuata. Attendi il completamento; nessuna sostituzione manuale del DB.
4. Riapri dall'alias della vecchia cartella. Nel browser Cmd+Maiusc+R, Impostazioni → EVENTLY V2.2.
5. Prova Segmenti Community, VIP & Rewards e Eventi → Performance e report. Il grafico Overview conserva Valore attribuito / Presenze.

Non avviare il pacchetto scaricato come una nuova installazione: usalo per aggiornare la cartella con i dati. Se il rilevatore non trova una copia, non ne sceglie una a caso; riapri la cartella che già mostrava i dati prima di aggiornare.
