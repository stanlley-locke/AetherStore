"""
Messaging Signals
Handles post-save events on Message to trigger delivery tasks.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='messaging.Message')
def on_message_created(sender, instance, created, **kwargs):
    """After a message is saved, queue delivery indexing if it's new."""
    if created and instance.search_vector is None and instance.message_type == 'text':
        try:
            from workers.message_delivery import index_message_for_search
            index_message_for_search.apply_async(
                args=[str(instance.id), ''],
                countdown=2
            )
        except Exception:
            pass
