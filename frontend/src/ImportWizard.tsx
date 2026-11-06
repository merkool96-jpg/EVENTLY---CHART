import { useState } from "react";
import { Upload, ArrowRight, Check } from "lucide-react";

type EventOption = { id: number; name: string };
type Mapping = Record<string, number | null>;
type Inspection = {
  sheets: string[];
  sheet: string;
  headers: string[];
  mapping: Mapping;
  sample: unknown[][];
};
type Preview = {
  token: string;
  rows: number;
  summary: Record<string, number | boolean>;
  config: { status: string };
  sample: { name: string; email: string; amount: number }[];
};
const fields: Record<string, string> = {
  name: "Nome completo",
  first: "Nome",
  last: "Cognome",
  email: "Email",
  phone: "Telefono",
  amount: "Spesa riportata (€)",
};
async function post(path: string, data?: FormData) {
  const r = await fetch("/api" + path, { method: "POST", body: data });
  const result = await r.json();
  if (!r.ok)
    throw Error(
      typeof result.detail === "string" ? result.detail : "Controlla i campi",
    );
  return result;
}
export function ImportWizard({
  events,
  initialEvent,
  onDone,
  onCreate,
}: {
  events: EventOption[];
  initialEvent: string;
  onDone: (message: string) => void;
  onCreate: () => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [info, setInfo] = useState<Inspection | null>(null),
    [mapping, setMapping] = useState<Mapping>({}),
    [event, setEvent] = useState(initialEvent),
    [status, setStatus] = useState("registered"),
    [preview, setPreview] = useState<Preview | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function execute(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function inspect(selected: File, sheet?: string) {
    const data = new FormData();
    data.append("file", selected);
    if (sheet) data.append("sheet", sheet);
    const result = await post("/imports/inspect", data);
    setInfo(result);
    setMapping(result.mapping);
    setPreview(null);
  }
  if (!events.length)
    return (
      <>
        <h2>Prima, un evento</h2>
        <p>
          Crea un evento per associare le registrazioni al contesto corretto.
        </p>
        <button className="primary" onClick={onCreate}>
          Crea evento
        </button>
      </>
    );
  return (
    <>
      <h2>Importa le tue persone</h2>
      <p>
        Originali conservati. Identità verificabili. Nessuna presenza presunta.
      </p>
      <ol className="wizard-steps">
        <li className={!info ? "current" : ""}>1 · File</li>
        <li className={info && !preview ? "current" : ""}>2 · Mappatura</li>
        <li className={preview ? "current" : ""}>3 · Conferma</li>
      </ol>
      {error && (
        <div role="alert" className="alert error">
          {error}
        </div>
      )}
      {!preview ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void execute(async () => {
              if (!file || !info) throw Error("Seleziona un file");
              const data = new FormData();
              data.append("file", file);
              data.append("event_id", event);
              data.append("status", status);
              data.append("sheet", info.sheet);
              data.append("mapping", JSON.stringify(mapping));
              setPreview(await post("/imports/preview", data));
            });
          }}
        >
          <label className="drop-zone">
            <Upload size={25} />
            <strong>Scegli XLSX, XLS o CSV</strong>
            <span>10 MB · 20.000 righe · CSV UTF-8</span>
            <input
              aria-label="File partecipanti"
              type="file"
              accept=".csv,.xlsx,.xls"
              disabled={busy}
              onChange={(e) => {
                const selected = e.target.files?.[0];
                setInfo(null);
                setPreview(null);
                if (selected) {
                  setFile(selected);
                  void execute(() => inspect(selected));
                }
              }}
            />
          </label>
          {info && (
            <>
              <label>
                Foglio Excel
                <select
                  aria-label="Foglio Excel"
                  disabled={busy}
                  value={info.sheet}
                  onChange={(e) => {
                    if (file) void execute(() => inspect(file, e.target.value));
                  }}
                >
                  {info.sheets.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <div className="mapping-grid">
                {Object.entries(fields).map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <select
                      aria-label={label}
                      value={mapping[key] ?? ""}
                      onChange={(e) =>
                        setMapping({
                          ...mapping,
                          [key]:
                            e.target.value === ""
                              ? null
                              : Number(e.target.value),
                        })
                      }
                    >
                      <option value="">Non importare</option>
                      {info.headers.map((h, i) => (
                        <option key={i} value={i}>
                          {i + 1} · {h || "(senza nome)"}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="table-wrap">
                <table>
                  <caption>Prime righe del foglio originale</caption>
                  <thead>
                    <tr>
                      {info.headers.map((h, i) => (
                        <th key={i}>{h || i + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {info.sample.slice(0, 3).map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j}>{String(cell ?? "")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <label>
            Evento di destinazione
            <select
              aria-label="Evento di destinazione"
              required
              value={event}
              onChange={(e) => setEvent(e.target.value)}
            >
              <option value="">Seleziona evento</option>
              {events.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tipo di elenco
            <select
              aria-label="Tipo di elenco"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="registered">Semplici registrazioni</option>
              <option value="confirmed">Presenze confermate</option>
            </select>
          </label>
          <p className="hint">
            La spesa riportata resta distinta dal valore convenzionale
            dell’evento. Solo le presenze confermate contribuiscono alla
            classifica e al valore attribuito.
          </p>
          <button className="primary" disabled={busy || !info}>
            {busy ? "Analisi…" : "Genera anteprima"}
            <ArrowRight size={15} />
          </button>
        </form>
      ) : (
        <div className="import-preview">
          <h3>Controlla prima di confermare</h3>
          <p>
            {events.find((e) => String(e.id) === event)?.name} · {preview.rows}{" "}
            righe ·{" "}
            {status === "confirmed" ? "Presenze confermate" : "Registrazioni"}
          </p>
          <dl className="summary-grid">
            {[
              ["Nuove righe", "imported"],
              ["Già presenti / duplicati", "skipped"],
              ["Presenze aggiornate", "updated"],
              ["Unioni per email", "automatic"],
              ["Unioni presunte per nome", "presumed"],
              ["Casi ambigui", "ambiguous"],
              ["Profili incompleti", "incomplete"],
            ].map(([label, key]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{Number(preview.summary[key] || 0)}</dd>
              </div>
            ))}
          </dl>
          <p className="hint">
            I duplicati non sommano nuovamente gli importi. Le ambiguità restano
            separate nel Centro Verifica Identità. L’anteprima non ha ancora
            aggiunto partecipanti.
          </p>
          <div className="match-actions">
            <button disabled={busy} onClick={() => setPreview(null)}>
              Torna alla mappatura
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                void execute(async () => {
                  const result = await post(
                    "/imports/" + preview.token + "/confirm",
                  );
                  onDone(
                    `Importazione confermata: ${result.imported} righe aggiunte, ${result.skipped} già presenti, ${result.updated} presenze aggiornate.`,
                  );
                })
              }
            >
              <Check size={16} />
              {busy ? "Salvataggio…" : "Conferma importazione"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
