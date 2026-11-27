import { useEffect, useState } from 'react';
import { apiFetch, apiJson } from '../lib/api';

export default function SourceChannels() {
  const [channels, setChannels] = useState(null);
  const [url, setUrl] = useState('');
  const [videos, setVideos] = useState([]);
  const [statisticsConfigured, setStatisticsConfigured] = useState(false);
  const [topics, setTopics] = useState('');
  const [topicMessage, setTopicMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [data, discovered] = await Promise.all([
      apiJson('/api/source-channels'), apiJson('/api/source-videos')
    ]);
    setChannels(data.channels);
    setVideos(discovered.videos);
    setStatisticsConfigured(discovered.statistics_configured);
    setError('');
  }

  useEffect(() => {
    apiJson('/api/source-topics').then(data => setTopics(data.topics))
      .catch(() => setError('Could not load your topics.'));
  }, []);

  async function saveTopics(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await apiJson('/api/source-topics', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topics }) });
      setTopicMessage('Topics saved.');
      await refresh();
    } catch (e) { setError(e.detail || 'Could not save topics.'); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    let active = true;
    const load = () => refresh().catch(() => { if (active) setError('Could not load channels.'); });
    load();
    const timer = setInterval(load, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);

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
    <p className="text-sm text-muted">Recent uploads are checked automatically. Discovering a video does not start processing or publishing it.</p>
    <form onSubmit={saveTopics} className="card p-4 space-y-3">
      <label htmlFor="source-topics" className="block text-sm text-ink">Topics to prioritize</label>
      <div className="flex flex-wrap gap-2">
        <input id="source-topics" className="input-field flex-1 min-w-48" value={topics}
          onChange={event => { setTopics(event.target.value); setTopicMessage(''); }}
          placeholder="GTA 6, gaming news" maxLength={500} />
        <button className="btn-ghost px-4 py-2" disabled={busy}>Save topics</button>
      </div>
      <p className="text-sm text-muted">Matches are based on video titles. Separate topics with commas.</p>
      {topicMessage && <p role="status" className="text-sm">{topicMessage}</p>}
    </form>
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
        <div className="flex-1 min-w-48">
          <a href={channel.url} target="_blank" rel="noreferrer" className="break-all text-ink">{channel.url}</a>
          <p className="text-sm text-muted mt-1">{channel.error || (channel.checked_at ? `Last checked ${new Date(channel.checked_at).toLocaleString()}` : 'Waiting for first check')}</p>
        </div>
        <button className="btn-quiet px-3 py-2" disabled={busy} onClick={() => remove(channel)}>Remove</button>
      </article>)}</div>
    <h2 className="font-display text-xl text-ink pt-3">Recent videos</h2>
    <p className="text-sm text-muted">Topic matches appear first, followed by average views per day when available. Videos under one day old use one day for the estimate.</p>
    {!statisticsConfigured && <p className="text-sm text-muted">Connect a YouTube Data API key to add view statistics.</p>}
    {videos.length === 0 && <p className="text-sm text-muted">No videos discovered yet.</p>}
    <div className="space-y-3">{videos.map(video =>
      <article key={video.video_id} className="card p-4">
        <a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noreferrer" className="text-ink">{video.title || 'Video'}</a>
        {video.topic_match && <span className="text-xs text-brass ml-2">Topic match</span>}
        <p className="text-sm text-muted mt-1">{video.channel_url} · {video.published_at ? new Date(video.published_at).toLocaleDateString() : 'Date unavailable'}{video.views_per_day != null && ` · ${video.views_per_day.toLocaleString()} views/day`}</p>
      </article>)}</div>
  </section>;
}
