import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Users,
  CalendarDays,
  Trophy,
  GitMerge,
  LayoutDashboard,
  Upload,
  Plus,
  ArrowUpRight,
  ChevronRight,
  X,
  Search,
  Euro,
  Sparkles,
  Check,
  Pencil,
  Trash2,
} from "lucide-react";
import "./style.css";
import { ImportWizard } from "./ImportWizard";
import {
  defaultPeopleSort,
  nextPeopleSort,
  sortPeople,
  sortLabels,
  type PeopleSort,
  type PeopleSortKey,
} from "./peopleSorting";

type Person = {
  id: number;
  name: string;
  email: string;
  phone: string;
  visits: number;
  registrations: number;
  unknown: number;
  value: number;
  actual_spend: number;
  undefined_values: number;
  last_seen: string | null;
  members: Person[];
  incomplete: boolean;
};
type Event = {
  id: number;
  name: string;
  date: string;
  location: string;
  cost: number;
  participant_value_cents: number | null;
  participants: number;
  registrations: number;
  unknown: number;
  actual_spend: number;
  attributed_value: number | null;
  amount?: number;
  status?: string;
  records?: { id: number; person_id: number; status: string }[];
};
type History = {
  id: number;
  action: string;
  a: number;
  b: number;
  link_id: number | null;
  active: number | null;
  reason: string;
  created_at: string;
};
type ImportEntry = {
  id: number;
  filename: string;
  sheet: string;
  status: string;
  created_at: string;
};
type Match = { a: Person; b: Person; evidence: string; reason: string };
type Stats = {
  people: number;
  events: number;
  attributed_value: number;
  undefined_events: number;
  actual_spend: number;
  cost: number;
  attendance: number;
  registrations: number;
  unknown: number;
  returning: number;
  timeline: Event[];
};
const euro = (n: number) =>
  new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(n / 100);
