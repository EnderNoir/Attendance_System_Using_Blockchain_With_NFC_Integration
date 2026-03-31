// Admin users page script: extracted from template for easier debugging.

let curFaUser = null;
const CAN_EDIT_ROLES = document.getElementById('facultyMeta')?.dataset?.canEdit === 'true';

function markRoleDirty(username) {
  const btn = document.getElementById('applyrole_' + username);
  if (btn) btn.disabled = false;
}

function applyRole(username) {
  const sel = document.getElementById('rolesel_' + username);
  const btn = document.getElementById('applyrole_' + username);
  const pill = document.getElementById('rolepill_' + username);
  if (!sel || !btn) return;
  const newRole = sel.value;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass"></i> …';
  fetch('/update_faculty', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: username, role: newRole})
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok) {
      btn.innerHTML = '<i class="bi bi-check-lg"></i> Applied!';
      if (pill) {
        const labels = {teacher: 'Teacher', admin: 'Admin', super_admin: 'Super Admin'};
        pill.textContent = labels[newRole] || newRole;
        pill.className = (newRole === 'admin' || newRole === 'super_admin') ? 'pill-a' : 'pill-t';
      }
      setTimeout(() => { btn.innerHTML = '<i class="bi bi-check-lg"></i> Apply'; btn.disabled = true; }, 2000);
    } else {
      btn.innerHTML = '<i class="bi bi-check-lg"></i> Apply';
      btn.disabled = false;
      showAppAlert('Error: ' + (d.error || 'Could not update role. Try again.'), 'Role Update Failed');
    }
  })
  .catch(() => {
    btn.innerHTML = '<i class="bi bi-check-lg"></i> Apply';
    btn.disabled = false;
    showAppAlert('Network error. Please try again.', 'Network Error');
  });
}

const CS_YEARS = ['1st Year','2nd Year','3rd Year','4th Year'];
const IT_YEARS = ['1st Year','2nd Year','3rd Year','4th Year'];
const SECS = ['A','B','C','D'];

function switchTab(id, btn) {
  document.querySelectorAll('.fa-tab-pane').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}

function switchFaTab(id, btn) {
  document.querySelectorAll('.fapane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.fatab').forEach(b => b.classList.remove('active'));
  document.getElementById('fapane-' + id).classList.add('active');
  btn.classList.add('active');
}

function buildSectionGrid(assignedSections) {
  const assigned = new Set(assignedSections || []);
  function courseBlock(course, prefix, years) {
    const rows = years.map(yr => {
      const checks = SECS.map(sec => {
        const val = `${course}|${yr}|${sec}`;
        const id = `fa_sec_${prefix}_${yr.replace(/ /g,'')}_${sec}`;
        const chk = assigned.has(val) ? 'checked' : '';
        return `<div class="sec-cb-wrap">
          <input type="checkbox" id="${id}" class="fa-sec-cb" value="${val}" ${chk}/>
          <label for="${id}">${sec}</label>
        </div>`;
      }).join('');
      return `<div class="year-row">
        <span class="year-label">${yr}</span>
        <div class="sec-checks">${checks}</div>
      </div>`;
    }).join('');
    return `<div class="section-course-block">
      <div class="section-course-header">
        <span class="section-course-title">${course}</span>
        <button type="button" class="btn-select-all" onclick="toggleAllSections('${prefix}',this)">Select All</button>
      </div>
      ${rows}
    </div>`;
  }
  return courseBlock('BS Computer Science', 'cs', CS_YEARS)
       + courseBlock('BS Information Technology', 'it', IT_YEARS);
}

function toggleAllSections(prefix, btn) {
  const course = prefix === 'cs' ? 'BS Computer Science' : 'BS Information Technology';
  const cbs = document.querySelectorAll(`.fa-sec-cb[value^="${course}"]`);
  const allChk = [...cbs].every(c => c.checked);
  cbs.forEach(c => c.checked = !allChk);
  btn.textContent = allChk ? 'Select All' : 'Deselect All';
}

function getSelectedSections() {
  return [...document.querySelectorAll('.fa-sec-cb:checked')].map(c => c.value);
}

