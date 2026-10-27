'use client';

import React, { useState, useEffect } from 'react';
import { 
  TopicCluster, 
  listTopicClusters, 
  triggerAutoCluster,
  getJobStatus
} from '../lib/api';

export default function TopicExplorer() {
  const [clusters, setClusters] = useState<TopicCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchClusters = async () => {
    try {
      setLoading(true);
      const res = await listTopicClusters();
      setClusters(res.clusters || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load topic clusters.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusters();
  }, []);

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      setError(null);
      const res = await triggerAutoCluster({ min_clusters: 2, max_clusters: 8, min_chunks: 5 });
      pollJobStatus(res.job_id);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze topics.');
      setAnalyzing(false);
    }
  };

  const pollJobStatus = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const statusResponse = await getJobStatus(jobId);
        const status = statusResponse.job || statusResponse;
        if (status.status === 'succeeded') {
          clearInterval(interval);
          setAnalyzing(false);
          fetchClusters();
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setAnalyzing(false);
          setError(`Analysis failed: ${status.error_message || 'Unknown error'}`);
        }
      } catch (err: any) {
        clearInterval(interval);
        setAnalyzing(false);
        setError('Error polling job status');
      }
    }, 2000);
  };

  return (
    <div className="topic-explorer">
      <div className="topic-header">
        <div>
          <h2 className="title" style={{fontSize: "1.5rem"}}>Topic Explorer</h2>
          <p className="subtitle">Discover recurring concepts and themes across your documents.</p>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="btn btn-primary"
        >
          {analyzing ? 'Analyzing...' : 'Analyze Topics'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {loading ? (
        <div className="topic-empty">Loading topic clusters...</div>
      ) : clusters.length === 0 ? (
        <div className="topic-empty">
          No topic clusters found. Click "Analyze Topics" to group your documents by concept.
        </div>
      ) : (
        <div className="topic-grid">
          {clusters.map((cluster) => {
            let keywords: string[] = [];
            try {
              if (cluster.keywords_json) {
                keywords = JSON.parse(cluster.keywords_json);
              }
            } catch (e) {
              // Ignore parse error
            }
            
            return (
              <div key={cluster.id} className="topic-card">
                <h3 className="topic-title">{cluster.name}</h3>
                {cluster.description && (
                  <p className="topic-description" style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                    {cluster.description}
                  </p>
                )}
                
                <div className="topic-meta">
                  <span>{cluster.document_count} document{cluster.document_count !== 1 ? 's' : ''}</span>
                  <span>{cluster.chunk_count} chunk{cluster.chunk_count !== 1 ? 's' : ''}</span>
                </div>
                
                {keywords.length > 0 && (
                  <div className="topic-keywords">
                    {keywords.map((kw, i) => (
                      <span key={i} className="topic-keyword">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
