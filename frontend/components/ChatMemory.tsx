import { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  ConversationRead, 
  ChatMessageRead, 
  listConversations, 
  createConversation, 
  getConversationMessages, 
  sendConversationMessage, 
  streamConversationMessage,
  deleteConversation,
  saveWebResultToKb,
  listDocuments,
  DocumentRead
} from '../lib/api';

export default function ChatMemory() {
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [selectedConv, setSelectedConv] = useState<ConversationRead | null>(null);
  const [messages, setMessages] = useState<ChatMessageRead[]>([]);
  const [actionRequired, setActionRequired] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedCitIds, setSavedCitIds] = useState<Record<number, boolean>>({});
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({});
  
  // Document Filtering
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchConversations();
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (selectedConv) {
      fetchMessages(selectedConv.id);
    } else {
      setMessages([]);
    }
  }, [selectedConv]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function fetchConversations() {
    try {
      const data = await listConversations();
      setConversations(data.items);
    } catch (err: any) {
      console.error(err);
    }
  }

  async function fetchDocuments() {
    try {
      const data = await listDocuments();
      setDocuments(data.items);
    } catch (err: any) {
      console.error(err);
    }
  }

  async function fetchMessages(convId: string) {
    setLoading(true);
    try {
      const data = await getConversationMessages(convId);
      setMessages(data);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateNew() {
    try {
      const newConv = await createConversation('New Chat');
      setSelectedConv(newConv);
      fetchConversations();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  }

  async function handleSend(e: React.FormEvent, overrideText?: string, fallbackAction?: string, confidenceMode?: string) {
    if (e && e.preventDefault) e.preventDefault();
    if (!selectedConv || sending) return;

    const userText = overrideText || input;
    if (!userText.trim()) return;

    if (!overrideText) setInput('');
    setSending(true);
    setErrorMsg(null);
    setActionRequired(null);
    
    const tempUserMsg: ChatMessageRead = {
      id: `temp-${Date.now()}`,
      conversation_id: selectedConv.id,
      role: 'user',
      content: fallbackAction ? `[Fallback: ${fallbackAction}] ${userText}` : userText,
      citations: [],
      created_at: new Date().toISOString()
    };
    const tempAssistantId = `temp-assistant-${Date.now()}`;
    const tempAssistantMsg: ChatMessageRead = {
      id: tempAssistantId,
      conversation_id: selectedConv.id,
      role: 'assistant',
      content: '',
      citations: [],
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg]);

    try {
      await streamConversationMessage(
        selectedConv.id,
        userText,
        (citations) => {
          setMessages(prev => prev.map(m => m.id === tempAssistantId ? { ...m, citations } : m));
        },
        (token) => {
          setMessages(prev => prev.map(m => m.id === tempAssistantId ? { ...m, content: m.content + token } : m));
        },
        (errMsg) => {
          setErrorMsg(errMsg);
          setSending(false);
        },
        () => {
          setSending(false);
          fetchMessages(selectedConv.id);
          fetchConversations();
        },
        (actionData) => {
          setActionRequired(actionData);
        },
        fallbackAction,
        confidenceMode,
        false, // research_mode
        2,     // max_iterations
        undefined, // onResearchStep
        selectedDocumentId || undefined // pass chosen document_id
      );
    } catch (err: any) {
      setErrorMsg(err.message);
      setSending(false);
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      if (selectedConv?.id === id) {
        setSelectedConv(null);
      }
      fetchConversations();
    } catch (err: any) {
      console.error(err);
    }
  }

  return (
    <div className="chat-memory-container" style={{ border: '1px solid var(--border-color)', borderRadius: '0.5rem', backgroundColor: 'var(--surface-color)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-primary)' }}>Chat With Your Knowledge Base</h2>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Responses are grounded in retrieved chunks.</p>
        </div>
        <button onClick={handleCreateNew} className="btn-primary" style={{ padding: '0.5rem 1rem' }}>
          + New Chat
        </button>
      </div>
      
      <div style={{ display: 'flex', flexGrow: 1, minHeight: 0 }}>
        {/* Sidebar */}
        <div style={{ width: '250px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
          {conversations.length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.875rem', textAlign: 'center' }}>No conversations yet.</p>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {conversations.map(conv => (
                <li 
                  key={conv.id} 
                  onClick={() => setSelectedConv(conv)}
                  style={{ 
                    padding: '0.75rem 1rem', 
                    cursor: 'pointer', 
                    backgroundColor: selectedConv?.id === conv.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    borderBottom: '1px solid var(--border-light)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    color: selectedConv?.id === conv.id ? 'var(--accent-color)' : 'var(--text-primary)'
                  }}
                >
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.875rem', flex: 1 }}>
                    {conv.title || 'New Conversation'}
                  </div>
                  <button onClick={(e) => handleDelete(conv.id, e)} style={{ border: 'none', background: 'transparent', color: 'var(--status-error-text)', cursor: 'pointer', fontSize: '0.875rem', padding: '0 0 0 0.5rem' }}>Delete</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Main Chat Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: 'var(--background-color)', minWidth: 0 }}>
          {errorMsg && (
            <div style={{ padding: '0.5rem', backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '0.875rem', borderBottom: '1px solid #fca5a5' }}>
              Error: {errorMsg}
            </div>
          )}
          
          {!selectedConv ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>👋</div>
              <p>Select a conversation or create a new one to start chatting.</p>
            </div>
          ) : (
            <>
              <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
                {loading ? (
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading messages...</p>
                ) : messages.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textAlign: 'center', marginTop: '2rem' }}>Send a message to start.</p>
                ) : (
                  messages.filter(m => m.role !== 'system').map(msg => (
                    <div key={msg.id} style={{ 
                      marginBottom: '1.5rem', 
                      display: 'flex', 
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start'
                    }}>
                      <div style={{ 
                        maxWidth: '85%', 
                        padding: '1rem 1.25rem', 
                        borderRadius: '0.5rem',
                        backgroundColor: msg.role === 'user' ? 'var(--accent-color)' : 'var(--surface-light)',
                        color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                        border: msg.role === 'user' ? 'none' : '1px solid var(--border-color)',
                        boxShadow: 'var(--shadow-sm)'
                      }}>
                        <div style={{ fontSize: '0.95rem', lineHeight: '1.6' }} className={msg.role === 'user' ? 'user-markdown' : 'assistant-markdown'}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                        
                        {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                          <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-light)' }}>
                            <strong style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Citations:</strong>
                            <ul style={{ margin: '0.25rem 0 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                              {msg.citations.map((c, i) => {
                                const isExpanded = !!expandedCitations[`${msg.id}-${i}`];
                                const toggleExpand = () => {
                                  setExpandedCitations(prev => ({ ...prev, [`${msg.id}-${i}`]: !isExpanded }));
                                };
                                return (
                                  <li key={i} style={{ border: '1px solid var(--border-color)', borderRadius: '0.375rem', backgroundColor: 'var(--surface-color)', overflow: 'hidden' }}>
                                    <div 
                                      onClick={toggleExpand}
                                      style={{ padding: '0.5rem 0.75rem', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                                    >
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: 0 }}>
                                        <span style={{ fontWeight: 600, color: 'var(--accent-color)', flexShrink: 0 }}>[{c.citation_id}]</span>
                                        <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                          {c.source_type === 'web_tavily' && (
                                            <span style={{ backgroundColor: 'rgba(59, 130, 246, 0.2)', color: 'var(--accent-color)', padding: '0.05rem 0.3rem', borderRadius: '0.125rem', fontSize: '0.7rem', fontWeight: 600, marginRight: '0.4rem' }}>🌐 Web</span>
                                          )}
                                          {c.document_title}
                                        </div>
                                      </div>
                                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem', flexShrink: 0 }}>
                                        {isExpanded ? '▲ Hide Details' : '▼ View Source'}
                                      </span>
                                    </div>
                                    
                                    {isExpanded && (
                                      <div style={{ padding: '0.75rem', borderTop: '1px solid var(--border-color)', backgroundColor: 'var(--surface-light)' }}>
                                        {c.source_uri && (
                                          <div style={{ marginBottom: '0.5rem' }}>
                                            <a href={c.source_uri} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline', fontSize: '0.75rem' }}>
                                              {c.source_uri}
                                            </a>
                                          </div>
                                        )}
                                        {c.text_preview ? (
                                          <div style={{ fontSize: '0.8rem', color: '#475569', backgroundColor: '#f1f5f9', padding: '0.5rem', borderRadius: '0.25rem', fontStyle: 'italic', borderLeft: '3px solid #94a3b8' }}>
                                            "{c.text_preview}"
                                          </div>
                                        ) : (
                                          <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontStyle: 'italic' }}>
                                            No source excerpt available.
                                          </div>
                                        )}
                                        
                                        {c.source_type === 'web_tavily' && (
                                          <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                                            <button
                                              type="button"
                                              onClick={async (e) => {
                                                e.stopPropagation();
                                                try {
                                                  await saveWebResultToKb(c.document_title, c.source_uri || '', c.text_preview || '');
                                                  setSavedCitIds(prev => ({ ...prev, [c.citation_id]: true }));
                                                } catch (err: any) {
                                                  setErrorMsg(err.message || 'Failed to save web result');
                                                }
                                              }}
                                              disabled={savedCitIds[c.citation_id]}
                                              style={{
                                                backgroundColor: savedCitIds[c.citation_id] ? '#10b981' : '#2563eb',
                                                color: '#ffffff',
                                                padding: '0.25rem 0.5rem',
                                                borderRadius: '0.25rem',
                                                border: 'none',
                                                fontSize: '0.7rem',
                                                cursor: savedCitIds[c.citation_id] ? 'default' : 'pointer',
                                                fontWeight: 600
                                              }}
                                            >
                                              {savedCitIds[c.citation_id] ? '✓ Saved to Knowledge Base' : '💾 Save to Knowledge Base'}
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', backgroundColor: 'var(--surface-color)' }}>
                {actionRequired && actionRequired.status === 'insufficient_knowledge' && (
                  <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--status-pending-text)', fontWeight: 600, fontSize: '0.9rem' }}>
                      <span>⚠️ Insufficient Local Evidence ({actionRequired.confidence_mode || 'balanced'} mode)</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.4 }}>
                      {actionRequired.evidence_summary || 'Your knowledge base does not contain strong enough evidence answering this message.'}
                    </p>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {actionRequired.confidence_mode !== 'permissive' && (
                        <button
                          type="button"
                          onClick={(e) => {
                            const lastUserMsg = messages.filter(m => m.role === 'user').slice(-1)[0]?.content || input;
                            handleSend(e, lastUserMsg, undefined, 'permissive');
                          }}
                          style={{ padding: '0.4rem 0.8rem', backgroundColor: 'transparent', color: 'var(--status-pending-text)', border: '1px solid var(--status-pending-text)', borderRadius: '0.375rem', fontSize: '0.75rem', fontWeight: 500, cursor: 'pointer' }}
                        >
                          Try Permissive Mode
                        </button>
                      )}
                      {actionRequired.fallback_options?.includes('search_web') && (
                        <button
                          type="button"
                          onClick={(e) => {
                            const lastUserMsg = messages.filter(m => m.role === 'user').slice(-1)[0]?.content || input;
                            handleSend(e, lastUserMsg, 'search_web');
                          }}
                          className="btn-primary"
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem', height: 'auto' }}
                        >
                          🌐 Search Web with Tavily
                        </button>
                      )}
                      {actionRequired.fallback_options?.includes('general_model') && (
                        <button
                          type="button"
                          onClick={(e) => {
                            const lastUserMsg = messages.filter(m => m.role === 'user').slice(-1)[0]?.content || input;
                            handleSend(e, lastUserMsg, 'general_model');
                          }}
                          style={{ padding: '0.4rem 0.8rem', backgroundColor: 'var(--surface-light)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '0.375rem', fontSize: '0.75rem', fontWeight: 500, cursor: 'pointer' }}
                        >
                          🤖 Answer from General Knowledge
                        </button>
                      )}
                    </div>
                  </div>
                )}
                
                <form onSubmit={handleSend} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <select 
                    value={selectedDocumentId} 
                    onChange={(e) => setSelectedDocumentId(e.target.value)}
                    style={{ padding: '0.5rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem', fontSize: '0.875rem', maxWidth: '200px', backgroundColor: 'var(--surface-light)', color: 'var(--text-primary)' }}
                  >
                    <option value="">All Documents</option>
                    {documents.map(doc => (
                      <option key={doc.id} value={doc.id}>{doc.title}</option>
                    ))}
                  </select>
                  <input 
                    type="text" 
                    value={input} 
                    onChange={e => setInput(e.target.value)}
                    disabled={sending}
                    placeholder="Ask a question..."
                    style={{ flex: 1, padding: '0.75rem 1rem', border: '1px solid var(--border-color)', borderRadius: '2rem', fontSize: '0.875rem', backgroundColor: 'var(--surface-light)', color: 'var(--text-primary)' }}
                  />
                  <button 
                    type="submit" 
                    disabled={sending || !input.trim()}
                    className="btn-primary"
                    style={{ padding: '0.5rem 1.5rem', borderRadius: '2rem', cursor: sending || !input.trim() ? 'not-allowed' : 'pointer', opacity: sending || !input.trim() ? 0.5 : 1 }}
                  >
                    {sending ? 'Sending...' : 'Send'}
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