function openFaModal(u) {
  curFaUser = u;
  document.getElementById('faTitle').textContent = u.name;
  const st = u.status;
  const pill = st==='approved'
    ? `<span class="pill-ok">Active</span>`
    : st==='pending'
    ? `<span class="pill-pend">Pending</span>`
    : `<span class="pill-rej">Rejected</span>`;
  document.getElementById('faSubPill').innerHTML = pill;

  const photoHtml = u.photo
    ? `<img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);flex-shrink:0;" id="faInfoAvatar"/>`
    : `<div id="faInfoAvatar" style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,#2D6A27,#F5C518);display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:#000;flex-shrink:0;">${u.name[0].toUpperCase()}</div>`;

  const secAccordionHtml = (u.sections && u.sections.length)
    ? buildSectionAccordion(u.sections)
    : '<span style="color:var(--muted);font-size:12px;">None assigned</span>';

  document.getElementById('faInfoContent').innerHTML = `
    <div style="padding:14px 0;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border);flex-wrap:wrap;">
        ${photoHtml}
        <div>
          <div style="font-size:16px;font-weight:700;">${u.name}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:3px;"><code>@${u.username}</code></div>
          <div style="font-size:10px;color:rgba(45,106,39,.5);margin-top:4px;"><i class="bi bi-pencil-square"></i> Go to Update tab to edit</div>
        </div>
      </div>
      <div class="sec-title">// Account Details</div>
      <div class="info-row"><span class="info-lbl">Full Name</span><span class="info-val">${u.name}</span></div>
      <div class="info-row"><span class="info-lbl">Username</span><span class="info-val"><code>@${u.username}</code></span></div>
      <div class="info-row"><span class="info-lbl">Email</span><span class="info-val">${u.email||'—'}</span></div>
      <div class="info-row"><span class="info-lbl">Role</span><span class="info-val"><span class="${u.role==='admin'?'pill-a':'pill-t'}">${u.role}</span></span></div>
      <div class="info-row"><span class="info-lbl">Status</span><span class="info-val">${pill}</span></div>
      <div class="info-row"><span class="info-lbl">Registered</span><span class="info-val">${u.created||'—'}</span></div>
      <div class="sec-title">// Assigned Sections</div>
      <div style="padding:4px 0;">${secAccordionHtml}</div>
    </div>`;

  if (!CAN_EDIT_ROLES) {
    document.querySelectorAll('.fapane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.fatab').forEach(b => b.classList.remove('active'));
    document.getElementById('fapane-info').classList.add('active');
    const firstTab = document.querySelector('.fatab');
    if (firstTab) firstTab.classList.add('active');
    document.getElementById('faModal').classList.add('show');
    return;
  }

  const roleOpts = ['teacher','admin'].map(v=>`<option value="${v}" ${u.role===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const stOpts = ['approved','pending','rejected'].map(v=>`<option value="${v}" ${st===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');

  const editPhotoInner = u.photo
    ? `<img src="/static/uploads/${u.photo}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;"/>`
    : `<span style="font-size:20px;font-weight:700;color:#000;">${u.name[0].toUpperCase()}</span>`;

  document.getElementById('faEditContent').innerHTML = `
    <div class="photo-upload-block">
      <div class="photo-av" id="faEditAvatar" onclick="document.getElementById('faPhotoInput').click()" title="Click to change photo" style="cursor:pointer;">${editPhotoInner}</div>
      <div>
        <div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"><i class="bi bi-camera-fill"></i> Profile Photo</div>
        <button type="button" onclick="document.getElementById('faPhotoInput').click()" style="background:rgba(45,106,39,.1);border:1px solid rgba(45,106,39,.2);color:var(--accent);border-radius:7px;padding:6px 12px;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:5px;font-family:'DM Sans',sans-serif;font-weight:600;">
          <i class="bi bi-upload"></i> Change Photo
        </button>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">JPG, PNG, WEBP · Max 5 MB</div>
      </div>
    </div>

    <div class="sec-title">// Account Information</div>
    <div class="fa-grid">
      <div class="fa-field" style="grid-column:1/-1">
        <span class="fa-label">Full Name *</span>
        <input class="fa-input" id="fa_name" value="${u.name}" placeholder="Prof. Maria Santos" oninput="validateFaField(this,'fa_name_err','required')"/>
        <span class="err-msg" id="fa_name_err">Full name is required.</span>
      </div>
      <div class="fa-field">
        <span class="fa-label">Username *</span>
        <input class="fa-input" id="fa_username" value="${u.username}" placeholder="msantos" oninput="validateFaField(this,'fa_uname_err','required')"/>
        <span class="err-msg" id="fa_uname_err">Username is required.</span>
      </div>
      <div class="fa-field">
        <span class="fa-label">Email Address</span>
        <input class="fa-input" id="fa_email" type="email" value="${u.email||''}" placeholder="msantos@school.edu" oninput="validateFaField(this,'fa_email_err','email')"/>
        <span class="err-msg" id="fa_email_err">Enter a valid email address.</span>
      </div>
      <div class="fa-field">
        <span class="fa-label">Role</span>
        <select class="fa-input" id="fa_role" style="appearance:none;">${roleOpts}</select>
      </div>
      <div class="fa-field">
        <span class="fa-label">Account Status</span>
        <select class="fa-input" id="fa_status" style="appearance:none;">${stOpts}</select>
      </div>
    </div>

    <div class="sec-title">// Change Password <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted);font-size:9px;">(leave blank to keep current)</span></div>
    <div class="fa-grid">
      <div class="fa-field">
        <span class="fa-label">New Password</span>
        <input class="fa-input" id="fa_pw" type="password" placeholder="Min. 6 characters" oninput="validateFaField(this,'fa_pw_err','minlen:6')"/>
        <span class="err-msg" id="fa_pw_err">Min. 6 characters.</span>
      </div>
      <div class="fa-field">
        <span class="fa-label">Confirm Password</span>
        <input class="fa-input" id="fa_pw2" type="password" placeholder="Repeat new password" oninput="checkFaPwMatch()"/>
        <span class="err-msg" id="fa_pw2_err">Passwords do not match.</span>
      </div>
    </div>

    <div class="sec-title">// Assigned Sections</div>
    <p style="font-size:12px;color:var(--muted);margin-bottom:10px;">Select which sections this faculty member handles. They will only see students from these sections.</p>
    <div id="faSectionGrid">${buildSectionGrid(u.sections)}</div>`;

  const isApproved = st==='approved';
  const isPending  = st==='pending';
  const isRejected = st==='rejected';

  document.getElementById('faActionsContent').innerHTML = `
    <div style="padding:4px 0;display:flex;flex-direction:column;gap:10px;">
      <div class="sec-title">// Account Actions</div>
      ${isPending ? `
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn-action-approve" id="btnApprove" onclick="doApprove()"><i class="bi bi-check-lg"></i> Approve Account</button>
          <button class="btn-action-reject"  id="btnReject"  onclick="doReject()"><i class="bi bi-x-lg"></i> Reject</button>
        </div>` : ''}
      ${isRejected ? `<button class="btn-action-restore" id="btnRestore" onclick="doApprove()"><i class="bi bi-arrow-counterclockwise"></i> Restore Account</button>` : ''}
      ${isApproved ? `<div style="font-size:12px;color:var(--muted);padding:6px 0;">This account is active. Use the <strong>Update</strong> tab to modify details or change status to rejected.</div>` : ''}
      <div id="faActionMsg" style="font-size:12px;display:none;padding:8px 12px;border-radius:8px;"></div>
      <div style="margin-top:8px;padding-top:12px;border-top:1px solid var(--border);">
        <div style="font-size:11px;color:var(--danger);font-weight:600;margin-bottom:8px;"><i class="bi bi-exclamation-triangle"></i> Danger Zone</div>
        <button class="btn-action-delete" id="btnDelete" onclick="doDelete()"><i class="bi bi-trash"></i> Delete Account Permanently</button>
      </div>
    </div>`;

  document.querySelectorAll('.fapane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.fatab').forEach(b => b.classList.remove('active'));
  document.getElementById('fapane-info').classList.add('active');
  document.querySelector('.fatab').classList.add('active');
  document.getElementById('faMsg').style.display = 'none';
  document.getElementById('faModal').classList.add('show');
}

function closeFaModal() {
  document.getElementById('faModal').classList.remove('show');
  curFaUser = null;
}

function uploadFaPhoto(input) {
  if (!input.files || !input.files[0] || !curFaUser) return;
  const fd = new FormData();
  fd.append('photo', input.files[0]);
  fd.append('person_id', curFaUser.username);
  fetch('/upload_photo', {method:'POST', credentials:'same-origin', body:fd})
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        const url = d.url + '?t=' + Date.now();
        const editAv = document.getElementById('faEditAvatar');
        if (editAv) { editAv.innerHTML = ''; editAv.style.overflow='hidden'; const img=document.createElement('img'); img.src=url; img.style='width:100%;height:100%;object-fit:cover;border-radius:50%;'; editAv.appendChild(img); }
        const infoAv = document.getElementById('faInfoAvatar');
        if (infoAv) { if (infoAv.tagName==='IMG') { infoAv.src=url; } else { const img=document.createElement('img'); img.src=url; img.style='width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);flex-shrink:0;'; infoAv.parentNode.replaceChild(img, infoAv); img.id='faInfoAvatar'; } }
        curFaUser.photo = d.filename;
      }
    });
  input.value = '';
}

