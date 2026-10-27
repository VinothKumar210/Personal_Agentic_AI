'use client';
import { useState } from 'react';
import { askKnowledgeBase, streamKnowledgeBase, saveWebResultToKb, ResearchStepRecord, startDeepResearch, getRagJobStatus } from '../lib/api';

export default function RagQuestionAnswer() {
  const [question, setQuestion] = useState('');
  const [confidenceMode, setConfidenceMode] = useState<string>('balanced');
  const [response, setResponse] = useState<any | null>(null);
  const [actionRequired, setActionRequired] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedCitIds, setSavedCitIds] = useState<Record<number, boolean>>({});
  const [researchMode, setResearchMode] = useState(false);
  const [researchSteps, setResearchSteps] = useState<any[]>([]);
  const [showAuditTrail, setShowAuditTrail] = useState(false);

  async function handleAsk(e: React.FormEvent, overrideMode?: string, fallbackAction?: string) {
    if (e && e.preventDefault) e.preventDefault();
    if (!question.trim()) return;

    const modeToUse = overrideMode || confidenceMode;
    if (overrideMode) setConfidenceMode(overrideMode);

    setLoading(true);
    setError(null);
    setActionRequired(null);
    setResponse({ answer: '', citations: [] });
    setResearchSteps([]);

    // Trigger deep research background job
    if (researchMode || fallbackAction === 'autonomous_research') {
      try {
        const job = await startDeepResearch(question);
        pollJobStatus(job.id);
      } catch (err: any) {
        setError(err.message || 'Failed to start deep research');
        setLoading(false);
      }
      return;
    }

    try {
      await streamKnowledgeBase(
        question,
        (citations) => {
          setResponse((prev: any) => ({ ...(prev || { answer: '' }), citations }));
        },
        (token) => {
          setResponse((prev: any) => ({ ...(prev || { citations: [] }), answer: (prev?.answer || '') + token }));
        },
        (errMsg) => {
          setError(errMsg);
          setLoading(false);
        },
        () => {
          setLoading(false);
        },
        undefined,
        undefined,
        modeToUse,
        (actionData) => {
          setActionRequired(actionData);
        },
        fallbackAction,
        false, // streamKnowledgeBase no longer runs deep research
        2,
        (stepData) => {
          setResearchSteps(prev => [...prev, stepData]);
        }
      );
    } catch (err: any) {
      setError(err.message || 'An error occurred during Q&A.');
      setLoading(false);
    }
  }

  async function pollJobStatus(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const status = await getRagJobStatus(jobId);
        if (status.status === 'succeeded') {
          clearInterval(interval);
          setResponse({
            answer: `Deep Research complete! A detailed report has been generated and saved to your Document Library.\n\n[View Document]`,
            documentId: status.document_id,
            citations: []
          });
          setLoading(false);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setError(`Deep Research failed: ${status.error_message || 'Unknown error'}`);
          setLoading(false);
        } else {
          // Still processing
          setResponse({
            answer: `Researching... (Job ID: ${jobId})`,
            citations: []
          });
        }
      } catch (err: any) {
        clearInterval(interval);
        setError('Error polling job status');
        setLoading(false);
      }
    }, 2000);
  }

  return (
    <div className="rag-qa" style={{ padding: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', backgroundColor: '#fff', marginBottom: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem', color: '#0f172a' }}>Ask Your Knowledge Base</h2>
      <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '1.25rem' }}>Generated from retrieved chunks with multi-factor confidence gating. This is a one-shot Q&A, not a multi-turn chat.</p>

      <form onSubmit={(e) => handleAsk(e)} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <input 
          type="text" 
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          style={{ flex: '1 1 300px', padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '0.375rem', fontSize: '0.875rem', outline: 'none' }}
          disabled={loading}
        />
        <select
          value={confidenceMode}
          onChange={(e) => setConfidenceMode(e.target.value)}
          disabled={loading}
          style={{ padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '0.375rem', fontSize: '0.875rem', backgroundColor: '#fff', color: '#0f172a' }}
        >
          <option value="strict">Strict Mode (0.45+)</option>
          <option value="balanced">Balanced Mode (0.28+)</option>
          <option value="permissive">Permissive Mode (0.18+)</option>
        </select>
        <button 
          type="submit" 
          disabled={loading || !question.trim()}
          style={{ padding: '0.75rem 1.5rem', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '0.375rem', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500, opacity: (loading || !question.trim()) ? 0.7 : 1 }}
        >
          {loading ? (researchMode ? '🔬 Researching...' : 'Thinking...') : 'Ask'}
        </button>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8rem', color: researchMode ? '#7c3aed' : '#64748b', fontWeight: researchMode ? 600 : 400 }}>
          <input
            type="checkbox"
            checked={researchMode}
            onChange={(e) => setResearchMode(e.target.checked)}
            disabled={loading}
            style={{ accentColor: '#7c3aed' }}
          />
          🔬 Deep Research
        </label>
      </form>

      {error && <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '0.875rem', padding: '0.75rem', backgroundColor: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '0.375rem' }}>{error}</div>}

      {actionRequired && actionRequired.status === 'insufficient_knowledge' && (
        <div style={{ marginBottom: '1.5rem', padding: '1.25rem', backgroundColor: '#fffbeb', border: '1px solid #f59e0b', borderRadius: '0.5rem', boxShadow: '0 2px 4px rgba(245, 158, 11, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#b45309', fontWeight: 600, fontSize: '0.95rem' }}>
            <span>⚠️ Insufficient Local Evidence ({actionRequired.confidence_mode || confidenceMode} mode)</span>
          </div>
          <p style={{ fontSize: '0.875rem', color: '#78350f', marginBottom: '1rem', lineHeight: 1.5 }}>
            {actionRequired.evidence_summary || 'Your local documents do not contain strong enough evidence to confidently answer this question.'}
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {confidenceMode !== 'permissive' && (
              <button
                type="button"
                onClick={(e) => handleAsk(e, 'permissive')}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #f59e0b', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
              >
                Try Permissive Mode (Lower Threshold)
              </button>
            )}
            {actionRequired.fallback_options?.includes('search_web') && (
              <button
                type="button"
                onClick={(e) => handleAsk(e, undefined, 'search_web')}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
              >
                🌐 Search Web with Tavily
              </button>
            )}
            {actionRequired.fallback_options?.includes('general_model') && (
              <button
                type="button"
                onClick={(e) => handleAsk(e, undefined, 'general_model')}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
              >
                🤖 Answer from General Model Knowledge
              </button>
            )}
            <button
              type="button"
              onClick={(e) => handleAsk(e, undefined, 'autonomous_research')}
              style={{ padding: '0.5rem 1rem', backgroundColor: '#7c3aed', color: '#fff', border: 'none', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 500, cursor: 'pointer' }}
            >
              🔬 Run Autonomous Deep Research
            </button>
          </div>
        </div>
      )}

      {researchSteps.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <button
            type="button"
            onClick={() => setShowAuditTrail(!showAuditTrail)}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#f5f3ff', color: '#7c3aed', border: '1px solid #c4b5fd', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', marginBottom: '0.75rem' }}
          >
            🔬 Research Audit Trail ({researchSteps.filter(s => s.iteration).length} steps)
            <span style={{ transform: showAuditTrail ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
          </button>
          {showAuditTrail && (
            <div style={{ padding: '1rem', backgroundColor: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: '0.5rem' }}>
              {researchSteps.map((step, idx) => (
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

      {response && (response.answer || (response.citations && response.citations.length > 0)) && (
        <div className="qa-response" style={{ paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
          <div style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.5rem' }}>Answer</h3>
            <div style={{ fontSize: '0.875rem', color: '#334155', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {response.answer}
              {response.documentId && (
                <div style={{ marginTop: '1rem' }}>
                  <a href={`/documents/${response.documentId}`} style={{ color: '#2563eb', textDecoration: 'underline' }}>
                    Open Detailed Research Report
                  </a>
                </div>
              )}
            </div>
          </div>

          {response.citations && response.citations.length > 0 && (
            <div>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#64748b', marginBottom: '0.5rem' }}>Citations</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {response.citations.map((cit: any) => (
                  <div key={cit.citation_id} style={{ fontSize: '0.75rem', padding: '0.75rem', backgroundColor: cit.source_type === 'web_tavily' ? '#eff6ff' : '#f8fafc', border: cit.source_type === 'web_tavily' ? '1px solid #bfdbfe' : '1px solid #e2e8f0', borderRadius: '0.375rem' }}>
                    <div style={{ fontWeight: 600, color: '#0f172a', marginBottom: '0.25rem' }}>
                      [{cit.citation_id}] {cit.document_title}
                    </div>
                    <div style={{ color: '#64748b', marginBottom: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                      <span style={{ backgroundColor: cit.source_type === 'web_tavily' ? '#dbeafe' : '#e2e8f0', color: cit.source_type === 'web_tavily' ? '#1d4ed8' : '#475569', padding: '0.125rem 0.375rem', borderRadius: '0.125rem', fontWeight: cit.source_type === 'web_tavily' ? 600 : 400 }}>
                        {cit.source_type === 'web_tavily' ? '🌐 Web Search (Ephemeral)' : cit.source_type}
                      </span>
                      {cit.source_type === 'web_tavily' && (
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await saveWebResultToKb(cit.document_title, cit.source_uri || '', cit.text_preview || '');
                              setSavedCitIds(prev => ({ ...prev, [cit.citation_id]: true }));
                            } catch (err: any) {
                              alert(err.message || 'Failed to save web result');
                            }
                          }}
                          disabled={savedCitIds[cit.citation_id]}
                          style={{
                            backgroundColor: savedCitIds[cit.citation_id] ? '#10b981' : '#2563eb',
                            color: '#ffffff',
                            padding: '0.125rem 0.5rem',
                            borderRadius: '0.25rem',
                            border: 'none',
                            fontSize: '0.7rem',
                            cursor: savedCitIds[cit.citation_id] ? 'default' : 'pointer',
                            fontWeight: 600
                          }}
                        >
                          {savedCitIds[cit.citation_id] ? '✓ Saved to KB' : '💾 Save to KB'}
                        </button>
                      )}
                      {cit.original_filename && <span>File: {cit.original_filename}</span>}
                      {cit.source_uri && (
                        <span>
                          {cit.source_type === 'web_tavily' ? (
                            <a href={cit.source_uri} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline' }}>{cit.source_uri}</a>
                          ) : (
                            `URI: ${cit.source_uri}`
                          )}
                        </span>
                      )}
                      {cit.source_type !== 'web_tavily' && <span>Chunk {cit.chunk_index}</span>}
                    </div>
                    <div style={{ color: '#475569', fontStyle: 'italic' }}>"{cit.text_preview}"</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
