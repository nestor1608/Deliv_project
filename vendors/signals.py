# vendors/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from .models import VendorRating, Vendor

@receiver(post_save, sender=VendorRating)
def update_vendor_rating(sender, instance, created, **kwargs):
    """Actualizar rating promedio del comercio"""
    if created:
        vendor = instance.vendor
        ratings = VendorRating.objects.filter(vendor=vendor)
        avg_rating = ratings.aggregate(avg=models.Avg('rating'))['avg']
        vendor.rating = round(avg_rating, 2) if avg_rating else 0
        vendor.save()