function saveFaculty() {
  if (!CAN_EDIT_ROLES) return;
  if (!curFaUser) return;
  const v1 = validateFaField(document.getElementById('fa_name'),     'fa_name_err',  'required');
  const v2 = validateFaField(document.getElementById('fa_username'), 'fa_uname_err', 'required');
  const v3 = validateFaField(document.getElementById('fa_email'),    'fa_email_err', 'email');
  const pw  = document.getElementById('fa_pw') ? document.getElementById('fa_pw').value : '';
  const v4  = !pw || validateFaField(document.getElementById('fa_pw'), 'fa_pw_err', 'minlen:6');
  const v5  = checkFaPwMatch();
  if (!v1||!v2||!v3||!v4||!v5) return;

  const btn = document.getElementById('faSaveBtn');
  const msg = document.getElementById('faMsg');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass"></i> Saving…';

  fetch('/update_faculty', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      username:     curFaUser.username,
      full_name:    document.getElementById('fa_name').value.trim(),
      new_username: document.getElementById('fa_username').value.trim(),
      email:        document.getElementById('fa_email').value.trim(),
      role:         document.getElementById('fa_role').value,
      status:       document.getElementById('fa_status').value,
      new_password: pw || null,
      sections:     getSelectedSections()
    })
  })
  .then(r => r.json())
  .then(d => {
    msg.style.display = 'block';
    msg.style.color   = d.ok ? 'var(--success)' : 'var(--danger)';
    msg.textContent   = d.ok ? '✓ Account updated successfully.' : (d.error || 'Error saving.');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Save Changes';
    if (d.ok) setTimeout(() => { closeFaModal(); location.reload(); }, 1200);
  })
  .catch(() => {
    msg.style.display = 'block'; msg.style.color = 'var(--danger)'; msg.textContent = 'Network error.';
    btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Save Changes';
  });
}

