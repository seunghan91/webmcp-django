import django
from django.conf import settings


def pytest_configure():
    settings.configure(
        DEBUG=True,
        SECRET_KEY="webmcp-tests-only",
        DATABASES={},
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "webmcp_django",
        ],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
                "OPTIONS": {},
            }
        ],
        WEBMCP_ORIGIN_TRIAL_TOKEN="",
        USE_TZ=True,
    )
    django.setup()
