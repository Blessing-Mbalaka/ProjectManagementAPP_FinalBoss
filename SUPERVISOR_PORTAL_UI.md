# Supervisor Portal - User Interface Guide

## Navigation Structure

```
┌─────────────────────────────────────────────────────────────┐
│  🎓 UJ Logo                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 Dashboard                           ← Currently Active   │
│  💬 Messages                                                │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                        🚪 Logout                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Navigation Items:**
- Only 2 menu items (Dashboard, Messages)
- Logout button in footer
- Active items highlighted
- Mobile-responsive hamburger menu

---

## Page 1: Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  Welcome, Dr. Muranga                                       │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐
│  │ Supervised       │  │ Pending          │  │ Active       │
│  │ Students         │  │ Messages         │  │ Submissions  │
│  │                  │  │                  │  │              │
│  │       3          │  │        2         │  │       5      │
│  └──────────────────┘  └──────────────────┘  └──────────────┘
│
│  📋 My Supervised Students (3 Students)
│  ┌────────────────────────────────────────────────────────┐
│  │ Student Name | Email | Program | Year | Title | Action │
│  ├────────────────────────────────────────────────────────┤
│  │ Alice Johnson│ email │ Master  │ 2    │ AI... │ VIEW   │
│  │ Bob Smith    │ email │ Master  │ 2    │ ML... │ VIEW   │
│  │ Carol...     │ email │ Master  │ 2    │ BD... │ VIEW   │
│  └────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Statistics cards with key metrics
- My Students table with all assigned students
- Quick "View Details" button for each student
- Shows: Name, Email, Program, Year, Research Title

---

## Page 2: Messages

```
┌─────────────────────────────────────────────────────────────┐
│  💬 Messages                                                 │
│  Communicate with your supervised students                 │
│                                                              │
│  Student Conversations (3 Students)                         │
│  ┌────────────────────────────────────────────────────────┐
│  │ 👤 Alice Johnson                                        │
│  │    alice.johnson@student.edu                            │
│  │    ┌────────────────────────────────────────────────┐   │
│  │    │ Dr. Muranga: I received your submission... │   │
│  │    │ 2 hours ago                                    │   │
│  │    └────────────────────────────────────────────────┘   │
│  │                                   [Open Chat]            │
│  ├────────────────────────────────────────────────────────┤
│  │ 👤 Bob Smith                                            │
│  │    bob.smith@student.edu                                │
│  │    ┌────────────────────────────────────────────────┐   │
│  │    │ Bob Smith: Can I reschedule...                │   │
│  │    │ 1 day ago                                      │   │
│  │    └────────────────────────────────────────────────┘   │
│  │                                   [Open Chat]            │
│  └────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- List of all students with conversations
- Last message preview shown
- Timestamp of last message
- "Open Chat" button for each student

---

## Page 3: Student Detail

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                         │
│                                                              │
│  👤 Alice Johnson                                            │
│  Student Profile & Messages                                 │
│
│  ┌──────────────────────┐  ┌──────────────────────────────┐
│  │ 👤 Student Info      │  │ 💬 Messages with Alice       │
│  ├──────────────────────┤  ├──────────────────────────────┤
│  │ Full Name            │  │                              │
│  │ Alice Johnson        │  │ Dr. Muranga                  │
│  │                      │  │ Dec 15, 2024 10:30 AM       │
│  │ Email                │  │ ┌────────────────────────┐   │
│  │ alice@student.edu    │  │ │ Hi Alice, how are your │   │
│  │                      │  │ │ experiments going?     │   │
│  │ Program              │  │ └────────────────────────┘   │
│  │ Master's             │  │                              │
│  │                      │  │ Alice Johnson                │
│  │ Year                 │  │ Dec 15, 2024 11:15 AM       │
│  │ 2nd Year             │  │ ┌────────────────────────┐   │
│  │                      │  │ │ Great! I got results...│   │
│  │ Research Title       │  │ └────────────────────────┘   │
│  │ AI in Healthcare     │  │                              │
│  ├──────────────────────┤  │ [Type message here...] [SEND]│
│  │ 📊 Activity          │  │                              │
│  │ Total Messages: 5    │  │                              │
│  │ Submissions: 3       │  │                              │
│  │ Member Since: Jan 15 │  │                              │
│  └──────────────────────┘  └──────────────────────────────┘
│
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Back button to return to dashboard
- Left side: Student profile card with key information
- Right side: Full chat history (scrollable)
- Message form at bottom to send new messages
- Messages color-coded by sender

