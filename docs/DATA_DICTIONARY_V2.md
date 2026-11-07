# Dizionario dati V2

| Entità/campo | Significato e vincoli |
|---|---|
| people | Identità originale immutabile; name può essere vuoto se esiste email valida; campi first_name/last_name e name_structure distinguono struttura importata, proposta, parziale. Nessuna stringa provvisoria UI archiviata come nome. |
| identity_links / decisions | Collegamenti reversibili e storico append-only; separate è indice dei blocchi attivi; revoca ha nuova decisione, non cancella lo storico. deferred_pairs separa rinvio da blocco. |
| profile_edits | Versioni anagrafiche manuali applicabili al gruppo, fonti e alias conservati. |
| events | archived separato da include_analytics; category, edition, registration_complete e valore nullable; cost separato. Nessuna esclusione implicita dello storico per archivio. |
| attendance | Righe per identità/evento di origine, amount in centesimi, cinque stati. Non è il conteggio consolidato. |
| participation_overrides | Correzioni esplicite versionate: membri originali + evento, stato/operatore/batch. Applicazione al read-model corrente senza spostare fonti. |
| bulk_operations | Preview/config/snapshot, conferma e undo tracciati; nessun undo su record successivamente modificati. |
| imports / import_rows | Binari e righe originali; IDs registrazione e ordine come metadati, solo registrazione con contesto evento può supportare deduplica. |
| import_issues | Originale non attribuibile/errori con riga e motivazione, eventuale correzione collegata a persona; mai nome inventato. |
| mapping_templates | Mappature e riga intestazione per formato, salvate esplicitamente; validazione colonne al riuso. |
| saved_views | Filtri JSON validati, nome e data, persistenti nel database. |
| backup previews | File temporaneo privato verificato, hash/token/scadenza; conferma esplicita; snapshot attuale salvato prima del ripristino. |

KPI: persone uniche = gruppi; presenti = gruppi con stato consolidato confirmed; presenze = coppie persona/evento confirmed, non numero righe. Registrazioni residue = registered senza presenza. Assenti/annullati non aumentano ranking o valore. Conflitto confirmed vs absent/cancelled senza override = unknown + conflict. Valore attribuito = somma valori non null per presenze confermate; count null indica subtotale incompleto. Eventi gratuiti valore0 distinti da null. Prima/ultima presenza usa storia inclusa; filtro periodo non ridefinisce la prima presenza storica.

Finestre temporali ISO incluse ai bordi, data riferimento UTC nel calcolo backend salvo parametro esplicito; UI date italiane. Date senza orario non permettono inferenze entro la stessa giornata. Tasso ritorno: tornati entro finestra / presenti all'evento di partenza; nuovi ritornati è una metrica separata. Conversione solo con iscritti completi attestati e esiti noti; denominatore persone iscritte, non file presenti.
