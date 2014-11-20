from .devstack import *
from datetime import timedelta

FEATURES['ENABLE_LEARNING_ANALYTICS'] = True    # Enable Learning Analytics App
FEATURES['ENABLE_SQL_TRACKING_LOGS'] = True    # Enable Tracking Logs
# Backwards compatibility with ENABLE_SQL_TRACKING_LOGS feature flag.
# In the future, adding the backend to TRACKING_BACKENDS should be enough.
if FEATURES.get('ENABLE_SQL_TRACKING_LOGS'):
    TRACKING_BACKENDS.update({
        'sql': {
            'ENGINE': 'track.backends.django.DjangoBackend'
        }
    })
    EVENT_TRACKING_BACKENDS.update({
        'sql': {
            'ENGINE': 'track.backends.django.DjangoBackend'
        }
    })


# Add learning analytics to installed apps
INSTALLED_APPS += ('learning_analytics',)

############## CELERY ################

CELERY_BROKER_VHOST = "edx_host"
CELERY_BROKER_HOSTNAME = "localhost"
CELERY_BROKER_TRANSPORT = "amqp"
CELERY_BROKER_PASSWORD = "edx"
CELERY_BROKER_USER = "edx"

BROKER_URL = "{0}://{1}:{2}@{3}/{4}".format(CELERY_BROKER_TRANSPORT,
                                            CELERY_BROKER_USER,
                                            CELERY_BROKER_PASSWORD,
                                            CELERY_BROKER_HOSTNAME,
                                            CELERY_BROKER_VHOST)

CELERYBEAT_SCHEDULE = {
    'add-every-30-seconds': {
        'task': 'learning_analytics.tasks.update_DB_analytics',
        'schedule': timedelta(seconds=150),
    },
}

CELERY_TIMEZONE = 'UTC'