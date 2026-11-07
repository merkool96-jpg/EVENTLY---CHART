# EVENTLY V2.2.1 — stabilizzazione post-audit

7 novembre 2026. Base: tag v2.2.0 / 932266a. Branch dedicato: fix/evently-v2.2.1. Nessuna nuova dipendenza, nessuna migrazione (schema5 invariato), nessuna modifica ai dati originali. Prove esclusivamente sintetiche. Audit e regressioni scritti prima della correzione: [AUDIT_V221.md](AUDIT_V221.md).

## Problemi confermati e correzioni

- **Riassegnazione CRM:** riprodotta una richiesta verso una persona estranea con risposta200. Ora l'API accetta solo uno degli ID originali dello scope di un record ancora irrisolto. Essere fuso oggi con uno dei proprietari non rende un estraneo un'identità originale del conflitto. Input validati, motivazione e revisione obbligatori, controllo dentro la stessa transazione; richieste respinte non modificano record, origini o audit. Vale per note, VIP, tag e premi. Una coda divenuta obsoleta per un'altra unione non consente spostamenti arbitrari.
- **Blocco durante il rendering:** PDF/XLSX venivano costruiti dentro `with db()`, trattenendo il blocco globale anche durante impaginazione/compressione. Ora il modello completo è materializzato in una sola transazione di lettura; connessione e lock sono rilasciati prima del rendering. Cambiamenti successivi non alterano il report in corso.

## Chiarezza e protezioni preventive

- **Temporalità:** il PDF aveva già un timestamp e una nota generica sui segmenti; intestazioni Excel e frase VIP potevano far pensare a uno stato storico. Ora VIP e segmenti sono esplicitamente riferiti alla generazione, con timestamp e dichiarazione che non viene ricostruito lo stato alla data evento. Nessuna inferenza o modifica retroattiva dei VIP.
- **Privacy:** il PDF era già aggregato; nessuna divulgazione effettiva è stata riscontrata nei test. Mancava però un avviso prima del dettaglio Excel. Ora una finestra distingue i formati e spiega nominativi/email, esclusione delle note e condivisione autorizzata. Annullare non invia richieste di generazione né scarica file. Filename, prima riga e proprietà del documento Excel indicano DATI PERSONALI. Il dettaglio completo resta disponibile.
- **Reversibilità:** l'ultima riassegnazione può essere annullata esplicitamente prima di modifiche successive al record. Si ripristina lo scope precedente, si incrementa la revisione e si aggiunge un audit; non si cancella lo storico. Nessuna duplicazione di note/premi. Il comando compare dopo la riassegnazione; l'API rifiuta revisioni obsolete e annullamenti ripetuti.

## Verifiche

- **129 test backend passati**, inclusi18 nuovi casi parametrizzati: quattro tipi CRM × estranei/undo, identificativi invalidi, nuova unione che risolve il conflitto, etichette e privacy, due prove concorrenti PDF/XLSX su10.000 persone. Un solo avviso di deprecazione interno Starlette/AnyIO, nessun errore.
- La regressione CRM è stata eseguita prima della correzione: falliva perché l'API restituiva200 all'estraneo, dimostrando il difetto.
- Nelle prove concorrenti il renderer è fermato con una barriera: una scrittura e una lettura completano mentre è sospeso. Il report conserva10.000 presenze, mentre il database aggiornato ne mostra9.999. Nessuna soglia arbitraria per il tempo di generazione.
- Build TypeScript/Vite riuscita. Test browser HTTP/Chromium reali: percorsi V2.2 completi, tentativo API estraneo respinto, undo/nuova riassegnazione, avviso Excel anche mobile, annullamento senza richiesta, download consentito, PDF/XLSX, navigazione e controllo errori JavaScript.
- Regressioni browser: import a7 passi, profili/alias/unioni, ordinamento globale Top50, grafico Valore/Presenze, aggiornamento KPI, eventi e backup. Contrasto del testo visibile campionato:1.391 coppie nelle nuove pagine e1.221 nel dataset di regressione, nessun errore; non è una certificazione completa di accessibilità.
- Prova browser10.000 profili: ricerca oltre prima pagina,50 righe renderizzate, anteprimaVIP10.000, export10.000 e download dei due report. PDF circa1,42s; XLSX dettagliato circa2,32s. Misure singole sulla macchina cloud, includono rete/browser e non sono p95 né garanzie per il Mac. [Misure grezze](V221_BENCHMARK.json).
- Excel reale aperto con openpyxl:10.000 righe partecipanti, conteggi coerenti e avvisi presenti. PDF reale convertito in testo: etichette temporali presenti, nessuna lista nominativa. Note riservate assenti dai formati standard.

## Backup e pacchetto

Un solo archivio tag v2.2.1, compatibile con AGGIORNA_EVENTLY.command. Manifest SHA256; nessun database/backup personale nel pacchetto. Rehearsal sintetico V2.2/schema5→V2.2.1/schema5 con VIP, tag, nota, premio, iniziativa, audit e decisioni: confronto esatto di tutte le tabelle/righe e backup verificato. Anche V2.1/schema4→V2.2.1/schema5 è verificato: non occorrono installazioni intermedie. L'updater salva codice e database prima di copiare i file. CI aggiornato per ripetere entrambe le prove; risultati locali distinti da GitHub Actions.

## Limiti residui

- La costruzione dello snapshot richiede ancora il lock durante query/calcoli; rendering PDF/XLSX è esterno. Generazioni simultanee usano comunque CPU/memoria locali.
- Non si ricostruisce lo status CRM storico alla data evento. Le presenze/nuovi/ricorrenti derivano dallo storico conosciuto, non da fonti esterne.
- Nessuna correzione automatica di riassegnazioni già fatte nella V2.2: non conosciamo l'intenzione dell'amministratore. Audit e informazioni esistenti sono conservati.
- PDF aggregato non significa anonimizzazione garantita: titolo, luogo e nomi dei segmenti sono testi inseriti dall'utente. Verificare il contenuto prima della condivisione. Excel contiene dati personali; nessun invio automatico.
- Finder/Gatekeeper non sono riproducibili sul Linux del collaudo; launcher e aggiornamento sono verificati su copie temporanee. Nessun accesso al database del Mac o agli allegati reali.

## Aggiornamento semplice sul Mac

1. Scarica e decomprimi il pacchetto unico V2.2.1.
2. Con la vecchia EVENTLY aperta sui tuoi dati, lancia TROVA_EVENTLY.command dal pacchetto nuovo e tieni aperto il Finder sulla cartella individuata.
3. Ferma EVENTLY con Ctrl+C nel suo Terminale.
4. Apri AGGIORNA_EVENTLY.command dal pacchetto nuovo e seleziona la vecchia cartella individuata. Attendi il completamento; i backup vengono creati automaticamente.
5. Riapri AVVIA_EVENTLY.command dalla vecchia cartella (o dal suo alias). Cmd+Maiusc+R nel browser, Impostazioni → EVENTLY V2.2.1.
6. Eventi → apri evento → Genera report XLSX: compare l'avviso. Genera report PDF scarica il riepilogo aggregato.

Non serve spostare database, reimportare file o usare un aggiornamento intermedio. Mantieni un alias del launcher della cartella in uso sulla Scrivania per evitare copie avviate per errore.
