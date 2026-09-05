import {useEffect, useMemo, useState} from 'react';
import {getStockDetail} from '../api.js';
import {RangeSelector} from './MarketRecap.jsx';
import CompanyContext from './CompanyContext.jsx';

const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:2}).format(value);
const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const moment = value => new Intl.DateTimeFormat(undefined, {weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit'}).format(new Date(value));

function JourneyChart({candles, high, low, latest}) {
  const chart = useMemo(() => {
    if (!candles?.length) return null;
    const values = candles.map(point => point.close);
    const min = Math.min(...values), max = Math.max(...values), spread = max - min || 1;
    const points = values.map((value, index) => `${20 + index * 760 / Math.max(1, values.length - 1)},${190 - (value - min) * 150 / spread}`).join(' ');
    return {points, min, max};
  }, [candles]);
  if (!chart) return <p>No chart data is available for this period.</p>;
  return <div className="journey-chart" role="img" aria-label={`Price journey from ${money(candles[0].close)} to ${money(latest)}`}>
    <svg viewBox="0 0 800 220" preserveAspectRatio="none"><line x1="20" y1="190" x2="780" y2="190"/><polyline points={chart.points}/></svg>
    <div className="chart-range"><span>Low {money(low)}</span><span>High {money(high)}</span></div>
  </div>;
}

export default function StockDetail({symbol, initialRange, onBack, backLabel}) {
  const [range, setRange] = useState(initialRange || '1D');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setData(null); setError('');
    getStockDetail(symbol, range).then(result => active && setData(result)).catch(error => active && setError(error.message || 'Couldn’t load this stock journey.'));
    return () => { active = false; };
  }, [symbol, range]);

  return <main className="stock-detail-page">
    <button type="button" className="detail-back" onClick={onBack}>← {backLabel}</button>
    {error ? <section className="recap-empty"><h2>Stock journey unavailable</h2><p>{error}</p></section> : !data ? <div className="catchup-loading">Loading price journey…</div> : <>
      <section className="detail-header"><div><p className="eyebrow">{data.symbol}</p><h1>{data.company_name}</h1><div className="detail-price">{money(data.latest_price)} <span className={data.period_return_pct >= 0 ? 'positive' : 'negative'}>{signed(data.period_return_pct)}</span></div></div>
        <RangeSelector value={range} onChange={setRange} label="Choose stock journey period"/></section>
      {data.period.is_partial && <p className="partial-note">Showing {data.period.session_count} available trading sessions. No missing sessions were fabricated.</p>}
      <section className="detail-panel"><h2>Price journey</h2><JourneyChart candles={data.candles} high={data.period_high} low={data.period_low} latest={data.latest_price}/>
        <p className="detail-freshness">{data.freshness.is_stale ? 'Delayed data' : 'Latest data'} · Updated {moment(data.freshness.market_timestamp)}</p></section>
      <div className="detail-grid"><section className="detail-panel what-happened-panel"><p className="eyebrow">WHAT HAPPENED?</p><h2>{data.display_label}</h2><p className="detail-summary">{data.summary} {data.explanation}</p></section>
        <section className="detail-panel"><p className="eyebrow">KEY FACTS</p><dl className="detail-facts">
          <div><dt>Period return</dt><dd>{signed(data.period_return_pct)}</dd></div><div><dt>Largest excursion</dt><dd>{signed(data.max_excursion_pct)}</dd></div>
          <div><dt>Period high</dt><dd>{money(data.period_high)}</dd></div><div><dt>Period low</dt><dd>{money(data.period_low)}</dd></div><div><dt>{data.movement_label}</dt><dd>{data.reversal_pct.toFixed(0)}%</dd></div>
        </dl></section></div>
      <section className="detail-panel"><p className="eyebrow">IMPORTANT MOMENTS</p><div className="moments">
        <div><strong>Peak</strong><span>{moment(data.period_high_time)}</span><b>{money(data.period_high)}</b></div>
        <div><strong>Period low</strong><span>{moment(data.period_low_time)}</span><b>{money(data.period_low)}</b></div>
        <div><strong>Latest</strong><span>{moment(data.freshness.market_timestamp)}</span><b>{money(data.latest_price)}</b></div>
      </div></section>
      {range === '1D' && <CompanyContext context={data.context}/>} 
    </>}
  </main>;
}
