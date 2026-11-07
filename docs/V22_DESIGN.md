# EVENTLY V2.2 — progetto preventivo

Base verificata prima del codice: tag v2.1.0/0782247, anche dopo fetch remoto. Branch feat/evently-v2.2. Nessuna installazione sul Mac o prova sui DB allegati: soltanto archivi temporanei sintetici.

## A. Audit

V2.1: import XLSX/XLS/CSV, originali, cinque stati consolidati, anagrafiche, gruppi reversibili, ranking/search/export comuni, archivio distinto da esclusione, segmenti filtro, bulk presenze, analytics e backup/updater funzionanti. Riutilizzare people_report/select_people, consolidamento, identità, filtri e layout. Mancano CRM manuale, segmenti configurabili, premi, report PDF e comparazioni temporali mature. Il ritorno V2.1 usa una sola finestra e segnala coorte recente, ma non distingue zero da mancanza di opportunità. La prima presenza a pari data usa un ID arbitrario: nella V2.2 gli eventi della stessa prima data sono indicati come esordio conosciuto nella giornata; nessun ordine temporale viene dedotto.

## B. Flussi UX

| Percorso | Azioni/risultato | Attesa, errore, conferma e recupero |
|---|---|---|
| Segmenti | Card dinamica → elenco con criterio esplicito → filtri aggiuntivi → selezione/export | Skeleton, criteri validati, nessuna copia permanente dei membri; stessa query per conteggi e download |
| VIP | Candidati trasparenti → pagina o tutti risultati → anteprima numero → conferma manuale | VIP non automatico; riepilogo e undo se niente è cambiato su origine/stato; errore stale chiede nuova anteprima |
| Tag | Crea/rinomina/archivia → selezione persone in DB/Top50/segmento → applica/rimuovi → anteprima/conferma | Nome normalizzato univoco, VIP riservato; transazione e audit, undo sicuro |
| Note | Profilo → testo semplice → crea/modifica/elimina con conferma → storico | Nessun effetto sulle metriche, delete logico, versioni/audit; non esportate di default |
| Premi | Campagna/tipo/data/stato → gruppo selezionato → controllo duplicati → escludi o eccezione motivata → conferma | Proposto distinto da assegnato; nessun premio automatico, nessun effetto sul valore delle presenze, audit |
| Separazione | Undo identità esistente → origini singole tornano al proprietario; elementi di gruppo ambigui → coda riassegnazione | Nessuna copia/cancellazione; assegnazione esplicita a un'identità originale, motivazione e audit |
| Post evento | Workspace → Performance → finestre30/60/90/180 → confronto → Genera report PDF/XLSX | Dati insufficienti/assenza opportunità dichiarati; report snapshot con ora e metodo; nessun servizio esterno |
| Liste | Filtri/segmento/VIP/tag/premio/selezione → anteprima persone/email/campi → download | XLSX/CSV senza limite pagina; note e premi solo se richiesti esplicitamente, formule neutralizzate |

Ogni nuova area offre stato vuoto, caricamento, errore leggibile e ritorno/chiusura. Sidebar: Community raggruppa partecipanti/classifica/segmenti/VIP; Analytics riusa analytics e aggiunge performance, report dentro evento. Nessun invito/RSVP/check-in/invio email.

## C. Modello dati / integrità

Schema5 additivo, backup SQLite verificato prima dell'upgrade, transazione DDL e integrità/FK finali. Nessuna riscrittura delle fonti originali.

- crm_tags: ID, nome/nome_normalizzato univoco (maiuscole/accenti/spazi ignorati), colore, descrizione, archivio. Il nome VIP è riservato: esiste un solo stato VIP, mai un tag VIP.
- crm_campaigns: iniziativa con nome normalizzato univoco e archivio.
- crm_records: ID stabile, tipo vip/tag/note/reward, scope JSON degli ID originali al momento dell'azione, payload, FK tag/campagna/evento facoltative, attivo, autore/date. Pre-unione scope singolo; operazione su gruppo scope intero. Il proprietario corrente si deriva dal gruppo identità: se lo scope ora attraversa più gruppi, il record è ambiguo e non viene duplicato. In coda fino a riassegnazione esplicita. Note/premi mantengono ID/autore/date/originali e versioni nell'audit.
- crm_record_origins: relazione con FK verso record e persone originali; trigger sincronizzano lo scope JSON validato senza cancellare le fonti.
- events.cost_defined: costo esplicito distinto da zero legacy non documentato; i costi legacy positivi sono riconosciuti come definiti.
- crm_batches: anteprima con snapshot dati+CRM, selezione completa, configurazione, conferma e undo.
- crm_audit: azione, operatore, before/after, record, batch e timestamp append-only; delete logico.
- community_settings: soglie validate; crm_segments: definizioni/filtro salvato, non membership.

