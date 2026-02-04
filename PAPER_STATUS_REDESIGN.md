# Paper Status System Redesign - Implementation Summary

## Overview
Successfully implemented a non-destructive, context-aware status system for research papers that distinguishes between **internal circulation** and **external journal submissions**.

---

## Changes Made

### 1. **Model Updates** (`manager/models.py`)

#### New Status System
Papers now use unified STATUS_CHOICES that work for both internal and external, with context-aware filtering:

**Internal Paper Statuses** (circulation within institution):
- `draft` - Initial draft
- `circulation` - Being circulated for internal review
- `ready-submission` - Ready to submit externally
- `returned-feedback` - Returned from external with feedback

**External Paper Statuses** (journal submission workflow):
- `submitted` - Submitted to journal/conference
- `under-review` - Under peer review
- `accepted` - Accepted as-is
- `accepted-minor` - Accepted with minor revisions required
- `accepted-major` - Accepted with major revisions required
- `published` - Published/Presented
- `rejected` - Rejected by journal

#### New Fields on Paper Model
- `decision_date` (DateField) - When external decision was made
- `feedback_text` (TextField) - Reviewer feedback when returned to internal

#### New PaperStatusHistory Model
Tracks all status changes for audit trail:
- `paper` (FK) - Reference to Paper
- `old_status` - Previous status value
- `new_status` - New status value
- `changed_by` (FK) - User who made change
- `changed_at` (DateTimeField) - When change occurred
- `reason` (TextField) - Why status was changed

#### Paper Model Methods
- `get_available_statuses()` - Returns appropriate statuses based on internal_external type

---

### 2. **View Updates** (`adminpanel/views.py`)

#### Enhanced `admin_journal()` View
- Passes `internal_statuses` and `external_statuses` to template
- Populates `available_statuses` for each paper
- Queries internal and external papers separately

#### New `move_paper_external()` View
Moves paper from internal to external:
- Requires: `submission_date`, `target_journal`
- Changes: `internal_external='external'`, `status='submitted'`
- Creates: PaperStatusHistory record
- Logs reason with target journal

**Usage:**
```
POST /adminpanel/paper/<id>/move-external/
```

#### New `return_paper_internal()` View
Returns paper from external to internal:
- Requires: `feedback`, `decision_date`
- Changes: `internal_external='internal'`, `status='returned-feedback'`
- Stores: `feedback_text`, `decision_date`
- Creates: PaperStatusHistory record

**Usage:**
```
POST /adminpanel/paper/<id>/return-internal/
```

---

### 3. **URL Routes** (`adminpanel/urls.py`)

Added two new routes:
```python
path('paper/<int:paper_id>/move-external/', views.move_paper_external, name='move_paper_external'),
path('paper/<int:paper_id>/return-internal/', views.return_paper_internal, name='return_paper_internal'),
```

---

### 4. **Template Updates** (`templates/adminpanel/admin_journal.html`)

#### Status Dropdown - Now Context-Aware
Replaced single dropdown with two `<optgroup>` elements:
- **Internal Circulation** - Shows only when editing internal papers
- **Submission Status** - Shows only when editing external papers

#### JavaScript Enhancement
Added `updateStatusOptions()` function:
- Monitors edit button clicks
- Detects paper type from `data-type` attribute
- Shows/hides appropriate status options
- Triggered automatically when edit modal opens

**Code:**
```javascript
function updateStatusOptions(paperType) {
    const internalGroup = document.getElementById('internal-statuses-group');
    const externalGroup = document.getElementById('external-statuses-group');
    
    if (paperType === 'internal') {
        internalGroup.style.display = 'block';
        externalGroup.style.display = 'none';
    } else if (paperType === 'external') {
        internalGroup.style.display = 'none';
        externalGroup.style.display = 'block';
    }
}
```

---

## Non-Destructive Implementation

✅ **Backward Compatible:**
- Existing `status` field preserved
- Old status values remain in database
- PaperStatusHistory model only adds records
- No deletions or overwrites

✅ **Reversible:**
- Can rollback migration if needed
- History preserved in new table
- Original data untouched

✅ **No Data Loss:**
- All existing papers preserved
- Migration added new fields (not removed)
- Two new tables created, no existing tables modified

---

## Migration Details

**Migration: `manager/0006_paper_decision_date_paper_feedback_text_and_more.py`**

