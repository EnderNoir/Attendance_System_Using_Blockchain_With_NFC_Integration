// Dashboard page script: extracted from template for easier debugging.

const DASHBOARD_BOOTSTRAP = window.DASHBOARD_BOOTSTRAP || {};
const RAW_STUDENTS = Array.isArray(DASHBOARD_BOOTSTRAP.students) ? DASHBOARD_BOOTSTRAP.students : [];
const RAW_TEACHERS = DASHBOARD_BOOTSTRAP.teachers || {};
const PHOTO_MAP = DASHBOARD_BOOTSTRAP.photos || {};
const CURRENT_ROLE = String(DASHBOARD_BOOTSTRAP.currentRole || '').toLowerCase();
const CURRENT_USERNAME = String(DASHBOARD_BOOTSTRAP.currentUsername || '');

const studentData = RAW_STUDENTS.map((s, idx) => {
  const nfc = s.nfcId || s.nfc_id || '';
  return {
    idx,
    nfc,
    name: s.name || '',
    sid: s.student_id || '',
    course: s.course || '',
    year: s.year_level || '',
    section: s.section || '',
    major: s.major || 'N/A',
    adviser: s.adviser || '',
    email: s.email || '',
    contact: s.contact || '',
    semester: s.semester || '',
    sy: s.school_year || '',
    datereg: s.date_registered || '',
    photo: PHOTO_MAP[nfc] || '',
  };
});

const teacherData = {};
Object.entries(RAW_TEACHERS).forEach(([username, u]) => {
  teacherData[username] = {
    username,
    name: u.full_name || '',
    email: u.email || '',
    role: u.role || '',
    status: u.status || 'pending',
    created: u.created_at || '',
    sections: Array.isArray(u.sections) ? u.sections : [],
    photo: PHOTO_MAP[username] || '',
  };
});

let curMode=null, curId=null, allSessions=[];

// Modal open / close (required by openStudentRecord and openTeacherRecord)
function openUpdModal() {
  document.getElementById('updModal').classList.add('show');
  document.body.style.overflow = 'hidden';
}
function closeUpdModal() {
  document.getElementById('updModal').classList.remove('show');
  document.body.style.overflow = '';
  // Reset message state
  const msg = document.getElementById('updMsg');
  if (msg) { msg.style.display = 'none'; msg.textContent = ''; }
  const btn = document.getElementById('updSaveBtn');
  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Update'; }
}

function switchTab(id,btn){
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}

// FIX 1: switchMTab always reloads sessions when tab clicked - no allSessions guard
function switchMTab(id, btn) {
  document.querySelectorAll('.mpane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.mtab').forEach(b => b.classList.remove('active'));
  document.getElementById('mpane-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'sessions' && curMode === 'student') {
    loadStudentSessions(curId);
  }
}

// FIX 2: Single authoritative loadStudentSessions definition
function loadStudentSessions(nfcId) {
  if (!nfcId) return;
  const wrap  = document.getElementById('sessLogWrap');
  const label = document.getElementById('sessCountLabel');
  wrap.innerHTML = `<div style="text-align:center;color:var(--muted);padding:24px;font-size:12px;">
    <div style="width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 8px;"></div>
    Loading sessions...
  </div>`;
  if (label) label.textContent = 'Loading...';

  fetch(`/api/student_sessions/${nfcId}`, { credentials: 'same-origin' })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      allSessions = data;
      const subjects = [...new Set(data.map(s => s.subject_name).filter(Boolean))].sort();
      const sel = document.getElementById('sessSubject');
      if (sel) {
        sel.innerHTML = '<option value="">All Subjects</option>' +
          subjects.map(s => `<option value="${s}">${s}</option>`).join('');
      }
      renderSessions(data);
    })
    .catch(err => {
      console.error('loadStudentSessions error:', err);
      if (wrap) wrap.innerHTML = `<div style="color:var(--danger);text-align:center;padding:16px;font-size:12px;">
        Failed to load sessions: ${err.message}
      </div>`;
    });
}

function handleUpdPhoto(input){
  if(!input.files||!input.files[0]||!curId) return;
  const fd=new FormData();
  fd.append('photo',input.files[0]);
  fd.append('person_id',curId);
  fetch('/upload_photo',{method:'POST',credentials:'same-origin',body:fd})
    .then(r=>r.json()).then(d=>{
      if(d.ok){
        const editAv = document.getElementById('editPhotoPreview');
        if(editAv){
          editAv.innerHTML='';
          editAv.style.overflow='hidden';
          const img=document.createElement('img');
          img.src=d.url+'?t='+Date.now();
          img.style='width:100%;height:100%;object-fit:cover;border-radius:50%;';
          editAv.appendChild(img);
        }
        const infoAv = document.getElementById('infoPhotoWrap');
        if(infoAv && infoAv.tagName==='DIV'){
          infoAv.innerHTML='';
          infoAv.style.overflow='hidden';
          const img=document.createElement('img');
          img.src=d.url+'?t='+Date.now();
          img.style='width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);';
          infoAv.appendChild(img);
        }
        if(curMode==='student'){
          const s=studentData.find(x=>x.nfc===curId);
          if(s) s.photo=d.filename;
        }
      }
    });
}

