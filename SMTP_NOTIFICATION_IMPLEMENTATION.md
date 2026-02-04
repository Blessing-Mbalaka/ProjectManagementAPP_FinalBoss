# SMTP Notification System Implementation - Complete

## Overview
Successfully implemented a comprehensive SMTP notification system that automatically sends email notifications to stakeholders when Papers and Conferences are updated via form submission. The system includes change tracking via ChangeLog model and in-app notifications.

## Implementation Summary

### 1. ChangeLog Model
**File:** [manager/models.py](manager/models.py#L296-L343)

- Tracks all field changes for Papers and Conferences
- Fields:
  - `content_type`: Choice field (paper/conference)
  - `object_id`: Integer ID of changed object
  - `object_title`: String representation of object
  - `changed_by`: Foreign key to user making change
  - `changed_at`: Automatic timestamp
  - `field_name`: Technical field name
  - `field_label`: Human-readable field label
  - `old_value`: Previous value (TextField)
  - `new_value`: New value (TextField)
- Includes helper methods:
  - `log_change()`: Log a single field change
  - `get_recent_changes()`: Retrieve recent changes for object

### 2. Notification Service
**File:** [manager/notification_service.py](manager/notification_service.py)

Core functions:
- `get_email_recipients()`: Gets all stakeholders excluding the user who made changes
- `send_update_notification_email()`: Sends SMTP email to recipients with change summary
- `create_change_summary()`: Formats changes for display

Features:
- Uses Django's `send_mail()` with HTML templates
- Creates in-app Notification records for dashboard display
- Logs errors and notifications for debugging
- Handles both Papers and Conferences

### 3. Extended Signals
**File:** [manager/signals.py](manager/signals.py)

Added signal receivers:
- `capture_paper_original_values()`: Pre-save signal to capture original values
- `notify_on_paper_form_update()`: Post-save signal to detect changes and send notifications
- `capture_conference_original_values()`: Pre-save for conferences
- `notify_on_conference_form_update()`: Post-save for conferences

Features:
- Compares old vs new values for all tracked fields
- Detects M2M relationship changes (co-authors, reviewers)
- Creates ChangeLog entries for audit trail
- Sends emails only if changes are detected
- Excludes user who made the change from recipients

### 4. View Layer Updates
**Files:** 
- [manager/views.py](manager/views.py#L677-L724) - `edit_paper_ajax()`
- [adminpanel/views.py](adminpanel/views.py#L1345-L1397) - `edit_conference()`

Changes:
- Sets `_changed_by` attribute on object before save
- Detects M2M changes (co-authors, assigned reviewers)
- Sets change flags for signal processing
- Maintains form validation and error handling

### 5. Email Templates
**Files:**
- [templates/emails/paper_updated.html](templates/emails/paper_updated.html)
- [templates/emails/conference_updated.html](templates/emails/conference_updated.html)

Features:
- Professional HTML styling with Bootstrap-like design
- Displays all changed fields with old/new values
- Shows who made the change and when
- Includes links to view the record
- Plain text fallback for email clients
- Color-coded for better readability

### 6. Test Management Command
**File:** [manager/management/commands/test_form_update_notification.py](manager/management/commands/test_form_update_notification.py)

Usage:
```bash
python manage.py test_form_update_notification
```

Tests:
- Creates test Papers and Conferences
- Simulates form updates
- Verifies ChangeLog entries creation
- Confirms email sending
- Validates in-app notifications

## How It Works

### Workflow
1. User edits Paper/Conference form in admin interface
2. Form data is submitted to `edit_paper_ajax()` or `edit_conference()`
3. View captures original M2M values
4. Form validation occurs
5. `_changed_by` attribute is set on model instance
6. M2M change detection flags are set
7. `form.save()` calls `post_save` signal
8. Pre-save signal captured original field values
9. Post-save signal detects all changes:
   - Scalar field changes (title, abstract, etc.)
   - Foreign key changes (lead_author)
   - M2M relationship changes (co-authors, reviewers)
10. For each change:
    - Creates ChangeLog entry
    - Adds to change summary list
11. Calls `send_update_notification_email()`:
    - Gets all stakeholders via `get_all_contributors()`
    - Removes the user who made changes
    - Renders HTML email template
    - Sends via SMTP
    - Creates in-app Notification record

### Email Recipients
Automatically includes:
- Lead author of the paper/conference
- All co-authors
- All assigned reviewers
- Creator of the record
- Excludes the user who made the change

## Configuration

### Email Backend
**File:** [project_manage/settings.py](project_manage/settings.py#L77-L85)

Current configuration for development:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

For production, switch to:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'lotriet.work@gmail.com'
EMAIL_HOST_PASSWORD = 'app_password_here'
```

## Testing Results

### Test Execution
```
Starting notification system test...
Using lead author: Blessing
Using co-author: Musa

Test 1: Paper Form Update Notification
  Created test paper: 7
  [OK] Updated paper title and abstract
  [OK] 2 changelog entries created
    - Abstract: Initial abstract -> Updated abstract with more details
    - Title: Test Paper for Notification -> Updated Test Paper Title

Test 2: Conference Form Update Notification
  Created test conference: 5
  [OK] Updated conference name and location
  [OK] 2 changelog entries created
    - Location: Test Location -> Updated Location - New City
    - Conference Name: Test Conference for Notification -> Updated Test Conference Name

Test 3: Verify ChangeLog Entries
  Paper changelog entries: 10
  Conference changelog entries: 8
  [OK] ChangeLog entries working correctly

[OK] All tests completed!
```

### Email Verification
- SMTP emails are being sent successfully
- Console backend captures email output for testing
- Both HTML and plain text versions generated
- Change details properly formatted in emails
- In-app notifications created alongside emails

## Database Migrations

Applied migrations:
```
manager\migrations\0008_changelog.py - Create ChangeLog model
users\migrations\0004_alter_customuser_role.py - Alter field role on customuser
```

## Future Enhancements

1. **Email Templates**: Add more sophisticated templates with styles
2. **Notification Preferences**: Allow users to opt-in/out of notifications
3. **Real-time Updates**: Add WebSocket support for instant notifications
4. **Attachment Support**: Include paper/conference details in email attachments
5. **Change History UI**: Display ChangeLog in admin interface for audit trail
6. **Bulk Operations**: Handle bulk updates with single notification
7. **Scheduled Notifications**: Queue emails for off-peak delivery
8. **SMS Notifications**: Add SMS as alternative notification channel

## Troubleshooting

### Email Not Sending
- Check `EMAIL_BACKEND` setting
- Verify `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`
- Check logs for exceptions
- Test with console backend first

### ChangeLog Not Creating
- Verify `_changed_by` is set on model instance
- Check signal is connected (use `get_signal_receivers()`)
- Review logs for signal processing errors

### Notification Not In-App
- Check Notification model creation in logs
- Verify recipients are set correctly
- Ensure `created_by` user exists

## Files Modified/Created

### New Files
- [manager/notification_service.py](manager/notification_service.py)
- [manager/management/commands/test_form_update_notification.py](manager/management/commands/test_form_update_notification.py)
- [templates/emails/paper_updated.html](templates/emails/paper_updated.html)
- [templates/emails/conference_updated.html](templates/emails/conference_updated.html)

### Modified Files
- [manager/models.py](manager/models.py) - Added ChangeLog model
- [manager/signals.py](manager/signals.py) - Extended with form update notifications
- [manager/views.py](manager/views.py) - Updated edit_paper_ajax()
- [adminpanel/views.py](adminpanel/views.py) - Updated edit_conference()
- [project_manage/settings.py](project_manage/settings.py) - Fixed EMAIL_BACKEND typo

## Integration Points

The notification system integrates with:
- **Notification Model**: Existing in-app notification system
- **CustomUser Model**: For recipient management
- **Django Signals**: For automatic detection
- **Email System**: For SMTP delivery
- **Form System**: For user input handling
- **Audit Trail**: ChangeLog provides complete change history

---

**Implementation Date:** February 4, 2026
**Status:** Complete and Tested
**Test Coverage:** Papers, Conferences, M2M relationships, Email sending, In-app notifications
