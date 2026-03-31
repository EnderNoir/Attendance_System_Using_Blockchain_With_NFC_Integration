// Teacher create session page script: extracted from template for easier debugging.

function updateAddSectionKey() {
  const prog = document.getElementById('add_program').value;
  const year = document.getElementById('add_year').value;
  const sec = document.getElementById('add_section').value;
  const btn = document.getElementById('addBtn');
  const key = document.getElementById('add_section_key');
  if (prog && year && sec) {
    key.value = `${prog}|${year}|${sec}`;
    btn.disabled = false;
  } else {
    key.value = '';
    btn.disabled = true;
  }
}

function filterCards() {
  const q = document.getElementById('sf_q').value.toLowerCase();
  const prog = document.getElementById('sf_program').value;
  const yr = document.getElementById('sf_year').value;
  const sec = document.getElementById('sf_section').value;
  const st = document.getElementById('sf_status').value;
  let shown = 0;
  document.querySelectorAll('#subjectCardList .sess-card').forEach((c) => {
    const ok = (!q || c.dataset.subj.includes(q))
      && (!prog || c.dataset.program === prog)
      && (!yr || c.dataset.year === yr)
      && (!sec || c.dataset.section === sec)
      && (!st || c.dataset.status === st);
    c.style.display = ok ? '' : 'none';
    if (ok) shown += 1;
  });
  const emp = document.getElementById('sf_empty');
  if (emp) emp.style.display = shown === 0 ? 'block' : 'none';
}

function resetFilter() {
  ['sf_q', 'sf_program', 'sf_year', 'sf_section', 'sf_status'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  filterCards();
}

function parseTimeToMinutes(timeStr) {
  const m = timeStr.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!m) return null;
  let h = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  const ampm = m[3].toUpperCase();
  if (ampm === 'PM' && h !== 12) h += 12;
  if (ampm === 'AM' && h === 12) h = 0;
  return h * 60 + min;
}

function filterPastTimeSlots() {
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();

  document.querySelectorAll('.slot-select').forEach((sel) => {
    let firstAvailable = null;
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      const sep = opt.value.includes('–') ? '–' : '-';
      const parts = opt.value.split(sep);
      if (parts.length < 2) return;

      const endMins = parseTimeToMinutes(parts[1].trim());
      if (endMins === null) return;

      const isPast = endMins <= nowMinutes;
      opt.disabled = isPast;
      if (isPast) {
        opt.textContent = opt.value + ' (past)';
        opt.classList.add('slot-past');
      } else if (!firstAvailable) {
        firstAvailable = opt;
      }
    });
    if (firstAvailable && !sel.value) {
      sel.value = firstAvailable.value;
    }
  });
}

function validateStartForm(form) {
  const sel = form.querySelector('.slot-select');
  if (!sel.value) {
    showAppAlert('Please select a time slot.', 'Missing Time Slot');
    return false;
  }
  const selected = Array.from(sel.options).find((o) => o.value === sel.value);
  if (selected && selected.disabled) {
    showAppAlert('That time slot has already ended. Please select a current or future slot.', 'Invalid Time Slot');
    return false;
  }
  const grace = parseInt(form.querySelector('[name="grace_period"]').value, 10);
  if (isNaN(grace) || grace < 1 || grace > 120) {
    showAppAlert('Grace period must be between 1 and 120 minutes.', 'Invalid Grace Period');
    return false;
  }
  return true;
}

filterPastTimeSlots();
setInterval(filterPastTimeSlots, 60000);
