type EventAttendance = {id: number; name: string; date: string; participants: number};
const number = (value: number) => new Intl.NumberFormat('it-IT').format(value);
const eventDate = (value: string) => new Date(value + 'T00:00:00').toLocaleDateString('it-IT', {day: '2-digit', month: 'short', year: 'numeric'});

export function ParticipantsChart({events}: {events: EventAttendance[]}) {
  const maximum = Math.max(1, ...events.map(event => event.participants));
  const total = events.reduce((sum, event) => sum + event.participants, 0);
  return <section className="panel attendance-panel" aria-labelledby="attendance-chart-title">
    <div className="panel-heading">
      <div><h3 id="attendance-chart-title">I partecipanti agli incontri</h3><p>Persone con presenza confermata per evento</p></div>
      <span className="tag">{events.length} eventi</span>
    </div>
    {events.length ? <>
      <div className="attendance-chart-scroll" tabIndex={0} role="region" aria-label="Grafico partecipanti per evento, scorribile orizzontalmente">
        <ul className="chart attendance-chart" aria-label="Partecipanti confermati per evento">
          {events.map(event => <li className="bar-column" key={event.id} aria-label={`${event.name}, ${eventDate(event.date)}: ${number(event.participants)} partecipanti confermati`} title={`${event.name} · ${eventDate(event.date)} · ${number(event.participants)} partecipanti confermati`}>
            <span>{number(event.participants)}</span>
            <div className="bar" aria-hidden="true" style={{height: `${event.participants / maximum * 160}px`}}/>
            <small className="attendance-event-name">{event.name}</small>
            <small>{eventDate(event.date)}</small>
          </li>)}
        </ul>
      </div>
      <div className="chart-footer"><span><i/> Presenze confermate</span><span>Presenze complessive <strong>{number(total)}</strong></span></div>
      <p className="hint">Ogni persona conta una sola volta per evento. Le semplici iscrizioni non sono incluse; chi partecipa a più eventi conta in ciascuno.</p>
      <details className="attendance-data"><summary>Visualizza i numeri per evento</summary><div className="table-wrap"><table><caption>Partecipanti con presenza confermata</caption><thead><tr><th>Evento</th><th>Data</th><th>Partecipanti confermati</th></tr></thead><tbody>{events.map(event => <tr key={event.id}><td>{event.name}</td><td>{eventDate(event.date)}</td><td>{number(event.participants)}</td></tr>)}</tbody></table></div></details>
    </> : <div className="empty"><p>Nessun evento disponibile. Crea un evento e importa i partecipanti per vedere il grafico.</p></div>}
  </section>;
}
