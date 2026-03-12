from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('team/', views.team_view, name='team'),
    path('team/invite/', views.invite_member, name='invite'),
    path('team/remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('join/<uuid:token>/', views.accept_invitation, name='accept_invitation'),
]
