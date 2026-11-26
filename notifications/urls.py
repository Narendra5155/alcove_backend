from django.urls import path

from . import api, views

api_urlpatterns = [
    path("notifications/", api.NotificationListView.as_view()),
    path("notifications/read/", api.MarkReadView.as_view()),
]
urlpatterns = [path("notifications/", views.notifications_page, name="notifications")]
