# Alcove

Alcove is a full-stack Django app for booking hotels, homestays and apartments across India. Travellers search stays around them on a live map, book a room, and pay through Razorpay. Hosts list properties, manage bookings and check-ins, and track earnings, and on arrival day they can watch an incoming guest approach on a map.

![Alcove home page with search and a map of stays across India](screenshots/home.png)

## Features

- **Email + password sign-in with an emailed one-time code** as the second factor. Sessions are JWTs kept in HttpOnly cookies.
- **Travellers and hosts** have their own dashboards and profile photos, and an account can switch between the two roles.
- **Search by place or by "near me"**, with dates, guests, price, property type and amenity filters. Results and price pins update as you move.
- **Room availability** is calculated per room type and night, and two people can never book the last unit at the same time.
- **Razorpay checkout** with a 15-minute room hold, server-side signature verification, a webhook backup, and refunds on cancellation.
- **Live location on arrival day.** If the guest opts in, the host sees their position and distance live, plus "on the way" and "arriving soon" alerts.
- **Real-time notifications**: a bell with an unread count and pop-up alerts for bookings, payments, check-ins and reviews.
- **Host dashboard** with monthly payouts, occupancy, a 12-month payout chart, a bookings table with check-in and check-out, a calendar, property and room management with photo uploads and a map pin, and an earnings ledger with CSV export.

## A walk through the app

**Find a stay.** Search a city or use your location. Prices are pinned on the map, and hovering a result highlights its pin.

![Search results beside a map with price pins](screenshots/search-map.png)

**Pick a room.** Each property shows a photo gallery, rooms with live availability for your dates, amenities, house rules, a map and reviews.

![Property page with arched photo gallery](screenshots/property-detail.png)

**Confirm and pay.** The room is held for 15 minutes while you pay. Taxes (12% GST) are shown before you pay.

![Checkout page with hold timer and price breakdown](screenshots/checkout.png)

**Pay with Razorpay.** Cards, UPI, netbanking and wallets all go through Razorpay's own checkout window.

| Razorpay checkout | Payment confirmed |
|---|---|
| ![Razorpay payment options](screenshots/razorpay-checkout.png) | ![Razorpay payment successful](screenshots/payment-success.png) |

**You're booked.** The host is notified instantly. On arrival day the guest can switch on location sharing so the host knows when they're close.

![Booking confirmation with live location sharing map and payment receipt](screenshots/booking-confirmed.png)

### For hosts

**Overview.** Hosts start on a summary of the month: payouts, occupancy, guests in house and bookings awaiting payment. Below it are a 12-month payout chart, upcoming arrivals and the latest bookings.

![Host dashboard with monthly KPIs, payout chart and latest bookings](screenshots/host-overview.png)

**Bookings.** Every booking across a host's properties is in one table. Filter by status (upcoming, in house, awaiting payment, completed, cancelled), search by guest or reference, and check guests in and out from the table.

![Host bookings table with status tabs](screenshots/host-bookings.png)

**Calendar.** See who is staying on each night, filtered by property, with the month's occupancy.

![Monthly booking calendar](screenshots/host-calendar.png)

**Properties.** Add and edit listings: details, a map pin, amenities, photos, and room types with prices and unit counts. A listing can be hidden from search without deleting it.

![Host property list](screenshots/host-properties.png)

**Earnings.** Each payout is shown after Alcove's 10% fee, and refunded bookings are marked. The ledger can be downloaded as a CSV.

![Earnings ledger with payouts, fees and refunds](screenshots/host-earnings.png)

## Tech stack

| Area | Technology |
|---|---|
| Web | Django 5.1 templates, Alpine.js 3, Tailwind CSS (standalone CLI, no Node), Leaflet |
| API | Django REST Framework, SimpleJWT with HttpOnly cookies, CSRF enforced |
| Realtime | Django Channels 4 on Redis: `/ws/notifications/` and `/ws/location/` |
| Maps and location | PostGIS + GeoDjango for radius search and distances; Redis GEO for live positions and fast nearby lookups |
| Background jobs | Celery + beat: emails, expiring unpaid holds, check-in reminders, clearing stale positions |
| Payments | Razorpay (test mode) |
| Email | Brevo SMTP, or Mailpit for local development |

## Getting started

You need Docker. To run Django directly on macOS you also need Python 3.11 and Homebrew.

```bash
cp .env.example .env     # then set SECRET_KEY, and optionally the Brevo and Razorpay keys
```

### Option A: everything in Docker

```bash
make up      # PostGIS, Redis, Mailpit, Django (Daphne), Celery worker and beat, Tailwind watcher
make seed    # demo hosts, travellers, 12 properties, bookings, payments and reviews
```

### Option B: Django on your machine, services in Docker

```bash
brew install gdal                         # GeoDjango needs GDAL and GEOS
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
make services                             # PostGIS on :5433, Redis on :6380, Mailpit on :8025
make local-migrate && make local-seed
```

Add these to `.env` so Django finds the Docker services:

```
DATABASE_URL=postgis://alcove:alcove@localhost:5433/alcove
REDIS_URL=redis://localhost:6380
```

Then run each of these in its own terminal:

```bash
make local-run       # http://localhost:8000 (HTTP and WebSockets)
make local-worker    # sends sign-in emails; uses a thread pool because Celery's default pool breaks on macOS
make local-beat      # scheduled jobs
make local-css       # rebuilds Tailwind CSS on change
```

### Useful URLs

