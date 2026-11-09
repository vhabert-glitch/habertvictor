"""
Script de déploiement automatique sur PythonAnywhere.
Usage: python pythonanywhere_deploy.py <username> <api_token>

1. Crée un compte gratuit sur pythonanywhere.com
2. Va dans Account → API Token → Create
3. Lance ce script avec ton username et token
"""
import sys
import os
import requests
import zipfile
import io

if len(sys.argv) < 3:
    print("Usage: python pythonanywhere_deploy.py <username> <api_token>")
    print("\n1. Crée un compte sur https://www.pythonanywhere.com")
    print("2. Va dans Account → API Token")
    print("3. Lance: python pythonanywhere_deploy.py ton_username ton_token")
    sys.exit(1)

USERNAME = sys.argv[1]
TOKEN = sys.argv[2]
API_BASE = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}"
HEADERS = {"Authorization": f"Token {TOKEN}"}
DOMAIN = f"{USERNAME}.pythonanywhere.com"
PROJECT_PATH = f"/home/{USERNAME}/ia-formation-radar"
VENV_PATH = f"/home/{USERNAME}/.virtualenvs/ia-radar"

def api(method, endpoint, **kwargs):
    url = f"{API_BASE}/{endpoint}"
    resp = getattr(requests, method)(url, headers=HEADERS, **kwargs)
    if resp.status_code >= 400:
        print(f"  ERREUR {resp.status_code}: {resp.text[:200]}")
    return resp

print("=== Déploiement sur PythonAnywhere ===\n")

# 1. Upload du projet via zip
print("[1/6] Upload du projet...")
project_dir = os.path.dirname(os.path.abspath(__file__))
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(project_dir):
        # Skip unnecessary dirs
        dirs[:] = [d for d in dirs if d not in (
            '.git', '__pycache__', 'staticfiles', 'venv', '.venv',
            'node_modules', 'db.sqlite3'
        )]
        for f in files:
            if f.endswith(('.pyc', '.sqlite3')):
                continue
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, project_dir)
            zf.write(filepath, f"ia-formation-radar/{arcname}")

zip_buffer.seek(0)
# Upload via files API
resp = api('post', f'files/path/home/{USERNAME}/ia-formation-radar.zip',
           files={'content': ('project.zip', zip_buffer, 'application/zip')})
print(f"  Upload: {'OK' if resp.status_code < 400 else 'ERREUR'}")

# 2. Unzip + setup via console
print("[2/6] Setup via console (virtualenv + dépendances)...")
setup_commands = f"""
cd /home/{USERNAME}
unzip -o ia-formation-radar.zip
cd ia-formation-radar
mkvirtualenv ia-radar --python=python3.10 || true
workon ia-radar
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@ia-radar.fr', 'admin123')" | python manage.py shell 2>/dev/null || true
python manage.py generate_test_data --count 5
"""

resp = api('post', 'consoles/', json={
    'executable': 'bash',
    'arguments': '',
    'working_directory': f'/home/{USERNAME}',
})
if resp.status_code < 400:
    console_id = resp.json()['id']
    api('post', f'consoles/{console_id}/send_input/',
        json={'input': setup_commands + '\nexit\n'})
    print(f"  Console #{console_id} lancée")

# 3. Configurer le web app
print(f"[3/6] Configuration du web app ({DOMAIN})...")
resp = api('post', 'webapps/', json={
    'domain_name': DOMAIN,
    'python_version': '3.10',
})
print(f"  Web app: {'OK' if resp.status_code < 400 else resp.text[:100]}")

# 4. Configurer WSGI
print("[4/6] Configuration WSGI...")
wsgi_content = f"""
import os
import sys

path = '{PROJECT_PATH}'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['ALLOWED_HOSTS'] = '{DOMAIN}'
os.environ['DEBUG'] = 'False'
os.environ['DJANGO_SECRET_KEY'] = 'production-change-this-to-random-string'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
"""
resp = api('put', f'webapps/{DOMAIN}/wsgi/',
           json={'content': wsgi_content})

# 5. Configurer static files et virtualenv
print("[5/6] Configuration static files + virtualenv...")
api('patch', f'webapps/{DOMAIN}/', json={
    'virtualenv_path': VENV_PATH,
    'source_directory': PROJECT_PATH,
})
api('post', f'webapps/{DOMAIN}/static_files/', json={
    'url': '/static/',
    'path': f'{PROJECT_PATH}/staticfiles',
})

# 6. Reload
print("[6/6] Reload de l'application...")
resp = api('post', f'webapps/{DOMAIN}/reload/')
print(f"  Reload: {'OK' if resp.status_code < 400 else 'ERREUR'}")

print(f"\n{'='*50}")
print(f"  DÉPLOYÉ : https://{DOMAIN}")
print(f"  Admin   : https://{DOMAIN}/admin/")
print(f"  Login   : admin / admin123")
print(f"{'='*50}")
