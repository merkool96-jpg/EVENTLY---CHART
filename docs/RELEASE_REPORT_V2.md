# Consegna EVENTLY V2.0 — 7 novembre 2026

## Versione e ambito

Branch `feat/evently-v2`, base V1.2 `4cb44ae`. Documenti di progetto salvati nel commit `16f79ed` prima delle modifiche funzionali. Milestone A–F distinte; stack locale conservato. Nessuna prova ha usato il database del Mac né il database operativo del workspace: test, browser, benchmark e aggiornamento hanno percorsi temporanei dedicati.

## Problemi risolti

- File con errori isolati o identificativi parziali: righe valide importate e fonti errate conservate, senza persone inventate.
- Nomi composti importati in colonne distinte rispettati; suggerimento manuale conservato; alias sempre ricercabili.
- Fusione bloccata: stessa validazione nella preview e nel commit, membri responsabili indicati, pulsante disabilitato; rinvio/revoca separazione espliciti.
- Registrazioni/presenze e stati contrari: cinque stati, evidenze originali e override amministrativi; niente presenze inventate e niente assenza dedotta da righe mancanti.
- Gestione massiva con selezione di tutto il filtro, preview, conferma e annullamento controllato.
- Archivio separato dall'esclusione analytics; nuovo/ricorrente non azzera lo storico con il filtro periodo.
- Ricerca prima della Top50, selezione globale per colonna, pagine da50, Top3 con metrica esplicita, viste persistenti ed export con selettore comune.
- Coda identità aggiornata dopo unione; dashboard non attende il matching; Mantieni separati non ricalcola tutti gli aggregati.
- Backup/download e ripristino verificato su copia; updater con backup codice/DB e riferimento alla coppia precedente.

## Verifiche eseguite

- **88 test pytest superati**: integrità, identità/gruppi, importazioni XLSX/XLS/CSV, alias/anagrafica, status/undo, filtri, valori dinamici, archivio, analytics, backup/restore e updater. Un avviso di deprecazione Starlette/AnyIO non influisce sull'esito.
- Build TypeScript + Vite superata; `npm audit --audit-level=high`: zero vulnerabilità segnalate al momento del controllo.
- Chromium: `v2.cjs` su API e SQLite reali sintetici (import7 passi, header2, contatori, bulk/undo, merge, export, navigazione9 aree, analytics e viewport390); `profiles-export.cjs` su seconda istanza vuota (scelta nome, correzione, alias, downloadXLSX/CSV).
- Chromium con API simulate: `sorting.cjs` (66 candidati, cinque colonne, ricerca posto51, Top50/3, tastiera/mobile), `performance.cjs` (nessun matching iniziale, nessun refresh aggregati per separazione, refresh dopo merge). Sono controlli UI, non benchmark dell'API simulata.
- Export XLSX reale con **10.001 persone**, tre fogli e tutte le righe; export CSV oltre10k; formule neutralizzate e download senza cambiamenti ai dati.
- Pacchetto completo provato da `scripts.verify_v2_update`: installazione temporanea dal commit V1.2, dati sintetici con fonti/importazioni/decisioni, updater, avvio schema4, confronto di tutte le colonne e righe delle12 tabelle legacy, `integrity_check` e `foreign_key_check`, backup database e codice. Non è una prova fisica di Finder/macOS.
- Git/manifest controllati: nessun DB, backup o file personale. L'unico CSV tracciato è dimostrativo con indirizzi `example.test`.

## Benchmark riproducibile

Secondi di tempo trascorso, singola esecuzione per scenario, interprete caldo, Linux6.18 x86_64, Python3.12.14, AMD EPYC9V74, 5 CPU logiche disponibili. Archivi sintetici con2000/10000 profili, una partecipazione ciascuno e due varianti controllate; gli import aggiungono110 profili prima di merge/export. Nessun dato utente. Risultati JSON integrali in `BENCHMARK_V2.json` e `BENCHMARK_V12_COMPARISON.json`; script `scripts/benchmark_v2.py`.

La ricerca V2 usa il nuovo selettore paginato; quella V1.2 il vecchio endpoint. Il matching core non comprende tutta la schermata: per la V2 viene misurata separatamente anche la validazione preventiva con impatto. Tempi senza rete/browser, non p95, non un confronto controllato su Mac. Gli export V2 contengono colonne aggiuntive. Non tutte le operazioni sono più veloci: evidenze, filtri e controlli hanno un costo, visibile nella tabella.

