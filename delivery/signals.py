# delivery/signals.py
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DeliveryRating


@receiver(post_save, sender=DeliveryRating)
def update_delivery_rating(sender, instance, created, **kwargs):
    """Actualizar rating promedio del repartidor"""
    if created:
        delivery_person = instance.delivery_person
        ratings = DeliveryRating.objects.filter(delivery_person=delivery_person)
        avg_rating = ratings.aggregate(avg=models.Avg("rating"))["avg"]
        delivery_person.rating = round(avg_rating, 2) if avg_rating else 0
        delivery_person.save()