---

## User Flow Diagram

```
Login Page
    │
    ├─ Enter: prof_muranga / TestPass123!
    └─ Submit
         │
         ✓ Valid Credentials
         │
         └─ Redirect to Supervisor Dashboard
              │
              ├─ Dashboard (Home)
              │  ├─ View statistics
              │  ├─ See all supervised students
              │  └─ Click "View Details" → Student Detail Page
              │
              ├─ Messages
              │  ├─ See all conversations
              │  └─ Click "Open Chat" → Student Detail Page
              │
              ├─ Student Detail Page
              │  ├─ View student information
              │  ├─ Read chat history
              │  ├─ Send new message
              │  └─ Click "Back" → Return to Dashboard
              │
              └─ Logout
                 └─ Redirect to Login Page
```

---

## Key URL References

| Page | URL | Route Name |
|------|-----|-----------|
| Dashboard | `/adminpanel/supervisor-portal/dashboard/` | `supervisor_dashboard_portal` |
| Messages | `/adminpanel/supervisor-portal/messages/` | `supervisor_messages` |
| Student Detail | `/adminpanel/supervisor-portal/student/<id>/` | `supervisor_student_detail` |

---

## Component Breakdown

### Dashboard Page
- **Header:** Page title + subtitle
- **Statistics Row:** 3 cards with numbers
- **Main Section:** Students table with action buttons
- **Empty State:** "No students assigned yet" message

### Messages Page
- **Header:** Page title + conversation count badge
- **Conversation Items:** Each shows:
  - Student name with icon
  - Email address
  - Last message preview box
  - "Open Chat" button
- **Empty State:** "No conversations yet" message

### Student Detail Page
- **Navigation:** Back button
- **Header:** Student name + page subtitle
- **Left Column:** Two cards
  - Student Information card (5 fields)
  - Activity stats card (3 metrics)
- **Right Column:** Chat card
  - Scrollable message area
  - Messages from both directions
  - Message input form with Send button

---

## Styling & Colors

- **Primary Color:** Bootstrap primary (blue) - #0d6efd
- **Information Alert:** Light blue background
- **Success/Actions:** Primary color for buttons
- **Messages:** 
  - Supervisor messages → Light blue background
  - Student messages → White/gray background
- **Icons:** Bootstrap Icons (bi-* classes)
- **Responsive:** Works on mobile with collapsible sidebar

---

## Navigation Experience

### Desktop
- Fixed sidebar (can be collapsed)
- Full-width content area
- All menu items visible

### Mobile
- Hidden sidebar by default
- Hamburger menu button
- Sidebar slides in from left
- Closes when menu item clicked

---

## Empty States

**Dashboard - No Students:**
```
📥 
No students assigned to you yet.
```

**Messages - No Conversations:**
```
💬
No conversations yet
Messages from students will appear here when they start a conversation with you.
```

**Student Detail - No Messages:**
```
💬
No messages yet. Start the conversation!
```

---

## Success Indicators

✅ Page loads with supervisor info bar
✅ Sidebar shows only Dashboard and Messages items
✅ Logout button is accessible
✅ Student list displays correctly
✅ Message form works
✅ Chat history shows bidirectional messages
✅ Timestamps display correctly
✅ Navigation between pages works smoothly

---

## Error Handling

❌ Supervisor tries to access non-assigned student → 404 Page Not Found
❌ Non-supervisor tries to access portal → Redirects to admin dashboard
❌ Supervisor logs out → Redirects to login page
❌ Session expires → Redirects to login page
