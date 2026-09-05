import {useEffect, useState} from 'react';
import {addStock, addWatchLevel, getWatchLevels, getWatchlist, removeStock} from '../api.js';
import AddStock from './AddStock.jsx';
import StockCard from './StockCard.jsx';

export default function Watchlist() {
  const [stocks, setStocks] = useState([]);
  const [watchLevels, setWatchLevels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getWatchlist(), getWatchLevels()])
      .then(([savedStocks, savedLevels]) => { setStocks(savedStocks); setWatchLevels(savedLevels); })
      .catch(() => setError('Couldn’t load your watchlist. Please try again.'))
      .finally(() => setLoading(false));
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
    <section className="watchlist-heading">
      <p className="eyebrow">MY WATCHLIST</p>
      <h1>Stocks you’re following</h1>
      <p>Keep an eye on the stocks that matter to you.</p>
    </section>
    <AddStock onAdd={add} busy={busy} existingSymbols={stocks.map(stock => stock.symbol)} />
    {error && <p className="error" role="alert">{error}</p>}
    <section className="saved-watchlist" aria-busy={loading}>
      <div className="section-title"><h2>Your Watchlist</h2>{!loading && <span>{stocks.length} {stocks.length === 1 ? 'stock' : 'stocks'}</span>}</div>
      {loading ? <div className="stock-grid" aria-label="Loading watchlist">{[1, 2, 3, 4].map(item => <div className="stock-card skeleton-card" key={item}><span/><span/><span/><div><i/><i/><i/></div></div>)}</div>
        : stocks.length === 0 ? <div className="empty-state"><h3>Your watchlist is empty</h3><p>Search for a company above to start following it.</p></div>
        : <div className="stock-grid">{stocks.map(stock => <StockCard key={stock.id} stock={stock} watchLevels={watchLevels.filter(level => level.instrument_key === stock.instrument_key)} onRemove={remove} busy={busy} />)}</div>}
    </section>
  </main>;
}
