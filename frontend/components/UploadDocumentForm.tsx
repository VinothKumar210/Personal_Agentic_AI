import { useState, useRef } from 'react';
import { uploadDocument } from '../lib/api';

export default function UploadDocumentForm({ onUploaded }: { onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [sourceUri, setSourceUri] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError('');
      setMessage('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file.');
      return;
    }
    
    setLoading(true);
    setMessage('');
    setError('');
    
    try {
      const result = await uploadDocument(file, title || undefined, sourceUri || undefined);
      if (result.document.status === 'failed') {
        setError(result.message || 'Ingestion failed.');
      } else {
        setMessage(result.message || 'File uploaded successfully.');
      }
      setFile(null);
      setTitle('');
      setSourceUri('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      onUploaded();
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="create-doc-form" onSubmit={handleSubmit}>
      <h3>Upload Document</h3>
      <div className="form-group">
        <label>File (.pdf, .docx, .md, .txt)</label>
        <input 
          type="file" 
          accept=".pdf,.docx,.md,.markdown,.txt" 
          onChange={handleFileChange}
          ref={fileInputRef}
          required 
        />
      </div>
      <div className="form-group">
        <label>Title (Optional)</label>
        <input 
          value={title} 
          onChange={e => setTitle(e.target.value)} 
          placeholder="Leave blank to use filename"
        />
      </div>
      <div className="form-group">
        <label>Source URI (Optional)</label>
        <input 
          value={sourceUri} 
          onChange={e => setSourceUri(e.target.value)} 
          placeholder="e.g. original URL or source path"
        />
      </div>
      <button type="submit" className="btn-primary" disabled={loading || !file}>
        {loading ? 'Uploading & Chunking...' : 'Upload'}
      </button>
      
      {message && <div className="status-message" style={{color: 'green', marginTop: '10px'}}>{message}</div>}
      {error && <div className="status-message" style={{color: 'red', marginTop: '10px'}}>{error}</div>}
    </form>
  );
}
