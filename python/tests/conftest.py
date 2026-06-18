import atexit
import os
import sys
import tempfile

os.environ.setdefault('FLASK_DEBUG', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.setdefault('DEVICE_API_KEY', 'test-device-key')
# Force local-dev auth bypass regardless of what's in .env (load_dotenv won't override these).
os.environ.setdefault('SUPABASE_URL', '')
os.environ.setdefault('SUPABASE_ANON_KEY', '')

_tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
os.environ.setdefault('DATABASE_URL', f'sqlite:///{_tmp_db.name}')
atexit.register(lambda: os.path.exists(_tmp_db.name) and os.unlink(_tmp_db.name))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    app_module.app.config['WTF_CSRF_ENABLED'] = False
    with app_module.app.app_context():
        app_module.db.create_all()
        with app_module.app.test_client() as test_client:
            yield test_client
        app_module.db.session.remove()
        app_module.db.drop_all()
