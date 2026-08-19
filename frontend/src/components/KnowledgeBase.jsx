import React, { useEffect, useState } from 'react';
import { Database, FileText, Trash2, RefreshCw } from 'lucide-react';
import { fetchHealth, fetchDocuments, deleteDocument } from '../services/api';

export default function KnowledgeBase({ refreshTrigger, onDocDeleted }) {
  const [chunkCount, setChunkCount] = useState(0);
  const [documents, setDocuments] = useState([]);
  const [deletingFile, setDeletingFile] = useState(null);

  const loadData = async () => {
    try {
      const [health, docs] = await Promise.all([
        fetchHealth().catch(() => ({ vector_store_chunks: 0 })),
        fetchDocuments().catch(() => []),
      ]);
      setChunkCount(health.vector_store_chunks || 0);
      setDocuments(docs || []);
    } catch (error) {
      console.error("Failed to load KnowledgeBase data", error);
    }
  };

  useEffect(() => {
    loadData();
  }, [refreshTrigger]);

  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to remove "${filename}" from ChromaDB?`)) {
      return;
    }
    setDeletingFile(filename);
    try {
      await deleteDocument(filename);
      await loadData();
      if (onDocDeleted) onDocDeleted();
    } catch (error) {
      alert(`Error deleting document: ${error.message}`);
    } finally {
      setDeletingFile(null);
    }
  };

  return (
    <div className="knowledge-base-widget">
      <div className="widget-header">
        <Database size={16} color="var(--accent-teal)" />
        <h4>Active Context ({chunkCount} chunks)</h4>
        <div style={{ flex: 1 }} />
        <button 
          className="icon-btn-subtle" 
          onClick={loadData} 
          title="Refresh Knowledge Base"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      <div className="doc-list">
        {documents.length === 0 ? (
          <div className="empty-docs">No documents ingested yet.</div>
        ) : (
          documents.map((doc, idx) => (
            <div key={idx} className="doc-item">
              <FileText size={14} color="var(--accent-blue)" />
              <div className="doc-info" title={doc.filename}>
                <span className="doc-name">{doc.filename}</span>
                <span className="doc-chunks">{doc.chunks} chunks</span>
              </div>
              <button 
                className="delete-doc-btn" 
                onClick={() => handleDelete(doc.filename)}
                disabled={deletingFile === doc.filename}
                title="Remove from vector store"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
