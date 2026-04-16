/* ── app.js — Professional Profile Agent frontend ─────────────────────────── */

'use strict';

// ── Tab switching ─────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    document.getElementById(`tab-${tab}`).classList.add('active');
  });
});


// ── Generic: radio-driven source panel switching ──────────────────────────────

function wireSourceToggle(radioName, panelMap) {
  document.querySelectorAll(`input[name="${radioName}"]`).forEach(radio => {
    radio.addEventListener('change', () => {
      Object.entries(panelMap).forEach(([value, panelId]) => {
        const el = document.getElementById(panelId);
        if (el) el.classList.toggle('hidden', value !== radio.value);
      });
    });
  });
}

wireSourceToggle('jd-source-a', {
  url: 'jd-url-input-a', file: 'jd-file-input-a', text: 'jd-text-input-a',
});
wireSourceToggle('jd-source-c', {
  url: 'jd-url-input-c', file: 'jd-file-input-c', text: 'jd-text-input-c',
});
wireSourceToggle('cv-source', {
  file: 'cv-file-panel', text: 'cv-text-panel',
});
wireSourceToggle('li-source', {
  file: 'li-file-panel', text: 'li-text-panel', none: 'li-none-panel',
});


// ── Generic: drop zone wiring ─────────────────────────────────────────────────

function wireDropZone(dropId, fileInputId, fileNameId) {
  const zone = document.getElementById(dropId);
  const input = document.getElementById(fileInputId);
  const nameEl = fileNameId ? document.getElementById(fileNameId) : null;
  if (!zone || !input) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      if (nameEl) nameEl.textContent = [...e.dataTransfer.files].map(f => f.name).join(', ');
    }
  });
  input.addEventListener('change', () => {
    if (nameEl && input.files.length) {
      nameEl.textContent = [...input.files].map(f => f.name).join(', ');
    }
  });
}

wireDropZone('jd-drop-a', 'jd-file-a', 'jd-file-name-a');
wireDropZone('jd-drop-c', 'jd-file-c', 'jd-file-name-c');
wireDropZone('cv-drop', 'cv-file', 'cv-file-name');
wireDropZone('li-drop', 'li-file', 'li-file-name');


// ── Multi-file candidate upload ───────────────────────────────────────────────

const candidatesInput = document.getElementById('candidates-file');
const candidatesDrop = document.getElementById('candidates-drop');
const candidatesList = document.getElementById('candidates-list');
let candidateFiles = [];

function renderCandidateList() {
  candidatesList.innerHTML = '';
  candidateFiles.forEach((file, i) => {
    const li = document.createElement('li');
    li.innerHTML = `📄 ${esc(file.name)}
      <button class="remove-file" title="Remove" data-index="${i}">✕</button>`;
    candidatesList.appendChild(li);
  });
}

function addCandidateFiles(files) {
  [...files].forEach(f => {
    if (!candidateFiles.find(x => x.name === f.name)) candidateFiles.push(f);
  });
  renderCandidateList();
}

candidatesInput.addEventListener('change', () => {
  addCandidateFiles(candidatesInput.files);
  candidatesInput.value = '';
});
candidatesDrop.addEventListener('dragover', e => { e.preventDefault(); candidatesDrop.classList.add('drag-over'); });
candidatesDrop.addEventListener('dragleave', () => candidatesDrop.classList.remove('drag-over'));
candidatesDrop.addEventListener('drop', e => {
  e.preventDefault();
  candidatesDrop.classList.remove('drag-over');
  addCandidateFiles(e.dataTransfer.files);
});
candidatesList.addEventListener('click', e => {
  const btn = e.target.closest('.remove-file');
  if (!btn) return;
  candidateFiles.splice(Number(btn.dataset.index), 1);
  renderCandidateList();
});


// ── Loading state helpers ─────────────────────────────────────────────────────

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.querySelector('.btn-text').classList.toggle('hidden', loading);
  btn.querySelector('.btn-spinner').classList.toggle('hidden', !loading);
}

