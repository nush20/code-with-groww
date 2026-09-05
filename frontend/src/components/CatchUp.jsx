import {useEffect, useState} from 'react';
import {getCatchup, getCatchupDemo, markCaughtUp} from '../api.js';

const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', minimumFractionDigits:2, maximumFractionDigits:2}).format(value);
const percent = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const time = value => new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'}).format(new Date(value));
function JourneyCard({event}) {
  const unusual = event.unusualness?.state === 'UNUSUAL_MOVE';
  const level = event.watch_level_events?.[0];
  const movement = event.excursion.direction === 'up' ? 'rise' : 'decline';
  return <article className="journey-card">
    <header><div><span>{event.symbol}</span><h2>{event.company_name}</h2></div></header>
    <h3 className="journey-headline">{event.headline}</h3>
    <p className="journey-summary">{event.summary}</p>
    <div className="journey-values">
      <div><span>Your checkpoint · {time(event.baseline.time)}</span><strong>{money(event.baseline.price)}</strong></div>
      <div><span>{event.excursion.direction === 'up' ? 'Highest reached' : 'Lowest reached'} · {time(event.excursion.time)}</span><strong>{money(event.excursion.price)}</strong><em>{percent(event.excursion.return_pct)}</em></div>
      <div><span>Latest observed · {time(event.current.time)}</span><strong>{money(event.current.price)}</strong><em>{percent(event.current.return_pct)}</em></div>
    </div>
    <section className="attention-reasons"><strong>Why this matters to you</strong>
      {level && <p><span>Price alert</span> Crossed {money(level.target_price)} at {time(level.event_candle_time)} and is {level.currently_beyond_level ? 'still beyond it' : `now back ${level.direction === 'ABOVE' ? 'below' : 'above'} it`}.</p>}
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

export default function CatchUp() {
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
    <section className="catchup-heading"><p className="eyebrow">CATCH-UP</p><h1>What did I miss?</h1>
      <p>{data?.mode === 'demo' ? `${data.meaningful_count} complete Catch-Up examples · historical replay using real market data.` : data?.since ? `Since you last checked on ${new Intl.DateTimeFormat(undefined, {dateStyle:'medium', timeStyle:'short'}).format(new Date(data.since))}` : 'Mark caught up once to start remembering what happens while you’re away.'}</p>
      {!loading && <div className="catchup-controls">
        {data?.mode === 'demo' ? <>
          <button className="demo-entry" onClick={exitDemo} disabled={demoLoading}>{demoLoading ? 'Exiting…' : 'Exit replay'}</button>
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
        <div className="journey-grid">{data.events.map(event => <JourneyCard event={event} key={event.instrument_key}/>)}</div>
      </section>
      {!data.meaningful_count && !!data.insufficient_count && <p className="compressed-note">There wasn’t enough new market history for {data.insufficient_count} {data.insufficient_count === 1 ? 'stock' : 'stocks'} yet.</p>}
      {!data.meaningful_count && !!data.unavailable_count && <p className="compressed-note">Market history was temporarily unavailable for {data.unavailable_count} {data.unavailable_count === 1 ? 'stock' : 'stocks'}.</p>}
    </>}
  </main>;
}
