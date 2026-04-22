// Attendance record page script: extracted from template for easier debugging.

function getNfcId() {
  return document.getElementById('attendanceMeta')?.dataset?.nfcId || '';
}

function loadSessionRecords() {
  const nfcId = getNfcId();
  if (!nfcId) {
    const list = document.getElementById('sessionDetailList');
    if (list) {
      list.innerHTML = '<div style="color:var(--danger);text-align:center;padding:24px;font-size:12px;">Missing student identifier.</div>';
    }
    return;
  }

  fetch('/api/student_sessions/' + encodeURIComponent(nfcId), { credentials: 'same-origin' })
    .then((r) => r.json())
    .then((sessions) => {
      const list = document.getElementById('sessionDetailList');
      const count = document.getElementById('sessCount');

      if (count) {
        count.textContent = `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`;
      }

      if (!list) return;

      if (!sessions.length) {
        list.innerHTML = '<div style="text-align:center;color:var(--muted);padding:32px;font-size:12px;"><i class="bi bi-calendar-x" style="font-size:28px;display:block;opacity:.2;margin-bottom:8px;"></i>No detailed session records found.</div>';
        return;
      }

      list.innerHTML = sessions
        .map((s, i) => `
    <div class="sess-card ${s.status}" style="${i > 0 ? 'margin-top:8px' : ''}">
      <div style="flex:1;min-width:0;">
        <div style="font-weight:600;font-size:13px;">${s.subject_name}${s.course_code ? ' <span style="font-family:monospace;font-size:10px;color:var(--accent);">[' + s.course_code + ']</span>' : ''}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px;display:flex;flex-wrap:wrap;gap:12px;">
          <span><i class="bi bi-person-badge"></i> ${s.teacher_name}</span>
          <span><i class="bi bi-grid"></i> ${s.section_key.replace(/\|/g, ' · ')}</span>
          <span><i class="bi bi-tags"></i> ${(String(s.class_type || 'lecture').toLowerCase() === 'laboratory' ? 'Laboratory' : 'Lecture')}</span>
          <span><i class="bi bi-clock"></i> ${s.time_slot}</span>
          <span><i class="bi bi-calendar3"></i> ${s.date}</span>
          ${s.units ? `<span><i class="bi bi-layers"></i> ${s.units} units</span>` : ''}
        </div>
        ${s.excuse_note ? `<div style="font-size:11px;color:var(--warning);margin-top:6px;"><i class="bi bi-info-circle"></i> Reason: <strong>${s.excuse_note}</strong></div>` : ''}
        ${s.tx_hash ? `<div style="font-size:10px;color:var(--muted);margin-top:6px;display:flex;align-items:center;gap:5px;">
          <i class="bi bi-blockchain"></i> TX: <code style="color:var(--accent);">${s.tx_hash.slice(0, 20)}...</code>
          <a href="https://sepolia.etherscan.io/tx/${s.tx_hash}" target="_blank" title="View on Etherscan" style="color:var(--muted);"><i class="bi bi-box-arrow-up-right"></i></a>
        </div>` : ''}
      </div>
      <span style="padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600;flex-shrink:0;
        ${s.status === 'present'
          ? 'background:rgba(16,185,129,.12);color:var(--success);border:1px solid rgba(16,185,129,.25);'
          : s.status === 'late'
            ? 'background:rgba(245,158,11,.1);color:var(--warning);border:1px solid rgba(245,158,11,.25);'
            : s.status === 'excused'
              ? 'background:rgba(96,165,250,.1);color:#60a5fa;border:1px solid rgba(96,165,250,.25);'
              : 'background:rgba(239,68,68,.1);color:var(--danger);border:1px solid rgba(239,68,68,.2);'}">
        ${s.status.charAt(0).toUpperCase() + s.status.slice(1)}
      </span>
    </div>
  `)
        .join('');
    })
    .catch(() => {
      const list = document.getElementById('sessionDetailList');
      if (list) {
        list.innerHTML = '<div style="color:var(--danger);text-align:center;padding:24px;font-size:12px;">Failed to load session records.</div>';
      }
    });
}

loadSessionRecords();
