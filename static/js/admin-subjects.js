// Admin subjects page script: extracted from template for easier debugging.

let curSubj = null;

function openSubjModal(s){
  curSubj = s;
  document.getElementById('subjModalTitle').textContent = s.name;

  document.getElementById('subjInfoContent').innerHTML = `
    <div style="padding:16px 20px;">
      <div class="sec-title">// Subject Details</div>
      <div class="info-row"><span class="info-lbl">Subject Name</span><span class="info-val">${s.name}</span></div>
      <div class="info-row"><span class="info-lbl">Course Code</span><span class="info-val">${s.code||'—'}</span></div>
      <div class="info-row"><span class="info-lbl">Units</span><span class="info-val">${s.units} Units</span></div>
      <div class="info-row"><span class="info-lbl">Added By</span><span class="info-val">${s.created_by||'—'}</span></div>
      <div class="info-row"><span class="info-lbl">Added On</span><span class="info-val">${s.created_at||'—'}</span></div>
    </div>`;

  const unitsOpts = ['2','3'].map(v =>
    `<option value="${v}" ${s.units===v?'selected':''}>${v} Units</option>`
  ).join('');

  document.getElementById('subjEditContent').innerHTML = `
    <form method="POST" action="/admin/subjects/${s.sid}/rename" id="editSubjForm" onsubmit="return validateEdit()">
      <div style="padding:16px 20px 0;">
        <div class="sec-title">// Edit Subject</div>
        <div style="margin-bottom:12px;">
          <label style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:5px;">Subject Name *</label>
          <input class="s-input" id="edit_name" name="name" value="${s.name}" placeholder="Subject name" oninput="clearInvalid(this,'edit_name_err')"/>
          <div class="err-txt" id="edit_name_err">Subject name cannot be empty.</div>
        </div>
        <div class="edit-grid">
          <div>
            <label style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:5px;">Course Code</label>
            <input class="s-input" id="edit_code" name="course_code" value="${s.code}" placeholder="e.g. CS 201"/>
          </div>
          <div>
            <label style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;display:block;margin-bottom:5px;">Units</label>
            <select class="s-input" id="edit_units" name="units" style="appearance:none;cursor:pointer;">${unitsOpts}</select>
          </div>
        </div>
      </div>
      <div class="s-footer">
        <span class="s-msg" id="editMsg" style="display:none;"></span>
        <button type="button" class="back-btn" onclick="closeSubjModal()"><i class="bi bi-arrow-left"></i> Back</button>
        <button type="button" class="btn-primary" onclick="saveSubjectEdit()"><i class="bi bi-check-circle-fill"></i> Save Changes</button>
      </div>
    </form>`;

  document.getElementById('subjDeleteContent').innerHTML = `
    <div style="padding:20px;">
      <div class="sec-title">// Delete Subject</div>
      <div style="background:rgba(192,57,43,.06);border:1px solid rgba(192,57,43,.2);border-radius:9px;padding:12px 14px;font-size:13px;color:var(--danger);margin-bottom:16px;">
        <i class="bi bi-exclamation-triangle"></i> Deleting <strong>${s.name}</strong> will remove it from all teachers' schedules. This cannot be undone.
      </div>
      <form method="POST" action="/admin/subjects/delete/${s.sid}">
        <div class="s-footer" style="border:none;padding:0;">
          <button type="button" class="back-btn" onclick="closeSubjModal()"><i class="bi bi-arrow-left"></i> Back</button>
          <button type="submit" style="background:var(--danger);border:none;color:#fff;font-weight:700;border-radius:8px;padding:9px 18px;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:6px;"><i class="bi bi-trash"></i> Confirm Delete</button>
        </div>
      </form>
    </div>`;

  document.querySelectorAll('.spane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
  document.getElementById('spane-info').classList.add('active');
  document.querySelector('.stab').classList.add('active');
  document.getElementById('subjModal').classList.add('show');
}

function saveSubjectEdit() {
  if (!curSubj) return;
  const nameEl  = document.getElementById('edit_name');
  const codeEl  = document.getElementById('edit_code');
  const unitsEl = document.getElementById('edit_units');
  const msgEl   = document.getElementById('editMsg');

  if (!nameEl.value.trim()) {
    nameEl.classList.add('invalid');
    document.getElementById('edit_name_err').style.display = 'block';
    return;
  }

  fetch(`/admin/subjects/${curSubj.sid}/rename`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name:        nameEl.value.trim(),
      course_code: codeEl ? codeEl.value.trim() : curSubj.code,
      units:       unitsEl ? unitsEl.value : curSubj.units
    })
  })
  .then(r => r.json())
  .then(d => {
    if (msgEl) msgEl.style.display = 'block';
    if (d.ok) {
      if (msgEl) { msgEl.style.color = 'var(--success)'; msgEl.textContent = '✓ Subject updated.'; }
      setTimeout(() => { closeSubjModal(); location.reload(); }, 1000);
    } else {
      if (msgEl) { msgEl.style.color = 'var(--danger)'; msgEl.textContent = d.error || 'Error saving.'; }
    }
  })
  .catch(() => {
    if (msgEl) { msgEl.style.display = 'block'; msgEl.style.color = 'var(--danger)'; msgEl.textContent = 'Network error.'; }
  });
}

function validateEdit() {
  const n = document.getElementById('edit_name');
  if (!n.value.trim()) {
    n.classList.add('invalid');
    const e = document.getElementById('edit_name_err');
    if (e) e.style.display = 'block';
    return false;
  }
  return true;
}

function clearInvalid(el, errId) {
  el.classList.remove('invalid');
  const e = document.getElementById(errId);
  if (e) e.style.display = 'none';
}

function closeSubjModal() { document.getElementById('subjModal').classList.remove('show'); curSubj = null; }
function switchStab(id, btn){
  document.querySelectorAll('.spane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
  document.getElementById('spane-' + id).classList.add('active');
  btn.classList.add('active');
}
function validateAddSubj(){
  const n = document.getElementById('as_name');
  if (!n.value.trim()){
    n.classList.add('invalid');
    const e = document.getElementById('as_name_err');
    if (e) e.style.display = 'block';
    return false;
  }
  return true;
}

const totalSubj = Number(document.getElementById('subjectMeta')?.dataset?.total || '0');
function filterSubjects(){
  const units  = document.getElementById('sf_units').value;
  const search = document.getElementById('sf_search').value.toLowerCase();
  let shown = 0;
  document.querySelectorAll('#subjList .person-row').forEach(r => {
    const m = (!units || r.dataset.units === units) && (!search || r.dataset.name.includes(search) || r.dataset.code.includes(search));
    r.style.display = m ? '' : 'none'; if(m) shown++;
  });
  document.getElementById('sf_count').textContent = `${shown} of ${totalSubj}`;
  document.getElementById('sf_empty').style.display = shown === 0 ? 'block' : 'none';
}
function resetSubjFilters(){
  document.getElementById('sf_units').value = '';
  document.getElementById('sf_search').value = '';
  filterSubjects();
}
