from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("ping/", views.ping, name="ping"),
    path("health/", views.healthcheck, name="healthcheck"),
    path("api/messages/", views.messages_api, name="messages_api"),
]
