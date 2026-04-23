const sessionsData = {{ sessions_json | tojson }};
sData = sessionsData; // alias for convenience
  let currentSessId = null;
  let currentStudNfc = null;
  let currentStudName = null;
  const sessCache = {};

  function classTypeLabel(v) {
    const t = String(v || 'lecture').toLowerCase().trim();
    if (t === 'laboratory') return 'Laboratory';
    if (t === 'school_event' || t === 'school event') return 'School Event';
    return 'Lecture';
  }

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

  function parseTapDateTime(dtStr, fallbackDateStr = '') {
    if (!dtStr) return { date: '—', time: '—' };
    const raw = String(dtStr).trim();
    if (!raw) return { date: '—', time: '—' };
    const timeOnly = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (timeOnly) {
      const base = parseTapDateTime(fallbackDateStr || '');
      const hh = Number(timeOnly[1]);
      const mm = timeOnly[2];
      const ss = timeOnly[3] || '00';
      const period = hh >= 12 ? 'PM' : 'AM';
      const hh12 = hh % 12 === 0 ? 12 : hh % 12;
      return {
        date: base.date !== '—' ? base.date : '—',
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
      if (Number.isNaN(d.getTime())) return { date: '—', time: '—' };
      return {
        date: d.toLocaleDateString('en-US', { month: 'long', day: '2-digit', year: 'numeric' }).replace(',', ''),
        time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }),
      };
    } catch (e) {
      return { date: '—', time: '—' };
    }
  }

  function formatHistoryDate(input) {
    if (!input) return '—';
    const raw = String(input).trim();
    if (!raw) return '—';
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
      if (Number.isNaN(d.getTime())) return '—';
      const month = d.toLocaleString('en-US', { month: 'long' });
      const day = String(d.getDate()).padStart(2, '0');
      const year = d.getFullYear();
      return `${month}:${day}:${year}`;
    } catch (e) {
      return '—';
    }
  }

  function normalizeTimeToAmPm(input) {
    if (!input) return '—';
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

  function normalizeTimeSlot(slot) {
    if (!slot) return '—';
    const raw = String(slot).trim();
    if (!raw) return '—';
    if (/[A-Za-z]+-\d{2}-\d{4}/.test(raw)) return '—';
    if (/\b(am|pm)\b/i.test(raw)) return raw.toUpperCase();
    if (/^\d{4}-\d{2}-\d{2}[ T]/.test(raw)) {
      const d = new Date(raw.replace(' ', 'T').replace(/\.(\d{3})\d+/, '.$1'));
      if (!Number.isNaN(d.getTime())) {
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
      }
    }
    const parts = raw.split(/\s*[\-–]\s*/);
    if (parts.length === 2) return `${normalizeTimeToAmPm(parts[0])} - ${normalizeTimeToAmPm(parts[1])}`;
    return normalizeTimeToAmPm(raw);
  }

  function pickHistoryDate(sessionObj) {
    if (!sessionObj) return '—';
    const candidates = [sessionObj.started_at, sessionObj.date, sessionObj.tap_time];
    for (const c of candidates) {
      const out = formatHistoryDate(c || '');
      if (out !== '—') return out;
    }
    return '—';
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

  function bindTxCopyHandlers(scopeEl) {
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
    const s = sData[sessId];
    const sts = data.students || [];
    const classType = String(s.class_type || data.class_type || 'lecture').toLowerCase();
    const teachersInvolved = (data.teachers_involved || []).join(', ') || (s.teacher_name || '-');
    const sectionsInvolved = (data.sections_involved || []).map((x) => String(x || '').replace(/\|/g, ' · ')).join(', ') || ((s.section_key || '').replace(/\|/g, ' · '));
    const cnt = { present: 0, late: 0, absent: 0, excused: 0 };
    sts.forEach(st => { if (cnt[st.status] !== undefined) cnt[st.status]++; });

    // Info tab — readable dates
    let sessTxHtml = '';
  if (s.session_tx_hash) {
    sessTxHtml = `
    <div class="sm-info-box">
      <div class="sm-info-lbl"><i class="bi bi-blockchain"></i> Session TX</div>
      <div class="sm-info-val">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
          <a href="https://sepolia.etherscan.io/tx/${s.session_tx_hash}" target="_blank" title="View on Etherscan" style="font-size:11px; font-family:'Space Mono',monospace; color:var(--accent); text-decoration:underline; word-break: break-all;">
            ${s.session_tx_hash}
          </a>
        </div>
        ${s.session_block_number ? `<div style="font-size:10px;color:var(--muted);margin-top:4px;">Block #${s.session_block_number}</div>` : ''}
      </div>
    </div>`;
  }
  document.getElementById('sm_info_grid').innerHTML = `${sessTxHtml}
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-book"></i> Subject</div>
      <div class="sm-info-val">${s.subject_name}${s.course_code ? ' <code style="font-size:10px;">[' + s.course_code + ']</code>' : ''}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-collection"></i> Class Type</div>
      <div class="sm-info-val">${classTypeLabel(s.class_type || data.class_type || 'lecture')}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-grid"></i> Section</div>
      <div class="sm-info-val">${(s.section_key || '').replace(/\|/g, ' · ')}${s.semester ? ' · ' + s.semester : ''}</div></div>
    ${classType === 'school_event' ? `
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-people"></i> Teachers Involved</div>
      <div class="sm-info-val">${teachersInvolved}</div></div>
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-diagram-3"></i> Sections Involved</div>
      <div class="sm-info-val">${sectionsInvolved}</div></div>
    ` : ''}
    <div class="sm-info-box"><div class="sm-info-lbl"><i class="bi bi-clock"></i> Time Slot</div>
      <div class="sm-info-val">${normalizeTimeSlot(s.time_slot) || '—'}</div></div>
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
    const stLbl = { present: 'Present', late: 'Late', absent: 'Absent', excused: 'Excused' };
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
        <th>${classType === 'school_event' ? 'Program-Year-Section' : 'Class Type'}</th>
        <th>Status</th>
        <th>Tapped Time</th>
        <th>Excused Reason</th>
        <th>Document</th>
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
      const tap = parseTapDateTime(st.time || st.tap_time || s.started_at || '', s.started_at || '');
      return `<tr>
            <td class="att-num">${i + 1}</td>
            <td style="font-weight:600;">${st.name || '—'}</td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${st.student_id || st.nfc_id || '—'}</td>
            <td>${classType === 'school_event'
              ? `<span style="font-size:11px;color:var(--muted);">${st.section_origin || '—'}</span>`
              : `<span class="att-status st-excused">${classTypeLabel(st.class_type || s.class_type || data.class_type || 'lecture')}</span>`}</td>
            <td><span class="att-status ${stCls[status] || 'st-absent'}">${stLbl[status] || '—'}</span></td>
            <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${tap.time}</td>
            <td style="font-size:11px;">${reasonHtml}</td>
            <td>${isExcused ? docHtml : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
          </tr>`;
    }).join('')}
      </tbody>
    </table>`;
    bindTxCopyHandlers(document.getElementById('sm_att_list'));
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
          <div class="sem-accordion-header flex-stack-mobile" style="padding: 12px 16px; background: rgba(45,106,39,.05); display: flex; justify-content: space-between; align-items: center; font-weight: 600; flex-wrap: wrap; gap: 8px;">
            <div style="cursor: pointer; flex: 1;" onclick="const b=this.parentElement.nextElementSibling; const i=this.querySelector('i'); if(b.style.display==='none'){b.style.display='block';i.classList.replace('bi-chevron-down','bi-chevron-up');}else{b.style.display='none';i.classList.replace('bi-chevron-up','bi-chevron-down');}">
              <span>${sem} <span style="font-size: 11px; font-weight: 400; color: var(--muted); margin-left: 8px;">(${semSessions.length} sessions)</span></span>
              <i class="bi bi-chevron-${sIdx === 0 ? 'up' : 'down'}" style="margin-left: 8px;"></i>
            </div>
            <button class="btn-export-xl" style="padding: 4px 10px; font-size: 11px; margin-left: 12px; border-radius: 4px;" onclick="exportStudentSemester('${sem}')">
              <i class="bi bi-file-earmark-excel"></i> Export
            </button>
          </div>
          <div class="sem-accordion-body" style="display: ${sIdx === 0 ? 'block' : 'none'}; padding: 0; overflow-x: auto;">
            <table class="hist-table" style="margin: 0; border: none; border-radius: 0; width: 100%; min-width: 800px;">
              <thead><tr>
                <th>#</th>
                <th>Course Code</th>
                <th>Subject Name</th>
                <th>Class Type</th>
                <th>Status</th>
                <th>Tapped Time</th>
                <th>Date</th>
                <th>Time Slot</th>
                <th>Excused Reason</th>
                <th>Document</th>
                <th>Transaction Number (TX)</th>
                <th>Block Number</th>
              </tr></thead>
              <tbody>
                ${semSessions.map((s, i) => {
                  const isExcused = s.status === 'excused';
                  const reasonKey = s.excuse_note || '';
                  const reasonLabel = RLABELS[reasonKey] || (reasonKey || '—');
                  const docHtml = s.attachment_url
                    ? `<a href="${s.attachment_url}" target="_blank" style="font-size:11px;color:var(--accent);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;background:rgba(45,106,39,.07);border:1px solid rgba(45,106,39,.2);border-radius:5px;padding:2px 7px;white-space:nowrap;"><i class="bi bi-paperclip"></i> View</a>`
                    : '<span style="color:var(--muted);font-size:11px;">—</span>';
                  return `<tr>
                    <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${i + 1}</td>
                    <td>${s.course_code ? `<span class="hist-code">${s.course_code}</span>` : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
                    <td><span style="font-weight:600;">${s.subject_name || '—'}</span></td>
                    <td><span class="att-status st-excused">${classTypeLabel(s.class_type || 'lecture')}</span></td>
                    <td><span class="att-status ${stCls[s.status] || 'st-absent'}">${stLbl[s.status] || '—'}</span></td>
                    <td style="font-family:'Space Mono',monospace;font-size:11px;white-space:nowrap;">${s.tap_time ? parseTapDateTime(s.tap_time).time : '—'}</td>
                    <td style="font-family:'Space Mono',monospace;font-size:11px;white-space:nowrap;">${pickHistoryDate(s)}</td>
                    <td style="font-size:11px;color:var(--muted);white-space:nowrap;">${normalizeTimeSlot(s.time_slot || s.tap_time || '')}</td>
                    <td style="font-size:11px;">${isExcused && reasonKey ? `<span style="color:#60a5fa;font-weight:600;">${reasonLabel}</span>` : '<span style="color:var(--muted);">—</span>'}</td>
                    <td>${isExcused ? docHtml : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
                    <td>${s.tx_hash ? `<a href="https://sepolia.etherscan.io/tx/${s.tx_hash}" target="_blank" title="View on Etherscan" style="font-size:11px; font-family:'Space Mono',monospace; color:var(--accent); text-decoration:none; word-break: break-all;">${s.tx_hash.slice(0, 16)}...</a>` : '<span style="color:var(--muted);font-size:11px;">—</span>'}</td>
                    <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);">${s.block || '—'}</td>
                  </tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    });

    document.getElementById('stud_hist').innerHTML = html;
    bindTxCopyHandlers(document.getElementById('stud_hist'));
}

function closeStudModal() {
  document.getElementById('studModal').classList.remove('show');
  currentStudNfc = null; currentStudName = null;
}

function exportStudentSemester(sem) {
  if (!currentStudNfc || !currentStudName) return;
  const p    = currentStudName.split(' ');
  const last = (p[p.length-1]||'student').toLowerCase().replace(/[^a-z0-9]/g,'');
  const fst  = (p[0]||'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const now  = new Date();
  const fname= `${ last }_${ fst }_${sem.replace(/[^a-z0-9]/gi, '_')}_${ now.getFullYear() }${ String(now.getMonth() + 1).padStart(2, '0') }.xlsx`;
  window.location.href = '/export/student_sessions/' + currentStudNfc + '?name=' + encodeURIComponent(currentStudName) + '&semester=' + encodeURIComponent(sem) + '&filename=' + encodeURIComponent(fname);
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

