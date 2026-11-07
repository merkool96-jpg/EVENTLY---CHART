# EVENTLY V2.2

EVENTLY organizza eventi, partecipanti, presenze e relazioni della community sul tuo computer. React/Vite/TypeScript/Tailwind, FastAPI, SQLite e importazione XLSX/XLS/CSV locali. Nessun servizio a pagamento, account o API AI necessario. Internet serve per installare le dipendenze gratuite al primo avvio o quando cambiano; l'uso successivo è locale.

La V2.2 integra segmenti dinamici configurabili, VIP manuali, tag, note riservate e premi tracciati; Community Insights, confronti eventi, ritorno a30/60/90/180 giorni e report PDF/XLSX generati localmente. Conserva importazioni, identità reversibili, ordinamento e ottimizzazioni precedenti. Lo schema5 è additivo, con backup verificato; nessuna reimportazione necessaria.

## Aggiornamento semplice sul Mac

1. Chiudi EVENTLY premendo **Ctrl+C nella finestra Terminale che lo ha avviato**.
2. Scarica e decomprimi l'unico [pacchetto unico V2.2](https://github.com/merkool96-jpg/EVENTLY---CHART/archive/refs/tags/v2.2.0.zip).
3. Nella cartella **appena scaricata**, fai doppio clic su **AGGIORNA_EVENTLY.command**.
4. Nella finestra di scelta, seleziona la **vecchia cartella EVENTLY che usi già**, quella che contiene i dati. Attendi «Aggiornamento completato».
5. Dalla **vecchia cartella**, riapri **AVVIA_EVENTLY.command**. Lascia aperto il Terminale; si apre il browser su **http://127.0.0.1:8765**.

Non spostare il database e non sostituire manualmente la vecchia cartella. Il comando conserva database e file locali, verifica il pacchetto e salva codice e database precedenti. Prima della migrazione allo schema5 viene creato un ulteriore backup SQLite verificato. Se macOS blocca il comando, usa clic destro → Apri; le restrizioni possono variare con la versione di macOS. Finder e Gatekeeper non sono riproducibili in questo ambiente Linux.

Prerequisiti: Python 3.12+ e Node.js LTS22+ con npm. Per una nuova installazione, apri direttamente AVVIA_EVENTLY.command. Non avviare due copie contemporaneamente.

In **Overview** c'è un solo grafico con due pulsanti: **Valore attribuito** mostra il valore attribuito, **Presenze** mostra i presenti confermati per evento. Non aggiunge una seconda scheda. Versione riconoscibile in Impostazioni: **V2.2 · locale e gratuito**.

### Se hai tante cartelle EVENTLY

Lascia aperta la copia che mostra i tuoi dati. Dal pacchetto nuovo apri **TROVA_EVENTLY.command**: individua il server locale sulle porte abituali e apre il Finder evidenziando AVVIA_EVENTLY.command nella cartella in uso, senza aprire o modificare il database. Se trova più copie o nessuna, non ne sceglie una arbitrariamente. Mantieni aperto quel Finder. Crea un alias di AVVIA_EVENTLY.command (clic destro → Crea alias), sposta **solo l'alias** sulla Scrivania e chiamalo EVENTLY: da allora avvia sempre quello. Non spostare né rinominare la cartella applicativa o il database.

Poi ferma il server con Ctrl+C nel suo Terminale e lancia AGGIORNA_EVENTLY.command dal pacchetto nuovo, scegliendo **la cartella appena individuata**, non quella del download. Riapri dall'alias; nel browser premi Cmd+Maiusc+R e controlla i pulsanti Valore attribuito / Presenze sopra il grafico. Non serve reimportare file o ripristinare nuovamente il database. Il rilevatore è collaudato con processi simulati; l'apertura fisica del Finder richiede il Mac.

## Novità V2.2 da provare

