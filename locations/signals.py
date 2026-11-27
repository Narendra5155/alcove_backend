import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from properties.models import Property

from . import services

log = logging.getLogger(__name__)


@receiver(post_save, sender=Property)
def sync_index(sender, instance, **kwargs):
    try:
        services.index_property(instance)
    except Exception:  # index is rebuildable; never block a save
        log.exception("Failed to index property %s", instance.pk)


@receiver(post_delete, sender=Property)
def drop_index(sender, instance, **kwargs):
    try:
        services.unindex_property(instance.pk)
    except Exception:
        log.exception("Failed to unindex property %s", instance.pk)
