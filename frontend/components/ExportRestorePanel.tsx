"use client";

import React, { useState } from 'react';
import { exportKnowledgeBase, restoreKnowledgeBase, RestoreResponse } from '../lib/api';

export default function ExportRestorePanel() {
  const [exportLoading, setExportLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'dry_run' | 'merge' | 'replace'>('dry_run');
  const [result, setResult] = useState<RestoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setExportLoading(true);
    setError(null);
    try {
      const data = await exportKnowledgeBase();
      const jsonString = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `knowledge-backup-${dateStr}.json`;
      
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to export knowledge base');
    } finally {
      setExportLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setResult(null);
      setError(null);
    }
  };

  const handleRestore = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a JSON backup file to restore.');
      return;
    }

    if (mode === 'replace') {
      const confirmReplace = window.confirm(
        "WARNING: Replace mode will permanently delete ALL your current knowledge base records (documents, conversations, topic clusters, graph nodes) before restoring from the backup. Are you sure you want to proceed?"
      );
      if (!confirmReplace) return;
    }

    setRestoreLoading(true);
    setError(null);
    setResult(null);

    try {
      const fileText = await selectedFile.text();
      let bundleData: any;
      try {
        bundleData = JSON.parse(fileText);
      } catch (parseErr) {
        throw new Error("Invalid JSON file. Please provide a valid backup bundle.");
      }

      const res = await restoreKnowledgeBase(bundleData, mode);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to restore knowledge base');
    } finally {
      setRestoreLoading(false);
    }
  };

  return (
    <div className="export-restore-panel">
      <h2 className="export-restore-main-title">
        Export & Restore Knowledge Base
      </h2>
      <p className="export-restore-subtitle">
        Safely backup your metadata, documents, chunks, conversations, and learning paths to a JSON file, or restore them into your account.
      </p>

      <div className="export-restore-grid">
        {/* Export Section */}
        <div className="export-restore-section">
          <h3 className="export-restore-title">
            Export Backup
          </h3>
          <p className="export-restore-desc">
            Downloads a single JSON bundle containing your database-backed records and text chunks. Note: Raw files and Chroma embeddings are excluded.
          </p>
          <button
            onClick={handleExport}
            disabled={exportLoading}
            aria-disabled={exportLoading}
            aria-label="Download Backup JSON"
            className="btn btn-primary"
          >
            {exportLoading ? 'Exporting...' : 'Download Backup JSON'}
          </button>
        </div>

        {/* Restore Section */}
        <div className="export-restore-section">
          <h3 className="export-restore-title">
            Restore Backup
          </h3>
          <form onSubmit={handleRestore}>
            <div className="export-restore-form-group">
              <label htmlFor="backup-file-input" className="form-label">
                Select JSON Backup File
              </label>
              <input
                id="backup-file-input"
                type="file"
                accept=".json,application/json"
                onChange={handleFileChange}
                aria-describedby="file-input-desc"
                className="file-input"
              />
              <span id="file-input-desc" className="sr-only">Upload a valid knowledge base backup JSON file</span>
            </div>

            <div className="export-restore-form-group">
              <label htmlFor="restore-mode-select" className="form-label">
                Restore Mode
              </label>
              <select
                id="restore-mode-select"
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                aria-describedby={mode === 'replace' ? 'replace-mode-warning' : undefined}
                className="select-input"
              >
                <option value="dry_run">Dry Run (Validate & preview counts only)</option>
                <option value="merge">Merge (Add new records, skip duplicates, remap IDs)</option>
                <option value="replace">Replace (Delete existing records, then import)</option>
              </select>
            </div>

            {mode === 'replace' && (
              <div id="replace-mode-warning" className="warning-box" role="alert" aria-live="polite">
                <strong className="warning-title">WARNING: REPLACE MODE</strong>
                <span className="warning-text">
                  This will permanently wipe all your current restorable records before importing the backup bundle.
                </span>
              </div>
            )}

            <button
              type="submit"
              disabled={restoreLoading || !selectedFile}
              aria-disabled={restoreLoading || !selectedFile}
              aria-label={`Run Restore (${mode})`}
              className="btn btn-primary"
            >
              {restoreLoading ? 'Restoring...' : `Run Restore (${mode})`}
            </button>
          </form>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="export-restore-error" role="alert" aria-live="assertive">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Result Display */}
      {result && (
        <div className="restore-result-box" role="status" aria-live="polite">
          <h4 className="restore-result-title">
            Restore Result ({result.mode})
          </h4>
          <p className="restore-result-msg">{result.message}</p>
          <div className="restore-result-grid">
            <div><strong>Skipped:</strong> {result.skipped_records}</div>
            <div><strong>Remapped IDs:</strong> {result.remapped_ids}</div>
            <div><strong>Documents:</strong> {result.counts.documents || 0}</div>
            <div><strong>Chunks:</strong> {result.counts.chunks || 0}</div>
            <div><strong>Collections:</strong> {result.counts.collections || 0}</div>
            <div><strong>Tags:</strong> {result.counts.tags || 0}</div>
            <div><strong>Conversations:</strong> {result.counts.conversations || 0}</div>
            <div><strong>Messages:</strong> {result.counts.chat_messages || 0}</div>
            <div><strong>Learning Profiles:</strong> {result.counts.learning_profiles || 0}</div>
            <div><strong>Recommendations:</strong> {result.counts.learning_recommendations || 0}</div>
            <div><strong>Topic Clusters:</strong> {result.counts.topic_clusters || 0}</div>
            <div><strong>Graph Nodes:</strong> {result.counts.knowledge_nodes || 0}</div>
          </div>
        </div>
      )}
    </div>
  );
}
