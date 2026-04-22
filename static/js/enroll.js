/* ═══════════════════════════════════════════════════════════════════
   TAB SWITCHING
═══════════════════════════════════════════════════════════════════ */
function switchTab(tab) {
  document.getElementById('panelSingle').classList.toggle('active', tab === 'single');
  document.getElementById('panelBatch').classList.toggle('active', tab === 'batch');
  document.getElementById('tabSingle').classList.toggle('active', tab === 'single');
  document.getElementById('tabBatch').classList.toggle('active', tab === 'batch');
  // When switching to batch, NFC taps go to batch handler; single tab owns them otherwise
  phase2Active = false;
  refocusNFC();
}

/* ═══════════════════════════════════════════════════════════════════
   SHARED: CVSU EMAIL GENERATOR  (mirrors Python _generate_cvsu_email)
═══════════════════════════════════════════════════════════════════ */
function cvsuEmail(name) {
  if (!name) return '';
  // Remove middle initials (single letter followed by a dot)
  let clean = name.replace(/\b[A-Za-z]\.\s*/g, '').trim();
  // Remove suffixes
  clean = clean.replace(/\b(JR|SR|II|III|IV)\.?\b/gi, '').trim();
  clean = clean.replace(/\s+/g, ' ').trim();
  const words = clean.split(' ').filter(Boolean);
  if (words.length < 2) return '';
  const firstSlug = words.slice(0, -1).map(w => w.toLowerCase().replace(/[^a-z]/g, '')).join('');
  const lastSlug = words[words.length - 1].toLowerCase().replace(/[^a-z]/g, '');
  if (!firstSlug || !lastSlug) return '';
  return `sc.${firstSlug}.${lastSlug}@cvsu.edu.ph`;
}

/* ═══════════════════════════════════════════════════════════════════
   SHARED: NFC HID READER
═══════════════════════════════════════════════════════════════════ */
const nfcHid = document.getElementById('nfcHidInput');
let nfcBuf = '', nfcTimer = null;
const NFC_TIMEOUT = 300;
let phase2Active = false;   // true only during batch NFC phase

function refocusNFC() {
  const tag = document.activeElement ? document.activeElement.tagName : '';
  if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') nfcHid.focus();
}

nfcHid.addEventListener('keydown', function (e) {
  clearTimeout(nfcTimer);
  if (e.key === 'Enter') {
    const uid = nfcBuf.trim(); nfcBuf = ''; nfcHid.value = '';
    if (uid) { if (phase2Active) handleNFCTap(uid); else s_applyUID(uid); }
    return;
  }
  if (e.key.length === 1) { nfcBuf += e.key; nfcHid.value = nfcBuf; }
  nfcTimer = setTimeout(() => {
    const uid = nfcBuf.trim(); nfcBuf = ''; nfcHid.value = '';
    if (uid) { if (phase2Active) handleNFCTap(uid); else s_applyUID(uid); }
  }, NFC_TIMEOUT);
});

document.addEventListener('click', refocusNFC);
nfcHid.addEventListener('blur', () => setTimeout(refocusNFC, 150));
window.addEventListener('load', () => nfcHid.focus());

// Export to window for global access (e.g. from Phone NFC reader in base.js)
window.phase2Active = phase2Active;
window.s_applyUID = s_applyUID;
window.handleNFCTap = handleNFCTap;


/* ═══════════════════════════════════════════════════════════════════
   TAB 1 — SINGLE ENROLL
═══════════════════════════════════════════════════════════════════ */
let s_pendingSubjects = [];

function s_handleDrop(e) {
  e.preventDefault();
  document.getElementById('s_uploadBanner').classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') s_processPdf(f);
  else showMsg('Please drop a PDF file.', 'error');
}
function s_handlePdfUpload(input) { if (input.files && input.files[0]) s_processPdf(input.files[0]); }

