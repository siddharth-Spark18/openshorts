import { useEffect, useState } from 'react';
import { apiFetch, apiJson } from '../lib/api';

export default function YoutubeCookies() {
  const [configured, setConfigured] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiJson('/api/youtube-cookies').then(data => setConfigured(data.configured))
      .catch(() => setMessage('Could not check YouTube cookies.'));
  }, []);

  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setBusy(true);
    setMessage('');
    try {
      const form = new FormData();
      form.append('file', file);
      const data = await apiJson('/api/youtube-cookies', { method: 'PUT', body: form });
      setConfigured(data.configured);
      setMessage('Cookies saved. Try the YouTube link again.');
    } catch (error) { setMessage(error.detail || 'Could not save cookies.'); }
    finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true);
    try {
      const response = await apiFetch('/api/youtube-cookies', { method: 'DELETE' });
      if (!response.ok) throw new Error();
      setConfigured(false);
      setMessage('Cookies removed.');
    } catch { setMessage('Could not remove cookies.'); }
    finally { setBusy(false); }
  }

  return <section className="card p-4 sm:p-6 mb-8 space-y-3">
    <h2 className="font-display text-lg text-ink">YouTube connection</h2>
    <p className="text-sm text-muted">Upload a Netscape-format YouTube cookies file if YouTube asks the server to sign in. Cookies stay on your server.</p>
    <p className="text-sm">{configured ? 'Cookies saved' : 'No cookies saved'}</p>
    <div className="flex gap-3 flex-wrap">
      <label className="btn-ghost px-4 py-2 cursor-pointer">{configured ? 'Replace cookies' : 'Upload cookies'}
        <input type="file" accept=".txt,text/plain" className="sr-only" disabled={busy} onChange={upload} />
      </label>
      {configured && <button className="btn-quiet px-4 py-2" disabled={busy} onClick={remove}>Remove</button>}
    </div>
    {message && <p role="status" className="text-sm">{message}</p>}
  </section>;
}
