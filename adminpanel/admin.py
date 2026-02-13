from django.contrib import admin
from .models import CostCentre, Expenditure, Notification, SupervisorProfile, SupervisorFeedback, ClockInRecord, AuditLog, UserAvailability, UserLeaveRequest

from .media_models import SystemMedia

# Register SystemMedia model
@admin.register(SystemMedia)
class SystemMediaAdmin(admin.ModelAdmin):
    list_display = ('filename', 'file_type', 'purpose', 'get_file_size_display', 'uploaded_by', 'related_model_name', 'uploaded_at', 'is_active')
    list_filter = ('file_type', 'purpose', 'is_active', 'uploaded_at', 'content_type')
    search_fields = ('filename', 'description', 'uploaded_by__username', 'uploaded_by__first_name', 'uploaded_by__last_name')
    readonly_fields = ('uploaded_at', 'created_at', 'updated_at', 'filename', 'file_size', 'related_object_display', 'related_model_name')
    fieldsets = (
        ('File Information', {
            'fields': ('file', 'filename', 'file_type', 'file_size', 'mime_type')
        }),
        ('Upload Details', {
            'fields': ('uploaded_by', 'uploaded_at', 'purpose', 'description')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id', 'related_object_display', 'related_model_name'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'deleted_at')
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_file_size_display(self, obj):
        return obj.get_file_size_display()
    get_file_size_display.short_description = 'File Size'
    
    def related_model_name(self, obj):
        return obj.related_model_name or 'N/A'
    related_model_name.short_description = 'Related Model'



@admin.register(ClockInRecord)
class ClockInRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'clock_in_time', 'status', 'duration_display')
    list_filter = ('status', 'clock_in_time')
    search_fields = ('employee__username',)
    readonly_fields = ('clock_in_time', 'duration_display')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only admin interface for immutable audit logs"""
    list_display = ('timestamp', 'get_user_display', 'get_action_display', 'entity_type', 'entity_name')
    list_filter = ('action', 'entity_type', 'timestamp')
    search_fields = ('entity_name', 'user__first_name', 'user__last_name', 'user__username')
    readonly_fields = ('action', 'entity_type', 'entity_id', 'entity_name', 'user', 'previous_values', 'new_values', 'timestamp')
    ordering = ['-timestamp']
    
    def get_user_display(self, obj):
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username}"
        return "System"
    get_user_display.short_description = 'User'
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit logs"""
        return False
    
    fieldsets = (
        ('Action Details', {
            'fields': ('timestamp', 'user', 'action')
        }),
        ('Entity Information', {
            'fields': ('entity_type', 'entity_id', 'entity_name')
        }),
        ('Changes', {
            'fields': ('previous_values', 'new_values')
        }),
    )


@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    """Admin interface for managing staff availability"""
    list_display = ('user', 'date', 'status', 'start_time', 'end_time', 'created_by')
    list_filter = ('status', 'date', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'reason', 'meeting_title')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('User & Date', {
            'fields': ('user', 'date')
        }),
        ('Availability Details', {
            'fields': ('status', 'start_time', 'end_time')
        }),
        ('Additional Information', {
            'fields': ('meeting_title', 'reason', 'is_personal'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('user', 'date')
        return self.readonly_fields


@admin.register(UserLeaveRequest)
class UserLeaveRequestAdmin(admin.ModelAdmin):
    """Admin interface for managing leave requests with approval workflow"""
    list_display = ('user', 'start_date', 'end_date', 'status', 'approved_by', 'approval_date')
    list_filter = ('status', 'start_date', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'reason')
    readonly_fields = ('created_at', 'updated_at', 'approval_date')
    date_hierarchy = 'start_date'
    actions = ['approve_leave', 'reject_leave']
    
    fieldsets = (
        ('Leave Request', {
            'fields': ('user', 'start_date', 'end_date', 'reason')
        }),
        ('Approval Status', {
            'fields': ('status', 'approved_by', 'approval_date', 'rejection_reason')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('user', 'start_date', 'end_date')
        return self.readonly_fields
    
    def approve_leave(self, request, queryset):
        """Bulk approve leave requests"""
        for leave_request in queryset.filter(status='pending'):
            leave_request.approve(request.user)
        self.message_user(request, f'{queryset.filter(status="approved").count()} leave request(s) approved.')
    approve_leave.short_description = 'Approve selected leave requests'
    
    def reject_leave(self, request, queryset):
        """Bulk reject leave requests"""
        count = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{count} leave request(s) rejected.')
    reject_leave.short_description = 'Reject selected leave requests'
