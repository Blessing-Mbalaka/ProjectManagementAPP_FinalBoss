# Test Users Documentation

## Overview
This document provides credentials and instructions for testing the supervisor messaging feature and supervisor dashboard functionality.

## Test Users Created

### Supervisors (role='supervisor')

| Username | Password | Name | Email | Role |
|----------|----------|------|-------|------|
| `prof_muranga` | `TestPass123!` | Dr. Muranga | muranga@university.edu | Supervisor |
| `prof_adeyemi` | `TestPass123!` | Prof. Adeyemi | adeyemi@university.edu | Supervisor |
| `prof_okonkwo` | `TestPass123!` | Dr. Okonkwo | okonkwo@university.edu | Supervisor |

### Students (role='student')

| Username | Password | Name | Email | Assigned Supervisor | Research Title |
|----------|----------|------|-------|---------------------|-----------------|
| `student_test1` | `StudentPass123!` | Alice Johnson | alice.johnson@student.edu | Dr. Muranga | AI Applications in Healthcare |
| `student_test2` | `StudentPass123!` | Bob Smith | bob.smith@student.edu | Prof. Adeyemi | Machine Learning for Climate Prediction |
| `student_test3` | `StudentPass123!` | Carol Williams | carol.williams@student.edu | Dr. Okonkwo | Big Data Analytics in Finance |

## Testing Scenarios

### Test 1: Student Messaging Supervisor

**Objective:** Verify students can send messages to their assigned supervisor

**Steps:**
1. Login as `student_test1` / `StudentPass123!`
2. Navigate to `/projects/student_dashboard/`
3. Scroll to "Chat with Supervisor" section
4. Verify supervisor name shows "Dr. Muranga"
5. Type a message and click Send
6. Check server terminal for debug output:
   ```
   === SEND CHAT MESSAGE DEBUG ===
   Sender: Alice Johnson (ID: X, Role: student)
   ...
   ✓ Message SAVED (ID: Y)
   === END DEBUG ===
   ```

### Test 2: Supervisor Viewing Messages

**Objective:** Verify supervisors can see student messages and reply

**Steps:**
1. Login as `prof_muranga` / `TestPass123!`
2. Navigate to `/adminpanel/supervisor_dashboard/`
3. Verify page title is "My Supervised Students" (supervisor-only UI)
4. Verify sidebar only has "My Students" menu item (limited access)
5. Click "View Details" for Alice Johnson
6. Scroll to "Chat with Supervisor" section
7. Verify Alice's message appears
8. Type a reply and click Send
9. Verify message saved with debug output in server terminal

### Test 3: Cross-Supervisor Access Prevention

**Objective:** Verify supervisors cannot access students they don't supervise

**Steps:**
1. Login as `prof_muranga` / `TestPass123!`
2. Navigate to supervisor dashboard
3. Try to access Bob Smith's detail page via URL directly:
   ```
   http://127.0.0.1:8000/adminpanel/supervisor/student/X/
   ```
   where X is Bob Smith's user ID
4. Verify you get a 404 or "Permission denied" error
5. This proves cross-supervisor access is blocked

### Test 4: Admin vs Supervisor UI Differences

**Objective:** Verify different UI for admin vs supervisor roles

**Steps:**

**As Supervisor:**
1. Login as `prof_muranga` / `TestPass123!`
2. Navigate to `/adminpanel/supervisor_dashboard/`
3. Observe:
   - Limited sidebar (only "My Students")
   - Uses `supervisor_only_dashboard.html` template
   - No access to Papers, Books, Finance, Manage Users

**As Admin (Blessing/Arnesh):**
1. Login as admin/superuser
2. Navigate to `/adminpanel/supervisor_dashboard/`
3. Observe:
   - Full admin sidebar with all menu items
   - Uses `supervisor_dashboard.html` template
   - Access to all admin features

### Test 5: Message Bidirectional Flow

**Objective:** Verify messages flow correctly both directions

