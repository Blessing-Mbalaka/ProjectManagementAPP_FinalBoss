from django.contrib import admin
from .models import CostCentre, Expenditure, Notification, SupervisorProfile, SupervisorFeedback
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
