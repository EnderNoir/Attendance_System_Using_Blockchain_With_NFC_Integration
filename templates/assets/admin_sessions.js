/* Build a flat sessions lookup from Jinja */
const sessionsData = {
  {% for sid, s in active.items() %}
  "{{ sid }}": {
    subject_name: "{{ s.subject_name|e }}",
    course_code: "{{ s.get('course_code','')|e }}",
    class_type: "{{ s.get('class_type','lecture')|e }}",
    section_key: "{{ s.section_key|e }}",
    teacher_name: "{{ s.teacher_name|e }}",
    time_slot: "{{ (s.time_slot|fmt_timeslot)|e if s.time_slot else '' }}",
    semester: "{{ s.semester|e }}",
    started_at: "{{ s.started_at|e }}",
    ended_at: null,
    units: "{{ s.get('units','3') }}",
    session_tx_hash: "{{ s.session_tx_hash|e if s.session_tx_hash else '' }}",
    session_block_number: "{{ s.session_block_number|e if s.session_block_number else '' }}",
    event_description: "{{ (s.get('event_description','') or '')|e }}",
    teachers_involved: {{ s.get('teachers_involved', [])|tojson }},
    section_keys_involved: {{ s.get('section_keys_involved', [])|tojson }},
  },
  {% endfor %}
  {% for sid, s in ended.items() %}
  "{{ sid }}": {
    subject_name: "{{ s.subject_name|e }}",
    course_code: "{{ s.get('course_code','')|e }}",
    class_type: "{{ s.get('class_type','lecture')|e }}",
    section_key: "{{ s.section_key|e }}",
    teacher_name: "{{ s.teacher_name|e }}",
    time_slot: "{{ (s.time_slot|fmt_timeslot)|e if s.time_slot else '' }}",
    semester: "{{ s.semester|e }}",
    started_at: "{{ s.started_at|e }}",
    ended_at: "{{ s.ended_at|e }}",
    units: "{{ s.get('units','3') }}",
    session_tx_hash: "{{ s.session_tx_hash|e if s.session_tx_hash else '' }}",
    session_block_number: "{{ s.session_block_number|e if s.session_block_number else '' }}",
    event_description: "{{ (s.get('event_description','') or '')|e }}",
    teachers_involved: {{ s.get('teachers_involved', [])|tojson }},
    section_keys_involved: {{ s.get('section_keys_involved', [])|tojson }},
  },
  {% endfor %}
};

let currentSessId = null;
const sessCache = {};

function fmtReadable(dtStr) {
  if (!dtStr || dtStr === 'None') return '-';
  try {
    const d = new Date(dtStr.replace(' ', 'T'));
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
      + ' | '
      + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  } catch (e) {
    return dtStr;
  }
}

function parseTapDateTime(dtStr, fallbackDateStr = '') {
  if (!dtStr) return { date: '-', time: '-' };
  const raw = String(dtStr).trim();
  if (!raw) return { date: '-', time: '-' };
  const timeOnly = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (timeOnly) {
    const base = parseTapDateTime(fallbackDateStr || '');
    const hh = Number(timeOnly[1]);
    const mm = timeOnly[2];
    const ss = timeOnly[3] || '00';
    const period = hh >= 12 ? 'PM' : 'AM';
    const hh12 = hh % 12 === 0 ? 12 : hh % 12;
    return {
      date: base.date !== '-' ? base.date : '-',
      time: `${String(hh12).padStart(2, '0')}:${mm}:${ss} ${period}`,
    };
  }
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
    if (Number.isNaN(d.getTime())) return { date: '-', time: '-' };
    return {
      date: d.toLocaleDateString('en-US', { month: 'long', day: '2-digit', year: 'numeric' }).replace(',', ''),
      time: d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }),
    };
  } catch (e) {
    return { date: '-', time: '-' };
  }
}

