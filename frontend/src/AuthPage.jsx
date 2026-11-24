import { useState } from 'react'
import { ArrowRight, BrainCircuit, LockKeyhole, Mail, Sparkles, UserRound } from 'lucide-react'
import { api } from './api.js'

export default function AuthPage({ onAuthenticated, backendError }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setError('')
    setBusy(true)
    try {
      const result = await api(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      })
      onAuthenticated(result.user)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  function changeMode(nextMode) {
    setMode(nextMode)
    setError('')
  }

  return (
    <main className="auth-shell">
      <section className="auth-story">
        <div className="auth-brand">
          <span className="auth-brand-icon"><BrainCircuit size={25} /></span>
          <span>StudentDesk <b>AI</b></span>
        </div>
        <div className="auth-story-copy">
          <span className="auth-kicker"><Sparkles size={14} /> YOUR SEMESTER, IN SYNC</span>
          <h1>Make room for<br /><span>your best work.</span></h1>
          <p>One calm place for assignments, classes, plans, and the next step you need to take.</p>
          <div className="auth-proof">
            <span className="auth-proof-icon"><LockKeyhole size={17} /></span>
            <span><b>Your workspace stays yours</b><small>Your academic data is private to your account.</small></span>
          </div>
        </div>
        <div className="auth-orbit auth-orbit-one" />
        <div className="auth-orbit auth-orbit-two" />
        <div className="auth-story-footer">STUDY WITH MORE CLARITY</div>
      </section>

      <section className="auth-form-side">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand">
            <span className="auth-brand-icon"><BrainCircuit size={23} /></span>
            <b>StudentDesk <i>AI</i></b>
          </div>
          <div className="auth-form-heading">
            <span className="auth-kicker">{isSignup ? 'GET STARTED' : 'WELCOME BACK'}</span>
            <h2>{isSignup ? 'Create your account' : 'Sign in to your space'}</h2>
            <p>{isSignup ? 'Build a study routine that works for you.' : 'Pick up right where you left off.'}</p>
          </div>
          <div className="auth-mode-switch" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={!isSignup} className={!isSignup ? 'selected' : ''} onClick={() => changeMode('login')}>Log in</button>
            <button type="button" role="tab" aria-selected={isSignup} className={isSignup ? 'selected' : ''} onClick={() => changeMode('signup')}>Sign up</button>
          </div>
          {(error || backendError) && <div className="auth-error" role="alert">{error || backendError}</div>}
          <form className="auth-form" onSubmit={submit}>
            {isSignup && (
              <label className="auth-field">
                <span>Your name</span>
                <div className="auth-input-wrap"><UserRound size={17} /><input autoComplete="name" required maxLength={120} value={name} onChange={event => setName(event.target.value)} placeholder="Alex Morgan" /></div>
              </label>
            )}
            <label className="auth-field">
              <span>Email address</span>
              <div className="auth-input-wrap"><Mail size={17} /><input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="you@university.edu" /></div>
            </label>
            <label className="auth-field">
              <span>Password</span>
              <div className="auth-input-wrap"><LockKeyhole size={17} /><input type="password" autoComplete={isSignup ? 'new-password' : 'current-password'} required minLength={isSignup ? 8 : undefined} value={password} onChange={event => setPassword(event.target.value)} placeholder={isSignup ? 'At least 8 characters' : 'Enter your password'} /></div>
            </label>
            <button className="auth-submit" type="submit" disabled={busy}>
              {busy ? 'Please wait…' : isSignup ? 'Create account' : 'Log in'}
              {!busy && <ArrowRight size={17} />}
            </button>
          </form>
          <p className="auth-switch-copy">
            {isSignup ? 'Already have an account?' : 'New to StudentDesk AI?'}
            {' '}<button type="button" onClick={() => changeMode(isSignup ? 'login' : 'signup')}>{isSignup ? 'Log in' : 'Create an account'}</button>
          </p>
          <div className="auth-privacy"><LockKeyhole size={13} /> Private and secure student workspace</div>
        </div>
      </section>
    </main>
  )
}
