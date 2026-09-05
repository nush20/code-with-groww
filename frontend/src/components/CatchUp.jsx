import {useEffect, useMemo, useState} from 'react';
import {getCatchup, getCatchupDemo, markCaughtUp} from '../api.js';

const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', minimumFractionDigits:2, maximumFractionDigits:2}).format(value);
const percent = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const time = value => new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'}).format(new Date(value));
const eventKey = event => `${event.instrument_key}-${event.baseline.time}`;
const hasAlert = event => Boolean(event.watch_level_events?.length);
const isUnusual = event => event.unusualness?.state === 'UNUSUAL_MOVE';
const getSignal = event => event.reversal_pct >= 90 ? 'Full reversal' : isUnusual(event) ? 'Unusual movement' : hasAlert(event) ? 'Alert reached' : 'Hidden journey';
function JourneyCard({event}) {
  const unusual = isUnusual(event);
  const level = event.watch_level_events?.[0];
  const movement = event.excursion.direction === 'up' ? 'rise' : 'decline';
  const signal = getSignal(event);
  return <article className="journey-card">
    <header><div><span className="journey-symbol">{event.symbol}</span><h2>{event.company_name}</h2>{event.replay_label && <em className="replay-example-label">{event.replay_label}</em>}</div><span className="journey-signal">{signal}</span></header>
    <h3 className="journey-headline">{event.headline}</h3>
    <p className="journey-summary">{event.summary}</p>
    <div className="journey-values">
      <div><span>Your checkpoint</span><small>{time(event.baseline.time)}</small><strong>{money(event.baseline.price)}</strong></div>
      <div className="journey-extreme"><span>{event.excursion.direction === 'up' ? 'Highest reached' : 'Lowest reached'}</span><small>{time(event.excursion.time)}</small><strong>{money(event.excursion.price)}</strong><em>{percent(event.excursion.return_pct)}</em></div>
      <div><span>Latest observed</span><small>{time(event.current.time)}</small><strong>{money(event.current.price)}</strong><em>{percent(event.current.return_pct)}</em></div>
    </div>
    <section className="attention-reasons"><strong>Why this matters to you</strong>
      {level && <p><span>{level.alert_type === 'PERCENT' ? 'Percentage alert' : 'Price alert'}</span> {level.alert_type === 'PERCENT' ? `${level.direction === 'ABOVE' ? 'Rose' : 'Fell'} ${Number(level.target_percent).toFixed(2).replace(/\.00$/, '')}% from ${money(level.reference_price)}` : `Crossed ${money(level.target_price)}`} at {time(level.event_candle_time)} and is {level.currently_beyond_level ? 'still beyond it' : `now back ${level.direction === 'ABOVE' ? 'below' : 'above'} it`}.</p>}
      {unusual && <p><span>Unusual move</span> {event.unusualness.significance_multiple.toFixed(1)}× the expected movement for this length of time.</p>}
      {event.is_hidden_journey && <p><span>Round trip</span> {Math.round(event.reversal_pct)}% of the {movement} later {event.excursion.direction === 'up' ? 'faded' : 'recovered'}.</p>}
    </section>
    {!!event.context?.company_developments?.length && <section className="relevant-context">
      <strong>Related development</strong>
      {event.context.company_developments.slice(0, 1).map(development => <div key={development.id}><p>{development.headline}</p>
        <span>{time(development.published_at)}</span>{development.source_url && <a href={development.source_url} target="_blank" rel="noreferrer">View source</a>}</div>)}
    </section>}
    <p className="journey-freshness">Upstox · Updated {time(event.data_freshness.market_timestamp)}{event.data_freshness.is_stale ? ' · Delayed' : ''}</p>
  </article>;
}

