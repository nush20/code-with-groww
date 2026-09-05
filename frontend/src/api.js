const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const marketRecapCache = new Map();

async function request(path, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: 'include',
      signal: controller.signal,
      headers: {'Content-Type': 'application/json', ...options?.headers},
    });
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The server took too long to respond');
    throw new Error('Couldn’t connect to the backend');
  } finally {
    clearTimeout(timeout);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.detail || 'Request failed');
  return data;
}

export const getWatchlist = () => request('/watchlist');
export const getCurrentUser = () => request('/auth/me');
export const signUp = (values) => request('/auth/signup', {method:'POST', body:JSON.stringify(values)});
export const logIn = (values) => request('/auth/login', {method:'POST', body:JSON.stringify(values)});
export const continueAsDemo = () => request('/auth/demo', {method:'POST'});
export const logOut = () => request('/auth/logout', {method:'POST'});
export const getCatchupStatus = () => request('/catchup/status');
export const getCatchup = () => request('/catchup');
export const getCatchupDemo = (scenario = 'combined') => request(`/catchup/demo?scenario=${encodeURIComponent(scenario)}`);
export function getMarketRecap(range = '1D') {
  const cached = marketRecapCache.get(range);
  if (cached && Date.now() - cached.createdAt < 60_000) return cached.promise;
  const promise = request(`/market-recap?range=${encodeURIComponent(range)}`)
    .catch(error => { marketRecapCache.delete(range); throw error; });
  marketRecapCache.set(range, {createdAt: Date.now(), promise});
  return promise;
}
export const getStockDetail = (symbol, range = '1D') => request(`/stocks/${encodeURIComponent(symbol)}/detail?range=${encodeURIComponent(range)}`);
export const getWatchLevels = (instrumentKey) => request(
  instrumentKey ? `/watch-levels/${encodeURIComponent(instrumentKey)}` : '/watch-levels'
);
export const addWatchLevel = (level) => request('/watch-levels', {method:'POST', body:JSON.stringify(level)});
export const removeWatchLevel = (id) => request(`/watch-levels/${id}`, {method:'DELETE'});
export const markCaughtUp = () => request('/catchup/mark', {method: 'POST'});
export const searchStocks = (query) => request(`/stocks/search?q=${encodeURIComponent(query)}`);
export const addStock = async (stock) => {
  const created = await request('/watchlist', {method: 'POST', body: JSON.stringify(stock)});
  marketRecapCache.clear();
  return created;
};
export const removeStock = async (id) => {
  const result = await request(`/watchlist/${id}`, {method: 'DELETE'});
  marketRecapCache.clear();
  return result;
};