- **Segmenti Community** → scegli una card → Visualizza partecipanti. I membri si ricalcolano; i segmenti possono sovrapporsi. Soglie in Impostazioni.
- **Partecipanti** → seleziona persone o tutti i risultati filtrati → **VIP, tag o riconoscimenti** → Anteprima → Conferma. Puoi escludere singole persone e annullare se i dati pertinenti non sono cambiati.
- **VIP & Rewards** → candidati (solo suggerimenti), VIP manuali, definizioni tag/iniziative, storico premi e informazioni da riassegnare dopo una separazione.
- **Scheda persona** → note private con modifica/eliminazione logica e storico. Note escluse dagli export standard; esportarle richiede scelta esplicita.
- **Eventi** → apri evento → **Performance e report post-evento** → PDF o XLSX. **Performance eventi** permette confronti fra due eventi, categoria o edizioni con lo stesso nome.
- **Community Insights** → distribuzione, aumento frequenza su periodi uguali, recupero, crescita, affinità e timeline. Un ritorno recente o senza occasioni conosciute è non misurabile, non zero.
- **Esporta lista strategica** → campi, ambito, formato e conteggio email prima del download. Nessun limite alle righe visibili.

[Progetto e regole V2.2](docs/V22_DESIGN.md) · [Collaudo, 20 scenari, risultati e limiti](docs/V22_RESULTS.md).

## Percorsi da provare

- **Eventi → Nuovo evento**: data, luogo, categoria, edizione, costo organizzativo e valore convenzionale per presenza. Null = non definito; zero = gratuito. Il valore non è un incasso.
- **Importa partecipanti**: evento → file → mappatura → verifica → anteprima → conferma → riepilogo. Seleziona foglio e riga intestazione; salva un modello. Clicca i contatori per vedere le righe e i dati mancanti. Solo la conferma salva i partecipanti. File e righe originali restano conservati.
- **Eventi → apri evento**: filtra le persone, seleziona anche tutti i risultati oltre la pagina, scegli lo stato e controlla l'anteprima. Conferma; usa Annulla ultima operazione se non sono intervenute correzioni successive. I cinque stati distinguono iscritti, presenti, assenti, annullati e da verificare.
- **Centro Verifica**: consulta motivazioni, fonti, membri dei gruppi e impatto. Unisci scegliendo il nome, Mantieni separati o Decidi più tardi. Un blocco reale disabilita l'unione e indica i membri responsabili. Le separazioni si possono revocare esplicitamente; una revoca non unisce nessuno. Nello storico puoi annullare un'unione.
- **Partecipanti → apri persona → Modifica anagrafica**: nome, cognome, visualizzazione e contatti con controlli sui conflitti. Originali e alias restano ricercabili; un'importazione incompleta non sovrascrive una scelta manuale.
- **Top 50**: clicca un'intestazione per riordinare l'intero insieme idoneo prima di scegliere i50; Top3 segue la metrica. La ricerca trova anche chi era oltre il posto50. Filtri combinabili e viste persistenti sono disponibili anche nel database partecipanti. Sul telefono usa il selettore Ordina risultati.
- **Community Insights**: frequenze, eventi gratuiti/positivi, nuovi e ricorrenti sullo storico completo, ritorno entro una finestra, affinità e inattività. Coorti recenti e copertura incompleta sono segnalate. Conversione iscritti→presenti soltanto con iscritti completi attestati ed esiti risolti.
- **Qualità Dati**: contatori cliccabili per anagrafica, contatti, ambiguità, conflitti, importazioni e righe non attribuite. Una persona senza email non diventa automaticamente un'identità inaffidabile.
- **Esporta partecipanti**: XLSX con Partecipanti/Partecipazioni/Eventi o CSV partecipanti, tutti oppure filtro corrente; nessun limite di50 o di pagina. Stati espliciti, importi/date e protezione formule.
- **Impostazioni**: crea/scarica backup. Per ripristinare, carica una copia, premi Verifica su copia e soltanto dopo Conferma ripristino. Il database corrente viene salvato prima della sostituzione. Copia un backup anche su un supporto esterno.

