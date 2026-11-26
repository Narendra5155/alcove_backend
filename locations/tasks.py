from celery import shared_task

from . import services


@shared_task
def purge_stale_positions():
    return services.purge_stale()