function showError(elId, msg) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideError(elId) {
  const el = document.getElementById(elId);
  if (el) el.classList.add('hidden');
}


// ── Assessor form submission ──────────────────────────────────────────────────

document.getElementById('assessor-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideError('assessor-error');

  const jdSource = document.querySelector('input[name="jd-source-a"]:checked')?.value;

  if (!candidateFiles.length) {
    showError('assessor-error', 'Please upload at least one candidate PDF.');
    return;
  }

  const fd = new FormData();

  if (jdSource === 'url') {
    const url = document.querySelector('#jd-url-input-a input').value.trim();
    if (!url) { showError('assessor-error', 'Please enter a job description URL.'); return; }
    fd.append('jd_url', url);
  } else if (jdSource === 'file') {
    const file = document.getElementById('jd-file-a').files[0];
    if (!file) { showError('assessor-error', 'Please upload a job description file.'); return; }
    fd.append('jd_file', file);
  } else {
    const text = document.querySelector('#jd-text-input-a textarea').value.trim();
    if (!text) { showError('assessor-error', 'Please paste the job description text.'); return; }
    fd.append('jd_text', text);
  }

  candidateFiles.forEach(f => fd.append('candidates', f));

  setLoading('assess-btn', true);
  try {
    const resp = await fetch('/api/assess', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || `Server error ${resp.status}`);
    renderAssessorResults(data.results);
  } catch (err) {
    showError('assessor-error', `Error: ${err.message}`);
  } finally {
    setLoading('assess-btn', false);
  }
});


// ── Curator form submission ───────────────────────────────────────────────────

document.getElementById('curator-form').addEventListener('submit', async e => {
  e.preventDefault();
  hideError('curator-error');

  const jdSource = document.querySelector('input[name="jd-source-c"]:checked')?.value;
  const cvSource = document.querySelector('input[name="cv-source"]:checked')?.value;
  const liSource = document.querySelector('input[name="li-source"]:checked')?.value;

  const fd = new FormData();

  // JD
  if (jdSource === 'url') {
    const url = document.querySelector('#jd-url-input-c input').value.trim();
    if (!url) { showError('curator-error', 'Please enter a job description URL.'); return; }
    fd.append('jd_url', url);
  } else if (jdSource === 'file') {
    const file = document.getElementById('jd-file-c').files[0];
    if (!file) { showError('curator-error', 'Please upload a job description file.'); return; }
    fd.append('jd_file', file);
  } else {
    const text = document.querySelector('#jd-text-input-c textarea').value.trim();
    if (!text) { showError('curator-error', 'Please paste the job description text.'); return; }
    fd.append('jd_text', text);
  }

  // CV
  if (cvSource === 'file') {
    const file = document.getElementById('cv-file').files[0];
    if (!file) { showError('curator-error', 'Please upload your CV file.'); return; }
    fd.append('cv_file', file);
  } else {
    const text = document.querySelector('#cv-text-panel textarea').value.trim();
    if (!text) { showError('curator-error', 'Please paste your CV text.'); return; }
    fd.append('cv_text', text);
  }

  // LinkedIn (optional)
  if (liSource === 'file') {
    const file = document.getElementById('li-file').files[0];
    if (file) fd.append('linkedin_file', file);
  } else if (liSource === 'text') {
    const text = document.querySelector('#li-text-panel textarea').value.trim();
    if (text) fd.append('linkedin_text', text);
  }

  // Notes
  const notes = document.querySelector('#curator-form textarea[name="user_notes"]').value.trim();
  if (notes) fd.append('user_notes', notes);

  setLoading('curate-btn', true);
  try {
    const resp = await fetch('/api/curate', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || `Server error ${resp.status}`);
    renderCuratorResults(data);
  } catch (err) {
    showError('curator-error', `Error: ${err.message}`);
  } finally {
    setLoading('curate-btn', false);
  }
});


