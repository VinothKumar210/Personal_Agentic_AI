'use client';
import { useState } from 'react';
import { searchKnowledge } from '../lib/api';

export default function SemanticSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const data = await searchKnowledge(query);
      setResults(data.results || []);
    } catch (err: any) {
      setError(err.message || 'An error occurred during search.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="semantic-search" style={{ padding: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#fff', marginBottom: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem', color: '#0f172a' }}>Semantic Search</h2>
      <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '1.25rem' }}>Search indexed chunks using local embeddings.</p>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter search query..."
          style={{ flex: 1, padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '0.375rem', fontSize: '0.875rem', outline: 'none' }}
          disabled={loading}
        />
        <button 
          type="submit" 
          disabled={loading || !query.trim()}
          style={{ padding: '0.75rem 1.5rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '0.375rem', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500, opacity: (loading || !query.trim()) ? 0.7 : 1 }}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '0.875rem', padding: '0.75rem', backgroundColor: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '0.375rem' }}>{error}</div>}

      <div className="search-results">
        {!loading && !error && results.length === 0 && query && (
          <p style={{ color: '#64748b', fontSize: '0.875rem', textAlign: 'center', padding: '2rem 0' }}>No retrieved chunks found.</p>
        )}
        
        {results.map((result, idx) => (
          <div key={`${result.chunk_id}-${idx}`} style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.375rem', marginBottom: '1rem', backgroundColor: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{result.document_title}</span>
              <span style={{ color: '#64748b' }}>Score: {result.score ? result.score.toFixed(4) : 'N/A'}</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <span style={{ backgroundColor: '#e2e8f0', padding: '0.25rem 0.5rem', borderRadius: '0.25rem', fontWeight: 500 }}>{result.source_type}</span>
              <span>Chunk: {result.chunk_index}</span>
              {result.original_filename && <span>File: {result.original_filename}</span>}
              {result.source_uri && <span>URI: {result.source_uri}</span>}
            </div>
            <div style={{ fontSize: '0.875rem', whiteSpace: 'pre-wrap', lineHeight: 1.6, color: '#334155' }}>
              {result.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
