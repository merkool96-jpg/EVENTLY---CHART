# EVENTLY V2.2.1 — audit preventivo e piano di stabilizzazione

7 novembre 2026, base tag v2.2.0 / 932266a, branch fix/evently-v2.2.1. Solo database sintetici; nessuna riscrittura, migrazione o dipendenza nuova.

## Riscontri confermati

1. `reassign` controlla esistenza e revisione, ma non lo scope originale né che il record sia realmente irrisolto. Una richiesta diretta può spostare informazioni a un estraneo. Correzione: accettare soltanto gli ID originali nello scope della coda ancora irrisolta, all'interno della stessa transazione di scrittura. Conservare payload, autore e date originali. Revisioni, motivazione e audit obbligatori; annullamento della sola ultima riassegnazione con controllo revisione.
2. PDF ha già un timestamp e una nota sui segmenti alla generazione, ma la frase VIP e i titoli Excel sono ambigui su eventi passati. Rendere esplicito che VIP e segmenti sono attuali alla generazione, senza ricostruzione storica attendibile dello status alla data evento. Presenze/nuovi/ricorrenti restano metriche sull'evento e sullo storico noto.
3. PDF non stampa nominativi/email dei partecipanti; XLSX include un foglio dettagliato ma non ha un avviso preventivo nell'interfaccia. Conservare il dettaglio aggiungendo conferma comprensibile, descrizione di entrambi i formati e dicitura nel file Excel.
4. `pdf(data)`/`xlsx(data)` sono chiamati dentro `with db()`, che mantiene `DB_LOCK`. Creare il modello completo e indipendente in una singola transazione, poi chiudere connessione/rilasciare lock prima della serializzazione. Non cambiare il blocco globale per le altre operazioni.

## Protezioni preventive e test prima del codice

- Regressioni per tutti i quattro tipi CRM, destinatario estraneo (anche fuso con un originale), record risolto, revisione obsoleta, rifiuto senza mutazioni, motivazione e undo senza cancellare audit/provenienza; modifiche successive bloccano undo.
- Evento passato con VIP assegnato oggi: conteggio attuale ed etichette esplicite PDF/XLSX. PDF solo aggregati e note private escluse; Excel conserva dettaglio e avviso.
- Renderer fermato con barriera: letture e scritture parallele devono completare mentre la generazione è sospesa; il documento continua a usare lo snapshot precedente. Verifica PDF e XLSX, database sintetico grande, nessuna soglia di prestazioni dipendente dalla macchina.
- Browser: annullamento/consenso Excel prima di qualsiasi richiesta/download, PDF diretto, undo riassegnazione, messaggi e navigazione V2.2.
- Suite completa, build, regressioni browser e test aggiornamento V2.2→V2.2.1 (schema5 invariato) e V2.1→V2.2.1 (schema4→5), backup codice/database e manifest SHA256.

## Ambito e limiti

Non correggere retroattivamente riassegnazioni già effettuate: non è possibile inferire l'intenzione dell'amministratore. Conservare audit e dati. Lo snapshot richiede ancora il lock durante le letture/calcoli; la creazione del documento ne viene separata. Un PDF aggregato può comunque contenere titolo/luogo evento inseriti dall'utente: non equivale a anonimizzazione garantita. L'autore locale non è autenticazione multiutente.
