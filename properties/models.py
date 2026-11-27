from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import Avg, Min
from django.utils import timezone
from django.utils.text import slugify

from core.images import resize_image, validate_image


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)
    icon = models.CharField(
        max_length=40, blank=True, help_text="Icon key used by the frontend"
    )

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "amenities"

    def __str__(self):
        return self.name


class Property(models.Model):
    class Type(models.TextChoices):
        HOTEL = "HOTEL", "Hotel"
        APARTMENT = "APARTMENT", "Apartment"
        VILLA = "VILLA", "Villa"
        HOMESTAY = "HOMESTAY", "Homestay"
        RESORT = "RESORT", "Resort"
        HOSTEL = "HOSTEL", "Hostel"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties"
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    property_type = models.CharField(
        max_length=12, choices=Type.choices, default=Type.HOTEL
    )
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80, db_index=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    location = models.PointField(geography=True, srid=4326)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="properties")
    check_in_time = models.TimeField(default="12:00")
    check_out_time = models.TimeField(default="11:00")
    house_rules = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name_plural = "properties"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.name}-{self.city}")[:150] or "stay"
            slug, i = base, 2
            while Property.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def lat(self):
        return self.location.y if self.location else None

    @property
    def lng(self):
        return self.location.x if self.location else None

    @property
    def cover_url(self):
        imgs = list(self.images.all())
        cover = next((i for i in imgs if i.is_cover), imgs[0] if imgs else None)
        return cover.image.url if cover else ""

    @property
    def starting_price(self):
        if hasattr(self, "min_price"):
            return getattr(self, "min_price", 0)
        return (
            getattr(self, "rooms", None)
            .filter(is_active=True)
            .aggregate(m=Min("price_per_night"))["m"]
        )

    @property
    def rating(self):
        if hasattr(self, "avg_rating"):
            return self.avg_rating
        return self.reviews.aggregate(a=Avg("rating"))["a"]


def property_image_path(instance, filename):
    return f"properties/{instance.property_id}/{timezone.now():%Y%m%d%H%M%S%f}.jpg"


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=property_image_path)
    caption = models.CharField(max_length=120, blank=True)
    is_cover = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-is_cover", "order", "id")

    @classmethod
    def create_from_upload(cls, prop, uploaded, **kwargs):
        validate_image(uploaded)
        obj = cls(property=prop, **kwargs)
        obj.image.save("photo.jpg", resize_image(uploaded, (1600, 1200)), save=False)
        if not prop.images.exists():
            obj.is_cover = True
        obj.save()
        return obj


class Room(models.Model):
    """A room type within a property; `quantity` identical units are available."""

    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="rooms"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    max_guests = models.PositiveSmallIntegerField(default=2)
    beds = models.PositiveSmallIntegerField(default=1)
    quantity = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("price_per_night",)

    def __str__(self):
        return f"{self.property.name} · {self.name}"