function openStudentRecord(idx){
  const s=studentData[idx];
  curMode='student'; curId=s.nfc; allSessions=[];

  document.getElementById('updTitle').textContent = s.name;
  document.getElementById('updSub').textContent   = (s.course||'-')+' | '+(s.year||'-')+' | Section '+(s.section||'-');

  const photoHtml = s.photo
    ? `<img src="/static/uploads/${s.photo}?t=${Date.now()}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);" id="infoPhotoWrap"/>`
    : `<div id="infoPhotoWrap" style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:#000;">${s.name[0].toUpperCase()}</div>`;

  document.getElementById('infoContent').innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:18px;padding:4px 0 12px;border-bottom:1px solid var(--border);flex-wrap:wrap;">
      ${photoHtml}
      <div style="flex:1;min-width:0;">
        <div style="font-size:16px;font-weight:700;">${s.name}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:3px;">${s.course}</div>
        <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;">
          <span style="background:rgba(45,106,39,.08);border:1px solid rgba(45,106,39,.2);border-radius:5px;padding:2px 8px;font-size:11px;font-family:'Space Mono',monospace;color:var(--accent);">NFC: ${s.nfc}</span>
          ${s.sid?`<span style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:5px;padding:2px 8px;font-size:11px;font-family:'Space Mono',monospace;color:var(--muted);">ID: ${s.sid}</span>`:''}
        </div>
        <div style="font-size:10px;color:rgba(45,106,39,.5);margin-top:5px;"><i class="bi bi-pencil-square"></i> Go to Update tab to change photo</div>
      </div>
    </div>
    <div class="info-card-grid">
      ${infoRow('Semester', s.semester)}
      ${infoRow('School Year', s.sy)}
      ${infoRow('Date of Admission', s.datereg)}
      ${infoRow('Year Level', s.year)}
      ${infoRow('Section', s.section)}
      ${infoRow('Major', s.major)}
      ${infoRow('Class Adviser', s.adviser)}
      ${infoRow('Contact Number', s.contact)}
      ${infoRow('Email Address', s.email, true)}
    </div>`;

  const semOpts = ['First','Second','Summer','Mid-Year'].map(v=>
    `<option value="${v}" ${s.semester===v||s.semester===v+' Semester'?'selected':''}>${v} Semester</option>`).join('');
  const yearOpts = ['1st Year','2nd Year','3rd Year','4th Year','5th Year'].map(v=>
    `<option value="${v}" ${s.year===v?'selected':''}>${v}</option>`).join('');
  const courseOpts = ['BS Computer Science','BS Information Technology','BS Information Systems',
    'BS Computer Engineering','BS Electronics Engineering','BS Electrical Engineering',
    'BS Civil Engineering','BS Mechanical Engineering','BS Education','BS Nursing',
    'BS Accountancy','BS Business Administration'].map(v=>
    `<option value="${v}" ${s.course===v?'selected':''}>${v}</option>`).join('');
  const secOpts = ['A','B','C','D'].map(v=>`<option value="${v}" ${s.section===v?'selected':''}>${v}</option>`).join('');

  const editPhotoInner = s.photo
    ? `<img src="/static/uploads/${s.photo}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`
    : `<span style="font-size:22px;font-weight:700;color:#000;">${s.name[0].toUpperCase()}</span>`;

  document.getElementById('editContent').innerHTML = `
    <div class="photo-upload-block">
      <div class="photo-avatar-preview" id="editPhotoPreview" onclick="document.getElementById('updPhotoInput').click()" title="Click to change photo">${editPhotoInner}</div>
      <div>
        <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"><i class="bi bi-camera-fill"></i> Student Photo</div>
        <button type="button" onclick="document.getElementById('updPhotoInput').click()" style="background:rgba(45,106,39,.1);border:1px solid rgba(45,106,39,.2);color:var(--accent);border-radius:7px;padding:7px 14px;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-family:'DM Sans',sans-serif;font-weight:600;">
          <i class="bi bi-upload"></i> Change Photo
        </button>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">JPG, PNG, WEBP | Max 5 MB</div>
      </div>
    </div>
    <div class="sec-title">// Enrollment Details</div>
    <div class="upd-grid">
      <div class="upd-field"><span class="upd-label">Semester</span>
        <select class="upd-input" id="uf_semester" style="appearance:none;"><option value="">- Select -</option>${semOpts}</select>
      </div>
      <div class="upd-field"><span class="upd-label">School Year</span>
        <input class="upd-input" id="uf_sy" value="${s.sy}" placeholder="e.g. 2024-2025"/>
      </div>
      <div class="upd-field"><span class="upd-label">Date of Admission</span>
        <input class="upd-input" id="uf_datereg" value="${s.datereg}" placeholder="e.g. March 2024"/>
      </div>
    </div>
    <div class="sec-title">// Personal Information</div>
    <div class="upd-grid">
      <div class="upd-field" style="grid-column:1/-1"><span class="upd-label">Full Name *</span>
        <input class="upd-input" id="uf_name" value="${s.name}" placeholder="Juan Dela Cruz"/>
      </div>
      <div class="upd-field"><span class="upd-label">Student ID</span>
        <input class="upd-input" id="uf_sid" value="${s.sid}" placeholder="e.g. 2021-00123"/>
      </div>
      <div class="upd-field"><span class="upd-label">Contact Number</span>
        <input class="upd-input" id="uf_contact" value="${s.contact}" placeholder="09XX-XXX-XXXX"/>
      </div>
      <div class="upd-field" style="grid-column:1/-1"><span class="upd-label">Email Address</span>
        <input class="upd-input" id="uf_email" value="${s.email}" placeholder="juan@cvsu.edu.ph"/>
      </div>
    </div>
    <div class="sec-title">// Academic Information</div>
    <div class="upd-grid">
      <div class="upd-field" style="grid-column:1/-1"><span class="upd-label">Course / Program *</span>
        <select class="upd-input" id="uf_course" style="appearance:none;"><option value="">- Select -</option>${courseOpts}</select>
      </div>
      <div class="upd-field"><span class="upd-label">Year Level *</span>
        <select class="upd-input" id="uf_year" style="appearance:none;"><option value="">- Select -</option>${yearOpts}</select>
      </div>
      <div class="upd-field"><span class="upd-label">Section *</span>
        <select class="upd-input" id="uf_section" style="appearance:none;"><option value="">- Select -</option>${secOpts}</select>
      </div>
      <div class="upd-field"><span class="upd-label">Major / Specialization</span>
        <input class="upd-input" id="uf_major" value="${s.major==='N/A'?'':s.major}" placeholder="e.g. Software Engineering"/>
      </div>
      <div class="upd-field"><span class="upd-label">Class Adviser *</span>
        <input class="upd-input" id="uf_adviser" value="${s.adviser}" placeholder="Prof. Santos"/>
      </div>
    </div>
    <div class="sec-title">// NFC Card (Cannot be changed)</div>
    <div class="upd-grid g1">
      <div class="upd-field"><span class="upd-label">NFC Card UID</span>
        <input class="upd-input" value="${s.nfc}" readonly style="font-family:'Space Mono',monospace;font-size:12px;"/>
      </div>
    </div>`;

  // Reset sessions tab
  document.getElementById('sessLogWrap').innerHTML =
    `<div style="text-align:center;color:var(--muted);padding:24px;font-size:12px;">Switch to this tab to load session history.</div>`;
  document.getElementById('sessCountLabel').textContent = '';
  document.getElementById('sessSubject').innerHTML = '<option value="">All Subjects</option>';
  const classTypeSel = document.getElementById('sessClassType');
  if (classTypeSel) classTypeSel.value = '';

  // Show sessions tab for students
  if (document.getElementById('mtab_action')) document.getElementById('mtab_action').style.display='';
  document.querySelectorAll('.mtab')[2].style.display='';
  document.getElementById('mpane-sessions').style.display='';
  document.getElementById('mpane-action').style.display='';

  const canDelete = CURRENT_ROLE === 'super_admin' || CURRENT_ROLE === 'admin';
  document.getElementById('actionContent').innerHTML = canDelete
    ? `<div style="border:1px dashed rgba(239,68,68,.35);border-radius:12px;padding:16px;background:rgba(239,68,68,.06);">
        <div style="font-size:14px;font-weight:700;color:var(--danger);margin-bottom:8px;"><i class="bi bi-exclamation-triangle"></i> Danger Zone</div>
        <p style="font-size:12px;color:var(--muted);margin:0 0 12px;">Deleting this student permanently removes all their attendance records and enrollment data.</p>
        <button class="btn-rst" style="border-color:var(--danger);color:var(--danger);background:#fff;" onclick="deleteStudent('${s.nfc}','${(s.name || '').replace(/'/g, "\\'")}')">
          <i class="bi bi-trash"></i> Delete Student
        </button>
      </div>`
    : '<div style="font-size:12px;color:var(--muted);">No actions available for this student.</div>';

  // Reset to Info tab
  document.querySelectorAll('.mpane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.mtab').forEach(b=>b.classList.remove('active'));
  document.getElementById('mpane-info').classList.add('active');
  document.querySelectorAll('.mtab')[0].classList.add('active');

  openUpdModal();
}

