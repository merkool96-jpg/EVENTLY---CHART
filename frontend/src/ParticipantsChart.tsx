import {useState} from 'react';

type EventAttendance = {id: number; name: string; date: string; participants: number; attributed_value: number | null};
const number = (value: number) => new Intl.NumberFormat('it-IT').format(value);
const eventDate = (value: string) => new Date(value + 'T00:00:00').toLocaleDateString('it-IT', {day: '2-digit', month: 'short', year: 'numeric'});

const euro = (value: number) => new Intl.NumberFormat('it-IT', {style:'currency',currency:'EUR'}).format(value / 100);
export function ParticipantsChart({events,actualSpend}: {events: EventAttendance[];actualSpend:number}) {
  const [mode,setMode] = useState<'economics'|'participants'>('economics');
  const participants = mode === 'participants';
  const value = (event: EventAttendance) => participants ? event.participants : event.attributed_value;
  const formatted = (event: EventAttendance) => value(event) === null ? 'Non definito' : participants ? number(event.participants) : euro(event.attributed_value!);
  const maximum = Math.max(1, ...events.map(event => value(event) || 0));
  const total = events.reduce((sum, event) => sum + event.participants, 0);
  return <section className="panel attendance-panel" aria-labelledby="attendance-chart-title">
    <div className="panel-heading">
      <div><h3 id="attendance-chart-title">{participants ? 'I partecipanti agli incontri' : 'Il valore degli incontri'}</h3><p>{participants ? 'Persone con presenza confermata per evento' : 'Valore convenzionale × presenze confermate'}</p></div>
      <div className="chart-mode-switch" role="group" aria-label="Scegli il grafico">
        <button type="button" aria-pressed={!participants} onClick={()=>setMode('economics')}>Economics</button>
        <button type="button" aria-pressed={participants} onClick={()=>setMode('participants')}>Partecipanti</button>
      </div>
    </div>
    {events.length ? <>
      <div className="attendance-chart-scroll" tabIndex={0} role="region" aria-label={participants ? "Grafico partecipanti per evento, scorribile orizzontalmente" : "Grafico economics per evento, scorribile orizzontalmente"}>
        <ul className="chart attendance-chart" aria-label={participants ? "Partecipanti confermati per evento" : "Valore attribuito per evento"}>
          {events.map(event => <li className="bar-column" key={event.id} aria-label={`${event.name}, ${eventDate(event.date)}: ${formatted(event)} ${participants ? 'partecipanti confermati' : 'di valore attribuito'}`} title={`${event.name} · ${eventDate(event.date)} · ${formatted(event)} ${participants ? 'partecipanti confermati' : 'di valore attribuito'}`}>
            <span>{formatted(event)}</span>
            <div className="bar" aria-hidden="true" style={{height: `${(value(event) || 0) / maximum * 160}px`}}/>
            <small className="attendance-event-name">{event.name}</small>
            <small>{eventDate(event.date)}</small>
          </li>)}
        </ul>
      </div>
      <div className="chart-footer"><span><i/> {participants ? 'Presenze confermate' : 'Valore attribuito'}</span><span>{participants ? 'Presenze complessive' : 'Spesa riportata'} <strong>{participants ? number(total) : euro(actualSpend)}</strong></span></div>
      <p className="hint">{!participants && events.some(event=>event.attributed_value===null) ? 'Valori economici incompleti: alcuni eventi hanno valore non definito. ' : ''}Ogni persona conta una sola volta per evento. Le semplici iscrizioni non sono incluse; chi partecipa a più eventi conta in ciascuno.</p>
      <details className="attendance-data"><summary>Visualizza i numeri per evento</summary><div className="table-wrap"><table><caption>{participants ? 'Partecipanti con presenza confermata' : 'Valore economico attribuito'}</caption><thead><tr><th>Evento</th><th>Data</th><th>{participants ? 'Partecipanti confermati' : 'Valore attribuito'}</th></tr></thead><tbody>{events.map(event => <tr key={event.id}><td>{event.name}</td><td>{eventDate(event.date)}</td><td>{formatted(event)}</td></tr>)}</tbody></table></div></details>
    </> : <div className="empty"><p>Nessun evento disponibile. Crea un evento e importa i partecipanti per vedere il grafico.</p></div>}
  </section>;
}
