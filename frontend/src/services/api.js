const API_BASE = import.meta.env.VITE_API_URL || "";

/**
 * Sends a query to the Polymath FastAPI backend.
 * @param {string} question - The user's input question
 * @returns {Promise<Object>} The JSON response from the backend
 */
export async function fetchPolymathResponse(question) {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  
  const headers = {
    "Content-Type": "application/json",
  };
  
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const response = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error: ${response.status}`);
  }

  return response.json();
}

/**
 * Uploads a PDF to the Polymath FastAPI backend for dynamic ingestion.
 * @param {File} file - The PDF file to upload
 * @returns {Promise<Object>} The JSON response with upload status and chunk count
 */
export async function uploadDocument(file) {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  
  const headers = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetches the health status and current vector store chunk count.
 */
export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error("Unable to fetch system health");
  }
  return response.json();
}

/**
 * Fetches the list of unique ingested documents.
 */
export async function fetchDocuments() {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  const headers = {};
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(`${API_BASE}/documents`, { headers });
  if (!response.ok) throw new Error("Failed to fetch documents");
  return response.json();
}

/**
 * Deletes a document from the vector store by filename.
 */
export async function deleteDocument(filename) {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  const headers = {};
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) throw new Error("Failed to delete document");
  return response.json();
}

/**
 * Generates an interactive practice quiz for a domain.
 */
export async function generateQuiz(domain = "general_cs") {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(`${API_BASE}/quiz`, {
    method: "POST",
    headers,
    body: JSON.stringify({ domain }),
  });
  if (!response.ok) throw new Error("Failed to generate quiz");
  return response.json();
}

/**
 * Generates interactive study flashcards for a domain.
 */
export async function generateFlashcards(domain = "general_cs") {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(`${API_BASE}/flashcards`, {
    method: "POST",
    headers,
    body: JSON.stringify({ domain }),
  });
  if (!response.ok) throw new Error("Failed to generate flashcards");
  return response.json();
}