function infoRow(label, val, full=false){
  const v = val||'-';
  return `<div class="info-card-field${full?' full':''}">
    <span class="info-card-label">${label}</span>
    <span class="info-card-value">${v}</span>
  </div>`;
}

function formatDateMonthDayYear(input) {
  if (!input) return '-';
  const raw = String(input).trim();
  if (!raw) return '-';
  try {
    const normalized = raw
      .replace(' ', 'T')
      .replace(/\.(\d{3})\d+/, '.$1');
    let d = new Date(normalized);
    if (Number.isNaN(d.getTime())) {
      d = new Date(raw);
    }
    if (Number.isNaN(d.getTime()) && /^\d{4}-\d{2}-\d{2}/.test(raw)) {
      const dateOnly = raw.slice(0, 10);
      const [y, m, day] = dateOnly.split('-').map(Number);
      d = new Date(y, (m || 1) - 1, day || 1);
    }
    if (Number.isNaN(d.getTime())) return '-';
    return d.toLocaleDateString('en-US', { month: 'long', day: '2-digit', year: 'numeric' }).replace(',', '');
  } catch (e) {
    return '-';
  }
}

function pickSessionDate(sessionObj) {
  if (!sessionObj) return '-';
  const candidates = [sessionObj.started_at, sessionObj.date, sessionObj.tap_time];
  for (const c of candidates) {
    const out = formatDateMonthDayYear(c || '');
    if (out !== '-') return out;
  }
  return '-';
}

