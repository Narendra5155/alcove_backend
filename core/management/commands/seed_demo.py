"""Create demo users, properties, rooms, bookings, payments and reviews."""
import random
import urllib.request
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from bookings.models import Booking, Review
from locations.services import rebuild_property_index
from payments.models import Payment
from properties.models import Amenity, Property, PropertyImage, Room

User = get_user_model()
PASSWORD = "AlcoveDemo!2026"

AMENITIES = ["Wi-Fi", "Air conditioning", "Breakfast included", "Parking", "Swimming pool", "Power backup",
             "Hot water", "Room service", "Kitchen", "Workspace", "Pet friendly", "Airport pickup", "Geyser", "TV"]

PHOTOS = [
    "photo-1566073771259-6a8506099945", "photo-1582719478250-c89cae4dc85b", "photo-1551882547-ff40c63fe5fa",
    "photo-1571896349842-33c89424de2d", "photo-1590490360182-c33d57733427", "photo-1611892440504-42a792e24d32",
    "photo-1618773928121-c32242e63f39", "photo-1631049307264-da0ec9d70304", "photo-1564501049412-61c2a3083791",
    "photo-1520250497591-112f2f40a3f4", "photo-1542314831-068cd1dbfeeb", "photo-1584132967334-10e028bd69f7",
]

PROPERTIES = [
    # name, type, city, state, address, lat, lng
    ("Indiranagar Courtyard Rooms", "HOMESTAY", "Bengaluru", "Karnataka", "12th Main Rd, HAL 2nd Stage, Indiranagar", 12.9719, 77.6412),
    ("Koramangala Business Suites", "HOTEL", "Bengaluru", "Karnataka", "80 Feet Rd, 4th Block, Koramangala", 12.9352, 77.6245),
    ("Whitefield Garden Apartments", "APARTMENT", "Bengaluru", "Karnataka", "ITPL Main Rd, Whitefield", 12.9698, 77.7500),
    ("MG Road Transit Hostel", "HOSTEL", "Bengaluru", "Karnataka", "Brigade Rd, Shanthala Nagar", 12.9716, 77.6070),
    ("Anjuna Laterite Villa", "VILLA", "Goa", "Goa", "Flea Market Rd, Anjuna", 15.5736, 73.7407),
    ("Panjim Old Quarter Inn", "HOTEL", "Goa", "Goa", "Rua de Ourem, Fontainhas, Panaji", 15.4989, 73.8318),
    ("Palolem Palm Huts", "RESORT", "Goa", "Goa", "Palolem Beach Rd, Canacona", 15.0100, 74.0232),
    ("Hauz Khas Village Rooms", "HOMESTAY", "Delhi", "Delhi", "Hauz Khas Village, near Deer Park", 28.5535, 77.1940),
    ("Connaught Place Residency", "HOTEL", "Delhi", "Delhi", "N Block, Connaught Place", 28.6315, 77.2167),
    ("Bandra Sea-Link Studios", "APARTMENT", "Mumbai", "Maharashtra", "Carter Rd, Bandra West", 19.0650, 72.8227),
    ("Colaba Heritage Hotel", "HOTEL", "Mumbai", "Maharashtra", "Shahid Bhagat Singh Rd, Colaba", 18.9067, 72.8147),
    ("Pink City Haveli Stay", "HOMESTAY", "Jaipur", "Rajasthan", "Gangori Bazaar, Old City", 26.9239, 75.8267),
]

ROOM_TYPES = [
    ("Standard double", 1800, 2, 1, 6), ("Deluxe king", 2900, 2, 1, 4), ("Family suite", 4800, 4, 2, 2),
    ("Twin room", 2200, 2, 2, 3), ("Dorm bed", 650, 1, 1, 12), ("Entire villa", 14500, 8, 4, 1),
]

PALETTE = [(27, 42, 74), (242, 165, 26), (31, 122, 107), (200, 54, 78), (142, 155, 184)]

