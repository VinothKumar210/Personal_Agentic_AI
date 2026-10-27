import { useState } from 'react';
import { importAiChat } from '../lib/api';

interface AiChatImportFormProps {
  onSuccess: () => void;
}

export default function AiChatImportForm({ onSuccess }: AiChatImportFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const allowedExtensions = ['.json', '.md', '.txt'];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    // Validate extension
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setMessage({ text: `Unsupported file extension for AI Chat Import: ${ext}`, type: 'error' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const result = await importAiChat(file, title.trim());
      setMessage({ text: result.message || 'AI Chat successfully imported.', type: 'success' });
      setFile(null);
      setTitle('');
      // Reset file input
      const fileInput = document.getElementById('chat-file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
      onSuccess();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-import-form card" style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#fff', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem' }}>Import AI Chat</h3>
      <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '1rem' }}>
        Upload an exported chat conversation (.json, .md, .txt) from ChatGPT, Claude, or generic tools.
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>Chat File</label>
          <input 
            id="chat-file-input"
            type="file" 
            accept=".json,.md,.txt"
            onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)} 
            required 
            disabled={loading}
            style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>Optional Title</label>
          <input 
            type="text" 
            placeholder="Custom title overrides filename" 
            value={title} 
            onChange={(e) => setTitle(e.target.value)} 
            disabled={loading}
            style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
          />
        </div>
        <div>
          <button 
            type="submit" 
            disabled={loading || !file}
            className="primary-button"
            style={{ padding: '0.5rem 1rem', width: '100%' }}
          >
            {loading ? 'Importing...' : 'Import Chat'}
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
