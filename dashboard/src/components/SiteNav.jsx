// The landing's header: the shared site navigation of seo/nav.js, the same
// markup the static SEO pages and the crawler fallback render, so the header
// does not change when React replaces the fallback in #root.
//
// The one thing only this surface knows is the session. A visitor with a
// stored token sees "Open app" and no "Log in"; the token is read from
// localStorage straight away (no network) so the label is right on the first
// paint, then confirmed by /api/me through AuthContext.
import { useEffect, useMemo, useRef } from 'react';
import { renderNav, wireNav, NAV_CSS } from '../../seo/nav.js';
import { useAuth } from '../contexts/AuthContext';
import { getToken } from '../lib/api';

const hasStoredSession = () => {
  try { return !!getToken(); } catch { return false; }
};

export default function SiteNav({ className = '' }) {
  const { isSignedIn, loading, billingEnabled } = useAuth();
  const signedIn = isSignedIn || (loading && hasStoredSession());
  // Self-hosted (no billing) has no accounts to sign in to.
  const showLogin = loading || billingEnabled;
  const html = useMemo(() => renderNav({ signedIn, showLogin }), [signedIn, showLogin]);
  const ref = useRef(null);
  useEffect(() => wireNav(ref.current?.querySelector('[data-osn]')), [html]);
  return (
    <>
      <style>{NAV_CSS}</style>
      <div ref={ref} className={className} dangerouslySetInnerHTML={{ __html: html }} />
    </>
  );
}
