# Railway Session Auto-Start Debugging Guide

## Problem: Sessions Start on Localhost but Not on Railway

### Why This Happens

**Session Storage:** Sessions ARE properly stored in PostgreSQL and persist across container restarts. ✅

**Issue Identified:** Timezone mismatch between your browser local time and Railway server time.

- Your browser runs JavaScript that checks `new Date()` (your local timezone)
- Railway server runs in UTC timezone (or different timezone)
- If you're in UTC+8 and Railway is UTC, schedule times are off by 8 hours
- Example: You schedule session for 2:00 PM (your time), but server sees 6:00 AM

### Solution

We've implemented **server-side automatic session starting** that doesn't depend on your browser. Sessions now start automatically when the scheduled time arrives on the server.

---

## How to Debug

### Step 1: Check Server Time and Status

Visit: `https://your-railway-app.up.railway.app/api/diagnostics`

You'll see JSON like:

```json
{
  "server_time": "2024-12-15 06:00:00",
  "server_weekday": "Sun",
  "active_sessions_count": 2,
  "active_sessions": [...],
  "schedules_today": [...],
  "automation_running": true,
  "automation_thread_name": "davs-automation-loop"
}
```

**Check these:**

- ✅ `"automation_running": true` - automation thread is active
- ✅ Server time matches your expectation (or note the UTC difference)
- ✅ `"schedules_today"` shows your created schedules

### Step 2: Monitor Active Sessions

Visit: `https://your-railway-app.up.railway.app/api/active_sessions`

Shows all currently running sessions:

```json
{
  "active_count": 1,
  "sessions": [
    {
      "sess_id": "a1b2c3d4e5f",
      "subject": "Introduction to Computer Science",
      "teacher": "john_doe",
      "section": "BS Information Technology|1st Year|A",
      "started_at": "2024-12-15 06:00:00",
      "students_present": 15,
      "students_late": 2
    }
  ]
}
```

---

## How Server-Side Auto-Start Works

1. **Background Thread:** Runs every 5 seconds checking for scheduled sessions
2. **Timing:** Triggers when current server time falls within schedule window
3. **Independent:** Works even if no teacher is logged in or looking at page
4. **Logging:** Every 60 seconds, logs heartbeat with active session count

### Example Timeline

```
06:00:00 - [AUTO] Heartbeat: 2024-12-15 06:00:00 | Active sessions: 0
          Schedule matches (start_time = 06:00, end_time = 08:00)
          Session auto-starts immediately
          Database updated: sessions table

06:00:15 - Student NFC tap recorded
          Blockchain logs attendance
          Email sent to student

07:30:00 - [AUTO] Heartbeat: 2024-12-15 07:30:00 | Active sessions: 1

08:00:00 - Schedule end time reached
          [AUTO] Ended session (Schedule End Time Reached)
          Session marked as ended
          Attendance finalized
          Teacher receives summary email
```

---

## Troubleshooting Checklist

### ✓ Session isn't auto-starting

**Debug:** Check diagnostics endpoint

```
1. Is "automation_running" true?
   If false: Server needs to process a request first
   Solution: Visit any page, then check diagnostics again

2. Are "schedules_today" showing?
   If empty: Schedule isn't created or not active for today
   Solution: Create schedule, verify day_of_week matches today

3. Is server_time in the right window?
   Example: schedule 06:00-08:00, server_time 06:30 should auto-start
   Solution: Wait for correct time or create test schedule for current time
```

**Check Railway Logs:**

```
Look for [AUTO] messages:

✓ Good:  "[AUTO] Started session 23abc... for Intro to CS (john_doe)"
✗ Bad:   "[AUTO ERROR] [some error message]"
```

### ✓ Session started but students can't tap

**Possible causes:**

1. Session is actually a past/ended session (check `ended_at`)
2. Student section doesn't match session section
3. NFC scanner not configured

**Debug:**

```
GET /api/session_attendance/<session_id>
Look for:
  - "students_involved_count" > 0
  - "session_key" matches student's section
```

### ✓ Multiple sessions for same subject/section

**This is OK** - means schedules ran multiple times (likely testing)

**To clean up:**

```
Via Admin Dashboard:
1. Go to Admin > Sessions (if available)
2. End old sessions manually
3. Or delete rows from sessions table if comfortable with database
```

---

## Expected Behavior After Fix

### On Localhost (Before)

- Manual button click required
- Or JavaScript auto-start when browser on page
- If browser closed, session doesn't start

### On Railway (After)

- ✓ Sessions start automatically at scheduled time
- ✓ Works even if no one is logged in
- ✓ Works across container restarts
- ✓ Survives midnight/day changes
- ✓ All attendees notified via email

---

## Advanced: Manual Testing

### Create a Test Schedule for Exact Time

1. Go to Admin Dashboard
2. Create Schedule:

   - Subject: "Test Auto-Start"
   - Section: Any active section
   - Day: Today
   - Start time: **Current server time + 2 minutes**
   - End time: Current server time + 5 minutes

3. Wait for start time to arrive
4. Check `/api/active_sessions` - session should auto-appear
5. Check `/api/diagnostics` - should log [AUTO] Started session

### Monitor the Logs in Real-Time

Railway Logs dashboard:

```bash
# Watch for these patterns:
[AUTO] Checking X schedule(s) for today
[AUTO] Started session XXXXX for [subject]
[AUTO] Ended session XXXXX (Schedule End Time Reached)
[AUTO] Heartbeat: ....
```

---

## Questions?

If diagnostics show:

- ❌ `"automation_running": false`
  → Server needs first HTTP request to start automation
- ❌ `"schedules_today": []`
  → Create a schedule for today
- ❌ `"server_time"` is UTC
  → Note the timezone difference (Railway = UTC)
  → Schedule times should match server UTC time

---

## Rollback Plan

If issues persist, you can:

1. Manually start each session via Dashboard
2. Revert to client-side auto-start only (browser on page)
3. Contact development team for server configuration audit

---

**Last Updated:** 2024-12-15  
**Railway Session Feature:** Enabled with server-side automatic session starting
