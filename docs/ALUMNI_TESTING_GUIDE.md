# 🎓 Alumni & Semester Management — Testing Guide

## ✅ What Was Implemented

### 1. **Student Management Page** 
- Location: Admin Dashboard → Student Management
- Features:
  - View all students with status (Active, Graduated, Alumni)
  - Filter by status with tabs
  - Search by name, student ID, email, or NFC ID
  - Live statistics counters

### 2. **Change Student Status**
- Update any student's status: Active → Graduated → Alumni
- Real-time database update
- Status badges auto-update in UI

### 3. **Move to Next Semester**
- Only visible for Active students
- Move students between semesters: First → Second → Summer
- Update school year (e.g., 2024-2025 → 2025-2026)
- Auto-increments year when moving to next academic cycle

### 4. **Database Layer**
- `student_status` column added to students table
- Values: `'active'`, `'graduated'`, `'alumni'`
- All new students default to `'active'`
- Existing students auto-default to `'active'`

---

## 🧪 Testing Procedures

### **Test 1: Access Student Management Page**

**Steps:**
1. Log in as Admin or SuperAdmin
2. Look at left sidebar → Administration section
3. Click **"Student Management"** (icon: 👥✓)
4. Should see list of all students with status badges

**Expected Result:**
```
✅ Page loads with 4 stat cards showing:
   - Active Students (count)
   - Graduated (count)
   - Alumni (count)
   - Total Students (count)

✅ Student list displays with filters:
   - Active (default tab selected)
   - Graduated tab
   - Alumni tab
   - All Students tab
```

---

### **Test 2: Filter Students by Status**

**Steps:**
1. On Student Management page
2. Click the **"Graduated"** tab
3. Observe: Only students with status='graduated' show
4. Click **"Alumni"** tab
5. Observe: Only alumni students show

**Expected Result:**
```
✅ Tab switching filters students correctly
✅ Stats update to reflect filtered count
✅ Search still works within filtered results
```

---

### **Test 3: Search Functionality**

**Steps:**
1. In search bar, type a student's **name** (e.g., "Juan")
2. Observe: Results filtered to matching names
3. Clear and search by **student ID** (e.g., "2021-0001")
4. Observe: Shows student with that ID
5. Search by **NFC ID** (e.g., "0482AB12")
6. Observe: Shows student with that card

**Expected Result:**
```
✅ Real-time search across all visible fields
✅ Case-insensitive matching
✅ Multiple student results if matching
```

---

### **Test 4: Change Student Status**

**Steps:**
1. Find an Active student in the list
2. Click **"Change Status"** button on their card
3. Modal popup appears with student name
4. In dropdown, select **"Graduated"**
5. Click **"Update"** button
6. Wait for success message
7. Observe: Status badge changes to Graduated (blue)

**Expected Result:**
```
✅ Modal shows with student name: "Juan Dela Cruz"
✅ Status dropdown shows: [Active, Graduated, Alumni]
✅ Success toast appears: "Status updated to graduated"
✅ Student card refreshes with new status badge
✅ Stats update: Graduated count +1, Active count -1
```

**Test Status Transitions:**
- Active → Graduated ✅
- Graduated → Alumni ✅
- Alumni → Active ✅ (can revert)

---

### **Test 5: Move to Next Semester**

**Steps:**
1. Find an **Active** student with semester "First" and year "2024-2025"
2. Click **"Next Semester"** button (only visible for Active)
3. Modal appears with:
   - Current Semester: "First"
   - New Semester: auto-populated with "Second"
   - New School Year: auto-populated with "2025-2026"
4. Click **"Move Student"** button
5. Wait for success message
6. Page refreshes and shows new semester

**Expected Result:**
```
✅ Modal shows student name: "Maria Santos"
✅ Current Semester shows: "First"
✅ New Semester auto-set to: "Second"
✅ School Year auto-set to: "2025-2026"
✅ Success message: "Maria Santos moved to Second Semester 2025-2026"
✅ Student card now shows: "Second · 2025-2026"
```

**Test Semester Cycle:**
- First → Second ✅
- Second → Summer ✅
- Summer → First (next year) ✅

---

### **Test 6: Alumni Cannot Move Semesters**

**Steps:**
1. Change a student's status to **"Alumni"**
2. View that student in the list (use Alumni tab)
3. Observe: **"Next Semester"** button is NOT visible
4. Only **"Change Status"** button is available

