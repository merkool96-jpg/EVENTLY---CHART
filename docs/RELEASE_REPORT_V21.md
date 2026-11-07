# EVENTLY V2.1 — audit correttivo e consegna

7 novembre 2026. Base V2.0.1 `f08e73e`, verificata con origin/feat/evently-v2. Branch dedicato `feat/evently-v2.1`. Checklist e risultati attesi salvati **prima del codice**, commit `4b17427`, in [AUDIT_V21.md](AUDIT_V21.md). Stack e direzione visiva conservati. Tutte le prove su database sintetici temporanei: nessun database del Mac o allegato personale è stato aperto, modificato o pubblicato.

## Problemi realmente confermati e corretti

- **Qualità Dati**: il frontend cambiava page ma richiedeva e renderizzava sempre l'intera categoria. Ora invia categoria/ricerca/pagina/dimensione; API risponde con total/page/page_size/pages e sole righe della pagina. Provati200 e10000 casi con pagine distinte, ultima pagina, ricerca e limite massimo200; default50. Non si scarica più l'intera lista per visualizzare una pagina.
- **Centro Verifica**: i blocchi di gruppo erano corretti, ma senza percorso diretto di correzione. Ora la coda separa Da decidere, Conflitti da risolvere e Rinviati. Risolvi conflitto spiega la regola e i membri responsabili, distingue incompatibilità/contatti potenzialmente condivisi/separazioni precedenti, mostra originali, fonti e collegamenti attivi. L'annullamento di un collegamento ha anteprima presenze/valore/persone, conferma, audit e guardia contro dati cambiati; poi ricalcola la verifica e l'impatto dell'eventuale unione. I blocchi di separazione si revocano esplicitamente, senza unire nulla. Nessuna fusione forzata.
- **Analytics su tutto lo storico**: non presenta più tutti come nuovi. Nuovi/già conosciuti richiedono un periodo o insieme selezionato; la ricorrenza storica (almeno2 presenze complessive) è distinta e dichiarata indipendente dal periodo. I segmenti frequenza/inattività e i relativi elenchi/export usano il medesimo selettore.
- **Eventi**: eliminata duplicazione del nome; archivio presentato con etichetta/azione esplicita e icona appropriata, reversibile. Archiviare continua a mantenere presenze e valore nello storico.
- **Contrasto**: misura del testo renderizzato ha confermato colori troppo chiari in breadcrumb, tabelle, etichette, footer e podio. Corretti mantenendo la palette. Nessuna animazione aggiunta.

## Miglioramenti UX

- Overview: quattro KPI con definizioni, eventi esplicitamente inclusi nelle analisi, persone unificate distinte dalle righe originali. Un solo grafico Valore attribuito/Presenze; scala, nomi e date italiane con anno, tutti gli eventi scorribili, zero distinto da valore sconosciuto, spesa riportata separata. Apertura evento da barra o tabella. Miglior partecipante con presenze/ultima data e apertura profilo.
- Analytics: sezioni visuali Fidelizzazione, Nuovi/ricorrenti, Inattività, Eventi che fidelizzano, Gratuiti/valore positivo e Affinità. Card2/3/5/10 e30/90/180/365 cliccabili. Denominatori/finestra espliciti, coorti recenti segnalate. Periodi rapidi, categoria da quelle esistenti e reset. Barre di ritorno costruite su conteggi reali; nessun fatturato inferito.
- Eventi: card compatte e contrastate, ricerca, ordinamento data/presenze/valore/nome e vista tabellare alternativa. Costi, valore attribuito e spesa riportata restano distinti.
- Partecipanti/Top50: date italiane, Riga distinta da Pos., Reset ordinamento nel database, disponibili/idonei/mostrati e filtri attivi espliciti. Ranking predefinito resta presenze/data/nome; ricerca prima del limite50 conservata.
- Sidebar raggruppata Operatività/Persone/Analisi/Impostazioni, nessuna dicitura di piano commerciale. Focus da tastiera rinforzato.

## Funzionalità aggiunte

Risolutore guidato dei conflitti e simulazione di correzione; segmenti Analytics con apertura del filtro; tabella eventi; metadati backup reali (data/ora locale, dimensione, verifica integrità/hash se manifest disponibile, schema, conteggi originali disponibili), confronto attuale/copia prima del ripristino. Versione e note di rilascio separate dai backup. Ripristino ancora solo dopo conferma e backup dell'attuale.

## Verifiche realmente eseguite

