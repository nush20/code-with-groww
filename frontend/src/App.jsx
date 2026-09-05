import {useEffect, useState} from 'react';
import {getCurrentUser, logOut} from './api.js';
import Auth from './components/Auth.jsx';
import CatchUp from './components/CatchUp.jsx';
import Watchlist from './components/Watchlist.jsx';
import StockDetail from './components/StockDetail.jsx';
import BrandMark from './components/BrandMark.jsx';

export default function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [view, setView] = useState('watchlist');
  const [detail, setDetail] = useState(null);
  const openDetail = (stock, range = '1D') => {
    setDetail({symbol: stock.symbol, range});
    setView('detail');
  };
  const returnHome = () => setView('watchlist');
  useEffect(() => { getCurrentUser().then(setUser).catch(() => setUser(null)).finally(() => setCheckingAuth(false)); }, []);
  async function logout() { await logOut().catch(() => {}); setUser(null); setView('watchlist'); }
  if (checkingAuth) return <div className="auth-loading">Opening MarketMemo…</div>;
  if (!user) return <div className="app-shell auth-shell"><Auth onAuthenticated={setUser}/></div>;
  return <div className="app-shell">
    <header><div className="header-inner"><div className="brand"><BrandMark className="brand-mark"/><span>MarketMemo</span></div>
      <div className="account-menu"><span>{user.name}</span><button onClick={logout}>Log out</button></div>
    </div></header>
    {view === 'watchlist' ? <Watchlist onOpenCatchUp={() => setView('catchup')} onViewStock={openDetail} />
      : view === 'detail' ? <StockDetail symbol={detail.symbol} initialRange={detail.range} onBack={returnHome} backLabel="Watchlist" />
      : <CatchUp onBack={returnHome} />}
  </div>;
}
