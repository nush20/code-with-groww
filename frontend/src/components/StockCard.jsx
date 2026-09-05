export default function StockCard({stock, watchLevels = [], onRemove, busy}) {
  const money = value => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value);
  const age = timestamp => {
    const seconds = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000));
    if (seconds < 60) return `${seconds} sec ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m ago`;
  };
  const change = stock.market?.change_percent ?? 0;
  const changeLabel = change > 0 ? `▲ +${change.toFixed(2)}%` : change < 0 ? `▼ ${change.toFixed(2)}%` : '0.00%';

  return <article className="stock-card">
    <header className="card-header">
      <div><strong>{stock.symbol}</strong><h3>{stock.company_name}</h3></div>
      <button className="remove" onClick={() => onRemove(stock.id)} disabled={busy} aria-label={`Remove ${stock.company_name} from watchlist`}>Remove</button>
    </header>
    {stock.market ? <>
      <div className="quote-line">
        <span className="price">{money(stock.market.price)}</span>
        <span className={`change ${change > 0 ? 'positive' : change < 0 ? 'negative' : 'unchanged'}`}>{changeLabel}<small>Today</small></span>
      </div>
      <dl className="market-details">
        <div><dt>High</dt><dd>{money(stock.market.day_high)}</dd></div>
        <div><dt>Low</dt><dd>{money(stock.market.day_low)}</dd></div>
        <div><dt>Prev. close</dt><dd>{money(stock.market.previous_close)}</dd></div>
      </dl>
      <p className={stock.market.is_stale ? 'freshness stale' : 'freshness'}>
        {stock.market.is_stale ? 'Delayed · ' : ''}Updated {age(stock.market.market_timestamp)}
      </p>
    </> : <p className="market-error">Market data temporarily unavailable.</p>}
    {!!watchLevels.length && <div className="stock-watch-levels" aria-label={`${stock.symbol} price alerts`}>
      <strong>Your price alert</strong>
      {watchLevels.map(level => <span key={level.id}>{level.direction === 'ABOVE' ? '↑ Above' : '↓ Below'} {money(level.target_price)}</span>)}
    </div>}
  </article>;
}