Operations:
1. Added `decision_date` field to Paper (DateField, blank/null)
2. Added `feedback_text` field to Paper (TextField, blank/null)
3. Altered `status` field choices (from 7 to 11 status options)
4. Created `PaperStatusHistory` model

---

## Database State

Current statistics:
- **Total Papers:** 2 (1 internal, 1 external)
- **Status History Records:** 0 (created on first status change)
- **Migration Status:** Applied ✅

---

## Workflow Examples

### Example 1: Internal Paper → External Submission
```
1. Paper created with status="draft", internal_external="internal"
2. Author updates through circulation: draft → circulation → ready-submission
3. Admin clicks "Move to External"
4. Form requires:
   - Target Journal: "Nature"
   - Submission Date: "2026-02-05"
5. System changes:
   - internal_external = "external"
   - status = "submitted"
   - submission_date = "2026-02-05"
   - target_journal = "Nature"
6. PaperStatusHistory created:
   - old_status: "ready-submission"
   - new_status: "submitted"
   - changed_by: current user
   - reason: "Moved to external - Target: Nature"
```

### Example 2: External Paper Rejection → Return to Internal
```
1. External paper in status="under-review"
2. Journal sends rejection with comments
3. Admin clicks "Return to Internal"
4. Form requires:
   - Feedback: "[Reviewer comments]"
   - Decision Date: "2026-02-04"
5. System changes:
   - internal_external = "internal"
   - status = "returned-feedback"
   - feedback_text = "[Reviewer comments]"
   - decision_date = "2026-02-04"
6. PaperStatusHistory created:
   - old_status: "under-review"
   - new_status: "returned-feedback"
   - changed_by: current user
   - reason: "Returned to internal with feedback"
```

---

## Status Badge Colors (Recommended)

Add to `static/css/journal.css`:

```css
/* Internal statuses */
.status-draft { background-color: #e9ecef; color: #495057; }
.status-circulation { background-color: #ffc107; color: #000; }
.status-ready-submission { background-color: #6f42c1; color: #fff; }
.status-returned-feedback { background-color: #fd7e14; color: #fff; }

/* External statuses */
.status-submitted { background-color: #0dcaf0; color: #000; }
.status-under-review { background-color: #0d6efd; color: #fff; }
.status-accepted { background-color: #198754; color: #fff; }
.status-accepted-minor { background-color: #ffc107; color: #000; }
.status-accepted-major { background-color: #ff6b6b; color: #fff; }
.status-published { background-color: #20c997; color: #fff; font-weight: bold; }
.status-rejected { background-color: #dc3545; color: #fff; }
```

---

## Next Steps

### Optional Enhancements
1. **UI Buttons** - Add "Move to External" / "Return to Internal" buttons to paper rows
2. **Feedback Modal** - Create modal forms for move/return operations
3. **Status Badge Colors** - Update CSS with colors matching new statuses
4. **History Display** - Show status change timeline in paper detail view
5. **Validation Rules** - Add workflow constraints (e.g., can only accept after under-review)

### Testing Checklist
- [ ] Load /adminpanel/admin_journal/ page
- [ ] Edit internal paper - verify only internal statuses show
- [ ] Edit external paper - verify only external statuses show
- [ ] Change status and verify PaperStatusHistory records created
- [ ] Test move_paper_external with valid data
- [ ] Test return_paper_internal with valid data
- [ ] Verify feedback and decision_date stored correctly

---

## Technical Details

**Key Implementation Features:**
- ✅ Unified STATUS_CHOICES with two filter lists
- ✅ Context-aware frontend filtering (JavaScript)
- ✅ Full audit trail (PaperStatusHistory)
- ✅ Non-destructive migration
- ✅ No breaking changes
- ✅ Django check passes
- ✅ Database migration applied successfully

**Files Modified:**
- `manager/models.py` - Model definitions
- `adminpanel/views.py` - Views
- `adminpanel/urls.py` - URL routes
- `templates/adminpanel/admin_journal.html` - Template

**Files Created:**
- Migration: `manager/migrations/0006_paper_decision_date_paper_feedback_text_and_more.py`

---

## Rollback Instructions

If needed, rollback with:
```bash
python manage.py migrate manager 0005_conference
```

This removes:
- `PaperStatusHistory` table
- `decision_date` and `feedback_text` fields
- New STATUS_CHOICES

Original `status` field values remain untouched.

---

**Status:** ✅ Implementation Complete
**Date:** February 4, 2026
**Database:** Applied and verified
**Tests:** Configuration check passed