const day = (d: string) =>
  new Date(d + "T12:00:00").toLocaleDateString("it-IT", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
const initials = (s: string) =>
  s
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
async function api(path: string, options: RequestInit = {}) {
  const r = await fetch("/api" + path, options);
  const d = await r.json();
  if (!r.ok)
    throw new Error(
      typeof d.detail === "string" ? d.detail : "Controlla i campi inseriti",
    );
  return d;
}
const json = (body: unknown, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
function App() {
  const [page, setPage] = useState("Dashboard"),
    [people, setPeople] = useState<Person[]>([]),
    [events, setEvents] = useState<Event[]>([]),
    [matches, setMatches] = useState<Match[]>([]),
    [stats, setStats] = useState<Stats | null>(null),
    [query, setQuery] = useState(""),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [modal, setModal] = useState<"event" | "import" | null>(null),
    [edit, setEdit] = useState<Event | null>(null),
    [profile, setProfile] = useState<(Person & { events: Event[] }) | null>(
      null,
    ),
    [target, setTarget] = useState(""),
    [history, setHistory] = useState<History[]>([]),
    [imports, setImports] = useState<ImportEntry[]>([]);
  const dataRequest = useRef(0);
  const reviewRequest = useRef(0);
  async function refresh(scope: "all" | "review" = "all") {
    // Ignore older responses after a newer decision, without blocking the KPI.
    const reviewVersion = ++reviewRequest.current;
    const dataVersion =
      scope === "all" ? ++dataRequest.current : dataRequest.current;
    const load = (
      path: string,
      apply: (data: any) => void,
      kind: "data" | "review",
    ) => {
      const current = () =>
        kind === "data"
          ? dataRequest.current === dataVersion
          : reviewRequest.current === reviewVersion;
      return api(path)
        .then((value) => {
          if (current()) apply(value);
        })
        .catch((error) => {
          if (current()) setError("Aggiornamento incompleto: " + String(error));
        });
    };
    const tasks = [
      load("/matches", setMatches, "review"),
      load("/identity/history", setHistory, "review"),
    ];
    if (scope === "all")
      tasks.push(
        load("/people", setPeople, "data"),
        load("/events", setEvents, "data"),
        load("/dashboard", setStats, "data"),
        load("/imports", setImports, "data"),
      );
    await Promise.all(tasks);
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function act(
    fn: () => Promise<unknown>,
    message: string,
    scope: "all" | "review" = "all",
  ) {
    setBusy(true);
    setError("");
    try {
      await fn();
      if (message) setNotice(message);
      await refresh(scope);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  function openEvent(e: Event | null = null) {
    setEdit(e);
    setModal("event");
  }
  async function showProfile(p: Person) {
    try {
      setProfile(await api("/people/" + p.id));
    } catch (e) {
      setError(String(e));
    }
  }
  const [peopleSort, setPeopleSort] = useState<PeopleSort>(defaultPeopleSort);
  const orderedPeople = sortPeople(people, peopleSort);
  const rankedPeople = orderedPeople.filter((p) => p.visits > 0).slice(0, 50);
  const tablePeople = page === "Top 50" ? rankedPeople : orderedPeople;
  const filtered = tablePeople.filter((p) =>
    (p.name + " " + p.email).toLowerCase().includes(query.toLowerCase()),
  );
  function sortButton(key: PeopleSortKey, label: string) {
    const active = peopleSort.key === key;
    const next = nextPeopleSort(peopleSort, key);
    return (
      <button
        className={"column-sort " + (active ? "selected" : "")}
        aria-label={"Ordina per " + label}
        title={
          "Ordina per " +
          label +
          " in ordine " +
          (next.direction === "asc" ? "crescente" : "decrescente")
        }
        onClick={() => setPeopleSort((current) => nextPeopleSort(current, key))}
      >
        {label}
        <span aria-hidden="true">
          {active ? (peopleSort.direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    );
  }
  function sortHeader(key: PeopleSortKey, label: string) {
    return (
      <th
        aria-sort={
          peopleSort.key === key
            ? peopleSort.direction === "asc"
              ? "ascending"
              : "descending"
            : "none"
        }
      >
        {sortButton(key, label)}
      </th>
    );
  }
  const nav = [
    { icon: LayoutDashboard, label: "Dashboard" },
    { icon: CalendarDays, label: "Eventi" },
    { icon: Users, label: "Partecipanti" },
    { icon: Trophy, label: "Top 50" },
    { icon: GitMerge, label: "Identità" },
  ];
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="#" onClick={() => setPage("Dashboard")}>
          <span className="brand-icon">e</span>
          <span>
            evently<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="workspace">
          <span className="avatar">S</span>
          <div>
            Il mio workspace<small>Piano locale · Gratuito</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {nav.map(({ icon: I, label }) => (
            <button
              aria-label={label}
              key={label}
              className={page === label ? "active" : ""}
              onClick={() => {
                setPage(label);
                setQuery("");
              }}
            >
              <I size={19} />
              <span>{label}</span>
              {label === "Identità" && matches.length > 0 && (
                <b>{matches.length}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="local-card">
          <i className="dot" /> Tutto nel tuo spazio
          <p>I tuoi dati restano nel database locale. Nessun abbonamento.</p>
          <small>SQLite · archiviazione persistente</small>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar">EV</span>
          <div>
            EVENTLY Studio<small>Le persone, al centro.</small>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Workspace <ChevronRight size={13} /> <strong>{page}</strong>
          </span>
          <div>
            <i className="dot" /> Ambiente locale{" "}
            <span className="avatar small">EV</span>
          </div>
        </header>
        <div className="content">
          <div className="page-title">
            <div>
              <p className="eyebrow">IL TUO NETWORK, UNA STORIA ALLA VOLTA</p>
              <h1>{page === "Dashboard" ? "Ogni incontro conta." : page}</h1>
              <p>
                {
                  (
                    {
                      Dashboard:
                        "Una visione chiara dei tuoi eventi e delle persone che li rendono speciali.",
                      Eventi: "Organizza gli incontri. Misura il loro impatto.",
                      Partecipanti:
                        "Conosci le persone, oltre una semplice lista.",
                      "Top 50":
                        "La continuità conta: chi torna ai tuoi eventi, incontro dopo incontro.",
                      Identità:
                        "Un network pulito inizia da identità riconosciute.",
                    } as Record<string, string>
                  )[page]
                }
              </p>
            </div>
            <button
              className="primary"
              onClick={() => {
                setTarget(String(events[0]?.id || ""));
                setModal("import");
              }}
            >
              <Upload size={16} /> Importa partecipanti
            </button>
          </div>
          {error && (
            <div role="alert" className="alert error">
              {error}
              <button aria-label="Chiudi errore" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <Check size={17} />
              {notice}
              <button
                aria-label="Chiudi notifica"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {stats && page === "Dashboard" && (
            <>
              {stats.unknown > 0 && (
                <div className="info-banner">
                  <Check size={22} />
                  <div>
                    <strong>Presenze storiche da verificare</strong>
                    <p>
                      {stats.unknown} partecipazioni V1 non avevano uno stato
                      attendibile. Confermale dai profili: fino ad allora
                      restano escluse da classifica e valore attribuito.
                    </p>
                  </div>
                </div>
              )}
              <div className="metrics">
                {[
                  {
                    label: "Partecipanti unici",
                    value: stats.people,
                    icon: Users,
                    detail: "Persone nel tuo network",
                  },
                  {
                    label: "Eventi realizzati",
                    value: stats.events,
                    icon: CalendarDays,
                    detail: "Connessioni che prendono forma",
                  },
                  {
                    label: "Valore attribuito",
                    value: euro(stats.attributed_value),
                    icon: Euro,
                    detail: `${stats.undefined_events} eventi con valore non definito`,
                  },
                  {
                    label: "Presenze confermate",
                    value: stats.attendance,
                    icon: Sparkles,
                    detail: `${stats.registrations} registrazioni · ${stats.unknown} da verificare`,
                  },
                ].map(({ label, value, icon: I, detail }) => (
                  <section className="metric" key={label}>
                    <div>
                      {label}
                      <I size={17} />
                    </div>
                    <h2>{value}</h2>
                    <small>{detail}</small>
                  </section>
                ))}
              </div>
              <div className="dashboard-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Il valore degli incontri</h3>
                      <p>Valore convenzionale × presenze confermate</p>
                    </div>
                    <span className="tag">Tutti gli eventi</span>
                  </div>
                  <div className="chart">
                    {stats.timeline.length ? (
                      stats.timeline.map((e) => (
                        <div className="bar-column" key={e.id}>
                          <span>
                            {e.attributed_value === null
                              ? "Non definito"
                              : euro(e.attributed_value)}
                          </span>
                          <div
                            className="bar"
                            style={{
                              height: `${Math.max(4, ((e.attributed_value || 0) / Math.max(...stats.timeline.map((x) => x.attributed_value || 0), 1)) * 160)}px`,
                            }}
                          />
                          <small>
                            {new Date(e.date).toLocaleDateString("it-IT", {
                              month: "short",
                            })}
                          </small>
                        </div>
                      ))
                    ) : (
                      <Empty text="Il tuo prossimo evento è l’inizio di una bella storia." />
                    )}
                  </div>
                  <div className="chart-footer">
                    <span>
                      <i /> Valore attribuito
                    </span>
                    <span>
                      Spesa riportata{" "}
                      <strong>{euro(stats.actual_spend)}</strong>
                    </span>
                  </div>
                </section>
                <section className="panel spotlight">
                  <span className="tag">PERSONE CHE FANNO LA DIFFERENZA</span>
                  <Trophy size={31} />
                  <h3>
                    Il tuo network ha
                    <br />
                    persone speciali.
                  </h3>
                  <p>
                    La classifica premia gli eventi distinti con presenza
                    confermata, senza usare gli importi.
                  </p>
                  {people[0]?.visits > 0 && (
                    <div className="spot-person">
                      <span className="avatar">{initials(people[0].name)}</span>
                      <div>
                        <strong>{people[0].name}</strong>
                        <small>
                          {people[0].visits} eventi · {euro(people[0].value)}
                        </small>
                      </div>
                    </div>
                  )}
                  <button onClick={() => setPage("Top 50")}>
                    Esplora la Top 50 <ArrowUpRight size={17} />
                  </button>
                </section>
              </div>
              <div className="section-heading">
                <div>
                  <h3>Gli ultimi eventi</h3>
                  <p>
                    Esperienze che diventano relazioni. Valori e costi restano
                    distinti.
                  </p>
                </div>
                <button
                  className="text-button"
                  onClick={() => setPage("Eventi")}
                >
                  Tutti gli eventi <ChevronRight size={15} />
                </button>
              </div>
              <div className="event-grid">
                {events.slice(0, 3).map((e, i) => (
                  <EventCard
                    key={e.id}
                    event={e}
                    index={i}
                    onEdit={() => openEvent(e)}
                  />
                ))}
              </div>
              {!events.length && (
                <section className="panel empty">
                  <h3>Benvenuto in EVENTLY</h3>
                  <p>Crea il tuo primo evento o esplora i dati dimostrativi.</p>
                  <button
                    disabled={busy}
                    className="primary"
                    onClick={() =>
                      act(
                        () => api("/demo", { method: "POST" }),
                        "Dati dimostrativi caricati",
                      )
                    }
                  >
                    Esplora la demo
                  </button>
                </section>
              )}
            </>
          )}
          {page === "Eventi" && (
            <>
              <div className="toolbar">
                <span>{events.length} eventi nel tuo calendario</span>
                <button className="primary" onClick={() => openEvent()}>
                  <Plus size={16} /> Nuovo evento
                </button>
              </div>
              <div className="event-grid">
                {events.map((e, i) => (
                  <div key={e.id}>
                    <EventCard
                      event={e}
                      index={i}
                      onEdit={() => openEvent(e)}
                    />
                    <div className="event-actions">
                      <button
                        onClick={() => {
                          setTarget(String(e.id));
                          setModal("import");
                        }}
                      >
                        <Upload size={14} /> Importa
                      </button>
                      <button onClick={() => openEvent(e)}>
                        <Pencil size={14} /> Modifica
                      </button>
                      <button
                        aria-label={"Elimina " + e.name}
                        onClick={() => {
                          if (
                            confirm(
                              "Archiviare questo evento? I dati originali saranno conservati.",
                            )
                          )
                            void act(
                              () =>
                                api("/events/" + e.id, { method: "DELETE" }),
                              "Evento archiviato",
                            );
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {!events.length && <Empty text="Crea un evento per iniziare." />}
            </>
          )}
          {page === "Top 50" && (
            <div className="podium">
              {rankedPeople.slice(0, 3).map((p, i) => (
                <button
                  key={p.id}
                  className="panel podium-card"
                  onClick={() => showProfile(p)}
                >
                  <span className="rank-number">0{i + 1}</span>
                  <span className="avatar">{initials(p.name)}</span>
                  <h3>{p.name}</h3>
                  <strong>{p.visits} presenze</strong>
                  <small>
                    {p.last_seen ? day(p.last_seen) : "—"} · {euro(p.value)}{" "}
                    attribuiti
                  </small>
                </button>
              ))}
            </div>
          )}
          {(page === "Partecipanti" || page === "Top 50") && (
            <section className="panel">
              <div className="table-toolbar">
                <div>
                  <h3>
                    {page === "Top 50"
                      ? "La classifica del tuo network"
                      : "Tutte le persone"}
                  </h3>
                  <p>
                    {tablePeople.length} profili · {sortLabels[peopleSort.key]}{" "}
                    {peopleSort.direction === "asc"
                      ? "↑ crescente"
                      : "↓ decrescente"}
                    {page === "Top 50"
                      ? " · prime 50 ricalcolate sulla colonna scelta"
                      : ""}
                  </p>
                </div>
                <div className="search">
                  <Search size={16} />
                  <input
                    aria-label="Cerca partecipante"
                    placeholder="Cerca nome o email…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
              </div>
              <div className="sort-toolbar">
                <span>
                  Clicca una colonna per ordinare; clicca di nuovo per
                  invertire.
                </span>
                <button
                  className="text-button"
                  onClick={() => setPeopleSort(defaultPeopleSort)}
                >
                  Ripristina classifica per presenze
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      {sortHeader("name", "Partecipante")}
                      <th
                        aria-sort={
                          ["visits", "registrations"].includes(peopleSort.key)
                            ? peopleSort.direction === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        <div className="split-sort">
                          {sortButton("visits", "Presenze")}
                          <span>/</span>
                          {sortButton("registrations", "Registrazioni")}
                        </div>
                      </th>
                      {sortHeader("value", "Valore attribuito")}
                      {sortHeader("last_seen", "Ultimo incontro")}
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered
                      .filter((p) => page !== "Top 50" || p.visits > 0)
                      .slice(0, page === "Top 50" ? 50 : 10000)
                      .map((p, i) => (
                        <tr
                          key={p.id}
                          onClick={() => showProfile(p)}
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void showProfile(p);
                          }}
                        >
                          <td>{i + 1}</td>
                          <td>
                            <div className="person-cell">
                              <span className={"avatar tone-" + (i % 4)}>
                                {initials(p.name)}
                              </span>
                              <div>
                                <strong>{p.name}</strong>
                                {p.incomplete && (
                                  <small>Profilo incompleto</small>
                                )}
                                <small>
                                  {p.email || "Email non disponibile"}
                                </small>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="tag">{p.visits} presenze</span>
                            <small>
                              {p.registrations} registrazioni · {p.unknown} da
                              verificare
                            </small>
                          </td>
                          <td>
                            <strong>{euro(p.value)}</strong>
                            {p.undefined_values > 0 && (
                              <small>
                                {p.undefined_values} valori non definiti
                              </small>
                            )}
                          </td>
                          <td>{p.last_seen ? day(p.last_seen) : "—"}</td>
                          <td>
                            <ChevronRight size={16} />
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {!filtered.filter((p) => page !== "Top 50" || p.visits > 0)
                .length && (
                <Empty
                  text={
                    page === "Top 50"
                      ? "Nessuna presenza confermata. Le semplici registrazioni non entrano in classifica."
                      : "Nessun partecipante trovato."
                  }
                />
              )}
            </section>
          )}
          {page === "Identità" && (
            <>
              <div className="info-banner">
                <GitMerge size={22} />
                <div>
                  <strong>
                    Tu conosci le persone. EVENTLY trova le somiglianze.
                  </strong>
                  <p>
                    Le unioni automatiche e manuali sono reversibili. Le
                    decisioni MANTIENI SEPARATI valgono per tutti i membri dei
                    gruppi e bloccano nuove unioni in conflitto.
                  </p>
                </div>
              </div>
              {matches.map((m) => (
                <section key={m.a.id + "-" + m.b.id} className="panel match">
                  <div className="match-top">
                    <span className="tag">
                      Da verificare · evidenza specifica
                    </span>
                    <span>{m.reason}</span>
                  </div>
                  <div className="match-people">
                    {[m.a, m.b].map((p) => (
                      <div key={p.id}>
                        <span className="avatar">{initials(p.name)}</span>
                        <h3>{p.name}</h3>
                        <p>{p.email || "Nessuna email"}</p>
                        <small>{p.phone || "Nessun telefono"}</small>
                      </div>
                    ))}
                  </div>
                  <div className="match-actions">
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(
                          () =>
                            api(
                              "/matches/decision",
                              json({
                                a: m.a.id,
                                b: m.b.id,
                                action: "separate",
                              }),
                            ),
                          "Identità mantenute separate",
                          "review",
                        )
                      }
                    >
                      Mantieni separati
                    </button>
                    <button
                      disabled={busy}
                      className="primary"
                      onClick={() => {
                        if (
                          confirm(
                            "Unire questi gruppi? Le identità originali saranno conservate. Potrai annullare l’unione dallo storico.",
                          )
                        )
                          void act(
                            () =>
                              api(
                                "/matches/decision",
                                json({ a: m.a.id, b: m.b.id, action: "merge" }),
                              ),
                            "Profili uniti",
                          );
                      }}
                    >
                      <GitMerge size={16} /> Unisci
                    </button>
                  </div>
                </section>
              ))}
              {!matches.length && (
                <section className="panel empty">
                  <Check size={30} />
                  <h3>Nessuna ambiguità da verificare</h3>
                  <p>Nessuna identità simile da verificare.</p>
                </section>
              )}
              <section className="panel history-panel">
                <h3>Storico decisioni</h3>
                <p>
                  Le unioni precedenti alla V1.1 non sono ricostruibili senza
                  una fonte o un backup. Gli alias legacy non equivalgono a
                  registrazioni originali.
                </p>
                {history.length ? (
                  history.slice(0, 100).map((h) => (
                    <div className="history-row" key={h.id}>
                      <div>
                        <strong>
                          {h.action === "merge"
                            ? "Unione"
                            : h.action === "undo"
                              ? "Annullamento"
                              : h.action === "override_automatic_exclusion"
                                ? "Superamento esclusione automatica"
                                : h.action === "split"
                                  ? "Separazione"
                                  : "Mantieni separati"}{" "}
                          · #{h.a}
                          {h.b ? " / #" + h.b : ""}
                        </strong>
                        <small>
                          {h.reason} · {h.created_at} UTC
                        </small>
                      </div>
                      {h.action === "merge" && h.active === 1 && (
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() =>
                            act(
                              () =>
                                api("/identity/links/" + h.link_id + "/undo", {
                                  method: "POST",
                                }),
                              "Unione annullata. Classifica aggiornata.",
                            )
                          }
                        >
                          Annulla unione
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  <Empty text="Le prossime decisioni saranno registrate qui." />
                )}
              </section>
              <section className="panel history-panel">
                <h3>Importazioni e fonti originali</h3>
                {imports.map((i) => (
                  <div className="history-row" key={i.id}>
                    <div>
                      <strong>{i.filename}</strong>
                      <small>
                        {i.sheet} ·{" "}
                        {i.status === "confirmed"
                          ? "Presenze"
                          : "Registrazioni"}{" "}
                        · {i.created_at} UTC
                      </small>
                    </div>
                    <a href={"/api/imports/" + i.id + "/original"} download>
                      Scarica originale
                    </a>
                  </div>
                ))}
              </section>
            </>
          )}
          <footer>
            EVENTLY <span>Fatto per connettere. Progettato per durare.</span>
            <span>100% locale · Nessun servizio a pagamento</span>
          </footer>
        </div>
      </main>
      {modal && (
        <div className="overlay">
          <section
            className={"dialog " + (modal === "import" ? "wide-dialog" : "")}
            role="dialog"
            aria-modal="true"
            aria-label={modal === "event" ? "Evento" : "Importazione"}
          >
            <button
              className="close"
              aria-label="Chiudi"
              onClick={() => setModal(null)}
            >
              <X />
            </button>
            {modal === "event" ? (
              <>
                <h2>{edit ? "Modifica evento" : "Un nuovo incontro"}</h2>
                <p>
                  Il valore per partecipante è convenzionale: non è un prezzo né
                  un ricavo.
                </p>
                {error && (
                  <div role="alert" className="alert error">
                    {error}
                  </div>
                )}
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    const value = String(f.get("participant_value") || "");
                    const ok = await act(
                      () =>
                        api(
                          "/events" + (edit ? "/" + edit.id : ""),
                          json(
                            {
                              name: f.get("name"),
                              date: f.get("date"),
                              location: f.get("location"),
                              cost: Math.round(Number(f.get("cost")) * 100),
                              participant_value_cents:
                                value === ""
                                  ? null
                                  : Math.round(Number(value) * 100),
                            },
                            edit ? "PUT" : "POST",
                          ),
                        ),
                      "Evento salvato. Valori attribuiti ricalcolati.",
                    );
                    if (ok) setModal(null);
                  }}
                >
                  <label>
                    Nome evento
                    <input
                      name="name"
                      required
                      maxLength={200}
                      defaultValue={edit?.name}
                    />
                  </label>
                  <label>
                    Data
                    <input
                      type="date"
                      name="date"
                      required
                      defaultValue={edit?.date}
                    />
                  </label>
                  <label>
                    Luogo
                    <input name="location" defaultValue={edit?.location} />
                  </label>
                  <label>
                    Valore per presenza confermata (€)
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      name="participant_value"
                      placeholder="Non definito"
                      defaultValue={
                        edit?.participant_value_cents == null
                          ? ""
                          : edit.participant_value_cents / 100
                      }
                    />
                    <small>
                      Vuoto = non definito · 0 = gratuito · positivo = valore
                      attribuito
                    </small>
                  </label>
                  <label>
                    Costo organizzativo (€)
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      name="cost"
                      required
                      defaultValue={(edit?.cost || 0) / 100}
                    />
                  </label>
                  <button disabled={busy} className="primary">
                    {busy ? "Salvataggio…" : "Salva evento"}
                  </button>
                </form>
              </>
            ) : (
              <ImportWizard
                events={events}
                initialEvent={target}
                onCreate={() => openEvent()}
                onDone={(message) => {
                  setNotice(message);
                  setModal(null);
                  void refresh();
                }}
              />
            )}
          </section>
        </div>
      )}
      {profile && (
        <div className="overlay">
          <section
            className="dialog wide-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Profilo partecipante"
          >
            <button
              className="close"
              aria-label="Chiudi"
              onClick={() => setProfile(null)}
            >
              <X />
            </button>
            <span className="avatar large">{initials(profile.name)}</span>
            <h2>{profile.name}</h2>
            <p>
              {profile.email} {profile.phone && "· " + profile.phone}
            </p>
            {error && (
              <div role="alert" className="alert error">
                {error}
              </div>
            )}
            <div className="profile-stats">
              <div>
                <small>Eventi con presenza confermata</small>
                <h2>{profile.visits}</h2>
              </div>
              <div>
                <small>Valore attribuito</small>
                <h2>{euro(profile.value)}</h2>
                <small>
                  {profile.undefined_values} eventi con valore non definito
                </small>
              </div>
            </div>
            <p>
              Spesa riportata: {euro(profile.actual_spend)} · Registrazioni:{" "}
              {profile.registrations} · Da verificare: {profile.unknown}
            </p>
            <h3>Identità originali del gruppo</h3>
            {profile.members.map((member) => (
              <div className="history-row" key={member.id}>
                <div>
                  <strong>
                    #{member.id} · {member.name}
                  </strong>
                  <small>
                    {member.email || "Email assente"} ·{" "}
                    {member.phone || "Telefono assente"}
                  </small>
                </div>
                {profile.members.length > 1 && (
                  <button
                    disabled={busy}
                    onClick={async () => {
                      if (
                        confirm(
                          "Separare questa identità dal gruppo? Le sue righe originali resteranno collegate e il blocco sarà permanente.",
                        )
                      ) {
                        const ok = await act(
                          () =>
                            api("/identity/" + member.id + "/split", {
                              method: "POST",
                            }),
                          "Identità separata. Classifica aggiornata.",
                        );
                        if (ok) setProfile(null);
                      }
                    }}
                  >
                    Separa identità
                  </button>
                )}
              </div>
            ))}
            <h3 className="profile-subtitle">La storia degli incontri</h3>
            {profile.events.map((e) => (
              <div className="profile-event" key={e.id}>
                <div>
                  <strong>{e.name}</strong>
                  <small>
                    {day(e.date)} · {e.location}
                  </small>
                  <span className={"status-pill " + e.status}>
                    {e.status === "confirmed"
                      ? "Presenza confermata"
                      : e.status === "registered"
                        ? "Registrazione"
                        : "Da verificare · dato V1"}
                  </span>
                  <small>
                    Valore attribuito:{" "}
                    {e.attributed_value === null
                      ? "non definito"
                      : euro(e.attributed_value || 0)}{" "}
                    · Spesa riportata: {euro(e.amount || 0)}
                  </small>
                  {e.records?.map((record) => (
                    <label className="status-control" key={record.id}>
                      Stato identità #{record.person_id}
                      <select
                        aria-label={"Stato registrazione " + record.id}
                        disabled={busy}
                        value={record.status}
                        onChange={async (ev) => {
                          const ok = await act(
                            () =>
                              api(
                                "/attendance/" + record.id,
                                json({ status: ev.target.value }, "PATCH"),
                              ),
                            "Stato aggiornato",
                          );
                          if (ok) await showProfile(profile);
                        }}
                      >
                        <option value="registered">Registrazione</option>
                        <option value="confirmed">Presenza confermata</option>
                        <option value="unknown">Da verificare</option>
                      </select>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {!profile.events.length && <p>Nessuna partecipazione.</p>}
          </section>
        </div>
      )}
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <Users size={26} />
      <p>{text}</p>
    </div>
  );
}
function EventCard({
  event: e,
  index,
  onEdit,
}: {
  event: Event;
  index: number;
  onEdit: () => void;
}) {
  return (
    <article className="event-card">
      <button className={"event-cover cover-" + (index % 3)} onClick={onEdit}>
        <span className="cover-orbit" />
        <span className="cover-caption">EVENTLY EXPERIENCES</span>
        <span className="cover-title">{e.name}</span>
        <ArrowUpRight size={23} />
      </button>
      <div className="event-body">
        <span className="event-date">{day(e.date)}</span>
        <h3>{e.name}</h3>
        <p>{e.location || "Luogo da definire"}</p>
        <div>
          <span>
            <Users size={14} /> {e.participants} presenze
          </span>
          <strong>
            {e.attributed_value === null
              ? "Non definito"
              : euro(e.attributed_value)}
          </strong>
        </div>
        <small>
          {e.registrations} registrazioni · {e.unknown} da verificare
        </small>
        <small>
          Valore per presenza:{" "}
          {e.participant_value_cents === null
            ? "non definito"
            : euro(e.participant_value_cents)}{" "}
          · Costo: {euro(e.cost)}
        </small>
      </div>
    </article>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