// ── Render: Assessor results ──────────────────────────────────────────────────

function renderAssessorResults(results) {
  const container = document.getElementById('assessor-results');

  const badgeClass = {
    strong_yes: 'badge-strong-yes',
    yes: 'badge-yes',
    maybe: 'badge-maybe',
    no: 'badge-no',
  };
  const badgeLabel = {
    strong_yes: 'Strong Yes ✓',
    yes: 'Yes ✓',
    maybe: 'Maybe',
    no: 'No ✗',
  };

  const html = results.map(({ candidate_name, record_id, assessment: a }) => {
    const rec = a.recommendation || 'maybe';
    const pillars = a.pillars || {};

    const pillarRows = ['cultural', 'operational', 'capability'].map(key => {
      const p = pillars[key] || {};
      const score = p.score ?? 0;
      return `
        <div class="pillar-row">
          <div class="pillar-name">${capitalize(key)} Fit</div>
          <div class="score-bar"><div class="score-bar-fill" style="width:${score}%"></div></div>
          <div class="pillar-score">${score}</div>
        </div>`;
    }).join('');

    const evidenceHtml = ['cultural', 'operational', 'capability'].map(key => {
      const p = pillars[key] || {};
      const quotes = p.evidence || [];
      if (!quotes.length) return '';
      return `<div class="evidence-block">
        <div class="evidence-label">${capitalize(key)} — Evidence</div>
        ${quotes.slice(0, 2).map(q => `<div class="evidence-quote">"${esc(q.quote || q)}"</div>`).join('')}
      </div>`;
    }).join('');

    const strengthsList = (a.strengths || []).map(s => `<li>${esc(s)}</li>`).join('');
    const risksList = (a.risks || []).map(r => `<li>${esc(r)}</li>`).join('');
    const questionsList = (a.recommended_interview_questions || []).map(q => `<li>${esc(q)}</li>`).join('');
    const gapsList = (a.evidence_gaps || []).map(g => `<li>${esc(g)}</li>`).join('');

    const summaryId = `summary-${record_id}`;
    const detailId = `detail-${record_id}`;

    return `
    <div class="card candidate-card">
      <div class="candidate-header">
        <div class="candidate-name">👤 ${esc(candidate_name)}</div>
        <span class="recommendation-badge ${badgeClass[rec] || 'badge-maybe'}">${badgeLabel[rec] || rec}</span>
      </div>

      <div class="score-grid">
        <div class="score-tile">
          <div class="score-label">Overall Fit</div>
          <div class="score-value">${a.overall_fit_score ?? '—'}</div>
          <div class="score-sub">/ 100</div>
          <div class="score-bar"><div class="score-bar-fill" style="width:${a.overall_fit_score ?? 0}%"></div></div>
        </div>
        <div class="score-tile">
          <div class="score-label">Confidence</div>
          <div class="score-value">${a.overall_confidence ?? '—'}</div>
          <div class="score-sub">/ 100</div>
          <div class="score-bar"><div class="score-bar-fill" style="width:${a.overall_confidence ?? 0}%; background:#9ca3af"></div></div>
        </div>
      </div>

      <div class="pillars">${pillarRows}</div>

      <p style="font-size:0.85rem;color:#374151;margin-bottom:1rem">${esc(a.candidate_summary || '')}</p>

      <div class="accordion">
        <button class="accordion-btn" aria-expanded="false" onclick="toggleAccordion(this)">
          📋 Evidence &amp; Pillar Details <span class="chevron">▶</span>
        </button>
        <div class="accordion-body">${evidenceHtml}</div>
      </div>

      <div class="accordion">
        <button class="accordion-btn" aria-expanded="false" onclick="toggleAccordion(this)">
          💪 Strengths &amp; Risks <span class="chevron">▶</span>
        </button>
        <div class="accordion-body">
          ${strengthsList ? `<div class="detail-section"><h4>Strengths</h4><ul class="detail-list">${strengthsList}</ul></div>` : ''}
          ${risksList ? `<div class="detail-section"><h4>Risks</h4><ul class="detail-list">${risksList}</ul></div>` : ''}
          ${gapsList ? `<div class="detail-section"><h4>Evidence Gaps</h4><ul class="detail-list">${gapsList}</ul></div>` : ''}
        </div>
      </div>

      <div class="accordion">
        <button class="accordion-btn" aria-expanded="false" onclick="toggleAccordion(this)">
          ❓ Interview Questions <span class="chevron">▶</span>
        </button>
        <div class="accordion-body">
          <ul class="detail-list">${questionsList}</ul>
        </div>
      </div>

      <div class="feedback-bar" id="fb-${record_id}">
        <span>Was this assessment helpful?</span>
        <button onclick="sendFeedback('assessment', ${record_id}, true, this)" title="Thumbs up">👍</button>
        <button onclick="sendFeedback('assessment', ${record_id}, false, this)" title="Thumbs down">👎</button>
      </div>
    </div>`;
  }).join('');

  container.innerHTML = `<div class="results-header">Assessment Results — ${results.length} candidate${results.length !== 1 ? 's' : ''}</div>${html}`;
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


// ── Base64 → Blob URL helper for PDF downloads ────────────────────────────────

function b64ToBlobUrl(b64, mimeType) {
  const bytes = atob(b64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return URL.createObjectURL(new Blob([arr], { type: mimeType }));
}

// ── Render: Curator results ───────────────────────────────────────────────────

function renderCuratorResults({ record_id, curation: c, cv_pdf_b64, cl_pdf_b64 }) {
  const container = document.getElementById('curator-results');

  const jd = c.jd_extraction || {};
  const gap = c.gap_analysis || {};
  const cv = c.tailored_cv || {};
  const rationale = c.rationale_log || [];

  // Gap analysis
  const strongItems = (gap.strong_matches || []).map(x => `<li>${esc(x.requirement || x)}</li>`).join('');
  const partialItems = (gap.partial_matches || []).map(x => `<li>${esc(x.requirement || x)}</li>`).join('');
  const missingItems = (gap.missing || []).map(x => `<li>${esc(x.requirement || x)}</li>`).join('');

  // Tailored CV
  const cvHtml = buildCVPreview(cv);

  // Cover letter
  const clText = c.cover_letter || '';

  // Rationale log
  const rationaleHtml = rationale.map(r =>
    `<div class="evidence-quote">
      <strong>${esc(r.change || '')}</strong><br>
      <em>Evidence: ${esc(r.source_evidence || '')}</em>
    </div>`
  ).join('');

  const html = `
  <div class="results-header">
    Curation Results — ${esc(jd.role_title || 'Role')}${jd.company ? ` · ${esc(jd.company)}` : ''}
  </div>

  <div class="card">
    <div class="detail-section">
      <h4>Gap Analysis</h4>
      <div class="gap-grid">
        <div class="gap-tile gap-strong">
          <div class="gap-tile-label">✓ Strong Matches</div>
          <ul class="gap-list">${strongItems || '<li>—</li>'}</ul>
        </div>
        <div class="gap-tile gap-partial">
          <div class="gap-tile-label">△ Partial Matches</div>
          <ul class="gap-list">${partialItems || '<li>—</li>'}</ul>
        </div>
        <div class="gap-tile gap-missing">
          <div class="gap-tile-label">✗ Gaps</div>
          <ul class="gap-list">${missingItems || '<li>None identified</li>'}</ul>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="candidate-header">
      <div class="candidate-name">📄 Tailored CV</div>
    </div>
    <div class="cv-preview">${cvHtml}</div>
    <div class="download-bar">
      ${cv_pdf_b64
        ? `<a href="${b64ToBlobUrl(cv_pdf_b64, 'application/pdf')}" download="CV_tailored.pdf" class="btn btn-secondary btn-sm">⬇ Download CV (PDF)</a>`
        : `<a href="/api/cv-pdf/${record_id}" download class="btn btn-secondary btn-sm">⬇ Download CV (PDF)</a>`}
    </div>
  </div>

  <div class="card">
    <div class="candidate-header">
      <div class="candidate-name">✉️ Cover Letter</div>
    </div>
    <div class="cover-letter-text">${esc(clText)}</div>
    <div class="download-bar">
      ${cl_pdf_b64
        ? `<a href="${b64ToBlobUrl(cl_pdf_b64, 'application/pdf')}" download="Cover_Letter.pdf" class="btn btn-secondary btn-sm">⬇ Download Cover Letter (PDF)</a>`
        : `<a href="/api/cl-pdf/${record_id}" download class="btn btn-secondary btn-sm">⬇ Download Cover Letter (PDF)</a>`}
    </div>
  </div>

  ${rationaleHtml ? `
  <div class="card">
    <div class="accordion">
      <button class="accordion-btn" aria-expanded="false" onclick="toggleAccordion(this)">
        📝 Rationale Log — what changed and why <span class="chevron">▶</span>
      </button>
      <div class="accordion-body">${rationaleHtml}</div>
    </div>
  </div>` : ''}

  <div class="card">
    <div class="feedback-bar" id="fb-${record_id}">
      <span>Was this curation useful?</span>
      <button onclick="sendFeedback('curation', ${record_id}, true, this)" title="Thumbs up">👍</button>
      <button onclick="sendFeedback('curation', ${record_id}, false, this)" title="Thumbs down">👎</button>
    </div>
  </div>`;

  container.innerHTML = html;
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


// ── CV preview builder ────────────────────────────────────────────────────────

function buildCVPreview(cv) {
  let html = '';

  if (cv.summary) {
    html += `<h4>Profile</h4><p>${esc(cv.summary)}</p>`;
  }

  if ((cv.experience || []).length) {
    html += '<h4>Experience</h4>';
    cv.experience.forEach(role => {
      html += `
        <p>
          <span class="role-title">${esc(role.title || '')}</span>
          <span class="role-meta"> — ${esc(role.employer || '')}${role.dates ? ` (${esc(role.dates)})` : ''}</span>
        </p>
        <ul>${(role.bullets || []).map(b => `<li>${esc(b)}</li>`).join('')}</ul>`;
    });
  }

  if ((cv.skills || []).length) {
    html += `<h4>Skills</h4><p>${cv.skills.map(s => esc(s)).join(' · ')}</p>`;
  }

  if ((cv.education || []).length) {
    html += '<h4>Education</h4>';
    cv.education.forEach(e => {
      html += `<p><strong>${esc(e.qualification || '')}</strong> — ${esc(e.institution || '')}${e.dates ? ` (${esc(e.dates)})` : ''}</p>`;
    });
  }

  if ((cv.certifications || []).length) {
    html += `<h4>Certifications</h4><ul>${cv.certifications.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`;
  }

  return html || '<p>No CV content returned.</p>';
}


// ── Accordion ─────────────────────────────────────────────────────────────────

function toggleAccordion(btn) {
  const expanded = btn.getAttribute('aria-expanded') === 'true';
  btn.setAttribute('aria-expanded', String(!expanded));
  const body = btn.nextElementSibling;
  if (body) body.classList.toggle('open', !expanded);
}


// ── Feedback ──────────────────────────────────────────────────────────────────

async function sendFeedback(type, id, thumbsUp, btn) {
  const bar = document.getElementById(`fb-${id}`);
  try {
    await fetch(`/api/feedback/${type}/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thumbs_up: thumbsUp }),
    });
    if (bar) bar.innerHTML = `<span class="feedback-sent">${thumbsUp ? '👍' : '👎'} Thanks for your feedback!</span>`;
  } catch {
    // Feedback is best-effort; don't surface errors
  }
}


// ── Utils ─────────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}
