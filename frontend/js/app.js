import { fetchHealth, validateUrl, runAudit, listAuditHistory, getAuditById } from './api.js';

let currentAuditData = null;

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  loadProviderBadge();
}

async function loadProviderBadge() {
  try {
    const health = await fetchHealth();
    const badge = document.getElementById('providerBadge');
    if (badge && health.llm_provider) {
      badge.textContent = `Provider: ${health.llm_provider.toUpperCase()}`;
    }
  } catch (err) {
    console.warn('Could not load provider info:', err);
  }
}

function setupEventListeners() {
  const form = document.getElementById('auditForm');
  const historyBtn = document.getElementById('historyBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const exportBtn = document.getElementById('exportJsonBtn');

  form.addEventListener('submit', handleAuditSubmit);
  historyBtn.addEventListener('click', openHistoryDrawer);
  closeDrawerBtn.addEventListener('click', closeHistoryDrawer);
  drawerOverlay.addEventListener('click', closeHistoryDrawer);

  if (exportBtn) {
    exportBtn.addEventListener('click', exportAuditJson);
  }

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const targetTab = e.target.dataset.tab;
      document.getElementById('tabAeo').style.display = targetTab === 'aeo' ? 'block' : 'none';
      document.getElementById('tabTechnical').style.display = targetTab === 'technical' ? 'block' : 'none';
    });
  });
}

async function handleAuditSubmit(e) {
  e.preventDefault();
  const input = document.getElementById('urlInput');
  const feedback = document.getElementById('formFeedback');
  const loader = document.getElementById('loaderCard');
  const resultsSec = document.getElementById('resultsSection');

  const rawUrl = input.value.trim();
  feedback.textContent = '';
  if (!rawUrl) {
    feedback.textContent = 'Please enter a valid website URL.';
    return;
  }

  // Step 1: Pre-flight URL validation
  try {
    await validateUrl(rawUrl);
  } catch (err) {
    feedback.textContent = `Security Check Failed: ${err.message}`;
    return;
  }

  // Show loader
  loader.style.display = 'block';
  resultsSec.style.display = 'none';

  try {
    const data = await runAudit(rawUrl);
    currentAuditData = data;
    renderResults(data);
  } catch (err) {
    feedback.textContent = `Audit Error: ${err.message}`;
  } finally {
    loader.style.display = 'none';
  }
}

function renderResults(data) {
  const resultsSec = document.getElementById('resultsSection');
  resultsSec.style.display = 'block';

  // Scores
  document.getElementById('techScore').textContent = data.score;
  
  const entityScore = data.aeo_summary ? data.aeo_summary.entity_clarity_score : '--';
  const answerScore = data.aeo_summary ? data.aeo_summary.answer_readiness_score : '--';
  
  document.getElementById('entityScore').textContent = entityScore;
  document.getElementById('answerScore').textContent = answerScore;

  // Header Info
  document.getElementById('auditedUrlDisplay').textContent = data.url;
  document.getElementById('fetchTimeDisplay').textContent = `${data.fetch_time_seconds.toFixed(2)}s`;

  // Render AEO Recommendations Tab
  renderAeoTab(data.aeo_summary);

  // Render Technical Findings Tab
  renderTechnicalTab(data.findings);

  // Smooth scroll
  resultsSec.scrollIntoView({ behavior: 'smooth' });
}

