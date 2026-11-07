# EVENTLY V2 — contratto di prodotto e audit (milestone A)

Base ispezionata: 4cb44ae, discendente di cd075e4, 500a9f1 e 44754b0. main ec2ca96 è arretrato. Verifica remota: nessuna correzione successiva. Stack e dipendenze locali mantenuti. Il database Mac è estraneo alle prove; ogni comando di sviluppo usa EVENTLY_DB temporaneo.

## Audit del codice V1.2

| Area | Stato verificato nel codice | Rischio / correzione V2 |
|---|---|---|
| Import XLSX/XLS/CSV, fogli, mappatura, preview/savepoint, token | Funzionanti | Prima riga obbligatoria; errore isolato abortisce tutto; nome obbligatorio; nessun modello mappatura. Servono righe non attribuibili e report riconciliato. |
| Originali e deduplica | File BLOB e import_rows conservati | ID ordine assente; identità deboli possono duplicarsi nel passaggio iscritti/presenti. Usare identificativi registrazione, mai ordine come persona. |
| Identità | Evidenze conservative, blocchi di gruppo e undo funzionanti | Split primo token non affidabile per nomi composti; blocco solo dopo clic; separazioni irrevocabili; manca rinvio. |
| Anagrafica | Overlay versionato, alias, contatti e merge dialog | Va conservata la struttura nome/cognome fornita; scelte manuali devono prevalere nel suggerimento. |
| Partecipazioni | Tre stati, una riga originale/persona/evento | Mancano assente/annullato, conflitti e correzioni amministrative consolidate. |
| Eventi | CRUD/costo/valore nullable | Archivio esclude erroneamente lo storico; mancano categoria, edizione, workspace, esclusione analytics distinta. |
| Ranking | Ordinamento e Top 50 globali funzionanti | Ricerca dopo limite 50, tabella fino a 10k righe; Top 3 non esplicita metrica. |
| Export | Tre fogli XLSX, CSV UTF-8, formule neutralizzate, no cap | Nuovi stati, filtri e archivio da allineare. |
| Prestazioni | Blocking matching e risposte progressive | Import rilegge identità a ogni riga; aggregazioni in memoria; niente paginazione. Misurare, non presumere. |
| Backup/update | Backup verificato, schema3, manifest updater, rollback codice | Ripristino assente; downgrade schema non universale; Finder/Gatekeeper non testabili qui. |
| UX | Design coerente, merge/edit/export dialog | Mancano feedback dettagliati import, selezione massiva, qualità, analytics, navigazione raggruppata. |

## Regole vincolanti

Persona = gruppo reversibile di identità originali; originali e file non vengono riscritti per semplificare. Una partecipazione consolidata/persona/evento è un read-model, non una duplicazione delle fonti. Ordine condiviso non identifica una persona.

Stati: registered, confirmed, absent, cancelled, unknown. Un override amministrativo esplicito prevale sulle fonti; altrimenti confirmed e absent/cancelled insieme producono unknown + conflitto visibile. confirmed prevale su sola iscrizione; nessuna assenza viene inferita da una riga mancante. Ogni override ha operatore locale e storico, e undo solo se non sono intervenute correzioni successive sugli stessi record.

Archivio = rimozione dall'operatività, non dallo storico. include_analytics è un flag separato e reversibile, modificabile con preview. I KPI/ranking usano solo presenze confermate senza conflitto in eventi inclusi. Economia: null non definito, zero gratuito, positivo convenzionale; la spesa non dimostra incassi. Nessun ROI.

Nuovo/ricorrente: prima presenza nell'intero storico incluso, mai nella sola finestra filtrata. Eventi nella stessa data non ordinabili temporalmente: usare il più basso ID per la prima presenza, segnalare granularità a giorno. Ritorno dopo evento richiede data strettamente successiva; finestra configurabile 90 giorni predefinita, coorte recente segnalata. Conversione solo con attestazione esplicita elenco iscritti completo e tutti gli esiti risolti, altrimenti dati insufficienti. Inattività combina giorni dall'ultima presenza e opportunità successive.

Ricerca e filtri precedono ordinamento, Top 50 e paginazione. Filtri personali valutati sullo stesso insieme del periodo/evento/categoria; nuovo/ricorrente usa la storia completa. Export usa lo stesso selettore backend e nessun limite pagina. Viste persistenti nel DB locale.

Dati deboli: email sola valida è importabile senza nome reale; cognome solo distinto e incompleto; solo nome non identifica arbitrariamente. Riga priva di dati utili viene conservata senza persona. Errori isolati sono esclusi dalle partecipazioni ma conservati con motivo. Queste non sono cancellazioni della fonte. Contatori primari: lette = valide + non attribuibili/errori; sottocategorie identità possono sovrapporsi e sono dichiarate.

Nomi separati sono autorevoli per la struttura; nomi completi hanno una suddivisione proposta. Scelte manuali preesistenti prevalgono. Revoca separazione è esplicita e tracciata, non unisce da sola. Merge preview e commit condividono la validazione degli originali; il nome scelto non la aggira.

## Sicurezza / release

Nessuna prova sul DB personale. Migrazioni additive e transazionali con backup verificato; stato originale confrontato dopo aggiornamento. Ripristino: prova su copia, preview dei conteggi, conferma, backup dell'attuale e sostituzione coordinata con accesso DB bloccato. Backup locali da copiare anche fuori macchina per protezione fisica. Un solo pacchetto finale, nessuna release intermedia richiesta.