|Profili|Operazione|V1.2 secondi|V2 secondi|
|---|---|---:|---:|
|2000|Dashboard|0.053|0.064|
|2000|Ricerca|0.026|0.042|
|2000|Matching core|0.012|0.023|
|2000|Unione|0.023|0.039|
|2000|Mantieni separati|0.004|0.036|
|2000|XLSX completo|0.554|0.668|
|2000|Anteprima 10 righe|0.275|0.053|
|2000|Conferma 10 righe|0.243|0.036|
|2000|Anteprima 100 righe|2.531|0.040|
|2000|Conferma 100 righe|2.417|0.042|
|2000|Schermata identità con preflight|non disponibile|0.104|
|2000|Analytics|non disponibile|0.074|
|10000|Dashboard|0.188|0.307|
|10000|Ricerca|0.171|0.314|
|10000|Matching core|0.082|0.110|
|10000|Unione|0.140|0.177|
|10000|Mantieni separati|0.034|0.025|
|10000|XLSX completo|2.903|3.889|
|10000|Anteprima 10 righe|1.514|0.238|
|10000|Conferma 10 righe|1.476|0.265|
|10000|Anteprima 100 righe|13.601|0.279|
|10000|Conferma 100 righe|13.893|0.250|
|10000|Schermata identità con preflight|non disponibile|0.560|
|10000|Analytics|non disponibile|0.437|

Il miglioramento maggiore misurato è l'importazione di profili nuovi senza possibili evidenze: evita la ricostruzione del grafo per ogni riga senza abbassare i controlli sulle corrispondenze. Tabelle paginano e l'identificazione non blocca più la dashboard.

## Limiti dichiarati

- macOS/Finder/Gatekeeper, Safari e lettore di schermo non disponibili qui. Sono verificati build, Chromium desktop/mobile, tastiera nei percorsi coperti e logica updater su Linux. Il collaudo finale sul Mac resta necessario.
- Import locale: massimo10MB e20.000 righe; restore UI massimo32MB. Nessuna coda background persistente: import ed export hanno indicatore di attesa e restano richieste sincrone; file grandi o molto ambigui possono richiedere più tempo e occupare il processo locale.
- Aggregati ancora costruiti in memoria; matching usa indici per evidenze ma un archivio molto denso di nomi/contatti identici può generare tante coppie. La coda valida soltanto la pagina visibile. Benchmark con pochi candidati, non prova di ogni distribuzione possibile né di archivi molto superiori a10k.
- La spesa riportata è separata dal valore attribuito e dai costi. Gli originali conservano ogni osservazione; il riepilogo monetario usa l'importo noto delle righe persona/evento ereditate, non è un registro di pagamenti, rimborsi o incassi verificati. Reimport di importi diversi non ricostruisce una contabilità. Nessun ROI o fatturato dichiarato.
- Due eventi nella stessa data non permettono di dedurre un ordine intragiornaliero: il primo ID sceglie la prima presenza, il ritorno richiede una data successiva. Analisi basate soltanto sullo storico caricato, con copertura esplicita; non conoscono eventi mai importati.
- Storico decisioni UI ultime100, dati originali completi nel DB; qualità mostra liste a pagine ma alcuni endpoint costruiscono ancora l'intero insieme in memoria. Le viste salvano filtri, non un rapporto statico.
- L'updater gestisce la normale installazione `backend/evently.db`; percorsi DB personalizzati richiedono una procedura dedicata. Il backup sullo stesso disco non protegge dalla perdita fisica: scaricare anche una copia esterna.

## Collaudo sul Mac

Seguire i cinque passaggi nel README con **AGGIORNA_EVENTLY.command dalla nuova cartella**, scegliendo la vecchia cartella; riaprire AVVIA dalla vecchia. Un solo pacchetto. Provare: Overview; nuovo evento; importazione di un piccolo file; contatori; iscritti→presenti dalla scheda evento e undo; Centro Verifica con scelta nome; anagrafica/ricerca alias; ordinamenti Top50; filtri/export; Analytics; backup e download. Non eseguire un ripristino di prova sui dati personali: usare una seconda installazione sintetica.

## Aggiornamento grafico Overview — 7 novembre 2026

Aggiunto secondo grafico indipendente dal valore economico: partecipanti confermati per evento, valori zero espliciti, nome/data con anno, totale delle presenze e tabella espandibile. Usa `dashboard.timeline[].participants` dal read-model consolidato esistente; nessuna modifica a DB/API o ai dati caricati. Grafico e tabella mostrano lo stesso insieme di eventi incluso nelle analisi. Build passata; suite Chromium `test:charts` su dati sintetici3/10/0, gratuito vs economico, totale13, vuoto, tabella e viewport390 senza overflow. Nessun dato personale usato nelle prove.
