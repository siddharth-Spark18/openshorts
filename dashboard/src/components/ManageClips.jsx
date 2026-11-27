import { useEffect, useState } from 'react';
import { Download, Trash2 } from 'lucide-react';
import { apiFetch, apiJson } from '../lib/api';
import { getApiUrl } from '../config';

export default function ManageClips() {
  const [clips, setClips] = useState(null);
  const [error, setError] = useState('');
  const [removing, setRemoving] = useState(false);
  useEffect(() => {
    let active = true;
    apiJson('/api/library').then(rows => { if (active) setClips(rows); })
      .catch(e => { if (active) setError(e.detail || 'Could not load your clips.'); });
    return () => { active = false; };
  }, []);

  async function remove(clip, url) {
    if (!window.confirm(`Delete “${clip.title}” from the app library? Any Google Drive backup will remain in Drive.`)) return;
    setRemoving(true);
    setError('');
    try {
      const response = await apiFetch(url, { method: 'DELETE' });
      if (!response.ok && response.status !== 404) throw new Error('Could not delete this clip.');
      setClips(rows => rows.filter(row => row !== clip));
    } catch (e) { setError(e.message); }
    finally { setRemoving(false); }
  }

  return <section className="max-w-4xl mx-auto space-y-4">
    <h1 className="font-display text-3xl text-ink">Manage clips</h1>
    {error && <p role="alert">{error}</p>}
    {!clips && !error && <p role="status">Loading clips…</p>}
    {clips?.length === 0 && <p>Finished clips will appear here when your first video is processed.</p>}
    {clips?.map(clip => {
      const url = `/api/library/${clip.job_id}/${clip.index}`;
      return <article key={url} className="card p-4 flex flex-wrap items-center gap-3">
        <h2 className="flex-1 min-w-40 break-words text-ink">{clip.title}</h2>
        <a href={getApiUrl(url)} download className="btn-ghost inline-flex items-center gap-2 px-3 py-2"><Download size={16}/>Download</a>
        <button disabled={removing} onClick={() => remove(clip, url)} className="btn-quiet inline-flex items-center gap-2 px-3 py-2"><Trash2 size={16}/>Delete</button>
      </article>;
    })}
  </section>;
}
