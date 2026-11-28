// Short-lived token that lets this browser load its own /videos and
// /thumbnails files (cloud mode). getApiUrl appends it to media URLs; the
// same call also sets it as an HttpOnly cookie on the API host, which covers
// players whose URL was built with a token that has since been refreshed.
import { apiFetch } from './api';
import { setMediaToken } from '../config';

const STORAGE_KEY = 'openshorts_media_token';
// Renew this long before it expires, so a URL built now outlives the page.
const RENEW_MARGIN_MS = 2 * 60 * 60 * 1000;
let renewTimer = null;
let cookieRefreshed = false;

const readCached = (userId) => {
  try {
    const cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (cached?.token && String(cached.token).startsWith(`${userId}.`)
        && cached.expires_at * 1000 - Date.now() > RENEW_MARGIN_MS) {
      return cached;
    }
  } catch (_) { /* ignore */ }
  return null;
};

const schedule = (userId, expiresAt) => {
  if (renewTimer) clearTimeout(renewTimer);
  const wait = Math.max(60 * 1000, expiresAt * 1000 - Date.now() - RENEW_MARGIN_MS);
  renewTimer = setTimeout(() => { ensureMediaToken(userId, true); }, wait);
};

export async function ensureMediaToken(userId, force = false) {
  if (!userId) return '';
  const cached = force ? null : readCached(userId);
  if (cached) {
    setMediaToken(cached.token);
    schedule(userId, cached.expires_at);
    // Refresh the cookie once per page (a new browser session may have dropped it).
    if (!cookieRefreshed) {
      cookieRefreshed = true;
      apiFetch('/api/media-token', { method: 'POST', credentials: 'include' }).catch(() => {});
    }
    return cached.token;
  }
  try {
    const res = await apiFetch('/api/media-token', { method: 'POST', credentials: 'include' });
    if (!res.ok) return '';
    const data = await res.json();
    if (!data?.token) return '';
    setMediaToken(data.token);
    cookieRefreshed = true;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: data.token, expires_at: data.expires_at }));
    } catch (_) { /* ignore */ }
    schedule(userId, data.expires_at);
    return data.token;
  } catch (_) {
    return '';
  }
}

export function clearMediaToken() {
  if (renewTimer) clearTimeout(renewTimer);
  renewTimer = null;
  cookieRefreshed = false;
  setMediaToken('');
  try { localStorage.removeItem(STORAGE_KEY); } catch (_) { /* ignore */ }
}