function renderAeoTab(aeo) {
  const container = document.getElementById('tabAeo');
  if (!aeo) {
    container.innerHTML = '<p class="text-muted">No AEO recommendations generated.</p>';
    return;
  }

  let html = `<div class="finding-card">
    <h3>Executive AEO Summary</h3>
    <p style="margin-top:0.5rem;">${aeo.summary}</p>
  </div>`;

  if (aeo.key_recommendations && aeo.key_recommendations.length > 0) {
    html += '<h3 style="margin-top:1.5rem; margin-bottom:1rem;">Prioritized Grounded Fixes</h3>';
    aeo.key_recommendations.forEach(rec => {
      html += `
      <div class="finding-card">
        <div class="finding-header">
          <span class="finding-title">${rec.title}</span>
          <span class="badge-severity severity-info">Confidence ${(rec.confidence_score * 100).toFixed(0)}%</span>
        </div>
        <p><strong>Category:</strong> ${rec.category}</p>
        <div class="finding-evidence"><strong>Current State Evidence:</strong> ${rec.current_state_evidence}</div>
        <p><strong>Suggested Action:</strong> ${rec.suggested_aeo_content}</p>
        ${rec.suggested_schema_code ? `<pre class="code-block"><code>${escapeHtml(rec.suggested_schema_code)}</code></pre>` : ''}
        <p style="margin-top:0.5rem; font-size:0.85rem;" class="text-muted"><strong>Limitations:</strong> ${rec.limitations}</p>
      </div>`;
    });
  }

  if (aeo.faq_opportunities && aeo.faq_opportunities.length > 0) {
    html += '<h3 style="margin-top:1.5rem; margin-bottom:1rem;">Extracted Q&A Opportunities for FAQ Schema</h3>';
    aeo.faq_opportunities.forEach(faq => {
      html += `
      <div class="finding-card" style="border-left: 3px solid var(--teal-primary);">
        <p style="font-weight:700; color:var(--teal-primary);">Q: ${faq.question}</p>
        <p style="margin-top:0.3rem;">A: ${faq.answer}</p>
      </div>`;
    });
  }

  container.innerHTML = html;
}

function renderTechnicalTab(findings) {
  const container = document.getElementById('tabTechnical');
  if (!findings || findings.length === 0) {
    container.innerHTML = '<p class="text-muted">No technical issues detected! Page passed all deterministic checks.</p>';
    return;
  }

  let html = '';
  findings.forEach(f => {
    const sevClass = `severity-${f.severity}`;
    html += `
    <div class="finding-card">
      <div class="finding-header">
        <span class="finding-title">[${f.check_id}] ${f.title}</span>
        <span class="badge-severity ${sevClass}">${f.severity}</span>
      </div>
      <p>${f.description}</p>
      <div class="finding-evidence"><strong>Evidence:</strong> ${f.evidence}</div>
      <p style="color:var(--teal-primary);"><strong>Suggested Fix:</strong> ${f.suggested_fix}</p>
    </div>`;
  });

  container.innerHTML = html;
}

async function openHistoryDrawer() {
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawerOverlay');
  const listContainer = document.getElementById('historyList');

  drawer.classList.add('open');
  overlay.style.display = 'block';

  try {
    listContainer.innerHTML = '<p class="text-muted">Loading past audits...</p>';
    const data = await listAuditHistory();
    if (!data.items || data.items.length === 0) {
      listContainer.innerHTML = '<p class="text-muted">No past audits found.</p>';
      return;
    }

    let html = '';
    data.items.forEach(item => {
      html += `
      <div class="history-item" data-id="${item.id}">
        <p style="font-weight:700; font-size:0.95rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${item.url}</p>
        <div style="display:flex; justify-content:space-between; margin-top:0.4rem; font-size:0.8rem;" class="text-muted">
          <span>Score: <strong style="color:var(--teal-primary);">${item.score}</strong></span>
          <span>${new Date(item.created_at).toLocaleDateString()}</span>
        </div>
      </div>`;
    });
    listContainer.innerHTML = html;

    listContainer.querySelectorAll('.history-item').forEach(el => {
      el.addEventListener('click', async () => {
        const id = el.dataset.id;
        const fullAudit = await getAuditById(id);
        currentAuditData = fullAudit;
        renderResults(fullAudit);
        closeHistoryDrawer();
      });
    });
  } catch (err) {
    listContainer.innerHTML = `<p style="color:var(--danger);">Error loading history: ${err.message}</p>`;
  }
}

function closeHistoryDrawer() {
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('drawerOverlay').style.display = 'none';
}

function exportAuditJson() {
  if (!currentAuditData) return;
  const jsonStr = JSON.stringify(currentAuditData, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `zenvora-audit-${currentAuditData.id.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
