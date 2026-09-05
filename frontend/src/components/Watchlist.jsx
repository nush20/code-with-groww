import {useEffect, useState} from 'react';
import {addStock, addWatchLevel, getMarketRecap, getWatchLevels, getWatchlist, removeStock} from '../api.js';
import AddStock from './AddStock.jsx';
import StockCard from './StockCard.jsx';

const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const shortDate = value => new Intl.DateTimeFormat(undefined, {month:'short', day:'numeric', timeZone:'Asia/Kolkata'}).format(new Date(`${value}T12:00:00+05:30`));

function DailyOverview({data}) {
  const [expanded, setExpanded] = useState(false);
  if (!data?.watchlist_impact) return null;
  const impact = data.watchlist_impact;
  const developments = data.daily_developments?.developments || [];
  const leading = [impact.largest_gainer, impact.largest_decliner].filter(Boolean)
    .sort((a, b) => Math.abs(b.return_pct) - Math.abs(a.return_pct))[0];
  return <section className="smart-daily-card">
    <header><div><p className="eyebrow">TODAY IN YOUR WATCHLIST</p><h2>{impact.up_count > impact.down_count ? 'More stocks finished higher' : impact.down_count > impact.up_count ? 'More stocks finished lower' : 'Your watchlist was evenly split'}</h2></div>
      <strong className={impact.average_return_pct >= 0 ? 'positive' : 'negative'}>{signed(impact.average_return_pct)}<small>equal-weight average</small></strong></header>
    <div className="daily-snapshot">
      <div className="daily-breadth"><span><b>{impact.up_count}</b> higher</span><span><b>{impact.down_count}</b> lower</span><span><b>{impact.flat_count}</b> unchanged</span></div>
      {leading && <div className="daily-leading"><small>Largest move</small><strong>{leading.symbol}</strong><span className={leading.return_pct >= 0 ? 'positive' : 'negative'}>{signed(leading.return_pct)}</span></div>}
      <div className="daily-development-count"><strong>{developments.length}</strong><span>{developments.length === 1 ? 'company development' : 'company developments'}</span></div>
    </div>
    {!!developments.length && <button type="button" className="daily-toggle" onClick={() => setExpanded(value => !value)}>{expanded ? 'Hide today’s activity' : 'View today’s activity'} <span aria-hidden="true">{expanded ? '↑' : '↓'}</span></button>}
    {expanded && <div className="daily-activity-list">
      {developments.map(item => <article key={item.id}><div>{item.symbols.map(symbol => <span key={symbol}>{symbol}</span>)}<time>{new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'}).format(new Date(item.published_at))}</time></div><h3>{item.headline}</h3>{item.summary && <p>{item.summary}</p>}<footer><span>{item.source_name}</span>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">View source ↗</a>}</footer></article>)}
      <p className="activity-context-note">Developments are relevant context and are not claimed causes of price movements.</p>
    </div>}
    {data.period?.end_date && <p className="daily-date">Latest trading session · {shortDate(data.period.end_date)}</p>}
  </section>;
}

export default function Watchlist({onOpenCatchUp, onViewStock}) {
  const [stocks, setStocks] = useState([]);
  const [watchLevels, setWatchLevels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [daily, setDaily] = useState(null);

  useEffect(() => {
    Promise.all([getWatchlist(), getWatchLevels()])
      .then(([savedStocks, savedLevels]) => { setStocks(savedStocks); setWatchLevels(savedLevels); })
      .catch(() => setError('Couldn’t load your watchlist. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    getMarketRecap('1D').then(result => active && setDaily(result)).catch(() => {});
    return () => { active = false; };
  }, []);

  async function add(values, watchLevel) {
    setError(''); setBusy(true);
    try {
      const created = await addStock(values);
      setStocks(current => [...current, created]);
      if (watchLevel) {
        try {
          const createdLevel = await addWatchLevel({instrument_key: created.instrument_key, symbol: created.symbol, ...watchLevel});
          setWatchLevels(current => [...current, createdLevel]);
        } catch {
          setError(`${created.symbol} was added, but its price alert couldn’t be saved.`);
        }
      }
      return true;
    } catch {
      setError('Couldn’t add this stock. It may already be in your watchlist.');
      return false;
    } finally { setBusy(false); }
  }

  async function remove(id) {
    setError(''); setBusy(true);
    try {
      await removeStock(id);
      const removed = stocks.find(stock => stock.id === id);
      setStocks(current => current.filter(stock => stock.id !== id));
      if (removed) setWatchLevels(current => current.filter(level => level.instrument_key !== removed.instrument_key));
    } catch {
      setError('Couldn’t remove this stock. Please try again.');
    } finally { setBusy(false); }
  }

  return <main>
    <section className="watchlist-heading smart-watchlist-heading">
      <div><p className="eyebrow">YOUR SMART WATCHLIST</p><h1>Your watchlist</h1><p>Live market information, personal price alerts, and the changes that matter.</p></div>
      <button type="button" className="catchup-primary" onClick={onOpenCatchUp}><span aria-hidden="true">✦</span><span><strong>Catch me up</strong><small>See what happened since your last check</small></span></button>
    </section>
    <DailyOverview data={daily}/>
    <AddStock onAdd={add} busy={busy} existingSymbols={stocks.map(stock => stock.symbol)} />
    {error && <p className="error" role="alert">{error}</p>}
    <section className="saved-watchlist" aria-busy={loading}>
      <div className="section-title"><h2>Your Watchlist</h2>{!loading && <span>{stocks.length} {stocks.length === 1 ? 'stock' : 'stocks'}</span>}</div>
      {loading ? <div className="stock-grid" aria-label="Loading watchlist">{[1, 2, 3, 4].map(item => <div className="stock-card skeleton-card" key={item}><span/><span/><span/><div><i/><i/><i/></div></div>)}</div>
        : stocks.length === 0 ? <div className="empty-state"><h3>Your watchlist is empty</h3><p>Search for a company above to start following it.</p></div>
        : <div className="stock-grid">{stocks.map(stock => <StockCard key={stock.id} stock={stock} watchLevels={watchLevels.filter(level => level.instrument_key === stock.instrument_key)} onRemove={remove} onView={onViewStock} busy={busy} />)}</div>}
    </section>
  </main>;
}
