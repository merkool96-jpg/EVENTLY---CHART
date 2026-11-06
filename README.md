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

La Top 50 include soltanto profili con almeno una **presenza confermata**, ordinati per:

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

- Stessa email personale con nome compatibile e contatti senza conflitti: unione automatica.
- Nome e cognome completi identici, un solo gruppo candidato e nessun conflitto: unione **presunta**, motivazione esplicita nello storico.
- Nomi parziali, email generiche/condivise, prove discordanti o più gruppi possibili: nuovo record e Centro Verifica Identità.
- Omonimi con email differenti: blocco permanente MANTIENI SEPARATI.
- Dati insufficienti: profilo incompleto; un nome singolo senza email personale non viene assunto come prova sufficiente per collegare eventi diversi.

Il riconoscimento di email personale è **euristico**, non una certificazione: esclude caselle generiche note e identificativi troppo brevi. La compatibilità nomi usa similarità normalizzata >=84%; il Centro propone somiglianze >=70%, telefoni uguali o email uguali. Il punteggio non è una probabilità. Tutte le decisioni automatiche sono tracciate e annullabili.

**UNISCI** controlla prima tutti i membri dei due gruppi: un solo blocco permanente impedisce la fusione con risposta 409. **Annulla unione** nello storico disattiva quel collegamento e ricalcola i gruppi; non annulla silenziosamente altre decisioni successive. La separazione risultante genera blocchi permanenti tra i gruppi. **Separa identità** nel profilo scollega tutte le unioni incidenti all’identità originale selezionata, conserva le sue righe e crea blocchi verso gli altri membri. Se era un ponte, anche il resto del gruppo può suddividersi: le righe originali rimangono sempre intatte.

MANTIENI SEPARATI è permanente e non ha un pulsante di sblocco in questa versione. Gli eventi vengono **archiviati**, non eliminati fisicamente: le fonti restano disponibili nello storico importazioni.

## Demo e verifiche

**Esplora la demo** dalla dashboard vuota carica quattro eventi e tredici identità fittizie. Il caricamento è consentito solo in un database senza eventi, anche archiviati. I nuovi dati demo hanno presenze esplicite e valori convenzionali.

```bash
.venv/bin/python -m pytest backend/tests -v
cd frontend
npm ci
npm run build
npm audit --audit-level=high
```

Sono mantenuti tutti i nove test V1, aggiornando le aspettative incompatibili con la revisione (spesa distinta da valore, separazioni permanenti e originali non distrutti), e aggiunti diciannove test di regressione. La suite verifica tutti i casi obbligatori, oltre a backup, migrazione bloccata in caso di errore, file reali dei tre formati, fogli, mappature, anteprime senza effetti, fonti conservate e conflitti tra gruppi.

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
