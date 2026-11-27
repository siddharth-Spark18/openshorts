import { useEffect, useState } from 'react';
import { apiFetch, apiJson } from '../lib/api';

export default function SourceChannels() {
  const [channels, setChannels] = useState(null);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const data = await apiJson('/api/source-channels');
    setChannels(data.channels);
  }

  useEffect(() => { refresh().catch(() => setError('Could not load channels.')); }, []);

  async function add(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await apiJson('/api/source-channels', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
      setUrl('');
      await refresh();
    } catch (e) { setError(e.detail || 'Could not add the channel.'); }
    finally { setBusy(false); }
  }

  async function remove(channel) {
    if (!window.confirm(`Remove ${channel.url} from your source list?`)) return;
    setBusy(true);
    setError('');
    try {
      const response = await apiFetch(`/api/source-channels/${channel.id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error();
      await refresh();
    } catch { setError('Could not remove the channel.'); }
    finally { setBusy(false); }
  }

  return <section className="max-w-4xl mx-auto p-4 sm:p-6 space-y-5">
    <h1 className="font-display text-3xl text-ink">Source channels</h1>
    <p className="text-sm text-muted">Add channels whose videos you own or have permission to republish. Automatic discovery is still being built.</p>
    <form onSubmit={add} className="flex flex-wrap gap-2">
      <label className="sr-only" htmlFor="source-channel-url">YouTube channel URL</label>
      <input id="source-channel-url" className="input-field flex-1 min-w-48" type="url"
        value={url} onChange={event => setUrl(event.target.value)}
        placeholder="https://www.youtube.com/@channel" required />
      <button className="btn-primary px-4 py-2" disabled={busy}>Add channel</button>
    </form>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!channels && !error && <p>Loading channels…</p>}
    {channels?.length === 0 && <p>No channels added yet.</p>}
    <div className="space-y-3">{channels?.map(channel =>
      <article key={channel.id} className="card p-4 flex flex-wrap items-center gap-3">
        <a href={channel.url} target="_blank" rel="noreferrer" className="flex-1 break-all text-ink">{channel.url}</a>
        <button className="btn-quiet px-3 py-2" disabled={busy} onClick={() => remove(channel)}>Remove</button>
      </article>)}</div>
  </section>;
}
