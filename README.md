# EVENTLY · V1.1

Gestionale personale locale per eventi e partecipanti. React + Vite + TypeScript + Tailwind, FastAPI e SQLite. Nessuna API AI, pagamento, chiave, abbonamento o servizio esterno necessario al funzionamento. Dipendenze gratuite. Hardware e hosting eventuale sono a scelta dell’utente; l’applicazione non richiede hosting.

## Avvio e aggiornamento

Prerequisiti: Python 3.12+ e Node.js 22+ con npm.

```bash
./scripts/install.sh
./scripts/start.sh
```

API su `127.0.0.1:8000`, frontend di sviluppo su `127.0.0.1:5173`, entrambi esclusivamente localhost per impostazione predefinita. Per usare solo la build, senza Vite:

```bash
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

FastAPI serve la build in `frontend/dist`; API documentate nel percorso `/docs`. Fermare la vecchia versione prima di aggiornare. `backend/evently.db` è persistente e non tracciato da Git; `EVENTLY_DB` consente un percorso alternativo. Non cancellare il database durante installazioni o aggiornamenti. L’installazione usa lockfile e non azzera dati.

## Backup e migrazione V1 → V1.1

Prima di qualsiasi modifica dello schema di un database esistente, la migrazione crea un backup tramite **SQLite Online Backup API**, lo riapre e verifica integrità e riferimenti. Se il backup fallisce, la migrazione si interrompe. DDL e aggiornamento della versione schema sono in una transazione. I backup sono in `backend/backups`, esclusi da Git, con manifest SHA-256 e permessi restrittivi. La migrazione è additiva e ripetibile: conserva le tabelle originali e aggiunge stato, valori, collegamenti, storico e fonti.

Backup manuale, anche prima di avviare/migrare l’app:

```bash
.venv/bin/python -m backend.backup
.venv/bin/python -m backend.backup --verify backend/backups/NOME-BACKUP.db
```

Il comando di verifica confronta SHA-256, `integrity_check` e `foreign_key_check`. È disponibile anche `POST /api/backup`. Conservare una copia esterna dei backup se la macchina può essere eliminata: il disco locale non è una copia off-site. Per verificare/ripristinare una copia senza sovrascrivere il database corrente, copiarla in un percorso distinto e usare `EVENTLY_DB` con il server fermo; l’avvio applicherà nuovamente l’eventuale migrazione della copia. Per tornare alla V1 usare una copia del backup V1 insieme al codice V1; non aprire un database V1.1 con codice V1.

**I dati V1 non attestavano la presenza:** tutte le righe migrate diventano `unknown` (da verificare), non presenze confermate. Sono visibili nei profili e si possono confermare esplicitamente. Il valore convenzionale degli eventi migrati è non definito. I totali di classifica possono quindi diminuire rispetto alla V1: nessuna partecipazione viene cancellata.

**Le fusioni distruttive fatte dalla V1 non sono reversibili retroattivamente.** I contatti rimasti negli alias vengono conservati e riutilizzati per identificazioni esatte, ma non ricostruiscono partecipazioni o registrazioni eliminate. Una fonte originale o un backup precedente alla fusione è necessario per recuperarli. Non viene inventata alcuna provenienza storica.

## Classifica e valori economici

La Top 50 include soltanto profili con almeno una **presenza confermata**. Per impostazione predefinita sono ordinati per:

1. Numero di eventi distinti confermati, decrescente.
2. Data dell’ultima presenza confermata, più recente per prima.
3. Nome alfabetico senza distinzione di maiuscole e accenti.

Registrazioni e righe da verificare restano visibili ma non incrementano il ranking. Più identità unite nello stesso evento contano una sola presenza. Dashboard, Top 3, classifica e profili usano lo stesso modello e si ricalcolano dopo ogni decisione o cambio di stato.

Ogni evento ha `participant_value_cents`, distinto da `cost`:

- `null`: non definito; la UI segnala i valori mancanti e mostra un subtotale noto.
- `0`: evento gratuito, valore definito pari a zero.
- Positivo: valore convenzionale in centesimi per ogni presenza confermata.

**Bottini Milano = 20 €** attribuisce 20 € per partecipante confermato. Modificandolo a 40 €, profili, dashboard e classifica visualizzano subito il nuovo valore, senza riscrivere partecipazioni o acquisti. Gli importi caricati dai file sono **spesa riportata**, non valore convenzionale, ricavi verificati o pagamenti incassati. I costi organizzativi restano separati e non vengono sottratti dal valore attribuito per simulare un margine. Nessuna API gestisce incassi reali.

## Importazione guidata

La UI richiede **file → foglio/mappatura → evento/stato → anteprima → conferma**.

- CSV UTF-8 con virgola, punto e virgola o tab; XLS e XLSX con selezione del foglio.
- Intestazioni nella prima riga; riconoscimento automatico e correzione manuale di Nome completo, Nome, Cognome, Email, Telefono e Spesa riportata.
- Numeri Excel, `1234.56` e `1.234,56`; la spesa opzionale vale zero se assente.
- Nessuna mappatura del prezzo di acquisto al valore convenzionale dell’evento.
- Stato predefinito **registrazione**; presenze confermate solo con selezione esplicita.
- L’anteprima simula l’intera importazione in un savepoint annullato e riepiloga nuove righe, duplicati, aggiornamenti, unioni automatiche/presunte, ambiguità e profili incompleti.
- Conferma atomica; anteprima valida un’ora, invalidata se cambiano i dati di riferimento. In quel caso rigenerarla prima di confermare.
- Originale binario, foglio, mappatura e righe originali conservati in SQLite. Download dell’originale nel Centro Verifica Identità. Il database e i backup contengono quindi dati personali e vanno custoditi come tali.
- Identità esatta una volta per evento. Stesso file/foglio/mappatura/evento/stato non duplica importazione né presenze, anche con nome file diverso. Le righe duplicate nello stesso file restano nella fonte ma non sommano nuovamente la spesa.
- Reimportare lo stesso elenco come presenze confermate aggiorna le registrazioni senza duplicarle. Reimportarlo come registrazioni non declassa presenze già confermate. I cambi manuali conservano uno storico separato.

Limiti: 10 MB, 20.000 righe e 200 colonne; XLSX decompresso massimo 50 MB. Per CSV non UTF-8 serve conversione. Tenere i telefoni come testo nei fogli Excel per non perdere zeri iniziali. `examples/partecipanti.csv` è un esempio.

L’endpoint V1 `POST /api/events/{id}/import` resta disponibile, marcato deprecato, per compatibilità con script: importa direttamente, con stato predefinito `registered`. Il flusso UI usa sempre anteprima e conferma. Le API nuove sono `/api/imports/inspect`, `/preview` e `/{token}/confirm`.

## Identità e decisioni reversibili

Le identità originali e le partecipazioni non vengono più spostate o cancellate durante una fusione. Un gruppo è un grafo di collegamenti attivi; lo storico registra decisioni manuali e automatiche.

- Nome e cognome vengono confrontati separatamente. Nomi propri differenti non sono compensati dal cognome uguale e non generano una segnalazione senza identificativi coincidenti.
- Stessa email personale, nome esatto, cognome esatto o con un solo refuso plausibile, nessun contatto contraddittorio e nessun indizio di email condivisa: unione automatica, dopo controllo di tutti i membri del gruppo.
- Nome e cognome normalizzati identici, un solo gruppo candidato e nessun conflitto: identità presunta. Le identità originali esattamente già note vengono riutilizzate per evitare duplicati.
- Nome esatto e cognome con un refuso plausibile: verifica manuale. Il refuso ammette una sola inserzione, rimozione, sostituzione o trasposizione adiacente, con cognome di almeno quattro lettere. Nessun fuzzy matching dei nomi propri.
- Email uguale con nomi incompatibili: verifica con avviso di possibile indirizzo condiviso, mai unione automatica. Stesso telefono è un'evidenza da verificare, non un'autorizzazione automatica a unire.
- Email personali differenti: profili distinti, nessuna proposta basata soltanto sul nome. L'amministratore può unirli manualmente se il nome è compatibile o ci sono identificativi forti/alias confermati; restano inviolabili le separazioni manuali.
- Nome incompleto: verifica solo se il nome è esatto, l'email contiene indizi specifici sia del nome sia del cognome e il gruppo candidato è univoco. L'email è un indizio, non una prova per l'unione automatica.
- Dati insufficienti: profilo incompleto senza segnalazioni generiche. Alias nominali confermati manualmente vengono riutilizzati soltanto nel gruppo in cui sono stati approvati.

Il riconoscimento di email personale è **euristico**, non una certificazione: esclude caselle generiche note e identificativi troppo brevi. Il Centro mostra la motivazione verificabile, non percentuali di somiglianza o probabilità. La coda viene calcolata dai dati correnti: aggiornando l'algoritmo, le proposte non conformi scompaiono senza cancellare persone o decisioni.

**Limite sui nomi composti:** quando il file contiene soltanto il nominativo completo, si interpreta il primo elemento come nome e il resto come cognome. Confini ambigui, doppi nomi e cognomi particolari restano conservativi e possono richiedere verifica con identificativi forti. Non si usa un servizio esterno o una lista di nomi per inventare equivalenze.

**UNISCI** controlla prima tutti i membri dei due gruppi: un solo blocco permanente impedisce la fusione con risposta 409. **Annulla unione** nello storico disattiva quel collegamento e ricalcola i gruppi; non annulla silenziosamente altre decisioni successive. La separazione risultante genera blocchi permanenti tra i gruppi. **Separa identità** nel profilo scollega tutte le unioni incidenti all’identità originale selezionata, conserva le sue righe e crea blocchi verso gli altri membri. Se era un ponte, anche il resto del gruppo può suddividersi: le righe originali rimangono sempre intatte.

MANTIENI SEPARATI deciso dall’amministratore è permanente e non ha un pulsante di sblocco. Le vecchie esclusioni create automaticamente dalla V1.1 per la sola email differente possono essere superate esclusivamente da una nuova unione manuale esplicita: lo storico resta intatto e registra il superamento. Se esiste anche una scelta manuale di separazione, il blocco prevale sempre. Gli eventi vengono **archiviati**, non eliminati fisicamente: le fonti restano disponibili nello storico importazioni.

## Demo e verifiche

**Esplora la demo** dalla dashboard vuota carica quattro eventi e tredici identità fittizie. Il caricamento è consentito solo in un database senza eventi, anche archiviati. I nuovi dati demo hanno presenze esplicite e valori convenzionali.

```bash
.venv/bin/python -m pytest backend/tests -v
cd frontend
npm ci
npm run build
npm audit --audit-level=high
```

Sono mantenuti tutti i nove test V1, aggiornando le aspettative incompatibili con la revisione, i diciannove test V1.1 e ventitré test sul motore conservativo: 51 test complessivi. Il test degli omonimi con email differenti ora verifica anche la scelta manuale esplicitamente consentita dai nuovi requisiti. La suite verifica tutti i casi obbligatori, oltre a backup, migrazione bloccata in caso di errore, file reali dei tre formati, fogli, mappature, anteprime senza effetti, fonti conservate e conflitti tra gruppi.

Smoke test browser **solo su database dedicato vuoto**, mai sul database personale. Esempio con due terminali:

```bash
# Terminale 1: scegliere un percorso NUOVO e vuoto
EVENTLY_DB=/tmp/evently-browser-test.db .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8001