Archiviare un evento mantiene normalmente lo storico. **Escludi dalle statistiche** è una scelta diversa, reversibile e con anteprima dell'impatto.

## Verifica, limiti e aggiornamento

[Audit preventivo V2.1](docs/AUDIT_V21.md), [report di consegna e limiti V2.1](docs/RELEASE_REPORT_V21.md), [42 scenari e prove](docs/ACCEPTANCE_MATRIX_V2.md), [regole di prodotto](docs/PRODUCT_RULES_V2.md), [flussi](docs/UX_FLOWS_V2.md), [dizionario](docs/DATA_DICTIONARY_V2.md), [milestone](docs/IMPLEMENTATION_PLAN_V2.md).

Il database abituale è `backend/evently.db`, escluso da Git. `EVENTLY_DB` permette un percorso di sviluppo alternativo; l'updater Mac gestisce l'installazione standard nella vecchia cartella. Non usare dati personali per le prove. Le fusioni distruttive delle primissime versioni V1 non sono ricostruibili senza una fonte o backup precedente: non viene inventata provenienza.

In `backend/backups/aggiornamento-…/` sono salvati codice sovrascritto e file del pacchetto; `coppia-compatibile.json` indica il backup pre-aggiornamento abbinato. Per tornare alla V2.1 occorrono **codice V2.1 e copia DB schema4**, a programma fermo: non aprire lo schema5 con codice precedente. Il ripristino dall'interfaccia verifica e migra una copia allo schema corrente.

## Sviluppo e test isolati

```bash
./scripts/install.sh
EVENTLY_DB=/tmp/evently-development.db ./scripts/start.sh
```

Sviluppo: frontend localhost5173, API localhost8000. Produzione locale tramite launcher: localhost8765. API `/docs`. Tutti i bind predefiniti restano localhost. Nessun dato viene inviato a servizi esterni dall'applicazione.

```bash
EVENTLY_DB=/tmp/evently-tests.db .venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
EVENTLY_DB=/tmp/evently-browser-empty.db .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8001
# In un altro terminale:
EVENTLY_URL=http://127.0.0.1:8001 npm run test:e2e --prefix frontend
EVENTLY_URL=http://127.0.0.1:8001 npm run test:sorting --prefix frontend
EVENTLY_URL=http://127.0.0.1:8001 npm run test:performance --prefix frontend
```

Chromium Playwright va installato per i test browser. `test:profiles` richiede una seconda istanza con database sintetico vuoto (default8003). Il test principale richiede un database vuoto ad ogni esecuzione e verifica questa condizione. Benchmark e simulazione updater usano soltanto archivi temporanei:

```bash
EVENTLY_DB=/tmp/evently-benchmark-control.db .venv/bin/python -m scripts.benchmark_v2
.venv/bin/python -m scripts.build_update_manifest
EVENTLY_DB=/tmp/evently-upgrade-control.db .venv/bin/python -m scripts.verify_v2_update
```

Il manifest rileva corruzioni del pacchetto, non autentica un'origine sconosciuta: scarica il pacchetto dal repository indicato.


## Collaudo V2.1

`npm run test:v21 --prefix frontend` richiede una nuova istanza locale con database sintetico vuoto (URL configurabile via EVENTLY_URL). `test:contrast` esamina sette pagine con i dati già creati dalla suite V2.1. Il workflow CI avvia istanze distinte per importazione, profili e V2.1. Nessuna suite usa il database del Mac.

```bash
EVENTLY_DB=/tmp/evently-v21-upgrade-control.db .venv/bin/python -m scripts.verify_v2_update --base f08e73e
```

Questa seconda simulazione verifica specificamente V2.0.1→V2.1/schema4→4; la simulazione senza `--base` verifica ancora V1.2→V2.1/schema3→4. Confronta tutte le colonne e righe preesistenti, oltre a backup codice/DB e integrità/FK.
