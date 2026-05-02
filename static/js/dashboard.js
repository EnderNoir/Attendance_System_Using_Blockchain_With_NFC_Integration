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
    status: s.student_status || 'active',
    enrollment: s.enrollment_status || 'Regular',
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
let currentEditStudent = null;

// Status Management
function openStatusModal(nfcId, studentName, currentStatus) {
  currentEditStudent = { nfcId, studentName, currentStatus };
  const nameEl = document.getElementById('statusModalStudent');
  if (nameEl) nameEl.textContent = studentName;
  const sel = document.getElementById('statusSelect');
  if (sel) sel.value = currentStatus || 'active';
  const modal = document.getElementById('statusModal');
  if (modal) modal.classList.add('show');
}
function closeStatusModal() {
  const modal = document.getElementById('statusModal');
  if (modal) modal.classList.remove('show');
  currentEditStudent = null;
}
async function confirmStatusChange() {
  if (!currentEditStudent) return;
  const newStatus = document.getElementById('statusSelect').value;
  const btn = event.target;
  const oldText = btn.textContent;
  btn.disabled = true; btn.textContent = 'Updating...';
  try {
    const response = await fetch(`/api/student/update-status/${currentEditStudent.nfcId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    closeStatusModal();
    location.reload();
  } catch (error) {
    console.error('Failed to update status:', error);
    alert('Update failed: ' + error.message);
  } finally {
    btn.disabled = false; btn.textContent = oldText;
  }
}

// Semester Management
function openMoveSemesterModal(nfcId, studentName, currentSem, currentYear) {
  currentEditStudent = { nfcId, studentName, currentSem, currentYear };
  const nameEl = document.getElementById('semesterModalStudent');
  if (nameEl) nameEl.textContent = studentName;
  const curSemSel = document.getElementById('currentSemesterSelect');
  if (curSemSel) curSemSel.value = currentSem || 'First';
  const semOptions = ['First', 'Second', 'Summer'];
  const currentIdx = semOptions.indexOf(currentSem);
  const nextIdx = (currentIdx + 1) % semOptions.length;
  const newSemSel = document.getElementById('newSemesterSelect');
  if (newSemSel) newSemSel.value = semOptions[nextIdx];
  if (currentYear && currentYear !== 'N/A') {
    const [start, end] = currentYear.split('-');
    if (start && end) {
      const yrInp = document.getElementById('newSchoolYear');
      if (yrInp) yrInp.value = end + '-' + (parseInt(end) + 1);
    }
  }
  
  // Update modal title and button for SINGLE move
  document.querySelector('#semesterModal h3').textContent = 'Move to Next Semester';
  const btn = document.querySelector('#semesterModal .btn-primary');
  btn.textContent = 'Move Student';
  btn.onclick = confirmStudentSemesterChange;
  
  const modal = document.getElementById('semesterModal');
  if (modal) modal.classList.add('show');
}
function closeSemesterModal() {
  const modal = document.getElementById('semesterModal');
  if (modal) modal.classList.remove('show');
  currentEditStudent = null;
}
async function confirmStudentSemesterChange() {
  if (!currentEditStudent) return;
  const newSem = document.getElementById('newSemesterSelect').value;
  const newYear = document.getElementById('newSchoolYear').value;
  if (!newYear || !newYear.match(/^\d{4}-\d{4}$/)) {
    alert('Please enter a valid school year (e.g. 2024-2025)');
    return;
  }
  const btn = event.target;
  const oldText = btn.textContent;
  btn.disabled = true; btn.textContent = 'Moving...';
  try {
    const response = await fetch(`/api/student/move-semester/${currentEditStudent.nfcId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_semester: newSem, new_school_year: newYear })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    closeSemesterModal();
    location.reload();
  } catch (error) {
    console.error('Failed to move semester:', error);
    alert('Move failed: ' + error.message);
  } finally {
    btn.disabled = false; btn.textContent = oldText;
  }
}

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
  
  // Reset NFC Capture state
  vsNfcActive = false;

  document.getElementById('updTitle').textContent = s.name;
  document.getElementById('updSub').textContent   = (s.course||'-')+' | '+(s.year||'-')+' | Section '+(s.section||'-');

  const photoHtml = s.photo
    ? `<div style="position:relative; width:72px; height:72px; flex-shrink:0;">
         <img src="/static/uploads/${s.photo}?t=${Date.now()}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:2px solid var(--accent);cursor:pointer;" id="infoPhotoWrap" onclick="window.open('/static/uploads/${s.photo}', '_blank')" onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<div style=\'width:72px;height:72px;border-radius:50%;background:var(--bg-secondary);display:flex;align-items:center;justify-content:center;\'><i class=\'bi bi-person\' style=\'font-size:32px;color:var(--muted);\'></i></div>';"/>
         <div onclick="window.open('/static/uploads/${s.photo}', '_blank')" style="position:absolute; bottom:0; right:0; width:22px; height:22px; background:var(--accent); border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 5px rgba(0,0,0,0.3); border:2px solid var(--bg-body);" title="View full photo">
           <i class="bi bi-zoom-in" style="color:#000; font-size:11px;"></i>
         </div>
       </div>`
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
      ${infoRow('Date of Admission', formatDateMonthDayYear(s.datereg))}
      ${infoRow('Year Level', s.year)}
      ${infoRow('Section', s.section)}
      ${infoRow('Enrollment Type', s.enrollment)}
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
    ? `<img src="/static/uploads/${s.photo}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<i class=\'bi bi-person\' style=\'font-size:24px;color:var(--muted);\'></i>';"/>`
    : `<span style="font-size:22px;font-weight:700;color:#000;">${s.name[0].toUpperCase()}</span>`;

    const teacherOpts = Object.values(teacherData).map(t => 
      `<option value="${t.name}" ${s.adviser === t.name ? 'selected' : ''}>${t.name}</option>`
    ).join('');

    const nameParts = s.name.split(' ');
    let firstName = '', middleInitial = '', lastName = '';
    
    if (nameParts.length >= 3) {
      lastName = nameParts[nameParts.length - 1];
      middleInitial = nameParts[nameParts.length - 2];
      firstName = nameParts.slice(0, -2).join(' ');
    } else if (nameParts.length === 2) {
      lastName = nameParts[1];
      firstName = nameParts[0];
    } else {
      firstName = s.name;
    }

  document.getElementById('editContent').innerHTML = `
    <div class="photo-upload-block">
      <div style="position:relative; display:inline-block;">
        <div class="photo-avatar-preview" id="editPhotoPreview" onclick="document.getElementById('updPhotoInput').click()" title="Click to change photo">${editPhotoInner}</div>
        ${s.photo ? `<div onclick="window.open('/static/uploads/${s.photo}', '_blank')" style="position:absolute; bottom:0; right:0; width:22px; height:22px; background:var(--accent); border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 5px rgba(0,0,0,0.3); border:2px solid var(--bg-body);" title="View full photo"><i class="bi bi-zoom-in" style="color:#000; font-size:11px;"></i></div>` : ''}
      </div>
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
        <input class="upd-input" id="uf_datereg" type="date" value="${s.datereg}"/>
      </div>
    </div>
    <div class="sec-title">// Personal Information</div>
    <div class="upd-grid">
      <div class="upd-field"><span class="upd-label">First Name *</span>
        <input class="upd-input" id="uf_fname" value="${firstName}" placeholder="Juan"/>
      </div>
      <div class="upd-field"><span class="upd-label">Middle Initial</span>
        <input class="upd-input" id="uf_mi" value="${middleInitial}" placeholder="D." maxlength="2"/>
      </div>
      <div class="upd-field"><span class="upd-label">Last Name *</span>
        <input class="upd-input" id="uf_lname" value="${lastName}" placeholder="Dela Cruz"/>
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
        <select class="upd-input" id="uf_adviser" style="appearance:none;">
          <option value="">- Select Teacher -</option>
          ${teacherOpts}
        </select>
      </div>
    </div>
    <div class="sec-title">// Account & Status</div>
    <div class="upd-grid">
      <div class="upd-field"><span class="upd-label">Enrollment Type</span>
        <select class="upd-input" id="uf_enrollment" style="appearance:none;">
          <option value="Regular" ${s.enrollment==='Regular'?'selected':''}>Regular</option>
          <option value="Irregular" ${s.enrollment==='Irregular'?'selected':''}>Irregular</option>
        </select>
      </div>
    </div>
    <div class="sec-title">// NFC Card</div>
    <div class="upd-grid g1">
      <div class="upd-field">
        <span class="upd-label">NFC Card UID</span>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="upd-input" id="uf_nfc_display" value="${s.nfc}" readonly style="font-family:'Space Mono',monospace;font-size:12px;flex:1;background:rgba(255,255,255,.05);"/>
          <button type="button" id="btnShowNfcCapture" onclick="toggleNfcCapture()" style="padding:8px 12px;background:var(--accent);color:#000;border:none;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer;">Change UID</button>
        </div>
        <input type="hidden" id="vsNewNfcId" value=""/>
      </div>
    </div>
    
    <!-- NFC Capture Container (Hidden by default) -->
    <div id="nfcCaptureContainer" style="display:none;margin-top:16px;padding:16px;background:rgba(255,255,255,.03);border:1px dashed var(--accent);border-radius:12px;text-align:center;">
      <div id="vsNfcIcon" style="font-size:32px;margin-bottom:8px;">💳</div>
      <div id="vsNfcTitle" style="font-size:14px;font-weight:700;margin-bottom:4px;">Tap NFC card on the reader</div>
      <div id="vsNfcSub" style="font-size:11px;color:var(--muted);margin-bottom:12px;">Hold the card near the reader — the UID will appear automatically</div>
      <div id="vsNfcUidDisplay" style="font-family:'Space Mono',monospace;font-size:16px;font-weight:700;color:var(--muted);padding:8px;background:rgba(0,0,0,.2);border-radius:6px;margin-bottom:12px;">No card tapped yet</div>
      <button type="button" onclick="startPhoneNFC()" style="width:100%;padding:10px;background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text);border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;">
        <i class="bi bi-phone"></i> Use Phone's NFC
      </button>
    </div>
    `;

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

