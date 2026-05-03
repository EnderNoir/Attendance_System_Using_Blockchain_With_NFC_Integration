// Advanced Create ID Logic
let cidSelectedStudents = [];
let cidPreviewIdx = 0;
let cidTemplates = { front: null, back: null };
let cidCustomVariables = [];
let cidElements = [
  { id: 'photo', label: 'Student Photo', type: 'photo', side: 'front', x: 20, y: 20, w: 100, h: 100 },
  { id: 'name', label: 'Full Name', type: 'text', side: 'front', x: 20, y: 130, size: 20, font: 'Inter', color: '#000000', weight: '700' },
  { id: 'course', label: 'Program', type: 'text', side: 'front', x: 20, y: 160, size: 14, font: 'Inter', color: '#333333', weight: '500' },
  { id: 'id_num', label: 'Student ID', type: 'text', side: 'front', x: 20, y: 180, size: 12, font: 'Space Mono', color: '#666666', weight: '400' },
  { id: 'program_full', label: 'Full Program (Back)', type: 'text', side: 'back', x: 20, y: 30, size: 11, font: 'Inter', color: '#000000', weight: '400' },
  { id: 'year_level', label: 'Year Level (Back)', type: 'text', side: 'back', x: 20, y: 50, size: 11, font: 'Inter', color: '#000000', weight: '400' },
  { id: 'semester', label: 'Semester (Back)', type: 'text', side: 'back', x: 20, y: 70, size: 11, font: 'Inter', color: '#000000', weight: '400' }
];

let cidActiveElId = null;

function openCreateIdModal() {
  document.getElementById('createIdModal').classList.add('show');
  cidUpdateCount();
  cidRenderElementList();
}

function closeCreateIdModal() {
  document.getElementById('createIdModal').classList.remove('show');
}

function cidUpdateCount() {
  const prog = document.getElementById('cid_program').value;
  const year = document.getElementById('cid_year').value;
  const sem = document.getElementById('cid_semester').value;
  const sec = document.getElementById('cid_section').value;

  const all = window.DASHBOARD_BOOTSTRAP.students || [];
  cidSelectedStudents = all.filter(s => {
    return (!prog || s.course === prog) &&
           (!year || s.year_level === year) &&
           (!sem || s.semester === sem) &&
           (!sec || s.section === sec);
  });

  document.getElementById('cid_count').textContent = cidSelectedStudents.length;
  cidPreviewIdx = 0;
  cidUpdatePreview();
  cidCheckReady();
}

function cidHandleFile(input, side) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      cidTemplates[side] = e.target.result;
      document.getElementById(`cid_${side}_preview`).src = e.target.result;
      document.getElementById(`cid_${side}_preview`).style.display = 'block';
      document.getElementById(`cid_${side}_text`).style.display = 'none';
      document.getElementById(`cid_card_${side}_bg`).src = e.target.result;
      cidUpdatePreview();
      cidCheckReady();
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function cidUpdateOrientation() {
  const orientation = document.querySelector('input[name="cid_orientation"]:checked').value;
  const boxes = document.querySelectorAll('.cid-card-box');
  boxes.forEach(box => {
    if (orientation === 'portrait') {
      box.style.width = '204px';
      box.style.height = '323.5px';
    } else {
      box.style.width = '323.5px';
      box.style.height = '204px';
    }
  });
  // Adjust scale to fit if portrait
  const container = document.getElementById('cid_preview_container');
  container.style.transform = orientation === 'portrait' ? 'scale(0.7)' : 'scale(0.9)';
}

function cidCheckReady() {
  const btn = document.getElementById('cid_generate_btn');
  const ready = cidSelectedStudents.length > 0 && cidTemplates.front && cidTemplates.back;
  btn.disabled = !ready;
  if (ready) {
    document.getElementById('cid_no_template_msg').style.display = 'none';
    document.getElementById('cid_preview_container').style.display = 'flex';
    document.getElementById('cid_preview_nav').style.display = 'flex';
  } else {
    document.getElementById('cid_no_template_msg').style.display = 'block';
    document.getElementById('cid_preview_container').style.display = 'none';
    document.getElementById('cid_preview_nav').style.display = 'none';
  }
}

