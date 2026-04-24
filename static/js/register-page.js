// Register student page script: extracted from template for easier debugging.

let _pendingSubjects = [];

// PDF upload and autofill flow.
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('uploadBanner').classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file && file.type === 'application/pdf') {
    processPdf(file);
  } else {
    showBannerError('Please drop a PDF file.');
  }
}

function handlePdfUpload(input) {
  if (input.files && input.files[0]) processPdf(input.files[0]);
}

function processPdf(file) {
  document.getElementById('uploadBanner').className = 'upload-banner loading';
  document.getElementById('ubIcon').textContent = '⏳';
  document.getElementById('ubTitle').textContent = 'Reading PDF…';
  document.getElementById('ubSub').textContent = 'Extracting from ' + file.name;
  const btn = document.getElementById('btnUpload');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Parsing…';

  const fd = new FormData();
  fd.append('file', file);

  fetch('/parse_registration_pdf', { method: 'POST', credentials: 'same-origin', body: fd })
    .then((r) => {
      if (!r.ok && r.status === 302) throw new Error('Session expired.');
      const ct = r.headers.get('content-type') || '';
      if (!ct.includes('application/json')) throw new Error('Server error (' + r.status + ').');
      return r.json();
    })
    .then((data) => {
      if (data.error) {
        showBannerError(data.error);
        return;
      }
      autofill(data);
      showBannerSuccess(file.name);
      if (data.subjects && data.subjects.length) {
        _pendingSubjects = data.subjects;
        document.getElementById('pendingSubjectsJson').value = JSON.stringify(_pendingSubjects);
        showSubjectPreview(data.subjects);
      }
    })
    .catch((err) => showBannerError('Error: ' + err.message));
}

function autofill(d) {
  const map = {
    f_student_id: d.student_id,
    f_name: d.name,
    f_email: d.email,
    f_contact: d.contact,
    f_section: d.section,
    f_adviser: d.adviser,
    f_major: d.major,
    f_school_year: d.school_year,
    f_date_registered: d.date_registered,
  };
  for (const [id, val] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el && val) {
      el.value = val;
      highlight(el);
    }
  }

  if (d.semester) {
    const sel = document.getElementById('f_semester');
    for (const opt of sel.options) {
      if (opt.value.toLowerCase().includes(d.semester.toLowerCase())) {
        sel.value = opt.value;
        highlight(sel);
        break;
      }
    }
  }

  if (d.course) {
    const sel = document.getElementById('f_course');
    const allowed = ['BS Computer Science', 'BS Information Technology'];
    const match = allowed.find((c) => c.toLowerCase() === d.course.toLowerCase() || d.course.toLowerCase().includes(c.replace('BS ', '').toLowerCase()));
    if (match) {
      sel.value = match;
      highlight(sel);
    }
  }

  if (d.year_level) {
    const sel = document.getElementById('f_year_level');
    for (const opt of sel.options) {
      if (opt.value.toLowerCase() === d.year_level.toLowerCase()) {
        sel.value = opt.value;
        highlight(sel);
        break;
      }
    }
  }
}

function highlight(el) {
  el.style.transition = 'box-shadow .3s,border-color .3s';
  el.style.borderColor = 'var(--success)';
  el.style.boxShadow = '0 0 0 3px rgba(45,106,39,.15)';
  setTimeout(() => {
    el.style.borderColor = '';
    el.style.boxShadow = '';
  }, 2000);
}

function showBannerSuccess(filename) {
  document.getElementById('uploadBanner').className = 'upload-banner success';
  document.getElementById('ubIcon').textContent = '✅';
  document.getElementById('ubTitle').textContent = 'Filled from: ' + filename;
  document.getElementById('ubSub').textContent = 'Fields auto-populated. Subjects will be saved when you click Register.';
  const btn = document.getElementById('btnUpload');
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Re-upload';
}

function showBannerError(msg) {
  document.getElementById('uploadBanner').className = 'upload-banner error';
  document.getElementById('ubIcon').textContent = '❌';
  document.getElementById('ubTitle').textContent = 'Could not read PDF';
  document.getElementById('ubSub').textContent = msg;
  const btn = document.getElementById('btnUpload');
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-cloud-upload"></i> Try Again';
}

function showSubjectPreview(subjects) {
  document.getElementById('subjPreviewNote').textContent = subjects.length + ' subject(s) will be added on Register';
  document.getElementById('subjPreviewList').innerHTML = '<table class="subj-table"><thead><tr><th>Code</th><th>Subject Name</th><th>Units</th><th>Status</th></tr></thead><tbody>' + subjects.map((s) => {
    return '<tr><td><code>' + s.course_code + '</code></td><td>' + s.name + '</td><td style="color:var(--muted);">' + s.units + '</td><td style="color:var(--warning);"><i class="bi bi-clock"></i> Pending register</td></tr>';
  }).join('') + '</tbody></table>';
  document.getElementById('subjPreview').classList.add('show');
}

// HID NFC input handler: collects keystrokes from USB reader and commits on Enter.
const nfcHid = document.getElementById('nfcHidInput');
let nfcBuf = '';
let nfcTimer = null;
const NFC_TIMEOUT = 300;