# Terminale 2
cd frontend
npx playwright install chromium
npm run test:e2e
```

Se Chromium è già installato: `BROWSER_EXECUTABLE=/usr/bin/chromium npm run test:e2e`. Il test rifiuta un database con eventi, crea dati fittizi e lascia il database di prova per diagnosi; per ripeterlo scegliere un altro percorso nuovo. `EVENTLY_URL` cambia la destinazione. Verifica UI di creazione evento, wizard, conferma, registrazione esclusa, conferma presenza, 20→40 €, Top 50, unione/annullamento, errori JavaScript e assenza di overflow pagina mobile. Gli screenshot diagnostici sono in `/tmp/evently-v11-*.png`. La CI è configurata per test API, build, audit e lo stesso smoke browser con database temporaneo. È stata verificata l’esecuzione locale; l’esito della CI ospitata va controllato su GitHub dopo il push.

## Limiti ancora presenti

- Uso personale locale, senza autenticazione o multiutenza. Non esporre su Internet né cambiare i bind senza una revisione della sicurezza.
- Matching e aggregazioni in memoria, confronto candidati quadratico. Adatto a piccoli archivi; il limite file non è una garanzia di prestazioni su 20.000 persone diverse. Nessun benchmark su archivi grandi. Sono mostrate al massimo 200 coppie e 10.000 profili.
- Storico UI delle decisioni limitato alle ultime 100, storico completo disponibile via API. Nessun ripristino eventi archiviati dall’interfaccia né sblocco delle separazioni permanenti.
- La spesa di una partecipazione già presente non viene sovrascritta dal reimport: l’originale successivo viene conservato; non esiste ancora un editor della spesa. Non è contabilità o gestione pagamenti.
- I file originali aumentano la dimensione del database; nessuna politica automatica di cancellazione delle fonti confermate. Le anteprime scadute vengono rimosse alla successiva anteprima.
- Le unioni V1 non hanno una provenienza recuperabile se mancano fonti o backup. La V1.1 non dichiara di recuperarli.

## Utilizzo sul Mac senza terminale

Aprire `LEGGIMI-MAC.html` per le istruzioni illustrate dal browser. Con Python 3.12+ e Node.js LTS installati, fare doppio clic su `AVVIA_EVENTLY.command`. Il primo avvio prepara l'ambiente, installa dai lockfile e compila il frontend; poi apre automaticamente la dashboard su `http://127.0.0.1:8765`. Lasciare aperta la finestra di avvio. Il launcher usa la build servita da FastAPI, con un solo indirizzo e senza dipendere dal server di sviluppo Vite.

