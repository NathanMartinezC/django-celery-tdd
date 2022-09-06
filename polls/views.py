import json
import logging
import random
import time
from string import ascii_lowercase

import requests
from celery.result import AsyncResult
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from polls.forms import YourForm
from polls.tasks import sample_task, task_process_notification, task_send_welcome_email, task_add_subscribe

logger = logging.getLogger(__name__)


def api_call(email):
    if random.choice([0,1]):
        raise Exception('Random processing error')
    requests.post('https://httpbin.org/delay/5')


def subscribe(request):
    if request.method == 'POST':
        form = YourForm(request.POST)
        if form.is_valid():
            task = sample_task.delay(form.cleaned_data['email'])
            return JsonResponse({
                'task_id': task.task_id
            })
    form = YourForm()
    return render(request, 'form.html', {'form': form})


def task_status(request):
    task_id = request.GET.get('task_id')

    if task_id:
        task = AsyncResult(task_id)
        if task.state == 'FAILURE':
            error = str(task.result)
            response = {
                'state': task.state,
                'error': error
            }
        else:
            response = {
                'state': task.state
            }
        return JsonResponse(response)

@csrf_exempt
def webhook_test(request):
    if not random.choice([0,1]):
        raise Exception()
    requests.post("https://httpbin.org/delay/5")
    return HttpResponse('pong')

@csrf_exempt
def webhook_test2(request):
    """
    Use Celery worker to handle the notification
    """
    task = task_process_notification.delay()
    logger.info(task.id)
    return HttpResponse('pong')

def subscribe_ws(request):
    """
    Use Websocket to get notification of Celery task, instead of using ajax polling
    """
    if request.method == 'POST':
        form = YourForm(request.POST)
        if form.is_valid():
            task = sample_task.delay(form.cleaned_data['email'])
            # return the task id so the JS can poll the state
            return JsonResponse({
                'task_id': task.task_id
            })
    form = YourForm()
    return render(request, 'form_ws.html', {'form': form})

def random_username():
    username = ''.join([random.choice(ascii_lowercase) for i in range(5)])
    return username

@transaction.atomic
def transaction_celery(request):
    username = random_username()
    user = User.objects.create_user(username, 'lennon@beatles.com','johnpassword')
    logger.info(f"Create user: {user.pk}")
    # the task does not get called until after the transaction is commited
    transaction.on_commit(lambda: task_send_welcome_email.delay(user.pk))

    time.sleep(1)
    return HttpResponse('test')

@transaction.atomic
def user_subscribe(request):
    """
    This Django view saves user info to the database and sends task to Celery worker
    to subscribe the user to the database
    """
    if request.method == "POST":
        form = YourForm(request.POST)
        if form.is_valid():
            instance, flag = User.objects.get_or_create(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
            )
            transaction.on_commit(
                lambda: task_add_subscribe.delay(instance.pk)
            )
            return HttpResponseRedirect('')
    else:
        form = YourForm()
    
    return render(request, 'user_subscribe.html', {'form': form})