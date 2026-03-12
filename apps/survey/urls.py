from django.urls import path
from . import views

app_name = 'survey'

urlpatterns = [
    path('', views.survey_start, name='start'),
    path('new/', views.survey_create, name='create'),
    path('<uuid:token>/step/<int:step>/', views.survey_step, name='step'),
    path('<uuid:token>/confirmation/', views.survey_confirmation, name='confirmation'),
    path('export/csv/', views.export_csv, name='export_csv'),
]
