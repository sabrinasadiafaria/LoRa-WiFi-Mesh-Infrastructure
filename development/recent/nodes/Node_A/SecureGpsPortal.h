#pragma once

// Native ESP-IDF HTTPS server for Arduino-ESP32.
// No third-party ESP32_HTTPS_Server library is required.
// The HTTP captive portal remains on port 80; the GPS page is served on
// https://192.168.4.1/ so browser geolocation can be requested.

#include <Arduino.h>
#include <esp_https_server.h>
#include <esp_http_server.h>
#include <esp_err.h>

extern double phoneLat;
extern double phoneLon;
extern bool phoneValid;
extern uint32_t phoneTime;
extern float phoneAcc;
extern uint32_t phoneUpdates;
extern bool locValid(double lat, double lon);

static httpd_handle_t sarGpsHttpsServer = NULL;

static const char SAR_GPS_CERT[] PROGMEM = R"CERT(
-----BEGIN CERTIFICATE-----
MIIDYjCCAkqgAwIBAgIUOwQqUMB/ZboVwGobTc0H5UXZg98wDQYJKoZIhvcNAQEL
BQAwODEUMBIGA1UEAwwLMTkyLjE2OC40LjExEzARBgNVBAoMClNBUi1SRVNDVUUx
CzAJBgNVBAYTAkJEMB4XDTI2MDkyNTE1MzM0M1oXDTM2MDkyMjE1MzM0M1owODEU
MBIGA1UEAwwLMTkyLjE2OC40LjExEzARBgNVBAoMClNBUi1SRVNDVUUxCzAJBgNV
BAYTAkJEMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtpSMwaUI7abq
7nbKdigoNpklCeCKuU5hxtP5jLFK8w1VATVjgCviCPx4q36IIBxbcvgll8YwnEnT
XB2Qlw+YYABlMbV61INS1wY0zeoDIInwflMNt8zUe4PoRgvzKd5akKrFYbMT3s83
onkNZAd4jyQHcRQCerOPyUqOKjXvvaXPAzUnCQKT0yyPnu8kc+xgCSk74uFNh5si
bEQlP1hYc9K1nDvnyBrm2gpRXlHuccJITs72dzCUforQjK7YfISdMOceXdEr9Gyg
UBiMfpKgnEaUZM/3iq46ws+RpUsvUUQU+i4Zlki/xdJm7VPIrvYOcOyNjwAzLpzR
dbhjOCoo9QIDAQABo2QwYjAdBgNVHQ4EFgQUfOa2sNpsymqE4B+iFNJPQ/3iiwcw
HwYDVR0jBBgwFoAUfOa2sNpsymqE4B+iFNJPQ/3iiwcwDwYDVR0TAQH/BAUwAwEB
/zAPBgNVHREECDAGhwTAqAQBMA0GCSqGSIb3DQEBCwUAA4IBAQB/2rFu5h2C5eNu
vbWwy6mRvyzAVzpMpC6zCU/4c/PqTEe6Fi8QRpPrL0+qArSMYYtA4syYOpkOLxgx
xqXD7VFh82YWGT1J6pnk9DfIgmY+I5/yz0EF5bUOsKqzrmThP7FIswJecpyVnck/
EK+Ufs/k6fXReN8Jl3m/Q8eVT1bzFbhfJaCKkfGSabMc+jxauvLQG6t22nul1rQ8
0kizPTOnYZB8xFoLYY4cSYfWq09dP9nItUHv3uBnLlfwVIsgOIqoEzF6VMo/Ai2E
DJ18HdW64aJQIh6YeLXG7Hv7SHG8l59JxS6zHVQxWSyZKOMkW/KwCBcqssjaIcjQ
zPedgQ+3
-----END CERTIFICATE-----
)CERT";

