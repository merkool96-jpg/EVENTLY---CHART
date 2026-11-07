# EVENTLY V1.2 — anagrafica ed esportazione

Base verificata `cd075e4`: include `44754b0` (identità), `500a9f1` (colonne) e ottimizzazione delle prestazioni. Branch `feat/profiles-and-participant-export`.

## Risultato

UNISCI permette ora di scegliere il nome da mostrare prima di confermare: due alternative, suggerimento basato su completezza/scelte manuali/ripetizioni e correzione libera con anteprima. Non può superare i blocchi tra identità originali. I campi principali vengono versionati separatamente dalle fonti; successive importazioni non li sovrascrivono. Il profilo permette modifiche anagrafiche, storico e ricerca per alias. I nuovi contatti in conflitto con altri gruppi vengono bloccati; contatti già condivisi restano conservabili senza impedire una correzione del solo nome.

Esporta partecipanti scarica XLSX con Partecipanti, Partecipazioni, Eventi o CSV anagrafico completo. Conteggio e contenuto provengono dal database in sola lettura, oltre Top 50 e limite UI, con filtri su nome/alias/email/telefono. XLSX con date e importi numerici; CSV UTF-8 BOM e separatore italiano. Testi neutralizzati contro formule. Valore convenzionale distinto dalla spesa; valori mancanti segnalati. Date di registrazione e presenze confermate sono distinte.

Schema 3 additivo, backup SQLite verificato prima della migrazione. Database reale confrontato riga per riga con backup: 13 persone, 4 eventi, 37 partecipazioni e decisioni originali conservati.

## Aggiornamento

Lo ZIP del branch include AGGIORNA_EVENTLY.command e update-manifest.json. Nel nuovo ZIP scegliere con Finder la vecchia cartella: verifica del contenuto, rilevamento app attiva, backup SQLite e codice, copia dei soli file applicativi, rollback se la copia fallisce. Database, backup e file locali protetti non vengono sostituiti. Rifiutati percorsi esterni, symlink e formati database più nuovi. Il launcher della vecchia cartella ricompila e applica la migrazione con ulteriore backup. Nessun Git richiesto sul Mac, nessun servizio a pagamento.

## Validazione

- Suite backend/updater completa e build TypeScript/Vite.
- Export oltre 10.000 persone CSV, XLSX oltre 50, eventi filtrati, sicurezza formule, sola lettura.
- Browser: scelta e modifica nome, alias, XLSX/CSV realmente scaricati, mobile, precedenti flussi import/unione/annullamento, ordinamento e prestazioni.
- Aggiornamento completo su una copia temporanea del codice cd075e4 con database schema 2: verifica backup, applicazione della release e primo avvio schema 3 senza alterare le tabelle originali.
- Sintassi shell verificata. Finder, Gatekeeper e doppio clic non sono stati eseguiti su un Mac reale; i test dell'updater sono nel runtime Linux. CI configurata, esito ospitato non ancora verificato.

## Limiti espliciti

L'app resta personale locale, senza autenticazione. I nomi composti non sono interpretati mediante un dizionario: il suggerimento è assistivo e richiede conferma. Le copie Mac/cloud non si sincronizzano. Il CSV contiene il solo foglio anagrafico; usare XLSX per tutti i dettagli. Il ripristino dopo una migrazione richiede codice precedente e una copia del database antecedente, non soltanto il rollback dei file applicativi. La verifica hash del pacchetto rileva alterazioni rispetto al manifest ma non autentica una fonte non attendibile: scaricare da GitHub ufficiale.