function cidRenderElementList() {
  const list = document.getElementById('cid_element_list');
  list.innerHTML = cidElements.map(el => `
    <div class="mu-action-label" style="padding:6px 10px; font-size:11px; ${cidActiveElId === el.id ? 'border-color:var(--accent); background:rgba(45,106,39,.04);' : ''}" onclick="cidSelectElement('${el.id}')">
       <i class="bi bi-${el.type === 'photo' ? 'image' : 'fonts'}"></i>
       <span style="flex:1;">${el.label}</span>
       <span style="font-size:8px; opacity:0.5; text-transform:uppercase;">${el.side}</span>
    </div>
  `).join('');
  cidInjectElements();
}

function cidInjectElements() {
  const front = document.getElementById('cid_front_elements');
  const back = document.getElementById('cid_back_elements');
  front.innerHTML = ''; back.innerHTML = '';
  
  const s = cidSelectedStudents[cidPreviewIdx] || { name: '[Student Name]', course: '[Program]', student_id: '[ID]', year_level: '[Year]', semester: '[Semester]' };
  
  cidElements.forEach(el => {
    const div = document.createElement('div');
    div.className = 'cid-draggable' + (el.type === 'text' ? ' cid-text' : '');
    div.id = `view_el_${el.id}`;
    div.style.left = el.x + 'px';
    div.style.top = el.y + 'px';
    
    if (el.type === 'text') {
      div.style.fontSize = el.size + 'px';
      div.style.fontFamily = el.font;
      div.style.color = el.color;
      div.style.fontWeight = el.weight;
      div.textContent = cidGetVal(el.id, s);
    } else {
      div.style.width = el.w + 'px';
      div.style.height = el.h + 'px';
      div.style.borderRadius = '6px';
      div.style.background = 'rgba(0,0,0,0.1)';
      div.style.border = '1px solid rgba(0,0,0,0.2)';
      const photoFile = (window.DASHBOARD_BOOTSTRAP.photos || {})[s.nfc_id];
      if (photoFile) {
        div.innerHTML = `<img src="/static/uploads/${photoFile}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;" />`;
      } else {
        div.innerHTML = `<i class="bi bi-person" style="font-size:24px; opacity:0.3;"></i>`;
        div.style.display = 'flex'; div.style.alignItems = 'center'; div.style.justifyContent = 'center';
      }
    }
    
    div.onclick = (e) => { e.stopPropagation(); cidSelectElement(el.id); };
    (el.side === 'front' ? front : back).appendChild(div);
  });
}

function cidGetVal(id, s) {
  if (id === 'name') return s.name || '[Name]';
  if (id === 'course') return s.course || s.program || '[Program]';
  if (id === 'id_num') return 'ID: ' + (s.student_id || '[ID]');
  if (id === 'program_full') return 'Program: ' + (s.course || s.program || '[Program]');
  if (id === 'year_level') return 'Year Level: ' + (s.year_level || '[Year]');
  if (id === 'semester') return 'Semester: ' + (s.semester || '[Semester]');
  
  const custom = cidCustomVariables.find(v => v.id === id);
  return custom ? custom.val : '';
}

function cidSelectElement(id) {
  cidActiveElId = id;
  const el = cidElements.find(e => e.id === id);
  cidRenderElementList();
  
  const panel = document.getElementById('cid_style_panel');
  panel.style.display = 'block';
  document.getElementById('cid_style_title').textContent = `Styling: ${el.label}`;
  
  if (el.type === 'text') {
    document.getElementById('cid_st_font').value = el.font;
    document.getElementById('cid_st_size').value = el.size;
    document.getElementById('cid_st_color').value = el.color;
    document.getElementById('cid_st_weight').value = el.weight;
    // Show text specific controls
    document.getElementById('cid_st_font').parentElement.style.display = 'block';
    document.getElementById('cid_st_color').parentElement.style.display = 'block';
    document.getElementById('cid_st_weight').parentElement.style.display = 'block';
  } else {
    // Hide text specific controls for photo
    document.getElementById('cid_st_font').parentElement.style.display = 'none';
    document.getElementById('cid_st_color').parentElement.style.display = 'none';
    document.getElementById('cid_st_weight').parentElement.style.display = 'none';
    document.getElementById('cid_st_size').value = el.w; // Reuse size for width in UI
  }
}

