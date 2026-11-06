# EVENTLY V1.1: presenze, valori evento e identità reversibili

La V1 classificava le persone per importi e univa i profili cancellando le identità assorbite. Questa revisione ordina per eventi distinti con presenza confermata, poi ultima presenza e nome, conserva le registrazioni originali e rende le nuove fusioni reversibili.

## Modifiche

- Stato esplicito registrazione/presenza confermata/da verificare; aggiornamenti dal profilo con storico.
- `participant_value_cents` nullable per evento, separato da spesa riportata e costi. Bottini Milano da 20 a 40 € aggiorna tutti i valori attribuiti senza modificare acquisti e partecipazioni.
- Gruppi di identità come collegamenti reversibili; annullamento e separazione di identità originali. Controllo di tutte le esclusioni dei gruppi prima di unire e blocchi permanenti.
- Regole automatiche equilibrate per email personali compatibili e nomi completi univoci; omonimi con email diverse separati, ambiguità e incompleti da verificare.
- Wizard con selezione foglio XLS/XLSX, mappatura modificabile, evento, stato, anteprima simulata e conferma atomica; fonti binarie/righe conservate e idempotenza.
- Migrazione additiva con backup SQLite verificato prima delle modifiche; errore backup blocca la migrazione. Eventi archiviati senza cancellazione delle fonti.
- Top 3, KPI coerenti, Centro Verifica Identità, storico decisioni/importazioni, maggiore leggibilità e layout mobile. Bind Vite e API solo localhost.

## Verifiche eseguite

- 28 test API/regressione superati: tutti i 9 test V1 conservati con aspettative aggiornate alla nuova logica e 19 test aggiuntivi.
- Tutti i sei casi obbligatori verificati; backup integro e migrazione ripetibile, fallimento backup, originali conservati, conflitti transitori/gruppi, fogli XLS/XLSX e mappature manuali.
- Build TypeScript/Vite riuscita e audit npm senza vulnerabilità.
- Test browser locale versionato: creazione evento, import guidato con conferma, registrazione esclusa, conferma presenza, 20→40 €, classifica, unione/annullamento, assenza di errori JavaScript e overflow pagina mobile.
- Confronto database locale con backup pre-migrazione: 13 identità, 4 eventi e 37 partecipazioni originali invariati; integrità SQLite e foreign key verificate. Nessun database/backup/dato personale incluso nel commit.

## Migrazione e limiti

Le righe V1 diventano **da verificare**, poiché la versione precedente non distingueva registrazione e presenza. I valori convenzionali V1 restano non definiti. Le precedenti fusioni distruttive non sono recuperabili senza fonti o backup antecedenti.

Le email personali sono riconosciute tramite euristiche esplicite, non verificate da servizi esterni. Il matching è quadratico e non è stato benchmarkato su grandi archivi. Mostrate al massimo 200 coppie, 10.000 profili e 100 decisioni nell’interfaccia; lo storico decisioni completo è disponibile via API. Nessuna autenticazione, multiutenza, gestione incassi o sblocco delle separazioni permanenti. Il vecchio endpoint import diretto resta deprecato per script; la UI richiede anteprima e conferma. La CI include lo stesso smoke browser; l’esecuzione ospitata non è stata ancora verificata.

README aggiornato con avvio, backup, migrazione, regole di business, API, riproduzione test e limiti. Nessun servizio a pagamento o API AI introdotto.