function refocusNFC() {
  const tag = document.activeElement ? document.activeElement.tagName : '';
  if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
    nfcHid.focus();
  }
}

function applyUID(uid) {
  uid = uid.trim().toUpperCase();
  if (!uid || uid.length < 4) return;

  document.getElementById('nfc_id').value = uid;

  const strip = document.getElementById('nfcCardStrip');
  const icon = document.getElementById('nfcStripIcon');
  const title = document.getElementById('nfcStripTitle');
  const sub = document.getElementById('nfcStripSub');
  const display = document.getElementById('nfcUidDisplay');

  strip.className = 'nfc-card-strip captured';
  icon.textContent = '✅';
  title.textContent = 'Card Captured!';
  sub.textContent = 'NFC card UID recorded. Click Register to save.';
  display.textContent = uid;
  display.className = 'nfc-uid-display has-uid';

  const hiddenInput = document.getElementById('nfc_id');
  hiddenInput.classList.remove('is-invalid');
  const err = hiddenInput.parentNode.querySelector('.reg-err');
  if (err) err.remove();
}

nfcHid.addEventListener('keydown', function onNfcKeydown(e) {
  clearTimeout(nfcTimer);
  if (e.key === 'Enter') {
    const uid = nfcBuf.trim();
    nfcBuf = '';
    nfcHid.value = '';
    if (uid) applyUID(uid);
    return;
  }
  if (e.key.length === 1) {
    nfcBuf += e.key;
    nfcHid.value = nfcBuf;
  }
  nfcTimer = setTimeout(() => {
    const uid = nfcBuf.trim();
    nfcBuf = '';
    nfcHid.value = '';
    if (uid) applyUID(uid);
  }, NFC_TIMEOUT);
});

document.addEventListener('click', refocusNFC);
nfcHid.addEventListener('blur', () => setTimeout(refocusNFC, 150));
window.addEventListener('load', () => nfcHid.focus());
nfcHid.focus();

async function startMobileRegistrationNfc() {
  const btn = document.getElementById('mobileNfcRegisterBtn');
  const sub = document.getElementById('nfcStripSub');
  const title = document.getElementById('nfcStripTitle');
  if (btn.dataset.scanning === '1') {
    btn.dataset.scanning = '0';
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-phone"></i> Use Phone NFC Reader';
    title.textContent = 'Phone NFC stopped';
    sub.textContent = 'Tap "Use Phone NFC Reader" to start scanning again.';
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
    } catch (_) {
      return '';
    }
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
    title.textContent = 'Phone NFC not supported here';
    sub.textContent = 'Use Android Chrome with NFC enabled, then try again.';
    return;
  }
  try {
    btn.disabled = true;
    btn.dataset.scanning = '1';
    const ndef = new NDEFReader();
    await ndef.scan();
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-stop-circle"></i> Stop Phone NFC';
    title.textContent = 'Phone NFC active';
    sub.textContent = 'Tap the student card on your phone.';
    ndef.addEventListener('readingerror', () => {
      sub.textContent = 'Read error. Tap the card again.';
    });
    ndef.addEventListener('reading', (event) => {
      if (btn.dataset.scanning !== '1') return;
      const uid = extractUid(event);
      if (!uid) return;
      applyUID(uid);
    });
  } catch (err) {
    title.textContent = 'Could not start phone NFC';
    sub.textContent = 'Check browser permission and NFC setting, then retry.';
    btn.dataset.scanning = '0';
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-phone"></i> Use Phone NFC Reader';
  }
}

const mobileNfcRegisterBtn = document.getElementById('mobileNfcRegisterBtn');
if (mobileNfcRegisterBtn) {
  mobileNfcRegisterBtn.addEventListener('click', startMobileRegistrationNfc);
}

function previewStudentPhoto(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById('photoPreviewImg');
    const init = document.getElementById('photoPreviewInit');
    img.src = e.target.result;
    img.style.display = 'block';
    init.style.display = 'none';
    const wrap = document.getElementById('photoPreviewWrap');
    wrap.style.borderStyle = 'solid';
    wrap.style.borderColor = 'var(--accent)';
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

  document.querySelectorAll('.form-control.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
  document.querySelectorAll('.reg-err').forEach((el) => el.remove());

  req.forEach(({ id, msg }) => {
    const el = document.getElementById(id);
    if (!el) return;

    if (!el.value || !el.value.trim()) {
      if (id === 'nfc_id') {
        document.getElementById('nfcCardStrip').className = 'nfc-card-strip error';
        document.getElementById('nfcStripTitle').textContent = 'NFC card required';
        document.getElementById('nfcStripSub').textContent = 'Tap the student\'s NFC card on the reader before registering.';
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
  document.querySelectorAll('#registerForm .form-control').forEach((el) => {
    el.addEventListener('input', () => {
      el.classList.remove('is-invalid');
      const next = el.nextSibling;
      if (next && next.classList && next.classList.contains('reg-err')) next.remove();
    });
  });
});
