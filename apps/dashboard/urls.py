from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('responses/', views.responses_list, name='responses'),
    path('reports/', views.reports_list, name='reports'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
]