function normalizeClassType(raw) {
  const val = String(raw || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (val === 'school_event' || val === 'event') return 'school_event';
  if (val === 'laboratory' || val === 'lab') return 'laboratory';
  if (val === 'lecture') return 'lecture';
  return 'lecture';
}

function switchTab(id, btn) {
  document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}

function switchSMTab(id, btn) {
  document.querySelectorAll('.sm-ipane').forEach((p) => {
    p.classList.remove('active');
    p.style.display = 'none';
  });
  document.querySelectorAll('.sm-itab').forEach((b) => b.classList.remove('active'));
  const pane = document.getElementById('smpane_' + id);
  pane.style.display = 'flex';
  pane.classList.add('active');
  btn.classList.add('active');
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

function bindTxCopyHandlers() {
  const scope = document.getElementById('sm_att_list');
  if (!scope) return;
  scope.querySelectorAll('.att-tx-copy, .sess-tx-copy').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const tx = btn.dataset.tx || '';
      copyText(tx).then((ok) => {
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

function openSessModal(sessId) {
  currentSessId = sessId;
  const s = sessionsData[sessId];
  if (!s) return;

  switchSMTab('info', document.getElementById('smtab_info'));

  document.getElementById('sm_title').textContent = (s.course_code ? '[' + s.course_code + '] ' : '') + s.subject_name;
  document.getElementById('sm_badge').innerHTML = s.ended_at
    ? '<span style="background:rgba(100,116,139,.08);color:var(--muted);border:1px solid var(--border);border-radius:20px;padding:2px 10px;font-size:10px;">Completed</span>'
    : '<span style="background:rgba(45,106,39,.12);color:var(--success);border:1px solid rgba(45,106,39,.25);border-radius:20px;padding:2px 10px;font-size:10px;font-weight:700;">LIVE</span>';

  document.getElementById('sessModal').classList.add('show');

  if (sessCache[sessId]) {
    renderSessModal(sessId, sessCache[sessId]);
    return;
  }

  document.getElementById('sm_info_grid').innerHTML =
    '<div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--muted);">' +
    '<span style="display:inline-block;width:18px;height:18px;border:2px solid var(--border);' +
    'border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;"></span></div>';
  document.getElementById('sm_stat_grid').innerHTML = '';
  document.getElementById('sm_att_list').innerHTML =
    '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;">' +
    '<span style="display:inline-block;width:16px;height:16px;border:2px solid var(--border);' +
    'border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;"></span>' +
    '<div style="margin-top:8px;">Loading attendance...</div></div>';

  fetch('/api/session_attendance/' + sessId, { credentials: 'same-origin' })
    .then((r) => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then((data) => {
      sessCache[sessId] = data;
      renderSessModal(sessId, data);
    })
    .catch((err) => {
      document.getElementById('sm_info_grid').innerHTML =
        '<div style="grid-column:1/-1;color:var(--danger);text-align:center;padding:24px;font-size:12px;">' +
        'Failed to load session data: ' + err.message + '</div>';
      document.getElementById('sm_att_list').innerHTML =
        '<div style="color:var(--danger);text-align:center;padding:24px;font-size:12px;">' +
        'Failed to load attendance. Please try again.</div>';
    });
}

function renderSessModal(sessId, data) {
  const s = sessionsData[sessId];
  const sts = data.students || [];
  const classType = normalizeClassType(s.class_type || data.class_type || 'lecture');
  const classTypeLabel = classType === 'school_event' ? 'School Event' : (classType === 'laboratory' ? 'Laboratory' : 'Lecture');
  const teachersInvolved = (data.teachers_involved || s.teachers_involved || []).join('<br>') || (s.teacher_name || '-');
  const sectionsInvolved = (data.programs_involved || s.section_keys_involved || []).map((x) => String(x || '').replace(/\|/g, ' ')).join('<br>') || ((s.section_key || '').replace(/\|/g, ' '));

  const cnt = { present: 0, late: 0, absent: 0, excused: 0 };
  sts.forEach((st) => {
    const status = (st.status || 'absent').toLowerCase();
    if (cnt[status] !== undefined) cnt[status]++;
  });

    const sessTx = data.session_tx_hash || s.session_tx_hash;
    const sessBlock = data.session_block_number || s.session_block_number;
    let sessTxHtml = '';
    if (sessTx) {
      sessTxHtml = `
      <div class="sm-info-box">
        <div class="sm-info-lbl"><i class="bi bi-blockchain"></i> Session TX</div>
        <div class="sm-info-val">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <a href="https://sepolia.etherscan.io/tx/${sessTx}" target="_blank" title="View on Etherscan" style="font-size:11px; font-family:'Space Mono',monospace; color:var(--accent); text-decoration:underline; word-break: break-all;">
              ${sessTx}
            </a>
          </div>
          ${sessBlock ? `<div style="font-size:10px;color:var(--muted);margin-top:4px;">Block #${sessBlock}</div>` : ''}
        </div>
      </div>`;
    } else {
      sessTxHtml = `
      <div class="sm-info-box">
        <div class="sm-info-lbl"><i class="bi bi-blockchain"></i> Session TX</div>
        <div class="sm-info-val"><span style="font-size:11px; color:var(--muted); font-style:italic;">Pending or Not Recorded</span></div>
      </div>`;
    }

  document.getElementById('sm_info_grid').innerHTML = `
    ${sessTxHtml}
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-book"></i> ${classType === 'school_event' ? 'Event Name' : 'Subject'}</div>
      <div class="sm-info-val">${s.subject_name}${s.course_code && classType !== 'school_event' ? ' <code style="font-size:10px;background:rgba(45,106,39,.08);color:var(--accent);padding:1px 5px;border-radius:3px;">[' + s.course_code + ']</code>' : ''}</div>
    </div>
    ${classType === 'school_event' && (data.event_description || s.event_description) ? `
    <div class="sm-info-box" style="grid-column: 1/-1;">
      <div class="sm-info-lbl"><i class="bi bi-card-text"></i> Event Description</div>
      <div class="sm-info-val">${data.event_description || s.event_description}</div>
    </div>` : ''}
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-grid"></i> ${classType === 'school_event' ? 'Program(s) and Section(s) Involved' : 'Section'}</div>
      <div class="sm-info-val">${classType === 'school_event' ? sectionsInvolved : (s.section_key || '').replace(/\|/g, ' · ') + (s.semester ? ' · ' + s.semester : '')}</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-person-badge"></i> ${classType === 'school_event' ? 'Teachers Involved' : 'Instructor'}</div>
      <div class="sm-info-val">${classType === 'school_event' ? teachersInvolved : (s.teacher_name || '-')}</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-clock"></i> Time Slot</div>
      <div class="sm-info-val">${s.time_slot || '-'}</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-tags"></i> Class Type</div>
      <div class="sm-info-val">${classTypeLabel}</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-people"></i> Total Enrolled</div>
      <div class="sm-info-val">${sts.length} students</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-journal"></i> Units</div>
      <div class="sm-info-val">${s.units || '3'} Units</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-play-circle"></i> Started</div>
      <div class="sm-info-val">${fmtReadable(s.started_at)}</div>
    </div>
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-stop-circle"></i> Ended</div>
      <div class="sm-info-val">${s.ended_at && s.ended_at !== 'None' ? fmtReadable(s.ended_at) : '<span style="color:var(--success);font-weight:600;">Still running</span>'}</div>
    </div>
    ${!s.ended_at || s.ended_at === 'None'
      ? `<div style="grid-column:1/-1;">
           <a href="/teacher/session/${sessId}" class="btn-vr" style="text-decoration:none;width:100%;justify-content:center;">
             <i class="bi bi-broadcast"></i> Monitor Live Session
           </a>
         </div>`
      : ''}`;

  document.getElementById('sm_stat_grid').innerHTML = `
    <div class="sm-stat" style="background:rgba(45,106,39,.07);border-color:rgba(45,106,39,.2);">
      <div class="sm-stat-num" style="color:var(--success);">${cnt.present}</div>
      <div class="sm-stat-lbl" style="color:var(--success);">Present</div>
    </div>
    <div class="sm-stat" style="background:rgba(245,197,24,.07);border-color:rgba(245,197,24,.2);">
      <div class="sm-stat-num" style="color:var(--warning);">${cnt.late}</div>
      <div class="sm-stat-lbl" style="color:var(--warning);">Late</div>
    </div>
    <div class="sm-stat" style="background:rgba(192,57,43,.07);border-color:rgba(192,57,43,.2);">
      <div class="sm-stat-num" style="color:var(--danger);">${cnt.absent}</div>
      <div class="sm-stat-lbl" style="color:var(--danger);">Absent</div>
    </div>
    <div class="sm-stat" style="background:rgba(96,165,250,.07);border-color:rgba(96,165,250,.2);">
      <div class="sm-stat-num" style="color:#60a5fa;">${cnt.excused}</div>
      <div class="sm-stat-lbl" style="color:#60a5fa;">Excused</div>
    </div>`;

  const stCls = { present: 'st-present', late: 'st-late', absent: 'st-absent', excused: 'st-excused' };
  const stLbl = { present: 'Present', late: 'Late', absent: 'Absent', excused: 'Excused' };

  if (!sts.length) {
    document.getElementById('sm_att_list').innerHTML =
      '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;">' +
      '<i class="bi bi-people" style="font-size:28px;display:block;opacity:.2;margin-bottom:8px;"></i>' +
      'No students found for this session.</div>';
    return;
  }

  const REASON_LABELS = {
    sickness: 'Sickness / Illness',
    lbm: 'LBM',
    emergency: 'Family Emergency',
    bereavement: 'Bereavement',
    medical: 'Medical Appointment',
    accident: 'Accident / Injury',
    official: 'Official School Business',
    weather: 'Extreme Weather / Calamity',
    transport: 'Transportation Problem',
    others: 'Others',
  };

  document.getElementById('sm_att_list').innerHTML = `
    <table class="att-table" style="margin-top:4px;">
      <thead><tr>
        <th style="width:36px;">#</th>
        <th>Student Name</th>
        <th>Student ID</th>
        <th>Enrollment Type</th>
        <th>${classType === 'school_event' ? 'Program-Year-Section' : 'Class Type'}</th>
        <th>Status</th>
        <th>Tapped Time</th>
        <th>Excused Reason</th>
        <th>Document</th>
      </tr></thead>
      <tbody>
        ${sts.map((st, i) => {
          const status = (st.status || 'absent').toLowerCase();
          const reasonLabel = st.reason ? (REASON_LABELS[st.reason] || st.reason) : '-';
          const reasonDetail = st.reason_detail
            ? `<div style="font-size:10px;color:var(--muted);font-style:italic;margin-top:2px;">"${st.reason_detail}"</div>`
            : '';
          const docLink = st.attachment_url
            ? `<a href="${st.attachment_url}" target="_blank" style="font-size:11px;color:var(--accent);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.2);border-radius:5px;padding:2px 7px;white-space:nowrap;"><i class="bi bi-paperclip"></i> View</a>`
            : '<span style="color:var(--muted);font-size:11px;">-</span>';
          const tap = parseTapDateTime(st.time || st.tap_time || s.started_at || '', s.started_at || '');
          const displayTapTime = (status === 'absent' || status === 'excused') ? '-' : tap.time;
          return `<tr>
            <td class="att-num">${i + 1}</td>
            <td style="font-weight:600;">${st.name || '-'}</td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${st.student_id || st.nfc_id || '-'}</td>
            <td>${st.enrollment_status === 'Irregular' ? '<span style="font-size:9px;background:rgba(192,57,43,.1);color:var(--danger);padding:1px 5px;border-radius:4px;font-weight:700;text-transform:uppercase;border:1px solid rgba(192,57,43,.2);">Irregular</span>' : '<span style="font-size:9px;background:rgba(46,204,113,.1);color:var(--success);padding:1px 5px;border-radius:4px;font-weight:700;text-transform:uppercase;border:1px solid rgba(46,204,113,.2);">Regular</span>'}</td>
            <td>${classType === 'school_event'
              ? `<span style="font-size:11px;color:var(--muted);">${st.section_origin || '-'}</span>`
              : `<span style="font-size:11px;color:var(--muted);">${classTypeLabel}</span>`}</td>
            <td><span class="att-status ${stCls[status] || 'st-absent'}">${stLbl[status] || status}</span></td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${displayTapTime}</td>
            <td style="font-size:11px;">${status === 'excused' ? `<span style="color:#60a5fa;font-weight:600;">${reasonLabel}</span>${reasonDetail}` : '<span style="color:var(--muted);">-</span>'}</td>
            <td>${status === 'excused' ? docLink : '<span style="color:var(--muted);font-size:11px;">-</span>'}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;

  bindTxCopyHandlers();
}

  function closeSessModal() {
    document.getElementById('sessModal').classList.remove('show');
    currentSessId = null;
  }

  function confirmDeleteSession() {
    if (!currentSessId) return;
    document.getElementById('deleteConfirmModal').classList.add('show');
  }

  function executeDeleteSession() {
    if (!currentSessId) return;
    const btn = document.getElementById('btnExecuteDelete');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass"></i> Deleting...';
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/admin/session/' + currentSessId + '/delete';
    document.body.appendChild(form);
    form.submit();
  }

  function closeDeleteModal() {
    document.getElementById('deleteConfirmModal').classList.remove('show');
  }

function exportCurrentSession() {
  if (!currentSessId) return;
  const s = sessionsData[currentSessId];
  if (!s) return;
  const slug = (s.subject_name || 'session').replace(/[^a-zA-Z0-9]/g, '_').toLowerCase().substring(0, 20);
  const sec = (s.section_key || '').split('|').pop().toLowerCase();
  const now = new Date();
  const fname = `session_${slug}_sec${sec}_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}.xlsx`;
  const btn = document.querySelector('.btn-export-xl[onclick*="exportCurrentSession"]')
    || document.querySelector('#stud_export_btn')
    || document.querySelector('.att-tab-top .btn-export-xl');
  if (btn) {
    animateExportBtn(btn, '/export/session/' + currentSessId + '?filename=' + encodeURIComponent(fname));
  } else {
    window.location.href = '/export/session/' + currentSessId + '?filename=' + encodeURIComponent(fname);
  }
}

function filterLive() {
  const q = document.getElementById('lf_search').value.toLowerCase();
  const classType = (document.getElementById('lf_class_type')?.value || '').toLowerCase();
  const sem = (document.getElementById('lf_semester')?.value || '').toLowerCase();
  let shown = 0;
  document.querySelectorAll('#liveList .sess-row').forEach((r) => {
    const m = (!q || r.dataset.subject.includes(q) || r.dataset.teacher.includes(q))
      && (!classType || (r.dataset.classtype || 'lecture') === classType)
      && (!sem || (r.dataset.semester || '').includes(sem));
    r.style.display = m ? '' : 'none';
    if (m) shown++;
  });
  document.getElementById('lf_count').textContent = shown + ' shown';
}

function resetLive() {
  document.getElementById('lf_search').value = '';
  const classTypeSel = document.getElementById('lf_class_type');
  if (classTypeSel) classTypeSel.value = '';
  const semSel = document.getElementById('lf_semester');
  if (semSel) semSel.value = '';
  filterLive();
}

function filterEnded() {
  const q = document.getElementById('ef_search').value.toLowerCase();
  const t = document.getElementById('ef_teacher').value;
  const prog = document.getElementById('ef_program').value;
  const yr = document.getElementById('ef_year').value;
  const sec = document.getElementById('ef_secletter').value;
  const subj = document.getElementById('ef_subject').value;
  const classType = (document.getElementById('ef_class_type')?.value || '').toLowerCase();
  const sem = (document.getElementById('ef_semester')?.value || '').toLowerCase();
  let shown = 0;
  document.querySelectorAll('#endedList .sess-row').forEach((r) => {
    const m = (!q || r.dataset.subject.includes(q) || r.dataset.teacher.includes(q))
      && (!t || r.dataset.teacher === t)
      && (!prog || r.dataset.program === prog)
      && (!yr || r.dataset.year === yr)
      && (!sec || r.dataset.secletter === sec)
      && (!subj || r.dataset.subject === subj)
      && (!classType || (r.dataset.classtype || 'lecture') === classType)
      && (!sem || (r.dataset.semester || '').includes(sem));
    r.style.display = m ? '' : 'none';
    if (m) shown++;
  });
  document.getElementById('ef_count').textContent = shown + ' shown';
  const empty = document.getElementById('ef_empty');
  if (empty) empty.style.display = shown === 0 ? 'block' : 'none';
}

function resetEnded() {
  ['ef_search', 'ef_teacher', 'ef_program', 'ef_year', 'ef_secletter', 'ef_subject', 'ef_class_type', 'ef_semester'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  filterEnded();
}

/** 
 * --- BLOCKCHAIN INTEGRITY AUDIT ---
 */
let auditAbortController = null;

function runBlockchainAudit() {
  const overlay = document.getElementById('auditOverlay');
  overlay.style.display = 'flex';
  overlay.classList.add('show');

  auditAbortController = new AbortController();

  fetch('/api/admin/audit_sessions', { signal: auditAbortController.signal })
    .then(r => r.json())
    .then(data => {
      if (data.error) throw new Error(data.error);
      showAuditResults(data);
    })
    .catch(err => {
      if (err.name === 'AbortError') {
        console.log('Audit cancelled by user.');
      } else {
        alert("Audit failed: " + err.message);
      }
    })
    .finally(() => {
      overlay.classList.remove('show');
      setTimeout(() => overlay.style.display = 'none', 300);
    });
}

function cancelAudit() {
  if (auditAbortController) {
    auditAbortController.abort();
  }
}

function showAuditResults(data) {
  const modal = document.getElementById('auditResultModal');
  const body = document.getElementById('auditResultBody');
  const countSpan = document.getElementById('auditConflictCount');
  
  const conflicts = data.conflicts || [];
  countSpan.textContent = conflicts.length + ' Conflicts';
  countSpan.style.background = conflicts.length > 0 ? 'var(--danger)' : 'var(--success)';
  countSpan.style.color = 'white';

  if (conflicts.length === 0) {
    body.innerHTML = `
      <div style="text-align:center;padding:40px;color:var(--muted);">
        <i class="bi bi-shield-check" style="font-size:48px;color:var(--success);opacity:.5;display:block;margin-bottom:12px;"></i>
        <div style="font-weight:600;color:var(--foreground);font-size:16px;">All Records Verified</div>
        <p style="font-size:12px;margin-top:8px;">No discrepancies detected between Local Database and Blockchain Ledger.</p>
      </div>
    `;
    document.getElementById('btnResolveAudit').style.display = 'none';
  } else {
    let html = `
      <div style="margin-bottom:16px;font-size:12px;color:var(--danger);background:rgba(192,57,43,.05);padding:10px;border-radius:6px;border:1px solid rgba(192,57,43,.1);">
        <i class="bi bi-exclamation-triangle-fill"></i> Data tampering detected in ${conflicts.length} record(s). Local database does not match the immutable blockchain ledger.
      </div>
      <table class="att-table">
        <thead>
          <tr>
            <th>Session / Event</th>
            <th>Session Tx</th>
            <th>Session Date</th>
            <th>Student Name</th>
            <th>Local DB</th>
            <th>Blockchain</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
    `;
    
    conflicts.forEach(c => {
      let dateFmt = '-';
      if (c.started_at) {
        try {
          const d = new Date(c.started_at.replace(' ', 'T'));
          dateFmt = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
        } catch (e) {
          dateFmt = c.started_at;
        }
      }
      
      html += `
        <tr>
          <td>
            <div style="font-weight:600;">${c.subject_name}</div>
            <div style="font-size:10px;color:var(--muted);">${c.class_type || 'Lecture'}</div>
          </td>
          <td>
            <a href="https://sepolia.etherscan.io/tx/${c.tx_hash}" target="_blank" style="font-size:10px;font-family:monospace;color:var(--accent);text-decoration:none;">
              ${c.tx_hash.substring(0,10)}... <i class="bi bi-box-arrow-up-right"></i>
            </a>
          </td>
          <td>
            <div style="font-size:10px;color:var(--foreground);">${dateFmt}</div>
          </td>
          <td>
             <div style="font-weight:600;">${c.student_name}</div>
             <div style="font-size:10px;font-family:monospace;color:var(--muted);">${c.nfc_id}</div>
          </td>
          <td><span class="att-status st-absent" style="text-transform:uppercase;font-size:10px;">${c.db_status}</span></td>
          <td><span class="att-status st-present" style="text-transform:uppercase;font-size:10px;background:var(--success);color:white;">${c.bc_status}</span></td>
          <td>
            <button class="btn-rst" onclick="openSessModal('${c.sess_id}');" style="padding:4px 8px;font-size:10px;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text);cursor:pointer;">
              <i class="bi bi-eye"></i> View Session
            </button>
          </td>
        </tr>
      `;
    });
    
    html += `</tbody></table>`;
    body.innerHTML = html;
    document.getElementById('btnResolveAudit').style.display = 'block';
    document.getElementById('btnResolveAudit').onclick = () => resolveAuditConflicts(conflicts);
  }

  modal.classList.add('show');
}

function resolveAuditConflicts(conflicts) {
  const btn = document.getElementById('btnResolveAudit');
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Resolving...';

  fetch('/api/admin/resolve_tampering', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conflicts })
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) throw new Error(data.error);
    alert(`Success! ${data.resolved} tampered records have been restored to their original blockchain state. Faculty and Admin have been notified.`);
    closeAuditModal();
    window.location.reload();
  })
  .catch(err => {
    alert("Resolution failed: " + err.message);
    btn.disabled = false;
    btn.innerHTML = originalHtml;
  });
}

function closeAuditModal() {
  document.getElementById('auditResultModal').classList.remove('show');
}