function s_processPdf(file) {
  s_setBanner('loading', '⏳', 'Reading PDF…', 'Extracting from ' + file.name);
  const btn = document.getElementById('s_btnUpload'); btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Parsing…';
  const fd = new FormData(); fd.append('file', file);
  fetch('/parse_registration_pdf', { method: 'POST', credentials: 'same-origin', body: fd })
    .then(r => {
      if (!r.ok && r.status === 302) throw new Error('Session expired.');
      const ct = r.headers.get('content-type') || '';
      if (!ct.includes('application/json')) throw new Error('Server error (' + r.status + ').');
      return r.json();
    })
    .then(data => {
      if (data.error) { s_setBanner('error', '❌', 'Could not read PDF', data.error); return; }
      s_autofill(data);
      s_setBanner('success', '✅', 'Filled from: ' + file.name,
        'Fields auto-populated. Subjects will be saved when you click Register.');
      if (data.subjects && data.subjects.length) {
        s_pendingSubjects = data.subjects;
        document.getElementById('pendingSubjectsJson').value = JSON.stringify(s_pendingSubjects);
        s_showSubjectPreview(data.subjects);
      }
    })
    .catch(err => s_setBanner('error', '❌', 'Could not read PDF', 'Error: ' + err.message));
}

function s_autofill(d) {
  // Generate email from name if server didn't return one
  const emailVal = d.email || cvsuEmail(d.name || '');
  const map = {
    f_student_id: d.student_id, f_name: d.name,
    f_email: emailVal,
    f_contact: d.contact, f_section: d.section,
    f_adviser: d.adviser, f_major: d.major,
    f_school_year: d.school_year, f_date_registered: d.date_registered
  };
  for (const [id, val] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el && val) { el.value = val; s_highlight(el); }
  }
  if (d.semester) {
    const sel = document.getElementById('f_semester');
    for (const opt of sel.options) {
      if (opt.value.toLowerCase().includes(d.semester.toLowerCase())) { sel.value = opt.value; s_highlight(sel); break; }
    }
  }
  if (d.course) {
    const sel = document.getElementById('f_course');
    const allowed = ['BS Computer Science', 'BS Information Technology'];
    const match = allowed.find(c => c.toLowerCase() === d.course.toLowerCase() ||
      d.course.toLowerCase().includes(c.replace('BS ', '').toLowerCase()));
    if (match) { sel.value = match; s_highlight(sel); }
  }
  if (d.year_level) {
    const sel = document.getElementById('f_year_level');
    for (const opt of sel.options) {
      if (opt.value.toLowerCase() === d.year_level.toLowerCase()) { sel.value = opt.value; s_highlight(sel); break; }
    }
  }
}

function s_highlight(el) {
  el.style.transition = 'box-shadow .3s,border-color .3s';
  el.style.borderColor = 'var(--success)';
  el.style.boxShadow = '0 0 0 3px rgba(45,106,39,.15)';
  setTimeout(() => { el.style.borderColor = ''; el.style.boxShadow = ''; }, 2000);
}

function s_setBanner(cls, icon, title, sub) {
  document.getElementById('s_uploadBanner').className = 'upload-banner ' + cls;
  document.getElementById('s_ubIcon').textContent = icon;
  document.getElementById('s_ubTitle').textContent = title;
  document.getElementById('s_ubSub').textContent = sub;
  const btn = document.getElementById('s_btnUpload');
  btn.disabled = (cls === 'loading');
  btn.innerHTML = cls === 'loading'
    ? '<span class="spin"></span> Parsing…'
    : (cls === 'success'
      ? '<i class="bi bi-arrow-repeat"></i> Re-upload'
      : '<i class="bi bi-cloud-upload"></i> Upload PDF');
}

function s_showSubjectPreview(subjects) {
  document.getElementById('s_subjPreviewNote').textContent = subjects.length + ' subject(s) will be added on Register';
  document.getElementById('s_subjPreviewList').innerHTML =
    '<table class="subj-table"><thead><tr><th>Code</th><th>Subject Name</th><th>Units</th><th>Status</th></tr></thead><tbody>' +
    subjects.map(s => `<tr><td><code>${s.course_code}</code></td><td>${s.name}</td>
      <td style="color:var(--muted);">${s.units}</td>
      <td style="color:var(--warning);"><i class="bi bi-clock"></i> Pending register</td></tr>`).join('') +
    '</tbody></table>';
  document.getElementById('s_subjPreview').classList.add('show');
}

