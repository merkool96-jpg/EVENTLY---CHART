import { useState, useEffect } from "react";
import { X, Check, Download } from "lucide-react";
export type Details = {
  first_name: string;
  last_name: string;
  display_name: string;
  email: string;
  phone: string;
};
type Option = Details & { name: string };
async function request(path: string, method = "GET", data?: unknown) {
  const r = await fetch("/api" + path, {
    method,
    headers: data ? { "Content-Type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined,
  });
  const value = await r.json();
  if (!r.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : "Controlla i campi inseriti",
    );
  return value;
}
function Frame({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="overlay">
      <section
        className="dialog wide-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <button
          className="close"
          aria-label="Chiudi finestra"
          onClick={onClose}
        >
          <X />
        </button>
        <h2>{title}</h2>
        {children}
      </section>
    </div>
  );
}
function Fields({
  value,
  onChange,
}: {
  value: Details;
  onChange: (value: Details) => void;
}) {
  return (
    <div className="mapping-grid">
      {(
        [
          ["first_name", "Nome principale"],
          ["last_name", "Cognome principale"],
          ["display_name", "Nominativo visualizzato"],
          ["email", "Email principale"],
          ["phone", "Telefono principale"],
        ] as const
      ).map(([key, label]) => (
        <label key={key}>
          {label}
          <input
            aria-label={label}
            required={key === "first_name" || key === "display_name"}
            maxLength={
              key === "display_name" ? 300 : key === "phone" ? 50 : 254
            }
            type={key === "email" ? "email" : "text"}
            value={value[key]}
            onChange={(e) => onChange({ ...value, [key]: e.target.value })}
          />
        </label>
      ))}
    </div>
  );
}
export function MergeDialog({
  a,
  b,
  onClose,
  onDone,
}: {
  a: number;
  b: number;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [info, setInfo] = useState<{
      options: Option[];
      recommended: Details & { reason: string };
      members: number;
    } | null>(null),
    [value, setValue] = useState<Details | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    request("/matches/preview", "POST", { a, b })
      .then((data) => {
        if (alive) {
          setInfo(data);
          setValue(data.recommended);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [a, b]);
  return (
    <Frame title="Scegli il profilo risultante" onClose={onClose}>
      <p>
        Le identità originali e gli alias restano conservati. Conferma il
        nominativo da mostrare.
      </p>
      {error && (
        <div role="alert" className="alert error">
          {error}
        </div>
      )}
      {info && value ? (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await request("/matches/decision", "POST", {
                a,
                b,
                action: "merge",
                profile: value,
              });
              onDone("Profili uniti. Nominativo principale salvato.");
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="name-options">
            {info.options.map((p, i) => (
              <button
                type="button"
                key={i}
                onClick={() =>
                  setValue({
                    first_name: p.first_name,
                    last_name: p.last_name,
                    display_name: p.name,
                    email: value.email,
                    phone: value.phone,
                  })
                }
              >
                <small>
                  {i === 0 ? "Primo nominativo" : "Secondo nominativo"}
                </small>
                <strong>{p.name}</strong>
              </button>
            ))}
            <button
              type="button"
              className="recommended"
              onClick={() => setValue(info.recommended)}
            >
              <small>Consigliato dal sistema</small>
              <strong>{info.recommended.display_name}</strong>
            </button>
          </div>
          <p className="hint">
            {info.recommended.reason} Puoi correggere liberamente i campi qui
            sotto.
          </p>
          <Fields value={value} onChange={setValue} />
          <div className="profile-preview">
            <small>ANTEPRIMA · {info.members} identità originali</small>
            <h3>{value.display_name}</h3>
            <p>
              {value.first_name} {value.last_name}
              <br />
              {value.email || "Email non disponibile"} ·{" "}
              {value.phone || "Telefono non disponibile"}
            </p>
          </div>
          <button disabled={busy} className="primary">
            <Check size={16} />
            {busy ? "Unione…" : "Conferma unione"}
          </button>
        </form>
      ) : (
        !error && <p role="status">Controllo dei profili e dei conflitti…</p>
      )}
    </Frame>
  );
}
export function EditPersonDialog({
  person,
  onClose,
  onDone,
}: {
  person: Omit<Details, "display_name"> & { id: number; name: string };
  onClose: () => void;
  onDone: () => void;
}) {
  const [value, setValue] = useState<Details>({
      ...person,
      display_name: person.name,
    }),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState<
      { id: number; display_name: string; reason: string; created_at: string }[]
    >([]);
  useEffect(() => {
    request("/people/" + person.id + "/history")
      .then(setHistory)
      .catch((e) => setError(e.message));
  }, [person.id]);
  return (
    <Frame title="Modifica anagrafica" onClose={onClose}>
      <p>
        Salva i dati principali senza cancellare quelli importati. Le precedenti
        versioni resteranno nello storico.
      </p>
      {error && (
        <div role="alert" className="alert error">
          {error}
        </div>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await request("/people/" + person.id, "PATCH", value);
            onDone();
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Fields value={value} onChange={setValue} />
        <button disabled={busy} className="primary">
          {busy ? "Salvataggio…" : "Salva anagrafica"}
        </button>
      </form>
      <details className="profile-subtitle">
        <summary>Storico anagrafica ({history.length})</summary>
        {history.map((h) => (
          <p key={h.id}>
            <strong>{h.display_name}</strong>
            <br />
            {h.reason} · {h.created_at} UTC
          </p>
        ))}
      </details>
    </Frame>
  );
}
export function ExportDialog({
  query,
  onClose,
  onDone,
}: {
  query: string;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [format, setFormat] = useState("xlsx"),
    [scope, setScope] = useState("all"),
    [count, setCount] = useState<number | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const q = scope === "filtered" ? query : "";
  useEffect(() => {
    let alive = true;
    setCount(null);
    setError("");
    request("/exports/count?q=" + encodeURIComponent(q))
      .then((d) => {
        if (alive) setCount(d.count);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [q]);
  return (
    <Frame title="Esporta partecipanti" onClose={onClose}>
      <p>
        Scarica i dati aggiornati dal database, senza limiti di classifica o
        righe visibili.
      </p>
      {error && (
        <div role="alert" className="alert error">
          {error}
        </div>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const r = await fetch(
              "/api/exports/participants?format=" +
                format +
                "&q=" +
                encodeURIComponent(q),
            );
            if (!r.ok) throw Error("Esportazione non riuscita. Riprova.");
            const blob = await r.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "EVENTLY-partecipanti." + format;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            onDone(
              "File di esportazione pronto. Controlla la cartella Download.",
            );
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Formato file
          <select
            aria-label="Formato file"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option value="xlsx">XLSX · consigliato, tre fogli</option>
            <option value="csv">CSV · elenco partecipanti</option>
          </select>
        </label>
        <label>
          Ambito dei dati
          <select
            aria-label="Ambito dei dati"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="all">Tutti i partecipanti</option>
            <option value="filtered">
              Solo i filtri attivi{query ? " · " + query : " · nessun filtro"}
            </option>
          </select>
        </label>
        <div className="profile-preview">
          <small>PARTECIPANTI INCLUSI</small>
          <h2>{count === null ? "…" : count}</h2>
          <p>
            {format === "xlsx"
              ? "Tre fogli: Partecipanti, Partecipazioni ed Eventi."
              : "Un file CSV UTF-8 con tutti i campi dell’anagrafica partecipanti."}{" "}
            Gli importi sono valori attribuiti, non spese reali.
          </p>
        </div>
        <button disabled={busy || count === null} className="primary">
          <Download size={16} />
          {busy ? "Preparazione…" : "Scarica file"}
        </button>
      </form>
    </Frame>
  );
}
