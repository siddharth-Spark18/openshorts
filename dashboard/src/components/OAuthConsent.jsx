import React, { useEffect, useMemo, useState } from 'react';
import { Plug, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { apiJson } from '../lib/api';
import { getApiUrl } from '../config';
import LoginModal from './LoginModal';

// The OAuth consent screen for MCP clients (claude.ai, ChatGPT, ...). The API
// bounced the client's /oauth/authorize request here because only the
// dashboard holds the session. Approving mints a code server-side and sends
// the browser back to the client; the access token it then receives is an
// ordinary API key, listed (and revocable) in the account page.

// Only ever navigate to a web URL the API built: a javascript: or data: URL
// here would run in the dashboard's origin, next to the session.
function goTo(url) {
  let u;
  try { u = new URL(url); } catch { throw new Error('bad redirect'); }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') throw new Error('bad redirect');
  window.location.replace(u.toString());
}

function readParams() {
  const hash = window.location.hash || '';
  const q = hash.includes('?') ? hash.slice(hash.indexOf('?') + 1) : '';
  return Object.fromEntries(new URLSearchParams(q).entries());
}

export default function OAuthConsent() {
  const { isSignedIn, loading, me } = useAuth();
  const params = useMemo(readParams, []);
  const [client, setClient] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showLogin, setShowLogin] = useState(false);

  useEffect(() => {
    if (!params.client_id) { setError('This link is missing the client id.'); return; }
    fetch(getApiUrl(`/api/oauth/client/${encodeURIComponent(params.client_id)}`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Unknown client'))))
      .then(setClient)
      .catch(() => setError('This connection request comes from an unknown app. Start again from the app you are connecting.'));
  }, [params.client_id]);

  useEffect(() => {
    if (!loading && !isSignedIn) setShowLogin(true);
  }, [loading, isSignedIn]);

  const decide = async (allow) => {
    setBusy(true);
    try {
      if (!allow) {
        // The API checks redirect_uri against the client's registered ones;
        // this page's own URL is whatever the link it came from said.
        const d = await apiJson('/api/oauth/deny', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            client_id: params.client_id,
            redirect_uri: params.redirect_uri,
            state: params.state || null,
          }),
        });
        goTo(d.redirect);
        return;
      }
      const d = await apiJson('/api/oauth/authorize', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: params.client_id,
          redirect_uri: params.redirect_uri,
          state: params.state || null,
          code_challenge: params.code_challenge,
          code_challenge_method: params.code_challenge_method || 'S256',
          scope: params.scope || null,
          response_type: params.response_type || 'code',
        }),
      });
      goTo(d.redirect);
    } catch (e) {
      setError(e?.detail || 'Could not complete the connection. Try again from the app.');
      setBusy(false);
    }
  };

  const name = client?.client_name || 'an app';
  const hosts = client?.redirect_hosts || [];

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="card p-8 max-w-md w-full text-center">
        <div className="w-12 h-12 rounded-full bg-brass/10 flex items-center justify-center mx-auto mb-4">
          <Plug size={20} className="text-brass" />
        </div>
        <h1 className="font-display lowercase text-2xl text-ink mb-2">Connect {name} to OpenShorts</h1>
        {error ? (
          <p className="text-warn text-sm">{error}</p>
        ) : (
          <>
            <p className="text-muted text-sm mb-6">
              <b className="text-ink">{name}</b> wants to clip and publish videos with your account
              {me?.email ? <> (<span className="text-ink">{me.email}</span>)</> : null}.
              It will use your plan&apos;s minutes and you can disconnect it any time from
              Account → API keys.
            </p>
            {hosts.length > 0 && (
              <p className="text-xs text-ink2 mb-4">
                Access goes to <b className="text-ink break-all">{hosts.join(', ')}</b>.
                Only allow it if that is the app you started from.
              </p>
            )}
            <ul className="text-left text-xs text-ink2 space-y-1.5 mb-6">
              <li className="flex gap-2"><ShieldCheck size={14} className="text-ok shrink-0 mt-0.5" /> Process videos and read the resulting clips</li>
              <li className="flex gap-2"><ShieldCheck size={14} className="text-ok shrink-0 mt-0.5" /> Add subtitles, recut and publish clips you own</li>
              <li className="flex gap-2"><ShieldCheck size={14} className="text-ok shrink-0 mt-0.5" /> Nothing else: no billing, no account settings, no key management</li>
            </ul>
            {loading || !client ? (
              <div className="flex justify-center py-2"><Loader2 className="animate-spin text-brass" size={18} /></div>
            ) : isSignedIn ? (
              <div className="flex gap-3">
                <button onClick={() => decide(false)} disabled={busy} className="btn-ghost flex-1 py-2.5">Cancel</button>
                <button onClick={() => decide(true)} disabled={busy} className="btn-primary flex-1 py-2.5">
                  {busy ? <Loader2 size={16} className="animate-spin" /> : 'Allow'}
                </button>
              </div>
            ) : (
              <button onClick={() => setShowLogin(true)} className="btn-primary w-full py-2.5">Sign in to continue</button>
            )}
          </>
        )}
      </div>
      {showLogin && !isSignedIn && <LoginModal onClose={() => setShowLogin(false)} />}
    </div>
  );
}