VIP = presenza di un record VIP attivo vero risolto al gruppo. Rimozione esplicita disattiva i record VIP visibili al gruppo; non esiste una seconda fonte. Tag di origini diverse sono uniti per ID nella vista ma restano distinti nell'origine per undo. Premi ripetuti dopo merge sono segnalati (persona/campagna/tipo normalizzato), non cancellati. Operazioni massive atomiche, preview stale rifiutata, undo rifiutato dopo cambiamenti pertinenti o mutazione dei gruppi. Nessun aggregato presenze memorizzato permanentemente.

## D. Metriche

- Super Fedeli: >=5 presenze storiche incluse; Abituali: >=3 negli ultimi365 giorni inclusi; Nuovi: prima presenza conosciuta nel periodo selezionato, nessun automatismo su sole iscrizioni; Recupero: >=3 storiche, ultima oltre180 giorni e >=2 eventi inclusi già svolti dopo l'ultima presenza; Valore positivo: >=2 eventi inclusi con valore>0. Soglie configurabili.
- Candidati VIP: >=5 storiche AND >=3 in365 giorni AND ultima entro180 giorni, esclusi VIP già assegnati. Suggerimento, non decisione.
- Segmenti sovrapposti; archivio incluso, esclusione analytics rispettata; nuovo dato/merge/split ricalcola il read-model. Variazioni: confrontare lo stesso criterio a due date di osservazione esplicite (storia conosciuta, non snapshot di ciò che il sistema sapeva allora). Per Nuovi confrontare due periodi contigui della stessa durata. Se impossibile, mostrare non disponibile.
- Ritorno: solo date strettamente successive,30/60/90/180 giorni; denominatore presenti confermati dell'evento. Definitivo soltanto finestra trascorsa e almeno un evento successivo nella finestra nello storico disponibile; non garantisce copertura esterna. Nessuna opportunità → non disponibile, mai giudizio negativo. Recenti → provvisorio, percentuale definitiva non pubblicata.
- Esordio: nessun ordine fra eventi della stessa data; tutti quelli della prima data sono esordio nella giornata. Ricorrente richiede una data precedente.
- Confronto percentuale (b-a)/a solo a diverso da0 e valori definiti; ritorni confrontabili solo con finestre uguali/mature/opportunità. Incremento frequenza: due intervalli consecutivi uguali, confermate, variazione conteggi (non causalità).
- Economia: valore convenzionale, spesa riportata dalle fonti e costo separati. Nessun incasso verificato disponibile; non chiamare la spesa riportata incasso o contabilità completa. Null diverso da gratuito0. Nessun ROI.
- PDF/XLSX dello stesso snapshot letto in transazione: intestazione, riepilogo, distribuzione, ritorni, confronti pertinenti, economia, segmenti, metodologia e data/ora (Europe/Rome). Report non modifica dati e non include note private per default.

## E. Matrice preventiva

| ID | Scenario e risultato atteso |
|---|---|
|1–2|Quinta presenza entra in Super Fedeli; correzione assente esce senza cache obsoleta|
|3|VIP manuale rimane se inattivo|
|4–5|Tag100 oltre pagina, anteprima esatta, conferma atomica e undo; rifiuto stale/successive modifiche|
|6|Merge due origini con tag diversi, unione vista senza perdita|
|7|Undo conserva note/premi origine singola; record aggiunti sul gruppo finiscono in coda, nessuna copia; riassegnazione tracciata|
|8–9|Stessa persona/campagna/tipo avviso; tipo o campagna diversi ammessi; eccezione solo conferma+motivo|
|10|Presente2025 è ricorrente2026|
|11–12|Recente non ha tasso definitivo90; nessun evento successivo segnala assenza opportunità|
|13|Zero e null restano distinti anche nel report|
|14|PDF/XLSX e workspace usano lo stesso payload economico e conteggi|
|15–16|Export selezionato100+/10k, mai limite pagina; note escluse salvo flag esplicito|
|17|Import nuovo aggiorna segmento senza sovrascrivere CRM manuale|
|18|PDF generato localmente, nessuna API esterna, output leggibile/multipagina|
|19|Migrazione4→5 con backup, confronto tutte righe/tabelle legacy, idempotenza e blocco se backup fallisce|
|20|Regressioni V2.1 + browser percorsi segmenti/VIP/tag/note/premi/separazione/performance/report/export;10k sintetici|

Ulteriori: tag normalizzati duplicati/VIP riservato, archiviazione conserva associazioni, note versionate, duplicate postmerge, autor/data invariati, nessuna alterazione presenze da CRM, stesse date, divisione per zero, opportunità future non considerate trascorse, PDF testi non causali, CSV formula injection, backup/restore schema5 e downgrade rifiutato.

## F. Piano / stato

A questo documento prima del codice; B schema5 + migrazione/test; C segmenti/CRM/VIP/tag/note; D premi/duplicati/bulk; E performance/finestre/confronti/insights; F report PDF/XLSX/export; G browser/10k/regressioni/updater/pacchetto unico. Commit progressivi. Documentare esiti reali e limiti, nessuna release intermedia sul Mac.
