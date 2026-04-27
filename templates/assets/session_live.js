const sessId = "{{ sess_id }}";
const IS_SCHOOL_EVENT = {{ 'true' if is_school_event else 'false' }};
const gracePeriodMinutes = Number("{{ sess.grace_period or 15 }}") || 15;
const totalStudents = {{ section_students| length }};
let lastTimestamp = 0;
let pollInitialized = false;
const shownTaps = new Set();

// ── Popup gate ────────────────────────────────────────────────────────────
// popupAllowed is set true ONLY when a physical card tap is detected by
// the HID input handler. It is consumed (set false) after ONE popup fires.
// The poll() loop NEVER shows popups — it only updates the status list.
// This guarantees exactly one popup per physical card tap, no repeats.
let popupAllowed = false;
function openPopupGate() { popupAllowed = true; }
function consumePopupGate() { const v = popupAllowed; popupAllowed = false; return v; }

// ── NFC strip ─────────────────────────────────────────────────────────────
let stripTimer = null;
function updateNFCStrip(uid, colorClass, statusText, iconEmoji) {
  const strip = document.getElementById('nfcTapStrip');
  const uidEl = document.getElementById('nfcStripUid');
  const statEl = document.getElementById('nfcStripStatus');
  const iconEl = document.getElementById('nfcStripIcon');
  if (!strip || !uidEl) return;
  strip.classList.remove('active', 'warning', 'error');
  uidEl.classList.remove('flash-green', 'flash-yellow', 'flash-red');
  strip.classList.add(colorClass);
  uidEl.classList.add(colorClass === 'active' ? 'flash-green' : colorClass === 'warning' ? 'flash-yellow' : 'flash-red');
  uidEl.textContent = uid || 'Waiting for card tap…';
  statEl.textContent = statusText || '—';
  iconEl.textContent = iconEmoji || '💳';
  statEl.style.color = colorClass === 'active' ? 'var(--success)' : colorClass === 'warning' ? 'var(--warning)' : 'var(--danger)';
  clearTimeout(stripTimer);
  stripTimer = setTimeout(() => {
    strip.classList.remove('active', 'warning', 'error');
    uidEl.classList.remove('flash-green', 'flash-yellow', 'flash-red');
    uidEl.textContent = 'Waiting for card tap…';
    statEl.textContent = '—';
    statEl.style.color = 'var(--muted)';
    iconEl.textContent = '💳';
  }, 4000);
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(title, sub, colorClass, iconEmoji, duration = 4000) {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${colorClass}`;
  t.innerHTML = `<span class="toast-icon">${iconEmoji}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        ${sub ? `<div class="toast-sub">${sub}</div>` : ''}
      </div>`;
  c.appendChild(t);
  setTimeout(() => { t.classList.add('removing'); setTimeout(() => t.remove(), 260); }, duration);
}

// ── Modal ─────────────────────────────────────────────────────────────────
let modalTimer = null;
function openEndModal() { document.getElementById('endSessionModal').classList.add('show'); }
function closeEndModal() { document.getElementById('endSessionModal').classList.remove('show'); }

function showModal(type, name, studentId, message, time) {
  const overlay = document.getElementById('tapModalOverlay');
  const modal = document.getElementById('tapModal');
  const icon = document.getElementById('modalIcon');
  const status = document.getElementById('modalStatus');
  const mName = document.getElementById('modalName');
  const mId = document.getElementById('modalStudentId');
  const mMsg = document.getElementById('modalMessage');
  const mTime = document.getElementById('modalTime');
  if (!overlay || !modal) return;

  ['green', 'yellow', 'orange', 'red'].forEach(c => {
    modal.classList.remove(c); icon.classList.remove(c);
    status.classList.remove(c); mMsg.classList.remove(c);
  });
  const cfg = {
    'present': { cls: 'green', icon: '✔', label: 'PRESENT', msg: 'Attendance recorded successfully.' },
    'late': { cls: 'orange', icon: '⏱', label: 'LATE', msg: `Arrived after the ${gracePeriodMinutes}-minute grace period - marked Late.` },
    'warning': { cls: 'yellow', icon: '⚠', label: 'DUPLICATE TAP', msg: 'Already marked — this tap was not counted again.' },
    'invalid': { cls: 'red', icon: '✕', label: 'INVALID CARD', msg: message || 'This NFC card is not registered in the system.' },
  };
  const c = cfg[type] || cfg['invalid'];
  modal.classList.add(c.cls); icon.className = 'modal-icon-ring ' + c.cls; icon.textContent = c.icon;
  status.className = 'modal-status ' + c.cls; status.textContent = c.label;
  mMsg.className = 'modal-message ' + c.cls; mMsg.textContent = c.msg;
  mName.textContent = name || '—';
  mId.textContent = studentId ? 'ID: ' + studentId : '';
  mTime.textContent = time || '';
  overlay.classList.add('show');
  clearTimeout(modalTimer);
  modalTimer = setTimeout(() => overlay.classList.remove('show'), 3500);
}

const tapModalOverlay = document.getElementById('tapModalOverlay');
if (tapModalOverlay) {
  tapModalOverlay.addEventListener('click', function (e) {
    if (e.target === this) this.classList.remove('show');
  });
}

// ── Status update (used by both HID handler and poll) ─────────────────────
function updateStudentStatus(nfc_id, status, reason = '') {
  const row = document.getElementById('srow_' + nfc_id);
  const badge = document.getElementById('sbadge_' + nfc_id);
  const avt = document.getElementById('savt_' + nfc_id);
  const excBtn = document.getElementById('sexc_' + nfc_id);
  const reasEl = document.getElementById('sreason_' + nfc_id);
  const ereasEl = document.getElementById('ereason_' + nfc_id);
  if (!row) return;
  row.dataset.status = status;
  const map = {
    'present': { avCls: 'av-green', badgeCls: 'sb-present', label: '✔ Present' },
    'late': { avCls: 'av-yellow', badgeCls: 'sb-late', label: '⏱ Late' },
    'excused': { avCls: 'av-blue', badgeCls: 'sb-excused', label: '🔵 Excused' },
    'absent': { avCls: 'av-red', badgeCls: 'sb-absent', label: '✕ Absent' },
  };
  const s = map[status] || { avCls: 'av-gray', badgeCls: 'sb-unknown', label: '— Unknown' };
  if (avt) { ['av-green', 'av-yellow', 'av-blue', 'av-red', 'av-gray'].forEach(c => avt.classList.remove(c)); avt.classList.add(s.avCls); }
  if (badge) { badge.className = 'status-badge ' + s.badgeCls; badge.textContent = s.label; }
  if (excBtn) {
    const showExcuse = status !== 'excused';
    excBtn.classList.toggle('show-excuse', showExcuse);
    excBtn.style.display = showExcuse ? '' : 'none';
  }

  const updateReason = (el) => {
    if (!el) return;
    el.style.display = (status === 'excused' && reason) ? 'block' : 'none';
    if (reason) el.textContent = reason;
  };
  updateReason(reasEl);
  updateReason(ereasEl);
}

function updateCounts() {
  const rows = document.querySelectorAll('#statusList .student-row[data-status]');
  let present = 0, late = 0, absent = 0, excused = 0;
  rows.forEach(r => {
    const st = r.dataset.status;
    if (st === 'present') present++;
    else if (st === 'late') late++;
    else if (st === 'absent') absent++;
    else if (st === 'excused') excused++;
  });
  const presentEl = document.getElementById('sc_present');
  const lateEl = document.getElementById('sc_late');
  const absentEl = document.getElementById('sc_absent');
  const excusedEl = document.getElementById('sc_excused');
  if (presentEl) presentEl.textContent = present;
  if (lateEl) lateEl.textContent = late;
  if (absentEl) absentEl.textContent = absent;
  if (excusedEl) excusedEl.textContent = excused;
  const pCount = IS_SCHOOL_EVENT ? present : (present + late);
  const rate = totalStudents > 0 ? ((pCount / totalStudents) * 100).toFixed(1) : 0;
  const presentLabel = document.getElementById('presentLabel');
  const progressFill = document.getElementById('progressFill');
  const rateLabel = document.getElementById('rateLabel');
  if (presentLabel) presentLabel.textContent = pCount + ' students present';
  if (progressFill) progressFill.style.width = rate + '%';
  if (rateLabel) rateLabel.textContent = rate + '%';
}

// ── HID Keyboard NFC reader ───────────────────────────────────────────────
const nfcInput = document.getElementById('nfcHidInput');
let nfcBuffer = '';
let nfcTimer = null;
const NFC_TIMEOUT = 300;

function refocusNFC() {
  if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin') return;
  const tag = document.activeElement ? document.activeElement.tagName : '';
  const excuseOverlay = document.getElementById('excuseOverlay');
  const endSessionModal = document.getElementById('endSessionModal');
  const isModal = (excuseOverlay && excuseOverlay.classList.contains('show')) ||
    (endSessionModal && endSessionModal.classList.contains('show'));
  if (!isModal && tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
    if (nfcInput) nfcInput.focus();
  }
}

async function processNFCUid(uid) {
  if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin') {
    showToast('Admin View', 'NFC tapping is disabled for administrators.', 't-blue', '🛡');
    return;
  }
  uid = uid.trim().toUpperCase();
  if (!uid || uid.length < 4) return;
  openPopupGate();
  updateNFCStrip(uid, 'active', 'Reading…', '📡');
  try {
    const resp = await fetch('/mark_pico', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nfc_id: uid, sess_id: sessId })
    });
    const data = await resp.json();
    const status = data.status || '';
    if (status === 'ok') {
      const isLate = !IS_SCHOOL_EVENT && data.is_late;
      const label = isLate ? 'LATE' : 'PRESENT';
      const color = isLate ? 'warning' : 'active';
      const icon = isLate ? '⏱' : '✔';
      updateNFCStrip(uid, color, `${label} — ${data.name || uid}`, icon);
      updateStudentStatus(uid, isLate ? 'late' : 'present');
      updateCounts();
      if (consumePopupGate()) {
        showModal(isLate ? 'late' : 'present', data.name, data.student_id, '', data.time);
        showToast(data.name || uid, isLate ? `⏱ Marked LATE · ${data.time || ''}` : `✔ Marked PRESENT · ${data.time || ''}`, isLate ? 't-yellow' : 't-green', isLate ? '⏱' : '✔');
      }
    } else if (status === 'already_marked') {
      updateNFCStrip(uid, 'warning', `DUPLICATE — ${data.name || uid}`, '⚠');
      if (consumePopupGate()) {
        showModal('warning', data.name, data.student_id, '', '');
        showToast(data.name || uid, 'Already marked — not counted again.', 't-yellow', '⚠');
      }
    } else if (status === 'registration') {
      updateNFCStrip(uid, 'active', 'Sent to registration form', '📋');
      if (consumePopupGate()) {
        showToast('Registration Scan', `UID ${uid} sent to register form.`, 't-blue', '📋');
      }
    } else if (status === 'no_session') {
      updateNFCStrip(uid, 'error', 'No active session', '✕');
      if (consumePopupGate()) {
        showModal('invalid', 'No Session', '', 'No active session for this section.', uid);
        showToast('No Session', `UID: ${uid} — no active session.`, 't-red', '✕');
      }
    } else if (status === 'excused') {
      updateNFCStrip(uid, 'warning', 'Excused student tap blocked', '⚠');
      if (consumePopupGate()) {
        showModal('warning', 'Excused', '', data.message || 'Student is marked Excused and cannot tap in.', uid);
        showToast('Excused Student', data.message || 'Tap ignored for excused student.', 't-yellow', '⚠');
      }
    } else {
      updateNFCStrip(uid, 'error', 'Not registered', '✕');
      if (consumePopupGate()) {
        showModal('invalid', 'Unknown Card', '', data.message || 'Card not registered.', uid);
        showToast('Unknown Card', `UID: ${uid}`, 't-red', '✕');
      }
    }
  } catch (e) {
    updateNFCStrip(uid, 'error', 'Server error', '⚠');
    consumePopupGate();
    console.warn('NFC error:', e);
  }
}

if (nfcInput) {
  nfcInput.addEventListener('keydown', function (e) {
    clearTimeout(nfcTimer);
    if (e.key === 'Enter') {
      const uid = nfcBuffer.trim();
      nfcBuffer = ''; nfcInput.value = '';
      if (uid) processNFCUid(uid);
      return;
    }
    if (e.key.length === 1) { nfcBuffer += e.key; nfcInput.value = nfcBuffer; }
    nfcTimer = setTimeout(() => {
      const uid = nfcBuffer.trim();
      nfcBuffer = ''; nfcInput.value = '';
      if (uid) processNFCUid(uid);
    }, NFC_TIMEOUT);
  });
  nfcInput.addEventListener('blur', () => setTimeout(refocusNFC, 150));
}

document.addEventListener('click', refocusNFC);
document.addEventListener('keyup', refocusNFC);
window.addEventListener('load', () => { 
  if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin') {
    if (nfcInput) nfcInput.disabled = true;
    const mobileBtn = document.getElementById('mobileNfcSessionBtn');
    if (mobileBtn) {
      mobileBtn.disabled = true;
      mobileBtn.title = 'NFC tapping is disabled for administrators';
    }
    updateNFCStrip('', 'warning', 'Admin View - Tapping Disabled', '🛡');
  } else {
    if (nfcInput) nfcInput.focus();
  }
});

// ── Phone Web NFC integration ─────────────────────────────────────────────
async function startMobileSessionNfc() {
  const btn = document.getElementById('mobileNfcSessionBtn');
  if (!btn) return;
  if (btn.dataset.scanning === '1') {
    btn.dataset.scanning = '0';
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-phone"></i> Use Phone NFC Reader';
    updateNFCStrip('', 'warning', 'Phone NFC stopped', '📱');
    return;
  }

  const decodeRecordPayload = (record) => {
    try {
      const decoder = new TextDecoder();
      const bytes = new Uint8Array(record.data.buffer || record.data);
      if (!bytes.length) return '';
      if (record.recordType === 'text') {
        const langLen = bytes[0] & 0x3f;
        return decoder.decode(bytes.slice(1 + langLen)).trim();
      }
      if (record.recordType === 'url') {
        const prefixes = ['', 'http://www.', 'https://www.', 'http://', 'https://'];
        const prefix = prefixes[bytes[0]] || '';
        return (prefix + decoder.decode(bytes.slice(1))).trim();
      }
      return decoder.decode(bytes).trim();
    } catch (_) { return ''; }
  };

  const extractUid = (event) => {
    const fromSerial = String(event.serialNumber || '').replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    if (fromSerial) return fromSerial;
    const records = (event.message && event.message.records) ? Array.from(event.message.records) : [];
    for (const rec of records) {
      const raw = decodeRecordPayload(rec);
      const normalized = raw.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
      if (normalized.length >= 4) return normalized;
    }
    return '';
  };

  if (!('NDEFReader' in window)) {
    updateNFCStrip('', 'error', 'Phone NFC unavailable on this browser', '✕');
    return;
  }
  try {
    btn.disabled = true;
    btn.dataset.scanning = '1';
    const ndef = new NDEFReader();
    await ndef.scan();
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-stop-circle"></i> Stop Phone NFC';
    updateNFCStrip('', 'active', 'Phone NFC active - tap card on phone', '📱');
    ndef.addEventListener('readingerror', () => {
      updateNFCStrip('', 'warning', 'Read failed - try tapping again', '⚠');
    });
    ndef.addEventListener('reading', (event) => {
      if (btn.dataset.scanning !== '1') return;
      const uid = extractUid(event);
      if (!uid) return;
      processNFCUid(uid);
    });
  } catch (e) {
    btn.dataset.scanning = '0';
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-phone"></i> Use Phone NFC Reader';
    updateNFCStrip('', 'error', 'Unable to start phone NFC scanner', '✕');
  }
}

const mobileNfcBtn = document.getElementById('mobileNfcSessionBtn');
if (mobileNfcBtn) {
  mobileNfcBtn.addEventListener('click', startMobileSessionNfc);
}

// ── Poll loop — ONLY updates status list, NEVER shows popups ─────────────
async function poll() {
  try {
    const r = await fetch(`/api/session/${sessId}/poll?since=${lastTimestamp}`);
    const data = await r.json();

    if (!data.active) {
      if (pollInitialized) {
        // Show blockchain upload overlay and redirect to teacher dashboard
        const loadingEl = document.getElementById('blockchainLoadingModal');
        if (loadingEl) loadingEl.classList.add('show');
        setTimeout(() => { window.location.href = '/teacher?sess_ended=' + sessId; }, 1200);
      }
      return;
    }

    if (!pollInitialized) {
      pollInitialized = true;
      const presentSet = new Set(data.present_ids || []);
      const lateSet = new Set(IS_SCHOOL_EVENT ? [] : (data.late_ids || []));
      const excusedSet = new Set(IS_SCHOOL_EVENT ? [] : (data.excused_ids || []));
      document.querySelectorAll('#statusList .student-row[data-nfc]').forEach(row => {
        const nid = row.dataset.nfc;
        if (excusedSet.has(nid)) updateStudentStatus(nid, 'excused');
        else if (lateSet.has(nid)) updateStudentStatus(nid, 'late');
        else if (presentSet.has(nid)) updateStudentStatus(nid, 'present');
      });
      updateCounts();
      lastTimestamp = data.server_time || (Date.now() / 1000);
      setTimeout(poll, 1500);
      return;
    }

    if (data.new_taps && data.new_taps.length > 0) {
      let gotNew = false;
      data.new_taps.forEach(tap => {
        const tapKey = tap.nfc_id + '_' + tap.timestamp;
        if (shownTaps.has(tapKey)) return;
        shownTaps.add(tapKey);
        gotNew = true;
        const isLate = !IS_SCHOOL_EVENT && (data.late_ids || []).includes(tap.nfc_id);
        updateStudentStatus(tap.nfc_id, isLate ? 'late' : 'present');
        if (tap.timestamp && tap.timestamp > lastTimestamp)
          lastTimestamp = tap.timestamp + 0.001;
      });
      if (gotNew) updateCounts();
    }

    if ((!data.new_taps || !data.new_taps.length) &&
      (!data.new_warnings || !data.new_warnings.length) &&
      (!data.new_invalids || !data.new_invalids.length)) {
      if (data.server_time) lastTimestamp = data.server_time;
    }

  } catch (e) { console.warn('Poll error:', e); }
  setTimeout(poll, 1500);
}

poll();

// ── Excuse modal ──────────────────────────────────────────────────────────
function openExcuse(nfc_id, name) {
  document.getElementById('excuseNfc').value = nfc_id;
  document.getElementById('excuseName').textContent = name;
  document.getElementById('excuseReason').value = '';
  document.getElementById('excuseDetail').value = '';
  document.getElementById('excuseDetail').style.display = 'none';
  const filesWrap = document.getElementById('excuseFilesWrap');
  if (filesWrap) filesWrap.style.display = 'none';
  const filesEl = document.getElementById('excuseFiles');
  if (filesEl) filesEl.value = '';
  document.getElementById('excuseOverlay').classList.add('show');
}
function closeExcuse() {
  const overlay = document.getElementById('excuseOverlay');
  if (overlay) overlay.classList.remove('show');
  setTimeout(refocusNFC, 150);
}

document.addEventListener('DOMContentLoaded', function () {
  const reasonSelect = document.getElementById('excuseReason');
  const detailInput = document.getElementById('excuseDetail');
  const filesWrap = document.getElementById('excuseFilesWrap');
  const filesInput = document.getElementById('excuseFiles');
  const fileCount = document.getElementById('fileCount');
  if (reasonSelect) {
    reasonSelect.addEventListener('change', function () {
      const isOthers = this.value === 'others';
      detailInput.style.display = isOthers ? 'block' : 'none';
      if (!isOthers) detailInput.value = '';
      if (filesWrap) filesWrap.style.display = this.value ? 'block' : 'none';
    });
  }
  if (filesInput && fileCount) {
    filesInput.addEventListener('change', function () {
      const n = this.files.length;
      fileCount.textContent = n ? `${n} file${n > 1 ? 's' : ''} selected` : 'No files selected';
    });
  }
});

async function submitExcuse() {
  const nfc_id = document.getElementById('excuseNfc').value;
  const reason_type = document.getElementById('excuseReason').value || '';
  const reason_detail = (document.getElementById('excuseDetail').value || '').trim();
  const fileInput = document.getElementById('excuseFiles');

  if (!nfc_id) { showToast('Error', 'No student selected', 't-red', '✕'); return; }
  if (!reason_type) { showToast('Validation Error', 'Please select a reason', 't-red', '✕'); return; }
  if (reason_type === 'others' && !reason_detail) {
    showToast('Validation Error', 'Please provide details for "Others"', 't-red', '✕'); return;
  }

  const submitBtn = document.querySelector('#excuseOverlay .btn-excuse-submit');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Submitting…'; }

  const studentName = document.getElementById('excuseName').textContent;
  const reasonLabels = {
    sickness: 'Sickness / Illness', lbm: 'LBM', emergency: 'Family Emergency',
    bereavement: 'Bereavement', medical: 'Medical Appointment', accident: 'Accident / Injury',
    official: 'Official School Business', weather: 'Extreme Weather', transport: 'Transportation Problem',
    others: reason_detail || 'Others'
  };
  const reasonDisplay = reasonLabels[reason_type] || reason_type;

  const formData = new FormData();
  formData.append('nfc_id', nfc_id);
  formData.append('reason_type', reason_type);
  formData.append('reason_detail', reason_detail);
  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    for (let i = 0; i < fileInput.files.length; i++) {
      formData.append('attachments', fileInput.files[i]);
    }
  }

  try {
    const r = await fetch(`/teacher/session/${sessId}/excuse`, {
      method: 'POST',
      body: formData
    });
    const d = await r.json();
    if (!d.status || d.status !== 'ok') {
      console.warn('Excuse server error:', d.error || d.message);
      showToast('Server Warning', d.error || d.message || 'Failed to mark student as excused.', 't-red', '✕');
      return;
    }
    updateStudentStatus(nfc_id, 'excused', d.reason || reasonDisplay);
    updateCounts();
    closeExcuse();
    showToast(studentName || nfc_id, '🔵 Marked Excused — ' + (d.reason || reasonDisplay), 't-blue', '🔵');
  } catch (e) {
    console.warn('Excuse network error:', e);
    showToast('Network Warning', 'Could not save excuse. Please try again.', 't-red', '✕');
  } finally {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = 'Submit'; }
  }
}

// ── Search/filter ─────────────────────────────────────────────────────────
function filterEnrolled() {
  const q = document.getElementById('enrolledSearch').value.toLowerCase();
  document.querySelectorAll('#enrolledList .student-row').forEach(r => {
    r.style.display = (!q || r.dataset.enrollName.includes(q)) ? '' : 'none';
  });
}
function filterByStatus() {
  const st = document.getElementById('statusFilter').value;
  const q = document.getElementById('statusSearch').value.toLowerCase();
  document.querySelectorAll('#statusList .student-row').forEach(r => {
    r.style.display = ((!st || r.dataset.status === st) && (!q || r.dataset.statusName.includes(q))) ? '' : 'none';
  });
}
function filterStatus() { filterByStatus(); }
