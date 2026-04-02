// Batch enrollment page script: extracted from template for easier debugging.

/* State */
let students = []; // all parsed + sorted students
let assignmentIndex = 0; // which student we're currently assigning
let pendingUID = null; // UID scanned but not yet confirmed
let history_stack = []; // [{index, nfc_id}] for undo

// NFC HID reader state
let nfcBuffer = '';
let nfcTimer = null;
const NFC_TIMEOUT = 300;
let phase2Active = false; // only process taps during phase 2

/* Step navigation */
function gotoPhase(n) {
  document.querySelectorAll('.phase').forEach((p, i) => {
    p.classList.toggle('active', i + 1 === n);
  });
  ['beStep1', 'beStep2', 'beStep3'].forEach((id, i) => {
    const el = document.getElementById(id);
    el.classList.remove('active', 'done');
    if (i + 1 === n) el.classList.add('active');
    if (i + 1 < n) el.classList.add('done');
  });
  phase2Active = (n === 2);
  if (n === 2) {
    refocusNFC();
    renderQueue();
  }
  if (n === 3) {
    renderSummary();
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* PDF upload and parsing */
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('uploadBanner').classList.remove('dragover');
  processPDFFiles(e.dataTransfer.files);
}

function handleFileSelect(input) {
  if (input.files && input.files.length > 0) processPDFFiles(input.files);
}

function processPDFFiles(files) {
  const pdfs = Array.from(files).filter((f) =>
    f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
  if (!pdfs.length) {
    showMsg('Please select PDF files only.', 'error');
    return;
  }

  setBanner('loading', '⏳',
    `Processing ${pdfs.length} PDF(s)…`,
    'Extracting student data and sorting alphabetically…');

  const fd = new FormData();
  pdfs.forEach((f) => fd.append('files', f));

  fetch('/parse_batch_pdfs', { method: 'POST', credentials: 'same-origin', body: fd })
    .then((r) => {
      if (!r.ok) throw new Error('Server error ' + r.status);
      return r.json();
    })
    .then((data) => {
      if (data.error) {
        setBanner('error', '❌', 'Could not parse PDFs', data.error);
        (data.details || []).forEach((e) => showMsg(e, 'error'));
        return;
      }
      students = (data.students || []).map((s) => ({ ...s, nfc_id: null, _skipped: false }));
      if (!students.length) {
        setBanner('error', '❌', 'No student data found', 'Check that the PDFs are CvSU registration forms.');
        return;
      }
      setBanner('success', '✅',
        `Found ${students.length} student(s) — sorted alphabetically`,
        'Review data below. Click Edit on any row to fill missing fields.');
      renderReviewTable();
      document.getElementById('reviewPanel').style.display = 'block';
      (data.errors || []).forEach((e) => showMsg('⚠ ' + e, 'info'));
    })
    .catch((err) => {
      setBanner('error', '❌', 'Upload failed', err.message);
    });
}

/* Phase 1: review table */
function renderReviewTable() {
  const tbody = document.getElementById('studentTbody');
  tbody.innerHTML = '';
  students.forEach((s, i) => {
    const missName = !s.name;
    const missSid = !s.student_id;
    const missCourse = !s.course;
    const missYear = !s.year_level;
    const hasMiss = missName || missSid || missCourse || missYear;

    const nameHtml = (s.name || '<em style="color:var(--muted)">—</em>') + (missName ? '<span class="miss-badge">!</span>' : '');
    const sidHtml = (s.student_id || '<em style="color:var(--muted)">—</em>') + (missSid ? '<span class="miss-badge">!</span>' : '');
    const courseHtml = (s.course || '<em style="color:var(--muted)">—</em>') + (missCourse ? '<span class="miss-badge">!</span>' : '');
    const yearSec = [s.year_level, s.section].filter(Boolean).join(' / ') || '<em style="color:var(--muted)">—</em>';
    const emailHtml = s.email || '<em style="color:var(--muted)">—</em>';
    const file = (s.filename || '').replace(/\.pdf$/i, '');

    const mainRow = document.createElement('tr');
    mainRow.id = `strow_${i}`;
    mainRow.className = hasMiss ? 'row-warn' : '';
    mainRow.innerHTML = `
      <td><span class="order-badge">${i + 1}</span></td>
      <td style="font-weight:600;">${nameHtml}</td>
      <td>${sidHtml}</td>
      <td>${courseHtml}</td>
      <td>${yearSec}${missYear ? '<span class="miss-badge">!</span>' : ''}</td>
      <td style="font-size:11px;">${emailHtml}</td>
      <td style="font-size:11px;color:var(--muted);">${file}</td>
      <td>
        <button class="btn-vr" style="font-size:11px;padding:5px 10px;" onclick="toggleInlineEdit(${i})">
          <i class="bi bi-pencil"></i> Edit
        </button>
      </td>`;

    const editRow = document.createElement('tr');
    editRow.id = `stedit_${i}`;
    editRow.className = 'inline-edit-row';
    editRow.style.display = 'none';
    editRow.innerHTML = `<td colspan="8"><div class="ie-grid">${buildIEFields(s, i)}</div>
      <div class="ie-actions">
        <button class="btn-ie-save" onclick="saveInlineEdit(${i})"><i class="bi bi-check-lg"></i> Save</button>
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
    'BS Civil Engineering', 'BS Education', 'BS Nursing', 'BS Accountancy', 'BS Business Administration',
  ].map((c) => `<option value="${c}" ${s.course === c ? 'selected' : ''}>${c}</option>`).join('');

  const yearOpts = ['1st Year', '2nd Year', '3rd Year', '4th Year', '5th Year']
    .map((y) => `<option value="${y}" ${s.year_level === y ? 'selected' : ''}>${y}</option>`).join('');

  const semOpts = ['First', 'Second', 'Summer']
    .map((v) => `<option value="${v}" ${s.semester === v ? 'selected' : ''}>${v} Semester</option>`).join('');

  const secOpts = ['A', 'B', 'C', 'D']
    .map((v) => `<option value="${v}" ${s.section === v ? 'selected' : ''}>${v}</option>`).join('');

  return `
    <div class="ie-field"><label class="ie-label">Full Name *</label>
      <input class="ie-input ${!s.name ? 'warn' : ''}" id="ie_name_${i}" value="${esc(s.name)}" placeholder="Full Name"/></div>
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
      <input class="ie-input" id="ie_email_${i}" value="${esc(s.email)}" placeholder="sc.first.last@cvsu.edu.ph"/></div>
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

function toggleInlineEdit(i) {
  const editRow = document.getElementById(`stedit_${i}`);
  const isOpen = editRow.style.display !== 'none';
  document.querySelectorAll('[id^="stedit_"]').forEach((r) => {
    r.style.display = 'none';
  });
  if (!isOpen) editRow.style.display = '';
}

function saveInlineEdit(i) {
  const g = (id) => {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  };
  const s = students[i];
  s.name = g(`ie_name_${i}`) || s.name;
  s.student_id = g(`ie_sid_${i}`) || s.student_id;
  s.course = g(`ie_course_${i}`) || s.course;
  s.year_level = g(`ie_year_${i}`) || s.year_level;
  s.section = g(`ie_sec_${i}`) || s.section;
  s.email = g(`ie_email_${i}`) || s.email;
  s.semester = g(`ie_sem_${i}`) || s.semester;
  s.school_year = g(`ie_sy_${i}`) || s.school_year;
  s.adviser = g(`ie_adv_${i}`) || s.adviser;
  s.contact = g(`ie_contact_${i}`) || s.contact;
  s.major = g(`ie_major_${i}`) || s.major || 'N/A';

  renderReviewTable();
  document.getElementById(`stedit_${i}`).style.display = '';
}

function proceedToNFC() {
  if (!students.length) return;
  const noName = students.filter((s) => !s.name);
  if (noName.length) {
    showMsg(`⚠ ${noName.length} student(s) have no name. Edit them before proceeding.`, 'error');
    return;
  }
  assignmentIndex = 0;
  history_stack = [];
  pendingUID = null;
  gotoPhase(2);
  updateCurrentCard();
}

/* Phase 2: NFC assignment */
function updateCurrentCard() {
  while (assignmentIndex < students.length && (students[assignmentIndex].nfc_id || students[assignmentIndex]._skipped)) {
    assignmentIndex += 1;
  }

  const total = students.length;
  const assigned = students.filter((s) => s.nfc_id).length;
  const pct = total ? Math.round((assigned / total) * 100) : 0;

  document.getElementById('progBarInner').style.width = pct + '%';
  document.getElementById('progLabel').textContent = `${assigned} / ${total} assigned`;

  if (assignmentIndex >= students.length) {
    allAssigned();
    return;
  }

  const s = students[assignmentIndex];
  document.getElementById('currAvatar').textContent = (s.name || '?')[0].toUpperCase();
  document.getElementById('currName').textContent = s.name || '(No name)';
  document.getElementById('currMeta').textContent = [s.course, s.year_level, s.section ? 'Section ' + s.section : ''].filter(Boolean).join(' · ');
  document.getElementById('currOrder').textContent = `Student ${assignmentIndex + 1} of ${total}`;

  resetTapZone();
  pendingUID = null;
  document.getElementById('btnConfirm').disabled = true;
  document.getElementById('btnUndo').disabled = history_stack.length === 0;
  document.getElementById('dupWarn').classList.remove('show');

  renderQueue();
  refocusNFC();
}

function resetTapZone() {
  const zone = document.getElementById('tapZone');
  const icon = document.getElementById('tapIcon');
  const title = document.getElementById('tapTitle');
  const sub = document.getElementById('tapSub');
  const uid = document.getElementById('uidDisplay');
  zone.className = 'tap-zone waiting';
  icon.textContent = '💳';
  title.textContent = 'Tap the NFC card for this student';
  sub.textContent = 'Hold the card near the USB reader — the UID will appear automatically';
  uid.style.display = 'none';
}

function renderQueue() {
  const tbody = document.getElementById('queueTbody');
  tbody.innerHTML = '';
  students.forEach((s, i) => {
    const isCurrent = i === assignmentIndex && !s.nfc_id && !s._skipped;
    const isAssigned = !!s.nfc_id;
    const isSkipped = s._skipped;

    let statusHtml;
    if (isAssigned) statusHtml = `<span class="status-tag st-assigned">✓ ${s.nfc_id}</span>`;
    else if (isSkipped) statusHtml = '<span class="status-tag st-skipped">Skipped</span>';
    else if (isCurrent) statusHtml = '<span class="status-tag st-current">← Current</span>';
    else statusHtml = '<span class="status-tag st-waiting">Waiting</span>';

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
  if (assignmentIndex >= students.length) return;

  const dupIdx = students.findIndex((s, i) => s.nfc_id === uid && i !== assignmentIndex);
  if (dupIdx !== -1) {
    const dup = students[dupIdx];
    document.getElementById('dupWarnText').textContent = `This card (${uid}) is already assigned to ${dup.name} (#${dupIdx + 1}). Please use a different card.`;
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
  if (!pendingUID || assignmentIndex >= students.length) return;
  const s = students[assignmentIndex];
  s.nfc_id = pendingUID;

  history_stack.push({ index: assignmentIndex, nfc_id: pendingUID });

  assignmentIndex += 1;
  pendingUID = null;
  updateCurrentCard();
}

function undoAssignment() {
  if (!history_stack.length) return;
  const last = history_stack.pop();
  students[last.index].nfc_id = null;
  students[last.index]._skipped = false;
  assignmentIndex = last.index;
  pendingUID = null;
  document.getElementById('dupWarn').classList.remove('show');
  updateCurrentCard();
}

function skipStudent() {
  if (assignmentIndex >= students.length) return;
  students[assignmentIndex]._skipped = true;
  history_stack.push({ index: assignmentIndex, nfc_id: null, skipped: true });
  assignmentIndex += 1;
  pendingUID = null;
  updateCurrentCard();
}

function allAssigned() {
  const hasAssigned = students.some((s) => s.nfc_id);
  if (!hasAssigned) {
    showMsg('No students were assigned NFC cards. Please go back and retry.', 'error');
    return;
  }
  gotoPhase(3);
}

function goBack() {
  phase2Active = false;
  students.forEach((s) => {
    s.nfc_id = null;
    s._skipped = false;
  });
  history_stack = [];
  assignmentIndex = 0;
  pendingUID = null;
  gotoPhase(1);
}

/* Phase 3: summary and register */
function renderSummary() {
  const total = students.length;
  const assigned = students.filter((s) => s.nfc_id).length;
  const skipped = students.filter((s) => s._skipped).length;
  const nocard = total - assigned - skipped;

  document.getElementById('summaryGrid').innerHTML = `
    <div class="sum-chip total">
      <div style="font-size:28px;">👥</div>
      <div><div class="sum-val">${total}</div><div class="sum-lab">Total Students</div></div>
    </div>
    <div class="sum-chip assigned">
      <div style="font-size:28px;">✅</div>
      <div><div class="sum-val" style="color:var(--success);">${assigned}</div><div class="sum-lab">Cards Assigned</div></div>
    </div>
    <div class="sum-chip skipped">
      <div style="font-size:28px;">⏭</div>
      <div><div class="sum-val" style="color:var(--danger);">${skipped + nocard}</div><div class="sum-lab">Skipped / No Card</div></div>
    </div>`;

  const allSubjects = {};
  students.filter((s) => s.nfc_id).forEach((s) => {
    (s.subjects || []).forEach((subj) => {
      if (subj.course_code && !allSubjects[subj.course_code]) {
        allSubjects[subj.course_code] = subj;
      }
    });
  });

  const subjKeys = Object.keys(allSubjects);
  if (subjKeys.length) {
    document.getElementById('subjectSummaryBox').style.display = '';
    document.getElementById('subjectList').innerHTML = subjKeys.map((k) => {
      const s = allSubjects[k];
      return `<span style="background:rgba(45,106,39,.08);border:1px solid rgba(45,106,39,.2);border-radius:6px;padding:4px 10px;font-size:11px;font-family:'Space Mono',monospace;color:var(--accent);">[${s.course_code}] ${s.name}</span>`;
    }).join('');
  }

  const tbody = document.getElementById('resultTbody');
  tbody.innerHTML = '';
  students.forEach((s, i) => {
    const isAssigned = !!s.nfc_id;
    const statusHtml = isAssigned
      ? '<span class="status-tag st-assigned">Will Register</span>'
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
  const toRegister = students.filter((s) => s.nfc_id);
  if (!toRegister.length) {
    showMsg('No students with NFC cards assigned. Nothing to register.', 'error');
    return;
  }
  const btn = document.getElementById('registerBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Registering…';

  document.getElementById('studentsDataInput').value = JSON.stringify(toRegister);
  document.getElementById('finalForm').submit();
}

/* NFC HID reader */
const nfcHid = document.getElementById('nfcHidInput');

function refocusNFC() {
  const tag = document.activeElement ? document.activeElement.tagName : '';
  if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
    nfcHid.focus();
  }
}

nfcHid.addEventListener('keydown', function onNfcKeydown(e) {
  clearTimeout(nfcTimer);
  if (e.key === 'Enter') {
    const uid = nfcBuffer.trim();
    nfcBuffer = '';
    nfcHid.value = '';
    if (uid) handleNFCTap(uid);
    return;
  }
  if (e.key.length === 1) {
    nfcBuffer += e.key;
    nfcHid.value = nfcBuffer;
  }
  nfcTimer = setTimeout(() => {
    const uid = nfcBuffer.trim();
    nfcBuffer = '';
    nfcHid.value = '';
    if (uid) handleNFCTap(uid);
  }, NFC_TIMEOUT);
});

document.addEventListener('click', refocusNFC);
nfcHid.addEventListener('blur', () => setTimeout(refocusNFC, 150));
window.addEventListener('load', () => nfcHid.focus());

/* Helpers */
function setBanner(cls, icon, title, sub) {
  document.getElementById('uploadBanner').className = 'upload-banner ' + cls;
  document.getElementById('ubIcon').textContent = icon;
  document.getElementById('ubTitle').textContent = title;
  document.getElementById('ubSub').textContent = sub;
  const btn = document.getElementById('btnUpload');
  btn.disabled = (cls === 'loading');
  btn.innerHTML = cls === 'loading'
    ? '<span class="spin"></span> Parsing…'
    : (cls === 'success'
      ? '<i class="bi bi-arrow-repeat"></i> Upload More'
      : '<i class="bi bi-cloud-upload"></i> Select PDFs');
}

function showMsg(text, type = 'info') {
  const box = document.getElementById('msgBox');
  const div = document.createElement('div');
  div.className = 'msg-box ' + type;
  const icon = type === 'error' ? 'bi-x-circle' : type === 'success' ? 'bi-check-circle' : 'bi-info-circle';
  div.innerHTML = `<i class="bi ${icon}"></i> ${text}`;
  box.appendChild(div);
  setTimeout(() => {
    if (div.parentNode) div.remove();
  }, 7000);
}

function resetAll() {
  students = [];
  assignmentIndex = 0;
  history_stack = [];
  pendingUID = null;
  phase2Active = false;
  document.getElementById('reviewPanel').style.display = 'none';
  document.getElementById('studentTbody').innerHTML = '';
  document.getElementById('msgBox').innerHTML = '';
  setBanner('', '📄',
    'Upload Multiple CvSU Registration PDFs',
    'Drop PDF files here or click to browse — students will be sorted alphabetically by surname');
  gotoPhase(1);
}

function esc(v) {
  if (!v) return '';
  return String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
