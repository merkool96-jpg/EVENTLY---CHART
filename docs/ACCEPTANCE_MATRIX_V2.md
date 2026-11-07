# Matrice preventiva di accettazione

La matrice è stata salvata nella milestone A prima del codice. Lo stato iniziale era pianificato; le prove finali sono registrate sotto. Input sintetici soltanto. I test V1.2 restano, salvo aspettative esplicitamente cambiate dal contratto V2. Nessun test usa il database reale.

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

## Evidenze finali (2026-11-07)

Tutti gli input automatizzati sono sintetici. «Superato» indica il comportamento coperto dai test nominati, non certificazione su ogni file reale o su macOS.

| Scenari | Stato / prova realmente eseguita |
|---|---|
|1–3,8–10|Superati: `test_identity_evidence.py`, nomi differenti senza evidenza, omonimi, email familiare, candidato unico e separazione permanente.|
|4–5,12|Superati: `test_profiles_export.py` scelta/persistenza/alias e `test_revision.py` undo connessioni; Chromium `profiles-export.cjs` e `v2.cjs`.|
|6–7|Superati: `test_5_6_7_compound_aliases_require_review_and_keep_sources`, preflight conservativo.|
|11|Superato: `test_11_revoke_no_auto_merge`.|
|13–17,22|Superati: `test_13_16_17_22_incomplete_rows_header_and_issues`, doppio nome strutturato, pattern email; Chromium header2 e contatori senza scritture definitive.|
|18|Superato: `test_workbook_sheet_selection_manual_mapping_and_stale_preview` e `test_xls_multi_sheet_inspection_and_preview`.|
|19–21|Superati: test fonte duplicata/idempotenza in revision/app; `test_19_order_shared_never_identity_registration_key_preserves_weak`, `test_21_weak_same_source_registration_presence_no_new_people`; Chromium bulk e import.|
|23–25|Superati: test ranking/iscrizioni in revision, stati absent/cancelled in v2_contract; nessun valore da iscrizione.|
|26–27|Superati: `test_26_two_hundred_bulk_all_filtered_and_undo`, `test_21_27_conflicting_sources_and_admin_override`; Chromium selezione, conferma e undo.|
|28–30|Superati: test Bottini20→40, ranking presenze/data/nome, null/zero/positivo in revision.|
|31–32|Superati: `test_31_32_search_before_top50_and_shared_export_filters`, Chromium sorting su66 candidati e ricerca posto51.|
|33|Superato: archivio mantiene storia, preview esclusione senza effetti, reinclusione reversibile.|
|34–36|Superati: storico2025/2026, ritorno entro finestra e conversione insufficiente/50% con copertura attestata.|
|37|Superato: `test_37_frequency_free_paid_and_export_five_states`.|
|38|Superato: `test_38_xlsx_ten_thousand_and_one_all_three_sheets_read_only`, verifica10002 righe con intestazione e tre fogli; benchmark export10k aggiuntivo.|
|39–40|Superati: backup pre-migrazione e blocco se fallisce, restore su copia sintetica con conferma, file corrotto rifiutato; nessun database utente coinvolto.|
|41|Superato: `scripts.verify_v2_update`, pacchetto completo su installazione temporanea dal commit4cb44ae: confronto di tutte le colonne/righe legacy, schema3→4, integrità/FK, backup codice/DB; test updater errori/rollback/percorso/schema futuro.|
|42|Verifica git/manifest: nessun DB, backup, allegato personale o file reale; CSV in examples è dimostrativo. Manifest verifica tutti i file distribuiti.|

Verifiche browser: nessuna eccezione JavaScript nei percorsi coperti; desktop1440 e mobile390; accesso da tastiera a ordinamento e tabelle. Screen reader, Safari e dialog Finder/Gatekeeper: **non verificati** qui. In `RELEASE_REPORT_V2.md` sono registrati limiti di carico e di usabilità ancora da collaudare sul Mac.
