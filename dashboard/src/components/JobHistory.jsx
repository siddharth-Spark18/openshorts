import { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

export default function JobHistory({ onOpen, onRetry }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await apiJson('/api/jobs');
        if (active) { setJobs(data.jobs); setError(''); }
      } catch {
        if (active) setError('Could not load project history.');
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  async function open(jobId) {
    setOpening(jobId);
    setError('');
    try { await onOpen(jobId); }
    catch { setError('Could not open this project. Its working files may have expired.'); }
    finally { setOpening(null); }
  }

  async function retry(jobId) {
    setOpening(jobId);
    setError('');
    try {
      await apiJson(`/api/jobs/${jobId}/retry`, { method: 'POST' });
      await onRetry(jobId);
    } catch (e) { setError(e.detail || 'Could not retry this project.'); }
    finally { setOpening(null); }
  }

  return <section className="max-w-4xl mx-auto space-y-5">
    <h1 className="font-display text-3xl text-ink">Project history</h1>
    <p className="text-sm text-muted">Start another video while your existing jobs continue processing.</p>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!jobs && !error && <p role="status">Loading projects…</p>}
    {jobs?.length === 0 && <p>Your submitted videos will appear here.</p>}
    <div className="space-y-3">
      {jobs?.map(job => <article key={job.job_id} className="card p-4 flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-48">
          <h2 className="text-ink break-all">{job.input_source || 'Video project'}</h2>
          <p className="text-sm text-muted mt-1">{job.status} · {new Date(job.created_at).toLocaleString()}
            {job.clip_count != null && ` · ${job.clip_count} clips`}
          </p>
          {!job.available && <p className="text-sm text-muted mt-1">{job.archived ? 'Saved clips are in Manage clips.' : job.status === 'failed' ? 'This job failed and its working files are unavailable.' : 'Working files are no longer available.'}</p>}
        </div>
        {job.retryable && <button className="btn-primary px-4 py-2" disabled={!!opening} onClick={() => retry(job.job_id)}>
          {opening === job.job_id ? 'Starting…' : 'Retry'}
        </button>}
        {job.available && <button className="btn-ghost px-4 py-2" disabled={!!opening} onClick={() => open(job.job_id)}>
          {opening === job.job_id ? 'Opening…' : 'Open'}
        </button>}
      </article>)}
    </div>
  </section>;
}
