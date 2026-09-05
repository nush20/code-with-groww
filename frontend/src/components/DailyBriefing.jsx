import {useEffect, useState} from 'react';
import {getMarketRecap} from '../api.js';

const LABELS = {
  EARNINGS:'Results', GUIDANCE:'Outlook', MAJOR_ORDER_OR_DEAL:'Order or deal',
  MERGER_OR_ACQUISITION:'M&A', REGULATORY_OR_LEGAL:'Regulatory', MANAGEMENT_CHANGE:'Leadership',
  DIVIDEND:'Dividend', BUYBACK:'Buyback', STOCK_SPLIT:'Stock action',
  MAJOR_BUSINESS_ANNOUNCEMENT:'Business update', OTHER_MATERIAL:'Company news',
};
const time = value => new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'}).format(new Date(value));
const day = value => new Intl.DateTimeFormat(undefined, {dateStyle:'long', timeZone:'Asia/Kolkata'}).format(new Date(`${value}T12:00:00+05:30`));
const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;

export default function DailyBriefing() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    getMarketRecap('1D').then(result => active && setData(result)).catch(() => active && setError('Couldn’t load your daily briefing. Please try again.'));
    return () => { active = false; };
  }, []);
  const context = data?.daily_developments;
  const items = context?.developments || [];
  const impact = data?.watchlist_impact;
  const symbols = new Set(items.flatMap(item => item.symbols)).size;

  return <main className="briefing-page">
    <section className="briefing-heading"><p className="eyebrow">DAILY BRIEFING</p><h1>Your watchlist, in context.</h1>
      <p>Company developments published during the latest selected trading session.</p></section>
    {error ? <p className="error" role="alert">{error}</p> : !data ? <div className="catchup-loading">Preparing your daily briefing…</div> : <>
      {impact && <section className="watchlist-impact" aria-label="Watchlist daily impact">
        <header><div><p className="eyebrow">WATCHLIST IMPACT</p><h2>How your watchlist moved</h2></div>
          <strong className={impact.average_return_pct >= 0 ? 'positive' : 'negative'}>{signed(impact.average_return_pct)} <small>equal-weight average</small></strong></header>
        <p>{impact.up_count > impact.down_count ? 'More watched stocks finished higher than lower.' : impact.down_count > impact.up_count ? 'More watched stocks finished lower than higher.' : 'Advancing and declining stocks were evenly balanced.'}</p>
        <div className="impact-breadth">
          <span><b>{impact.up_count}</b> higher</span><span><b>{impact.down_count}</b> lower</span><span><b>{impact.flat_count}</b> unchanged</span>
        </div>
        {(impact.largest_gainer || impact.largest_decliner) && <div className="impact-movers">
          {impact.largest_gainer && <span><small>Largest rise</small><b>{impact.largest_gainer.symbol} {signed(impact.largest_gainer.return_pct)}</b></span>}
          {impact.largest_decliner && <span><small>Largest decline</small><b>{impact.largest_decliner.symbol} {signed(impact.largest_decliner.return_pct)}</b></span>}
        </div>}
        <small className="impact-note">Each watched company is weighted equally. This is not a portfolio return. Developments below are context, not claimed causes.</small>
      </section>}
      <section className="briefing-overview">
        <div><strong>{items.length}</strong><span>{items.length === 1 ? 'development' : 'developments'}</span></div>
        <div><strong>{symbols}</strong><span>watchlist {symbols === 1 ? 'company' : 'companies'}</span></div>
        <p>{context?.date ? day(context.date) : 'Latest trading session'}</p>
      </section>
      {context?.status === 'UNAVAILABLE' ? <section className="briefing-empty"><h2>Developments are temporarily unavailable.</h2><p>Your market information is unaffected.</p></section>
        : !items.length ? <section className="briefing-empty"><h2>No watchlist developments were found.</h2><p>Nothing source-backed was published for this trading date.</p></section>
        : <section className="briefing-timeline" aria-label="Watchlist developments">
          {items.map(item => <article key={item.id}>
            <time dateTime={item.published_at}>{time(item.published_at)}</time>
            <span className="timeline-dot" aria-hidden="true" />
            <div className="timeline-story">
              <div className="development-labels"><div className="development-symbols">{item.symbols.map(symbol => <span key={symbol}>{symbol}</span>)}</div>{item.type !== 'OTHER_MATERIAL' && <span className="development-category">{LABELS[item.type]}</span>}</div>
              <h2>{item.headline}</h2>
              {item.summary && <p>{item.summary}</p>}
              <footer><span>{item.source_name}</span>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">View original <span aria-hidden="true">↗</span></a>}</footer>
            </div>
          </article>)}
        </section>}
      {context?.status === 'PARTIAL' && <p className="daily-developments-partial">Some watchlist news was temporarily unavailable.</p>}
      <p className="briefing-disclaimer">News is shown as relevant context. It does not necessarily explain or cause a price movement.</p>
    </>}
  </main>;
}
