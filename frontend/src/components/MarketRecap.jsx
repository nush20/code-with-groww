import {useEffect, useState} from 'react';
import {getMarketRecap} from '../api.js';

const RANGES = ['1D', '1W', '2W', '1M'];
const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:2}).format(value);
const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;

function RangeSelector({value, onChange, label = 'Choose recap period'}) {
  return <div className="range-selector" role="group" aria-label={label}>
    {RANGES.map(range => <button type="button" key={range} className={value === range ? 'active' : ''} aria-pressed={value === range} onClick={() => onChange(range)}>{range}</button>)}
  </div>;
}

function RecapCard({story, range, onView}) {
  return <article className="recap-card">
    <header><div><strong>{story.symbol}</strong><h2>{story.display_label}</h2></div>
      <span className={`period-return ${story.session_return_pct >= 0 ? 'positive' : 'negative'}`}>{signed(story.session_return_pct)}</span></header>
    <p className="recap-story">{story.short_summary}</p>
    {story.classification !== 'QUIET' && <p className="recap-retention">{story.movement_label} {story.reversal_pct.toFixed(0)}%</p>}
    <div className="recap-card-range"><span>High <b>{money(story.high)}</b></span><span>Low <b>{money(story.low)}</b></span></div>
    <div className="recap-card-footer">
      <button type="button" className="view-journey" onClick={() => onView(story, range)}>View journey <span aria-hidden="true">→</span></button></div>
  </article>;
}

function OverviewCard({stock, range, onView}) {
  return <article className="overview-card">
    <header><strong>{stock.symbol}</strong><span className={stock.return_pct >= 0 ? 'positive' : 'negative'}>{signed(stock.return_pct)}</span></header>
    <p>{stock.company_name}</p>
    <div><span>High {money(stock.high)}</span><span>Low {money(stock.low)}</span></div>
    <button type="button" className="view-journey" onClick={() => onView(stock, range)}>View period <span aria-hidden="true">→</span></button>
  </article>;
}

export default function MarketRecap({onView, range, onRangeChange, onOpenBriefing}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setData(null); setError('');
    getMarketRecap(range).then(result => active && setData(result)).catch(() => active && setError('Couldn’t load this Market Recap. Please try again.'));
    return () => { active = false; };
  }, [range]);

  return <main className="recap-page">
    <section className="recap-heading"><p className="eyebrow">MARKET RECAP</p><h1>What happened in your watchlist?</h1>
      <p>Choose a period to see the journeys that mattered.</p><RangeSelector value={range} onChange={onRangeChange}/>
      {data?.period && <span>{data.period.label} · {data.period.session_count} trading {data.period.session_count === 1 ? 'session' : 'sessions'} analyzed{data.period.is_partial ? ' · Partial history' : ''}</span>}
    </section>
    {error ? <p className="error" role="alert">{error}</p> : !data ? <div className="catchup-loading">Preparing your market recap…</div> : <>
      {!data.period ? <section className="recap-empty"><h2>No market history is available yet.</h2><p>We couldn’t find enough real candles to calculate this period.</p></section>
        : <section className="recap-results">
          <div className="recap-result-heading"><h2>{data.stories.length ? `${data.stories.length} watchlist ${data.stories.length === 1 ? 'stock' : 'stocks'}` : 'No stock data available'}</h2><span>{data.period.label}</span></div>
          {!data.stories.length && <><p className="all-caught-up">Market observations were unavailable for this period.</p>
            <div className="overview-grid">{data.market_overview.map(stock => <OverviewCard stock={stock} range={range} onView={onView} key={stock.instrument_key}/>)}</div></>}
          <div className="recap-grid">{data.stories.map(story => <RecapCard story={story} range={range} onView={onView} key={story.instrument_key}/>)}</div>
        </section>}
      {range === '1D' && data.daily_developments && <button type="button" className="briefing-preview" onClick={onOpenBriefing}>
        <span><strong>Today in your watchlist</strong><small>{data.daily_developments.developments.length} source-backed {data.daily_developments.developments.length === 1 ? 'development' : 'developments'} from the latest trading session</small></span>
        <b>Open briefing <span aria-hidden="true">→</span></b>
      </button>}
      {!!data.unavailable_count && <p className="compressed-note">Market history was temporarily unavailable for {data.unavailable_count} {data.unavailable_count === 1 ? 'stock' : 'stocks'}.</p>}
    </>}
  </main>;
}

export {RangeSelector};
