# Matrice preventiva di accettazione

Stato iniziale per tutti: pianificato, non dichiarato superato. Input sintetici soltanto. I test V1.2 restano, salvo aspettative esplicitamente cambiate dal contratto V2. Nessun test usa il database reale.

| ID | Input / azione | Risultato richiesto | Verifica prevista |
|---|---|---|---|
|1|Marco/Rocco Giacalone|Nessuna proposta|API identità|
|2|Arianna Aricò/Marianna Marino|Nessuna proposta|API identità|
|3|Mario Rossi senza email, unico|Presunta solo senza conflitti|Import/API|
|4|Sofia/Sofia Di Gio, decisione valida|Scelta principale persistente|API + browser|
|5|Iside Oliveti ripetuto, email uguale|Nome pulito proposto, guard gruppo|API + browser|
|6|Francesco Son/Sonnessa email uguale|Verifica, no auto|API|
|7|Rebecca Lai/Lai Musa email uguale|Conservativo, no auto|API|
|8|Email familiare nomi diversi|No auto|API|
|9|Omonimi email personali diverse|Distinti|API|
|10|Blocco manuale + reimport|Blocco rispettato|API|
|11|Revoca blocco|Nessuna fusione automatica|API|
|12|Merge poi undo|Collegamenti/fonti ripristinati|API|
|13|Solo nome+cognome|Importabile, struttura mantenuta|File/API|
|14|Nome+email|Importabile incompleto|File/API|
|15|Solo email valida|Persona senza nome inventato|File/API|
|16|Nessun identificativo|Originale non attribuibile|File/API|
|17|Introduzioni/colonne superflue|Header proposto/correggibile, originali|File/API/browser|
|18|XLSX multifoglio|Selezione foglio|File/API|
|19|Righe ripetute|Fonti sì, una partecipazione|API|
|20|Stesso file due volte|Idempotente|API|
|21|Iscritti→presenti|Aggiornamento senza duplicati|API/browser|
|22|Errore isolato|Valide salvate, errore visibile/originale|API|
|23|Iscritto|Non in Top 50 presenze|API|
|24|Presente ripetuto|Una presenza/evento|API|
|25|Assente|Zero presenze|API|
|26|200 persone bulk preview/conferma/undo|Conteggi esatti, reversibile|API/browser|
|27|Fonti presente+assente|Conflitto, unknown finché corretto|API|
|28|Valore20→40|Aggregati dinamici|API|
|29|Gratuito vs null|Distinti|API/export|
|30|Ranking base|Presenze/data/nome|API/browser|
|31|Ordina per valore|Selezione prima del limite50|API/browser|
|32|Cerca posto51|Trovato prima del limite|API/browser|
|33|Archivia evento|Storico presente in ranking|API|
|34|Presente2025 +2026|Ricorrente nel filtro2026|API analytics|
|35|Solo file presenti|Conversione dati insufficienti|API|
|36|Ritorno|Solo date successive/finestra|API|
|37|Gratis frequente vs pagante occasionale|Metriche distinte|API analytics|
|38|XLSX10001+|Tutte righe, tre fogli|Export/API|
|39|Migrazione|Backup verificato prima modifica|Migrazione sintetica|
|40|Restore|Prova copia e conferma, no DB utente|API sintetica|
|41|UpdateV1.2→V2|Fonti/decisioni/versioni conservate|Updater sintetico|
|42|Pubblicazione|Nessun DB/file personale tracciato|Controllo git + manifest|

Test aggiuntivi: conflitti sui gruppi prima commit, import preview senza effetti, token scaduti/stale, rollback atomico, formule CSV/XLSX, filtri/export identici, viste persistenti, annullamento bulk dopo intervento successivo rifiutato, archivio vs esclusione, sole righe vuote, BOM/accénti, nomi composti strutturati, errori comprensibili, navigazione e responsive. Benchmark 2k e10k, hardware/dati/tempi reali in report finale; celle non eseguite rimangono non verificate.
