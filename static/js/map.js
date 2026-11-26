/* Leaflet helpers shared by search, property and booking pages. */
window.AlcoveMap = {
  create(el, { lat = 20.59, lng = 78.96, zoom = 5 } = {}) {
    const map = L.map(el, { zoomControl: true, scrollWheelZoom: true }).setView([lat, lng], zoom);
    const tiles = document.body.dataset.tiles || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    L.tileLayer(tiles, {
      maxZoom: 19,
      attribution: document.body.dataset.tilesAttribution || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    return map;
  },
  pricePin(label, active) {
    return L.divIcon({ className: "", html: `<div class="price-pin ${active ? "active" : ""}">${label}</div>`, iconSize: null });
  },
  meIcon() { return L.divIcon({ className: "", html: '<div class="me-dot"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }); },
  homeIcon() { return L.divIcon({ className: "", html: '<div class="home-pin"></div>', iconSize: [22, 22], iconAnchor: [11, 22] }); },
};

/** Watches browser geolocation and streams it over /ws/location/. */
function liveLocation({ onNearby, onError, radius = () => 10 } = {}) {
  let watchId = null;
  const ws = Alcove.socket("/ws/location/", {
    onMessage(m) {
      if (m.type === "nearby") onNearby && onNearby(m);
      if (m.type === "error") onError && onError(m.detail);
    },
  });
  return {
    start(onPosition) {
      if (!navigator.geolocation) { onError && onError("Your browser doesn't support location."); return; }
      watchId = navigator.geolocation.watchPosition(
        (p) => {
          const pos = { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy };
          onPosition && onPosition(pos);
          ws.send({ action: "position", ...pos, radius_km: radius() });
        },
        (err) => onError && onError(err.code === 1 ? "Location permission was denied. Allow it in your browser to see stays around you." : "We couldn't get your location."),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
      );
    },
    stop() { if (watchId != null) navigator.geolocation.clearWatch(watchId); watchId = null; },
    socket: ws,
  };
}
