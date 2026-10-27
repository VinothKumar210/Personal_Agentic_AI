import { useState } from 'react';
import { ingestGithubRepo } from '../lib/api';

interface GithubRepoIngestionFormProps {
  onSuccess: () => void;
}

export default function GithubRepoIngestionForm({ onSuccess }: GithubRepoIngestionFormProps) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setMessage(null);

    try {
      const result = await ingestGithubRepo(url.trim(), title.trim());
      setMessage({ text: result.message || 'GitHub repo successfully ingested.', type: 'success' });
      setUrl('');
      setTitle('');
      onSuccess();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="github-ingestion-form card" style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#fff', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem' }}>Ingest GitHub Repo</h3>
      <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '1rem' }}>
        Provide a public GitHub repository URL (e.g. https://github.com/owner/repo).
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>Repository URL</label>
          <input 
            type="url" 
            placeholder="https://github.com/owner/repo" 
            value={url} 
            onChange={(e) => setUrl(e.target.value)} 
            required 
            disabled={loading}
            style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>Optional Title</label>
          <input 
            type="text" 
            placeholder="Custom title overrides repo name" 
            value={title} 
            onChange={(e) => setTitle(e.target.value)} 
            disabled={loading}
            style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
          />
        </div>
        <div>
          <button 
            type="submit" 
            disabled={loading || !url.trim()}
            className="primary-button"
            style={{ padding: '0.5rem 1rem', width: '100%' }}
          >
            {loading ? 'Ingesting...' : 'Ingest Repository'}
          </button>
        </div>
        {message && (
          <div style={{ 
            padding: '0.75rem', 
            borderRadius: '0.25rem', 
            fontSize: '0.875rem',
            backgroundColor: message.type === 'success' ? '#dcfce7' : '#fee2e2',
            color: message.type === 'success' ? '#166534' : '#b91c1c'
          }}>
            {message.text}
          </div>
        )}
      </form>
    </div>
  );
}
