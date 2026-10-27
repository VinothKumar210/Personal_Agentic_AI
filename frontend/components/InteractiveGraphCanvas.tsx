"use client";

import React, { useState, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { KnowledgeGraphNode, KnowledgeGraphEdge } from '@/lib/api';

// Dynamically import force graphs to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), { ssr: false });

interface InteractiveGraphCanvasProps {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  selectedNodeId: string | null;
  onSelectNode: (node: KnowledgeGraphNode | null) => void;
  searchQuery?: string;
}

export default function InteractiveGraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  searchQuery = '',
}: InteractiveGraphCanvasProps) {
  const [mode, setMode] = useState<'2d' | '3d'>('2d');

  // Memoize graph data format required by react-force-graph
  const graphData = useMemo(() => {
    return {
      nodes: nodes.map(n => ({ ...n })), // Copy to avoid mutating props
      links: edges.map(e => ({
        ...e,
        source: e.source_node_id,
        target: e.target_node_id,
      }))
    };
  }, [nodes, edges]);

  // Visual encoding helpers
  const getNodeColor = useCallback((node: any) => {
    const isSelected = selectedNodeId === node.id;
    const isPruned = node.is_pruned;
    
    let color = '#3b82f6'; // Default blue
    
    // Example mapping by type (if backend returns these types)
    if (node.node_type === 'concept') color = '#10b981'; // Green
    else if (node.node_type === 'entity') color = '#f59e0b'; // Yellow
    else if (node.node_type === 'document') color = '#8b5cf6'; // Purple
    
    if (isPruned) color = '#94a3b8'; // Gray out pruned nodes
    if (isSelected) color = '#ef4444'; // Red for selected
    
    return color;
  }, [selectedNodeId]);

  const getNodeVal = useCallback((node: any) => {
    // node size based on frequency
    return Math.max(1, Math.min(10, Math.sqrt(node.frequency || 1)));
  }, []);

  const getLinkColor = useCallback((link: any) => {
    const isInferred = link.relation_type?.startsWith('inferred');
    return isInferred ? 'rgba(168, 85, 247, 0.4)' : 'rgba(148, 163, 184, 0.4)';
  }, []);

  const getLinkWidth = useCallback((link: any) => {
    return Math.max(1, Math.min(4, (link.weight || 1) * 0.8));
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '600px', backgroundColor: '#f8fafc', borderRadius: '0.75rem', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 10 }}>
        <button
          onClick={() => setMode('2d')}
          style={{
            padding: '6px 12px',
            backgroundColor: mode === '2d' ? '#3b82f6' : '#e2e8f0',
            color: mode === '2d' ? '#fff' : '#475569',
            border: 'none',
            borderRadius: '4px 0 0 4px',
            cursor: 'pointer'
          }}
        >
          2D
        </button>
        <button
          onClick={() => setMode('3d')}
          style={{
            padding: '6px 12px',
            backgroundColor: mode === '3d' ? '#3b82f6' : '#e2e8f0',
            color: mode === '3d' ? '#fff' : '#475569',
            border: 'none',
            borderRadius: '0 4px 4px 0',
            cursor: 'pointer'
          }}
        >
          3D
        </button>
      </div>

      {mode === '2d' ? (
        <ForceGraph2D
          graphData={graphData}
          nodeLabel="label"
          nodeColor={getNodeColor}
          nodeVal={getNodeVal}
          linkColor={getLinkColor}
          linkWidth={getLinkWidth}
          onNodeClick={(node: any) => onSelectNode(node)}
          width={800} // Force initial render dimensions, it handles resize if wrap in AutoSizer, but fixed is fine if container flexes
          height={600}
        />
      ) : (
        <ForceGraph3D
          graphData={graphData}
          nodeLabel="label"
          nodeColor={getNodeColor}
          nodeVal={getNodeVal}
          linkColor={getLinkColor}
          linkWidth={getLinkWidth}
          onNodeClick={(node: any) => onSelectNode(node)}
          width={800}
          height={600}
          enableNodeDrag={false}
        />
      )}
    </div>
  );
}