`127.0.0.1` indica sempre il dispositivo su cui si trova il browser: quello del Mac non raggiunge il server cloud. Se il desktop cloud non è accessibile, usare questa copia locale gratuita. Il codice scaricato da GitHub non include database personali; un eventuale pacchetto privato con dati va conservato privatamente. Le copie cloud e Mac non si sincronizzano.

Il launcher non cancella database o backup, memorizza soltanto le versioni delle dipendenze nella cartella ignorata `.evently-local` e mantiene il server su localhost. Verifica disponibilità della porta e salute dell'API prima di aprire il browser. Gli aggiornamenti richiedono una nuova preparazione solo quando cambiano lockfile o sorgenti. L'avvio è stato verificato nel runtime Linux cloud; il doppio clic e gli avvisi Gatekeeper richiedono verifica sul Mac dell'utente.


## Aggiornamento del motore conservativo sul Mac

Il branch dedicato è `fix/evidence-based-identities`. La copia già scaricata sul Mac non cambia automaticamente. Chiudere EVENTLY, fare una copia della cartella attuale e scaricare lo ZIP di quel branch. Per applicare questa correzione senza sostituire i dati, copiare soltanto `backend/identity.py` e `frontend/src/main.tsx` dallo ZIP nelle rispettive cartelle dell'installazione esistente. Poi riaprire `AVVIA_EVENTLY.command`: il launcher ricompila il frontend aggiornato. Non sostituire `backend/evently.db`, `backend/backups` o l'intera cartella `backend`. Nessuna migrazione o cancellazione dei dati è richiesta da questa correzione.