function cidApplyStyle() {
  if (!cidActiveElId) return;
  const el = cidElements.find(e => e.id === cidActiveElId);
  if (el.type === 'text') {
    el.font = document.getElementById('cid_st_font').value;
    el.size = parseInt(document.getElementById('cid_st_size').value);
    el.color = document.getElementById('cid_st_color').value;
    el.weight = document.getElementById('cid_st_weight').value;
  } else {
    const val = parseInt(document.getElementById('cid_st_size').value);
    el.w = val; el.h = val;
  }
  cidInjectElements();
}

function cidMoveTo(side) {
  if (!cidActiveElId) return;
  const el = cidElements.find(e => e.id === cidActiveElId);
  el.side = side;
  cidRenderElementList();
  cidInjectElements();
}

function cidAddCustomVariable() {
  const name = document.getElementById('cid_custom_name').value.trim();
  const val = document.getElementById('cid_custom_val').value.trim();
  if (!name || !val) return;
  
  const id = 'custom_' + Date.now();
  cidCustomVariables.push({ id, label: name, val });
  cidElements.push({ id, label: name, type: 'text', side: 'front', x: 50, y: 50, size: 12, font: 'Inter', color: '#000000', weight: '400' });
  
  document.getElementById('cid_custom_name').value = '';
  document.getElementById('cid_custom_val').value = '';
  cidRenderElementList();
}

function cidUpdatePreview() {
  cidInjectElements();
  document.getElementById('cid_preview_idx').textContent = `${cidPreviewIdx + 1} / ${cidSelectedStudents.length}`;
}

function cidPrevPreview() { if (cidPreviewIdx > 0) { cidPreviewIdx--; cidUpdatePreview(); } }
function cidNextPreview() { if (cidPreviewIdx < cidSelectedStudents.length - 1) { cidPreviewIdx++; cidUpdatePreview(); } }

function cidViewFull(side) {
  if (!cidTemplates[side]) return;
  const w = window.open("");
  w.document.write(`<img src="${cidTemplates[side]}" style="max-width:100%;">`);
}

function cidViewPreviewFull(side) {
  // Simple zoom implementation
  const container = document.getElementById('cid_card_' + side);
  const clone = container.cloneNode(true);
  const w = window.open("");
  w.document.write(`
    <style>
      body { background: #111; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
      .cid-card-box { width: 856px; height: 540px; position: relative; background: white; border-radius: 20px; overflow: hidden; transform: scale(1); }
      .cid-card-bg { width: 100%; height: 100%; position: absolute; top:0; left:0; object-fit: cover; }
      .cid-draggable { position: absolute; z-index: 2; }
    </style>
  `);
  // Need to adjust scaling for the zoom window
  const scale = 856 / 323.5;
  clone.querySelectorAll('.cid-draggable').forEach(el => {
    el.style.left = (parseFloat(el.style.left) * scale) + 'px';
    el.style.top = (parseFloat(el.style.top) * scale) + 'px';
    if (el.classList.contains('cid-text')) {
       el.style.fontSize = (parseFloat(el.style.fontSize) * scale) + 'px';
    } else {
       el.style.width = (parseFloat(el.style.width) * scale) + 'px';
       el.style.height = (parseFloat(el.style.height) * scale) + 'px';
    }
  });
  w.document.body.appendChild(clone);
}

// Global Drag Logic for cidElements
let cidDraggingId = null;
let cidDragOffset = { x: 0, y: 0 };