static const char SAR_GPS_KEY[] PROGMEM = R"KEY(
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC2lIzBpQjtpuru
dsp2KCg2mSUJ4Iq5TmHG0/mMsUrzDVUBNWOAK+II/HirfoggHFty+CWXxjCcSdNc
HZCXD5hgAGUxtXrUg1LXBjTN6gMgifB+Uw23zNR7g+hGC/Mp3lqQqsVhsxPezzei
eQ1kB3iPJAdxFAJ6s4/JSo4qNe+9pc8DNScJApPTLI+e7yRz7GAJKTvi4U2HmyJs
RCU/WFhz0rWcO+fIGubaClFeUe5xwkhOzvZ3MJR+itCMrth8hJ0w5x5d0Sv0bKBQ
GIx+kqCcRpRkz/eKrjrCz5GlSy9RRBT6LhmWSL/F0mbtU8iu9g5w7I2PADMunNF1
uGM4Kij1AgMBAAECggEAChsb1WYYoergyxU5LKQZYbhFVBAhLZOYluRJxk9T6jMd
NuVpHgGPz9aFqVxmFXzsVOdGUWnPa/8sG0eppqre0MWE1GUKqPOh5LP7vUAML0Nj
U+Kt+jP0uOd6tlHYAkPD+IjzRu6eFXGbzzrrElPViPrCDLDCWF9TAJ3HU6/LltAc
PywvEoc+Ge0Od18AbFXNGavdHQrNG00ICTq4tWuHlYIJbDjb2gpGDB85AAa0mdG1
vuWatRfSEBtIuuJI1jxVJQOsKsOy+n2RgWu89tFJp34VdxbrB6iD5XBWg0QOTVrz
/quJsACNFbTmVXbKwa7ghg7Qxo1OseI4BXh79F/GMQKBgQDbSdiKgld4OKkkYqev
ZeD474AnLE0RSiWZRmR2HfTiJAnmcsdLM3DYw74JUFxZXh0F/X4P9eiQIBzyx+nm
hfBMAEkcUaPDyOxMei/9gPR7qvTedJfF9yOdjpbQtZOQ7lboMgxcVjZUdpJ8gsVF
Sba03xCOrNAmrc3eJ6UnhDWy/QKBgQDVJXulVSPP5zbJB+G0+CbBAsw0p1dtUNJH
ZEbLUF9naxZWZRqymzf4HH0/9NtAABxGMQo3FZYhGMkOjqzCOEUbxxb0pLFlDSbp
uzcK8k726PCJN//eZt2+e2CGP5mV44ak9QxvwmbRMocnwMBkYX9qKKXX5t/3q8Hv
w1SEggtbWQKBgE7UOgJ4nob6H1uUF2GHBxuVxQTP+RhZBjEWS/DmDezpNaHg6uGO
qWdS3lKsz7XUjixkFtgX9zUwRhfEY8HZris0AxQqCOvNo5xOZEgF/l0idIovcYvZ
rrTp2C9IxrZX52fq7eSXnUo5oakevVmOCR71/Ra86sqsug+9QrJ05XTlAoGAGc6b
BO6lEmQdVwPUSTQOhSoQjYOBa2PwweIbTDykAIKPxtAhBmUSxsC0TY0ZCsu4oKsJ
YJgFgGZe2ZtewXlMrMtTNTXHoMOR5ZTcWj/yXaTgksyr90KfMJQBoN+MegB9afWd
lt6D0mp6wM5uvPitE65uPhDfJz6tkZkl35FbTKkCgYEAscwmuYwg83D/nObdEGJQ
mYz9G24g5xG8a9SMcB67pbc7v4RJKneNdncOzX/zECC7IuCRjhb2uIpHH1oCQRpJ
3P2IQ4exvz4xEetq9tzC7oBnk0OrUw2WmbYtILMogPD4RH/c2FHFT9flwNI8P+OM
ucjMZIcl1Jfv5EvrKsAs34s=
-----END PRIVATE KEY-----
)KEY";

