// Create ID logic
let cidSelectedStudents = [];
let cidPreviewIdx = 0;
let cidTemplates = { front: null, back: null };

function openCreateIdModal() {
  document.getElementById('createIdModal').classList.add('show');
  cidUpdateCount();
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
    const sCourse = s.course || s.program || '';
    const sYear = s.year_level || '';
    const sSem = s.semester || '';
    const sSec = s.section || '';

    return (!prog || sCourse === prog) &&
           (!year || sYear === year) &&
           (!sem || sSem === sem) &&
           (!sec || sSec === sec);
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
      
      // Update background of cards in preview
      document.getElementById(`cid_card_${side}_bg`).src = e.target.result;
      
      cidUpdatePreview();
      cidCheckReady();
    };
    reader.readAsDataURL(input.files[0]);
  }
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

function cidUpdatePreview() {
  if (cidSelectedStudents.length === 0) return;
  const s = cidSelectedStudents[cidPreviewIdx];
  
  // Update text placeholders
  document.getElementById('cid_el_name').textContent = s.name || '[Student Name]';
  document.getElementById('cid_el_course').textContent = s.course || s.program || '[Program]';
  document.getElementById('cid_el_id').textContent = 'ID: ' + (s.student_id || '[Student ID]');
  
  document.getElementById('cid_el_program_full').textContent = 'Program: ' + (s.course || s.program || '[Program]');
  document.getElementById('cid_el_year').textContent = 'Year Level: ' + (s.year_level || '[Year]');
  document.getElementById('cid_el_semester').textContent = 'Semester: ' + (s.semester || '[Semester]');
  document.getElementById('cid_el_contact').textContent = 'Contact: ' + (s.contact || '[Contact]');
  
  // Handle Photo
  const photoEl = document.getElementById('cid_el_photo');
  const photoFile = (window.DASHBOARD_BOOTSTRAP.photos || {})[s.nfc_id];
  if (photoFile) {
    photoEl.innerHTML = `<img src="/static/uploads/${photoFile}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;" />`;
  } else {
    photoEl.innerHTML = `<i class="bi bi-person"></i> Photo`;
  }
  
  document.getElementById('cid_preview_idx').textContent = `${cidPreviewIdx + 1} / ${cidSelectedStudents.length}`;
}

function cidPrevPreview() {
  if (cidPreviewIdx > 0) {
    cidPreviewIdx--;
    cidUpdatePreview();
  }
}

function cidNextPreview() {
  if (cidPreviewIdx < cidSelectedStudents.length - 1) {
    cidPreviewIdx++;
    cidUpdatePreview();
  }
}

// DRAG AND DROP LOGIC
let draggingEl = null;
let offset = { x: 0, y: 0 };

document.addEventListener('mousedown', function(e) {
  const el = e.target.closest('.cid-draggable');
  if (!el) return;
  
  draggingEl = el;
  draggingEl.classList.add('dragging');
  const rect = draggingEl.getBoundingClientRect();
  
  offset.x = e.clientX - rect.left;
  offset.y = e.clientY - rect.top;
});

document.addEventListener('mousemove', function(e) {
  if (!draggingEl) return;
  
  const parent = draggingEl.parentElement;
  const parentRect = parent.getBoundingClientRect();
  
  // Calculate relative position within parent, accounting for scale(0.8)
  const scale = 0.8;
  let x = (e.clientX - parentRect.left - offset.x) / scale;
  let y = (e.clientY - parentRect.top - offset.y) / scale;
  
  // Constrain
  x = Math.max(0, Math.min(x, parent.clientWidth - draggingEl.clientWidth));
  y = Math.max(0, Math.min(y, parent.clientHeight - draggingEl.clientHeight));
  
  draggingEl.style.left = x + 'px';
  draggingEl.style.top = y + 'px';
});

document.addEventListener('mouseup', function() {
  if (draggingEl) {
    draggingEl.classList.remove('dragging');
    draggingEl = null;
  }
});

// PDF GENERATION
async function cidGeneratePDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({
    orientation: 'landscape',
    unit: 'mm',
    format: [85.6, 54]
  });
  
  const btn = document.getElementById('cid_generate_btn');
  const status = document.getElementById('cid_generate_status');
  const progress = document.getElementById('cid_progress');
  
  btn.disabled = true;
  status.style.display = 'block';
  
  const total = cidSelectedStudents.length;
  const ratio = 85.6 / 323.5;
  
  const getPos = (id) => {
    const el = document.getElementById(id);
    return {
      x: parseFloat(el.style.left || 0) * ratio,
      y: parseFloat(el.style.top || 0) * ratio,
      w: el.clientWidth * ratio,
      h: el.clientHeight * ratio,
      fs: parseFloat(window.getComputedStyle(el).fontSize) * ratio
    };
  };

  const pos = {
    photo: getPos('cid_el_photo'),
    name: getPos('cid_el_name'),
    course: getPos('cid_el_course'),
    id: getPos('cid_el_id'),
    prog_full: getPos('cid_el_program_full'),
    year: getPos('cid_el_year'),
    sem: getPos('cid_el_semester'),
    contact: getPos('cid_el_contact')
  };

  for (let i = 0; i < total; i++) {
    progress.textContent = Math.round((i / total) * 100) + '%';
    const s = cidSelectedStudents[i];
    
    if (i > 0) doc.addPage([85.6, 54], 'landscape');
    
    // FRONT
    doc.addImage(cidTemplates.front, 'JPEG', 0, 0, 85.6, 54);
    const photoFile = (window.DASHBOARD_BOOTSTRAP.photos || {})[s.nfc_id];
    if (photoFile) {
       try {
         const imgData = await cidUrlToBase64(`/static/uploads/${photoFile}`);
         doc.addImage(imgData, 'JPEG', pos.photo.x, pos.photo.y, pos.photo.w, pos.photo.h);
       } catch(e) { console.error("Photo error", e); }
    }
    
    doc.setTextColor(0,0,0);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(pos.name.fs * 3); 
    doc.text(s.name || '', pos.name.x, pos.name.y + (pos.name.fs * 2.5));
    
    doc.setFontSize(pos.course.fs * 3);
    doc.setFont("helvetica", "normal");
    doc.text(s.course || s.program || '', pos.course.x, pos.course.y + (pos.course.fs * 2.5));
    
    doc.setFontSize(pos.id.fs * 3);
    doc.text('ID: ' + (s.student_id || ''), pos.id.x, pos.id.y + (pos.id.fs * 2.5));
    
    // BACK
    doc.addPage([85.6, 54], 'landscape');
    doc.addImage(cidTemplates.back, 'JPEG', 0, 0, 85.6, 54);
    
    doc.setFontSize(pos.prog_full.fs * 3);
    doc.text('Program: ' + (s.course || s.program || ''), pos.prog_full.x, pos.prog_full.y + (pos.prog_full.fs * 2.5));
    doc.text('Year Level: ' + (s.year_level || ''), pos.year.x, pos.year.y + (pos.year.fs * 2.5));
    doc.text('Semester: ' + (s.semester || ''), pos.sem.x, pos.sem.y + (pos.sem.fs * 2.5));
    doc.text('Contact: ' + (s.contact || ''), pos.contact.x, pos.contact.y + (pos.contact.fs * 2.5));
  }
  
  doc.save(`Student_IDs_${new Date().getTime()}.pdf`);
  btn.disabled = false;
  status.style.display = 'none';
}

function cidUrlToBase64(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous';
    img.onload = function() {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      resolve(canvas.toDataURL('image/jpeg', 0.9));
    };
    img.onerror = reject;
    img.src = url;
  });
}
