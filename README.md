# Alcove

A full-stack Django platform for booking hotels, homestays and apartments. Travellers find stays near them on a live map and pay online. Hosts manage properties, bookings, check-ins and earnings from a dashboard.

## Stack

| Concern | Tech |
|---|---|
| Web | Django 5.1, Django templates, Alpine.js 3, Tailwind CSS (standalone CLI), Leaflet |
| API | Django REST Framework + SimpleJWT (HttpOnly cookie auth, CSRF enforced) |
| Auth | Email + password → 6-digit email OTP (2FA) → JWT access/refresh cookies |
| Realtime | Django Channels 4 over Redis (`/ws/notifications/`, `/ws/location/`) |
| GIS | PostGIS + GeoDjango (search by radius/distance), Redis GEO (live positions, fast nearby) |
| Jobs | Celery + beat (OTP emails, hold expiry, check-in reminders, stale-position cleanup) |
| Payments | Razorpay (test mode) with signature verification + webhook; simulated checkout when keys are blank |
| Email (dev) | Mailpit |

## Run it

```bash
cp .env.example .env          # set SECRET_KEY; optionally add Razorpay test keys
make up                        # db, redis, mailpit, web (daphne), worker, beat, tailwind
make seed                      # demo users, 12 properties, bookings, payments, reviews
```

- App: http://localhost:8000 · Admin: http://localhost:8000/admin/ (`make superuser`)
- Mailpit (OTP emails): http://localhost:8025

Demo accounts (password `AlcoveDemo!2026`): `owner@alcove.test` (host), `host2@alcove.test` (host), `renter@alcove.test` (traveller). Every sign-in sends a code to Mailpit.

### Payments

Leave `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` blank to use the built-in simulated checkout (only allowed when `PAYMENTS_DEMO_FALLBACK` is on, which defaults to `DEBUG`). With `rzp_test_…` keys, the real Razorpay Checkout opens. Use card `4111 1111 1111 1111`, any future expiry and any CVV, or UPI `success@razorpay`. For the webhook, point Razorpay to `/api/payments/webhook/` and set `RAZORPAY_WEBHOOK_SECRET`.

## Apps

| App | Responsibility |
|---|---|
| `alcove/` | Project package: split settings (`base`/`dev`/`prod`/`test`), ASGI router, Celery |
| `accounts` | Email-based `User` (role `RENTER`/`OWNER`), `Profile` + avatar, OTP service (`otp.py`), JWT cookie auth (`authentication.py`, `middleware.py`, `ws_auth.py`) |
| `properties` | `Property` (PointField), `Room`, `PropertyImage`, `Amenity`; geo search & availability (`services.py`); owner CRUD API |
| `bookings` | `Booking` lifecycle with row-locking against double-booking, `Review`, expiry/reminder tasks |
| `payments` | `Payment`, Razorpay order/verify/webhook/refund (`services.py`) |
| `locations` | Redis GEO indexes, `LocationConsumer` (renter stream → nearby stays; owner watches an arriving guest) |
| `notifications` | `Notification` model, `notify()` helper (DB row + push after commit), `NotificationConsumer` |
| `dashboard` | Owner KPIs, revenue series, calendar, earnings ledger + CSV; renter trips |
| `core` | Home page, shared helpers (Redis client, image resizing, role decorators/permissions), `seed_demo` |

## How the main flows work

**Sign-in.** `POST /api/auth/login/` checks the password, stores an HMAC of a 6-digit code in Redis (5 min TTL, 5 attempts, 60 s resend cooldown) and emails it. It returns a `challenge_id`. `POST /api/auth/verify-otp/` consumes the challenge and sets `alcove_access` (15 min) and `alcove_refresh` (7 days, rotated and blacklisted on logout) as HttpOnly cookies. `JWTCookieMiddleware` authenticates page views and silently refreshes an expired access token. New accounts verify their email the same way.

**Live location.** The browser streams `watchPosition` over `/ws/location/`. The server records the renter in Redis (`GEOADD`, 60 s TTL) and replies with nearby stays from the Redis GEO property index. On arrival day, if the renter opted in for that booking, each position is fanned out to the `booking_<id>` group. The host's booking page shows a live marker, the distance, and "on the way" / "arriving soon" notifications.

**Booking → payment.** Creating a booking locks the room row, checks overlapping units, and holds it as `PENDING` for 15 minutes. Paying creates a Razorpay order; the server verifies the signature and confirms the booking, and both parties are notified in real time. Cancelling a paid booking triggers a refund.

## API (selected)

```
POST /api/auth/{register,login,verify-otp,resend-otp,logout,password-reset,password-reset/confirm}/
GET|PATCH /api/profile/            POST|DELETE /api/profile/avatar/
GET  /api/properties/search/?lat=&lng=&radius_km=&checkin=&checkout=&guests=&min_price=&max_price=&property_type=&amenities=
GET  /api/properties/<slug>/       GET /api/properties/<slug>/availability/?checkin=&checkout=
GET|POST /api/owner/properties/    …/<id>/  …/<id>/images/  …/<id>/rooms/  …/<id>/rooms/<room_id>/
POST /api/bookings/                GET /api/bookings/mine/   GET /api/bookings/quote/
POST /api/bookings/<ref>/{cancel,share-location,review}/
POST /api/owner/bookings/<ref>/{check-in,check-out,cancel}/
POST /api/payments/{order,verify,failed,webhook}/
GET  /api/notifications/           POST /api/notifications/read/
WS   /ws/notifications/            WS /ws/location/
```

## Tests

```bash
make test     # pytest inside the web container (needs db + redis running)
```

Covers the OTP flow (attempt limits, single use, cooldown, reset), cookie auth/refresh/logout, avatar validation, geo search and availability, ownership checks, booking overlap/expiry/lifecycle, Razorpay signature and webhook verification, refunds, and the WebSocket consumers.

## Production notes

- Use `DJANGO_SETTINGS_MODULE=alcove.settings.prod` (secure cookies, HSTS, SSL redirect, hashed static files), and set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and real SMTP settings.
- Serve `media/` from object storage or a web server; the dev URLconf only serves it when `DEBUG` is on.
- OpenStreetMap's public tile servers are for light use only; set `MAP_TILE_URL` to a tile provider for real traffic.
