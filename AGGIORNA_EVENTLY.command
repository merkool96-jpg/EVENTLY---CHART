#!/bin/bash
# Avvio locale Mac: nessun servizio a pagamento e nessuna cancellazione dati.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"
python_bin=""
for candidate in python3.14 python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    python_bin="$candidate"
    break
  fi
done
if [ -z "$python_bin" ]; then
  echo "Installa Python 3.12 o successivo da https://www.python.org/downloads/macos/"
  echo "Installa anche Node.js LTS da https://nodejs.org/"
  echo "Poi riapri AVVIA_EVENTLY.command."
  read -r -p "Premi Invio per chiudere. "
  exit 1
fi
"$python_bin" scripts/update.py
result=$?
if [ "$result" -ne 0 ]; then
  read -r -p "Premi Invio per chiudere. "
fi
if [ "$result" -eq 0 ]; then
  read -r -p "Premi Invio per chiudere. "
fi
exit "$result"