function formatFullDateTime(raw) {
  if (!raw || raw === '-') return '-';
  try {
    const normalized = raw.replace(' ', 'T');
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return raw;
    const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    const m = months[d.getMonth()];
    const day = d.getDate();
    const yr = d.getFullYear();
    let h = d.getHours();
    const min = String(d.getMinutes()).padStart(2, '0');
    const ampm = h >= 12 ? 'pm' : 'am';
    h = h % 12 || 12;
    return `${m} ${day} ${yr} ${h}:${min}${ampm}`;
  } catch (e) { return raw; }
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
                <th>Enrollment Type</th>
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
                  <td style="font-family:'Space Mono',monospace;font-size:11px;white-space:nowrap;">${(s.status === 'absent' || s.status === 'excused') ? '—' : (s.tap_time ? toAmPm(s.tap_time.split(' ')[1]||s.tap_time) : '—')}</td>
                  <td>${tx}</td>
                  <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${s.block || '-'}</td>
                  <td><span style="font-size:10px; font-weight:700; color:${(s.enrollment_status||'Regular')==='Irregular'?'var(--danger)':'var(--success)'};">${s.enrollment_status||'Regular'}</span></td>
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
  document.getElementById('updSub').textContent   = u.role.charAt(0).toUpperCase()+u.role.slice(1);

  // INFO TAB: use accordion (buildSectionAccordion is defined in base.html)
  const secAccordion = (u.sections && u.sections.length)
    ? buildSectionAccordion(u.sections)
    : '<span style="color:var(--muted);font-size:12px;">No sections assigned</span>';

  // Also used in edit tab as chip spans (read-only display in edit tab header)
  const secChips = (u.sections && u.sections.length)
    ? u.sections.map(s=>`<span style="background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.15);border-radius:5px;padding:2px 8px;font-size:11px;font-family:'Space Mono',monospace;color:var(--accent);display:inline-block;margin:2px;">${s.replace(/\|/g,' > ')}</span>`).join('')
    : '<span style="color:var(--muted);font-size:12px;">No sections assigned</span>';

  const tPhotoHtml = u.photo
    ? `<div style="position:relative; width:72px; height:72px; flex-shrink:0;">
         <img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:2px solid var(--accent);cursor:pointer;" id="infoPhotoWrap" onclick="window.open('/static/uploads/${u.photo}', '_blank')" onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<div style=\\'width:72px;height:72px;border-radius:50%;background:var(--bg-secondary);display:flex;align-items:center;justify-content:center;\\'><i class=\\'bi bi-person\\' style=\\'font-size:32px;color:var(--muted);\\'></i></div>';"/>
         <div onclick="window.open('/static/uploads/${u.photo}', '_blank')" style="position:absolute; bottom:0; right:0; width:22px; height:22px; background:var(--accent); border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 5px rgba(0,0,0,0.3); border:2px solid var(--bg-body);" title="View full photo">
           <i class="bi bi-zoom-in" style="color:#000; font-size:11px;"></i>
         </div>
       </div>`
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
      ${infoRow('Registered', formatFullDateTime(u.created))}
    </div>
    </div>`;

  const roleOpts   = ['teacher','admin'].map(v=>`<option value="${v}" ${u.role===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const statusOpts = ['approved','pending','rejected'].map(v=>`<option value="${v}" ${u.status===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const canChangeRole = CURRENT_ROLE === 'super_admin';

  const tEditPhotoInner = u.photo
    ? `<img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<i class=\'bi bi-person\' style=\'font-size:24px;color:var(--muted);\'></i>';"/>`
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
      <div class="upd-field"><span class="upd-label">Registered</span>
        <input class="upd-input" value="${formatFullDateTime(u.created)}" readonly/>
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
    </div>`;

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

async function saveStudentUpdate() {
  const g = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  const btn = document.getElementById('updSaveBtn');
  
  const fname = g('uf_fname');
  const mi = g('uf_mi');
  const lname = g('uf_lname');
  const fullName = `${fname} ${mi} ${lname}`.replace(/\s+/g, ' ').trim();

  const payload = {
    first_name: fname,
    middle_initial: mi,
    last_name: lname,
    full_name: fullName,
    student_id: g('uf_sid'),
    email: g('uf_email'),
    contact: g('uf_contact'),
    adviser: g('uf_adviser'),
    major: g('uf_major') || 'N/A',
    semester: g('uf_semester'),
    school_year: g('uf_sy'),
    date_registered: g('uf_datereg'),
    course: g('uf_course'),
    year_level: g('uf_year'),
    section: g('uf_section'),
    enrollment_status: g('uf_enrollment'),
    new_nfc_id: document.getElementById('vsNewNfcId')?.value.trim() || ''
  };

  if (!payload.first_name || !payload.last_name || !payload.course || !payload.year_level || !payload.section) {
    alert('Please fill in all required fields.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Saving...';

  try {
    const r = await fetch(`/api/student/update-profile/${curId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (d.ok) {
      showAppSuccess('Student profile updated successfully!');
      
      const studentObj = studentData.find(x => x.nfc === curId);
      if (studentObj) {
        studentObj.name = payload.full_name;
        studentObj.sid = payload.student_id;
        studentObj.course = payload.course;
        studentObj.year = payload.year_level;
        studentObj.section = payload.section;
        studentObj.enrollment = payload.enrollment_status;
        if (payload.new_nfc_id) {
          studentObj.nfc = payload.new_nfc_id;
        }

        const row = document.getElementById(`strow_${studentObj.idx}`);
        if (row) {
          row.dataset.name = studentObj.name.toLowerCase();
          row.dataset.id = studentObj.sid.toLowerCase();
          row.dataset.course = studentObj.course;
          row.dataset.year = studentObj.year;
          row.dataset.section = studentObj.section;
          row.dataset.enrollment = studentObj.enrollment;
          row.dataset.nfc = studentObj.nfc;

          const badge = row.querySelector('.status-badge') || row.querySelector('span[style*="border-radius:6px"]');
          if (badge) {
            badge.textContent = studentObj.enrollment.toUpperCase();
            if (studentObj.enrollment === 'Regular') {
              badge.style.background = 'rgba(76,175,80,0.15)';
              badge.style.color = '#4caf50';
            } else {
              badge.style.background = 'rgba(244,67,54,0.15)';
              badge.style.color = '#f44336';
            }
          }
          const nameEl = row.querySelector('.prow-name');
          if (nameEl) nameEl.textContent = studentObj.name;
        }
      }

      setTimeout(() => closeUpdModal(), 1000);
      if (typeof filterStudents === 'function') filterStudents();
      
      if (payload.new_nfc_id) curId = payload.new_nfc_id;
    } else {
      alert(d.error || 'Update failed');
    }
  } catch (e) {
    console.error(e);
    alert('Network error while saving');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Update';
  }
}

function showMsg(txt, type) {
  // Simple alert fallback for now, or use a dedicated element
  const msgEl = document.getElementById('updMsg');
  if (msgEl) {
    msgEl.textContent = txt;
    msgEl.style.display = 'block';
    msgEl.style.color = type === 'success' ? 'var(--accent)' : 'var(--danger)';
  } else {
    alert(txt);
  }
}

function saveTeacherUpdate(){
  const btn=document.getElementById('updSaveBtn');
  const pw=document.getElementById('tf_pw')?.value||'';
  const pw2=document.getElementById('tf_pw2')?.value||'';
  const pwErr=document.getElementById('tf_pw_err');
  if(pw&&pw!==pw2){if(pwErr)pwErr.style.display='block';return;}
  if(pwErr) pwErr.style.display='none';
  const g=id=>{const el=document.getElementById(id);return el?el.value.trim():'';};
  const payload={username:curId,full_name:g('tf_name'),new_username:g('tf_username'),
    email:g('tf_email'),role:(CURRENT_ROLE==='super_admin'?(g('tf_role')||'').toLowerCase():''),new_password:pw||null,
    sections:getSelectedSections()};
  btn.disabled=true; btn.innerHTML='<i class="bi bi-hourglass"></i> Saving...';
  fetch('/update_faculty',{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  .then(r=>r.json()).then(d=>{
    if(d.ok){
      showAppSuccess('Faculty record updated.');
      setTimeout(() => window.location.reload(), 500);
    } else { alert(d.error || 'Update failed'); }
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  }).catch(()=>{
    alert('Network error while saving faculty update');
    btn.disabled=false; btn.innerHTML='<i class="bi bi-check-circle-fill"></i> Update';
  });
}

// FIX 4: NO DOMContentLoaded guard - switchMTab handles this now
// (the old guard with allSessions.length===0 has been removed)

function sortStudentsAlphabetically() {
  const container = document.getElementById('studentList');
  if (!container) return;
  const rows = Array.from(container.querySelectorAll('.person-row'));
  
  rows.sort((a, b) => {
    const nameA = a.getAttribute('data-name') || '';
    const nameB = b.getAttribute('data-name') || '';
    return nameA.localeCompare(nameB);
  });
  
  rows.forEach(row => container.appendChild(row));
}

const totalSt=studentData.length;
function filterStudents(){
  const q=(document.getElementById('st_search')?.value || '').toLowerCase();
  const crs=document.getElementById('st_course')?.value;
  const yr=document.getElementById('st_year')?.value;
  const sec=document.getElementById('st_section')?.value;
  const sem=document.getElementById('st_semester')?.value;
  const status=document.getElementById('st_status')?.value;
  
  let shown=0;
  document.querySelectorAll('#studentList .person-row').forEach(r=>{
    const name = (r.dataset.name || '').toLowerCase();
    const sid = (r.dataset.id || '').toLowerCase();
    const rowCourse = r.dataset.course;
    const rowYear = r.dataset.year;
    const rowSection = r.dataset.section;
    const rowSemester = r.dataset.semester;
    const rowStatus = r.dataset.status || 'active';
    const rowEnrollment = r.dataset.enrollment || 'Regular';

    let m = true;
    if (q && !name.includes(q) && !sid.includes(q)) m = false;
    if (crs && rowCourse !== crs) m = false;
    if (yr && rowYear !== yr) m = false;
    if (sec && rowSection !== sec) m = false;
    if (sem && !rowSemester.toLowerCase().includes(sem.toLowerCase())) m = false;
    
    if (status === 'regular') {
      if (rowStatus !== 'active' || rowEnrollment !== 'Regular') m = false;
    } else if (status === 'irregular') {
      if (rowStatus !== 'active' || rowEnrollment !== 'Irregular') m = false;
    } else if (status === 'graduated_alumni') {
      if (rowStatus !== 'graduated' && rowStatus !== 'alumni') m = false;
    }

    r.style.display=m?'':'none'; if(m)shown++;
  });
  const countEl = document.getElementById('st_count');
  if (countEl) countEl.textContent=`${shown} of ${studentData.length} students`;
  updateStatistics();
}

function updateStatistics() {
  const rows = document.querySelectorAll('#studentList .person-row');
  let reg = 0, irreg = 0, grad = 0, total = 0;
  
  rows.forEach(r => {
    total++;
    const st = r.dataset.status || 'active';
    const en = r.dataset.enrollment || 'Regular';
    
    if (st === 'active') {
      if (en === 'Regular') reg++;
      else irreg++;
    } else if (st === 'graduated' || st === 'alumni') {
      grad++;
    }
  });
  
  const elReg = document.getElementById('statRegular');
  const elIrreg = document.getElementById('statIrregular');
  const elGrad = document.getElementById('statGraduatedAlumni');
  const elTotal = document.getElementById('statAll');
  
  if (elReg) elReg.textContent = reg;
  if (elIrreg) elIrreg.textContent = irreg;
  if (elGrad) elGrad.textContent = grad;
  if (elTotal) elTotal.textContent = total;
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
  closeUpdModal();
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
  closeUpdModal();
  const ok = await showAppConfirm(
    `Delete account for ${fullName || username}? This cannot be undone.`,
    'Delete Faculty Account',
    'Delete',
    'Cancel'
  );
  if (!ok) return;
  
  try {
    const r = await fetch(`/admin/users/${encodeURIComponent(username)}/delete`, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    // The backend redirects, but fetch follows it. We check if it was successful.
    if (r.ok) {
      showAppSuccess('Faculty account deleted successfully.');
      setTimeout(() => {
        window.location.href = '/dashboard?tab=faculty';
      }, 500);
    } else {
      alert('Error deleting faculty account.');
    }
  } catch (e) {
    console.error(e);
    alert('Network error.');
  }
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

// --- NFC Capture Logic for Dashboard Modal ---
let vsNfcActive = false;
function toggleNfcCapture() {
  const container = document.getElementById('nfcCaptureContainer');
  const btn = document.getElementById('btnShowNfcCapture');
  vsNfcActive = !vsNfcActive;
  
  if (vsNfcActive) {
    container.style.display = 'block';
    btn.textContent = 'Cancel Change';
    btn.style.background = 'var(--danger)';
    resetVsNfcStrip();
    refocusNfc();
  } else {
    container.style.display = 'none';
    btn.textContent = 'Change UID';
    btn.style.background = 'var(--accent)';
    document.getElementById('vsNewNfcId').value = '';
  }
}

function resetVsNfcStrip() {
  const icon = document.getElementById('vsNfcIcon');
  const title = document.getElementById('vsNfcTitle');
  const sub = document.getElementById('vsNfcSub');
  const display = document.getElementById('vsNfcUidDisplay');
  if (icon) icon.textContent = '💳';
  if (title) title.textContent = 'Tap NFC card on the reader';
  if (sub) sub.textContent = 'Hold the card near the reader — the UID will appear automatically';
  if (display) {
    display.textContent = 'No card tapped yet';
    display.style.color = 'var(--muted)';
  }
  const hid = document.getElementById('vsNewNfcId');
  if (hid) hid.value = '';
}

function applyVsNfcUid(uid) {
  if (!vsNfcActive) return;
  uid = uid.trim().toUpperCase();
  if (uid.length < 4) return;
  
  const hid = document.getElementById('vsNewNfcId');
  const icon = document.getElementById('vsNfcIcon');
  const title = document.getElementById('vsNfcTitle');
  const sub = document.getElementById('vsNfcSub');
  const display = document.getElementById('vsNfcUidDisplay');
  
  if (hid) hid.value = uid;
  if (icon) icon.textContent = '✅';
  if (title) title.textContent = 'Card Captured!';
  if (sub) sub.textContent = 'Click Update to save this new UID.';
  if (display) {
    display.textContent = uid;
    display.style.color = 'var(--success)';
  }
}

// Global NFC HID Handler for Dashboard
const nfcHid = document.getElementById('nfcHidInput');
let nfcBuf = '', nfcTimer = null;
function refocusNfc() {
  const tag = document.activeElement ? document.activeElement.tagName : '';
  if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
    const hid = document.getElementById('nfcHidInput');
    if (hid) hid.focus();
  }
}

if (nfcHid) {
  nfcHid.addEventListener('keydown', e => {
    clearTimeout(nfcTimer);
    if (e.key === 'Enter') {
      const u = nfcBuf.trim(); nfcBuf = ''; nfcHid.value = '';
      if (u) applyVsNfcUid(u);
      return;
    }
    if (e.key.length === 1) { nfcBuf += e.key; nfcHid.value = nfcBuf; }
    nfcTimer = setTimeout(() => {
      const u = nfcBuf.trim(); nfcBuf = ''; nfcHid.value = '';
      if (u) applyVsNfcUid(u);
    }, 300);
  });
  document.addEventListener('click', refocusNfc);
  nfcHid.addEventListener('blur', () => setTimeout(refocusNfc, 150));
}

// Poll for phone NFC changes if active
setInterval(() => {
  if (vsNfcActive && window.lastNfcUid) {
    applyVsNfcUid(window.lastNfcUid);
    window.lastNfcUid = null;
  }
}, 500);

// showAppSuccess moved to base.html

function moveUpAllStudents() {
  const modal = document.getElementById('semesterModal');
  if (modal) {
    modal.classList.add('show');
  }
}

function closeSemesterModal() {
  document.getElementById('semesterModal').classList.remove('show');
}

// Store pending move-up payload for the confirm modal
let _muPending = null;

function _nextSemLabel(year, sem) {
  const semMap = { First: 'Second', Second: 'First', Summer: 'First' };
  const yearMap = { '1st Year': '2nd Year', '2nd Year': '3rd Year', '3rd Year': '4th Year', '4th Year': '4th Year' };
  const nextSem = semMap[sem] || 'First';
  const bumpYear = (sem === 'Second' || sem === 'Summer');
  const nextYear = bumpYear ? (yearMap[year] || year) : year;
  return `${nextYear} — ${nextSem} Semester`;
}

function submitMoveUp() {
  const program    = document.getElementById('mu_program').value;
  const year       = document.getElementById('mu_year').value;
  const semester   = document.getElementById('mu_semester').value;
  const action     = document.querySelector('input[name="mu_action"]:checked').value;
  const enrollment = document.querySelector('input[name="mu_enrollment"]:checked').value;

  if (action === 'graduated') {
    if (year !== '4th Year' || semester !== 'Second') {
      showAppSuccess('Error: Only 4th Year 2nd Semester students can be marked as Graduated.', 'error');
      return;
    }
  }

  _muPending = { program, year_level: year, semester, action, enrollment_type: enrollment };

  // Build human-readable confirm text
  const actionLabels = {
    next_sem:   'Move to Next Sem',
    summer:     'Move to Summer Class',
    graduated:  'Mark as Graduated'
  };
  const enrollLabel = enrollment || 'All';
  const groupText   = `${program || 'All Programs'} · ${year} · ${semester} Sem · ${enrollLabel}`;

  let resultDesc = '';
  if (action === 'next_sem') {
    resultDesc = `Selected students will move from <b>${year} — ${semester}</b> to <b>${_nextSemLabel(year, semester)}</b>.`;
  } else if (action === 'summer') {
    resultDesc = `Selected students will move from <b>${year} — ${semester}</b> to <b>${year} — Summer</b>.`;
  } else if (action === 'graduated') {
    resultDesc = `Selected students will be marked as <b>Graduated / Alumni</b> and removed from active live sessions.`;
  }

  document.getElementById('muConfirmText').textContent = `You are about to apply: "${actionLabels[action]}" to the group below.`;
  document.getElementById('muConfirmDetails').innerHTML =
    `<b>Group:</b> ${groupText}<br><br>${resultDesc}<br><br><span style="color:#ef4444;">⚠ This action cannot be undone. Please double-check your selection.</span>`;

  document.getElementById('muConfirmModal').classList.add('show');
}

async function executeMoveUp() {
  const confirmModal = document.getElementById('muConfirmModal');
  const yesBtn       = document.getElementById('muConfirmYesBtn');

  yesBtn.disabled = true;
  const oldHtml   = yesBtn.innerHTML;
  yesBtn.innerHTML = '<span class="spin"></span> Processing...';

  try {
    const r = await fetch('/api/students/move-up-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_muPending)
    });
    const d = await r.json();

    confirmModal.classList.remove('show');

    if (d.ok) {
      closeSemesterModal();
      showAppSuccess(`Done! ${d.count} student${d.count !== 1 ? 's' : ''} updated.`);
      setTimeout(() => window.location.reload(), 1500);
    } else {
      // Show error inside confirm modal body
      document.getElementById('muConfirmDetails').innerHTML =
        `<span style="color:#ef4444;">❌ Error: ${d.error || 'Unknown error occurred.'}</span>`;
      confirmModal.classList.add('show');
    }
  } catch (e) {
    console.error(e);
    confirmModal.classList.remove('show');
    document.getElementById('muConfirmDetails').textContent = 'Network error. Please try again.';
  } finally {
    yesBtn.disabled = false;
    yesBtn.innerHTML = oldHtml;
    _muPending = null;
  }
}
function initializeStudentList() {
  sortStudentsAlphabetically();
  filterStudents();
  updateStatistics();
}
