'use client';

import { useState } from 'react';
import { ingestOcrDocument } from '../lib/api';

interface OcrIngestionFormProps {
  onSuccess: () => void;
}

export default function OcrIngestionForm({ onSuccess }: OcrIngestionFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    try {
      const response = await ingestOcrDocument(file, title);
      if (response.document?.status === 'failed') {
          setError(response.message || 'OCR ingestion failed internally.');
      } else {
          setFile(null);
          setTitle('');
          onSuccess();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to ingest OCR document');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="ingestion-form" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '0.5rem' }}>
        Extract text from images (PNG, JPG, WEBP, TIFF) and scanned PDFs using local OCR.
      </p>

      {error && <div style={{ color: 'red', fontSize: '0.875rem' }}>{error}</div>}
      
      <div>
        <label style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Image or Scanned PDF</label>
        <input 
          type="file" 
          accept=".png,.jpg,.jpeg,.webp,.tif,.tiff,.pdf" 
          onChange={(e) => setFile(e.target.files?.[0] || null)} 
          disabled={loading}
          style={{ width: '100%', fontSize: '0.875rem' }}
          required
        />
      </div>

      <div>
        <label style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Title (Optional)</label>
        <input 
          type="text" 
          value={title} 
          onChange={(e) => setTitle(e.target.value)} 
          placeholder="e.g., Scanned Invoice" 
          disabled={loading}
          style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
        />
      </div>

      <button 
        type="submit" 
        disabled={!file || loading}
        style={{ padding: '0.5rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '0.25rem', cursor: loading || !file ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}
      >
        {loading ? 'Processing OCR...' : 'Extract Text & Index'}
      </button>
    </form>
  );
}
