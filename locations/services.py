"""Live positions and a property GEO index, both in Redis."""

import json
import time
from typing import Any, cast

from django.db.models import Avg, Min, Q

from core.redis import get_redis

LIVE_RENTERS = "geo:live_renters"
PROPERTIES = "geo:properties"
POSITION_TTL = 60

_GeoHits = list[list[Any]]  # GEOSEARCH withdist=True -> [[member, distance], ...]


def _pos_key(user_id):
    return f"live:renter:{user_id}"


# ---------------------------------------------------------------- live renter positions


def update_position(user_id, lat: float, lng: float, accuracy=None):
    r = get_redis()
    pipe = r.pipeline()
    pipe.geoadd(LIVE_RENTERS, (lng, lat, str(user_id)))
    pipe.set(
        _pos_key(user_id),
        json.dumps({"lat": lat, "lng": lng, "accuracy": accuracy, "ts": time.time()}),
        ex=POSITION_TTL,
    )
    pipe.execute()


def get_position(user_id):
    raw = cast("str | None", get_redis().get(_pos_key(user_id)))
    return json.loads(raw) if raw else None


def clear_position(user_id):
    r = get_redis()
    r.zrem(LIVE_RENTERS, str(user_id))
    r.delete(_pos_key(user_id))


def purge_stale():
    r = get_redis()
    members = cast("list[str]", r.zrange(LIVE_RENTERS, 0, -1))
    stale = [m for m in members if not r.exists(_pos_key(m))]
    if stale:
        r.zrem(LIVE_RENTERS, *stale)
    return len(stale)


def live_renters_near(lat, lng, radius_km=5) -> _GeoHits:
    return cast(
        _GeoHits,
        get_redis().geosearch(
            LIVE_RENTERS,
            longitude=lng,
            latitude=lat,
            radius=radius_km,
            unit="km",
            withdist=True,
        ),
    )


# ---------------------------------------------------------------- property GEO index


def index_property(prop):
    r = get_redis()
    if prop.is_active and prop.location:
        r.geoadd(PROPERTIES, (prop.location.x, prop.location.y, str(prop.pk)))
    else:
        r.zrem(PROPERTIES, str(prop.pk))


def unindex_property(prop_id):
    get_redis().zrem(PROPERTIES, str(prop_id))


def rebuild_property_index():
    from properties.models import Property

    r = get_redis()
    r.delete(PROPERTIES)
    n = 0
    for p in Property.objects.filter(is_active=True).only("id", "location"):
        r.geoadd(PROPERTIES, (p.location.x, p.location.y, str(p.pk)))
        n += 1
    return n


def nearby_properties(lat, lng, radius_km: float = 10, limit=40):
    """Fast radius lookup via Redis GEOSEARCH, hydrated from Postgres."""
    from properties.models import Property

    hits = cast(
        _GeoHits,
        get_redis().geosearch(
            PROPERTIES,
            longitude=lng,
            latitude=lat,
            radius=radius_km,
            unit="km",
            withdist=True,
            sort="ASC",
            count=limit,
        ),
    )
    if not hits:
        return []
    dist = {int(pid): float(d) for pid, d in hits}
    props = (
        Property.objects.filter(pk__in=dist.keys(), is_active=True)
        .annotate(
            min_price=Min("rooms__price_per_night", filter=Q(rooms__is_active=True)),
            avg_rating=Avg("reviews__rating"),
        )
        .prefetch_related("images")
    )
    type_labels = dict(Property.Type.choices)
    out = [
        {
            "id": p.pk,
            "name": p.name,
            "city": p.city,
            "type_label": type_labels.get(p.property_type, p.property_type),
            "lat": p.lat,
            "lng": p.lng,
            "url": f"/stays/{p.slug}/",
            "cover_url": p.cover_url,
            # starting_price / rating read the min_price / avg_rating annotations above
            "starting_price": float(p.starting_price)
            if p.starting_price is not None
            else None,
            "rating": round(p.rating, 1) if p.rating else None,
            "distance_km": round(dist[p.pk], 2),
        }
        for p in props
    ]
    return sorted(out, key=lambda x: x["distance_km"])
