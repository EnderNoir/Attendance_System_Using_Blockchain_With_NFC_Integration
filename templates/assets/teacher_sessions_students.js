const sessionsData = {{ sessions_json | tojson }};
  let currentSessId = null;
  let currentStudNfc = null;
  let currentStudName = null;
  const sessCache = {};

  // ── Readable date formatter ──
  function fmtReadable(dtStr) {
    if (!dtStr) return '—';
    try {
      const d = new Date(dtStr.replace(' ', 'T'));
      return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
        + ' · '
        + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch (e) { return dtStr; }
  }

  // ── Main tabs ──
  function switchTab(id, btn) {
    document.querySelectorAll('.main-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('pane_' + id).classList.add('active');
    btn.classList.add('active');
  }

  // ── Modal inner tabs ──
  function switchSMTab(id, btn) {
    document.querySelectorAll('.sm-ipane').forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
    document.querySelectorAll('.sm-itab').forEach(b => b.classList.remove('active'));
    const pane = document.getElementById('smpane_' + id);
    pane.style.display = 'flex'; pane.classList.add('active');
    btn.classList.add('active');
  }

  // ══ SESSION MODAL ══
  function openSessModal(sessId) {
    currentSessId = sessId;
    const s = sessionsData[sessId];
    if (!s) return;
    switchSMTab('info', document.getElementById('smtab_info'));
    document.getElementById('sm_title').textContent = (s.course_code ? '[' + s.course_code + '] ' : '') + s.subject_name;
    document.getElementById('sm_badge').innerHTML = s.ended_at
      ? '<span style="background:rgba(100,116,139,.08);color:var(--muted);border:1px solid var(--border);border-radius:20px;padding:2px 10px;font-size:10px;">Completed</span>'
      : '<span style="background:rgba(45,106,39,.12);color:var(--success);border:1px solid rgba(45,106,39,.25);border-radius:20px;padding:2px 10px;font-size:10px;font-weight:700;">● LIVE</span>';
    document.getElementById('sessModal').classList.add('show');
    if (sessCache[sessId]) { renderSessModal(sessId, sessCache[sessId]); return; }
    document.getElementById('sm_info_grid').innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:24px;color:var(--muted);"><span style="display:inline-block;width:16px;height:16px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;"></span></div>';
    document.getElementById('sm_stat_grid').innerHTML = '';
    document.getElementById('sm_att_list').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;"><span style="display:inline-block;width:16px;height:16px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;"></span><div style="margin-top:8px;">Loading…</div></div>';
    fetch('/api/session_attendance/' + sessId, { credentials: 'same-origin' })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(data => { sessCache[sessId] = data; renderSessModal(sessId, data); })
      .catch(err => {
        document.getElementById('sm_info_grid').innerHTML = '<div style="grid-column:1/-1;color:var(--danger);text-align:center;padding:20px;font-size:12px;">Failed to load: ' + err.message + '</div>';
        document.getElementById('sm_att_list').innerHTML = '<div style="color:var(--danger);text-align:center;padding:20px;font-size:12px;">Failed to load attendance. Please try again.</div>';
      });
  }

  function renderSessModal(sessId, data) {
    const s = sessionsData[sessId];
    const sts = data.students || [];
    const cnt = { present: 0, late: 0, absent: 0, excused: 0 };
    sts.forEach(st => { if (cnt[st.status] !== undefined) cnt[st.status]++; });

    // Info tab — readable dates
    document.getElementById('sm_info_grid').innerHTML = `
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-book"></i> Subject</div>
      <div class="sm-info-val">${s.subject_name}${s.course_code ? ' <code style="font-size:10px;">[' + s.course_code + ']</code>' : ''}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-grid"></i> Section</div>
      <div class="sm-info-val">${(s.section_key || '').replace(/\|/g, ' · ')}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-clock"></i> Time Slot</div>
      <div class="sm-info-val">${s.time_slot || '—'}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-people"></i> Total Enrolled</div>
      <div class="sm-info-val">${sts.length} students</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-play-circle"></i> Started</div>
      <div class="sm-info-val">${fmtReadable(s.started_at)}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-stop-circle"></i> Ended</div>
      <div class="sm-info-val">${s.ended_at ? fmtReadable(s.ended_at) : '<span style="color:var(--success);">Still running</span>'}</div></div>`;

    document.getElementById('sm_stat_grid').innerHTML = `
    <div class="sm-stat" style="background:rgba(45,106,39,.07);border-color:rgba(45,106,39,.2);">
      <div class="sm-stat-num" style="color:var(--success);">${cnt.present}</div><div class="sm-stat-lbl" style="color:var(--success);">Present</div></div>
    <div class="sm-stat" style="background:rgba(245,197,24,.07);border-color:rgba(245,197,24,.2);">
      <div class="sm-stat-num" style="color:var(--warning);">${cnt.late}</div><div class="sm-stat-lbl" style="color:var(--warning);">Late</div></div>
    <div class="sm-stat" style="background:rgba(192,57,43,.07);border-color:rgba(192,57,43,.2);">
      <div class="sm-stat-num" style="color:var(--danger);">${cnt.absent}</div><div class="sm-stat-lbl" style="color:var(--danger);">Absent</div></div>
    <div class="sm-stat" style="background:rgba(96,165,250,.07);border-color:rgba(96,165,250,.2);">
      <div class="sm-stat-num" style="color:#60a5fa;">${cnt.excused}</div><div class="sm-stat-lbl" style="color:#60a5fa;">Excused</div></div>`;

    // Attendance Records tab — table format
    const stCls = { present: 'st-present', late: 'st-late', absent: 'st-absent', excused: 'st-excused' };
    const stLbl = { present: '✓ Present', late: '⏱ Late', absent: '✕ Absent', excused: '◎ Excused' };
    if (!sts.length) {
      document.getElementById('sm_att_list').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;"><i class="bi bi-people" style="font-size:28px;display:block;opacity:.2;margin-bottom:8px;"></i>No enrolled students found.</div>';
      return;
    }
    const REASON_LABELS_T = {
      sickness: 'Sickness / Illness', lbm: 'LBM', emergency: 'Family Emergency',
      bereavement: 'Bereavement', medical: 'Medical Appointment', accident: 'Accident / Injury',
      official: 'Official School Business', weather: 'Extreme Weather / Calamity',
      transport: 'Transportation Problem', others: 'Others'
    };
    document.getElementById('sm_att_list').innerHTML = `
    <table class="att-table">
      <thead><tr>
        <th style="width:32px;">#</th>
        <th>Student Name</th>
        <th>Student ID</th>
        <th>Status</th>
        <th>Tap Time</th>
        <th>Excused Reason</th>
        <th>Document</th>
        <th>TX Hash</th>
      </tr></thead>
      <tbody>
        ${sts.map((st, i) => {
      const status = (st.status || 'absent').toLowerCase();
      const isExcused = status === 'excused';
      const reasonLabel = st.reason ? (REASON_LABELS_T[st.reason] || st.reason) : '';
      const reasonDetail = st.reason_detail ? `<div style="font-size:10px;color:var(--muted);font-style:italic;margin-top:2px;">"${st.reason_detail}"</div>` : '';
      const docHtml = st.attachment_url
        ? `<a href="${st.attachment_url}" target="_blank" style="font-size:11px;color:var(--accent);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.2);border-radius:5px;padding:2px 7px;white-space:nowrap;"><i class="bi bi-paperclip"></i> View</a>`
        : '<span style="color:var(--muted);font-size:11px;">—</span>';
      const reasonHtml = isExcused && reasonLabel
        ? `<span style="color:#60a5fa;font-weight:600;font-size:11px;">${reasonLabel}</span>${reasonDetail}`
        : '<span style="color:var(--muted);font-size:11px;">—</span>';
      return `<tr>
            <td class="att-num">${i + 1}</td>
            <td style="font-weight:600;">${st.name || '—'}</td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${st.student_id || st.nfc_id || '—'}</td>
            <td><span class="att-status ${stCls[st.status] || 'st-absent'}">${stLbl[st.status] || '—'}</span></td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${st.time || '—'}</td>
            <td style="font-size:11px;">${reasonHtml}</td>
            <td>${isExcused ? docHtml : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
            <td>${st.tx_hash ? `<span class="att-tx">${st.tx_hash.substring(0, 18)}…</span>` : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
          </tr>`;
    }).join('')}
      </tbody>
    </table>`;
  }

  function closeSessModal() {
    document.getElementById('sessModal').classList.remove('show');
    currentSessId = null;
  }

  function exportCurrentSession() {
    if (!currentSessId) return;
    const s = sessionsData[currentSessId];
    if (!s) return;
    const slug = (s.subject_name || 'session').replace(/[^a-zA-Z0-9]/g, '_').toLowerCase().substring(0, 20);
    const sec = (s.section_key || '').split('|').pop().toLowerCase();
    const now = new Date();
    const fname = `session_${slug}_sec${sec}_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}.xlsx`;
    window.location.href = '/export/session/' + currentSessId + '?filename=' + encodeURIComponent(fname);
  }

  // ══ STUDENT MODAL ══
  const studCache = {};
  function openStudModal(nfcId, name, course, yearLevel, section, studentId) {
    currentStudNfc = nfcId;
    currentStudName = name;
    document.getElementById('stud_name').textContent = name;
    document.getElementById('stud_meta').innerHTML = `
    <div class="stud-meta-item"><i class="bi bi-mortarboard"></i> <strong>${course || '—'}</strong></div>
    <div class="stud-meta-item"><i class="bi bi-layers"></i> <strong>${yearLevel || '—'}</strong></div>
    <div class="stud-meta-item"><i class="bi bi-grid-1x2"></i> Section <strong>${section || '—'}</strong></div>
    ${studentId ? `<div class="stud-meta-item"><i class="bi bi-person-badge"></i> ID: <strong>${studentId}</strong></div>` : ''}
    <div class="stud-meta-item"><i class="bi bi-credit-card-2-front"></i> NFC: <code style="font-size:11px;">${nfcId}</code></div>`;
    document.getElementById('studModal').classList.add('show');
    if (studCache[nfcId]) { renderStudModal(studCache[nfcId]); return; }
    document.getElementById('stud_hist').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;"><span style="display:inline-block;width:16px;height:16px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;"></span><div style="margin-top:8px;">Loading…</div></div>';
    fetch('/api/student_sessions/' + nfcId, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => { studCache[nfcId] = data; renderStudModal(data); })
      .catch(() => {
        document.getElementById('stud_hist').innerHTML = '<div style="color:var(--danger);text-align:center;padding:20px;font-size:12px;">Failed to load. Please try again.</div>';
      });
  }

  function renderStudModal(sessions) {
    const stCls = { present: 'st-present', late: 'st-late', absent: 'st-absent', excused: 'st-excused' };
    const stLbl = { present: '✓ Present', late: '⏱ Late', absent: '✕ Absent', excused: '◎ Excused' };
    const RLABELS = {
      sickness: 'Sickness / Illness', lbm: 'LBM', emergency: 'Family Emergency',
      bereavement: 'Bereavement', medical: 'Medical Appointment', accident: 'Accident / Injury',
      official: 'Official School Business', weather: 'Extreme Weather', transport: 'Transport Problem', others: 'Others'
    };
    if (!sessions.length) {
      document.getElementById('stud_hist').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);font-size:12px;"><i class="bi bi-journal-x" style="font-size:28px;display:block;opacity:.2;margin-bottom:8px;"></i>No session records yet.</div>';
      return;
    }
    document.getElementById('stud_hist').innerHTML = `
    <table class="hist-table">
      <thead><tr>
        <th>#</th>
        <th>Subject</th>
        <th>Date</th>
        <th>Time Slot</th>
        <th>Status</th>
        <th>Excused Reason</th>
        <th>Document</th>
      </tr></thead>
      <tbody>
        ${sessions.map((s, i) => {
      const isExcused = s.status === 'excused';
      const reasonKey = s.excuse_note || '';
      const reasonLabel = RLABELS[reasonKey] || (reasonKey || '—');
      const docHtml = s.attachment_url
        ? `<a href="${s.attachment_url}" target="_blank" style="font-size:11px;color:var(--accent);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.2);border-radius:5px;padding:2px 7px;white-space:nowrap;"><i class="bi bi-paperclip"></i> View</a>`
        : '<span style="color:var(--muted);font-size:11px;">—</span>';
      return `<tr>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${i + 1}</td>
            <td>
              ${s.course_code ? `<span class="hist-code">${s.course_code}</span> ` : ''}
              <span style="font-weight:600;">${s.subject_name}</span>
            </td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;white-space:nowrap;">${s.date}</td>
            <td style="font-size:11px;color:var(--muted);white-space:nowrap;">${s.time_slot || '—'}</td>
            <td><span class="att-status ${stCls[s.status] || 'st-absent'}">${stLbl[s.status] || '—'}</span></td>
            <td style="font-size:11px;">${isExcused && reasonKey ? `<span style="color:#60a5fa;font-weight:600;">${reasonLabel}</span>` : '<span style="color:var(--muted);">—</span>'}</td>
            <td>${isExcused ? docHtml : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
          </tr>`;
    }).join('')}
      </tbody>
    </table>`;
}

function closeStudModal() {
  document.getElementById('studModal').classList.remove('show');
  currentStudNfc = null; currentStudName = null;
}

function exportCurrentStudent() {
  if (!currentStudNfc || !currentStudName) return;
  const p    = currentStudName.split(' ');
  const last = (p[p.length-1]||'student').toLowerCase().replace(/[^a-z0-9]/g,'');
  const fst  = (p[0]||'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const now  = new Date();
  const fname= `${ last }_${ fst }_attendance_${ now.getFullYear() }${ String(now.getMonth() + 1).padStart(2, '0') }.xlsx`;
  window.location.href = '/export/student_sessions/' + currentStudNfc + '?name=' + encodeURIComponent(currentStudName) + '&filename=' + encodeURIComponent(fname);
}

// ── Filters ──
function filterSessions() {
  const q    = document.getElementById('sf_q').value.toLowerCase();
  const prog = document.getElementById('sf_program').value;
  const yr   = document.getElementById('sf_year').value;
  const sec  = document.getElementById('sf_sec').value;
  const subj = document.getElementById('sf_subj').value;
  let n = 0;
  document.querySelectorAll('#sessions_list .session-card').forEach(c => {
    const ok = (!q    || c.dataset.subj.includes(q) || c.dataset.section.includes(q))
            && (!prog || c.dataset.program === prog)
            && (!yr   || c.dataset.year === yr)
            && (!sec  || c.dataset.sec === sec)
            && (!subj || c.dataset.subj === subj);
    c.style.display = ok ? '' : 'none';
    if (ok) n++;
  });
  document.getElementById('sf_count').textContent = n + ' sessions';
  document.getElementById('sf_empty').style.display = n === 0 ? 'block' : 'none';
}
function resetSessionFilters() {
  ['sf_q','sf_program','sf_year','sf_sec','sf_subj'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  filterSessions();
}

function filterStudents(){
  const q=document.getElementById('stf_q').value.toLowerCase();
  const y=document.getElementById('stf_year').value;
  const s=document.getElementById('stf_sec').value;
  let n=0;
  document.querySelectorAll('#students_list .student-card').forEach(c=>{
    const ok=(!q||c.dataset.name.includes(q)||c.dataset.nfc.includes(q)||c.dataset.sid.includes(q))&&(!y||c.dataset.year===y)&&(!s||c.dataset.section===s);
    c.classList.toggle('hidden',!ok); if(ok)n++;
  });
  document.getElementById('stf_count').textContent=n+' students';
  document.getElementById('stf_empty').style.display=n===0?'block':'none';
}
function resetStudentFilters(){['stf_q','stf_year','stf_sec'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});filterStudents();}

