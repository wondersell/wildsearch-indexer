import environ
import os
from celery import Celery
from django.conf import settings

__all__ = [
    'celery',
]

env = environ.Env(DEBUG=(bool, False))  # set default values and casting
environ.Env.read_env()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

celery = Celery('app')

# почему-то подключение из настроек джанги не заработало, нужно будет разобраться
celery.conf.update(
    broker_url=env('REDIS_URL'),
    task_always_eager=env('CELERY_ALWAYS_EAGER', cast=bool, default=False),
    redis_max_connections=env('CELERY_REDIS_MAX_CONNECTIONS', default=None),
    broker_transport_options={'visibility_timeout': 3600 * 48},
    timezone=env('TIME_ZONE', cast=str, default='Europe/Moscow'),
)

celery.autodiscover_tasks(lambda: settings.INSTALLED_APPS)  # noqa E800
