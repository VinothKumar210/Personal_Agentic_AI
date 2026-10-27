"use client";

import { useEffect, useState } from "react";
import { checkHealth, HealthResponse } from "../lib/api";
import StatusCard from "./StatusCard";
import SemanticSearch from "./SemanticSearch";
import RagQuestionAnswer from "./RagQuestionAnswer";
import DocumentLibrary from "./DocumentLibrary";
import ChatMemory from "./ChatMemory";
import TopicExplorer from "./TopicExplorer";
import LearningPathPlanner from "./LearningPathPlanner";
import KnowledgeGraphPanel from "./KnowledgeGraphPanel";
import ExportRestorePanel from "./ExportRestorePanel";
import PersonalMemoryProfile from "./PersonalMemoryProfile";
import CurationDashboard from "./CurationDashboard";
import AuthPanel from "./AuthPanel";
import StudyModePanel from "./StudyModePanel";
import { MessageSquare, BookOpen, BrainCircuit, CheckSquare, Settings, LogOut } from 'lucide-react';
import { getMe } from "../lib/api";

type Section = 'ask' | 'library' | 'knowledge' | 'review' | 'settings';
type KnowledgeTab = 'search' | 'memory' | 'topic' | 'graph' | 'learning' | 'study';

export default function AppShell() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  
  const [activeSection, setActiveSection] = useState<Section>('ask');
  const [activeKnowledgeTab, setActiveKnowledgeTab] = useState<KnowledgeTab>('search');

  useEffect(() => {
    async function fetchHealth() {
      try {
        const data = await checkHealth();
        setHealth(data);
      } catch (error) {
        console.error("Failed to fetch health", error);
      } finally {
        setLoading(false);
      }
    }
    async function checkAuth() {
      try {
        const user = await getMe();
        if (user && user.email) {
          setIsAuthenticated(true);
          setUserEmail(user.email);
        }
      } catch (err) {
        setIsAuthenticated(false);
      }
    }

    fetchHealth();
    checkAuth();
  }, []);

  const handleLoginSuccess = async () => {
    try {
      const user = await getMe();
      if (user && user.email) {
        setIsAuthenticated(true);
        setUserEmail(user.email);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setUserEmail('');
  };

  if (!isAuthenticated) {
    return (
      <div className="app-shell" style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        background: 'radial-gradient(circle at center, #1e2436 0%, #0a0e1a 100%)'
      }}>
        <AuthPanel onLoginSuccess={handleLoginSuccess} />
      </div>
    );
  }

  const isHealthy = health && health.database === 'ok' && health.chroma === 'ok';

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar" style={{ width: '64px', alignItems: 'center', padding: '1rem 0' }}>
        <div className="sidebar-header" style={{ border: 'none', padding: '0.5rem' }}>
          <BrainCircuit size={28} color="var(--accent-color)" />
        </div>
        <nav className="sidebar-nav" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '2rem' }}>
          <button title="Ask & Chat" className={`nav-item ${activeSection === 'ask' ? 'active' : ''}`} onClick={() => setActiveSection('ask')} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: 'none', display: 'flex', justifyContent: 'center' }}>
            <MessageSquare size={24} />
          </button>
          <button title="Document Library" className={`nav-item ${activeSection === 'library' ? 'active' : ''}`} onClick={() => setActiveSection('library')} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: 'none', display: 'flex', justifyContent: 'center' }}>
            <BookOpen size={24} />
          </button>
          <button title="Knowledge Base Tools" className={`nav-item ${activeSection === 'knowledge' ? 'active' : ''}`} onClick={() => setActiveSection('knowledge')} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: 'none', display: 'flex', justifyContent: 'center' }}>
            <BrainCircuit size={24} />
          </button>
          <button title="Knowledge Cleanup" className={`nav-item ${activeSection === 'review' ? 'active' : ''}`} onClick={() => setActiveSection('review')} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: 'none', display: 'flex', justifyContent: 'center' }}>
            <CheckSquare size={24} />
          </button>
          <button title="Settings" className={`nav-item ${activeSection === 'settings' ? 'active' : ''}`} onClick={() => setActiveSection('settings')} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: 'none', display: 'flex', justifyContent: 'center' }}>
            <Settings size={24} />
          </button>
        </nav>
        <div className="sidebar-footer" style={{ border: 'none', marginTop: 'auto', padding: '1rem 0' }}>
          <button onClick={handleLogout} className="btn-logout" title={`Logout ${userEmail}`} style={{ display: 'flex', justifyContent: 'center' }}>
            <LogOut size={24} />
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="top-header">
          <h2 className="section-title">
            {activeSection === 'ask' && 'Ask & Chat'}
            {activeSection === 'library' && 'Document Library'}
            {activeSection === 'knowledge' && 'Knowledge Base Tools'}
            {activeSection === 'review' && 'Knowledge Cleanup'}
            {activeSection === 'settings' && 'System Settings'}
          </h2>
          <div className="health-indicator" title={isHealthy ? 'System OK' : 'System issues detected'}>
            <span className={`indicator ${isHealthy ? 'ok' : 'unavailable'}`}></span>
            <span className="health-text">{isHealthy ? 'Online' : 'Degraded'}</span>
          </div>
        </header>

        <div className="workspace">
          {activeSection === 'ask' && (
            <div className="workspace-ask">
              {/* Optional: We can add an empty state here if no chats, but ChatMemory handles that */}
              <ChatMemory />
            </div>
          )}

          {activeSection === 'library' && (
             <div className="workspace-library">
               <DocumentLibrary />
             </div>
          )}

          {activeSection === 'knowledge' && (
            <div className="workspace-knowledge">
              <div className="knowledge-tabs">
                <button className={`tab-btn ${activeKnowledgeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('search')}>Semantic Search</button>
                <button className={`tab-btn ${activeKnowledgeTab === 'memory' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('memory')}>Personal Memory</button>
                <button className={`tab-btn ${activeKnowledgeTab === 'topic' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('topic')}>Topic Explorer</button>
                <button className={`tab-btn ${activeKnowledgeTab === 'graph' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('graph')}>Concept Map</button>
                <button className={`tab-btn ${activeKnowledgeTab === 'learning' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('learning')}>Skill Coverage</button>
                <button className={`tab-btn ${activeKnowledgeTab === 'study' ? 'active' : ''}`} onClick={() => setActiveKnowledgeTab('study')}>Study Mode</button>
              </div>
              <div className="knowledge-content">
                {activeKnowledgeTab === 'search' && <SemanticSearch />}
                {activeKnowledgeTab === 'memory' && <PersonalMemoryProfile />}
                {activeKnowledgeTab === 'topic' && <TopicExplorer />}
                {activeKnowledgeTab === 'graph' && <KnowledgeGraphPanel />}
                {activeKnowledgeTab === 'learning' && <LearningPathPlanner />}
                {activeKnowledgeTab === 'study' && <StudyModePanel />}
              </div>
            </div>
          )}

          {activeSection === 'review' && (
            <div className="workspace-review">
              <CurationDashboard />
            </div>
          )}

          {activeSection === 'settings' && (
            <div className="workspace-settings">
              <div className="settings-section">
                <h3>Backend Health Status</h3>
                <div className="health-details-grid">
                  {loading ? (
                    <span>Loading...</span>
                  ) : health ? (
                    <>
                      <div className="health-card">
                        <span className={`indicator ${health.database === "ok" ? "ok" : "unavailable"}`}></span>
                        <strong>PostgreSQL:</strong> {health.database}
                      </div>
                      <div className="health-card">
                        <span className={`indicator ${health.storage === "ok" ? "ok" : "unavailable"}`}></span>
                        <strong>Storage:</strong> {health.storage || 'unknown'}
                      </div>
                      <div className="health-card">
                        <span className={`indicator ${health.chroma === "ok" ? "ok" : "unavailable"}`}></span>
                        <strong>ChromaDB:</strong> {health.chroma}
                      </div>
                      <div className="health-card">
                        <span className={`indicator ${health.groq_configured ? "ok" : "unavailable"}`}></span>
                        <strong>Groq API:</strong> {health.groq_configured ? "configured" : "missing"}
                      </div>
                      <div className="health-card">
                        <strong>Auth Dev Mode:</strong> {health.auth_dev_mode ? "Enabled" : "Disabled"}
                      </div>
                      <div className="health-card">
                        <strong>Model:</strong> {health.embedding_model || 'unknown'}
                      </div>
                    </>
                  ) : (
                    <div className="health-card">
                      <span className="indicator unavailable"></span>
                      API Offline
                    </div>
                  )}
                </div>
              </div>

              <div className="settings-section" style={{ marginTop: '2rem' }}>
                <ExportRestorePanel />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
