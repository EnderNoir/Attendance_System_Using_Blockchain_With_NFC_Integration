// ═══ Advanced Create ID Logic ═══
let cidSelectedStudents = [];
let cidPreviewIdx = 0;
let cidTemplates = { front: null, back: null };
let cidCustomVariables = [];
let cidCurrentView = 'front';
let cidCustomType = 'text';
let cidCustomImgData = null;
let cidMode = 'batch';
let cidPdfCancelled = false;
let cidShowBorders = true;
let cidHistory = [];
const cidMaxHistory = 30;

function cidPushHistory() {
  // Capture global state
  const state = JSON.stringify({
    elements: cidElements.map(e => {
      const { history, ...rest } = e; // Don't include history in the snapshot
      return rest;
    }),
    vars: cidCustomVariables
  });
  if (cidHistory.length > 0 && cidHistory[cidHistory.length - 1] === state) return;
  cidHistory.push(state);
  if (cidHistory.length > cidMaxHistory) cidHistory.shift();
  
  // Also push to per-element history
  cidElements.forEach(el => {
    if (!el.history) el.history = [];
    const propState = JSON.stringify({
      x: el.x, y: el.y, w: el.w, h: el.h, size: el.size, color: el.color, font: el.font, weight: el.weight, align: el.align, text_w: el.text_w, side: el.side, visible: el.visible
    });
    if (el.history.length === 0 || el.history[el.history.length - 1] !== propState) {
      el.history.push(propState);
      if (el.history.length > 20) el.history.shift();
    }
  });

  const undoBtn = document.getElementById('cid_undo_btn');
  if (undoBtn) undoBtn.disabled = false;
}

window.cidUndoElement = function(id, e) {
  if (e) e.stopPropagation();
  const el = cidElements.find(d => d.id === id);
  if (!el || !el.history || el.history.length < 2) return;
  
  el.history.pop(); // Remove current
  const last = JSON.parse(el.history[el.history.length - 1]);
  Object.assign(el, last);
  
  cidRenderElementList();
  cidInjectElements();
};

window.cidToggleBorders = function() {
  cidShowBorders = !cidShowBorders;
  const btn = document.getElementById('cid_border_toggle_btn');
  if (btn) {
    btn.innerHTML = `<i class="bi bi-eye${cidShowBorders?'-slash':''}"></i> ${cidShowBorders?'Hide':'Show'} Borders`;
  }
  cidInjectElements();
};

window.cidUndo = function() {
  if (cidHistory.length < 2) {
    if (cidHistory.length === 1) {
      // Just one state, can't really "undo" to anything earlier
    }
    return;
  }
  // Pop the current state (the one we just pushed before calling undo)
  cidHistory.pop();
  const lastState = JSON.parse(cidHistory[cidHistory.length - 1]);
  cidElements = lastState.elements;
  cidCustomVariables = lastState.vars;
  
  cidRenderElementList();
  cidInjectElements();
  if (cidActiveElId) cidSelectElement(cidActiveElId);
  
  if (cidHistory.length <= 1) {
    const undoBtn = document.getElementById('cid_undo_btn');
    if (undoBtn) undoBtn.disabled = true;
  }
};


let cidElements = [
  { id:'photo', label:'Student Photo', type:'photo', side:'front', x:20, y:20, w:80, h:80, shape:'square', visible:true },
  { id:'name', label:'Full Name', type:'text', side:'front', x:20, y:110, text_w:283.5, size:16, font:'Inter', color:'#000000', weight:'700', align:'center', visible:true },
  { id:'course', label:'Program', type:'text', side:'front', x:20, y:132, text_w:283.5, size:12, font:'Inter', color:'#333333', weight:'500', align:'center', visible:true },
  { id:'id_num', label:'Student ID', type:'text', side:'front', x:20, y:150, text_w:283.5, size:11, font:'Space Mono', color:'#555555', weight:'400', align:'center', visible:true },
  { id:'school_year', label:'School Year', type:'text', side:'back', x:20, y:30, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'contact_number', label:'Contact Number', type:'text', side:'back', x:20, y:45, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'email', label:'Email Address', type:'text', side:'back', x:20, y:60, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'year_level', label:'Year Level', type:'text', side:'back', x:20, y:75, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'semester', label:'Semester', type:'text', side:'back', x:20, y:90, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true }
];
let cidActiveElId = null;

// ── Modal Open / Close ──
function openCreateIdModal() {
  document.getElementById('createIdModal').classList.add('show');
  cidUpdateCount();
  cidRenderElementList();
  // Initial state for undo
  if (cidHistory.length === 0) cidPushHistory();
}
function closeCreateIdModal() {
  document.getElementById('createIdModal').classList.remove('show');
}

// ── Mode Toggle (Single vs Batch) ──
function cidSetMode(mode) {
  cidMode = mode;
  document.getElementById('cid_btn_batch').className = mode === 'batch' ? 'btn-primary' : 'btn-vr';
  document.getElementById('cid_btn_single').className = mode === 'single' ? 'btn-primary' : 'btn-vr';
  document.getElementById('cid_batch_fields').style.display = mode === 'batch' ? 'block' : 'none';
  document.getElementById('cid_single_fields').style.display = mode === 'single' ? 'block' : 'none';
  if (mode === 'batch') cidUpdateCount();
}

function cidSingleSearch() {
  const q = (document.getElementById('cid_single_search').value || '').toLowerCase();
  const all = window.DASHBOARD_BOOTSTRAP.students || [];
  const box = document.getElementById('cid_single_results');
  if (q.length < 2) { box.innerHTML = ''; return; }
  const matches = all.filter(s => (s.name||'').toLowerCase().includes(q) || (s.student_id||'').toLowerCase().includes(q)).slice(0, 8);
  box.innerHTML = matches.map((s, i) => `<div onclick="cidPickSingle(${i})" style="padding:6px 10px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;display:flex;justify-content:space-between;" class="cid-single-result" data-idx="${i}"><span>${s.name}</span><span style="color:var(--muted);font-size:10px;">${s.student_id||''}</span></div>`).join('');
  box._matches = matches;
}

function cidPickSingle(idx) {
  const box = document.getElementById('cid_single_results');
  const s = box._matches[idx];
  cidSelectedStudents = [s];
  cidPreviewIdx = 0;
  document.getElementById('cid_single_selected').innerHTML = `<i class="bi bi-check-circle"></i> Selected: ${s.name} (${s.student_id||'N/A'})`;
  cidCheckReady();
  cidUpdatePreview();
}

// ── Batch Count ──
function cidUpdateCount() {
  const prog = document.getElementById('cid_program').value;
  const year = document.getElementById('cid_year').value;
  const sem = document.getElementById('cid_semester').value;
  const sec = document.getElementById('cid_section').value;
  const all = window.DASHBOARD_BOOTSTRAP.students || [];
  cidSelectedStudents = all.filter(s =>
    (!prog || s.course === prog) && (!year || s.year_level === year) &&
    (!sem || s.semester === sem) && (!sec || s.section === sec)
  );
  document.getElementById('cid_count').textContent = cidSelectedStudents.length;
  cidPreviewIdx = 0;
  cidCheckReady();
  cidUpdatePreview();
}

// ── File Upload ──
function cidHandleFile(input, side) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  document.getElementById(`cid_${side}_filename`).textContent = file.name;
  const reader = new FileReader();
  reader.onload = function(e) {
    cidTemplates[side] = e.target.result;
    document.getElementById(`cid_card_${side}_bg`).src = e.target.result;
    cidCheckReady();
    cidUpdatePreview();
  };
  reader.readAsDataURL(file);
}

// ── Orientation ──
function cidUpdateOrientation() {
  const o = document.querySelector('input[name="cid_orientation"]:checked').value;
  document.querySelectorAll('.cid-card-box').forEach(box => {
    if (o === 'portrait') { box.style.width = '204px'; box.style.height = '323.5px'; }
    else { box.style.width = '323.5px'; box.style.height = '204px'; }
  });
}

// ── Front/Back View Toggle ──
function cidSetView(view) {
  cidCurrentView = view;
  document.getElementById('cid_card_front').style.display = view === 'front' ? 'block' : 'none';
  document.getElementById('cid_card_back').style.display = view === 'back' ? 'block' : 'none';
  const fb = document.getElementById('cid_view_front_btn');
  const bb = document.getElementById('cid_view_back_btn');
  fb.style.background = view === 'front' ? 'var(--accent)' : 'transparent';
  fb.style.color = view === 'front' ? '#000' : '#fff';
  bb.style.background = view === 'back' ? 'var(--accent)' : 'transparent';
  bb.style.color = view === 'back' ? '#000' : '#fff';
}

// ── Ready Check ──
function cidCheckReady() {
  const btn = document.getElementById('cid_generate_btn');
  const ready = cidSelectedStudents.length > 0 && cidTemplates.front && cidTemplates.back;
  btn.disabled = !ready;
  if (ready) {
    document.getElementById('cid_no_template_msg').style.display = 'none';
    document.getElementById('cid_preview_container').style.display = 'block';
    document.getElementById('cid_preview_nav').style.display = 'flex';
  } else {
    document.getElementById('cid_no_template_msg').style.display = 'block';
    document.getElementById('cid_preview_container').style.display = 'none';
    document.getElementById('cid_preview_nav').style.display = 'none';
  }
}

window.cidToggleVisible = function(id, e) {
  e.stopPropagation();
  cidPushHistory();
  const el = cidElements.find(d => d.id === id);
  el.visible = !el.visible;
  
  if (el.visible) {
    cidResetPosition(id);
  }
  
  cidRenderElementList();
  cidInjectElements();
};

window.cidResetPosition = function(id, e) {
  // Now behaves as Per-Element Undo
  cidUndoElement(id, e);
};

function cidGetVal(id, s) {
  const el = cidElements.find(e => e.id === id);
  if (el && el.override_val) return el.override_val;
  if (id === 'name') return s.name || '[Full Name]';
  if (id === 'course') return s.course || s.program || '[Program]';
  if (id === 'id_num') return s.student_id || '[Student ID]';
  if (id === 'school_year') return s.school_year || '[School Year]';
  if (id === 'contact_number') return s.contact || s.contact_number || s.guardian_contact || '[Contact Number]';
  if (id === 'email') return s.email || '[Email Address]';
  if (id === 'year_level') return s.year_level || '[Year Level]';
  if (id === 'semester') return s.semester || '[Semester]';
  const cv = cidCustomVariables.find(v => v.id === id);
  return cv ? cv.val : '';
}

function cidRenderElementList() {
  const list = document.getElementById('cid_element_list');
  list.innerHTML = '';
  cidElements.forEach(el => {
    const isVis = el.visible !== false;
    const isCustom = el.id.startsWith('cv_') || el.id.startsWith('custom_');
    const div = document.createElement('div');
    div.className = 'cid-el-item';
    if (cidActiveElId === el.id) div.classList.add('active');
    div.style.display = 'flex';
    div.style.alignItems = 'center';
    div.style.padding = '6px 8px';
    div.style.border = '1px solid ' + (cidActiveElId === el.id ? 'var(--accent)' : 'transparent');
    div.style.borderRadius = '6px';
    div.style.background = cidActiveElId === el.id ? 'rgba(245,158,11,.05)' : 'transparent';
    div.style.marginBottom = '4px';
    div.style.cursor = 'pointer';
    div.onclick = () => cidSelectElement(el.id);
    
    const canUndo = el.history && el.history.length >= 2;

    div.innerHTML = `
      <i class="bi bi-${el.type==='photo'||el.type==='custom_img'?'image':'fonts'}" style="opacity:0.5;font-size:12px;margin-right:8px;"></i>
      <span style="font-size:12px;font-weight:600;flex:1;opacity:${isVis?1:0.4}">${el.label}</span>
      <span style="font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-right:8px;background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;">${el.side}</span>
      <div style="display:flex;gap:4px;">
        <button onclick="cidUndoElement('${el.id}', event)" style="background:none;border:none;color:var(--text);cursor:pointer;padding:0 3px;opacity:${canUndo?1:0.2}" title="Undo changes for this element" ${canUndo?'':'disabled'}><i class="bi bi-arrow-counterclockwise"></i></button>
        ${isCustom && el.type==='text' ? `<button onclick="cidEditLabel('${el.id}', event)" style="background:none;border:none;color:var(--text);cursor:pointer;padding:0 3px;" title="Edit Text"><i class="bi bi-pencil"></i></button>` : ''}
        <button onclick="cidToggleVisible('${el.id}', event)" style="background:none;border:none;color:var(--text);cursor:pointer;padding:0 3px;"><i class="bi bi-eye${isVis?'':'-slash'}"></i></button>
        ${isCustom ? `<button onclick="cidDeleteElement('${el.id}', event)" style="background:none;border:none;color:var(--danger);cursor:pointer;padding:0 3px;" title="Delete"><i class="bi bi-trash"></i></button>` : ''}
      </div>
    `;
    list.appendChild(div);
  });
}

function cidShowEditModal(el) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'app-dialog-backdrop show';
    overlay.style.zIndex = '2000000';
    overlay.onclick = e => { if (e.target === overlay) close(); };
    
    const box = document.createElement('div');
    box.className = 'app-dialog-box';
    
    const head = document.createElement('div');
    head.className = 'app-dialog-head';
    head.innerHTML = '<div class="app-dialog-title">Edit Variable</div><button type="button" class="app-dialog-close"><i class="bi bi-x"></i></button>';
    head.querySelector('button').onclick = close;
    
    const body = document.createElement('div');
    body.className = 'app-dialog-body';
    body.innerHTML = `
      <div style="margin-bottom:16px;">
        <label style="display:block;font-size:12px;font-weight:600;margin-bottom:6px;color:var(--text);">Variable Name</label>
        <input type="text" id="edit_lbl_input" class="upd-input" style="width:100%;font-size:14px;padding:8px;" value="${el.label}" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;margin-bottom:6px;color:var(--text);">Static Content (Optional)</label>
        <input type="text" id="edit_val_input" class="upd-input" style="width:100%;font-size:14px;padding:8px;" placeholder="Leave blank to use database value" value="${el.override_val || ''}" />
        <div style="font-size:11px;color:var(--muted);margin-top:6px;">Set a static text value to override the dynamic data for all IDs.</div>
      </div>
    `;
    
    const actions = document.createElement('div');
    actions.className = 'app-dialog-actions';
    actions.innerHTML = '<button type="button" class="btn-outline">Cancel</button><button type="button" class="btn-primary">Save Changes</button>';
    actions.querySelector('.btn-outline').onclick = close;
    actions.querySelector('.btn-primary').onclick = () => {
      const newLbl = body.querySelector('#edit_lbl_input').value.trim();
      const newVal = body.querySelector('#edit_val_input').value.trim();
      document.body.removeChild(overlay);
      resolve({ label: newLbl, val: newVal });
    };
    
    box.appendChild(head);
    box.appendChild(body);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    
    function close() {
      document.body.removeChild(overlay);
      resolve(null);
    }
  });
}

window.cidEditLabel = async function(id, e) {
  if (e) e.stopPropagation();
  const el = cidElements.find(d => d.id === id);
  if (!el) return;
  const res = await cidShowEditModal(el);
  if (res) {
    cidPushHistory();
    if (res.label) el.label = res.label;
    el.override_val = res.val !== '' ? res.val : null;
    cidRenderElementList();
    cidInjectElements();
  }
};

window.cidDeleteElement = async function(id, e) {
  e.stopPropagation();
  const dialog = document.getElementById('appDialog');
  const oldZ = dialog ? dialog.style.zIndex : '';
  if (dialog) dialog.style.zIndex = '2000001';
  if(await showAppConfirm('Delete this variable from the ID?')) {
    cidPushHistory();
    cidElements = cidElements.filter(d => d.id !== id);
    if (cidActiveElId === id) cidActiveElId = null;
    cidRenderElementList();
    cidInjectElements();
    cidApplyStyle();
  }
  if (dialog) dialog.style.zIndex = oldZ;
};

// ── Inject draggable elements into preview cards ──
function cidInjectElements() {
  const front = document.getElementById('cid_front_elements');
  const back = document.getElementById('cid_back_elements');
  front.innerHTML = ''; back.innerHTML = '';
  const s = cidSelectedStudents[cidPreviewIdx] || {};

  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  const borderW = (1.5 / actualScale) + 'px';

  cidElements.forEach(el => {
    const div = document.createElement('div');
    div.className = 'cid-draggable' + (el.type === 'text' ? ' cid-text' : '');
    div.id = 'view_el_' + el.id;
    div.style.left = el.x + 'px';
    div.style.top = el.y + 'px';
    div.style.position = 'absolute';
    if (el.visible === false) div.style.opacity = '0.4';

    if (el.type === 'text') {
      div.style.fontSize = el.size + 'px';
      div.style.fontFamily = '"' + el.font + '"';
      div.style.color = el.color;
      div.style.fontWeight = el.weight;
      div.style.lineHeight = '1';
      div.style.padding = '0';
      div.style.margin = '0';
      div.style.overflow = 'hidden';
      
      if (el.text_w) {
        div.style.width = el.text_w + 'px';
        div.style.whiteSpace = 'normal';
        div.style.wordBreak = 'break-word';
      } else {
        div.style.whiteSpace = 'nowrap';
      }
      div.style.textAlign = el.align || 'left';
      div.classList.add('cid-render-el');
      div.textContent = cidGetVal(el.id, s);
    } else if (el.type === 'custom_img') {
      div.style.width = (el.w||60) + 'px'; div.style.height = (el.h||60) + 'px';
      div.style.borderRadius = '4px'; div.style.overflow = 'hidden';
      div.classList.add('cid-render-el');
      if (el.imgData) div.innerHTML = `<img src="${el.imgData}" style="width:100%;height:100%;object-fit:contain;pointer-events:none;">`;
    } else { // photo
      div.style.width = (el.w||80) + 'px'; div.style.height = (el.h||80) + 'px';
      div.style.borderRadius = el.shape === 'circle' ? '50%' : '6px'; div.style.background = 'rgba(0,0,0,.08)';
      div.classList.add('cid-render-el');
      const pf = (window.DASHBOARD_BOOTSTRAP.photos||{})[s.nfc_id];
      if (pf) div.innerHTML = `<img src="/static/uploads/${pf}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;pointer-events:none;">`;
      else { div.style.display='flex'; div.style.alignItems='center'; div.style.justifyContent='center'; div.innerHTML='<i class="bi bi-person" style="font-size:20px;opacity:.3;"></i>'; }
    }
    
    if (cidShowBorders && el.visible !== false) {
      div.style.border = `${borderW} solid #F5C518`;
      if (cidActiveElId === el.id) div.style.boxShadow = `0 0 0 ${1/actualScale}px var(--accent)`;

      const handles = ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'];
      handles.forEach(dir => {
        const handle = document.createElement('div');
        handle.className = 'cid-resize-handle';
        handle.style.position = 'absolute';
        handle.style.zIndex = '10';
        handle.style.background = cidActiveElId === el.id ? 'var(--accent)' : '#F5C518';
        handle.style.border = '1px solid #000';
        const sizeVal = 12 / actualScale;
        const size = sizeVal + 'px';
        const offset = -(sizeVal / 2) + 'px';

        if (dir.includes('n')) handle.style.top = offset;
        else if (dir.includes('s')) handle.style.bottom = offset;
        else { handle.style.top = '50%'; handle.style.marginTop = offset; }

        if (dir.includes('w')) handle.style.left = offset;
        else if (dir.includes('e')) handle.style.right = offset;
        else { handle.style.left = '50%'; handle.style.marginLeft = offset; }

        handle.style.width = size; handle.style.height = size;
        handle.style.cursor = dir + '-resize';
        handle.onmousedown = e => {
          e.stopPropagation();
          cidResizingId = el.id;
          cidResizeDir = dir;
          cidResizeStart = { x: e.clientX, y: e.clientY, w: div.offsetWidth, h: div.offsetHeight, top: el.y, left: el.x };
          cidPushHistory();
        };
        div.appendChild(handle);
      });
    }
    div.onclick = e => { e.stopPropagation(); cidSelectElement(el.id); };
    (el.side === 'front' ? front : back).appendChild(div);
  });
}



// ── Select & Style Element ──
function cidSelectElement(id) {
  cidActiveElId = id;
  const el = cidElements.find(e => e.id === id);
  cidRenderElementList();
  const panel = document.getElementById('cid_style_panel');
  panel.style.display = 'block';
  document.getElementById('cid_style_title').textContent = 'Styling: ' + el.label;

  const textFields = document.getElementById('cid_text_style_fields');
  const photoField = document.getElementById('cid_photo_size_field');

  if (el.type === 'text') {
    textFields.style.display = 'grid';
    photoField.style.display = 'none';
    document.getElementById('cid_st_font').value = el.font;
    const fontSel = document.getElementById('cid_st_font');
    if (!Array.from(fontSel.options).some(o => o.value === el.font)) {
      const opt = document.createElement('option');
      opt.value = el.font; opt.textContent = el.font;
      fontSel.insertBefore(opt, fontSel.lastElementChild);
    }
    fontSel.value = el.font;
    const isCustom = fontSel.selectedIndex > 13 && fontSel.value !== '_custom';
    document.getElementById('cid_st_font_remove').style.display = isCustom ? 'block' : 'none';
    if (el.font === '_custom') document.getElementById('cid_st_font_custom_group').style.display = 'flex';
    else document.getElementById('cid_st_font_custom_group').style.display = 'none';
    
    document.getElementById('cid_st_size').value = el.size;
    document.getElementById('cid_st_weight').value = el.weight || '400';
    document.getElementById('cid_st_align').value = el.align || 'left';
    document.getElementById('cid_st_color_picker').value = el.color.startsWith('#') ? el.color : '#000000';
    document.getElementById('cid_st_color_text').value = el.color;
  } else {
    textFields.style.display = 'none';
    photoField.style.display = 'flex';
    document.getElementById('cid_st_photo_size').value = el.w || 80;
    document.getElementById('cid_st_photo_shape').value = el.shape || 'square';
  }
}

function cidApplyStyle() {
  if (!cidActiveElId) return;
  cidPushHistory();
  const el = cidElements.find(e => e.id === cidActiveElId);
  if (el.type === 'text') {
    const fontSel = document.getElementById('cid_st_font');
    let font = fontSel.value;
    const isCustom = fontSel.selectedIndex > 13 && font !== '_custom';
    document.getElementById('cid_st_font_remove').style.display = isCustom ? 'block' : 'none';
    const customGrp = document.getElementById('cid_st_font_custom_group');
    if (font === '_custom') {
      customGrp.style.display = 'flex';
      font = document.getElementById('cid_st_font_custom').value || 'Inter';
    } else { customGrp.style.display = 'none'; }
    el.font = font;
    el.size = parseInt(document.getElementById('cid_st_size').value) || 12;
    el.weight = document.getElementById('cid_st_weight').value;
    el.align = document.getElementById('cid_st_align').value;
    el.color = document.getElementById('cid_st_color_text').value || '#000000';
    cidLoadGoogleFont(el.font);
  } else {
    const v = parseInt(document.getElementById('cid_st_photo_size').value) || 80;
    el.w = v; el.h = v;
    el.shape = document.getElementById('cid_st_photo_shape').value || 'square';
  }
  cidInjectElements();
}

function cidSyncColorFromPicker() {
  const c = document.getElementById('cid_st_color_picker').value;
  document.getElementById('cid_st_color_text').value = c;
  cidApplyStyle();
}
function cidSyncColorFromText() {
  const c = document.getElementById('cid_st_color_text').value;
  if (/^#[0-9a-f]{6}$/i.test(c)) document.getElementById('cid_st_color_picker').value = c;
  cidApplyStyle();
}

function cidAddCustomFont() {
  const fontName = document.getElementById('cid_st_font_custom').value.trim();
  if (!fontName) return;
  const sel = document.getElementById('cid_st_font');
  let exists = Array.from(sel.options).find(o => o.value.toLowerCase() === fontName.toLowerCase());
  if (!exists) {
    const opt = document.createElement('option');
    opt.value = fontName; opt.textContent = fontName;
    sel.insertBefore(opt, sel.lastElementChild);
    exists = opt;
  }
  sel.value = exists.value;
  cidApplyStyle();
}

window.cidRemoveCustomFont = function() {
  const sel = document.getElementById('cid_st_font');
  const val = sel.value;
  if (val !== '_custom' && sel.selectedIndex > 13) {
    sel.options[sel.selectedIndex].remove();
    sel.value = 'Inter';
    cidApplyStyle();
  }
};

function cidLoadGoogleFont(fontName) {
  if (!fontName || fontName === '_custom') return;
  const id = 'gfont_' + fontName.replace(/\s+/g, '_');
  if (document.getElementById(id)) return;
  const link = document.createElement('link');
  link.id = id; link.rel = 'stylesheet';
  link.href = 'https://fonts.googleapis.com/css2?family=' + fontName.replace(/\s+/g, '+') + '&display=swap';
  document.head.appendChild(link);
}

function cidMoveTo(side) {
  if (!cidActiveElId) return;
  cidPushHistory();
  cidElements.find(e => e.id === cidActiveElId).side = side;
  cidRenderElementList();
  cidInjectElements();
  cidSetView(side);
}

// ── Custom Variable ──
function cidSetCustomType(type) {
  cidCustomType = type;
  document.getElementById('cid_ctype_text').className = type === 'text' ? 'btn-primary' : 'btn-vr';
  document.getElementById('cid_ctype_image').className = type === 'image' ? 'btn-primary' : 'btn-vr';
  document.getElementById('cid_custom_text_area').style.display = type === 'text' ? 'block' : 'none';
  document.getElementById('cid_custom_image_area').style.display = type === 'image' ? 'block' : 'none';
}

function cidCustomImgSelected(input) {
  if (!input.files || !input.files[0]) return;
  document.getElementById('cid_custom_img_filename').textContent = input.files[0].name;
  const r = new FileReader();
  r.onload = e => { cidCustomImgData = e.target.result; };
  r.readAsDataURL(input.files[0]);
}

function cidAddCustomVariable() {
  const name = document.getElementById('cid_custom_name').value.trim();
  const val = document.getElementById('cid_custom_val').value.trim();
  if (!name) return;
  
  cidPushHistory();
  const id = 'cv_' + Date.now();
  if (cidCustomType === 'text') {
    cidCustomVariables.push({ id, label: name, val });
    cidElements.push({ id, label: name, type:'text', side:'front', x:50, y:50, size:12, font:'Inter', color:'#000000', weight:'400' });
    document.getElementById('cid_custom_name').value = '';
    document.getElementById('cid_custom_val').value = '';
  } else {
    const imgName = document.getElementById('cid_custom_img_name').value.trim();
    if (!imgName || !cidCustomImgData) return;
    cidElements.push({ id, label: id, label_alias: imgName, type:'custom_img', side:'front', x:50, y:50, w:60, h:60, imgData: cidCustomImgData });
    document.getElementById('cid_custom_img_name').value = '';
    document.getElementById('cid_custom_img_filename').textContent = 'No file chosen';
    cidCustomImgData = null;
  }
  cidRenderElementList();
}

// ── Preview Navigation ──
function cidUpdatePreview() {
  cidInjectElements();
  if (cidSelectedStudents.length > 0)
    document.getElementById('cid_preview_idx').textContent = (cidPreviewIdx+1) + ' / ' + cidSelectedStudents.length;
}
function cidPrevPreview() { if (cidPreviewIdx > 0) { cidPreviewIdx--; cidUpdatePreview(); } }
function cidNextPreview() { if (cidPreviewIdx < cidSelectedStudents.length-1) { cidPreviewIdx++; cidUpdatePreview(); } }

// ── View Full Template ──
function cidViewFull(side) {
  if (!cidTemplates[side]) return;
  const w = window.open('', '_blank');
  w.document.write(`<html><head><title>${side} Template</title><style>body{margin:0;background:#111;display:flex;align-items:center;justify-content:center;height:100vh;}</style></head><body><img src="${cidTemplates[side]}" style="max-width:95vw;max-height:95vh;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.5);"></body></html>`);
}

let cidIsZoomed = false;
let cidZoomScale = 1;

// ── Zoom (renders current card in fullscreen overlay) ──
function cidZoom() {
  const modal = document.getElementById('cid_zoom_modal');
  const zoomGrid = document.getElementById('cid_zoom_grid');
  const origGrid = document.getElementById('cid_step3_grid');
  const preview = document.getElementById('cid_preview_col');
  const controls = document.getElementById('cid_controls_col');
  const btn = document.getElementById('cid_zoom_btn');

  cidIsZoomed = !cidIsZoomed;
  if (cidIsZoomed) {
    modal.style.display = 'block';
    zoomGrid.appendChild(preview);
    zoomGrid.appendChild(controls);
    cidZoomScale = 2.2;
    document.getElementById('cid_preview_container').style.transform = `scale(${cidZoomScale})`;
    controls.style.maxHeight = 'none';
    btn.style.display = 'none';
  } else {
    modal.style.display = 'none';
    origGrid.insertBefore(preview, origGrid.firstChild);
    origGrid.appendChild(controls);
    cidZoomScale = 1.0;
    document.getElementById('cid_preview_container').style.transform = `scale(${cidZoomScale})`;
    controls.style.maxHeight = '480px';
    btn.style.display = 'block';
  }
}

// ── Drag & Resize Logic ──
let cidDraggingId = null, cidDragOff = {x:0,y:0};
let cidResizingId = null, cidResizeDir = null, cidResizeStart = null;

document.addEventListener('mousedown', e => {
  const el = e.target.closest('.cid-draggable');
  if (!el || e.target.classList.contains('cid-resize-handle')) return;
  
  cidPushHistory();
  cidDraggingId = el.id.replace('view_el_', '');
  const r = el.getBoundingClientRect();
  const isResize = el.style.resize === 'horizontal' && (e.clientX > r.right - 18) && (e.clientY > r.bottom - 18);
  if (isResize) return; // allow native resize to take over without dragging
  
  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  cidDragOff.x = (e.clientX - r.left) / actualScale;
  cidDragOff.y = (e.clientY - r.top) / actualScale;
  cidSelectElement(cidDraggingId);
});

function drawSnapLine(dir, pos) {
  const line = document.createElement('div');
  line.className = 'cid-snap-line';
  line.style.position = 'absolute';
  line.style.zIndex = '9999';
  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  const borderW = (1 / actualScale) + 'px';
  line.style.border = `${borderW} dashed var(--accent)`;
  if (dir === 'v') {
    line.style.left = pos + 'px';
    line.style.top = '0'; line.style.bottom = '0'; line.style.width = '0px';
  } else {
    line.style.top = pos + 'px';
    line.style.left = '0'; line.style.right = '0'; line.style.height = '0px';
  }
  document.getElementById('cid_preview_container').appendChild(line);
}

document.addEventListener('mousemove', e => {
  if (cidResizingId) {
    const el = cidElements.find(d => d.id === cidResizingId);
    if (!el) return;
    const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
    let dx = (e.clientX - cidResizeStart.x) / actualScale;
    let dy = (e.clientY - cidResizeStart.y) / actualScale;
    
    let newW = cidResizeStart.w;
    let newH = cidResizeStart.h;
    let newX = cidResizeStart.left;
    let newY = cidResizeStart.top;

    if (cidResizeDir.includes('e')) newW += dx;
    if (cidResizeDir.includes('w')) { newW -= dx; newX += dx; }
    if (cidResizeDir.includes('s')) newH += dy;
    if (cidResizeDir.includes('n')) { newH -= dy; newY += dy; }
    
    if (newW < 20) {
      newX += (newW - 20) * (cidResizeDir.includes('w') ? 1 : 0);
      newW = 20;
    }
    if (newH < 20) { newY += (newH - 20) * (cidResizeDir.includes('n') ? 1 : 0); newH = 20; }
    
    el.x = newX;
    el.y = newY;
    if (el.type === 'text') {
      el.text_w = newW;
      if (cidResizeDir.includes('n') || cidResizeDir.includes('s')) {
        // Use decimal for smoother "gradual" font scaling
        el.size = Math.max(4, Number((newH * 0.82).toFixed(2)));
      }
    } else {
      el.w = newW;
      el.h = newH;
    }
    
    const div = document.getElementById('view_el_' + cidResizingId);
    if (div) {
      div.style.left = newX + 'px';
      div.style.top = newY + 'px';
      if (el.type === 'text') {
        div.style.width = newW + 'px';
        div.style.fontSize = el.size + 'px';
      } else {
        div.style.width = newW + 'px'; 
        div.style.height = newH + 'px';
      }
    }
    
    // Update style panel inputs if this is the active element
    if (cidActiveElId === cidResizingId && el.type === 'text') {
      const sizeInput = document.getElementById('cid_st_size');
      if (sizeInput) sizeInput.value = el.size;
    } else if (cidActiveElId === cidResizingId) {
      const sizeInput = document.getElementById('cid_st_photo_size');
      if (sizeInput) sizeInput.value = el.w;
    }
    return;
  }

  if (!cidDraggingId) return;
  const div = document.getElementById('view_el_' + cidDraggingId);
  if (!div) return;
  const parent = div.parentElement;
  const pR = parent.getBoundingClientRect();
  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  let x = (e.clientX - pR.left) / actualScale - cidDragOff.x;
  let y = (e.clientY - pR.top) / actualScale - cidDragOff.y;
  const data = cidElements.find(d => d.id === cidDraggingId);
  
  const divW = data.type === 'text' ? (data.text_w || div.offsetWidth) : (data.w || div.offsetWidth);
  const divH = data.type === 'text' ? div.offsetHeight : (data.h || div.offsetHeight);
  
  document.querySelectorAll('.cid-snap-line').forEach(e => e.remove());
  let snappedX = false, snappedY = false;
  const snapDist = 6;
  
  const myEdges = {
    x: { start: x, center: x + divW / 2, end: x + divW },
    y: { start: y, center: y + divH / 2, end: y + divH }
  };

  const pR_W = pR.width / actualScale;
  const pR_H = pR.height / actualScale;
  const targetsX = [ {val: 0, line: 0}, {val: pR_W/2, line: pR_W/2}, {val: pR_W, line: pR_W} ];
  const targetsY = [ {val: 0, line: 0}, {val: pR_H/2, line: pR_H/2}, {val: pR_H, line: pR_H} ];
  
  cidElements.forEach(other => {
    if (other.id === cidDraggingId || other.side !== data.side || other.visible === false) return;
    const oEl = document.getElementById('view_el_' + other.id);
    if (!oEl) return;
    const oW = other.type === 'text' ? (other.text_w || oEl.offsetWidth) : (other.w || oEl.offsetWidth);
    const oH = other.type === 'text' ? oEl.offsetHeight : (other.h || oEl.offsetHeight);
    targetsX.push( {val: other.x, line: other.x}, {val: other.x + oW/2, line: other.x + oW/2}, {val: other.x + oW, line: other.x + oW} );
    targetsY.push( {val: other.y, line: other.y}, {val: other.y + oH/2, line: other.y + oH/2}, {val: other.y + oH, line: other.y + oH} );
  });
  
  for (let pt of targetsX) {
    let matched = false;
    if (Math.abs(myEdges.x.start - pt.val) < snapDist) { if (!snappedX) x = pt.val; snappedX = true; matched = true; }
    else if (Math.abs(myEdges.x.center - pt.val) < snapDist) { if (!snappedX) x = pt.val - divW/2; snappedX = true; matched = true; }
    else if (Math.abs(myEdges.x.end - pt.val) < snapDist) { if (!snappedX) x = pt.val - divW; snappedX = true; matched = true; }
    if (matched) drawSnapLine('v', pt.line);
  }
  for (let pt of targetsY) {
    let matched = false;
    if (Math.abs(myEdges.y.start - pt.val) < snapDist) { if (!snappedY) y = pt.val; snappedY = true; matched = true; }
    else if (Math.abs(myEdges.y.center - pt.val) < snapDist) { if (!snappedY) y = pt.val - divH/2; snappedY = true; matched = true; }
    else if (Math.abs(myEdges.y.end - pt.val) < snapDist) { if (!snappedY) y = pt.val - divH; snappedY = true; matched = true; }
    if (matched) drawSnapLine('h', pt.line);
  }

  if (data) { data.x = x; data.y = y; }
  div.style.left = x + 'px';
  div.style.top = y + 'px';
});

document.addEventListener('mouseup', () => { 
  cidDraggingId = null; 
  cidResizingId = null;
  document.querySelectorAll('.cid-snap-line').forEach(e => e.remove());
});

// ── PDF Generation (via html2canvas for 1:1 exact matching) ──
async function cidGeneratePDF() {
  const { jsPDF } = window.jspdf;
  const ori = document.querySelector('input[name="cid_orientation"]:checked').value;
  const doc = new jsPDF({ orientation: ori, unit: 'mm', format: [85.6, 54] });
  const btn = document.getElementById('cid_generate_btn');
  const status = document.getElementById('cid_generate_status');
  const progress = document.getElementById('cid_progress');
  btn.disabled = true; status.style.display = 'inline';
  cidPdfCancelled = false;

  const pw = ori === 'landscape' ? 85.6 : 54;
  const ph = ori === 'landscape' ? 54 : 85.6;
  const total = cidSelectedStudents.length;

  const frontContainer = document.getElementById('cid_card_front');
  const backContainer = document.getElementById('cid_card_back');
  const wasFrontVisible = frontContainer.style.display !== 'none';
  const wasBackVisible = backContainer.style.display !== 'none';
  frontContainer.style.display = 'block';
  backContainer.style.display = 'block';
  
  const loadingScrn = document.getElementById('cid_pdf_loading');
  const loadingText = document.getElementById('cid_pdf_loading_text');
  const loadingBar = document.getElementById('cid_pdf_progress_bar');
  if (loadingScrn) loadingScrn.style.display = 'flex';
  
  // FIX: html2canvas text scattering bug caused by transform scale
  const previewCont = document.getElementById('cid_preview_container');
  const oldTransform = previewCont.style.transform;
  previewCont.style.transform = 'none';

  // FIX: hide UI selection borders during capture
  const oldActive = cidActiveElId;
  cidActiveElId = null;

  // Await ALL fonts injected via <link> to fully download and parse before capturing!
  await document.fonts.ready;
  await new Promise(r => setTimeout(r, 200));

  frontContainer.classList.add('cid-exporting');
  backContainer.classList.add('cid-exporting');

  for (let i = 0; i < total; i++) {
    if (cidPdfCancelled) break;
    const pctStr = Math.round(((i+1)/total)*100) + '%';
    progress.textContent = pctStr;
    if (loadingText) loadingText.textContent = `Processing student ${i+1} of ${total} (${pctStr})`;
    if (loadingBar) loadingBar.style.width = pctStr;
    
    cidPreviewIdx = i;
    cidInjectElements();
    
    // Wait for student photos to load into DOM
    await new Promise(r => setTimeout(r, 150));

    if (i > 0) doc.addPage([85.6, 54], ori);
    const canvasFront = await html2canvas(frontContainer, { scale: 3, useCORS: true, backgroundColor: null, logging: false });
    doc.addImage(canvasFront.toDataURL('image/png'), 'PNG', 0, 0, pw, ph);

    doc.addPage([85.6, 54], ori);
    const canvasBack = await html2canvas(backContainer, { scale: 3, useCORS: true, backgroundColor: null, logging: false });
    doc.addImage(canvasBack.toDataURL('image/png'), 'PNG', 0, 0, pw, ph);
  }

  // Restore state
  frontContainer.classList.remove('cid-exporting');
  backContainer.classList.remove('cid-exporting');
  previewCont.style.transform = oldTransform;
  cidActiveElId = oldActive;
  cidPreviewIdx = 0;
  cidInjectElements();
  if (!wasFrontVisible) frontContainer.style.display = 'none';
  if (!wasBackVisible) backContainer.style.display = 'none';

  if (!cidPdfCancelled) {
    doc.save('DAVS_IDs_' + Date.now() + '.pdf');
  }
  btn.disabled = false; status.style.display = 'none';
  if (loadingScrn) loadingScrn.style.display = 'none';
}

function cidCancelPDF() {
  cidPdfCancelled = true;
  const loadingText = document.getElementById('cid_pdf_loading_text');
  if (loadingText) loadingText.textContent = 'Cancelling...';
}