// NFC for single tab
function s_applyUID(uid) {
  uid = uid.trim().toUpperCase();
  if (!uid || uid.length < 4) return;
  document.getElementById('nfc_id').value = uid;
  const strip = document.getElementById('nfcCardStrip');
  strip.className = 'nfc-card-strip captured';
  document.getElementById('nfcStripIcon').textContent = '✅';
  document.getElementById('nfcStripTitle').textContent = 'Card Captured!';
  document.getElementById('nfcStripSub').textContent = 'NFC card UID recorded. Click Register to save.';
  const disp = document.getElementById('nfcUidDisplay');
  disp.textContent = uid;
  disp.className = 'nfc-uid-display has-uid';
  const hiddenInput = document.getElementById('nfc_id');
  hiddenInput.classList.remove('is-invalid');
  const err = hiddenInput.parentNode.querySelector('.reg-err');
  if (err) err.remove();
}

function previewStudentPhoto(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('photoPreviewImg');
    const init = document.getElementById('photoPreviewInit');
    img.src = e.target.result; img.style.display = 'block'; init.style.display = 'none';
    const wrap = document.getElementById('photoPreviewWrap');
    wrap.style.borderStyle = 'solid'; wrap.style.borderColor = 'var(--accent)';
  };
  reader.readAsDataURL(input.files[0]);
}

function validateRegisterForm() {
  let ok = true;
  const req = [
    { id: 'f_name', msg: 'Full name required.' },
    { id: 'f_student_id', msg: 'Student ID required.' },
    { id: 'f_course', msg: 'Select a program.' },
    { id: 'f_year_level', msg: 'Select year level.' },
    { id: 'f_section', msg: 'Select section.' },
    { id: 'f_adviser', msg: 'Adviser name required.' },
    { id: 'f_school_year', msg: 'School year required.' },
    { id: 'nfc_id', msg: 'Tap an NFC card first.' },
  ];
  document.querySelectorAll('.form-control.is-invalid').forEach(el => el.classList.remove('is-invalid'));
  document.querySelectorAll('.reg-err').forEach(el => el.remove());
  req.forEach(({ id, msg }) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (!el.value || !el.value.trim()) {
      if (id === 'nfc_id') {
        document.getElementById('nfcCardStrip').className = 'nfc-card-strip error';
        document.getElementById('nfcStripTitle').textContent = 'NFC card required';
        document.getElementById('nfcStripSub').textContent = "Tap the student's NFC card on the reader before registering.";
      } else {
        el.classList.add('is-invalid');
        const err = document.createElement('div');
        err.className = 'reg-err';
        err.style.cssText = 'font-size:11px;color:var(--danger);margin-top:3px;';
        err.textContent = msg;
        el.parentNode.insertBefore(err, el.nextSibling);
      }
      ok = false;
    }
  });
  if (!ok) {
    const first = document.querySelector('.form-control.is-invalid,.nfc-card-strip.error');
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  return ok;
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('#registerForm .form-control').forEach(el => {
    el.addEventListener('input', () => {
      el.classList.remove('is-invalid');
      const next = el.nextSibling;
      if (next && next.classList && next.classList.contains('reg-err')) next.remove();
    });
  });
});


/* ═══════════════════════════════════════════════════════════════════
   TAB 2 — BATCH ENROLL
═══════════════════════════════════════════════════════════════════ */
let b_students = [];
let assignmentIndex = 0;
let pendingUID = null;
let history_stack = [];

