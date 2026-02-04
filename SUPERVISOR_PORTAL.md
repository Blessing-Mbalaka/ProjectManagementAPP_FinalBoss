# Supervisor Portal - Complete Setup

## Overview
A dedicated supervisor portal has been created with complete isolation from the admin panel. Supervisors are now routed to their own dedicated interface with limited navigation.

## Portal Structure -----

### Navigation (2 Items Only)
1. **Dashboard** - View all supervised students
2. **Messages** - View conversations with students
3. **Logout** - Exit the portal

### URL Routes

All supervisor portal URLs are located under `/adminpanel/supervisor-portal/`:

```
/adminpanel/supervisor-portal/dashboard/     → Supervisor Dashboard
/adminpanel/supervisor-portal/messages/      → Messages Page
/adminpanel/supervisor-portal/student/<id>/  → Student Detail Page
```

### Templates Location

All supervisor templates are in `templates/supervisors/`:

```
templates/supervisors/
├── base.html                # Main supervisor template with 2-item nav
├── dashboard.html           # Dashboard with My Students section
├── messages.html            # Messages & conversations with students
└── student_detail.html      # Individual student detail & chat
```

## Features

### 1. Supervisor Dashboard (`/adminpanel/supervisor-portal/dashboard/`)
- **Statistics Cards:**
  - Total supervised students
  - Pending messages count
  - Active submissions count
  
- **My Students Section:**
  - Table of all assigned students
  - Quick view: Name, Email, Program, Year, Research Title
  - "View Details" button for each student
  - Shows "No students assigned" when empty

### 2. Messages Page (`/adminpanel/supervisor-portal/messages/`)
- **Conversation List:**
  - One entry per supervised student
  - Shows last message preview
  - Timestamp of last message
  - "Open Chat" button links to student detail page
  
- **Empty State:**
  - Shows friendly message when no conversations exist

### 3. Student Detail Page (`/adminpanel/supervisor-portal/student/<id>/`)

**Left Column - Student Info:**
- Full Name
- Email (with mailto link)
- Program
- Year
- Research Title
- Statistics:
  - Total messages with student
  - Submission count
  - Member since date

**Right Column - Chat:**
- Full message history (scrollable)
- Messages styled differently for sender vs. recipient
- Message form to send new messages
- "Send" button to post messages

## Views Implementation

### File: `adminpanel/supervisors.py` (NEW)

Three dedicated views for supervisor functionality:

```python
@login_required
def supervisor_dashboard(request):
    # Routes to templates/supervisors/dashboard.html
    # Shows all supervised students
    # Only accessible to role='supervisor'

@login_required
def supervisor_messages(request):
    # Routes to templates/supervisors/messages.html
    # Shows all conversations with students
    # Only accessible to role='supervisor'

@login_required
def supervisor_student_detail(request, student_id):
    # Routes to templates/supervisors/student_detail.html
    # Shows individual student with chat
    # Permission check: student must be supervised by request.user
```

**Key Features:**
- Check `if not is_supervisor(request.user)` to verify role
- Redirect to admin dashboard if not supervisor
- Permission checks prevent cross-supervisor access
- Prefetch related data for performance
- Order by `user__last_name` for consistent display

## Login Redirection

Updated `users/views.py` login_view to route supervisors:

```python
if user.role == 'supervisor':
    return redirect('supervisor_dashboard_portal')
```

**Routing Logic:**
- Admin users → `/adminpanel/overview/` (admin dashboard)
- Supervisors → `/adminpanel/supervisor-portal/dashboard/` (supervisor portal)
- Managers → Manager dashboard
- Students → Student dashboard
- Staff → General dashboard

## URL Configuration

Updated `adminpanel/urls.py` with supervisor portal routes:

```python
# Import supervisor views
from . import supervisors

# Supervisor Portal Routes
path('supervisor-portal/dashboard/', supervisors.supervisor_dashboard, name='supervisor_dashboard_portal'),
path('supervisor-portal/messages/', supervisors.supervisor_messages, name='supervisor_messages'),
path('supervisor-portal/student/<int:student_id>/', supervisors.supervisor_student_detail, name='supervisor_student_detail'),
```

## Sidebar Navigation

### Supervisor Base Template
**File:** `templates/supervisors/base.html`

Only displays 2 navigation items:
1. Dashboard (icon: `bi-speedometer2`)
2. Messages (icon: `bi-chat-dots`)

Sidebar footer has Logout button.

Active nav items are highlighted based on current URL.

## Security Features

### Permission Checks
1. **Role Verification:** `if not is_supervisor(request.user): redirect('admin_dashboard')`
2. **Supervisor-Student Relationship:** `if student_profile.supervisor != request.user: raise Http404`
3. **Message Filtering:** Only show messages between supervisor and student

### Isolation from Admin
- Supervisors cannot access admin panel
- Supervisors cannot access admin features
- No admin menu items visible
- Dedicated templates keep UI completely separate

## Database Queries

### Student Profiles
```python
student_profiles = StudentProfile.objects.filter(
    supervisor=supervisor
).select_related('user').order_by('user__last_name')
```

### Chat Messages
```python
chat_messages = ChatMessage.objects.filter(
    Q(sender=student_user, recipient=request.user) |
    Q(sender=request.user, recipient=student_user)
).order_by('timestamp')
```

## Testing Supervisor Portal

### Test Login
**Credentials:**
- Username: `prof_muranga`
- Password: `TestPass123!`
- Role: `supervisor`

### Expected Flow
1. Login with supervisor credentials
2. Auto-redirected to `/adminpanel/supervisor-portal/dashboard/`
3. See "My Supervised Students" section
4. Click "View Details" on a student
5. See student profile + chat history
6. Send a message to the student
7. Navigate to "Messages" to see all conversations

### Verify Isolation
1. Try accessing `/adminpanel/overview/` as supervisor → Should redirect
2. Try accessing `/adminpanel/admin_dashboard/` as supervisor → Should redirect
3. Try accessing another supervisor's students → Should get 404

## Migration Notes

No database migrations required. The supervisor portal uses existing:
- CustomUser model (role='supervisor' already added)
- StudentProfile model (accepts 'supervisor' role)
- ChatMessage model (already has sender/recipient fields)

## File Summary

### New Files Created
- `adminpanel/supervisors.py` - Supervisor views
- `templates/supervisors/base.html` - Supervisor base template
- `templates/supervisors/dashboard.html` - Supervisor dashboard
- `templates/supervisors/messages.html` - Messages page
- `templates/supervisors/student_detail.html` - Student detail

### Modified Files
- `adminpanel/urls.py` - Added supervisor portal routes
- `users/views.py` - Added supervisor login redirection

## Next Steps

1. **Test the supervisor portal** with `prof_muranga` / `TestPass123!`
2. **Verify isolation** - Try accessing admin pages as supervisor
3. **Test messaging** - Send messages from supervisor to student and vice versa
4. **Check permissions** - Verify supervisors can't see other supervisor's students

## Troubleshooting

### Supervisor redirects to admin dashboard
- Check `is_supervisor()` function in `supervisors.py`
- Verify user role is exactly 'supervisor' (case-sensitive)

### Can't access student detail
- Verify student is in StudentProfile with supervisor=request.user
- Check console for "You don't have permission..." error

### Messages not appearing
- Verify ChatMessage records exist in database
- Check sender/recipient IDs are correct
- Ensure filter uses Q objects for OR logic

### URLs not working
- Clear browser cache
- Verify supervisor portal routes added to adminpanel/urls.py
- Check URL name is `supervisor_dashboard_portal`, not `supervisor_dashboard`
