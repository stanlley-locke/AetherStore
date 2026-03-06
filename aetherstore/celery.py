"""
Celery config for aetherstore project.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')

app = Celery('aetherstore')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Also discover tasks from workers directory
app.autodiscover_tasks(['workers'])

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
