# Piano e stato V2

- A Specifica: audit codice/remote, regole, flussi, dizionario e matrice prima delle modifiche funzionali. Commit dedicato.
- B Integrità: schema4 additivo con backup; cinque stati/fonti/override; nomi strutturati, righe incomplete/non attribuibili; archivio distinto da analytics; identità preflight/revoca/rinvio. Test e commit.
- C Operatività: workspace evento, batch con preview/conferma/undo, qualità dati, import wizard/report/template. Test e commit.
- D Analytics: metriche con storia completa, coorti, affinità, inattività; filtri comuni/export/viste. Test e commit.
- E UX: navigazione raggruppata, paginazione, ricerca prima limite, Top3 metrica, token visuali, stati e dialog. Browser e commit.
- F Affidabilità: restore su copia, update schema4, 42 scenari, benchmark2k/10k, regressioni, audit dati tracciati, manifest finale. Commit finale e PR/link.

Scelte conservative/documentate: deduplica incompleti tramite stesso file/riga o ID registrazione evento, mai ordine. Errori isolati non attribuiti; nessun nome inventato. Correzioni massime filtrate validate in preview con snapshot. Undo batch rifiuta modifiche successive. Tabelle con default50 e massimo200 righe per pagina. Nomi composti solo struttura importata/manuale autorevole; il resto è proposta. Conversione richiede copertura dichiarata dall'operatore, non inferita automaticamente.

Non distribuire milestone intermedie. Il pacchetto unico viene generato soltanto al termine. Per prove e benchmark impostare sempre EVENTLY_DB su percorso temporaneo; la V1.2 del Mac rimane indipendente. Un limite non superato viene riportato come tale, non mascherato.

Registro iniziale: A documentata; B–F pianificate. Aggiornare il registro con risultati effettivi dopo ogni milestone.

Milestone B: implementato schema4 con backup, originali e struttura nominativi, cinque stati, conflitti/override, archivio distinto e filtri comuni; backend operativo di massa/analytics/restore predisposto. Regressioni: 78 test passati su EVENTLY_DB temporaneo. Due aspettative V1.2 aggiornate come pianificato: righe errate isolate conservate anziché abortire tutto; archivio mantiene storico. I test updater ora isolano la destinazione dall'ambiente di sviluppo, senza seguire un EVENTLY_DB esterno implicito.

Milestone C: workspace evento, selezione intero filtro e preview/undo; import wizard in sette passi con righe/categorie ispezionabili e modelli; qualità dati con attribuzione esplicita; nuove viste operative collegate. Build TypeScript passata. Test API: 79 superati, incluso reimport registrazioni/presenze per identità deboli dello stesso file. Percorso rapido solo se nessun nome/contatto può produrre evidenze; nessuna soglia abbassata. Verifiche browser pianificate alla milestone E/F, non ancora dichiarate eseguite sulla V2.

Milestone D: analytics con storia precedente al periodo, ritorno strettamente successivo entro finestra, coorti recenti, conversione solo con copertura attestata, soglie frequenza e affinità su presenze. I test verificano 2025→2026 ricorrente, ritorno successivo, dati insufficienti e conversione50% su iscritti con esiti. Eventi mostrati rispettano il periodo senza tagliare la storia che determina nuovo/ricorrente. Rifiniture import: struttura parziale non inventata e categorie ispezionabili coerenti. Nessuna richiesta di installazione intermedia.

Milestone E: verifica Chromium dell'importazione in sette passi, contatori, fonte con errore, bulk/undo, scelta nome, ricerca/export e nove aree; test separato anagrafica/alias/XLSX/CSV. Ordinamento su 66 profili simulati: cinque colonne, Top50/Top3 ricalcolate, ricerca posto51, tastiera, viewport390 senza overflow. Corretto un difetto emerso nel test di refresh: dopo unione il Centro Verifica viene ora aggiornato immediatamente. Nessuna scansione identità all'apertura dashboard; separazione non ricalcola gli aggregati. 88 test backend superati; build TypeScript/Vite superata. Aggiunto ordinamento esplicito utilizzabile anche nelle tabelle mobili con colonne ridotte. Accessibilità screen reader e Finder macOS non dichiarate collaudate.
