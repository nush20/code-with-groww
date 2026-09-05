import {useEffect, useState} from 'react';
import {getCurrentUser, logOut} from './api.js';
import Auth from './components/Auth.jsx';
import CatchUp from './components/CatchUp.jsx';
import MarketRecap from './components/MarketRecap.jsx';
import Watchlist from './components/Watchlist.jsx';
import StockDetail from './components/StockDetail.jsx';
import DailyBriefing from './components/DailyBriefing.jsx';

export default function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [view, setView] = useState('watchlist');
  const [recapRange, setRecapRange] = useState('1D');
  const [detail, setDetail] = useState(null);
  const openDetail = (stock, range = '1D', from = view) => {
    setDetail({symbol: stock.symbol, range, from});
    setView('detail');
  };
  const leaveDetail = () => setView(detail?.from || 'watchlist');
  useEffect(() => { getCurrentUser().then(setUser).catch(() => setUser(null)).finally(() => setCheckingAuth(false)); }, []);
  async function logout() { await logOut().catch(() => {}); setUser(null); setView('watchlist'); }
  if (checkingAuth) return <div className="auth-loading">Opening MarketMemo…</div>;
  if (!user) return <div className="app-shell auth-shell"><Auth onAuthenticated={setUser}/></div>;
  return <div className="app-shell">
    <header><div className="header-inner"><div><div className="brand">MarketMemo</div><p>Your watchlist remembers what you missed.</p></div>
      <nav aria-label="Primary navigation">
        <button className={view === 'watchlist' ? 'active' : ''} onClick={() => setView('watchlist')}><strong>Watchlist</strong><span>Current state</span></button>
        <button className={view === 'recap' ? 'active' : ''} onClick={() => setView('recap')}><strong>Market Recap</strong><span>Latest session</span></button>
        <button className={view === 'briefing' ? 'active' : ''} onClick={() => setView('briefing')}><strong>Daily Briefing</strong><span>Company developments</span></button>
        <button className={view === 'catchup' ? 'active' : ''} onClick={() => setView('catchup')}><strong>Catch-Up</strong><span>Since you last checked</span></button>
      </nav><div className="account-menu"><span>{user.name}</span><button onClick={logout}>Log out</button></div>
    </div></header>
    {view === 'watchlist' ? <Watchlist />
      : view === 'recap' ? <MarketRecap range={recapRange} onRangeChange={setRecapRange} onOpenBriefing={() => setView('briefing')} onView={(stock, range) => openDetail(stock, range, 'recap')} />
      : view === 'briefing' ? <DailyBriefing />
      : view === 'detail' ? <StockDetail symbol={detail.symbol} initialRange={detail.range} onBack={leaveDetail} backLabel={detail.from === 'recap' ? 'Market Recap' : 'Watchlist'} />
      : <CatchUp />}
  </div>;
}
