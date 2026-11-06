# EVENTLY

Prima versione di un gestionale locale per eventi e partecipanti. React + Vite + TypeScript + Tailwind, API FastAPI e SQLite. Nessuna API esterna, abbonamento, chiave o servizio cloud necessario. Le dipendenze sono gratuite; eventuale hosting e hardware restano a scelta dell’utente.

## Avvio

Prerequisiti: Python 3.12+ e Node.js 22+ con npm.

```bash
./scripts/install.sh
./scripts/start.sh
```

Il frontend di sviluppo usa la porta 5173, con proxy API verso 8000. Per usare la build senza Vite:

```bash
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

FastAPI serve anche il frontend compilato. Documentazione API disponibile sul percorso `/docs`. Il database persistente è `backend/evently.db`, escluso da Git. `EVENTLY_DB` consente un percorso alternativo. Fermare il processo prima di copiare il database per un backup. Il database e i processi non vengono pubblicati su GitHub.

## Funzioni

- Dashboard con persone uniche, eventi, ricorrenza, entrate e margine (entrate meno costi organizzativi).
- Creazione, modifica ed eliminazione eventi; costo in euro nell’interfaccia e centesimi interi nell’API.
- Importazione CSV UTF-8 (virgola, punto e virgola o tab), XLSX e XLS: primo foglio, prima riga come intestazione. Limiti: 10 MB e 20.000 righe; i file di origine non vengono conservati.
- Colonne riconosciute: Nome completo/Nominativo/Partecipante/Full name; Nome/First name e Cognome/Last name; Email/Mail; Telefono/Cellulare/Phone; Importo/Totale/Amount/Valore/Spesa/Pagato. Importo opzionale, predefinito zero. Supportati numeri Excel, `1234.56` e `1.234,56`.
- Identificazione automatica solo per nome normalizzato, email e telefono tutti coincidenti. Una persona partecipa una sola volta a ciascun evento: righe ripetute vengono ignorate, non sommate. Per correggere dati importati in questa versione occorre eliminare e ricreare l’evento.
- Candidati all’unione con stessa email, stesso telefono o somiglianza del nome >=84%. Il punteggio è una regola euristica, non una probabilità. I casi ambigui richiedono conferma.
- **UNISCI** conserva il profilo con ID inferiore, recupera contatti mancanti, mantiene alias dei profili assorbiti, somma importi delle presenze sovrapposte e conserva le esclusioni. L’unione non è annullabile dall’interfaccia: fare un backup prima di operazioni importanti.
- **MANTIENI SEPARATI** salva l’esclusione della coppia anche dopo il riavvio.
- Ricerca partecipanti, profili con storico e Top 50 ordinata per importi, poi numero di eventi.

Premere **Esplora la demo** nella dashboard vuota per caricare quattro eventi e tredici profili fittizi, incluso un duplicato da verificare. Il caricamento demo è esplicito e consentito solo senza eventi. `examples/partecipanti.csv` è un esempio importabile.

## Verifica

```bash
.venv/bin/python -m pytest backend/tests -v
cd frontend
npm run build
npm audit
```

I test usano database temporanei e file reali dei tre formati, verificano persistenza, importazioni ripetute, transazioni atomiche, CRUD, unioni, alias, separazioni e dati demo.

## Ambito della prima versione

Il prompt precedente non era presente nella conversazione disponibile: questa versione implementa i requisiti espliciti elencati. Il valore economico è l’importo associato alla partecipazione, non una previsione di valore futuro. Non sono presenti pagamenti, invio email o servizi a consumo.

Applicazione personale locale, senza autenticazione o multiutenza: tenere l’API su loopback e non esporla pubblicamente. Il confronto dei candidati è quadratico e adatto a piccoli archivi; vengono visualizzate al massimo 200 coppie. L’elenco partecipanti è limitato a 10.000 profili. Per archivi maggiori servono paginazione, indici di ricerca e un motore di abbinamento a blocchi. CSV con codifiche diverse da UTF-8 richiedono conversione. Conservare i telefoni come testo nei fogli Excel per preservare zeri iniziali.