function gotoPhase(n) {
  document.querySelectorAll('.phase').forEach((p, i) => p.classList.toggle('active', i + 1 === n));
  ['beStep1', 'beStep2', 'beStep3'].forEach((id, i) => {
    const el = document.getElementById(id);
    el.classList.remove('active', 'done');
    if (i + 1 === n) el.classList.add('active');
    if (i + 1 < n) el.classList.add('done');
  });
  phase2Active = (n === 2);
  if (n === 2) { refocusNFC(); renderQueue(); }
  if (n === 3) { renderSummary(); }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function b_handleDrop(e) {
  e.preventDefault();
  document.getElementById('b_uploadBanner').classList.remove('dragover');
  b_processPDFFiles(e.dataTransfer.files);
}
function b_handleFileSelect(input) {
  if (input.files && input.files.length > 0) b_processPDFFiles(input.files);
}

function b_processPDFFiles(files) {
  const pdfs = Array.from(files).filter(f =>
    f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
  if (!pdfs.length) { showMsg('Please select PDF files only.', 'error'); return; }
  b_setBanner('loading', '⏳',
    `Processing ${pdfs.length} PDF(s)…`, 'Extracting student data and sorting alphabetically…');
  const fd = new FormData();
  pdfs.forEach(f => fd.append('files', f));
  fetch('/parse_batch_pdfs', { method: 'POST', credentials: 'same-origin', body: fd })
    .then(r => { if (!r.ok) throw new Error('Server error ' + r.status); return r.json(); })
    .then(data => {
      if (data.error) {
        b_setBanner('error', '❌', 'Could not parse PDFs', data.error);
        (data.details || []).forEach(e => showMsg(e, 'error'));
        return;
      }
      // ── FIX: ensure email is generated for every student ──────────
      b_students = (data.students || []).map(s => {
        if (!s.email && s.name) s.email = cvsuEmail(s.name);
        return { ...s, nfc_id: null, _skipped: false };
      });
      if (!b_students.length) {
        b_setBanner('error', '❌', 'No student data found', 'Check that the PDFs are CvSU registration forms.');
        return;
      }
      b_setBanner('success', '✅',
        `Found ${b_students.length} student(s) — sorted alphabetically`,
        'Review data below. Click Edit on any row to fill missing fields.');
      renderReviewTable();
      document.getElementById('reviewPanel').style.display = 'block';
      (data.errors || []).forEach(e => showMsg('⚠ ' + e, 'info'));
    })
    .catch(err => b_setBanner('error', '❌', 'Upload failed', err.message));
}

/* ── Review table ─────────────────────────────────────────────────── */
function renderReviewTable() {
  const tbody = document.getElementById('studentTbody');
  tbody.innerHTML = '';
  b_students.forEach((s, i) => {
    const missName = !s.name;
    const missSid = !s.student_id;
    const missCourse = !s.course;
    const missYear = !s.year_level;
    const hasMiss = missName || missSid || missCourse || missYear;

    // Ensure email shown is always populated
    if (!s.email && s.name) s.email = cvsuEmail(s.name);

    const nameHtml = (s.name || '<em style="color:var(--muted)">—</em>') + (missName ? '<span class="miss-badge">!</span>' : '');
    const sidHtml = (s.student_id || '<em style="color:var(--muted)">—</em>') + (missSid ? '<span class="miss-badge">!</span>' : '');
    const courseHtml = (s.course || '<em style="color:var(--muted)">—</em>') + (missCourse ? '<span class="miss-badge">!</span>' : '');
    const yearSec = [s.year_level, s.section].filter(Boolean).join(' / ') || '<em style="color:var(--muted)">—</em>';
    const emailHtml = s.email || '<em style="color:var(--muted)">—</em>';
    const file = (s.filename || '').replace(/\.pdf$/i, '');

    const mainRow = document.createElement('tr');
    mainRow.id = `strow_${i}`;
    mainRow.innerHTML = `
      <td><span class="order-badge">${i + 1}</span></td>
      <td style="font-weight:600;">${nameHtml}</td>
      <td>${sidHtml}</td>
      <td>${courseHtml}</td>
      <td>${yearSec}${missYear ? '<span class="miss-badge">!</span>' : ''}</td>
      <td style="font-size:11px;">${emailHtml}</td>
      <td style="font-size:11px;color:var(--muted);">${esc(file)}</td>
      <td>
        <button class="btn-edit-row" id="editbtn_${i}" onclick="toggleInlineEdit(${i})">
          <i class="bi bi-pencil-fill"></i> Edit
        </button>
      </td>`;

    const editRow = document.createElement('tr');
    editRow.id = `stedit_${i}`;
    editRow.className = 'inline-edit-row';
    editRow.style.display = 'none';
    editRow.innerHTML = `<td colspan="8"><div class="ie-grid">${buildIEFields(s, i)}</div>
      <div class="ie-actions">
        <button class="btn-ie-save" onclick="saveInlineEdit(${i})">
          <i class="bi bi-check-lg"></i> Save
        </button>
        <button class="btn-ie-cancel" onclick="toggleInlineEdit(${i})">Cancel</button>
      </div></td>`;

    tbody.appendChild(mainRow);
    tbody.appendChild(editRow);
  });
}

function buildIEFields(s, i) {
  const courseOpts = [
    'BS Computer Science', 'BS Information Technology', 'BS Information Systems',
    'BS Computer Engineering', 'BS Electronics Engineering',
    'BS Civil Engineering', 'BS Education', 'BS Nursing', 'BS Accountancy', 'BS Business Administration'
  ].map(c => `<option value="${c}" ${s.course === c ? 'selected' : ''}>${c}</option>`).join('');
  const yearOpts = ['1st Year', '2nd Year', '3rd Year', '4th Year', '5th Year']
    .map(y => `<option value="${y}" ${s.year_level === y ? 'selected' : ''}>${y}</option>`).join('');
  const semOpts = ['First', 'Second', 'Summer']
    .map(v => `<option value="${v}" ${s.semester === v ? 'selected' : ''}>${v} Semester</option>`).join('');
  const secOpts = ['A', 'B', 'C', 'D']
    .map(v => `<option value="${v}" ${s.section === v ? 'selected' : ''}>${v}</option>`).join('');

  // Pre-generate email for the edit field
  const emailVal = s.email || cvsuEmail(s.name || '');

  return `
    <div class="ie-field"><label class="ie-label">Full Name *</label>
      <input class="ie-input ${!s.name ? 'warn' : ''}" id="ie_name_${i}" value="${esc(s.name)}" placeholder="Full Name"
             oninput="autoEmailFromName(${i})"/></div>
    <div class="ie-field"><label class="ie-label">Student ID</label>
      <input class="ie-input ${!s.student_id ? 'warn' : ''}" id="ie_sid_${i}" value="${esc(s.student_id)}" placeholder="e.g. 2021-00123"/></div>
    <div class="ie-field"><label class="ie-label">Course *</label>
      <select class="ie-input ${!s.course ? 'warn' : ''}" id="ie_course_${i}">
        <option value="">— Select —</option>${courseOpts}</select></div>
    <div class="ie-field"><label class="ie-label">Year Level *</label>
      <select class="ie-input ${!s.year_level ? 'warn' : ''}" id="ie_year_${i}">
        <option value="">— Select —</option>${yearOpts}</select></div>
    <div class="ie-field"><label class="ie-label">Section</label>
      <select class="ie-input" id="ie_sec_${i}">
        <option value="">—</option>${secOpts}</select></div>
    <div class="ie-field"><label class="ie-label">Email</label>
      <input class="ie-input" id="ie_email_${i}" value="${esc(emailVal)}" placeholder="sc.first.last@cvsu.edu.ph"/></div>
    <div class="ie-field"><label class="ie-label">Semester</label>
      <select class="ie-input" id="ie_sem_${i}">
        <option value="">—</option>${semOpts}</select></div>
    <div class="ie-field"><label class="ie-label">School Year</label>
      <input class="ie-input" id="ie_sy_${i}" value="${esc(s.school_year)}" placeholder="2024-2025"/></div>
    <div class="ie-field"><label class="ie-label">Adviser</label>
      <input class="ie-input" id="ie_adv_${i}" value="${esc(s.adviser)}" placeholder="Prof. Santos"/></div>
    <div class="ie-field"><label class="ie-label">Contact</label>
      <input class="ie-input" id="ie_contact_${i}" value="${esc(s.contact)}" placeholder="09XX-XXX-XXXX"/></div>
    <div class="ie-field"><label class="ie-label">Major</label>
      <input class="ie-input" id="ie_major_${i}" value="${esc(s.major)}" placeholder="N/A"/></div>`;
}

// Live email update when name is changed in edit row
function autoEmailFromName(i) {
  const nameEl = document.getElementById(`ie_name_${i}`);
  const emailEl = document.getElementById(`ie_email_${i}`);
  if (!nameEl || !emailEl) return;
  const generated = cvsuEmail(nameEl.value);
  if (generated) emailEl.value = generated;
}

function toggleInlineEdit(i) {
  const editRow = document.getElementById(`stedit_${i}`);
  const editBtn = document.getElementById(`editbtn_${i}`);
  const isOpen = editRow.style.display !== 'none';
  document.querySelectorAll('[id^="stedit_"]').forEach(r => r.style.display = 'none');
  document.querySelectorAll('[id^="editbtn_"]').forEach(b => b.classList.remove('open'));
  if (!isOpen) { editRow.style.display = ''; editBtn.classList.add('open'); editBtn.innerHTML = '<i class="bi bi-x-lg"></i> Close'; }
  else { editBtn.innerHTML = '<i class="bi bi-pencil-fill"></i> Edit'; }
}

function saveInlineEdit(i) {
  const g = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  const s = b_students[i];
  s.name = g(`ie_name_${i}`) || s.name;
  s.student_id = g(`ie_sid_${i}`) || s.student_id;
  s.course = g(`ie_course_${i}`) || s.course;
  s.year_level = g(`ie_year_${i}`) || s.year_level;
  s.section = g(`ie_sec_${i}`) || s.section;
  s.email = g(`ie_email_${i}`) || s.email || cvsuEmail(s.name);
  s.semester = g(`ie_sem_${i}`) || s.semester;
  s.school_year = g(`ie_sy_${i}`) || s.school_year;
  s.adviser = g(`ie_adv_${i}`) || s.adviser;
  s.contact = g(`ie_contact_${i}`) || s.contact;
  s.major = g(`ie_major_${i}`) || s.major || 'N/A';
  renderReviewTable();
}

function proceedToNFC() {
  if (!b_students.length) return;
  const noName = b_students.filter(s => !s.name);
  if (noName.length) { showMsg(`⚠ ${noName.length} student(s) have no name. Edit them before proceeding.`, 'error'); return; }
  assignmentIndex = 0; history_stack = []; pendingUID = null;
  gotoPhase(2); updateCurrentCard();
}

/* ── NFC Assignment ───────────────────────────────────────────────── */
function updateCurrentCard() {
  while (assignmentIndex < b_students.length &&
    (b_students[assignmentIndex].nfc_id || b_students[assignmentIndex]._skipped)) {
    assignmentIndex++;
  }
  const total = b_students.length;
  const assigned = b_students.filter(s => s.nfc_id).length;
  const pct = total ? Math.round(assigned / total * 100) : 0;
  document.getElementById('progBarInner').style.width = pct + '%';
  document.getElementById('progLabel').textContent = `${assigned} / ${total} assigned`;
  if (assignmentIndex >= b_students.length) { allAssigned(); return; }
  const s = b_students[assignmentIndex];
  document.getElementById('currAvatar').textContent = (s.name || '?')[0].toUpperCase();
  document.getElementById('currName').textContent = s.name || '(No name)';
  document.getElementById('currMeta').textContent =
    [s.course, s.year_level, s.section ? 'Section ' + s.section : ''].filter(Boolean).join(' · ');
  document.getElementById('currOrder').textContent = `Student ${assignmentIndex + 1} of ${total}`;
  resetTapZone(); pendingUID = null;
  document.getElementById('btnConfirm').disabled = true;
  document.getElementById('btnUndo').disabled = history_stack.length === 0;
  document.getElementById('dupWarn').classList.remove('show');
  renderQueue(); refocusNFC();
}

function resetTapZone() {
  document.getElementById('tapZone').className = 'tap-zone waiting';
  document.getElementById('tapIcon').textContent = '💳';
  document.getElementById('tapTitle').textContent = 'Tap the NFC card for this student';
  document.getElementById('tapSub').textContent = 'Hold the card near the USB reader — the UID will appear automatically';
  document.getElementById('uidDisplay').style.display = 'none';
}

function renderQueue() {
  const tbody = document.getElementById('queueTbody');
  tbody.innerHTML = '';
  b_students.forEach((s, i) => {
    const isCurrent = i === assignmentIndex && !s.nfc_id && !s._skipped;
    const isAssigned = !!s.nfc_id;
    const isSkipped = s._skipped;
    let statusHtml;
    if (isAssigned) statusHtml = `<span class="status-tag st-assigned">✓ Assigned</span>`;
    else if (isSkipped) statusHtml = `<span class="status-tag st-skipped">Skipped</span>`;
    else if (isCurrent) statusHtml = `<span class="status-tag st-current">← Current</span>`;
    else statusHtml = `<span class="status-tag st-waiting">Waiting</span>`;
    const tr = document.createElement('tr');
    if (isCurrent) tr.className = 'row-current';
    if (isAssigned || isSkipped) tr.className = 'row-done';
    tr.innerHTML = `
      <td><span class="order-badge">${i + 1}</span></td>
      <td style="font-weight:${isCurrent ? 700 : 500};">${s.name || '—'}</td>
      <td style="font-size:12px;color:var(--muted);">${[s.course, s.year_level, s.section].filter(Boolean).join(' / ') || '—'}</td>
      <td>${isAssigned ? `<span class="nfc-chip">${s.nfc_id}</span>` : '—'}</td>
      <td>${statusHtml}</td>`;
    tbody.appendChild(tr);
  });
}

function handleNFCTap(uid) {
  if (!phase2Active) return;
  uid = uid.trim().toUpperCase();
  if (!uid || uid.length < 4) return;
  if (assignmentIndex >= b_students.length) return;
  const dupIdx = b_students.findIndex((s, i) => s.nfc_id === uid && i !== assignmentIndex);
  if (dupIdx !== -1) {
    document.getElementById('dupWarnText').textContent =
      `This card (${uid}) is already assigned to ${b_students[dupIdx].name} (#${dupIdx + 1}). Please use a different card.`;
    document.getElementById('dupWarn').classList.add('show');
    return;
  }
  document.getElementById('dupWarn').classList.remove('show');
  pendingUID = uid;
  document.getElementById('tapZone').className = 'tap-zone scanned';
  document.getElementById('tapIcon').textContent = '✅';
  document.getElementById('tapTitle').textContent = 'Card detected — confirm assignment';
  document.getElementById('tapSub').textContent = 'Check the UID below then click Confirm to assign this card.';
  document.getElementById('uidText').textContent = uid;
  document.getElementById('uidDisplay').style.display = '';
  document.getElementById('btnConfirm').disabled = false;
}

function confirmAssignment() {
  if (!pendingUID || assignmentIndex >= b_students.length) return;
  b_students[assignmentIndex].nfc_id = pendingUID;
  history_stack.push({ index: assignmentIndex, nfc_id: pendingUID });
  assignmentIndex++; pendingUID = null;
  updateCurrentCard();
}

function undoAssignment() {
  if (!history_stack.length) return;
  const last = history_stack.pop();
  b_students[last.index].nfc_id = null;
  b_students[last.index]._skipped = false;
  assignmentIndex = last.index; pendingUID = null;
  document.getElementById('dupWarn').classList.remove('show');
  updateCurrentCard();
}

function skipStudent() {
  if (assignmentIndex >= b_students.length) return;
  b_students[assignmentIndex]._skipped = true;
  history_stack.push({ index: assignmentIndex, nfc_id: null, skipped: true });
  assignmentIndex++; pendingUID = null;
  updateCurrentCard();
}

/* ── Web NFC API Support (Phone NFC) ──────────────────────── */
// Handled by startPhoneNFC() in base.js

function allAssigned() {
  if (!b_students.some(s => s.nfc_id)) {
    showMsg('No students were assigned NFC cards. Please go back and retry.', 'error');
    return;
  }
  gotoPhase(3);
}

function b_goBack() {
  phase2Active = false;
  b_students.forEach(s => { s.nfc_id = null; s._skipped = false; });
  history_stack = []; assignmentIndex = 0; pendingUID = null;
  gotoPhase(1);
}

/* ── Summary ──────────────────────────────────────────────────────── */
function renderSummary() {
  const total = b_students.length;
  const assigned = b_students.filter(s => s.nfc_id).length;
  const skipped = b_students.filter(s => s._skipped).length;
  const nocard = total - assigned - skipped;
  document.getElementById('summaryGrid').innerHTML = `
    <div class="sum-chip total"><div style="font-size:28px;">👥</div>
      <div><div class="sum-val">${total}</div><div class="sum-lab">Total Students</div></div></div>
    <div class="sum-chip assigned"><div style="font-size:28px;">✅</div>
      <div><div class="sum-val" style="color:var(--success);">${assigned}</div><div class="sum-lab">Cards Assigned</div></div></div>
    <div class="sum-chip skipped"><div style="font-size:28px;">⏭</div>
      <div><div class="sum-val" style="color:var(--danger);">${skipped + nocard}</div><div class="sum-lab">Skipped / No Card</div></div></div>`;

  const allSubjects = {};
  b_students.filter(s => s.nfc_id).forEach(s => {
    (s.subjects || []).forEach(subj => {
      if (subj.course_code && !allSubjects[subj.course_code]) allSubjects[subj.course_code] = subj;
    });
  });
  const subjKeys = Object.keys(allSubjects);
  if (subjKeys.length) {
    document.getElementById('subjectSummaryBox').style.display = '';
    const tableRows = subjKeys.map(k => {
      const s = allSubjects[k];
      return `<tr><td style="padding:8px 10px;border-bottom:1px solid rgba(45,106,39,.15);font-family:'Space Mono',monospace;font-size:11px;color:var(--accent);font-weight:700;">${s.course_code}</td>
              <td style="padding:8px 10px;border-bottom:1px solid rgba(45,106,39,.15);font-size:12px;">${s.name}</td></tr>`;
    }).join('');
    document.getElementById('subjectList').innerHTML = `<table style="width:100%;border-collapse:collapse;"><thead><tr><th style="text-align:left;padding:8px 10px;border-bottom:1px solid rgba(45,106,39,.3);font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;">Code</th><th style="text-align:left;padding:8px 10px;border-bottom:1px solid rgba(45,106,39,.3);font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;">Subject</th></tr></thead><tbody>${tableRows}</tbody></table>`;
  }

  const tbody = document.getElementById('resultTbody');
  tbody.innerHTML = '';
  b_students.forEach((s, i) => {
    const isAssigned = !!s.nfc_id;
    const statusHtml = isAssigned
      ? `<span class="status-tag st-assigned">Will Register</span>`
      : `<span class="status-tag st-skipped">${s._skipped ? 'Skipped' : 'No Card'}</span>`;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="order-badge">${i + 1}</span></td>
      <td style="font-weight:600;">${s.name || '—'}</td>
      <td style="font-size:11px;font-family:monospace;">${s.student_id || '—'}</td>
      <td style="font-size:11px;">${s.course || '—'}</td>
      <td style="font-size:11px;">${[s.year_level, s.section].filter(Boolean).join(' / ') || '—'}</td>
      <td>${s.nfc_id ? `<span class="nfc-chip">${s.nfc_id}</span>` : '—'}</td>
      <td>${statusHtml}</td>`;
    tbody.appendChild(tr);
  });
}

function doRegister() {
  const toRegister = b_students.filter(s => s.nfc_id);
  if (!toRegister.length) { showMsg('No students with NFC cards assigned. Nothing to register.', 'error'); return; }
  const btn = document.getElementById('registerBtn');
  btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Registering…';
  document.getElementById('studentsDataInput').value = JSON.stringify(toRegister);
  document.getElementById('finalForm').submit();
}

function b_setBanner(cls, icon, title, sub) {
  document.getElementById('b_uploadBanner').className = 'upload-banner ' + cls;
  document.getElementById('b_ubIcon').textContent = icon;
  document.getElementById('b_ubTitle').textContent = title;
  document.getElementById('b_ubSub').textContent = sub;
  const btn = document.getElementById('b_btnUpload');
  btn.disabled = (cls === 'loading');
  btn.innerHTML = cls === 'loading'
    ? '<span class="spin"></span> Parsing…'
    : (cls === 'success'
      ? '<i class="bi bi-arrow-repeat"></i> Upload More'
      : '<i class="bi bi-cloud-upload"></i> Select PDFs');
}

function b_resetAll() {
  b_students = []; assignmentIndex = 0; history_stack = []; pendingUID = null; phase2Active = false;
  document.getElementById('reviewPanel').style.display = 'none';
  document.getElementById('studentTbody').innerHTML = '';
  document.getElementById('msgBox').innerHTML = '';
  b_setBanner('', '📄',
    'Upload Multiple CvSU Registration PDFs',
    'Drop PDF files here or click to browse — students will be sorted alphabetically by surname');
  gotoPhase(1);
}

/* ── Shared helpers ───────────────────────────────────────────────── */
function showMsg(text, type = 'info') {
  const box = document.getElementById('msgBox');
  const div = document.createElement('div');
  div.className = 'msg-box ' + type;
  const icon = type === 'error' ? 'bi-x-circle' : type === 'success' ? 'bi-check-circle' : 'bi-info-circle';
  div.innerHTML = `<i class="bi ${icon}"></i> ${text}`;
  box.appendChild(div);
  setTimeout(() => { if (div.parentNode) div.remove(); }, 7000);
}

function esc(v) {
  if (!v) return '';
  return String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