document.addEventListener('mousedown', (e) => {
  const el = e.target.closest('.cid-draggable');
  if (!el) return;
  cidDraggingId = el.id.replace('view_el_', '');
  const rect = el.getBoundingClientRect();
  cidDragOffset.x = e.clientX - rect.left;
  cidDragOffset.y = e.clientY - rect.top;
  cidSelectElement(cidDraggingId);
});

document.addEventListener('mousemove', (e) => {
  if (!cidDraggingId) return;
  const el = document.getElementById(`view_el_${cidDraggingId}`);
  const parent = el.parentElement;
  const pRect = parent.getBoundingClientRect();
  const orientation = document.querySelector('input[name="cid_orientation"]:checked').value;
  const scale = orientation === 'portrait' ? 0.7 : 0.9;
  
  let x = (e.clientX - pRect.left - cidDragOffset.x) / scale;
  let y = (e.clientY - pRect.top - cidDragOffset.y) / scale;
  
  const element = cidElements.find(e => e.id === cidDraggingId);
  element.x = x; element.y = y;
  el.style.left = x + 'px'; el.style.top = y + 'px';
});

document.addEventListener('mouseup', () => { cidDraggingId = null; });

// PDF GENERATION
async function cidGeneratePDF() {
  const { jsPDF } = window.jspdf;
  const orientation = document.querySelector('input[name="cid_orientation"]:checked').value;
  const doc = new jsPDF({
    orientation: orientation,
    unit: 'mm',
    format: [85.6, 54]
  });
  
  const btn = document.getElementById('cid_generate_btn');
  const status = document.getElementById('cid_generate_status');
  const progress = document.getElementById('cid_progress');
  btn.disabled = true; status.style.display = 'block';
  
  const total = cidSelectedStudents.length;
  const ratio = 85.6 / 323.5;

  for (let i = 0; i < total; i++) {
    progress.textContent = Math.round((i / total) * 100) + '%';
    const s = cidSelectedStudents[i];
    
    // Front Page
    if (i > 0) doc.addPage([85.6, 54], orientation);
    doc.addImage(cidTemplates.front, 'JPEG', 0, 0, (orientation === 'landscape' ? 85.6 : 54), (orientation === 'landscape' ? 54 : 85.6));
    
    for (const el of cidElements.filter(e => e.side === 'front')) {
       await cidDrawElement(doc, el, s, ratio, orientation);
    }
    
    // Back Page
    doc.addPage([85.6, 54], orientation);
    doc.addImage(cidTemplates.back, 'JPEG', 0, 0, (orientation === 'landscape' ? 85.6 : 54), (orientation === 'landscape' ? 54 : 85.6));
    
    for (const el of cidElements.filter(e => e.side === 'back')) {
       await cidDrawElement(doc, el, s, ratio, orientation);
    }
  }
  
  doc.save(`DAVS_IDs_${Date.now()}.pdf`);
  btn.disabled = false; status.style.display = 'none';
}

async function cidDrawElement(doc, el, s, ratio, orientation) {
  const x = el.x * ratio;
  const y = el.y * ratio;
  
  if (el.type === 'photo') {
    const photoFile = (window.DASHBOARD_BOOTSTRAP.photos || {})[s.nfc_id];
    if (photoFile) {
       try {
         const data = await cidUrlToBase64(`/static/uploads/${photoFile}`);
         doc.addImage(data, 'JPEG', x, y, el.w * ratio, el.h * ratio);
       } catch(e) {}
    }
  } else {
    const val = cidGetVal(el.id, s);
    doc.setTextColor(el.color);
    doc.setFontSize(el.size * 2.8); // jsPDF Scaling
    doc.setFont("helvetica", el.weight >= 700 ? "bold" : "normal");
    doc.text(val, x, y + (el.size * ratio * 0.8));
  }
}

function cidUrlToBase64(url) {
  return new Promise((resolve, reject) => {
    const img = new Image(); img.crossOrigin = 'Anonymous';
    img.onload = () => {
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
      c.getContext('2d').drawImage(img, 0, 0); resolve(c.toDataURL('image/jpeg', 0.9));
    };
    img.onerror = reject; img.src = url;
  });
}

