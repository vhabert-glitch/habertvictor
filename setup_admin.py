import os, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
django.setup()
from django.contrib.auth.models import User
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@ia-radar.fr", "admin123")
    print("Admin created")
else:
    print("Admin exists")
