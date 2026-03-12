from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('survey/', include('apps.survey.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('extractor/', include('apps.extractor.urls')),
]
