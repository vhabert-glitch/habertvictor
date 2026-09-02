from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('responses/', views.responses_list, name='responses'),
    path('reports/', views.reports_list, name='reports'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
    path('nexus/', views.nexus_dashboard, name='nexus'),
    path('api/nexus/', views.nexus_api, name='nexus_api'),
    path('api/nexus/opportunities/', views.nexus_opportunities, name='nexus_opportunities'),
    path('api/nexus/refresh/', views.nexus_refresh, name='nexus_refresh'),
]