function CatchUpList({events}) {
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const filters = [
    ['all', 'All'], ['alerts', 'My alerts'],
  ];
  const filtered = useMemo(() => events.filter(event => {
    if (filter === 'alerts') return hasAlert(event);
    return true;
  }).sort((left, right) => {
    const priority = event => hasAlert(event) ? 0 : isUnusual(event) ? 1 : 2;
    return priority(left) - priority(right);
  }), [events, filter]);
  const visible = showAll ? filtered : filtered.slice(0, 5);
  const groups = [
    ['Important updates', visible.filter(event => hasAlert(event) || isUnusual(event))],
    ['Other notable changes', visible.filter(event => !hasAlert(event) && !isUnusual(event))],
  ];
  const selectFilter = value => { setFilter(value); setExpanded(null); setShowAll(false); };

  return <section className="catchup-list-shell">
    <header className="catchup-list-summary"><div><strong>{events.length}</strong><span>important {events.length === 1 ? 'update' : 'updates'} across {new Set(events.map(event => event.symbol)).size} {new Set(events.map(event => event.symbol)).size === 1 ? 'stock' : 'stocks'}</span></div><small>Open an update to see the details</small></header>
    <div className="catchup-filter-bar"><div className="catchup-filters" aria-label="Filter Catch-Up updates">{filters.map(([value, label]) => <button type="button" className={filter === value ? 'active' : ''} onClick={() => selectFilter(value)} key={value}>{label}</button>)}</div></div>
    {!filtered.length && <p className="catchup-filter-empty">No updates match this filter.</p>}
    {groups.map(([title, items]) => items.length ? <section className="catchup-group" key={title}><h2>{title}<span>{items.length}</span></h2>
      <div className="catchup-event-list">{items.map(event => {
        const key = eventKey(event); const open = expanded === key;
        return <article className={`catchup-event${open ? ' open' : ''}`} key={key}>
          <button type="button" className="catchup-event-row" aria-expanded={open} onClick={() => setExpanded(open ? null : key)}>
            <span className="catchup-event-top"><span className="catchup-event-company"><strong>{event.company_name}</strong><small>{event.symbol}</small></span><span className={`catchup-event-return ${event.current.return_pct < 0 ? 'negative' : ''}`}>{percent(event.current.return_pct)}<small>since checkpoint</small></span></span>
            <span className="catchup-event-badges"><span className="catchup-event-signal">{getSignal(event)}</span>{!hasAlert(event) && <span className="catchup-no-alert">No alert set</span>}</span>
            <span className="catchup-event-excerpt">{event.headline}</span>
            <span className="catchup-event-action">{open ? 'Hide details' : 'View details'} <b aria-hidden="true">{open ? '↑' : '→'}</b></span>
          </button>
          {open && <div className="catchup-event-detail"><JourneyCard event={event}/></div>}
        </article>;
      })}</div>
    </section> : null)}
    {filtered.length > 5 && <button type="button" className="catchup-show-more" onClick={() => {setShowAll(value => !value); setExpanded(null);}}>{showAll ? 'Show fewer updates' : `Show remaining ${filtered.length - 5}`}</button>}
  </section>;
}

export default function CatchUp({onBack}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [marking, setMarking] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const load = () => getCatchup().then(setData).catch(() => setError('Couldn’t load your Catch-Up. Please try again.')).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  async function enterDemo() {
    setDemoLoading(true); setError(''); setMessage('');
    try { setData(await getCatchupDemo()); }
    catch { setError('Couldn’t load the replay demo. Please try again.'); }
    finally { setDemoLoading(false); }
  }

  async function exitDemo() {
    setDemoLoading(true); setError('');
    try { setData(await getCatchup()); }
    catch { setError('Couldn’t return to your live Catch-Up. Please try again.'); }
    finally { setDemoLoading(false); }
  }

  async function mark() {
    setMarking(true); setError(''); setMessage('');
    try {
      await markCaughtUp();
      const refreshed = await getCatchup();
      setData(refreshed); setMessage('You’re all caught up.');
    } catch { setError('Couldn’t update your Catch-Up state. Please try again.'); }
    finally { setMarking(false); }
  }

  return <main className="catchup-page">
    <button type="button" className="detail-back" onClick={onBack}>← Watchlist</button>
    <section className="catchup-heading"><p className="eyebrow">CATCH-UP</p><h1>What did I miss?</h1>
      {data?.mode !== 'demo' && <p>{data?.since ? `Since you last checked on ${new Intl.DateTimeFormat(undefined, {dateStyle:'medium', timeStyle:'short'}).format(new Date(data.since))}` : 'Mark caught up once to start remembering what happens while you’re away.'}</p>}
      {!loading && <div className="catchup-controls">
        {data?.mode === 'demo' ? <>
          <button className="demo-entry" onClick={exitDemo} disabled={demoLoading}>{demoLoading ? 'Exiting…' : 'Exit'}</button>
        </> : <>
          <button className="demo-entry" onClick={enterDemo} disabled={demoLoading}>{demoLoading ? 'Loading examples…' : 'View Catch-Up examples'}</button>
          <button className="mark-caught-up" onClick={mark} disabled={marking}>{marking ? 'Marking…' : 'Mark caught up'}</button>
        </>}
      </div>}
    </section>
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="catchup-notice" role="status">{message}</p>}
    {loading ? <div className="catchup-loading">Checking what happened…</div> : <>
      <section className="catchup-results">
        {!data.meaningful_count && <div className="catchup-empty"><h2>{data.since ? 'You’re all caught up.' : 'Ready when you are.'}</h2><p className="all-caught-up">{data.since ? 'Nothing significant was hidden by the current prices since your last Catch-Up.' : 'Mark caught up to create the starting point for your first Catch-Up.'}</p></div>}
        {!!data.meaningful_count && <CatchUpList events={data.events}/>}
      </section>
      {!data.meaningful_count && !!data.insufficient_count && <p className="compressed-note">There wasn’t enough new market history for {data.insufficient_count} {data.insufficient_count === 1 ? 'stock' : 'stocks'} yet.</p>}
      {!data.meaningful_count && !!data.unavailable_count && <p className="compressed-note">Market history was temporarily unavailable for {data.unavailable_count} {data.unavailable_count === 1 ? 'stock' : 'stocks'}.</p>}
    </>}
  </main>;
}
