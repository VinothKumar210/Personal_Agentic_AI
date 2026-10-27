import { useState } from 'react';
import { ingestWebpage } from '../lib/api';

interface WebpageIngestionFormProps {
  onSuccess: () => void;
}

export default function WebpageIngestionForm({ onSuccess }: WebpageIngestionFormProps) {
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
      const result = await ingestWebpage(url.trim(), title.trim());
      setMessage({ text: result.message || 'Webpage successfully ingested.', type: 'success' });
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
    <div className="webpage-ingestion-form card" style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#fff', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem' }}>Ingest Webpage</h3>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>URL</label>
          <input 
            type="url" 
            placeholder="https://example.com/article" 
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
            placeholder="Custom title overrides page title" 
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
            {loading ? 'Ingesting...' : 'Ingest Webpage'}
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
