import { useState } from 'react';
import { createDocument } from '../lib/api';

export default function CreateDocumentForm({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState('');
  const [sourceType, setSourceType] = useState('text');
  const [sourceUri, setSourceUri] = useState('');
  const [originalFilename, setOriginalFilename] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title) return;
    
    try {
      await createDocument({
        title,
        source_type: sourceType,
        source_uri: sourceUri || undefined,
        original_filename: originalFilename || undefined
      });
      setTitle('');
      setSourceUri('');
      setOriginalFilename('');
      onCreated();
    } catch (err) {
      console.error('Failed to create document', err);
    }
  };

  return (
    <form className="create-doc-form" onSubmit={handleSubmit}>
      <h3>Create Metadata Record</h3>
      <div className="form-group">
        <label>Title</label>
        <input value={title} onChange={e => setTitle(e.target.value)} required />
      </div>
      <div className="form-group">
        <label>Source Type</label>
        <select value={sourceType} onChange={e => setSourceType(e.target.value)}>
          <option value="pdf">PDF</option>
          <option value="docx">DOCX</option>
          <option value="markdown">Markdown</option>
          <option value="text">Text</option>
          <option value="webpage">Webpage</option>
        </select>
      </div>
      <div className="form-group">
        <label>Source URI (Optional)</label>
        <input value={sourceUri} onChange={e => setSourceUri(e.target.value)} />
      </div>
      <div className="form-group">
        <label>Original Filename (Optional)</label>
        <input value={originalFilename} onChange={e => setOriginalFilename(e.target.value)} />
      </div>
      <button type="submit" className="btn-primary">Create Record</button>
    </form>
  );
}