Il conteggio di proposte eliminate nella coda cloud non descrive il database indipendente del Mac. La verifica eseguita su questa istanza è documentata in `docs/IDENTITY_ENGINE_REVIEW.md`.

## Colonne ordinabili: Partecipanti e Top 50

Cliccare **Partecipante**, **Presenze**, **Registrazioni**, **Valore attribuito** o **Ultimo incontro** per ordinare. Un secondo clic inverte il verso; la freccia e il testo sopra la tabella mostrano il criterio attivo. Nomi inizialmente A–Z, quantità/importi dal maggiore, date dalla più recente. Date mancanti sempre in fondo. A parità rimangono presenze, ultima presenza, nome e ID come criteri deterministici.

In **Top 50** vengono selezionate nuovamente le prime 50 persone secondo il criterio scelto, limitatamente a chi ha almeno una presenza confermata. La Top 3 segue la stessa scelta. La ricerca filtra le 50 persone selezionate. **Ripristina classifica per presenze** torna al ranking predefinito. L'ordinamento resta durante la navigazione nella sessione corrente e si ripristina ricaricando la pagina. Nessuna decisione di identità, partecipazione o importo viene modificata; per i valori parzialmente non definiti viene ordinato il subtotale noto già visualizzato.

Test browser dedicato: con frontend avviato, `cd frontend && npm run test:sorting` (eventualmente `BROWSER_EXECUTABLE=/usr/bin/chromium`). Usa risposte API simulate, non modifica il database e verifica cinque criteri, inversione, Top 50/3, ricerca, reset, tastiera e mobile.