function toAmPm(input) {
  if (!input) return '-';
  const raw = String(input).trim();
  if (/\b(am|pm)\b/i.test(raw)) return raw.toUpperCase();
  const m = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return raw;
  const h = Number(m[1]);
  const min = m[2];
  const sec = m[3] ? `:${m[3]}` : '';
  const period = h >= 12 ? 'PM' : 'AM';
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh}:${min}${sec} ${period}`;
}

function formatTimeSlot(slot) {
  if (!slot) return '-';
  const raw = String(slot).trim();
  if (!raw) return '-';
  if (/[A-Za-z]+-\d{2}-\d{4}/.test(raw)) return '-';
  if (/\b(am|pm)\b/i.test(raw)) return raw.toUpperCase();
  if (/^\d{4}-\d{2}-\d{2}[ T]/.test(raw)) {
    const d = new Date(raw.replace(' ', 'T').replace(/\.(\d{3})\d+/, '.$1'));
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    }
  }
  const parts = raw.split(/\s*[\-–]\s*/);
  if (parts.length === 2) return `${toAmPm(parts[0])} - ${toAmPm(parts[1])}`;
  return toAmPm(raw);
}

function copyText(text) {
  if (!text) return Promise.resolve(false);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
  }
  const tmp = document.createElement('textarea');
  tmp.value = text;
  tmp.setAttribute('readonly', '');
  tmp.style.position = 'fixed';
  tmp.style.opacity = '0';
  document.body.appendChild(tmp);
  tmp.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(tmp);
  return Promise.resolve(ok);
}

function bindTxCopyButtons(scopeEl) {
  if (!scopeEl) return;
  scopeEl.querySelectorAll('.att-tx-copy').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      copyText(btn.dataset.tx || '').then((ok) => {
        btn.title = ok ? 'Copied' : 'Copy failed';
        btn.classList.add(ok ? 'copied' : 'copy-failed');
        setTimeout(() => {
          btn.title = 'Copy to clipboard';
          btn.classList.remove('copied', 'copy-failed');
        }, 1100);
      });
    });
  });
}

function renderSessions(sessions){
  const wrap  = document.getElementById('sessLogWrap');
  const label = document.getElementById('sessCountLabel');
  if(label) label.textContent = `${sessions.length} session${sessions.length!==1?'s':''} found`;
  if(!sessions.length){
    wrap.innerHTML = '<div style="text-align:center;color:var(--muted);padding:24px;font-size:12px;"><i class="bi bi-calendar-x" style="font-size:24px;display:block;opacity:.2;margin-bottom:6px;"></i>No sessions found.</div>';
    return;
  }
  
  const bySem = {};
  sessions.forEach(s => {
    const sem = s.semester || '1st Year 1st Sem';
    if (!bySem[sem]) bySem[sem] = [];
    bySem[sem].push(s);
  });

  const SEM_ORDER = [
    '1st Year 1st Sem', '1st Year 2nd Sem', '1st Year Summer',
    '2nd Year 1st Sem', '2nd Year 2nd Sem', '2nd Year Summer',
    '3rd Year 1st Sem', '3rd Year 2nd Sem', '3rd Year Summer',
    '4th Year 1st Sem', '4th Year 2nd Sem', '4th Year Summer'
  ];

  const sortedSems = Object.keys(bySem).sort((a, b) => {
    let ia = SEM_ORDER.indexOf(a);
    let ib = SEM_ORDER.indexOf(b);
    if (ia === -1) ia = 99;
    if (ib === -1) ib = 99;
    if (ia !== ib) return ia - ib;
    return a.localeCompare(b);
  });

  let html = '';
  sortedSems.forEach((sem, sIdx) => {
    const semSessions = bySem[sem];
    html += `
      <div class="sem-accordion" style="margin-bottom: 10px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface);">
        <div class="sem-accordion-header" style="padding: 12px 16px; background: rgba(45,106,39,.05); display: flex; justify-content: space-between; align-items: center; font-weight: 600;">
          <div style="cursor: pointer; flex: 1;" onclick="const b=this.parentElement.nextElementSibling; const i=this.querySelector('i'); if(b.style.display==='none'){b.style.display='block';i.classList.replace('bi-chevron-down','bi-chevron-up');}else{b.style.display='none';i.classList.replace('bi-chevron-up','bi-chevron-down');}">
            <span>${sem} <span style="font-size: 11px; font-weight: 400; color: var(--muted); margin-left: 8px;">(${semSessions.length} sessions)</span></span>
            <i class="bi bi-chevron-${sIdx === 0 ? 'up' : 'down'}" style="margin-left: 8px;"></i>
          </div>
          <button class="btn-success-custom" style="padding: 6px 12px; font-size: 11px; margin-left: 12px; font-family: 'DM Sans', sans-serif;" onclick="exportStudentSemester('${sem}')">
            <i class="bi bi-file-earmark-excel"></i> Export Semester
          </button>
        </div>
        <div class="sem-accordion-body" style="display: ${sIdx === 0 ? 'block' : 'none'}; padding: 0; overflow-x: auto;">
          <table class="sess-table" style="margin: 0; border: none; border-radius: 0; width: 100%; min-width: 800px;">
            <thead>
              <tr>
                <th>Course Code</th>
                <th>Subject Name</th>
                <th>Class Type</th>
                <th>Instructor Name</th>
                <th>Date</th>
                <th>Time Slot</th>
                <th>Tapped Time</th>
                <th>Transaction Number (TX)</th>
                <th>Block Number</th>
                <th>Status</th>
                <th>Excused Reason</th>
                <th>Document</th>
              </tr>
            </thead>
            <tbody>
              ${semSessions.map((s) => {
                const sbClass = `sb-${s.status}`;
                const statusLabel = s.status ? s.status.charAt(0).toUpperCase() + s.status.slice(1) : '-';
                const classType = String(s.class_type || 'lecture').toLowerCase();
                const classTypeLabel = classType === 'laboratory' ? 'Laboratory' : 'Lecture';
                const doc = s.attachment_url
                  ? `<a href="${s.attachment_url}" target="_blank" class="sess-doc-link"><i class="bi bi-paperclip"></i> View</a>`
                  : '<span class="muted-dash">-</span>';
                const reason = s.status === 'excused' && s.excuse_note
                  ? `<span style="color:#60a5fa;font-weight:600;">${s.excuse_note}</span>`
                  : '<span class="muted-dash">-</span>';
                const tx = s.tx_hash
                  ? `<a href="https://sepolia.etherscan.io/tx/${s.tx_hash}" target="_blank" title="View on Etherscan" style="font-size:11px; font-family:'Space Mono',monospace; color:var(--accent); text-decoration:none; word-break: break-all;">${s.tx_hash.slice(0, 16)}...</a>`
                  : '<span class="muted-dash">-</span>';
                return `<tr>
                  <td>${s.course_code ? `<span class="hist-code">${s.course_code}</span>` : '<span class="muted-dash">-</span>'}</td>
                  <td style="font-weight:600;">${s.subject_name || '-'}</td>
                  <td><span class="status-badge ${classType === 'laboratory' ? 'sb-excused' : 'sb-present'}">${classTypeLabel}</span></td>
                  <td>${s.teacher_name || '-'}</td>
                  <td style="font-family:'Space Mono',monospace;font-size:11px;">${pickSessionDate(s)}</td>
                  <td style="font-size:11px;color:var(--muted);">${formatTimeSlot(s.time_slot || s.tap_time || '')}</td>
                  <td style="font-family:'Space Mono',monospace;font-size:11px;white-space:nowrap;">${s.tap_time ? toAmPm(s.tap_time.split(' ')[1]||s.tap_time) : '—'}</td>
                  <td>${tx}</td>
                  <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${s.block || '-'}</td>
                  <td><span class="status-badge ${sbClass}">${statusLabel}</span></td>
                  <td>${reason}</td>
                  <td>${doc}</td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  });
  wrap.innerHTML = html;
  bindTxCopyButtons(wrap);
}

function filterSessions(){
  const q    = (document.getElementById('sessSearch').value||'').toLowerCase();
  const st   = document.getElementById('sessStatus').value;
  const subj = document.getElementById('sessSubject').value;
  const classType = document.getElementById('sessClassType').value;
  const filtered = allSessions.filter(s=>
    (!q    || s.subject_name.toLowerCase().includes(q) || (s.teacher_name||'').toLowerCase().includes(q)) &&
    (!st   || s.status === st) &&
    (!subj || s.subject_name === subj) &&
    (!classType || (String(s.class_type || 'lecture').toLowerCase() === classType))
  );
  renderSessions(filtered);
}

function resetSessFilters(){
  document.getElementById('sessSearch').value='';
  document.getElementById('sessStatus').value='';
  document.getElementById('sessSubject').value='';
  document.getElementById('sessClassType').value='';
  renderSessions(allSessions);
}

function exportStudentSemester(sem){
  const s = studentData.find(x=>x.nfc===curId);
  if(!s) return;
  const nameParts = s.name.split(' ');
  const lastName  = (nameParts[nameParts.length-1]||'student').toLowerCase().replace(/[^a-z0-9]/g,'');
  const firstName = (nameParts[0]||'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const now = new Date();
  const fname = `${lastName}_${firstName}_${sem.replace(/[^a-z0-9]/gi, '_')}_${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}.xlsx`;
  const q    = document.getElementById('sessStatus').value;
  const subj = document.getElementById('sessSubject').value;
  const classType = document.getElementById('sessClassType').value;
  let url = `/export/student_sessions/${s.nfc}?name=${encodeURIComponent(s.name)}&semester=${encodeURIComponent(sem)}&filename=${encodeURIComponent(fname)}`;
  if(q)    url += `&status=${encodeURIComponent(q)}`;
  if(subj) url += `&subject=${encodeURIComponent(subj)}`;
  if(classType) url += `&class_type=${encodeURIComponent(classType)}`;
  window.location.href = url;
}


// Section grid helpers (mirrors admin_users.html)
const DASH_CS_YEARS = ['1st Year','2nd Year','3rd Year','4th Year'];
const DASH_IT_YEARS = ['1st Year','2nd Year','3rd Year','4th Year'];
const DASH_SECS     = ['A','B','C','D'];

function buildSectionGrid(assignedSections) {
  const assigned = new Set(assignedSections || []);
  function courseBlock(course, prefix, years) {
    const rows = years.map(yr => {
      const checks = DASH_SECS.map(sec => {
        const val = course + '|' + yr + '|' + sec;
        const id  = 'dash_sec_' + prefix + '_' + yr.replace(/ /g,'') + '_' + sec;
        const chk = assigned.has(val) ? 'checked' : '';
        return '<div class="sec-cb-wrap">'
          + '<input type="checkbox" id="' + id + '" class="dash-sec-cb" value="' + val + '" ' + chk + '/>'
          + '<label for="' + id + '">' + sec + '</label>'
          + '</div>';
      }).join('');
      return '<div class="year-row"><span class="year-label">' + yr + '</span>'
           + '<div class="sec-checks">' + checks + '</div></div>';
    }).join('');
    return '<div class="section-course-block">'
      + '<div class="section-course-header"><span class="section-course-title">' + course + '</span>'
      + '<button type="button" class="btn-select-all" onclick="dashToggleAllSections(\'' + prefix + '\',this)">Select All</button></div>'
      + rows + '</div>';
  }
  return courseBlock('BS Computer Science','cs',DASH_CS_YEARS)
       + courseBlock('BS Information Technology','it',DASH_IT_YEARS);
}

function dashToggleAllSections(prefix, btn) {
  const course = prefix === 'cs' ? 'BS Computer Science' : 'BS Information Technology';
  const cbs = document.querySelectorAll('.dash-sec-cb[value^="' + course + '"]');
  const allChk = [...cbs].every(c => c.checked);
  cbs.forEach(c => c.checked = !allChk);
  btn.textContent = allChk ? 'Select All' : 'Deselect All';
}

function getSelectedSections() {
  return [...document.querySelectorAll('.dash-sec-cb:checked')].map(c => c.value);
}

// FIX 3: Teacher record - info pane uses buildSectionAccordion() from base.html
function openTeacherRecord(username){
  const u=teacherData[username];
  if(!u) return;
  curMode='teacher'; curId=username;

  document.getElementById('updTitle').textContent = u.name;
  document.getElementById('updSub').textContent   = u.role.charAt(0).toUpperCase()+u.role.slice(1)+' | '+u.status;

  // INFO TAB: use accordion (buildSectionAccordion is defined in base.html)
  const secAccordion = (u.sections && u.sections.length)
    ? buildSectionAccordion(u.sections)
    : '<span style="color:var(--muted);font-size:12px;">No sections assigned</span>';

  // Also used in edit tab as chip spans (read-only display in edit tab header)
  const secChips = (u.sections && u.sections.length)
    ? u.sections.map(s=>`<span style="background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.15);border-radius:5px;padding:2px 8px;font-size:11px;font-family:'Space Mono',monospace;color:var(--accent);display:inline-block;margin:2px;">${s.replace(/\|/g,' > ')}</span>`).join('')
    : '<span style="color:var(--muted);font-size:12px;">No sections assigned</span>';

  const tPhotoHtml = u.photo
    ? `<img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);" id="infoPhotoWrap"/>`
    : `<div id="infoPhotoWrap" style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:#000;">${u.name[0].toUpperCase()}</div>`;

  document.getElementById('infoContent').innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:18px;padding:4px 0 12px;border-bottom:1px solid var(--border);flex-wrap:wrap;">
      ${tPhotoHtml}
      <div>
        <div style="font-size:16px;font-weight:700;">${u.name}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:3px;"><code>@${u.username}</code></div>
        <div style="font-size:10px;color:rgba(45,106,39,.5);margin-top:5px;"><i class="bi bi-pencil-square"></i> Go to Update tab to change photo or sections</div>
      </div>
    </div>
    <div class="info-card-grid">
      ${infoRow('Full Name', u.name)}
      ${infoRow('Username', '@'+u.username)}
      ${infoRow('Email Address', u.email||'-', true)}
      ${infoRow('Role', u.role.charAt(0).toUpperCase()+u.role.slice(1))}
      ${infoRow('Account Status', u.status.charAt(0).toUpperCase()+u.status.slice(1))}
      ${infoRow('Registered', u.created||'-')}
    </div>
    <div class="sec-title">// Assigned Sections</div>
    <div style="padding:4px 0;">${secAccordion}</div>`;

  const roleOpts   = ['teacher','admin'].map(v=>`<option value="${v}" ${u.role===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const statusOpts = ['approved','pending','rejected'].map(v=>`<option value="${v}" ${u.status===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const canChangeRole = CURRENT_ROLE === 'super_admin';

  const tEditPhotoInner = u.photo
    ? `<img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;"/>`
    : `<span style="font-size:22px;font-weight:700;color:#000;">${u.name[0].toUpperCase()}</span>`;

  document.getElementById('editContent').innerHTML = `
    <div class="photo-upload-block">
      <div class="photo-avatar-preview" id="editPhotoPreview" onclick="document.getElementById('updPhotoInput').click()" title="Click to change photo">${tEditPhotoInner}</div>
      <div>
        <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"><i class="bi bi-camera-fill"></i> Profile Photo</div>
        <button type="button" onclick="document.getElementById('updPhotoInput').click()" style="background:rgba(45,106,39,.1);border:1px solid rgba(45,106,39,.2);color:var(--accent);border-radius:7px;padding:7px 14px;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-family:'DM Sans',sans-serif;font-weight:600;">
          <i class="bi bi-upload"></i> Change Photo
        </button>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">JPG, PNG, WEBP | Max 5 MB</div>
      </div>
    </div>
    <div class="sec-title">// Account Information</div>
    <div class="upd-grid">
      <div class="upd-field" style="grid-column:1/-1"><span class="upd-label">Full Name *</span>
        <input class="upd-input" id="tf_name" value="${u.name}"/>
      </div>
      <div class="upd-field"><span class="upd-label">Username *</span>
        <input class="upd-input" id="tf_username" value="${u.username}"/>
      </div>
      <div class="upd-field"><span class="upd-label">Email Address</span>
        <input class="upd-input" id="tf_email" value="${u.email||''}"/>
      </div>
      <div class="upd-field"><span class="upd-label">Role</span>
        ${canChangeRole
          ? `<select class="upd-input" id="tf_role" style="appearance:none;">${roleOpts}</select>`
          : `<input class="upd-input" id="tf_role" value="${u.role.charAt(0).toUpperCase()+u.role.slice(1)}" readonly/>`
        }
      </div>
      <div class="upd-field"><span class="upd-label">Account Status</span>
        <input class="upd-input" id="tf_status" value="${u.status.charAt(0).toUpperCase()+u.status.slice(1)}" readonly/>
      </div>
      <div class="upd-field"><span class="upd-label">Registered</span>
        <input class="upd-input" value="${u.created||'-'}" readonly/>
      </div>
    </div>
    <div class="sec-title">// Change Password <span style="color:var(--muted);font-size:9px;font-family:inherit;text-transform:none;letter-spacing:0;">(leave blank to keep current)</span></div>
    <div class="upd-grid">
      <div class="upd-field"><span class="upd-label">New Password</span>
        <input class="upd-input" id="tf_pw" type="password" placeholder="Min. 6 characters"/>
      </div>
      <div class="upd-field"><span class="upd-label">Confirm Password</span>
        <input class="upd-input" id="tf_pw2" type="password" placeholder="Repeat new password"/>
      </div>
    </div>
    <div id="tf_pw_err" style="font-size:11px;color:var(--danger);display:none;margin-top:4px;"><i class="bi bi-exclamation-circle"></i> Passwords do not match.</div>
    <div class="sec-title">// Assigned Sections</div>
    <p style="font-size:12px;color:var(--muted);margin-bottom:10px;">Select which sections this faculty member handles.</p>
    <div id="dashSectionGrid">${buildSectionGrid(u.sections || [])}</div>`;

  // Hide sessions tab for teachers
  document.getElementById('mtab_action').style.display='';
  document.querySelectorAll('.mtab')[2].style.display='none';
  document.getElementById('mpane-sessions').style.display='none';
  document.getElementById('mpane-action').style.display='';

  const canDelete = CURRENT_ROLE === 'super_admin' || CURRENT_ROLE === 'admin';
  const canDeleteThisUser = canDelete && username !== CURRENT_USERNAME && username !== 'admin';
  document.getElementById('actionContent').innerHTML = canDeleteThisUser
    ? `<div style="border:1px dashed rgba(239,68,68,.35);border-radius:12px;padding:16px;background:rgba(239,68,68,.06);">
        <div style="font-size:14px;font-weight:700;color:var(--danger);margin-bottom:8px;"><i class="bi bi-exclamation-triangle"></i> Danger Zone</div>
        <p style="font-size:12px;color:var(--muted);margin:0 0 12px;">Deleting this account permanently removes faculty access.</p>
        <button class="btn-rst" style="border-color:var(--danger);color:var(--danger);" onclick="deleteFacultyAccount('${u.username}','${(u.name || '').replace(/'/g, "\\'")}')">
          <i class="bi bi-trash"></i> Delete Account
        </button>
      </div>`
    : '<div style="font-size:12px;color:var(--muted);">No account actions available for this user.</div>';

  // Reset to Info tab
  document.querySelectorAll('.mpane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.mtab').forEach(b=>b.classList.remove('active'));
  document.getElementById('mpane-info').classList.add('active');
  document.querySelectorAll('.mtab')[0].classList.add('active');

  openUpdModal();
}

function saveUpdate(){
  if(curMode==='student') saveStudentUpdate();
  else if(curMode==='teacher') saveTeacherUpdate();
}

function saveStudentUpdate(){
  const msg=document.getElementById('updMsg');
  const btn=document.getElementById('updSaveBtn');
  const g=id=>{const el=document.getElementById(id);return el?el.value.trim():'';};
  const payload={
    nfc_id:curId,
    full_name:g('uf_name'), student_id:g('uf_sid'),
    email:g('uf_email'), contact:g('uf_contact'),
    adviser:g('uf_adviser'), major:g('uf_major')||'N/A',
    semester:g('uf_semester'), school_year:g('uf_sy'),
    date_registered:g('uf_datereg'),
    course:g('uf_course'), year_level:g('uf_year'), section:g('uf_section'),
  };
  btn.disabled=true; btn.innerHTML='<i class="bi bi-hourglass"></i> Saving...';
  fetch('/update_student',{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  .then(r=>r.json()).then(d=>{
    msg.style.display='block';
    if(d.ok){
      msg.style.color='var(--success)'; msg.textContent='Student information updated.';
      const s=studentData.find(x=>x.nfc===curId);
      if(s){ Object.assign(s,{name:payload.full_name||s.name,sid:payload.student_id||s.sid,
        email:payload.email||s.email,contact:payload.contact||s.contact,
        adviser:payload.adviser||s.adviser,major:payload.major||s.major,
        semester:payload.semester||s.semester,sy:payload.school_year||s.sy,
        datereg:payload.date_registered||s.datereg,course:payload.course||s.course,
        year:payload.year_level||s.year,section:payload.section||s.section});
      }
      document.getElementById('updTitle').textContent = payload.full_name||curId;
      document.getElementById('updSub').textContent   = `${payload.course} | ${payload.year_level} | Section ${payload.section}`;
      const si = studentData.find(x=>x.nfc===curId);
      const nameEl = si ? document.querySelector(`#strow_${si.idx} .prow-name`) : null;
      if(nameEl) nameEl.textContent=payload.full_name;
    } else { msg.style.color='var(--danger)'; msg.textContent=d.error||'Error saving changes.'; }
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  }).catch(()=>{
    msg.style.display='block'; msg.style.color='var(--danger)'; msg.textContent='Network error.';
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  });
}

function saveTeacherUpdate(){
  const msg=document.getElementById('updMsg');
  const btn=document.getElementById('updSaveBtn');
  const pw=document.getElementById('tf_pw')?.value||'';
  const pw2=document.getElementById('tf_pw2')?.value||'';
  const pwErr=document.getElementById('tf_pw_err');
  if(pw&&pw!==pw2){if(pwErr)pwErr.style.display='block';return;}
  if(pwErr) pwErr.style.display='none';
  const g=id=>{const el=document.getElementById(id);return el?el.value.trim():'';};
  const payload={username:curId,full_name:g('tf_name'),new_username:g('tf_username'),
    email:g('tf_email'),role:(CURRENT_ROLE==='super_admin'?g('tf_role').toLowerCase():''),status:'',new_password:pw||null,
    sections:getSelectedSections()};
  btn.disabled=true; btn.innerHTML='<i class="bi bi-hourglass"></i> Saving...';
  fetch('/update_faculty',{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  .then(r=>r.json()).then(d=>{
    msg.style.display='block';
    if(d.ok){
      msg.style.color='var(--success)'; msg.textContent='Faculty record updated.';
      const u=teacherData[curId];
      if(u){u.name=payload.full_name||u.name;u.email=payload.email||u.email;
        u.role=payload.role||u.role;u.status=payload.status||u.status;}
      document.getElementById('updTitle').textContent=payload.full_name;
      const nameEl=document.querySelector(`#tcrow_${curId} .prow-name`);
      if(nameEl) nameEl.textContent=payload.full_name;
    } else { msg.style.color='var(--danger)'; msg.textContent=d.error||'Error.'; }
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  }).catch(()=>{
    msg.style.display='block'; msg.style.color='var(--danger)'; msg.textContent='Network error.';
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  });
}

// FIX 4: NO DOMContentLoaded guard - switchMTab handles this now
// (the old guard with allSessions.length===0 has been removed)

const totalSt=studentData.length;
function filterStudents(){
  const q=document.getElementById('st_search').value.toLowerCase();
  const crs=document.getElementById('st_course').value;
  const yr=document.getElementById('st_year').value;
  const sec=document.getElementById('st_section').value;
  const sem=document.getElementById('st_semester').value;
  let shown=0;
  document.querySelectorAll('#studentList .person-row').forEach(r=>{
    const m=(!q||r.dataset.name.includes(q)||r.dataset.id.includes(q))&&
            (!crs||r.dataset.course===crs)&&(!yr||r.dataset.year===yr)&&(!sec||r.dataset.section===sec)&&
            (!sem||r.dataset.semester.toLowerCase().includes(sem.toLowerCase()));
    r.style.display=m?'':'none'; if(m)shown++;
  });
  document.getElementById('st_count').textContent=`${shown} of ${totalSt} students`;
}
function resetStudentFilters(){
  ['st_search','st_course','st_year','st_section','st_semester'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
  filterStudents();
}

const totalTc=Object.keys(teacherData).length;
function filterTeachers(){
  const q=document.getElementById('tc_search').value.toLowerCase();
  const role=document.getElementById('tc_role').value;
  let shown=0;
  document.querySelectorAll('#facultyList .person-row').forEach(r=>{
    const m=(!q||r.dataset.name.includes(q)||r.dataset.username.includes(q))&&
            (!role||r.dataset.role===role);
    r.style.display=m?'':'none'; if(m)shown++;
  });
  document.getElementById('tc_count').textContent=`${shown} of ${totalTc} faculty`;
}
function resetTeacherFilters(){
  ['tc_search','tc_role'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
  filterTeachers();
}

async function deleteStudent(nfcId, fullName) {
  if (!nfcId) return;
  const ok = await showAppConfirm(
    `Delete all records for student ${fullName || nfcId}? This will permanently remove their attendance history and account. This action cannot be undone.`,
    'Delete Student Record',
    'Delete Permanently',
    'Cancel'
  );
  if (!ok) return;

  try {
    const r = await fetch(`/api/students/delete/${nfcId}`, { method: 'POST', credentials: 'same-origin' });
    const d = await r.json();
    if (d.success) {
      location.reload();
    } else {
      alert(d.message || 'Error deleting student.');
    }
  } catch (e) {
    alert('Network error.');
  }
}

async function deleteFacultyAccount(username, fullName) {
  if (!username) return;
  const ok = await showAppConfirm(
    `Delete account for ${fullName || username}? This cannot be undone.`,
    'Delete Faculty Account',
    'Delete',
    'Cancel'
  );
  if (!ok) return;
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/admin/users/${encodeURIComponent(username)}/delete`;
  document.body.appendChild(form);
  form.submit();
}

function applyInitialDashboardTab() {
  const params = new URLSearchParams(window.location.search || '');
  const tab = String(params.get('tab') || '').toLowerCase();
  if (tab !== 'faculty') return;
  const facultyBtn = Array.from(document.querySelectorAll('.tab-btn')).find((b) =>
    String(b.textContent || '').toLowerCase().includes('faculty')
  );
  if (facultyBtn) switchTab('faculty', facultyBtn);
}

applyInitialDashboardTab();

fetch('/api/block_number').then(r=>r.json()).then(d=>{if(d.block!==undefined)document.getElementById('blockNum').textContent=d.block;}).catch(()=>{});