static const char SAR_GPS_HTML[] PROGMEM = R"HTML(
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAR Rescue - Phone GPS</title>
<style>
body{font-family:Arial,sans-serif;background:#10151b;color:#fff;margin:0;padding:22px;text-align:center}
.card{max-width:460px;margin:auto;background:#18212b;border-radius:18px;padding:24px;box-shadow:0 8px 30px #0006}
button{width:100%;padding:16px;border:0;border-radius:12px;background:#28a745;color:white;font-size:18px;font-weight:700;margin:12px 0}
button:disabled{opacity:.5}
#status{margin:18px 0;padding:14px;border-radius:10px;background:#0e151c}
.val{font-size:20px;margin:8px}.ok{color:#5ee887}.err{color:#ff7272}.warn{color:#ffd166}
small{color:#aeb8c2;line-height:1.5}
</style></head><body><div class="card">
<h2>📍 SAR Rescue</h2><p>Share your phone location with this rescue node.</p>
<button id="btn" onclick="getGPS()">GET MY PHONE GPS</button>
<div id="status">Waiting for location permission...</div>
<div id="coords"></div>
<small>Enable Android Location/GPS. When asked, choose <b>Allow</b> and <b>Precise location</b>.</small>
</div>
<script>
function msg(t,c){const e=document.getElementById('status');e.textContent=t;e.className=c||'';}
function getGPS(){
 if(!window.isSecureContext){msg('This page is not secure. Use the HTTPS address.','err');return;}
 if(!navigator.geolocation){msg('This browser does not provide geolocation.','err');return;}
 const b=document.getElementById('btn');b.disabled=true;msg('Requesting phone GPS permission...','warn');
 navigator.geolocation.getCurrentPosition(function(p){
   const c=p.coords,lat=c.latitude.toFixed(6),lon=c.longitude.toFixed(6),acc=Math.round(c.accuracy||0);
   document.getElementById('coords').innerHTML='<div class="val">Latitude: <b>'+lat+'</b></div><div class="val">Longitude: <b>'+lon+'</b></div><div class="val">Accuracy: <b>'+acc+' m</b></div>';
   msg('GPS acquired. Sending to rescue node...','warn');
   fetch('/api/loc?lat='+encodeURIComponent(lat)+'&lon='+encodeURIComponent(lon)+'&acc='+encodeURIComponent(acc),{cache:'no-store'})
   .then(r=>r.text().then(t=>({ok:r.ok,text:t})))
   .then(x=>{if(x.ok)msg('✓ Location received by rescue node.','ok');else msg('Node rejected location: '+x.text,'err');})
   .catch(e=>msg('Could not send location: '+e,'err'))
   .finally(()=>b.disabled=false);
 },function(e){
   let t='Location failed';
   if(e.code===1)t='Location permission denied. Allow location and try again.';
   else if(e.code===2)t='Phone could not determine a location. Move near a window/outdoors and try again.';
   else if(e.code===3)t='GPS timed out. Keep Location enabled and try again.';
   msg(t,'err');b.disabled=false;
 },{enableHighAccuracy:true,timeout:60000,maximumAge:0});
}
</script></body></html>
)HTML";

static esp_err_t sarGpsSend(httpd_req_t *req, const char *type, const char *body) {
  httpd_resp_set_type(req, type);
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_send(req, body, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t sarGpsRoot(httpd_req_t *req) {
  return sarGpsSend(req, "text/html; charset=utf-8", SAR_GPS_HTML);
}

static bool sarGpsQuery(httpd_req_t *req, const char *key, char *out, size_t outLen) {
  size_t len = httpd_req_get_url_query_len(req);
  if (len == 0 || len + 1 > 512) return false;
  char *buf = (char*)malloc(len + 1);
  if (!buf) return false;
  esp_err_t e = httpd_req_get_url_query_str(req, buf, len + 1);
  bool ok = (e == ESP_OK && httpd_query_key_value(buf, key, out, outLen) == ESP_OK);
  free(buf);
  return ok;
}

static esp_err_t sarGpsLocation(httpd_req_t *req) {
  char sLat[32] = {0}, sLon[32] = {0}, sAcc[24] = {0};
  if (!sarGpsQuery(req, "lat", sLat, sizeof(sLat)) || !sarGpsQuery(req, "lon", sLon, sizeof(sLon)))
    return sarGpsSend(req, "text/plain; charset=utf-8", "missing lat/lon");

  double lat = atof(sLat), lon = atof(sLon);
  if (!locValid(lat, lon)) {
    httpd_resp_set_status(req, "400 Bad Request");
    return sarGpsSend(req, "text/plain; charset=utf-8", "invalid coordinates");
  }

  float acc = 0.0f;
  if (sarGpsQuery(req, "acc", sAcc, sizeof(sAcc))) acc = atof(sAcc);

  phoneLat = lat;
  phoneLon = lon;
  phoneAcc = acc;
  phoneValid = true;
  phoneTime = millis();
  phoneUpdates++;

  Serial.printf("[secure-gps] phone position %.6f,%.6f (acc %.0fm)\n", lat, lon, (double)acc);
  return sarGpsSend(req, "text/plain; charset=utf-8", "Location received - thank you.");
}

static void sarGpsStartHttps() {
  if (sarGpsHttpsServer) return;

  httpd_ssl_config_t conf = HTTPD_SSL_CONFIG_DEFAULT();
  conf.servercert = (const uint8_t*)SAR_GPS_CERT;
  conf.servercert_len = sizeof(SAR_GPS_CERT) - 1;
  conf.prvtkey_pem = (const uint8_t*)SAR_GPS_KEY;
  conf.prvtkey_len = sizeof(SAR_GPS_KEY) - 1;
  conf.port_secure = 443;
  // TLS handshakes with a 2048-bit RSA key need more stack than the
  // normal HTTP server. Keep one client socket: the node only needs one phone.
  conf.httpd.max_open_sockets = 1;
  conf.httpd.max_uri_handlers = 4;
  conf.httpd.stack_size = 16384;
  conf.httpd.lru_purge_enable = true;
  conf.tls_handshake_timeout_ms = 30000;
  
  // FIX: Run HTTPS on Core 0 (PRO_CPU) at low priority so the TLS handshake
  // doesn't preempt the Arduino loop() on Core 1 and drop LoRa packets!
  conf.httpd.core_id = 0;
  conf.httpd.task_priority = 1;

  Serial.printf("[secure-gps] starting HTTPS, free heap=%lu\n", (unsigned long)ESP.getFreeHeap());
  esp_err_t rc = httpd_ssl_start(&sarGpsHttpsServer, &conf);
  if (rc != ESP_OK) {
    sarGpsHttpsServer = NULL;
    Serial.printf("[secure-gps] HTTPS start failed: %s (0x%x), free heap=%lu\n", esp_err_to_name(rc), (unsigned)rc, (unsigned long)ESP.getFreeHeap());
    return;
  }

  static httpd_uri_t rootUri = {
    .uri = "/", .method = HTTP_GET, .handler = sarGpsRoot, .user_ctx = NULL
  };
  static httpd_uri_t locUri = {
    .uri = "/api/loc", .method = HTTP_GET, .handler = sarGpsLocation, .user_ctx = NULL
  };
  httpd_register_uri_handler(sarGpsHttpsServer, &rootUri);
  httpd_register_uri_handler(sarGpsHttpsServer, &locUri);

  Serial.printf("[secure-gps] HTTPS GPS page ready: https://192.168.4.1/ (free heap=%lu)\n", (unsigned long)ESP.getFreeHeap());
}

static void sarGpsHttpsService() {
  // ESP-IDF HTTPS server runs its own task. Nothing is required here.
}