**Steps:**
1. Login as `student_test1` / `StudentPass123!`
2. Send message: "Hello Professor, I have a question"
3. Logout
4. Login as `prof_muranga` / `TestPass123!`
5. Go to Alice Johnson's student detail
6. Verify message appears in chat
7. Send reply: "Hello Alice, please tell me your question"
8. Logout
9. Login as `student_test1` again
10. Go to student dashboard
11. Verify professor's reply appears in chat section

## Key Features to Verify

✅ **Supervisor Role:**
- [x] Can login with supervisor credentials
- [x] Sees limited navbar (only "My Students")
- [x] Can view assigned students
- [x] Can see student detail page with chat
- [x] Can send messages to students
- [x] Cannot access other admin features

✅ **Student Role:**
- [x] Can login with student credentials
- [x] Sees "Chat with Supervisor" on dashboard
- [x] Supervisor name is dynamically loaded
- [x] Can send messages to assigned supervisor
- [x] Can receive replies from supervisor
- [x] Cannot message other supervisors

✅ **Permission Checks:**
- [x] Supervisor cannot view students they don't supervise
- [x] Supervisor cannot message students they don't supervise
- [x] Student can only message their assigned supervisor
- [x] Debug logs show permission failures

## Debug Output Examples

### Successful Student Message Send:
```
=== SEND CHAT MESSAGE DEBUG ===
Sender: Alice Johnson (ID: 5, Role: student)
Request POST data: <QueryDict: {'csrfmiddlewaretoken': [...], 'message': 'Hello Professor'}>
Form valid: True
Message content: 'Hello Professor'
Student -> Supervisor: Recipient set to Dr. Muranga (ID: 8)
✓ Message SAVED (ID: 42)
=== END DEBUG ===
```

### Successful Supervisor Message Send:
```
=== SEND CHAT MESSAGE DEBUG ===
Sender: Dr. Muranga (ID: 8, Role: supervisor)
Request POST data: <QueryDict: {..., 'student_id': '5', 'message': 'Hi Alice, ...'}>
Form valid: True
Message content: 'Hi Alice, ...'
Student ID from POST: 5
Student found: Alice Johnson (ID: 5)
Student's supervisor: Dr. Muranga (ID: 8)
Current supervisor: Dr. Muranga (ID: 8)
✓ Permission granted - Recipient set to Alice Johnson
✓ Message SAVED (ID: 43)
=== END DEBUG ===
```

### Permission Denied:
```
=== SEND CHAT MESSAGE DEBUG ===
Sender: Prof. Adeyemi (ID: 9, Role: supervisor)
Student ID from POST: 5
Student found: Alice Johnson (ID: 5)
Student's supervisor: Dr. Muranga (ID: 8)
Current supervisor: Prof. Adeyemi (ID: 9)
✗ Permission denied - Supervisor not authorized for this student
✗ Message NOT saved - No recipient set
=== END DEBUG ===
```

## How to Run Tests

1. Start the Django server:
   ```bash
   cd "c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage"
   python manage.py runserver 8000
   ```

2. Open browser to `http://127.0.0.1:8000/`

3. Use credentials from tables above to login

4. Watch server terminal for debug output when sending messages

## Resetting Test Data

To reset all test users and start fresh:

```bash
# Delete test users from Django shell
python manage.py shell
>>> from users.models import CustomUser
>>> CustomUser.objects.filter(username__startswith='student_test').delete()
>>> CustomUser.objects.filter(username__startswith='prof_').delete()
>>> exit()

# Then recreate them
python create_test_users.py
```

## Admin Panel Access

To manage users and change roles:

1. Login as Blessing (superuser)
2. Navigate to `/admin/`
3. Users section allows:
   - Changing role from 'admin' to 'supervisor' or vice versa
   - Creating new admin/supervisor accounts
   - Managing student assignments

## Notes

- All test users have `is_active=True` (can login)
- Supervisors have `is_staff=False` (cannot access Django admin)
- Admin user has full system access and can change any role
- Supervisor dashboard automatically redirects to limited UI based on role
- Debug prints in `send_chat_message` view help troubleshoot messaging issues
