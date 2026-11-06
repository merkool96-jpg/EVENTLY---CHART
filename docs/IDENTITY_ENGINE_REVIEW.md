# Revisione del motore di identificazione

Branch: `fix/evidence-based-identities`.

Il vecchio motore confrontava le lettere dell'intero nominativo; il nuovo confronta nome e cognome separatamente e ammette soltanto evidenze specifiche. Non usa servizi esterni e non cambia schema, partecipazioni o dati economici.

## Evidenze

- Stesso nome esatto e cognome con un solo refuso plausibile: verifica.
- Email personale coincidente e dati compatibili, candidato univoco, nessun conflitto di gruppo né indizio di condivisione: unione automatica.
- Nome e cognome esatti, candidato univoco, nessuna contraddizione: identità presunta.
- Email coincidente con nomi differenti: possibile indirizzo condiviso, soltanto verifica.
- Nome parziale ed email contenente il nome e il cognome del candidato: soltanto verifica e solo con candidato univoco.
- Telefoni coincidenti: evidenza da verificare, senza automatismo.
- Email personali differenti: distinti per impostazione predefinita; unione manuale esplicita possibile, salvo separazioni manuali.
- Alias nominali confermati: validi esclusivamente nel gruppo approvato. Controllo incrociato di tutti i membri prima di ogni nuova unione: nessuna catena tra nomi incompatibili senza identificativi forti o alias confermati.

Le proposte mostrano le identità originali che hanno prodotto l'evidenza, anche quando il rappresentante del gruppo ha un nome diverso. I badge non mostrano più percentuali.

## Ricalcolo e conservazione

Backup SQLite verificato prima della correzione. La coda è una query calcolata: non esiste una tabella di segnalazioni da cancellare. Persone, eventi, partecipazioni, link, storico e separazioni sono stati confrontati riga per riga con il backup e risultano identici.

Database cloud disponibile: **13 identità, 4 eventi, 37 partecipazioni**. Coda precedente **1**, nuova coda **1**, proposte eliminate **0**. La segnalazione demo rimasta ha email coincidente e nome compatibile, quindi resta valida. Non è stato possibile misurare la coda sul Mac dell'utente: i due database non sono sincronizzati.

Nei casi negativi di regressione:

| Coppia | Vecchia somiglianza testuale | Nuova proposta |
|---|---:|---|
| Marco Giacalone / Rocco Giacalone | 86% | Nessuna |
| Arianna Aricò / Marianna Marino | 85% | Nessuna |
| Mario Rossi / Luca Rossi | 63%, già sotto soglia | Nessuna |
| Arianna Rossi / Marianna Rossi | 96% | Nessuna |
| Anna Marino / Marianna Marino | 83% | Nessuna |
| Marianna Marino / Martina Marino | 89% | Nessuna |

Cinque delle sei coppie sarebbero state segnalate dal vecchio algoritmo; nessuna viene segnalata dal nuovo. È un risultato sui casi di test, non un conteggio di dati cancellati nel database reale.

## Verifica

- **51 test superati**: 28 precedenti conservati e 23 regressioni aggiunte. Tutti i casi obbligatori inclusi, più email condivise, ambiguità multiple, alias, originali, separazioni e conflitti tra gruppi.
- Build TypeScript/Vite verificata.
- Browser reale con database temporaneo: motivazioni visibili, nessun badge percentuale, esempi errati assenti, MANTIENI SEPARATI persistente al ricaricamento, UNISCI e annullamento funzionanti, nessun errore JavaScript.

Limiti: confini dei nomi composti non inferibili con certezza da una sola stringa; approccio conservativo che può lasciare distinti duplicati con refusi nel nome proprio. Non vengono annullate retroattivamente unioni già approvate. La modifica del solo motore non sposta persone e non ricalcola i valori tramite nuove fusioni sui dati già esistenti.
