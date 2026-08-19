import React, { useRef, useState } from 'react';
import { UploadCloud, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { uploadDocument } from '../services/api';

export default function Uploader({ onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // { type: 'success' | 'error', message: string }

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      setUploadStatus({ type: 'error', message: 'Please upload a valid PDF document.' });
      return;
    }

    setIsUploading(true);
    setUploadStatus(null);

    try {
      const result = await uploadDocument(file);
      setUploadStatus({ 
        type: 'success', 
        message: `Success! Added ${result.chunks_added} chunks. (Total: ${result.total_chunks})` 
      });
      if (onUploadSuccess) onUploadSuccess(result.total_chunks);
    } catch (error) {
      setUploadStatus({ type: 'error', message: error.message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = ''; // Reset input
      }
    }
  };

  return (
    <div className="uploader-container">
      <div 
        className={`upload-dropzone ${isUploading ? 'uploading' : ''}`}
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept="application/pdf"
          style={{ display: 'none' }}
        />
        
        {isUploading ? (
          <div className="upload-state">
            <Loader className="spin-icon" size={24} color="var(--accent-blue)" />
            <span>Ingesting document...</span>
          </div>
        ) : (
          <div className="upload-state">
            <UploadCloud size={24} color="var(--text-muted)" />
            <span>Upload new PDF</span>
          </div>
        )}
      </div>

      {uploadStatus && (
        <div className={`upload-feedback ${uploadStatus.type}`}>
          {uploadStatus.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          <span>{uploadStatus.message}</span>
        </div>
      )}
    </div>
  );
}
