'use client';
import { useState, useEffect } from 'react';
import {
  DocumentRead,
  listDocumentChunks,
  listDocumentNotes,
  createChunkNote,
  deleteChunkNote,
  NoteRead,
  streamKnowledgeBase,
  saveWebResultToKb,
  generateFlashcards,
  approveFlashcard,
  startDeepResearch,
  getRagJobStatus
} from '../lib/api';

interface DocumentWorkspaceModalProps {
  document: DocumentRead;
  onClose: () => void;
}

export default function DocumentWorkspaceModal({ document, onClose }: DocumentWorkspaceModalProps) {
  // Left pane: Chat with Document state
  const [question, setQuestion] = useState('');
  const [qaConfidenceMode, setQaConfidenceMode] = useState<string>('balanced');
  const [qaAnswer, setQaAnswer] = useState('');
  const [qaCitations, setQaCitations] = useState<any[]>([]);
  const [qaActionRequired, setQaActionRequired] = useState<any | null>(null);
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const [savedCitIds, setSavedCitIds] = useState<Record<number, boolean>>({});
  const [qaResearchMode, setQaResearchMode] = useState(false);
  const [qaResearchSteps, setQaResearchSteps] = useState<any[]>([]);
  const [showQaAuditTrail, setShowQaAuditTrail] = useState(false);

  // Right pane: Chunks & Notes state
  const [chunks, setChunks] = useState<any[]>([]);
  const [notes, setNotes] = useState<NoteRead[]>([]);
  const [chunksLoading, setChunksLoading] = useState(true);
  const [chunkFilter, setChunkFilter] = useState('');
  const [activeChunkIdForNote, setActiveChunkIdForNote] = useState<string | null>(null);
  const [newNoteText, setNewNoteText] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  // Flashcards state
  const [flashcardsDraft, setFlashcardsDraft] = useState<any[]>([]);
  const [generatingFlashcards, setGeneratingFlashcards] = useState(false);
  const [flashcardError, setFlashcardError] = useState<string | null>(null);

  useEffect(() => {
    fetchChunksAndNotes();
  }, [document.id]);

  async function fetchChunksAndNotes() {
    setChunksLoading(true);
    setNoteError(null);
    try {
      const [chunksData, notesData] = await Promise.all([
        listDocumentChunks(document.id),
        listDocumentNotes(document.id)
      ]);
      setChunks(chunksData.items || []);
      setNotes(notesData || []);
    } catch (err: any) {
      setNoteError(err.message || 'Failed to load document chunks or notes.');
    } finally {
      setChunksLoading(false);
    }
  }

  async function handleAskQuestion(e: React.FormEvent, overrideMode?: string, fallbackAction?: string) {
    if (e && e.preventDefault) e.preventDefault();
    if (!question.trim() || qaLoading) return;

    const modeToUse = overrideMode || qaConfidenceMode;
    if (overrideMode) setQaConfidenceMode(overrideMode);

    setQaLoading(true);
    setQaError(null);
    setQaActionRequired(null);
    setQaAnswer('');
    setQaCitations([]);
    setQaResearchSteps([]);

    // Trigger deep research background job
    if (qaResearchMode || fallbackAction === 'autonomous_research') {
      try {
        const job = await startDeepResearch(question);
        pollQaJobStatus(job.id);
      } catch (err: any) {
        setQaError(err.message || 'Failed to start deep research');
        setQaLoading(false);
      }
      return;
    }

    try {
      await streamKnowledgeBase(
        question,
        (citations) => {
          setQaCitations(citations);
        },
        (token) => {
          setQaAnswer((prev) => prev + token);
        },
        (errMsg) => {
          setQaError(errMsg);
          setQaLoading(false);
        },
        () => {
          setQaLoading(false);
        },
        undefined,
        document.id,
        modeToUse,
        (actionData) => {
          setQaActionRequired(actionData);
        },
        fallbackAction,
        false, // streamKnowledgeBase no longer runs deep research
        2,
        (stepData) => {
          setQaResearchSteps((prev) => [...prev, stepData]);
        }
      );
    } catch (err: any) {
      setQaError(err.message || 'Error asking question');
      setQaLoading(false);
    }
  }

  async function pollQaJobStatus(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const status = await getRagJobStatus(jobId);
        if (status.status === 'succeeded') {
          clearInterval(interval);
          setQaAnswer(`Deep Research complete! A detailed report has been generated and saved to your Document Library.\n\n[View Document]`);
          // Optionally link to document here if we add documentId to response
          setQaLoading(false);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setQaError(`Deep Research failed: ${status.error_message || 'Unknown error'}`);
          setQaLoading(false);
        } else {
          // Still processing
          setQaAnswer(`Researching... (Job ID: ${jobId})`);
        }
      } catch (err: any) {
        clearInterval(interval);
        setQaError('Error polling job status');
        setQaLoading(false);
      }
    }, 2000);
  }

  async function handleAddNote(chunkId: string) {
    if (!newNoteText.trim()) return;
    setNoteSaving(true);
    setNoteError(null);
    try {
      const created = await createChunkNote(document.id, chunkId, newNoteText);
      setNotes((prev) => [created, ...prev]);
      setNewNoteText('');
      setActiveChunkIdForNote(null);
    } catch (err: any) {
      setNoteError(err.message || 'Failed to add note');
    } finally {
      setNoteSaving(false);
    }
  }

  async function handleDeleteNote(noteId: string) {
    try {
      await deleteChunkNote(noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err: any) {
      setNoteError(err.message || 'Failed to delete note');
    }
  }

  async function handleGenerateFlashcards() {
    setGeneratingFlashcards(true);
    setFlashcardError(null);
    try {
      const cards = await generateFlashcards(document.id);
      setFlashcardsDraft(cards);
    } catch (err: any) {
      setFlashcardError(err.message || 'Failed to generate flashcards');
    } finally {
      setGeneratingFlashcards(false);
    }
  }

  async function handleApproveFlashcard(cardId: string) {
    try {
      await approveFlashcard(cardId);
      setFlashcardsDraft(prev => prev.map(c => c.id === cardId ? { ...c, is_approved: true } : c));
    } catch (err: any) {
      setFlashcardError(err.message || 'Failed to approve flashcard');
    }
  }

  const filteredChunks = chunks.filter((ch) => {
    if (!chunkFilter.trim()) return true;
    const query = chunkFilter.toLowerCase();
    return (
      ch.text?.toLowerCase().includes(query) ||
      ch.chunk_index?.toString().includes(query)
    );
  });

  return (
    <div
      aria-modal="true"
      role="dialog"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '2rem'
      }}
    >
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '0.75rem',
          width: '100%',
          maxWidth: '1200px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#f8fafc'
          }}
        >
          <div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: '#3b82f6',
                letterSpacing: '0.05em'
              }}
            >
              Interactive Workspace
            </span>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', margin: '0.25rem 0 0' }}>
              {document.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#e2e8f0',
              color: '#334155',
              border: 'none',
              borderRadius: '0.375rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>

        {/* Dual-Pane Content */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Left Pane: Chat with Document */}
          <div
            style={{
              flex: '1 1 45%',
              borderRight: '1px solid #e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              padding: '1.5rem',
              overflowY: 'auto'
            }}
          >
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.5rem' }}>
              Ask This Document
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '1rem' }}>
              Ask any question to stream an AI answer grounded exclusively in chunks from this document.
            </p>

            <form onSubmit={(e) => handleAskQuestion(e)} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about this document..."
                disabled={qaLoading}
                style={{
                  flex: '1 1 200px',
                  padding: '0.75rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem'
                }}
              />
              <select
                value={qaConfidenceMode}
                onChange={(e) => setQaConfidenceMode(e.target.value)}
                disabled={qaLoading}
                style={{ padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '0.375rem', fontSize: '0.875rem', backgroundColor: '#fff', color: '#0f172a' }}
              >
                <option value="strict">Strict (0.45+)</option>
                <option value="balanced">Balanced (0.28+)</option>
                <option value="permissive">Permissive (0.18+)</option>
              </select>
              <button
                type="submit"
                disabled={qaLoading || !question.trim()}
                style={{
                  padding: '0.75rem 1.25rem',
                  backgroundColor: '#3b82f6',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '0.375rem',
                  fontWeight: 600,
                  cursor: qaLoading || !question.trim() ? 'not-allowed' : 'pointer',
                  opacity: qaLoading || !question.trim() ? 0.7 : 1
                }}
              >
                {qaLoading ? (qaResearchMode ? '🔬 Researching...' : 'Streaming...') : 'Ask'}
              </button>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.8rem', color: qaResearchMode ? '#7c3aed' : '#64748b', fontWeight: qaResearchMode ? 600 : 400 }}>
                <input
                  type="checkbox"
                  checked={qaResearchMode}
                  onChange={(e) => setQaResearchMode(e.target.checked)}
                  disabled={qaLoading}
                  style={{ accentColor: '#7c3aed' }}
                />
                🔬 Deep Research
              </label>
            </form>

            {qaError && (
              <div role="alert" style={{ padding: '0.75rem', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '0.375rem', marginBottom: '1rem' }}>
                {qaError}
              </div>
            )}

            {qaActionRequired && qaActionRequired.status === 'insufficient_knowledge' && (
              <div style={{ marginBottom: '1.5rem', padding: '1.25rem', backgroundColor: '#fffbeb', border: '1px solid #f59e0b', borderRadius: '0.5rem', boxShadow: '0 2px 4px rgba(245, 158, 11, 0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#b45309', fontWeight: 600, fontSize: '0.95rem' }}>
                  <span>⚠️ Insufficient Local Evidence ({qaActionRequired.confidence_mode || qaConfidenceMode} mode)</span>
                </div>
                <p style={{ fontSize: '0.875rem', color: '#78350f', marginBottom: '1rem', lineHeight: 1.5 }}>
                  {qaActionRequired.evidence_summary || 'This document does not contain strong enough evidence to confidently answer this query.'}
                </p>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {qaConfidenceMode !== 'permissive' && (
                    <button
                      type="button"
                      onClick={(e) => handleAskQuestion(e, 'permissive')}
                      style={{ padding: '0.5rem 1rem', backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #f59e0b', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
                    >
                      Try Permissive Mode
                    </button>
                  )}
                  {qaActionRequired.fallback_options?.includes('search_web') && (
                    <button
                      type="button"
                      onClick={(e) => handleAskQuestion(e, undefined, 'search_web')}
                      style={{ padding: '0.5rem 1rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
                    >
                      🌐 Search Web with Tavily
                    </button>
                  )}
                  {qaActionRequired.fallback_options?.includes('general_model') && (
                    <button
                      type="button"
                      onClick={(e) => handleAskQuestion(e, undefined, 'general_model')}
                      style={{ padding: '0.5rem 1rem', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
                    >
                      🤖 Answer from General Knowledge
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={(e) => handleAskQuestion(e, undefined, 'autonomous_research')}
                    style={{ padding: '0.5rem 1rem', backgroundColor: '#7c3aed', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
                  >
                    🔬 Run Autonomous Deep Research
                  </button>
                </div>
              </div>
            )}

            {qaResearchSteps.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowQaAuditTrail(!showQaAuditTrail)}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#f5f3ff', color: '#7c3aed', border: '1px solid #c4b5fd', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', marginBottom: '0.75rem' }}
                >
                  🔬 Research Audit Trail ({qaResearchSteps.filter(s => s.iteration).length} steps)
                  <span style={{ transform: showQaAuditTrail ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
                </button>
                {showQaAuditTrail && (
                  <div style={{ padding: '1rem', backgroundColor: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: '0.5rem' }}>
                    {qaResearchSteps.map((step, idx) => (
                      <div key={idx} style={{ padding: '0.75rem', marginBottom: '0.5rem', backgroundColor: '#fff', border: '1px solid #e9d5ff', borderRadius: '0.375rem', fontSize: '0.8rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
                          {step.type === 'decomposition' && (
                            <span style={{ backgroundColor: '#dbeafe', color: '#1d4ed8', padding: '0.125rem 0.5rem', borderRadius: '0.25rem', fontWeight: 600, fontSize: '0.7rem' }}>DECOMPOSE</span>
                          )}
                          {step.type === 'reflection' && (
                            <span style={{ backgroundColor: step.status === 'sufficient' ? '#d1fae5' : '#fef3c7', color: step.status === 'sufficient' ? '#065f46' : '#b45309', padding: '0.125rem 0.5rem', borderRadius: '0.25rem', fontWeight: 600, fontSize: '0.7rem' }}>{step.status === 'sufficient' ? 'SUFFICIENT' : 'REWRITING'}</span>
                          )}
                          {step.status === 'retrieved' && (
                            <span style={{ backgroundColor: '#d1fae5', color: '#065f46', padding: '0.125rem 0.5rem', borderRadius: '0.25rem', fontWeight: 600, fontSize: '0.7rem' }}>RETRIEVED</span>
                          )}
                          {step.status === 'rewritten' && (
                            <span style={{ backgroundColor: '#fef3c7', color: '#b45309', padding: '0.125rem 0.5rem', borderRadius: '0.25rem', fontWeight: 600, fontSize: '0.7rem' }}>REWRITTEN</span>
                          )}
                          {step.iteration && <span style={{ color: '#64748b', fontWeight: 500 }}>Iteration {step.iteration}</span>}
                        </div>
                        {step.query && <div style={{ color: '#334155', marginBottom: '0.25rem' }}><strong>Query:</strong> {step.query}</div>}
                        {step.sub_queries && (
                          <div style={{ color: '#334155' }}>
                            <strong>Sub-queries:</strong>
                            <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0 }}>
                              {step.sub_queries.map((sq: any, i: number) => (
                                <li key={i}>{sq.query} → [{sq.target_sources?.join(', ')}]</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {step.target_sources && <div style={{ color: '#64748b' }}>Sources: {step.target_sources.join(', ')}</div>}
                        {step.source_counts && Object.keys(step.source_counts).length > 0 && (
                          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                            {Object.entries(step.source_counts).map(([src, count]) => (
                              <span key={src} style={{ backgroundColor: '#e2e8f0', color: '#475569', padding: '0.125rem 0.375rem', borderRadius: '0.125rem', fontSize: '0.7rem' }}>{src}: {String(count)}</span>
                            ))}
                          </div>
                        )}
                        {step.reason && <div style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '0.25rem', fontStyle: 'italic' }}>{step.reason}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {(qaAnswer || qaCitations.length > 0) && (
              <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.5rem' }}>
                  Answer
                </h4>
                <div style={{ fontSize: '0.875rem', color: '#334155', lineHeight: 1.6, whiteSpace: 'pre-wrap', marginBottom: '1.5rem' }}>
                  {qaAnswer}
                </div>

                {qaCitations.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#64748b', marginBottom: '0.5rem' }}>
                      Supporting Chunks ({qaCitations.length})
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {qaCitations.map((cit) => (
                        <div
                          key={cit.citation_id}
                          style={{
                            padding: '0.6rem',
                            backgroundColor: cit.source_type === 'web_tavily' ? '#eff6ff' : '#f8fafc',
                            border: cit.source_type === 'web_tavily' ? '1px solid #bfdbfe' : '1px solid #e2e8f0',
                            borderRadius: '0.375rem',
                            fontSize: '0.75rem'
                          }}
                        >
                          <div style={{ fontWeight: 600, color: '#0f172a', marginBottom: '0.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>{cit.source_type === 'web_tavily' ? `[Web] ${cit.document_title}` : `Chunk #${cit.chunk_index}`}</span>
                            {cit.source_type === 'web_tavily' && (
                              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                <span style={{ backgroundColor: '#dbeafe', color: '#1d4ed8', padding: '0.1rem 0.3rem', borderRadius: '0.125rem', fontSize: '0.65rem' }}>🌐 Ephemeral Web</span>
                                <button
                                  type="button"
                                  onClick={async () => {
                                    try {
                                      await saveWebResultToKb(cit.document_title, cit.source_uri || '', cit.text_preview || '');
                                      setSavedCitIds(prev => ({ ...prev, [cit.citation_id]: true }));
                                    } catch (err: any) {
                                      setQaError(err.message || 'Failed to save web result');
                                    }
                                  }}
                                  disabled={savedCitIds[cit.citation_id]}
                                  style={{
                                    backgroundColor: savedCitIds[cit.citation_id] ? '#10b981' : '#2563eb',
                                    color: '#ffffff',
                                    padding: '0.1rem 0.4rem',
                                    borderRadius: '0.25rem',
                                    border: 'none',
                                    fontSize: '0.65rem',
                                    cursor: savedCitIds[cit.citation_id] ? 'default' : 'pointer',
                                    fontWeight: 600
                                  }}
                                >
                                  {savedCitIds[cit.citation_id] ? '✓ Saved' : '💾 Save'}
                                </button>
                              </div>
                            )}
                          </div>
                          {cit.source_uri && (
                            <div style={{ marginBottom: '0.25rem' }}>
                              <a href={cit.source_uri} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline' }}>{cit.source_uri}</a>
                            </div>
                          )}
                          <div style={{ color: '#475569', fontStyle: 'italic' }}>
                            "{cit.text_preview}"
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Pane: Chunk Explorer & Annotator */}
          <div
            style={{
              flex: '1 1 55%',
              display: 'flex',
              flexDirection: 'column',
              padding: '1.5rem',
              backgroundColor: '#fafbfc',
              overflowY: 'auto'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#0f172a', margin: 0 }}>
                  Chunks & Inline Notes
                </h3>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {chunks.length} chunks • {notes.length} total notes
                </span>
              </div>
              <input
                type="text"
                value={chunkFilter}
                onChange={(e) => setChunkFilter(e.target.value)}
                placeholder="Filter chunks..."
                style={{
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '0.375rem',
                  fontSize: '0.8rem',
                  width: '200px'
                }}
              />
              <button
                onClick={handleGenerateFlashcards}
                disabled={generatingFlashcards}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#8b5cf6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '0.375rem',
                  fontWeight: 600,
                  fontSize: '0.8rem',
                  cursor: generatingFlashcards ? 'not-allowed' : 'pointer',
                  opacity: generatingFlashcards ? 0.7 : 1
                }}
              >
                {generatingFlashcards ? 'Generating...' : '🗂️ Generate Flashcards'}
              </button>
            </div>

            {flashcardError && (
              <div role="alert" style={{ padding: '0.75rem', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '0.375rem', marginBottom: '1rem' }}>
                {flashcardError}
              </div>
            )}

            {flashcardsDraft.length > 0 && (
              <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#f5f3ff', borderRadius: '0.5rem', border: '1px solid #ddd6fe' }}>
                <h4 style={{ margin: '0 0 0.5rem 0', color: '#4c1d95' }}>Generated Draft Flashcards ({flashcardsDraft.filter(c => !c.is_approved).length} pending)</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {flashcardsDraft.map((card) => (
                    <div key={card.id} style={{ padding: '0.75rem', backgroundColor: '#fff', borderRadius: '0.375rem', border: '1px solid #e9d5ff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ flex: 1, paddingRight: '1rem' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1e293b' }}>Q: {card.front}</div>
                        <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.25rem' }}>A: {card.back}</div>
                      </div>
                      <button
                        onClick={() => handleApproveFlashcard(card.id)}
                        disabled={card.is_approved}
                        style={{
                          padding: '0.375rem 0.75rem',
                          backgroundColor: card.is_approved ? '#10b981' : '#3b82f6',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '0.25rem',
                          fontSize: '0.75rem',
                          cursor: card.is_approved ? 'default' : 'pointer',
                          fontWeight: 600
                        }}
                      >
                        {card.is_approved ? 'Approved' : 'Approve'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {noteError && (
              <div role="alert" style={{ padding: '0.75rem', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '0.375rem', marginBottom: '1rem' }}>
                {noteError}
              </div>
            )}

            {chunksLoading ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>Loading document chunks...</div>
            ) : filteredChunks.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>No matching chunks found.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {filteredChunks.map((ch) => {
                  const chunkNotes = notes.filter((n) => n.chunk_id === ch.id);
                  const isAddingNote = activeChunkIdForNote === ch.id;

                  return (
                    <div
                      key={ch.id}
                      style={{
                        padding: '1rem',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.5rem',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#3b82f6' }}>
                          Chunk #{ch.chunk_index} ({ch.character_count} chars)
                        </span>
                        {!isAddingNote && (
                          <button
                            onClick={() => {
                              setActiveChunkIdForNote(ch.id);
                              setNewNoteText('');
                            }}
                            style={{
                              fontSize: '0.75rem',
                              padding: '0.25rem 0.5rem',
                              backgroundColor: '#f1f5f9',
                              color: '#334155',
                              border: '1px solid #cbd5e1',
                              borderRadius: '0.25rem',
                              cursor: 'pointer'
                            }}
                          >
                            + Add Note
                          </button>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: '0.85rem',
                          color: '#1e293b',
                          lineHeight: 1.6,
                          marginBottom: '0.75rem',
                          whiteSpace: 'pre-wrap'
                        }}
                      >
                        {ch.text}
                      </div>

                      {/* Attached Notes */}
                      {chunkNotes.length > 0 && (
                        <div style={{ borderTop: '1px dashed #e2e8f0', paddingTop: '0.75rem', marginTop: '0.5rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', display: 'block', marginBottom: '0.5rem' }}>
                            Notes ({chunkNotes.length})
                          </span>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {chunkNotes.map((note) => (
                              <div
                                key={note.id}
                                style={{
                                  padding: '0.6rem',
                                  backgroundColor: '#fffbeb',
                                  border: '1px solid #fde68a',
                                  borderRadius: '0.375rem',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'flex-start'
                                }}
                              >
                                <span style={{ fontSize: '0.8rem', color: '#78350f', flex: 1 }}>
                                  {note.note_text}
                                </span>
                                <button
                                  onClick={() => handleDeleteNote(note.id)}
                                  aria-label="Delete note"
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    color: '#b45309',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    marginLeft: '0.5rem'
                                  }}
                                >
                                  Delete
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Add Note Form */}
                      {isAddingNote && (
                        <div style={{ marginTop: '0.75rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.75rem' }}>
                          <textarea
                            value={newNoteText}
                            onChange={(e) => setNewNoteText(e.target.value)}
                            placeholder="Write your note or takeaway for this chunk..."
                            rows={2}
                            style={{
                              width: '100%',
                              padding: '0.5rem',
                              border: '1px solid #cbd5e1',
                              borderRadius: '0.375rem',
                              fontSize: '0.8rem',
                              marginBottom: '0.5rem'
                            }}
                          />
                          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                            <button
                              onClick={() => setActiveChunkIdForNote(null)}
                              disabled={noteSaving}
                              style={{
                                padding: '0.35rem 0.75rem',
                                backgroundColor: '#f1f5f9',
                                color: '#475569',
                                border: 'none',
                                borderRadius: '0.25rem',
                                fontSize: '0.75rem',
                                cursor: 'pointer'
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleAddNote(ch.id)}
                              disabled={noteSaving || !newNoteText.trim()}
                              style={{
                                padding: '0.35rem 0.75rem',
                                backgroundColor: '#10b981',
                                color: '#ffffff',
                                border: 'none',
                                borderRadius: '0.25rem',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                cursor: noteSaving || !newNoteText.trim() ? 'not-allowed' : 'pointer'
                              }}
                            >
                              {noteSaving ? 'Saving...' : 'Save Note'}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
