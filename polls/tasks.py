import functools
import json
import random

import requests
from celery import shared_task, Task
from celery.signals import task_postrun
from celery.utils.log import get_task_logger

from django.db import transaction
from django.contrib.auth.models import User
from polls.consumers import notify_channel_layer
from polls.base_task import custom_celery_task

logger = get_task_logger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, KeyError)
    retry_kwargs = {'max_retries': 5}
    retry_backoff = True

@shared_task()
def sample_task(email):
    from polls.views import api_call
    api_call(email)

@custom_celery_task(bind=True, retry_backoff=5, max_retries=5)
def task_process_notification(self):
    if not random.choice([0,1]):
        raise Exception()
    requests.post('https://httpbin.org/delay/5')

@task_postrun.connect
def task_postrun_handler(task_id, **kwargs):
    """
    When Celery task finish, send notification to Djanfo channel layer,
    so Django channel would receive the event and then send it to web client
    """
    notify_channel_layer(task_id)

@shared_task(name='task_clear_session')
def task_clear_session():
    from django.core.management import call_command
    call_command('clearsessions')

@shared_task(name='default:dynamic_example_one')
def dynamic_example_one():
    logger.info('Example One')

@shared_task(name='low_priority:dynamic_example_two')
def dynamic_example_two():
    logger.info('Example Two')

@shared_task(name='high_priority:dynamic_example_three')
def dynamic_example_three():
    logger.info('Example Three')

@shared_task()
def task_send_welcome_email(user_pk):
    user = User.objects.get(pk=user_pk)
    logger.info(f"Send email to {user.email} {user.pk}")


class custom_celery_task:
    """
    This is a decorator we can use to add custom logic to our Celery task
    such as retry or database transaction
    """
    def __init__(self, *args, **kwargs):
        self.task_args = args
        self.task_kwargs = kwargs

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper_func(*args, **kwargs):
            try:
                with transaction.atomic():
                    return func(*args, **kwargs)
            except Exception as e:
                # task_func.request.retries
                raise task_func.retry(exc=e, countdown=5)
        task_func = shared_task(*self.task_args, **self.task_kwargs)(wrapper_func)
        return task_func

@custom_celery_task(max_retries=5)
def task_transaction_test():
    pass

@shared_task()
def task_test_logger():
    logger.info('test')

@shared_task(bind=True)
def task_add_subscribe(self, user_pk):
    try:
        user = User.objects.get(pk=user_pk)
        requests.post(
            'https://httpbin.org/delay/5',
            data={'email': user.email},
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@custom_celery_task(max_retries=3)
def task_transaction_test():
    from .views import random_username
    username = random_username()
    user = User.objects.create_user(username, 'lennon@thebeatles', 'johnpassword')
    user.save()
    logger.info(f'send mail to {user.pk}')
    # this cause db rollback because of transaction.atomic
    raise Exception('test')