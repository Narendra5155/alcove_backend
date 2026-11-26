from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    verb = models.CharField(max_length=40)
    title = models.CharField(max_length=140)
    body = models.CharField(max_length=500, blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def as_dict(self):
        return {
            "id": self.id,
            "verb": self.verb,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }
