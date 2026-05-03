// ═══ Advanced Create ID Logic ═══
let cidSelectedStudents = [];
let cidPreviewIdx = 0;
let cidTemplates = { front: null, back: null };
let cidCustomVariables = [];
let cidCurrentView = 'front';
let cidCustomType = 'text';
let cidCustomImgData = null;
let cidMode = 'batch';

let cidElements = [
  { id:'photo', label:'Student Photo', type:'photo', side:'front', x:20, y:20, w:80, h:80, shape:'square', visible:true },
  { id:'name', label:'Full Name', type:'text', side:'front', x:161.75, y:110, size:16, font:'Inter', color:'#000000', weight:'700', align:'center', visible:true },
  { id:'course', label:'Program', type:'text', side:'front', x:161.75, y:132, size:12, font:'Inter', color:'#333333', weight:'500', align:'center', visible:true },
  { id:'id_num', label:'Student ID', type:'text', side:'front', x:161.75, y:150, size:11, font:'Space Mono', color:'#555555', weight:'400', align:'center', visible:true },
  { id:'school_year', label:'School Year (Back)', type:'text', side:'back', x:20, y:30, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'contact_number', label:'Contact Number (Back)', type:'text', side:'back', x:20, y:45, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'email', label:'Email Address (Back)', type:'text', side:'back', x:20, y:60, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'year_level', label:'Year Level (Back)', type:'text', side:'back', x:20, y:75, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true },
  { id:'semester', label:'Semester (Back)', type:'text', side:'back', x:20, y:90, size:10, font:'Inter', color:'#000000', weight:'600', align:'left', visible:true }
];
let cidActiveElId = null;

// ── Modal Open / Close ──
function openCreateIdModal() {
  document.getElementById('createIdModal').classList.add('show');
  cidUpdateCount();
  cidRenderElementList();
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

function cidToggleVisible(id, e) {
  e.stopPropagation();
  const el = cidElements.find(d => d.id === id);
  if (el) el.visible = !(el.visible !== false);
  cidRenderElementList();
}

// ── Element List Rendering ──
function cidRenderElementList() {
  const list = document.getElementById('cid_element_list');
  list.innerHTML = cidElements.map(el => {
    const isVis = el.visible !== false;
    return `<div class="mu-action-label" style="padding:5px 8px;font-size:11px;${cidActiveElId===el.id?'border-color:var(--accent);background:rgba(45,106,39,.06);':''}" onclick="cidSelectElement('${el.id}')">
       <i class="bi bi-${el.type==='photo'?'image':el.type==='custom_img'?'image':'fonts'}" style="font-size:13px;opacity:${isVis?1:0.4}"></i>
       <span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:${isVis?1:0.4}">${el.label}</span>
       <span style="font-size:8px;opacity:.5;text-transform:uppercase;">${el.side}</span>
       <button onclick="cidToggleVisible('${el.id}', event)" style="background:none;border:none;color:var(--text);cursor:pointer;padding:0 5px;opacity:${isVis?1:0.4}"><i class="bi bi-eye${isVis?'':'-slash'}"></i></button>
    </div>`;
  }).join('');
  cidInjectElements();
}

// ── Inject draggable elements into preview cards ──
function cidInjectElements() {
  const front = document.getElementById('cid_front_elements');
  const back = document.getElementById('cid_back_elements');
  front.innerHTML = ''; back.innerHTML = '';
  const s = cidSelectedStudents[cidPreviewIdx] || {};

  cidElements.forEach(el => {
    if (el.visible === false) return;
    const div = document.createElement('div');
    div.className = 'cid-draggable' + (el.type === 'text' ? ' cid-text' : '');
    div.id = 'view_el_' + el.id;
    div.style.left = el.x + 'px';
    div.style.top = el.y + 'px';

    if (el.type === 'text') {
      div.style.fontSize = el.size + 'px';
      div.style.fontFamily = el.font;
      div.style.color = el.color;
      div.style.fontWeight = el.weight;
      div.style.whiteSpace = 'nowrap';
      div.style.textAlign = el.align || 'left';
      if (el.align === 'center') div.style.transform = 'translateX(-50%)';
      else if (el.align === 'right') div.style.transform = 'translateX(-100%)';
      div.textContent = cidGetVal(el.id, s);
    } else if (el.type === 'custom_img') {
      div.style.width = (el.w||60) + 'px'; div.style.height = (el.h||60) + 'px';
      div.style.borderRadius = '4px'; div.style.overflow = 'hidden';
      if (el.imgData) div.innerHTML = `<img src="${el.imgData}" style="width:100%;height:100%;object-fit:contain;">`;
    } else { // photo
      div.style.width = (el.w||80) + 'px'; div.style.height = (el.h||80) + 'px';
      div.style.borderRadius = el.shape === 'circle' ? '50%' : '6px'; div.style.background = 'rgba(0,0,0,.08)';
      div.style.border = '1px solid rgba(0,0,0,.15)';
      const pf = (window.DASHBOARD_BOOTSTRAP.photos||{})[s.nfc_id];
      if (pf) div.innerHTML = `<img src="/static/uploads/${pf}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;">`;
      else { div.style.display='flex'; div.style.alignItems='center'; div.style.justifyContent='center'; div.innerHTML='<i class="bi bi-person" style="font-size:20px;opacity:.3;"></i>'; }
    }
    div.onclick = e => { e.stopPropagation(); cidSelectElement(el.id); };
    (el.side === 'front' ? front : back).appendChild(div);
  });
}

function cidGetVal(id, s) {
  if (id === 'name') return s.name || '[Name]';
  if (id === 'course') return s.course || s.program || '[Program]';
  if (id === 'id_num') return s.student_id || '[ID]';
  if (id === 'school_year') return s.school_year || '[School Year]';
  if (id === 'contact_number') return s.contact_number || s.guardian_contact || '[Contact]';
  if (id === 'email') return s.email || '[Email]';
  if (id === 'year_level') return s.year_level || '[Year]';
  if (id === 'semester') return s.semester || '[Semester]';
  const cv = cidCustomVariables.find(v => v.id === id);
  return cv ? cv.val : '';
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
    if (!Array.from(fontSel.options).some(o => o.value === el.font)) fontSel.value = '_custom';
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
  const el = cidElements.find(e => e.id === cidActiveElId);
  if (el.type === 'text') {
    let font = document.getElementById('cid_st_font').value;
    const customInput = document.getElementById('cid_st_font_custom');
    if (font === '_custom') {
      customInput.style.display = 'block';
      font = customInput.value || 'Inter';
    } else { customInput.style.display = 'none'; }
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

function cidLoadGoogleFont(fontName) {
  if (!fontName || fontName === '_custom') return;
  const id = 'gfont_' + fontName.replace(/\s+/g, '_');
  if (document.getElementById(id)) return;
  const link = document.createElement('link');
  link.id = id; link.rel = 'stylesheet';
  link.href = 'https://fonts.googleapis.com/css2?family=' + encodeURIComponent(fontName) + '&display=swap';
  document.head.appendChild(link);
}

function cidMoveTo(side) {
  if (!cidActiveElId) return;
  cidElements.find(e => e.id === cidActiveElId).side = side;
  cidRenderElementList();
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
  const id = 'custom_' + Date.now();
  if (cidCustomType === 'text') {
    const name = document.getElementById('cid_custom_name').value.trim();
    const val = document.getElementById('cid_custom_val').value.trim();
    if (!name || !val) return;
    cidCustomVariables.push({ id, label: name, val });
    cidElements.push({ id, label: name, type:'text', side:'front', x:50, y:50, size:12, font:'Inter', color:'#000000', weight:'400' });
    document.getElementById('cid_custom_name').value = '';
    document.getElementById('cid_custom_val').value = '';
  } else {
    const name = document.getElementById('cid_custom_img_name').value.trim();
    if (!name || !cidCustomImgData) return;
    cidElements.push({ id, label: name, type:'custom_img', side:'front', x:50, y:50, w:60, h:60, imgData: cidCustomImgData });
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

// ── Drag Logic ──
let cidDraggingId = null, cidDragOff = {x:0,y:0};

document.addEventListener('mousedown', e => {
  const el = e.target.closest('.cid-draggable');
  if (!el) return;
  cidDraggingId = el.id.replace('view_el_', '');
  const r = el.getBoundingClientRect();
  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  cidDragOff.x = (e.clientX - r.left) / actualScale;
  cidDragOff.y = (e.clientY - r.top) / actualScale;
  cidSelectElement(cidDraggingId);
});

document.addEventListener('mousemove', e => {
  if (!cidDraggingId) return;
  const el = document.getElementById('view_el_' + cidDraggingId);
  if (!el) return;
  const parent = el.parentElement;
  const pR = parent.getBoundingClientRect();
  const actualScale = cidIsZoomed ? cidZoomScale : 1.0;
  let x = (e.clientX - pR.left) / actualScale - cidDragOff.x;
  let y = (e.clientY - pR.top) / actualScale - cidDragOff.y;
  const data = cidElements.find(d => d.id === cidDraggingId);
  if (data) { data.x = x; data.y = y; }
  el.style.left = x + 'px';
  el.style.top = y + 'px';
});

document.addEventListener('mouseup', () => { cidDraggingId = null; });

// ── PDF Generation ──
async function cidGeneratePDF() {
  const { jsPDF } = window.jspdf;
  const ori = document.querySelector('input[name="cid_orientation"]:checked').value;
  const doc = new jsPDF({ orientation: ori, unit: 'mm', format: [85.6, 54] });
  const btn = document.getElementById('cid_generate_btn');
  const status = document.getElementById('cid_generate_status');
  const progress = document.getElementById('cid_progress');
  btn.disabled = true; status.style.display = 'inline';

  const pw = ori === 'landscape' ? 85.6 : 54;
  const ph = ori === 'landscape' ? 54 : 85.6;
  const cardW = ori === 'landscape' ? 323.5 : 204;
  const ratio = pw / cardW;
  const total = cidSelectedStudents.length;

  for (let i = 0; i < total; i++) {
    progress.textContent = Math.round(((i+1)/total)*100) + '%';
    const s = cidSelectedStudents[i];

    if (i > 0) doc.addPage([85.6, 54], ori);
    doc.addImage(cidTemplates.front, 'JPEG', 0, 0, pw, ph);
    for (const el of cidElements.filter(e => e.side === 'front'))
      await cidDrawEl(doc, el, s, ratio);

    doc.addPage([85.6, 54], ori);
    doc.addImage(cidTemplates.back, 'JPEG', 0, 0, pw, ph);
    for (const el of cidElements.filter(e => e.side === 'back'))
      await cidDrawEl(doc, el, s, ratio);
  }

  doc.save('DAVS_IDs_' + Date.now() + '.pdf');
  btn.disabled = false; status.style.display = 'none';
}

async function cidDrawEl(doc, el, s, ratio) {
  if (el.visible === false) return;
  const x = el.x * ratio, y = el.y * ratio;
  if (el.type === 'photo') {
    const pf = (window.DASHBOARD_BOOTSTRAP.photos||{})[s.nfc_id];
    if (pf) { try { const d = await cidB64('/static/uploads/'+pf, el.shape); doc.addImage(d,el.shape==='circle'?'PNG':'JPEG',x,y,el.w*ratio,el.h*ratio); } catch(e){} }
  } else if (el.type === 'custom_img') {
    if (el.imgData) { try { doc.addImage(el.imgData,'PNG',x,y,(el.w||60)*ratio,(el.h||60)*ratio); } catch(e){} }
  } else {
    doc.setTextColor(el.color || '#000');
    doc.setFontSize((el.size||12) * 0.75);
    doc.setFont('helvetica', (el.weight||400) >= 700 ? 'bold' : 'normal');
    doc.text(cidGetVal(el.id, s), x, y + (el.size||12)*ratio*0.8, { align: el.align || 'left' });
  }
}

function cidB64(url, shape) {
  return new Promise((res, rej) => {
    const img = new Image(); img.crossOrigin = 'Anonymous';
    img.onload = () => { 
      const c = document.createElement('canvas'); 
      const size = Math.min(img.width, img.height);
      c.width = size; c.height = size; 
      const ctx = c.getContext('2d');
      if (shape === 'circle') {
        ctx.beginPath();
        ctx.arc(size/2, size/2, size/2, 0, Math.PI*2);
        ctx.closePath();
        ctx.clip();
      }
      const sx = (img.width - size)/2, sy = (img.height - size)/2;
      ctx.drawImage(img, sx, sy, size, size, 0, 0, size, size); 
      res(c.toDataURL(shape === 'circle' ? 'image/png' : 'image/jpeg', 0.9)); 
    };
    img.onerror = rej; img.src = url;
  });
}
