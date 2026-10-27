'use client';

import React, { useState, useEffect } from 'react';
import {
  CurationSuggestion,
  KnowledgeBriefing,
  CurationLog,
  triggerCurationSweep,
  getCurationSuggestions,
  approveCurationSuggestion,
  rejectCurationSuggestion,
  applyCurationSuggestion,
  rollbackCurationSuggestion,
  getKnowledgeBriefings,
  getCurationLogs
} from '../lib/api';

export default function CurationDashboard() {
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'applied' | 'briefings' | 'logs'>('pending');
  const [suggestions, setSuggestions] = useState<CurationSuggestion[]>([]);
  const [briefings, setBriefings] = useState<KnowledgeBriefing[]>([]);
  const [logs, setLogs] = useState<CurationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [sweepLoading, setSweepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'briefings') {
        const b = await getKnowledgeBriefings();
        setBriefings(b);
      } else if (activeTab === 'logs') {
        const l = await getCurationLogs();
        setLogs(l);
      } else {
        const s = await getCurationSuggestions(activeTab === 'pending' ? 'pending' : activeTab === 'approved' ? 'approved' : activeTab === 'applied' ? 'applied' : undefined);
        setSuggestions(s);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load curation data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [activeTab]);

  async function handleRunSweep() {
    setSweepLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const resp = await triggerCurationSweep(true); // default dry_run=True
      setSuccessMsg(`Sweep completed! Discovered ${resp.suggestions_created} suggestions across memories and graph.`);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Curation sweep failed');
    } finally {
      setSweepLoading(false);
    }
  }

  async function handleApprove(id: string) {
    try {
      await approveCurationSuggestion(id);
      setSuggestions(prev => prev.filter(s => s.id !== id));
      setSuccessMsg('Suggestion approved and queued for application.');
    } catch (err: any) {
      setError(err.message || 'Failed to approve');
    }
  }

  async function handleReject(id: string) {
    try {
      await rejectCurationSuggestion(id);
      setSuggestions(prev => prev.filter(s => s.id !== id));
      setSuccessMsg('Suggestion rejected and dismissed.');
    } catch (err: any) {
      setError(err.message || 'Failed to reject');
    }
  }

  async function handleApply(id: string) {
    try {
      await applyCurationSuggestion(id);
      setSuggestions(prev => prev.filter(s => s.id !== id));
      setSuccessMsg('Suggestion successfully applied to knowledge base!');
    } catch (err: any) {
      setError(err.message || 'Failed to apply suggestion');
    }
  }

  async function handleRollback(id: string) {
    try {
      await rollbackCurationSuggestion(id);
      setSuggestions(prev => prev.filter(s => s.id !== id));
      setSuccessMsg('Applied action successfully rolled back.');
    } catch (err: any) {
      setError(err.message || 'Failed to rollback suggestion');
    }
  }

  function getBadgeColor(type: string) {
    switch (type) {
      case 'memory_merge': return 'bg-indigo-900/40 text-indigo-300 border-indigo-700/50';
      case 'memory_contradiction': return 'bg-amber-900/40 text-amber-300 border-amber-700/50';
      case 'graph_bridge': return 'bg-purple-900/40 text-purple-300 border-purple-700/50';
      case 'graph_prune': return 'bg-rose-900/40 text-rose-300 border-rose-700/50';
      default: return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  }

  return (
    <div style={{ maxWidth: '72rem', margin: '0 auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', color: 'var(--text-primary)' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', backgroundColor: 'var(--surface-color)', border: '1px solid var(--border-color)', borderRadius: '1rem', padding: '1.5rem', boxShadow: 'var(--shadow-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🧹 Knowledge Cleanup
            </h1>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Detect duplicates and conflicts across your documents and memories. Nothing is applied or deleted without explicit confirmation.
            </p>
          </div>
          <button
            onClick={handleRunSweep}
            disabled={sweepLoading}
            className="btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1.25rem', borderRadius: '0.75rem', flexShrink: 0 }}
          >
            {sweepLoading ? (
              <>
                <div style={{ width: '1rem', height: '1rem', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.75s linear infinite' }} />
                <span>Scanning Base...</span>
              </>
            ) : (
              <>
                <span>🔍</span>
                <span>Run Background Sweep (dry_run=True)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div style={{ backgroundColor: 'var(--status-error-bg)', border: '1px solid var(--status-error-text)', color: 'var(--status-error-text)', padding: '1rem', borderRadius: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}>✕</button>
        </div>
      )}
      {successMsg && (
        <div style={{ backgroundColor: 'var(--status-ok-bg)', border: '1px solid var(--status-ok-text)', color: 'var(--status-ok-text)', padding: '1rem', borderRadius: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>✨ {successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}>✕</button>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
        {[
          { id: 'pending', label: '⏳ Pending Suggestions', badge: suggestions.length },
          { id: 'approved', label: '✅ Approved / Ready to Apply' },
          { id: 'applied', label: '📜 Applied History' },
          { id: 'briefings', label: '📰 Cleanup Briefings Feed' },
          { id: 'logs', label: '📋 Sweep Audit Logs' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={activeTab === tab.id ? 'tab-btn active' : 'tab-btn'}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <span>{tab.label}</span>
            {tab.badge !== undefined && tab.id === activeTab && (
              <span style={{ background: 'rgba(59,130,246,0.2)', color: 'var(--accent-color)', fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px', border: '1px solid rgba(59,130,246,0.3)' }}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center gap-3">
          <div className="w-8 h-8 border-3 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading stewardship records...</span>
        </div>
      ) : activeTab === 'briefings' ? (
        <div className="space-y-4">
          {briefings.length === 0 ? (
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-12 text-center text-slate-400">
              No knowledge briefings found. Run a curation sweep to generate a proactive digest!
            </div>
          ) : (
            briefings.map(b => (
              <div key={b.id} className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-md space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                  <h3 className="text-lg font-bold text-teal-300">{b.title}</h3>
                  <span className="text-xs text-slate-400">{new Date(b.created_at).toLocaleString()}</span>
                </div>
                <div className="prose prose-invert max-w-none text-sm text-slate-300 whitespace-pre-wrap">
                  {b.summary_markdown}
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === 'logs' ? (
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-md overflow-x-auto">
          {logs.length === 0 ? (
            <div className="py-8 text-center text-slate-400">No sweep logs recorded yet.</div>
          ) : (
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-semibold">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Sweep Mode</th>
                  <th className="py-3 px-4">Items Processed</th>
                  <th className="py-3 px-4">Breakdown</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {logs.map(l => (
                  <tr key={l.id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-4 text-slate-300">{new Date(l.created_at).toLocaleString()}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${l.sweep_type === 'dry_run' ? 'bg-amber-900/40 text-amber-300 border border-amber-700/40' : 'bg-teal-900/40 text-teal-300 border border-teal-700/40'}`}>
                        {l.sweep_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-teal-400">{l.items_processed}</td>
                    <td className="py-3 px-4 text-xs text-slate-400">
                      {JSON.stringify(l.details || {})}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">{l.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        /* Suggestions Grid (`pending`, `approved`, `applied`) */
        <div className="space-y-4">
          {suggestions.length === 0 ? (
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-12 text-center text-slate-400">
              No {activeTab} suggestions available right now.
            </div>
          ) : (
            suggestions.map(s => (
              <div key={s.id} className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 transition-all hover:border-slate-700">
                {/* Header: Badge & Confidence */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 rounded-lg text-xs font-bold border ${getBadgeColor(s.suggestion_type)}`}>
                      {s.suggestion_type.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="text-xs text-slate-400">Discovered {new Date(s.created_at).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-slate-400">Confidence:</span>
                    <span className={`px-2 py-0.5 rounded font-bold ${s.confidence >= 0.85 ? 'bg-teal-950 text-teal-300 border border-teal-700/50' : 'bg-amber-950 text-amber-300 border border-amber-700/50'}`}>
                      {Math.round(s.confidence * 100)}%
                    </span>
                  </div>
                </div>

                {/* Explanation */}
                <div className="text-sm text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                  <span className="font-semibold text-teal-400">🤖 Cleanup Rationale: </span>
                  {s.explanation || 'No rationale provided.'}
                </div>

                {/* Split-View Provenance vs Proposed */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Left: Original Sources */}
                  <div className="bg-slate-950/80 border border-slate-800/90 rounded-xl p-3 space-y-2">
                    <div className="text-slate-400 font-semibold border-b border-slate-800 pb-1.5 flex items-center justify-between">
                      <span>📌 Original Sources ({s.source_ids.length})</span>
                      {s.provenance_metadata?.privacy_rule && (
                        <span className="text-amber-400 font-mono text-[11px]">{s.provenance_metadata.privacy_rule}</span>
                      )}
                    </div>
                    {s.provenance_metadata?.sources ? (
                      <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                        {s.provenance_metadata.sources.map((src: any, idx: number) => (
                          <div key={idx} className="bg-slate-900 p-2 rounded border border-slate-800/70 space-y-1">
                            <div className="flex justify-between text-[11px] text-slate-400">
                              <span>ID: {src.id?.slice(0, 8)}...</span>
                              <span className="text-teal-400 font-mono">[{src.privacy_level || 'private'}]</span>
                            </div>
                            <div className="text-slate-300 italic">"{src.content}"</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <pre className="text-slate-400 overflow-x-auto p-1 max-h-36">
                        {JSON.stringify(s.provenance_metadata, null, 2)}
                      </pre>
                    )}
                  </div>

                  {/* Right: Proposed Action / Consolidated Payload */}
                  <div className="bg-teal-950/20 border border-teal-900/50 rounded-xl p-3 space-y-2">
                    <div className="text-teal-300 font-semibold border-b border-teal-900/40 pb-1.5 flex items-center justify-between">
                      <span>✨ Proposed Consolidated Target</span>
                      {s.proposed_payload?.privacy_level && (
                        <span className="px-1.5 py-0.5 bg-teal-900/60 text-teal-200 rounded font-mono text-[11px] border border-teal-700">
                          🔒 {s.proposed_payload.privacy_level}
                        </span>
                      )}
                    </div>
                    {s.suggestion_type.startsWith('memory_') ? (
                      <div className="space-y-2">
                        <div className="text-sm text-slate-100 font-medium bg-teal-950/40 p-2.5 rounded border border-teal-800/40">
                          "{s.proposed_payload.content}"
                        </div>
                        <div className="flex justify-between text-[11px] text-slate-400 pt-1">
                          <span>Category: <strong className="text-teal-300">{s.proposed_payload.category}</strong></span>
                          <span>Inherited Privacy: <strong className="text-amber-300">{s.proposed_payload.privacy_level}</strong></span>
                        </div>
                      </div>
                    ) : (
                      <pre className="text-teal-200/90 overflow-x-auto p-1 max-h-36 font-mono text-xs">
                        {JSON.stringify(s.proposed_payload, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>

                {/* Actions Bar */}
                <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800/60">
                  {s.status === 'pending' && (
                    <>
                      <button
                        onClick={() => handleReject(s.id)}
                        className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-950/60 text-rose-300 hover:bg-rose-900/80 border border-rose-800/60 transition-all"
                      >
                        ✕ Reject & Dismiss
                      </button>
                      <button
                        onClick={() => handleApprove(s.id)}
                        className="px-4 py-2 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white shadow-md shadow-teal-600/20 transition-all"
                      >
                        ✓ Approve Suggestion
                      </button>
                    </>
                  )}
                  {s.status === 'approved' && (
                    <>
                      <button
                        onClick={() => handleReject(s.id)}
                        className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all"
                      >
                        Cancel / Reject
                      </button>
                      <button
                        onClick={() => handleApply(s.id)}
                        className="px-5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white shadow-lg shadow-emerald-500/20 transition-all"
                      >
                        🚀 Apply Now (Commit to Knowledge Base)
                      </button>
                    </>
                  )}
                  {s.status === 'applied' && (
                    <button
                      onClick={() => handleRollback(s.id)}
                      className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-950/80 text-amber-300 hover:bg-amber-900 border border-amber-800/80 transition-all"
                    >
                      ↩ Rollback Applied Action
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
