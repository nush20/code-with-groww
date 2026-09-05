import {useEffect, useRef, useState} from 'react';
import {searchStocks} from '../api.js';

export default function AddStock({onAdd, busy, existingSymbols}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [selected, setSelected] = useState(null);
  const [targetPrice, setTargetPrice] = useState('');
  const [direction, setDirection] = useState('ABOVE');
  const requestNumber = useRef(0);
  const containerRef = useRef(null);

  useEffect(() => {
    const close = event => {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  useEffect(() => {
    const cleaned = query.trim();
    setActiveIndex(-1);
    if (cleaned.length < 2) {
      setResults([]); setSearching(false); setSearchError(false); setOpen(false);
      return;
    }

    const currentRequest = ++requestNumber.current;
    setSearching(true); setSearchError(false); setOpen(true);
    const timer = setTimeout(async () => {
      try {
        const matches = await searchStocks(cleaned);
        if (currentRequest === requestNumber.current) setResults(matches);
      } catch {
        if (currentRequest === requestNumber.current) {
          setResults([]); setSearchError(true);
        }
      } finally {
        if (currentRequest === requestNumber.current) setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  function choose(stock) {
    if (existingSymbols.includes(stock.symbol)) return;
    setSelected(stock); setOpen(false); setTargetPrice(''); setDirection('ABOVE');
  }

  async function add() {
    if (!selected) return;
    const numericTarget = Number(targetPrice);
    const watchLevel = targetPrice.trim() && numericTarget > 0 ? {target_price: numericTarget, direction} : null;
    const added = await onAdd({symbol: selected.symbol, company_name: selected.company_name, instrument_key: selected.instrument_key}, watchLevel);
    if (added) {
      setQuery(''); setResults([]); setOpen(false); setSelected(null); setTargetPrice('');
    }
  }

  function handleKeyDown(event) {
    if (!open || !results.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault(); setActiveIndex(index => Math.min(index + 1, results.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault(); setActiveIndex(index => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault(); choose(results[activeIndex]);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  }

  return <section className="stock-search" ref={containerRef}>
    <label htmlFor="stock-search-input">Search stocks</label>
    <div className="search-input-wrap">
      <span aria-hidden="true">⌕</span>
      <input id="stock-search-input" value={query}
        onChange={event => setQuery(event.target.value)}
        onFocus={() => query.trim().length >= 2 && setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="Search stocks by company or symbol..." autoComplete="off"
        role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls="stock-search-results"
        aria-activedescendant={activeIndex >= 0 ? `stock-option-${activeIndex}` : undefined}/>
    </div>
    {open && <div className="search-results" id="stock-search-results" role="listbox">
      {searching ? <p className="search-message">Searching…</p>
        : searchError ? <p className="search-message search-error">Couldn’t load search results.</p>
        : results.length === 0 ? <p className="search-message">No matching NSE stocks found.</p>
        : results.map((stock, index) => {
          const added = existingSymbols.includes(stock.symbol);
          return <div id={`stock-option-${index}`} role="option" aria-selected={activeIndex === index}
            className={`search-result ${activeIndex === index ? 'active' : ''}`} key={stock.instrument_key}
            onMouseEnter={() => setActiveIndex(index)}>
            <div><strong>{stock.company_name}</strong><span>{stock.symbol} · {stock.exchange}</span></div>
            <button type="button" onClick={() => choose(stock)} disabled={busy || added}
              aria-label={added ? `${stock.company_name} already added` : `Add ${stock.company_name}`}>
              {added ? 'Added ✓' : '+ Add'}
            </button>
          </div>;
        })}
    </div>}
    {selected && <div className="add-stock-confirmation">
      <header><div><strong>{selected.company_name}</strong><span>{selected.symbol} · NSE</span></div><button type="button" onClick={() => setSelected(null)} aria-label="Cancel adding stock">×</button></header>
      <div className="optional-level-title"><strong>Add a price alert?</strong><span>Optional—you can add the stock without one.</span></div>
      <div className="optional-level-form">
        <div className="level-direction" role="group" aria-label="Watch price direction">
          <button type="button" className={direction === 'ABOVE' ? 'active' : ''} onClick={() => setDirection('ABOVE')}>Above</button>
          <button type="button" className={direction === 'BELOW' ? 'active' : ''} onClick={() => setDirection('BELOW')}>Below</button>
        </div>
        <label><span>Target price</span><div><b>₹</b><input type="number" min="0.01" step="0.01" value={targetPrice} onChange={event => setTargetPrice(event.target.value)} placeholder="Optional"/></div></label>
      </div>
      <button type="button" className="confirm-add-stock" onClick={add} disabled={busy || (targetPrice.trim() && Number(targetPrice) <= 0)}>{busy ? 'Adding…' : targetPrice.trim() ? 'Add stock & alert' : 'Add to watchlist'}</button>
    </div>}
  </section>;
}