COMMENTS = ["Spotless rooms and a host who replied within minutes.", "Great location, easy to reach from the station.",
            "Quiet at night, strong Wi-Fi, would book again.", "Breakfast was excellent and check-in was quick.",
            "Exactly like the photos. The staff helped us with a late checkout.", "Good value for the area."]


def fetch_photo(pid):
    url = f"https://images.unsplash.com/{pid}?w=1400&q=70&auto=format&fit=crop"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return r.read()
    except Exception:  # noqa: BLE001 - offline: draw a placeholder
        return None


def placeholder(seed):
    rnd = random.Random(seed)
    bg, fg = rnd.sample(PALETTE, 2)
    img = Image.new("RGB", (1400, 1000), bg)
    d = ImageDraw.Draw(img)
    for i in range(6):
        x = rnd.randint(-200, 1200)
        d.rounded_rectangle([x, 300 + i * 40, x + 380, 1100], radius=190, fill=tuple(min(255, c + 25 * i) for c in fg))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Seed demo data (idempotent-ish: skips if demo owner exists unless --reset)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first")
        parser.add_argument("--no-photos", action="store_true", help="Use generated placeholder photos only")

    def handle(self, *args, **opts):
        if opts["reset"]:
            demo = User.objects.filter(email__endswith="@alcove.test")
            Payment.objects.filter(booking__renter__in=demo).delete()
            Booking.objects.filter(renter__in=demo).delete()
            Property.objects.filter(owner__in=demo).delete()
            demo.delete()
        if User.objects.filter(email="owner@alcove.test").exists():
            self.stdout.write("Demo data already present (use --reset to recreate).")
            return
        photos = {} if opts["no_photos"] else {pid: fetch_photo(pid) for pid in PHOTOS}
        with transaction.atomic():
            self._seed(photos)
        n = rebuild_property_index()
        self.stdout.write(self.style.SUCCESS(f"Seeded demo data; {n} properties in the GEO index."))
        self.stdout.write(f"  Host:      owner@alcove.test / {PASSWORD}")
        self.stdout.write(f"  Host 2:    host2@alcove.test / {PASSWORD}")
        self.stdout.write(f"  Traveller: renter@alcove.test / {PASSWORD}")
        self.stdout.write("  (Sign-in codes arrive in Mailpit: http://localhost:8025)")

    def _user(self, email, name, role, city):
        u = User.objects.create_user(email=email, password=PASSWORD, full_name=name, role=role, is_email_verified=True)
        u.profile.city = city
        u.profile.phone = "+91 98" + "".join(random.choices("0123456789", k=8))
        u.profile.save()
        return u

    def _seed(self, photos):
        random.seed(7)
        amenities = [Amenity.objects.get_or_create(name=a)[0] for a in AMENITIES]
        owner = self._user("owner@alcove.test", "Meera Iyer", "OWNER", "Bengaluru")
        owner.profile.business_name = "Iyer Hospitality"
        owner.profile.save()
        host2 = self._user("host2@alcove.test", "Rohan Desai", "OWNER", "Goa")
        renter = self._user("renter@alcove.test", "Arjun Mehta", "RENTER", "Pune")
        others = [self._user(f"guest{i}@alcove.test", n, "RENTER", c) for i, (n, c) in enumerate(
            [("Priya Sharma", "Delhi"), ("Kabir Khan", "Mumbai"), ("Ananya Rao", "Hyderabad"), ("Vikram Singh", "Jaipur")], 1)]

        props = []
        for i, (name, ptype, city, state, addr, lat, lng) in enumerate(PROPERTIES):
            p = Property.objects.create(
                owner=owner if i % 3 != 2 else host2, name=name, property_type=ptype, city=city, state=state, address=addr,
                pincode=str(random.randint(110001, 600099)), location=Point(lng, lat, srid=4326),
                description=f"{name} is a short walk from the best of {city}. Rooms are cleaned daily, beds are firm, "
                            f"and the front desk can arrange cabs and local tours.\n\nIdeal for couples, families and work trips.",
                house_rules="No smoking indoors.\nQuiet hours from 10 PM to 7 AM.\nValid government ID required at check-in.",
            )
            p.amenities.set(random.sample(amenities, 6))
            for j in range(3):
                pid = PHOTOS[(i * 3 + j) % len(PHOTOS)]
                data = photos.get(pid) or placeholder(i * 10 + j)
                img = PropertyImage(property=p, is_cover=j == 0, order=j)
                img.image.save("photo.jpg", ContentFile(data), save=True)
            types = [ROOM_TYPES[5]] if ptype == "VILLA" else [ROOM_TYPES[4], ROOM_TYPES[3]] if ptype == "HOSTEL" else random.sample(ROOM_TYPES[:4], 3)
            for rname, price, guests, beds, qty in types:
                Room.objects.create(property=p, name=rname, price_per_night=Decimal(price + random.randint(0, 6) * 100),
                                    max_guests=guests, beds=beds, quantity=qty)
            props.append(p)

        today = timezone.localdate()
        now = timezone.now()
        guests = [renter, *others]

        def book(p, who, start, nights, status, paid_days_ago=None):
            room = p.rooms.first()
            sub = room.price_per_night * nights
            tax = (sub * Booking.TAX_RATE).quantize(Decimal("0.01"))
            b = Booking.objects.create(renter=who, property=p, room=room, check_in=start, check_out=start + timedelta(days=nights),
                                       guests=min(2, room.max_guests), nightly_rate=room.price_per_night, subtotal=sub, taxes=tax,
                                       total=sub + tax, status=status)
            if status != Booking.Status.PENDING and paid_days_ago is not None:
                paid_at = now - timedelta(days=paid_days_ago)
                Payment.objects.create(booking=b, amount=b.total, status=Payment.Status.PAID if status != "CANCELLED" else Payment.Status.REFUNDED,
                                       provider_order_id=f"order_demo_{b.reference.lower()}", provider_payment_id=f"pay_demo_{b.reference.lower()}",
                                       is_demo=True, method="card", paid_at=paid_at, refunded_at=paid_at if status == "CANCELLED" else None)
                Booking.objects.filter(pk=b.pk).update(created_at=paid_at)
            return b

        owner_props = [p for p in props if p.owner == owner]
        # history over the past year
        for k in range(40):
            p = random.choice(owner_props)
            days_ago = random.randint(5, 360)
            b = book(p, random.choice(guests), today - timedelta(days=days_ago), random.randint(1, 4), Booking.Status.COMPLETED, days_ago + 3)
            if random.random() < 0.6:
                Review.objects.create(booking=b, property=p, renter=b.renter, rating=random.choice([4, 4, 5, 5, 5, 3]), comment=random.choice(COMMENTS))
        # current & upcoming
        arriving = book(owner_props[0], renter, today, 2, Booking.Status.CONFIRMED, 6)
        arriving.share_location = True  # lets the host's live arrival map be demoed today
        arriving.save(update_fields=["share_location"])
        book(owner_props[1], others[0], today - timedelta(days=1), 3, Booking.Status.CHECKED_IN, 9)
        book(owner_props[2], others[1], today + timedelta(days=3), 2, Booking.Status.CONFIRMED, 2)
        book(owner_props[3], others[2], today + timedelta(days=5), 4, Booking.Status.CONFIRMED, 1)
        book(owner_props[0], others[3], today + timedelta(days=10), 2, Booking.Status.CANCELLED, 4)
        b = book(owner_props[1], renter, today + timedelta(days=20), 3, Booking.Status.PENDING)
        b.expires_at = now + timedelta(minutes=15)
        b.save(update_fields=["expires_at"])
        for p in props:
            if p.owner == host2:
                book(p, random.choice(guests), today - timedelta(days=20), 2, Booking.Status.COMPLETED, 22)
