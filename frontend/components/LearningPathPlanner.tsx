'use client';

import React, { useState, useEffect } from 'react';
import {
  LearningProfile,
  LearningPathResponse,
  createLearningProfile,
  listLearningProfiles,
  analyzeLearningPath,
  deleteLearningProfile
} from '../lib/api';

export default function LearningPathPlanner() {
  const [profiles, setProfiles] = useState<LearningProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [goalTitle, setGoalTitle] = useState('');
  const [targetRole, setTargetRole] = useState('llm_engineer');
  const [currentLevel, setCurrentLevel] = useState('');
  const [focusKeywords, setFocusKeywords] = useState('');
  
  const [analysisResult, setAnalysisResult] = useState<LearningPathResponse | null>(null);

  const fetchProfiles = async () => {
    try {
      setLoading(true);
      const res = await listLearningProfiles();
      setProfiles(res);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load learning profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalTitle.trim()) {
      setError("Goal title is required.");
      return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      setAnalysisResult(null);
      
      const keywords = focusKeywords.split(',').map(k => k.trim()).filter(k => k);
      
      // Create profile
      const profile = await createLearningProfile({
        goal_title: goalTitle,
        target_role: targetRole,
        current_level: currentLevel || undefined,
        focus_keywords: keywords
      });
      
      // Analyze
      const result = await analyzeLearningPath({
        profile_id: profile.id,
        target_role: targetRole,
        max_recommendations: 8
      });
      
      setAnalysisResult(result);
      await fetchProfiles();
    } catch (err: any) {
      setError(err.message || 'Failed to analyze learning path.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDeleteProfile = async (id: string) => {
    try {
      await deleteLearningProfile(id);
      await fetchProfiles();
      if (analysisResult?.profile?.id === id) {
        setAnalysisResult(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete profile.');
    }
  };

  const loadProfileResult = async (profileId: string, role?: string) => {
    try {
      setAnalyzing(true);
      setError(null);
      const result = await analyzeLearningPath({
        profile_id: profileId,
        target_role: role || 'llm_engineer',
        max_recommendations: 8
      });
      setAnalysisResult(result);
    } catch (err: any) {
      setError(err.message || 'Failed to load profile analysis.');
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="learning-planner">
      <div className="learning-header">
        <div>
          <h2 className="title" style={{fontSize: "1.5rem"}}>Skill Coverage Checklist</h2>
          <p className="subtitle">Skill Gap Analysis & Heuristic Recommendations based on your stored knowledge.</p>
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <div className="learning-content">
        <div className="learning-form-section">
          <h3>Create New Profile</h3>
          <form onSubmit={handleAnalyze} className="learning-form">
            <div className="form-group">
              <label>Goal Title</label>
              <input 
                type="text" 
                value={goalTitle} 
                onChange={e => setGoalTitle(e.target.value)} 
                placeholder="e.g. Master LLM Engineering"
                className="form-input"
              />
            </div>
            
            <div className="form-group">
              <label>Target Role</label>
              <select 
                value={targetRole} 
                onChange={e => setTargetRole(e.target.value)}
                className="form-input"
              >
                <option value="llm_engineer">LLM Engineer</option>
                <option value="backend_engineer">Backend Engineer</option>
                <option value="full_stack_ai_engineer">Full-Stack AI Engineer</option>
              </select>
            </div>

            <div className="form-group">
              <label>Current Level</label>
              <input 
                type="text" 
                value={currentLevel} 
                onChange={e => setCurrentLevel(e.target.value)} 
                placeholder="e.g. Beginner, Intermediate"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label>Focus Keywords (comma separated)</label>
              <input 
                type="text" 
                value={focusKeywords} 
                onChange={e => setFocusKeywords(e.target.value)} 
                placeholder="e.g. RAG, Python, React"
                className="form-input"
              />
            </div>

            <button type="submit" disabled={analyzing} className="btn btn-primary" style={{width: '100%'}}>
              {analyzing ? 'Analyzing...' : 'Analyze Skill Gap'}
            </button>
          </form>

          {profiles.length > 0 && (
            <div className="learning-profiles">
              <h3 style={{marginTop: '2rem'}}>Saved Profiles</h3>
              <div className="profiles-list">
                {profiles.map(p => (
                  <div key={p.id} className="profile-item">
                    <div>
                      <strong>{p.goal_title}</strong>
                      <span style={{display: 'block', fontSize: '0.8rem', color: '#64748b'}}>
                        Role: {p.target_role?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div style={{display: 'flex', gap: '0.5rem'}}>
                      <button onClick={() => loadProfileResult(p.id, p.target_role)} className="btn" style={{padding: '0.25rem 0.5rem', fontSize: '0.8rem'}}>View</button>
                      <button onClick={() => handleDeleteProfile(p.id)} className="btn-delete">Del</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="learning-results">
          {analysisResult ? (
            <div className="analysis-board">
              <div className="analysis-summary">
                <p><strong>Message:</strong> {analysisResult.message}</p>
              </div>

              <div className="strengths-gaps-grid">
                <div className="strengths-box">
                  <h4>Strengths ({analysisResult.strengths.length})</h4>
                  {analysisResult.strengths.length > 0 ? (
                    <ul className="learning-list">
                      {analysisResult.strengths.map(s => <li key={s} className="strength-item">[+] {s.replace(/_/g, ' ')}</li>)}
                    </ul>
                  ) : (
                    <p className="learning-empty-text">No matching strengths found in knowledge base.</p>
                  )}
                </div>
                
                <div className="gaps-box">
                  <h4>Gaps ({analysisResult.gaps.length})</h4>
                  {analysisResult.gaps.length > 0 ? (
                    <ul className="learning-list">
                      {analysisResult.gaps.map(g => <li key={g} className="gap-item">[-] {g.replace(/_/g, ' ')}</li>)}
                    </ul>
                  ) : (
                    <p className="learning-empty-text">No gaps identified!</p>
                  )}
                </div>
              </div>

              <div className="recommendations-section">
                <h4>Heuristic Recommendations</h4>
                {analysisResult.recommendations.length > 0 ? (
                  <div className="recommendation-grid">
                    {analysisResult.recommendations.map(r => (
                      <div key={r.id} className="recommendation-card">
                        <div className="rec-header">
                          <h5 className="rec-title">{r.title}</h5>
                          <span className="rec-priority">Priority: {r.priority}</span>
                        </div>
                        <p className="rec-desc">{r.description}</p>
                        <p className="rec-reason"><strong>Reason:</strong> {r.reason}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="learning-empty-text">No recommendations at this time.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="learning-empty">
              <p>Fill out the form and click "Analyze Skill Gap" to generate heuristic recommendations based on your knowledge base.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