function setActionBtnsDisabled(disabled) {
  ['btnApprove','btnReject','btnRestore','btnDelete'].forEach(id => { const el=document.getElementById(id); if(el) el.disabled=disabled; });
}

function showActionMsg(msg, isError) {
  const el = document.getElementById('faActionMsg');
  if (!el) return;
  el.style.display = 'block';
  el.style.background = isError ? 'rgba(192,57,43,.1)' : 'rgba(45,106,39,.1)';
  el.style.color = isError ? 'var(--danger)' : 'var(--success)';
  el.style.border = isError ? '1px solid rgba(192,57,43,.25)' : '1px solid rgba(45,106,39,.25)';
  el.textContent = msg;
}

function doAction(url, successMsg) {
  if (!curFaUser) return;
  setActionBtnsDisabled(true);
  showActionMsg('Processing…', false);
  fetch(url, {method:'POST', credentials:'same-origin', redirect:'follow'})
    .then(r => {
      if (r.ok || r.redirected) {
        showActionMsg('✓ ' + successMsg, false);
        setActionBtnsDisabled(false);
        setTimeout(() => { closeFaModal(); location.reload(); }, 1200);
      } else { showActionMsg('Error (status ' + r.status + '). Try again.', true); setActionBtnsDisabled(false); }
    })
    .catch(err => {
      console.warn('Fallback form submit:', err);
      const f = document.createElement('form'); f.method='POST'; f.action=url; document.body.appendChild(f); f.submit();
    });
}

function doApprove() { doAction('/admin/approve/' + encodeURIComponent(curFaUser.username), 'Account approved.'); }
function doReject()  { doAction('/admin/reject/' + encodeURIComponent(curFaUser.username), 'Account rejected.'); }
async function doDelete()  {
  const ok = await showAppConfirm('Permanently delete ' + curFaUser.name + '? This cannot be undone.', 'Delete Faculty Account', 'Delete', 'Cancel');
  if (!ok) return;
  doAction('/admin/delete/' + encodeURIComponent(curFaUser.username), 'Account deleted.');
}

function validateFaField(input, errId, rule) {
  const err = document.getElementById(errId);
  let valid = true;
  if (rule==='required') valid = input.value.trim().length>0;
  else if (rule==='email') valid = !input.value.trim()||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value.trim());
  else if (rule.startsWith('minlen:')) { const min=parseInt(rule.split(':')[1]); valid=!input.value||input.value.length>=min; }
  input.classList.toggle('invalid', !valid);
  if (err) err.style.display = valid ? 'none' : 'block';
  return valid;
}

function checkFaPwMatch() {
  const pw = document.getElementById('fa_pw') ? document.getElementById('fa_pw').value : '';
  const pw2 = document.getElementById('fa_pw2') ? document.getElementById('fa_pw2').value : '';
  const err = document.getElementById('fa_pw2_err');
  const inp = document.getElementById('fa_pw2');
  const match = !pw||!pw2||pw===pw2;
  if (err) err.style.display = match ? 'none' : 'block';
  if (inp) inp.classList.toggle('invalid', !match);
  return match;
}