Per applicare solo le colonne ordinabili alla copia Mac esistente: chiudere EVENTLY e conservare una copia della cartella; dallo ZIP del branch `feat/sortable-participant-columns` copiare `frontend/src/main.tsx`, **anche il nuovo file `frontend/src/peopleSorting.ts`**, e `frontend/src/style.css` nelle rispettive posizioni. Riaprire `AVVIA_EVENTLY.command` per ricompilare. Non sostituire il database o la cartella backend. Copiare soltanto main.tsx senza peopleSorting.ts impedirebbe la compilazione.

## Prestazioni al caricamento e dopo le decisioni

Il Centro Verifica seleziona le coppie da confrontare mediante indici temporanei su nome proprio, email e telefono: ogni coppia ammessa dalle regole di evidenza rimane esaminata, senza confrontare inutilmente tutti con tutti. I gruppi e le separazioni vengono sempre riletti dal database; non viene memorizzata una coda obsoleta. La normalizzazione di nomi e la classificazione delle email usano cache limitate, indipendenti dai dati modificabili.

Le risposte frontend vengono applicate singolarmente appena disponibili: statistiche e partecipanti non attendono la fine del matching. MANTIENI SEPARATI ricarica soltanto coda e storico; UNISCI ricarica anche aggregati e partecipanti. Il riepilogo dashboard riutilizza la stessa aggregazione anziché calcolarla due volte.

Benchmark locale riproducibile sul codice prima/dopo: 2.130 profili **simulati**, 213 nomi propri condivisi, email diverse. La stessa coda passa da circa **5,59 s a 0,035 s** (circa 160× per il solo calcolo candidati). Non è una misura del Mac dell'utente né una promessa su ogni archivio: un grande blocco di nomi/email condivisi può ancora avere costo quadratico. Un test confronta la coda ottimizzata con il confronto esaustivo su nomi, email, telefoni, gruppi e separazioni.

Test browser: `cd frontend && npm run test:performance`, con frontend già avviato. Usa API simulate: verifica che i KPI appaiano mentre il matching è in attesa, che la separazione non ricarichi gli aggregati e che l'unione li aggiorni. Nessuna modifica al database personale.

