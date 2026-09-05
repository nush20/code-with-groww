import {useState} from 'react';
import {logIn, signUp} from '../api.js';
import BrandMark from './BrandMark.jsx';

export default function Auth({onAuthenticated}) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({name:'', email:'', password:''});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const update = event => setForm(current => ({...current, [event.target.name]:event.target.value}));

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const user = mode === 'signup' ? await signUp(form) : await logIn({email:form.email, password:form.password});
      onAuthenticated(user);
    } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }

  return <main className="auth-page">
    <section className="auth-intro"><BrandMark className="auth-logo"/><h1>MarketMemo</h1></section>
    <section className="auth-card">
      <div className="auth-tabs" role="tablist"><button className={mode === 'login' ? 'active' : ''} onClick={() => {setMode('login');setError('');}}>Log in</button><button className={mode === 'signup' ? 'active' : ''} onClick={() => {setMode('signup');setError('');}}>Sign up</button></div>
      <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
      <p>{mode === 'login' ? 'Log in to open your saved watchlist.' : 'Your watchlist and Catch-Up checkpoints will stay with your account.'}</p>
      <form onSubmit={submit}>
        {mode === 'signup' && <label><span>Name</span><input name="name" value={form.name} onChange={update} minLength="2" autoComplete="name" required/></label>}
        <label><span>Email</span><input name="email" type="email" value={form.email} onChange={update} autoComplete="email" required/></label>
        <label><span>Password</span><input name="password" type="password" value={form.password} onChange={update} minLength="8" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required/></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="auth-primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}</button>
      </form>
    </section>
  </main>;
}
