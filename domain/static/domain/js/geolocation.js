async function sendLocation() {
  // Helper: fallback payload if we don’t have consent or GPS
  const payload = {};

  // Ask for precise location first (5 s timeout)
  const getCoords = () =>
    new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null); // unsupported
      navigator.geolocation.getCurrentPosition(
        pos => resolve(pos.coords),
        _err => resolve(null),            // denied / unavailable
        { enableHighAccuracy: true, timeout: 5000 }
      );
    });

  const coords = await getCoords();
  if (coords) {
    payload.lat = coords.latitude;
    payload.lon = coords.longitude;
  }

  // Send to the API
  fetch("/api/location", {
    method: "POST",
    headers: { "Content-Type": "application/json",
               "X-CSRFToken": "{{ csrf_token }}" }, // if you use Django forms / cookies
    body: JSON.stringify(payload),
    credentials: "include" // keeps session cookies
  }).then(r => r.json())
    .then(console.log)      // { city: "...", method: "gps" | "ip", … }
    .catch(console.error);
}
document.addEventListener("DOMContentLoaded", sendLocation);