# EVENTLY V2.1 — checklist preventiva (7 novembre 2026)

Base locale verificata: feat/evently-v2, f08e73e, software2.0.1/schema4. Il fetch remoto della sessione non è autorizzato (credenziali HTTPS assenti): non si presume l'assenza di ulteriori commit remoti. Nessun database Mac o allegato personale sarà aperto per sviluppo. Tutte le prove useranno EVENTLY_DB temporaneo e dati sintetici. Nessuna modifica alle regole di matching/merge; si riusa la validazione definitiva.

| Problema verificato nel codice prima di modificarlo | Risultato atteso | Test previsto |
|---|---|---|
| QualityPage page non inclusa nella richiesta, map di tutte le rows; API restituisce intera categoria | Filtri/total/page/page_size backend, massimo200, default50; pagina2 differente e stabile | 200 e10000 casi sintetici; browser avanti/indietro/filtro |
| ReviewPage sola coda/rinviati, nessun workflow guidato; merge valida i membri correttamente | Tre code; Risolvi conflitto con regola/membri/fonti/link, undo tracciato e nuova verifica senza forzare | Gruppo incompatibile con email condivisa, link errato, fonti invariate e gruppi estranei intatti |
| Overview definizioni implicite, spotlight senza apertura profilo; graph Economics/Partecipanti non cliccabile | Definizioni esatte, valore/presenze, scala/data e apertura evento, spotlight profilo | Riconciliazione dashboard/eventi/profile/export; browser click evento/profilo |
| Analytics assegna tutti nuovi su intera storia; frequenze e inattivi solo testo, nessun drill-down | Metriche periodo separate da ricorrenza storica, card cliccabili con identico filtro, confronto gratuiti/positivi | Segmenti2/3/5/10 e30/90/180/365 allineati al selettore persone |
| Eventi nome duplicato, Elimina/cestino per archivio, nessuna ricerca/vista tabella | Card compatte, azioni esplicite/reversibili, ricerca/sort e tabella | Browser ricerca/sort/archivio e storico incluso |
| Persone date ISO, reset classifica anche nel DB, contatore idonei non distingue disponibili/mostrati | Date italiane, riga vs posizione, filtri attivi e totali espliciti | UI/API ricerca globale/export/ranking invariati |
| Sidebar unico gruppo e dicitura Piano locale; testi secondari chiari | Quattro gruppi, locale gratuito, focus/contrasto AA verificato su token usati | Rapporti4.5 normale/3 grande e browser mobile/tastiera |
| Backup solo nome/KB; preview restore senza confronto corrente | Metadati reali read-only, data locale/verifica/schema/conteggi, confronto prima conferma | Backup integro/corrotto, restore preview non modifica dati; conferma conserva backup |

## Flussi e regole attese

- Conflitto: coda dedicata → Risolvi → consulta regole e originali → apri profilo/fonte/link → anteprima undo → conferma esplicita → audit e nuova verifica. Undo può creare blocchi di separazione intenzionali: revoca esplicita necessaria, nessuna unione automatica o forzata. Mostrare impatto simulato e rifiutare snapshot stale.
- Qualità: categoria + ricerca → pagina50 → avanti/indietro; cambio filtro azzera pagina. Nessuna lista completa inviata per una pagina. Calcolo read-model in memoria ammesso e misurato; non affermare paginazione SQL se non implementata.
- Analytics: frequenze sul periodo selezionato, ricorrenza storica separata; inattività sullo storico incluso con filtri personali coerenti. Clic passa lo stesso JSON al selettore partecipanti ed export. Intera storia non ha un confine 'prima del periodo': nuovo/ricorrente nel periodo non applicabile, non tutti nuovi. Ritorno solo date successive, finestra e denominatori espliciti, recenti segnalati.
- Economia: null distinto da0; solo confirmed genera valore attribuito; costi e spesa riportata separati; niente fatturato. Archivio non cambia inclusione analytics.
- Backup: metadati disponibili verificati read-only, errori leggibili; preview su copia + confronto corrente; restore soltanto dopo conferma. Nessun cambio schema previsto, aggiornamento unico con backup esistente.

Gli esiti verranno registrati in docs/RELEASE_REPORT_V21.md separando bug confermati, miglioramenti, aggiunte e limiti. Mac Finder/Safari/screen reader non vengono dichiarati verificati su Linux.

Aggiornamento verifica remota prima della consegna: fetch riuscito usando il credential helper GitHub già configurato, senza salvare credenziali. origin/feat/evently-v2 è f08e73e, identico alla base. Nessun commit remoto escluso.
