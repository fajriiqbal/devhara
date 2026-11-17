import os
import sys

BASE_DIR = "/home/mtssuna1/devhara/app"

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.chdir(BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mts_website.settings")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "dev-hara.mtssunankalijagatulung.sch.id")
os.environ.setdefault(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://dev-hara.mtssunankalijagatulung.sch.id,http://dev-hara.mtssunankalijagatulung.sch.id",
)

from mts_website.wsgi import application