Per ripetere il confronto senza usare dati personali: `.venv/bin/python -m scripts.benchmark_matching`. Crea un database temporaneo con 2.130 profili fittizi, confronta selezione esaustiva e indicizzata e verifica che la coda sia identica. La misura esaustiva nello script include già le nuove cache, quindi può differire dalla misura storica del codice precedente riportata sopra. Suite dopo questa ottimizzazione: 52 test API superati, più test browser di prestazioni e ordinamento. La copia Mac deve essere aggiornata: per questa correzione cambiano `backend/identity.py`, `backend/reporting.py`, `backend/app.py` e `frontend/src/main.tsx`; mantenere sempre database e backup esistenti e le dipendenze frontend dei precedenti aggiornamenti.

## V1.2 · Anagrafica, unione con scelta e download dati

Questa release parte da `perf/faster-identity-review` (`cd075e4`), discendente verificato delle correzioni identità (`44754b0`) e colonne ordinabili (`500a9f1`). Non sostituisce queste funzioni. Il branch della release è `feat/profiles-and-participant-export`.

### Scelta del nominativo

**UNISCI** apre una finestra con i due nominativi principali, il suggerimento, campi modificabili e anteprima. Il suggerimento considera presenza di nome e cognome, precedenti scelte manuali, ripetizioni consecutive e caratteri sospetti; non sceglie semplicemente il testo più lungo. “Iside Oliveti Oliveti” viene suggerito come “Iside Oliveti”, senza riscrivere l'originale. I nomi composti restano soggetti ai limiti di interpretazione già documentati e la conferma è sempre dell'amministratore.

**CONFERMA UNIONE** ricontrolla i membri originali e tutte le separazioni. La scelta del nome non modifica questi controlli e non autorizza una fusione altrimenti incompatibile. La validazione dell'anagrafica e il collegamento sono nella stessa transazione: se il salvataggio fallisce, l'unione non avviene.

Nel profilo, **Modifica anagrafica** permette di cambiare nome, cognome, nominativo visualizzato, email e telefono. Il nome visualizzato è un campo esplicito: modificarlo se si vuole che differisca o segua i cambi di nome/cognome. Nuovi contatti già presenti su altri profili vengono bloccati con un messaggio; un contatto condiviso già importato può rimanere invariato mentre si corregge il nome. Le scelte sono versionate nella nuova tabella `profile_edits`, senza modificare `people` o le fonti. Gli alias originali e i nominativi precedenti sono ricercabili anche se il nome principale cambia. Importazioni successive non riscrivono i campi manuali; un'identità esattamente corrispondente ai nuovi nome/email/telefono principali viene riconosciuta.

Le versioni manuali sono associate al gruppo in cui sono state approvate. Dopo annullamento/separazione, un nome scelto per il gruppo unito non viene applicato a un gruppo che non comprende più i membri originari; tornano applicabili le precedenti versioni pertinenti. Lo storico non viene cancellato.

### Esporta partecipanti

Nella pagina **Partecipanti** il pulsante **Esporta partecipanti** permette di scegliere formato, tutti i profili oppure la ricerca attiva, e mostra il conteggio ottenuto direttamente dal database. L'ordinamento visuale non è un filtro; la Top 50 non limita l'esportazione. Sono inclusi anche profili senza presenze e oltre il limite di 10.000 profili della lista UI.

- **XLSX:** fogli Partecipanti, Partecipazioni ed Eventi. Anagrafica canonica, presenze distinte, registrazioni senza presenza, stati da verificare, eventi gratuiti/positivi, subtotale attribuito e numero di valori non definiti, prima/ultima partecipazione (incluse registrazioni), prime/ultime presenze confermate in colonne distinte, completezza del nominativo e disponibilità dei contatti. Partecipazioni con data, tipo, stato e valore convenzionale. Nel foglio Eventi i conteggi rispettano i partecipanti esportati; con filtro, sono inclusi soltanto gli eventi collegati, senza filtro anche gli eventi vuoti. Gli eventi archiviati restano esclusi coerentemente con le viste attive.
- **CSV:** elenco completo Partecipanti con gli stessi campi anagrafici/aggregati; UTF-8 con BOM, separatore `;`, importi decimali con virgola e date ISO. Per il dettaglio delle partecipazioni e degli eventi scegliere XLSX.
- Importi XLSX numerici in euro e date come celle data, con filtri e intestazioni. Nessuna spesa reale viene spacciata per valore attribuito. Valori evento non definiti rimangono vuoti; gli aggregati mostrano il subtotale noto e il conteggio mancante.
- Testi potenzialmente interpretabili come formule vengono neutralizzati, compresi prefissi formula preceduti da spazi o caratteri di controllo. Il contenuto esportato è calcolato in un'unica transazione di sola lettura; non modifica dati.

