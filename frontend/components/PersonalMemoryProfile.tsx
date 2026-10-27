"use client";

import React, { useEffect, useState } from "react";
import {
  PersonalMemoryRead,
  listPersonalMemories,
  createPersonalMemory,
  updatePersonalMemory,
  deletePersonalMemory
} from "../lib/api";

export default function PersonalMemoryProfile() {
  const [memories, setMemories] = useState<PersonalMemoryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterPrivacy, setFilterPrivacy] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Form states
  const [category, setCategory] = useState<"fact" | "project" | "skill" | "preference">("fact");
  const [content, setContent] = useState("");
  const [privacyLevel, setPrivacyLevel] = useState<"public" | "private" | "sensitive">("private");
  const [sourceCitation, setSourceCitation] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editPrivacy, setEditPrivacy] = useState<"public" | "private" | "sensitive">("private");

  const loadMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPersonalMemories();
      setMemories(data);
    } catch (err: any) {
      setError(err.message || "Failed to load personal memories");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMemories();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    setSubmitting(true);
    try {
      await createPersonalMemory({
        category,
        content: content.trim(),
        privacy_level: privacyLevel,
        source_citation: sourceCitation.trim() || undefined
      });
      setContent("");
      setSourceCitation("");
      await loadMemories();
    } catch (err: any) {
      alert(`Error creating memory: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartEdit = (m: PersonalMemoryRead) => {
    setEditingId(m.id);
    setEditContent(m.content);
    setEditPrivacy(m.privacy_level);
  };

  const handleSaveEdit = async (id: string) => {
    if (!editContent.trim()) return;
    try {
      await updatePersonalMemory(id, {
        content: editContent.trim(),
        privacy_level: editPrivacy
      });
      setEditingId(null);
      await loadMemories();
    } catch (err: any) {
      alert(`Error updating memory: ${err.message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this memory item?")) return;
    try {
      await deletePersonalMemory(id);
      setMemories(prev => prev.filter(m => m.id !== id));
    } catch (err: any) {
      alert(`Error deleting memory: ${err.message}`);
    }
  };

  const filteredMemories = memories.filter(m => {
    if (filterCategory !== "all" && m.category !== filterCategory) return false;
    if (filterPrivacy !== "all" && m.privacy_level !== filterPrivacy) return false;
    if (searchQuery.trim() && !m.content.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const getPrivacyBadgeColor = (level: string) => {
    if (level === "sensitive") return "background: #fee2e2; color: #991b1b; border: 1px solid #f87171;";
    if (level === "private") return "background: #e0e7ff; color: #3730a3; border: 1px solid #818cf8;";
    return "background: #dcfce7; color: #166534; border: 1px solid #4ade80;";
  };

  return (
    <div className="card" style={{ marginTop: "2rem", padding: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            🧠 Personal Memory & Profile Dashboard
          </h2>
          <p className="subtitle" style={{ margin: "0.25rem 0 0" }}>
            Manage structured personal facts, project roles, skills, and preferences with strict privacy enforcement.
          </p>
        </div>
        <button onClick={loadMemories} className="btn" disabled={loading}>
          {loading ? "Refreshing..." : "🔄 Refresh"}
        </button>
      </div>

      <div style={{ background: "#f8fafc", padding: "1rem", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "1.5rem" }}>
        <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", color: "#334155" }}>🔒 Privacy Semantics Guarantees:</h4>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", fontSize: "0.85rem" }}>
          <div>
            <strong style={{ color: "#991b1b" }}>⚠️ Sensitive:</strong> Viewable ONLY in this profile dashboard. Never indexed in vector embeddings and strictly excluded from RAG / Chat injection.
          </div>
          <div>
            <strong style={{ color: "#3730a3" }}>🔒 Private:</strong> Indexed and injected only into your own authenticated RAG and chat sessions (`user_id` matching).
          </div>
          <div>
            <strong style={{ color: "#166534" }}>🌐 Public:</strong> Shared knowledge accessible across user sessions and surfaced via standard RAG citations.
          </div>
        </div>
      </div>

      <form onSubmit={handleCreate} style={{ display: "grid", gap: "1rem", background: "#ffffff", padding: "1.25rem", borderRadius: "8px", border: "1px solid #cbd5e1", marginBottom: "1.5rem" }}>
        <h3 style={{ margin: 0, fontSize: "1.1rem" }}>➕ Add New Memory Record</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>Category</label>
            <select
              value={category}
              onChange={e => setCategory(e.target.value as any)}
              className="input"
              style={{ width: "100%", padding: "0.5rem" }}
            >
              <option value="fact">📌 Fact / Background</option>
              <option value="project">🚀 Project Context</option>
              <option value="skill">🛠️ Technical Skill</option>
              <option value="preference">⚙️ Assistant Preference</option>
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>Privacy Level</label>
            <select
              value={privacyLevel}
              onChange={e => setPrivacyLevel(e.target.value as any)}
              className="input"
              style={{ width: "100%", padding: "0.5rem" }}
            >
              <option value="private">🔒 Private (User-Only)</option>
              <option value="public">🌐 Public (Cross-User Shared)</option>
              <option value="sensitive">⚠️ Sensitive (Never Injected/Indexed)</option>
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>Source / Reference (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Resume, Onboarding doc"
              value={sourceCitation}
              onChange={e => setSourceCitation(e.target.value)}
              className="input"
              style={{ width: "100%", padding: "0.5rem" }}
            />
          </div>
        </div>
        <div>
          <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>Memory Content</label>
          <textarea
            placeholder="Enter personal context, preference, or domain knowledge item..."
            value={content}
            onChange={e => setContent(e.target.value)}
            className="input"
            rows={2}
            style={{ width: "100%", padding: "0.5rem", fontFamily: "inherit" }}
            required
          />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Saving..." : "Save Memory Item"}
          </button>
        </div>
      </form>

      {/* Filter Bar */}
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center", marginBottom: "1rem" }}>
        <input
          type="text"
          placeholder="🔍 Search stored memories..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="input"
          style={{ flex: "1", minWidth: "200px", padding: "0.4rem 0.75rem" }}
        />
        <select
          value={filterCategory}
          onChange={e => setFilterCategory(e.target.value)}
          className="input"
          style={{ padding: "0.4rem 0.75rem" }}
        >
          <option value="all">All Categories</option>
          <option value="fact">📌 Fact</option>
          <option value="project">🚀 Project</option>
          <option value="skill">🛠️ Skill</option>
          <option value="preference">⚙️ Preference</option>
        </select>
        <select
          value={filterPrivacy}
          onChange={e => setFilterPrivacy(e.target.value)}
          className="input"
          style={{ padding: "0.4rem 0.75rem" }}
        >
          <option value="all">All Privacy Levels</option>
          <option value="private">🔒 Private</option>
          <option value="public">🌐 Public</option>
          <option value="sensitive">⚠️ Sensitive</option>
        </select>
      </div>

      {error && <div style={{ color: "#dc2626", marginBottom: "1rem" }}>❌ {error}</div>}

      {loading ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>Loading profile memories...</div>
      ) : filteredMemories.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", background: "#f8fafc", borderRadius: "8px", border: "1px dashed #cbd5e1", color: "#64748b" }}>
          No personal memory items found matching your criteria.
        </div>
      ) : (
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {filteredMemories.map(m => (
            <div
              key={m.id}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
                padding: "1rem",
                borderRadius: "8px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", padding: "0.15rem 0.5rem", borderRadius: "4px", background: "#f1f5f9", color: "#475569" }}>
                    {m.category}
                  </span>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      padding: "0.15rem 0.5rem",
                      borderRadius: "4px",
                      ...(m.privacy_level === "sensitive"
                        ? { background: "#fee2e2", color: "#991b1b", border: "1px solid #f87171" }
                        : m.privacy_level === "private"
                        ? { background: "#e0e7ff", color: "#3730a3", border: "1px solid #818cf8" }
                        : { background: "#dcfce7", color: "#166534", border: "1px solid #4ade80" })
                    }}
                  >
                    {m.privacy_level === "sensitive" ? "⚠️ Sensitive (No RAG)" : m.privacy_level === "private" ? "🔒 Private" : "🌐 Public"}
                  </span>
                  {m.source_citation && (
                    <span style={{ fontSize: "0.8rem", color: "#64748b" }}>📎 {m.source_citation}</span>
                  )}
                  {m.is_consolidated && (
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "0.15rem 0.5rem", borderRadius: "4px", background: "#fef3c7", color: "#92400e", border: "1px solid #f59e0b" }}>
                      🧹 Consolidated
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {editingId !== m.id ? (
                    <>
                      <button onClick={() => handleStartEdit(m)} className="btn btn-sm" style={{ padding: "0.2rem 0.5rem" }}>
                        ✏️ Edit
                      </button>
                      <button onClick={() => handleDelete(m.id)} className="btn btn-sm" style={{ padding: "0.2rem 0.5rem", color: "#dc2626" }}>
                        🗑️ Delete
                      </button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => handleSaveEdit(m.id)} className="btn btn-sm btn-primary" style={{ padding: "0.2rem 0.5rem" }}>
                        💾 Save
                      </button>
                      <button onClick={() => setEditingId(null)} className="btn btn-sm" style={{ padding: "0.2rem 0.5rem" }}>
                        ❌ Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>

              {editingId === m.id ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <textarea
                    value={editContent}
                    onChange={e => setEditContent(e.target.value)}
                    className="input"
                    rows={2}
                    style={{ width: "100%", fontFamily: "inherit" }}
                  />
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Privacy:</label>
                    <select
                      value={editPrivacy}
                      onChange={e => setEditPrivacy(e.target.value as any)}
                      className="input"
                      style={{ padding: "0.25rem 0.5rem" }}
                    >
                      <option value="private">🔒 Private</option>
                      <option value="public">🌐 Public</option>
                      <option value="sensitive">⚠️ Sensitive</option>
                    </select>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.95rem", color: "#1e293b", lineHeight: "1.5" }}>
                  {m.content}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
