from django.urls import path
from . import views
from . import supervisors
from . import notification_views
from . import api_booking_views
from .clock_views import clock_in, clock_out, get_clock_status, clock_history

urlpatterns = [
    # Supervisor Portal Routes
    path('supervisor-portal/dashboard/', supervisors.supervisor_dashboard, name='supervisor_dashboard_portal'),
    path('supervisor-portal/messages/', supervisors.supervisor_messages, name='supervisor_messages'),
    path('supervisor-portal/student/<int:student_id>/', supervisors.supervisor_student_detail, name='supervisor_student_detail'),
    
    # Admin Routes
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('communique/', views.communique, name='communique'),
    path('admin_book/', views.admin_book, name='admin_book'),
    path('update-book-status/<int:book_id>/', views.update_book_status, name='update_book_status'),
    path('app_kanban/', views.app_kanban, name='app_kanban'),
    path('admin_journal/', views.admin_journal, name='admin_journal'),
    path('paper/<int:paper_id>/move-external/', views.move_paper_external, name='move_paper_external'),
    path('paper/<int:paper_id>/return-internal/', views.return_paper_internal, name='return_paper_internal'),
    path('conferences/', views.admin_conferences, name='admin_conferences'),
    path('add-conference/', views.add_conference, name='add_conference'),
    path('edit-conference/<int:conference_id>/', views.edit_conference, name='edit_conference'),
    path('delete-conference/<int:conference_id>/', views.delete_conference, name='delete_conference'),
    path('conference/<int:conference_id>/form-html/', views.get_conference_form_html, name='get_conference_form_html'),
    path('conference/<int:conference_id>/data/', views.get_conference_data, name='get_conference_data'),
    path('admin_ganttchart/', views.admin_ganttchart, name='admin_ganttchart'),
    path('overview/', views.overview, name='overview'),
    path('finance/', views.finance, name='finance'),
    path('finance-readonly/', views.finance_readonly, name='finance_readonly'),
    path('admin_kanban/', views.admin_kanban, name='admin_kanban'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('supervisor/student/<int:student_id>/', views.student_detail_view, name='student_detail'),
    path('supervisor_dashboard/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('finance/add-cost-centre/', views.add_cost_centre, name='add_cost_centre'),
    path('finance/add-payment/', views.add_payment, name='add_payment'),
    path('finance/delete-payment/<int:payment_id>/', views.delete_payment, name='delete_payment'),
    path('finance/expenditures/<int:cost_centre_id>/', views.get_expenditures, name='get_expenditures'),
    path('feedback/<int:submission_id>/', views.provide_feedback, name='provide_feedback'),
    path('finance/add-expenditure/', views.add_expenditure, name='add_expenditure'),
    path('finance/delete-cost-centre/<int:pk>/', views.delete_cost_centre, name='delete_cost_centre'),
    path('finance/edit-cost-centre/<int:pk>/', views.edit_cost_centre, name='edit_cost_centre'),
    path('finance/edit-expenditure/<int:pk>/', views.edit_expenditure, name='edit_expenditure'),
    path('finance/delete-expenditure/<int:pk>/', views.delete_expenditure, name='delete_expenditure'),
    path('finance/update-expenditure/<int:pk>/', views.update_expenditure, name='update_expenditure'),
    
    # Budget Forecast Routes
    path('finance/add-budget-forecast/', views.add_budget_forecast, name='add_budget_forecast'),
    path('finance/forecasts/<int:cost_centre_id>/', views.get_budget_forecasts, name='get_budget_forecasts'),
    path('finance/delete-budget-forecast/<int:pk>/', views.delete_budget_forecast, name='delete_budget_forecast'),
    path('finance/release-forecasts/<int:cost_centre_id>/', views.release_budget_forecasts, name='release_budget_forecasts'),
    
    path('user-kanban/<int:user_id>/', views.admin_user_kanban, name='admin_user_kanban'),
    path('assign-project/', views.assign_project, name='admin_assign_project'),
    path('create-project/', views.create_project, name='admin_create_project'),
    path('update-project/<int:project_id>/', views.update_project, name='admin_update_project'),
    path('delete-project/<int:project_id>/', views.delete_project, name='admin_delete_project'),
    path('projects-json/', views.get_projects_json, name='admin_get_projects_json'),
    path('api/gantt-data/', views.gantt_data_api, name='gantt_data_api'),
    path('admin/project-tasks/<str:project_name>/', views.project_task_detail, name='project_task_detail'),
    path('admin/update-task-progress/<int:task_id>/', views.update_task_progress, name='update_task_progress'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('create-user/', views.create_user, name='create_user'),
    path('activate-user/<int:user_id>/', views.activate_user, name='activate_user'),
    path('deactivate-user/<int:user_id>/', views.deactivate_user, name='deactivate_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('api/user-activity/', views.user_activity_api, name='user_activity_api'),
    path('register_users/',views.register_users,name='register_users'),
        path('load-student-manual/', views.load_student_manual, name='load_student_manual'),
    path('load-students-csv/', views.load_students_csv, name='load_students_csv'),
    path('notifications/create/', views.create_notification, name='create_notification'),
    path('api/notifications/', notification_views.get_user_notifications, name='get_user_notifications'),
    path('api/notifications/<int:notification_id>/read/', notification_views.mark_notification_read, name='mark_notification_read'),
    path('clock-in/', clock_in, name='clock_in'),
    path('clock-out/', clock_out, name='clock_out'),
    path('clock-status/', get_clock_status, name='clock_status'),
    path('clock-history/', clock_history, name='clock_history'),
    
    # Staff Booking & Availability API
    path('api/availability/update/', api_booking_views.update_availability, name='api_update_availability'),
    path('api/availability/<int:user_id>/<str:date>/', api_booking_views.get_user_availability, name='api_get_user_availability'),
    path('api/team-availability/<str:date>/', api_booking_views.get_team_availability, name='api_get_team_availability'),
    path('api/availability/<int:availability_id>/delete/', api_booking_views.delete_availability, name='api_delete_availability'),
    path('api/leave-request/', api_booking_views.request_leave, name='api_request_leave'),
    path('api/month-events/<int:year>/<int:month>/', api_booking_views.get_month_events, name='api_get_month_events'),
    
    # Staff Messaging API
    path('api/messages/inbox/', api_booking_views.get_staff_inbox, name='api_staff_inbox'),
    path('api/messages/send/', api_booking_views.send_staff_message, name='api_send_staff_message'),
    path('api/messages/thread/<int:recipient_id>/', api_booking_views.get_message_thread, name='api_message_thread'),
    path('api/messages/recipients/', api_booking_views.get_recipients_list, name='api_recipients_list'),
    path('api/messages/unread-count/', api_booking_views.get_unread_message_count, name='api_unread_count'),
    path('api/messages/attachment/<int:message_id>/download/', api_booking_views.download_message_attachment, name='api_download_attachment'),

]