- **97 test backend superati**, inclusi test di identità, fonti, import/XLSX/XLS/CSV, valori dinamici, archivio, export, bulk/undo e updater preesistenti. Un avviso di deprecazione Starlette/AnyIO, nessun fallimento.
- Build TypeScript/Vite superata. Nessuna dipendenza aggiunta.
- Browser Chromium: sette suite (`v2`, `profiles-export`, `v21`, `attendance-chart`, `sorting`, `performance`, `contrast`). Le prime tre usano API/SQLite reali sintetici; le suite di grafico/ordinamento/caricamenti impiegano anche API simulate, senza dichiararle misure backend.
- Suite V2.1:205 casi navigati avanti/indietro e filtrati; conflitto specifico e annullamento collegamento; segmenti coerenti; eventi ricerca/tabella/archivio; apertura evento dal grafico e profilo dal podio; backup e confronto prima del ripristino; sette aree a viewport390 senza overflow dell'intera pagina. Nessuna eccezione JavaScript nei percorsi coperti.
- Riconciliazione economica verificata tra dashboard, eventi, profilo, ranking, analytics e XLSX. Ricerca globale, export completo oltre10k, fonti e decisioni conservati dai test di regressione. Grafico con18 eventi scorribili, valori0/null e tabella allineata.
- Contrasto:1178 elementi testuali campionati nelle sette pagine desktop, nessuna violazione nelle coppie misurate:4,5:1 testo normale /3:1 grande secondo luminanza sRGB. Output [CONTRAST_V21.json](CONTRAST_V21.json). Non è certificazione WCAG completa: loghi/elementi disabilitati esclusi, non verifica screen reader o ogni stato possibile.
- Qualità API:200 casi, pagine1/2 circa0,018/0,011 secondi;10000 casi, pagine1/2 circa0,279/0,212 secondi; sempre50 righe e circa24KB per risposta nel dataset misurato. Linux6.18/Python3.12.14, singola esecuzione TestClient, senza latenza browser/rete, non p95. Dati completi in [QUALITY_V21_MEASUREMENTS.json](QUALITY_V21_MEASUREMENTS.json).
- Pacchetto/updater provati su installazioni temporanee da V2.0.1 (schema4→4, tutte le righe/colonne delle21 tabelle conservate) e V1.2 (schema3→4,12 tabelle legacy conservate). Backup database/codice, avvio e integrity/FK superati. Nessuna migrazione nuova per chi usa già la V2.0.1.

## Matrice di accettazione V2.1

| Scenario | Evidenza |
|---|---|
|1 Blocco spiegato e percorso corretto|test_blocked_group_diagnostics_and_audited_link_correction + browserV21|
|2 Correzione senza perdita fonti/altre presenze|Confronto righe attendance prima/dopo, profilo estraneo invariato, decisione undo tracciata; stale preview rifiutata|
|3 Paginazione reale|Test parametrico200/10000 + browser205 avanti/indietro/ricerca|
|4 Card→segmento esatto|Test analytics/people/export e browser click card periodo/intera storia|
|5 Nuovi e ricorrenti|Intera storia non applicabile per nuovi nel periodo, ricorrenza storica distinta;2025/2026 coerenti|
|6 Valori fra viste|Test_totali dashboard/eventi/profilo/ranking/analytics/XLSX, regressione20→40|
|7 Archivio mantiene storico|Regressione API e browser con valore invariato dopo archivio|
|8 Grafico tutti eventi/zero/null|Suite grafico18 eventi, tabella e mobile; apertura dettaglio con API reale|
|9 Filtri/export|Regressioni complete, CSV/XLSX, alias, ricerca posto51 e Top50 ricalcolata|
|10 Nessuna perdita/duplicazione|Confronti originali, idempotenza, upgrade completo su copie sintetiche e verifiche FK|

## Limiti residui dichiarati

- Paginazione vera sulla risposta API e sul rendering; read-model e alcuni conteggi sono ancora costruiti in memoria, non tutte query SQL aggregate. Gli archivi molto densi di ambiguità possono richiedere attesa nella classificazione delle code: non viene ridotta la sicurezza per accelerarli.
- Backup list: verifica delle copie locali può richiedere tempo con molte copie grandi. Import/export restano richieste sincrone con indicatore d'attesa; limiti10MB/20000 righe import e32MB restore UI conservati.
- Le metriche conoscono solo presenze importate e incluse; categorie/finestre dichiarate. Affinità categorie esplicitamente sullo storico completo. Date senza orario non consentono ordine intragiornaliero.
- Spesa riportata non è contabilità completa né incasso verificato. Dati monetari originali conservati; nessun ROI/fatturato simulato.
- macOS/Finder/Gatekeeper, Safari, screen reader e ogni possibile stato di dialog non collaudabili qui. Build/Chromium/SQL e logica updater verificati su Linux. L'alias e TROVA_EVENTLY restano i percorsi per identificare l'installazione standard sul Mac.
- Nessun automatismo ripristina o unisce dati: scelta amministrativa esplicita sempre richiesta nelle operazioni importanti. Annullare un collegamento può creare una separazione intenzionale; revocarla è un'azione distinta e tracciata.

## Unico aggiornamento finale

Pacchetto `v2.1.0.zip`, branch `feat/evently-v2.1`. Dal pacchetto nuovo: TROVA_EVENTLY mentre la copia abituale è aperta → lascia Finder aperto → ferma server con Ctrl+C → AGGIORNA_EVENTLY.command → seleziona la cartella appena individuata → riapri AVVIA dalla cartella abituale/alias → Cmd+Maiusc+R. Impostazioni deve mostrare EVENTLYV2.1. Non reimportare file e non ripristinare nuovamente il database. Nessuna installazione intermedia.
