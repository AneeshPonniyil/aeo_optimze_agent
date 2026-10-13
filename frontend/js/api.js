/**
 * Zenvora AI REST API Client Library
 */
const API_BASE = '/api/v1';

export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error('Health check failed');
  return await response.json();
}

export async function validateUrl(url) {
  const response = await fetch(`${API_BASE}/validate-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'URL validation failed');
  }
  return data;
}

export async function runAudit(url) {
  const response = await fetch(`${API_BASE}/audits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Audit execution failed');
  }
  return data;
}

export async function getAuditById(id) {
  const response = await fetch(`${API_BASE}/audits/${id}`);
  if (!response.ok) throw new Error('Failed to fetch audit details');
  return await response.json();
}

export async function listAuditHistory() {
  const response = await fetch(`${API_BASE}/audits?limit=50`);
  if (!response.ok) throw new Error('Failed to fetch history');
  return await response.json();
}

export async function deleteAudit(id) {
  const response = await fetch(`${API_BASE}/audits/${id}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete audit');
  return true;
}
