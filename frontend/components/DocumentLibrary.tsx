import { useEffect, useState } from 'react';
import {
  listDocuments,
  DocumentRead,
  deleteDocument,
  listDocumentChunks,
  reindexDocument,
  syncGithubRepo,
  listTags,
  createTag,
  attachTagToDocument,
  removeTagFromDocument,
} from '../lib/api';
import CreateDocumentForm from './CreateDocumentForm';
import UploadDocumentForm from './UploadDocumentForm';
import WebpageIngestionForm from './WebpageIngestionForm';
import GithubRepoIngestionForm from './GithubRepoIngestionForm';
import AiChatImportForm from './AiChatImportForm';
import OcrIngestionForm from './OcrIngestionForm';
import DocumentWorkspaceModal from './DocumentWorkspaceModal';

export default function DocumentLibrary() {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState<DocumentRead | null>(null);
  const [workspaceDoc, setWorkspaceDoc] = useState<DocumentRead | null>(null);
  const [ingestionType, setIngestionType] = useState<'file' | 'webpage' | 'github' | 'aichat' | 'ocr'>('file');
  const [chunks, setChunks] = useState<any[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [syncingRepo, setSyncingRepo] = useState(false);

  const [syncMsg, setSyncMsg] = useState<{type: 'error'|'success', text: string} | null>(null);

  const handleSyncRepo = async (docId: string) => {
    setSyncingRepo(true);
    setSyncMsg(null);
    try {
      await syncGithubRepo(docId);
      setSyncMsg({type: 'success', text: 'GitHub repository delta-sync job queued successfully! Unchanged files will be skipped.'});
      fetchDocs();
    } catch (err: any) {
      setSyncMsg({type: 'error', text: `Error syncing repository: ${err.message}`});
    } finally {
      setSyncingRepo(false);
    }
  };
  const [reindexMsg, setReindexMsg] = useState('');
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState('');
  const [tagSaving, setTagSaving] = useState(false);
  const [tagError, setTagError] = useState<string | null>(null);

  const handleGenerateSummary = async () => {
    if (!selectedDoc) return;
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const { generateDocumentSummary } = await import('../lib/api');
      const res = await generateDocumentSummary(selectedDoc.id);
      setSelectedDoc(prev => prev ? { ...prev, summary: res.summary } : null);
      fetchDocs();
    } catch (err: any) {
      setSummaryError(err.message);
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleReindex = async () => {
    if (!selectedDoc) return;
    setReindexing(true);
    setReindexMsg('');
    try {
      const res = await reindexDocument(selectedDoc.id);
      setReindexMsg(`Success: Indexed ${res.indexed_count}, Failed: ${res.failed_count}`);
      fetchChunks(selectedDoc.id);
    } catch (err: any) {
      setReindexMsg(`Error: ${err.message}`);
    } finally {
      setReindexing(false);
    }
  };
  async function fetchDocs() {
    setLoading(true);
    try {
      const data = await listDocuments();
      setDocuments(data.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDocs();
  }, []);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    const hasProcessing = documents.some(doc => doc.status === 'processing');
    
    if (hasProcessing) {
      intervalId = setInterval(async () => {
        try {
          const data = await listDocuments();
          setDocuments(data.items);
        } catch (err) {
          console.error(err);
        }
      }, 3000);
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [documents]);

  async function fetchChunks(id: string) {
    setChunksLoading(true);
    try {
      const data = await listDocumentChunks(id);
      setChunks(data.items);
      setTotalChunks(data.total);
    } catch (err) {
      console.error(err);
      setChunks([]);
      setTotalChunks(0);
    } finally {
      setChunksLoading(false);
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteDocument(id);
    if (selectedDoc?.id === id) setSelectedDoc(null);
    fetchDocs();
  };

  const applyUpdatedDocument = (updated: DocumentRead) => {
    setSelectedDoc(updated);
    setDocuments((prev) => prev.map((doc) => doc.id === updated.id ? updated : doc));
  };

  const normalizeTagName = (name: string) => name.trim().toLowerCase().replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ');

  const handleAddTag = async () => {
    if (!selectedDoc || !tagInput.trim()) return;
    setTagSaving(true);
    setTagError(null);
    try {
      const desiredName = tagInput.trim();
      const existingTags = await listTags();
      let tag = existingTags.find((t: any) => normalizeTagName(t.name) === normalizeTagName(desiredName));
      if (!tag) {
        try {
          tag = await createTag({ name: desiredName });
        } catch (err: any) {
          if (!String(err.message || '').includes('409')) throw err;
          const refreshedTags = await listTags();
          tag = refreshedTags.find((t: any) => normalizeTagName(t.name) === normalizeTagName(desiredName));
        }
      }
      if (!tag) throw new Error('Could not find or create tag');
      const updated = await attachTagToDocument(tag.id, selectedDoc.id);
      applyUpdatedDocument(updated);
      setTagInput('');
    } catch (err: any) {
      setTagError(err.message || 'Failed to add tag');
    } finally {
      setTagSaving(false);
    }
  };

  const handleRemoveTag = async (tagId: string) => {
    if (!selectedDoc) return;
    setTagSaving(true);
    setTagError(null);
    try {
      const updated = await removeTagFromDocument(tagId, selectedDoc.id);
      applyUpdatedDocument(updated);
    } catch (err: any) {
      setTagError(err.message || 'Failed to remove tag');
    } finally {
      setTagSaving(false);
    }
  };

  return (
    <div className="document-library">
      <h2>Document Library</h2>
      <p className="subtitle">Manage metadata records and file uploads for your ingested documents.</p>

      <div className="library-layout">
        <div className="sidebar" style={{ width: '300px', borderRight: '1px solid var(--border-color)', padding: '1rem', overflowY: 'auto' }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Ingest Content</h2>
          
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <button 
              onClick={() => setIngestionType('file')} 
              style={{ flex: 1, minWidth: '45%', padding: '0.5rem', fontSize: '0.875rem', border: '1px solid var(--border-color)', backgroundColor: ingestionType === 'file' ? 'var(--surface-light)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer', borderRadius: '0.25rem' }}
            >File Upload</button>
            <button 
              onClick={() => setIngestionType('webpage')} 
              style={{ flex: 1, minWidth: '45%', padding: '0.5rem', fontSize: '0.875rem', border: '1px solid var(--border-color)', backgroundColor: ingestionType === 'webpage' ? 'var(--surface-light)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer', borderRadius: '0.25rem' }}
            >Webpage</button>
            <button 
              onClick={() => setIngestionType('github')} 
              style={{ flex: 1, minWidth: '45%', padding: '0.5rem', fontSize: '0.875rem', border: '1px solid var(--border-color)', backgroundColor: ingestionType === 'github' ? 'var(--surface-light)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer', borderRadius: '0.25rem' }}
            >GitHub Repo</button>
            <button 
              onClick={() => setIngestionType('aichat')} 
              style={{ flex: 1, minWidth: '45%', padding: '0.5rem', fontSize: '0.875rem', border: '1px solid var(--border-color)', backgroundColor: ingestionType === 'aichat' ? 'var(--surface-light)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer', borderRadius: '0.25rem' }}
            >AI Chat</button>
            <button 
              onClick={() => setIngestionType('ocr')} 
              style={{ flex: 1, minWidth: '45%', padding: '0.5rem', fontSize: '0.875rem', border: '1px solid var(--border-color)', backgroundColor: ingestionType === 'ocr' ? 'var(--surface-light)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer', borderRadius: '0.25rem' }}
            >OCR (Image/PDF)</button>
          </div>

          {ingestionType === 'file' ? (
            <UploadDocumentForm onUploaded={fetchDocs} />
          ) : ingestionType === 'webpage' ? (
            <WebpageIngestionForm onSuccess={fetchDocs} />
          ) : ingestionType === 'github' ? (
            <GithubRepoIngestionForm onSuccess={fetchDocs} />
          ) : ingestionType === 'aichat' ? (
            <AiChatImportForm onSuccess={fetchDocs} />
          ) : (
            <OcrIngestionForm onSuccess={fetchDocs} />
          )}
          
          <hr style={{ margin: '2rem 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />
          <CreateDocumentForm onCreated={fetchDocs} />
        </div>
        <div className="doc-list">
          {loading ? (
            <p>Loading documents...</p>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <p>No documents found. Upload a file or create a metadata record above.</p>
            </div>
          ) : (
            <table className="doc-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className={selectedDoc?.id === doc.id ? 'selected-row' : ''}
                  >
                    <td>
                      <div>
                        <strong>{doc.title}</strong>
                      </div>
                      {doc.tags && doc.tags.length > 0 && (
                        <div style={{ marginTop: '4px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {doc.tags.map((tag: any) => (
                            <span key={tag.id} style={{ fontSize: '0.7rem', backgroundColor: 'var(--surface-light)', color: 'var(--text-primary)', padding: '2px 6px', borderRadius: '4px' }}>
                              {tag.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td><span className="badge type-badge">{doc.source_type}</span></td>
                    <td>
                      <span className={`badge status-${doc.status}`} style={{
                        backgroundColor: doc.status === 'failed' ? '#fee2e2' : undefined,
                        color: doc.status === 'failed' ? '#ef4444' : undefined,
                        border: doc.status === 'failed' ? '1px solid #fca5a5' : undefined
                      }}>
                        {doc.status}
                      </span>
                      {doc.status === 'failed' && doc.error_message && (
                        <div style={{ fontSize: '0.65rem', color: '#ef4444', marginTop: '0.25rem', maxWidth: '150px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={doc.error_message}>
                          {doc.error_message}
                        </div>
                      )}
                    </td>
                    <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td>
                      <button onClick={(e) => handleDelete(doc.id, e)} className="btn-delete">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selectedDoc && (
          <div className="doc-detail-panel" style={{ width: '400px', overflowY: 'auto', maxHeight: '800px' }}>
            <h3>Document Details</h3>
            <button
              onClick={() => setWorkspaceDoc(selectedDoc)}
              className="btn-primary"
              style={{
                width: '100%',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
            >
              💬 Chat & Annotate Document
            </button>
            {selectedDoc.source_type === 'github_repo' && (
              <div style={{ marginBottom: '1rem' }}>
                <button
                  onClick={() => handleSyncRepo(selectedDoc.id)}
                  disabled={syncingRepo}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    backgroundColor: '#10b981',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '0.375rem',
                    fontWeight: 600,
                    cursor: syncingRepo ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem'
                  }}
                >
                  {syncingRepo ? '⏳ Queueing Sync...' : '🔄 Delta-Sync Repository'}
                </button>
                {syncMsg && (
                  <div style={{ marginTop: '0.5rem', padding: '0.5rem', borderRadius: '0.25rem', fontSize: '0.75rem', backgroundColor: syncMsg.type === 'error' ? '#fee2e2' : '#dcfce7', color: syncMsg.type === 'error' ? '#b91c1c' : '#15803d' }}>
                    {syncMsg.text}
                  </div>
                )}
              </div>
            )}
            <div className="detail-item"><strong>ID:</strong> {selectedDoc.id}</div>
            <div className="detail-item"><strong>Title:</strong> {selectedDoc.title}</div>
            <div className="detail-item"><strong>Type:</strong> {selectedDoc.source_type}</div>
            <div className="detail-item"><strong>Status:</strong> {selectedDoc.status}</div>
            {selectedDoc.source_uri && <div className="detail-item"><strong>URI:</strong> {selectedDoc.source_uri}</div>}
            {selectedDoc.original_filename && <div className="detail-item"><strong>Filename:</strong> {selectedDoc.original_filename}</div>}
            {selectedDoc.error_message && <div className="detail-item status-message error"><strong>Error:</strong> {selectedDoc.error_message}</div>}
            <div className="detail-item"><strong>Created:</strong> {new Date(selectedDoc.created_at).toLocaleString()}</div>
            <div className="detail-item"><strong>Updated:</strong> {new Date(selectedDoc.updated_at).toLocaleString()}</div>

            <div className="detail-section">
              <strong>Collections:</strong>
              {selectedDoc.collections && selectedDoc.collections.length > 0 ? (
                <ul>{selectedDoc.collections.map(c => <li key={c.id}>{c.name}</li>)}</ul>
              ) : <span> None</span>}
            </div>

            <div className="detail-section">
              <strong>Tags:</strong>
              {selectedDoc.tags && selectedDoc.tags.length > 0 ? (
                <div className="tag-list" style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                  {selectedDoc.tags.map(t => (
                    <span key={t.id} className="badge type-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      {t.name}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(t.id)}
                        disabled={tagSaving}
                        aria-label={`Remove ${t.name}`}
                        title={`Remove ${t.name}`}
                        style={{ border: 'none', background: 'transparent', cursor: tagSaving ? 'not-allowed' : 'pointer', color: 'inherit', padding: 0, lineHeight: 1 }}
                      >
                        x
                      </button>
                    </span>
                  ))}
                </div>
              ) : <span> None</span>}
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                  placeholder="Add tag"
                  disabled={tagSaving}
                  style={{ flex: 1, minWidth: 0, padding: '0.4rem 0.5rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem', fontSize: '0.8125rem', backgroundColor: 'var(--surface-light)', color: 'var(--text-primary)' }}
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  disabled={tagSaving || !tagInput.trim()}
                  className="btn-primary"
                  style={{ padding: '0.4rem 0.65rem', borderRadius: '0.25rem', fontSize: '0.8125rem', height: 'auto' }}
                >
                  Add
                </button>
              </div>
              {tagError && <div style={{ color: 'var(--status-error-text)', fontSize: '0.75rem', marginTop: '0.375rem' }}>{tagError}</div>}
            </div>

            <div className="detail-section summary-section" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>Document Summary</h4>
                <button 
                  onClick={handleGenerateSummary} 
                  disabled={summaryLoading || totalChunks === 0}
                  className="btn-primary"
                  style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', height: 'auto', opacity: summaryLoading || totalChunks === 0 ? 0.5 : 1 }}
                >
                  {summaryLoading ? 'Generating...' : 'Generate Summary'}
                </button>
              </div>
              
              {summaryError && <div style={{ color: 'var(--status-error-text)', fontSize: '0.75rem', marginBottom: '0.5rem' }}>Error: {summaryError}</div>}
              
              {selectedDoc.summary ? (
                <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', backgroundColor: 'var(--surface-light)', padding: '0.75rem', borderRadius: '0.375rem', border: '1px solid var(--border-color)' }}>
                  {selectedDoc.summary}
                </div>
              ) : (
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>No summary generated yet.</p>
              )}
            </div>

            <div className="detail-section chunks-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4>Extracted Chunks</h4>
                {totalChunks > 0 && (
                  <button onClick={handleReindex} disabled={reindexing} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', cursor: 'pointer', backgroundColor: 'transparent', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
                    {reindexing ? 'Reindexing...' : 'Reindex Document'}
                  </button>
                )}
              </div>
              {reindexMsg && <div style={{ fontSize: '0.75rem', color: reindexMsg.startsWith('Error') ? 'var(--status-error-text)' : 'var(--status-ok-text)', marginBottom: '0.5rem' }}>{reindexMsg}</div>}
              {chunksLoading ? (
                <p>Loading chunks...</p>
              ) : chunks.length === 0 ? (
                <p>No chunks available yet.</p>
              ) : (
                <div className="chunks-list">
                  <p className="chunk-count">Total Chunks: {totalChunks}</p>
                  {chunks.slice(0, 5).map(chunk => (
                    <div key={chunk.id} className="chunk-preview" style={{ padding: '0.5rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem', marginBottom: '0.5rem', backgroundColor: 'var(--surface-light)' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                        Chunk {chunk.chunk_index} ({chunk.character_count} chars) - <span style={{ color: chunk.embedding_status === 'indexed' ? 'var(--status-ok-text)' : chunk.embedding_status === 'failed' ? 'var(--status-error-text)' : 'var(--text-secondary)' }}>{chunk.embedding_status}</span>
                        {chunk.embedding_error && <div style={{ color: 'var(--status-error-text)', marginTop: '0.125rem' }}>{chunk.embedding_error}</div>}
                      </div>
                      <div style={{ fontSize: '0.875rem', whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                        {chunk.text.substring(0, 150)}{chunk.text.length > 150 ? '...' : ''}
                      </div>
                    </div>
                  ))}
                  {totalChunks > 5 && (
                    <p style={{ fontSize: '0.75rem', color: '#64748b', textAlign: 'center' }}>+ {totalChunks - 5} more chunks</p>
                  )}
                </div>
              )}
            </div>

            <button className="btn-close-detail" onClick={() => setSelectedDoc(null)}>Close</button>
          </div>
        )}

        {workspaceDoc && (
          <DocumentWorkspaceModal
            document={workspaceDoc}
            onClose={() => setWorkspaceDoc(null)}
          />
        )}
      </div>
    </div>
  );
}
