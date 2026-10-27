"use client";

import { useState, useEffect, useMemo } from 'react';
import { 
  getKnowledgeGraph, 
  buildKnowledgeGraph, 
  getKnowledgeNodeDocuments,
  KnowledgeGraphResponse,
  KnowledgeGraphNode,
  KnowledgeGraphEdge,
  DocumentRead
} from '@/lib/api';
import InteractiveGraphCanvas from './InteractiveGraphCanvas';

interface KnowledgeGraphPanelProps {
  onNavigateToDocument?: (docId: string) => void;
  onOpenChat?: (initialQuery: string) => void;
}

export default function KnowledgeGraphPanel({
  onNavigateToDocument,
  onOpenChat,
}: KnowledgeGraphPanelProps) {
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // View controls & Filters
  const [viewMode, setViewMode] = useState<'canvas' | 'list'>('canvas');
  const [searchQuery, setSearchQuery] = useState('');
  const [minFreqFilter, setMinFreqFilter] = useState<number>(1);

  // Selection & Inspector Drawer state
  const [selectedNode, setSelectedNode] = useState<KnowledgeGraphNode | null>(null);
  const [nodeDocs, setNodeDocs] = useState<DocumentRead[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraph();
  }, []);

  const fetchGraph = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getKnowledgeGraph();
      setData(result);
    } catch (err: any) {
      setError(err.message || "Failed to load knowledge graph.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleBuildGraph = async () => {
    setIsBuilding(true);
    setError(null);
    try {
      const result = await buildKnowledgeGraph({ min_frequency: minFreqFilter });
      setData(result);
      setSelectedNode(null);
    } catch (err: any) {
      setError(err.message || "Failed to build knowledge graph.");
    } finally {
      setIsBuilding(false);
    }
  };

  // Fetch associated documents whenever selectedNode changes
  useEffect(() => {
    if (!selectedNode) {
      setNodeDocs([]);
      setDocsError(null);
      return;
    }

    let active = true;
    const fetchNodeDocuments = async () => {
      setLoadingDocs(true);
      setDocsError(null);
      try {
        const docs = await getKnowledgeNodeDocuments(selectedNode.id);
        if (active) {
          setNodeDocs(docs);
        }
      } catch (err: any) {
        if (active) {
          setDocsError(err.message || "Failed to retrieve concept documents.");
        }
      } finally {
        if (active) {
          setLoadingDocs(false);
        }
      }
    };

    fetchNodeDocuments();
    return () => {
      active = false;
    };
  }, [selectedNode]);

  // Filter nodes and edges by minimum frequency and valid relationships
  const { filteredNodes, filteredEdges } = useMemo(() => {
    if (!data) return { filteredNodes: [], filteredEdges: [] };

    const nodes = data.nodes.filter((node) => node.frequency >= minFreqFilter);
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter(
      (edge) => nodeIds.has(edge.source_node_id) && nodeIds.has(edge.target_node_id)
    );

    return { filteredNodes: nodes, filteredEdges: edges };
  }, [data, minFreqFilter]);

  // Find connected edges and neighbors for the selected node
  const connectedNeighbors = useMemo(() => {
    if (!selectedNode || !data) return [];
    const neighbors: { node: KnowledgeGraphNode; weight: number; relation: string }[] = [];

    data.edges.forEach((edge) => {
      if (edge.source_node_id === selectedNode.id) {
        const target = data.nodes.find((n) => n.id === edge.target_node_id);
        if (target) {
          neighbors.push({ node: target, weight: edge.weight, relation: edge.relation_type || 'co-occurs' });
        }
      } else if (edge.target_node_id === selectedNode.id) {
        const source = data.nodes.find((n) => n.id === edge.source_node_id);
        if (source) {
          neighbors.push({ node: source, weight: edge.weight, relation: edge.relation_type || 'co-occurs' });
        }
      }
    });

    return neighbors.sort((a, b) => b.weight - a.weight);
  }, [selectedNode, data]);

  if (isLoading && !data) {
    return (
      <div className="kg-panel">
        <h2 className="kg-title">Concept Map</h2>
        <p className="kg-meta">Loading concept canvas...</p>
      </div>
    );
  }

  return (
    <div className="kg-panel">
      <div className="kg-header" style={{ flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
        <div>
          <h2 className="kg-title">Concept Map</h2>
          <div style={{ marginBottom: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <p className="kg-meta" style={{ marginBottom: 0 }}>
              Visual force-directed map of concepts automatically extracted from your documents. Click nodes to inspect.
            </p>
            <div style={{ fontSize: '0.75rem', color: '#92400e', backgroundColor: '#fef3c7', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #f59e0b', display: 'inline-block', alignSelf: 'flex-start' }}>
              <strong>Note:</strong> Concepts are extracted automatically and may contain noise. Run <em>Knowledge Cleanup</em> to refine them.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* View Switcher */}
          <div style={{ display: 'flex', backgroundColor: 'var(--background-color)', borderRadius: '0.5rem', padding: '0.25rem', border: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => setViewMode('canvas')}
              style={{
                padding: '0.375rem 0.75rem',
                border: 'none',
                background: viewMode === 'canvas' ? 'var(--primary-color)' : 'transparent',
                color: viewMode === 'canvas' ? '#ffffff' : 'var(--text-color)',
                borderRadius: '0.375rem',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Interactive Canvas
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              style={{
                padding: '0.375rem 0.75rem',
                border: 'none',
                background: viewMode === 'list' ? 'var(--primary-color)' : 'transparent',
                color: viewMode === 'list' ? '#ffffff' : 'var(--text-color)',
                borderRadius: '0.375rem',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              List / Table View
            </button>
          </div>

          {/* Rebuild Graph Button */}
          <button
            onClick={handleBuildGraph}
            disabled={isBuilding}
            className="kg-build-btn"
          >
            {isBuilding ? 'Rebuilding Graph...' : 'Rebuild Graph'}
          </button>
        </div>
      </div>

      {/* Toolbar & Filter Bar */}
      <div
        style={{
          display: 'flex',
          gap: '1rem',
          alignItems: 'center',
          flexWrap: 'wrap',
          margin: '1rem 0 1.25rem 0',
          padding: '0.75rem 1rem',
          backgroundColor: 'var(--background-color)',
          borderRadius: '0.5rem',
          border: '1px solid var(--border-color)',
        }}
      >
        <div style={{ flex: '1 1 200px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label htmlFor="kg-search" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Search Concept:
          </label>
          <input
            id="kg-search"
            type="text"
            placeholder="Filter concepts by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              padding: '0.375rem 0.75rem',
              border: '1px solid var(--border-color)',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
              backgroundColor: 'var(--surface-color)',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}
            >
              Clear
            </button>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label htmlFor="kg-min-freq" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Min Frequency:
          </label>
          <select
            id="kg-min-freq"
            value={minFreqFilter}
            onChange={(e) => setMinFreqFilter(Number(e.target.value))}
            style={{
              padding: '0.375rem 0.625rem',
              border: '1px solid var(--border-color)',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
              backgroundColor: 'var(--surface-color)',
            }}
          >
            <option value={1}>1+ (All Concepts)</option>
            <option value={2}>2+ (Repeated)</option>
            <option value={3}>3+ (Frequent)</option>
            <option value={5}>5+ (Core Concepts)</option>
            <option value={10}>10+ (Major Hubs)</option>
          </select>
        </div>

        {data && (
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Showing <strong>{filteredNodes.length}</strong> concepts and <strong>{filteredEdges.length}</strong> relationships
          </div>
        )}
      </div>

      {error && (
        <div className="error-message" role="alert" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {data?.message && data.nodes.length === 0 && (
        <div className="kg-empty">
          <p>{data.message}</p>
        </div>
      )}

      {/* Main Workspace (Canvas/List + Inspector Drawer) */}
      {data && data.nodes.length > 0 && (
        <div style={{ display: 'flex', gap: '1.25rem', position: 'relative' }}>
          {/* Main Content Area */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {viewMode === 'canvas' ? (
              <InteractiveGraphCanvas
                nodes={filteredNodes}
                edges={filteredEdges}
                selectedNodeId={selectedNode?.id || null}
                onSelectNode={(node) => setSelectedNode(node)}
                searchQuery={searchQuery}
              />
            ) : (
              <div className="kg-content" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                <div className="kg-section">
                  <h3 className="kg-section-title">Concept Nodes ({filteredNodes.length})</h3>
                  <div className="kg-nodes">
                    {filteredNodes
                      .filter((n) => !searchQuery || n.label.toLowerCase().includes(searchQuery.toLowerCase()))
                      .map((node) => (
                        <div
                          key={node.id}
                          className="kg-node"
                          onClick={() => setSelectedNode(node)}
                          style={{
                            cursor: 'pointer',
                            border: selectedNode?.id === node.id ? '2px solid var(--primary-color)' : undefined,
                            backgroundColor: selectedNode?.id === node.id ? 'rgba(79, 70, 229, 0.08)' : undefined,
                          }}
                        >
                          <span className="kg-node-label">{node.label}</span>
                          <span className="kg-node-freq">{node.frequency}</span>
                        </div>
                      ))}
                  </div>
                </div>

                <div className="kg-section" style={{ marginTop: '1.5rem' }}>
                  <h3 className="kg-section-title">Relationships ({filteredEdges.length})</h3>
                  <div className="kg-edges">
                    {filteredEdges
                      .sort((a, b) => b.weight - a.weight)
                      .slice(0, 30)
                      .map((edge) => {
                        const source = data.nodes.find((n) => n.id === edge.source_node_id);
                        const target = data.nodes.find((n) => n.id === edge.target_node_id);
                        if (!source || !target) return null;
                        return (
                          <div
                            key={edge.id}
                            className="kg-edge"
                            onClick={() => setSelectedNode(source)}
                            style={{ cursor: 'pointer' }}
                          >
                            <span className="kg-edge-nodes">{source.label} &lt;-&gt; {target.label}</span>
                            <span className="kg-edge-weight">wt: {edge.weight}</span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Concept Node Inspector Drawer */}
          {selectedNode && (
            <div
              className="kg-inspector-drawer"
              style={{
                width: '340px',
                flexShrink: 0,
                backgroundColor: 'var(--surface-color)',
                border: '1px solid var(--border-color)',
                borderRadius: '0.75rem',
                padding: '1.25rem',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.08)',
                maxHeight: '600px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
              }}
            >
              {/* Drawer Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 600, letterSpacing: '0.05em' }}>
                    Concept Inspector
                  </span>
                  <h3 style={{ margin: '0.25rem 0 0 0', fontSize: '1.25rem', color: 'var(--primary-color)' }}>
                    {selectedNode.label}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  title="Close Inspector"
                  style={{
                    border: 'none',
                    background: 'var(--background-color)',
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    fontSize: '1rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-secondary)',
                  }}
                >
                  &times;
                </button>
              </div>

              {/* Concept Stats Card */}
              <div style={{ backgroundColor: 'var(--background-color)', padding: '0.75rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)', fontSize: '0.8125rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Frequency across docs:</span>
                  <strong style={{ color: 'var(--text-color)', fontSize: '0.9375rem' }}>{selectedNode.frequency}</strong>
                </div>
                {selectedNode.node_type && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Category Type:</span>
                    <span style={{ color: 'var(--text-color)' }}>{selectedNode.node_type}</span>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Connected Neighbors:</span>
                  <span style={{ color: 'var(--text-color)' }}>{connectedNeighbors.length}</span>
                </div>
                {selectedNode.is_pruned && (
                  <div style={{ marginTop: '0.625rem', padding: '0.5rem', backgroundColor: '#fef3c7', borderRadius: '0.375rem', border: '1px solid #f59e0b', color: '#92400e', fontSize: '0.75rem' }}>
                    <strong>⚠️ Soft-Pruned Concept: </strong>
                    {selectedNode.pruned_reason || 'Hidden from active traversal during curation.'}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {onOpenChat && (
                  <button
                    onClick={() => onOpenChat(`Explain what "${selectedNode.label}" is and summarize key points from my documents about it.`)}
                    style={{
                      flex: 1,
                      padding: '0.5rem 0.75rem',
                      backgroundColor: 'var(--primary-color)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '0.5rem',
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Ask AI About Concept
                  </button>
                )}
              </div>

              {/* Connected Concepts Section */}
              <div>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: 'var(--text-color)' }}>
                  Connected Concepts ({connectedNeighbors.length})
                </h4>
                {connectedNeighbors.length === 0 ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
                    No co-occurrence relationships found.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', maxHeight: '140px', overflowY: 'auto', padding: '0.25rem 0' }}>
                    {connectedNeighbors.map(({ node, weight }) => (
                      <button
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        style={{
                          padding: '0.25rem 0.5rem',
                          backgroundColor: 'var(--background-color)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '1rem',
                          fontSize: '0.75rem',
                          color: 'var(--text-color)',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                        }}
                        title={`Click to inspect ${node.label}`}
                      >
                        <span>{node.label}</span>
                        <span style={{ opacity: 0.6, fontSize: '0.6875rem' }}>({weight})</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Associated Documents Section */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.75rem' }}>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: 'var(--text-color)' }}>
                  Source Documents ({nodeDocs.length})
                </h4>

                {loadingDocs ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Loading source documents...</p>
                ) : docsError ? (
                  <div className="error-message" style={{ fontSize: '0.75rem', padding: '0.5rem' }}>
                    {docsError}
                  </div>
                ) : nodeDocs.length === 0 ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
                    No ready documents explicitly linked to this node.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
                    {nodeDocs.map((doc) => (
                      <div
                        key={doc.id}
                        style={{
                          padding: '0.625rem',
                          backgroundColor: 'var(--background-color)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '0.5rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.25rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '0.8125rem', color: 'var(--text-color)', wordBreak: 'break-word' }}>
                            {doc.title || doc.original_filename || 'Untitled Document'}
                          </strong>
                          <span
                            style={{
                              fontSize: '0.6875rem',
                              padding: '0.125rem 0.375rem',
                              borderRadius: '0.25rem',
                              backgroundColor: doc.status === 'ready' ? '#dcfce7' : '#f1f5f9',
                              color: doc.status === 'ready' ? '#166534' : '#475569',
                              fontWeight: 600,
                              textTransform: 'uppercase',
                            }}
                          >
                            {doc.status}
                          </span>
                        </div>
                        {doc.original_filename && doc.original_filename !== doc.title && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            File: {doc.original_filename}
                          </div>
                        )}
                        {onNavigateToDocument && (
                          <button
                            onClick={() => onNavigateToDocument(doc.id)}
                            style={{
                              marginTop: '0.25rem',
                              padding: '0.25rem 0.5rem',
                              backgroundColor: 'transparent',
                              border: '1px solid var(--primary-color)',
                              color: 'var(--primary-color)',
                              borderRadius: '0.375rem',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              alignSelf: 'flex-start',
                            }}
                          >
                            View in Library &rarr;
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
