from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    DebugPasswordResetView,
    login_view,
    logout_view,
    register_view,
    security_center,
    security_event_review,
    security_password_change,
)

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('security/', security_center, name='security_center'),
    path('security/event/<int:event_id>/', security_event_review, name='security_event_review'),
    path('security/change-password/', security_password_change, name='security_password_change'),
]


urlpatterns += [
    path('password-reset/',
         DebugPasswordResetView.as_view(),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html'),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
         name='password_reset_complete'),
]