API: `POST /api/matches/preview`, scelta opzionale `profile` nella decisione di merge, `PATCH /api/people/{id}`, `GET /api/people/{id}/history`, `GET /api/exports/count?q=…`, `GET /api/exports/participants?format=xlsx|csv&q=…`. La ricerca export usa gli stessi campi e alias della lista.

### Aggiornare sul Mac senza copiare i file a mano

1. Chiudere EVENTLY: nella vecchia finestra di avvio premere **Ctrl+C**.
2. Scaricare lo ZIP del branch `feat/profiles-and-participant-export` da GitHub ed estrarlo in una cartella **diversa** da quella che si usa già.
3. Nella cartella appena scaricata fare doppio clic su **AGGIORNA_EVENTLY.command**.
4. Quando Finder lo chiede, selezionare la **vecchia cartella EVENTLY**, quella che contiene i dati. Non selezionare la nuova cartella scaricata.
5. Attendere “Aggiornamento completato”, poi aprire **AVVIA_EVENTLY.command nella vecchia cartella**. Il launcher ricompila e apre il browser.

L'updater funziona dal pacchetto estratto, senza Git e senza scaricare codice al momento dell'aggiornamento. Verifica gli SHA-256 del manifest contro il contenuto del pacchetto; questa verifica rileva corruzioni, non sostituisce la fiducia nella provenienza: usare soltanto lo ZIP ufficiale GitHub. Rifiuta cartelle sbagliate, percorsi protetti/esterni e collegamenti simbolici. Verifica che l'applicazione nella cartella di destinazione sia ferma. Crea e verifica un backup SQLite e una copia dei file di codice sovrascritti in `backend/backups/aggiornamento-…`. Se la copia del codice fallisce, ripristina i file precedenti.

Non copia né cancella database, backup, `.env`, `.venv`, `node_modules`, build o file locali estranei al manifest. Il database rimane nella vecchia cartella; non spostarlo nella nuova. Il primo avvio V1.2 esegue una migrazione additiva allo schema **3**, con un ulteriore backup verificato prima della modifica. Se questo backup fallisce, non migra. I dati V1/V1.1 e le decisioni restano intatti. Per un eventuale ritorno a una versione precedente, usare il codice salvato **insieme a una copia del database pre-migrazione**, senza aprire schema 3 con il vecchio codice. Non sovrascrivere il database attuale per fare una prova di ripristino.

L'interfaccia macOS/Finder e gli avvisi Gatekeeper non possono essere verificati dal runtime Linux: sono stati verificati la sintassi dello script, il motore di aggiornamento con backup e rollback e l'avvio dell'app nel cloud. Su macOS il primo aggiornamento va confermato dall'utente. Nessun servizio a pagamento introdotto.

### Verifiche V1.2

Suite backend e updater, build TypeScript/Vite e browser: scelta nominativo, suggerimento senza ripetizioni, persistenza dopo importazioni, alias ricercabili, contatti con conflitti, blocchi di gruppo non aggirabili, XLSX/CSV sicuri e non limitati alla UI, file scaricati dal browser, comportamento mobile, backup e rollback dell'updater. Il test `npm run test:profiles` richiede un database dedicato vuoto e lascia dati fittizi per diagnosi. Il manifest si rigenera come passo finale di packaging con `.venv/bin/python -m scripts.build_update_manifest`.
