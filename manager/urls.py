from django.urls import path
from . import views
from . import api_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('manager_dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager_book/', views.manager_book, name='manager_book'),
    path('app_kanban/', views.app_kanban, name='app_kanban'),
    path('manager_journal/', views.manager_journal, name='manager_journal'),
    path('manager_ganttchart/', views.manager_ganttchart, name='manager_ganttchart'),
    path('manager_elearning/', views.elearning_page, name='manager_elearning'),
    path('manager_templates/', views.templates_page, name='manager_templates'),
    path('manager_kanban/', views.manager_kanban, name='manager_kanban'),
    path('add-task/<int:project_id>/', views.add_task, name='manager_create_task'),
    path('add-task/<int:project_id>', views.add_task, name='add_task'),
    path('edit-task/<int:task_id>/', views.edit_task, name='edit_task'),
    path('update-task-status/<int:task_id>/', views.update_task_status, name='update_task_status'),
    path('delete-task/<int:task_id>/', views.manager_delete_task, name='manager_delete_task'),
    path('assign/', views.assign_projects_view, name='assign_projects'),
    path('create_project/', views.create_project, name='create_project'),
    path('assign/team/<int:project_id>/', views.assign_team_member, name='assign_team_member'),
    path('add_task/<int:project_id>/', views.add_task, name='add_task'),
    path('remove_assignment/<int:assignment_id>/', views.remove_assignment, name='remove_assignment'),
    path('elearning/add/', views.add_learning_resource, name='add_learning_resource'),
    path('templates/add/', views.add_template, name='add_template'),
    path('templates/<int:pk>/edit/', views.edit_template, name='edit_template'),
    path('templates/<int:pk>/delete/', views.delete_template, name='delete_template'),
    path('add-paper/', views.add_paper, name='add_paper'),
    path('upload-excel/', views.upload_excel_papers, name='upload_excel_papers'),
    path('edit/<int:paper_id>/', views.edit_paper, name='edit_paper'),
    path('delete/<int:paper_id>/', views.delete_paper, name='delete_paper'),
    path('edit-ajax/<int:paper_id>/', views.edit_paper_ajax, name='edit_paper_ajax'),
    path('paper/<int:paper_id>/form-html/', views.get_paper_form_html, name='get_paper_form_html'),
    path('paper/<int:paper_id>/data/', views.get_paper_data, name='get_paper_data'),
    path('add-book/', views.add_book, name='add_book'),
    path('edit-book/<int:book_id>/', views.edit_book, name='edit_book'),
    path('delete-book/<int:book_id>/', views.delete_book, name='delete_book'),
    path('delete-chapter/<int:chapter_id>/', views.delete_chapter, name='delete_chapter'),
    path('add-chapter/<int:book_id>/', views.add_chapter, name='add_chapter'),
    path('edit-chapter/<int:chapter_id>/', views.edit_chapter, name='edit_chapter'),
    path('get-chapters/<int:book_id>/', views.get_chapters, name='get_chapters'),
    path('gantt/data/all/', views.manager_gantt_all_data, name='manager_gantt_all_data'),
    path('paper/<int:paper_id>/comments/', views.get_paper_comments, name='get_paper_comments'),
    
    # API endpoints for contributor management
    path('api/paper/<int:paper_id>/assign-reviewer/', api_views.assign_reviewer, name='assign_reviewer'),
    path('api/paper/<int:paper_id>/remove-reviewer/', api_views.remove_reviewer, name='remove_reviewer'),
    path('api/paper/<int:paper_id>/add-coauthor/', api_views.add_coauthor, name='add_coauthor'),
    path('api/paper/<int:paper_id>/remove-coauthor/', api_views.remove_coauthor, name='remove_coauthor'),
    path('api/paper/<int:paper_id>/set-lead-author/', api_views.set_lead_author, name='set_lead_author'),
    path('api/conference/<int:conference_id>/assign-reviewer/', api_views.assign_conference_reviewer, name='assign_conference_reviewer'),
    path('api/conference/<int:conference_id>/remove-reviewer/', api_views.remove_conference_reviewer, name='remove_conference_reviewer'),
    path('api/paper/<int:paper_id>/contributors/', api_views.get_paper_contributors, name='get_paper_contributors'),
    path('api/available-users/', api_views.get_available_users, name='get_available_users'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)