- App: http://localhost:8000
- Admin: http://localhost:8000/admin/ (create a login with `make superuser`)
- Mailpit inbox: http://localhost:8025

## Configuration

### Email

When `BREVO_SMTP_KEY` is empty, all email goes to Mailpit, so you can read sign-in codes at http://localhost:8025. To send real email through Brevo, set:

```
BREVO_SMTP_SERVER=smtp-relay.brevo.com
BREVO_MAIL_PORT=587
BREVO_LOGIN=<your Brevo SMTP login>
BREVO_SMTP_KEY=<your Brevo SMTP key>
DEFAULT_FROM_EMAIL=Alcove <you@your-verified-domain.com>
```

The sender in `DEFAULT_FROM_EMAIL` must be verified in Brevo. A sender on your own domain lands in inboxes far more reliably than a Gmail address.

### Payments (Razorpay)

1. In the Razorpay dashboard, switch to **Test Mode** and generate keys under **Account & Settings → API Keys**.
2. Add them to `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_...
   RAZORPAY_KEY_SECRET=...
   ```
3. Set **Payment Capture** to **Automatic** in the dashboard.
4. Restart Django, then pay with UPI ID `success@razorpay`, or `failure@razorpay` to try a failed payment.

If the keys are left empty, development builds show a simulated checkout instead, so you can test the booking flow offline.

**Webhook (optional).** Payments confirm in the browser, so the webhook is only a backup. To use it, expose the app publicly (for example with `cloudflared tunnel --url http://localhost:8000`) and add a webhook in Razorpay:
- URL: `https://<your-tunnel>/api/payments/webhook/`
- Events: `payment.captured` and `payment.failed`
- Secret: a random string you choose, also saved in `.env` as `RAZORPAY_WEBHOOK_SECRET`

### Maps

Map tiles come from OpenStreetMap by default. Its public servers are only for light use, so set `MAP_TILE_URL` (and `MAP_TILE_ATTRIBUTION`) to a tile provider before real traffic.

## Demo accounts

`make seed` creates these accounts. They all use the password `AlcoveDemo!2026`.

| Email | Role | What's in it |
|---|---|---|
| `owner@alcove.test` | Host | 8 properties, a year of bookings and payouts, a guest arriving today with location sharing on |
| `host2@alcove.test` | Host | 4 properties |
| `renter@alcove.test` | Traveller | Checking in today, an unpaid booking, past trips |
| `guest1@alcove.test` to `guest4@alcove.test` | Traveller | Past and upcoming stays |

Every sign-in sends a code by email. `alcove.test` is not a real domain, so use these accounts with Mailpit (leave `BREVO_SMTP_KEY` empty) and read the codes at http://localhost:8025.

## Project layout

| Path | What it holds |
|---|---|
| `alcove/` | Project package: settings (`base`, `dev`, `prod`, `test`), ASGI routing, Celery app |
| `accounts/` | User and profile models, sign-in codes (`otp.py`), cookie JWT auth for pages, the API and WebSockets, role switching |
| `properties/` | Properties, rooms, photos and amenities; geo search and availability (`services.py`); host property API |
| `bookings/` | Booking lifecycle with double-booking protection, reviews, hold expiry and reminders |
| `payments/` | Razorpay orders, verification, webhook and refunds |
| `locations/` | Redis GEO indexes and the live-location WebSocket consumer |
| `notifications/` | Notification model, `notify()` helper and WebSocket consumer |
| `dashboard/` | Host KPIs, payout chart, calendar, earnings and CSV export; traveller trips |
| `core/` | Home page, shared helpers and the `seed_demo` command |
| `templates/`, `static/` | Pages, Alpine.js components and Tailwind source |

## API overview

```
POST      /api/auth/{register,login,verify-otp,resend-otp,logout,password-reset,password-reset/confirm}/
GET|PATCH /api/profile/            POST|DELETE /api/profile/avatar/      POST /api/profile/role/
GET       /api/properties/search/?lat=&lng=&radius_km=&checkin=&checkout=&guests=&min_price=&max_price=&property_type=&amenities=
GET       /api/properties/<slug>/  GET /api/properties/<slug>/availability/?checkin=&checkout=
GET|POST  /api/owner/properties/   …/<id>/  …/<id>/images/  …/<id>/rooms/  …/<id>/rooms/<room_id>/
POST      /api/bookings/           GET /api/bookings/mine/   GET /api/bookings/quote/
POST      /api/bookings/<ref>/{cancel,share-location,review}/
POST      /api/owner/bookings/<ref>/{check-in,check-out,cancel}/
POST      /api/payments/{order,verify,failed,webhook}/
GET       /api/notifications/      POST /api/notifications/read/
WS        /ws/notifications/       WS /ws/location/
```

## Tests

```bash
make test         # inside Docker
make local-test   # on your machine (needs `make services` running)
```

The suite has 38 tests. They cover sign-in codes (attempt limits, single use, resend cooldown, password reset), cookie auth and token refresh, profile photos, geo search and availability, ownership checks, double-booking protection, hold expiry, the booking lifecycle, role switching, Razorpay signature and webhook verification, refunds, and both WebSocket consumers.

## Deploying

- Run with `DJANGO_SETTINGS_MODULE=alcove.settings.prod`. It turns on secure cookies, HSTS, the HTTPS redirect and hashed static files, and turns off the simulated checkout.
- Set `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, Brevo credentials, and live Razorpay keys with a webhook.
- Serve uploaded files (`media/`) from object storage or your web server. Django only serves them itself in development.
- Use a commercial map tile provider through `MAP_TILE_URL`.