**Expected Result:**
```
✅ Alumni students ONLY show "Change Status" button
✅ "Next Semester" button hidden (display:none)
```

---

### **Test 7: Graduated Students**

**Steps:**
1. Mark a student as **"Graduated"**
2. View in Graduated tab
3. Click **"Next Semester"** button (should appear)
4. Change status to **"Alumni"**
5. Observe: "Next Semester" button disappears

**Expected Result:**
```
✅ Graduated students CAN move to next semester
✅ Alumni students CANNOT move semesters
```

---

### **Test 8: Stats Update in Real-Time**

**Steps:**
1. Note initial counts at top:
   - Active: 25
   - Graduated: 3
   - Alumni: 2
2. Change one student from Active → Graduated
3. Observe stats update:
   - Active: 24 (-1) ✅
   - Graduated: 4 (+1) ✅
   - Alumni: 2 (no change)
4. Total should remain same

**Expected Result:**
```
✅ Stats cards update without page reload
✅ Counts always accurate
✅ Total unchanged when moving between categories
```

---

### **Test 9: Data Persists After Refresh**

**Steps:**
1. Change a student's status to "Graduated"
2. See success message
3. **Close and refresh the page** (Ctrl+R)
4. Navigate back to Student Management
5. Filter to "Graduated" tab

**Expected Result:**
```
✅ Student still shows as Graduated
✅ Data persisted in database
✅ Status survived page refresh
```

---

### **Test 10: Error Handling**

**Steps:**
1. Try to change a student's status but network drops
2. Try to move semester with invalid year format (e.g., "2025" instead of "2025-2026")
3. Try to move semester without selecting new semester

**Expected Result:**
```
✅ Error toast shows: "Failed to update status"
✅ Modal prevents "2025" format: "Invalid format (use YYYY-YYYY)"
✅ Button disabled while loading
```

---

## 📊 Testing Checklist

| Test Case | Status | Notes |
|-----------|--------|-------|
| Page loads correctly | ⬜ | [Test 1] |
| Filter by status works | ⬜ | [Test 2] |
| Search functionality works | ⬜ | [Test 3] |
| Change status updates DB | ⬜ | [Test 4] |
| Move semester works | ⬜ | [Test 5] |
| Alumni can't move semesters | ⬜ | [Test 6] |
| Graduated can move semesters | ⬜ | [Test 7] |
| Stats update in real-time | ⬜ | [Test 8] |
| Data persists after refresh | ⬜ | [Test 9] |
| Error handling works | ⬜ | [Test 10] |

---

## 🗄️ Database Verification

### Check student_status Column

```sql
-- In your database client:
SELECT nfcId, full_name, student_status, semester, school_year 
FROM students 
LIMIT 10;
```

**Expected columns:**
```
nfcId | full_name | student_status | semester | school_year
------|-----------|----------------|----------|-------------
048... | Juan      | active         | First    | 2024-2025
049... | Maria     | graduated      | First    | 2024-2025
050... | Jose      | alumni         | First    | 2024-2025
```

---

## 🔍 Browser Console Checks

When testing, open Browser DevTools (F12) → Console tab and check for:

✅ **No errors** in red
❌ **Avoid:**
```
Uncaught TypeError: Cannot read property 'endpoint' of undefined
Fetch failed: 404 not found
```

---

## 🚀 Deployment Notes

**Before deploying to Railway:**

1. Verify no syntax errors: ✅ Done
2. Test locally first (all 10 tests above)
3. Commit changes:
   ```bash
   git add -A
   git commit -m "Add Alumni & Semester Management features"
   ```
4. Push to Railway:
   ```bash
   git push origin main
   ```

---

## 📞 Quick Issue Fixes

**Issue: "Student Management" link not showing in sidebar**
- Clear browser cache (Ctrl+Shift+Delete)
- Restart Flask app

**Issue: Modal won't close**
- Hard refresh (Ctrl+Shift+R)
- Check console for JavaScript errors

**Issue: Stats show 0 students**
- Ensure you're logged in as Admin
- Check if students exist in database

---

## 🎯 Success Criteria

✅ All 10 tests pass
✅ Status changes persist after refresh
✅ Semester movement increments year correctly
✅ Alumni students cannot move semesters
✅ Stats counters accurate
✅ No console errors

**If all pass → Feature is production-ready! 🚀**
