// Configuration for API endpoints
// If VITE_API_URL is set (e.g. in production), use it.
// Otherwise, default to empty string which means relative paths (proxied in dev).

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Cloud: /videos and /thumbnails answer only to their owner. A <video> or
// <img> cannot send the Authorization header, so the app fetches a short-lived
// media token (/api/media-token, see lib/mediaToken.js) and every media URL
// built here carries it as ?mt=. Self-host never sets one.
let mediaToken = '';
export const setMediaToken = (token) => { mediaToken = token || ''; };

const MEDIA_PREFIXES = ['/videos/', '/thumbnails/'];

// Append a query parameter whether or not the URL already has a query.
export const withParam = (url, key, value) => {
    if (!url) return url;
    const [base, hash] = url.split('#');
    const sep = base.includes('?') ? '&' : '?';
    return `${base}${sep}${encodeURIComponent(key)}=${encodeURIComponent(value)}${hash !== undefined ? `#${hash}` : ''}`;
};

export const getApiUrl = (path) => {
    if (path.startsWith('http')) return path;
    // Ensure path starts with / if not present
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${API_BASE_URL}${normalizedPath}`;
    if (mediaToken && MEDIA_PREFIXES.some((p) => normalizedPath.startsWith(p))
        && !/[?&](mt|sig)=/.test(normalizedPath)) {
        return withParam(url, 'mt', mediaToken);
    }
    return url;
};
