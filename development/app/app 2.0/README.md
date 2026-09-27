# SAR GPS Provider - App 2.0

## Purpose of App 2.0
App 2.0 is designed to act as an upgraded GPS provider for the LoRa Wi-Fi Mesh Infrastructure, specifically leveraging Google's Android **Fused Location Provider** instead of standard GPS-only location acquisition. It ensures the fastest and most highly available location fixes by using GPS, Wi-Fi, Cellular, and sensor data.

## Difference from the Original App
The original app relied exclusively on the legacy `LocationManager` to get location coordinates. App 2.0 replaces this mechanism entirely with the modern `FusedLocationProviderClient`. 

Crucially, **App 2.0 does not reject location updates based on accuracy. The latest valid Fused Location reading is continuously sent to the SAR node together with its reported accuracy.** 

The existing communication logic with the SAR node (ESP32) remains completely unchanged. 

## Accuracy Handling
All locations, regardless of their accuracy (e.g., ±5m, ±30m, ±100m) are treated as valid data. The uncertainty is treated as metadata, passed directly to the ESP32 mesh, rather than acting as a hard filter. The app will never stop transmitting just because accuracy drops.

## Location Update Interval
Location updates are requested with high priority approximately **every 5 seconds**. The app continues pulling location fixes even if the connection to the SAR Node is temporarily lost.

## Permission Requirements
App 2.0 requires the following permissions:
- `ACCESS_FINE_LOCATION`: Required to obtain highly accurate GNSS fixes.
- `ACCESS_COARSE_LOCATION`: Required as a fallback and to assist the Fused Location Provider.
- `INTERNET` / `ACCESS_NETWORK_STATE` / `ACCESS_WIFI_STATE`: Required to transmit the data over HTTP via the local captive portal.

## SAR Node Communication
The app communicates with the existing ESP32 captive portal via HTTP GET requests to:
`http://192.168.4.1/api/loc`

The request includes `lat`, `lon`, `acc` (accuracy), and `ts` (timestamp). The node handles forwarding this data over LoRa to the Raspberry Pi.

## Build Instructions
1. Open **Android Studio**.
2. Select **Open** and choose the `development/app/app 2.0` directory.
3. Allow Gradle to sync. (The project forces Gradle 7.5 and AGP 7.4.2 to guarantee maximum compatibility).
4. Go to **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
5. The `app-debug.apk` will be generated in `app/build/outputs/apk/debug/`.

## Testing Instructions
1. Install the APK on an Android smartphone.
2. Ensure **Location/GPS is enabled** in Android's quick settings.
3. Open the app and grant the Location permissions.
4. Tap **START GPS SHARING**.
5. The UI will show the live dynamic coordinates and their accuracy (e.g., "Accuracy: ±12 m").
6. Connect your phone's Wi-Fi to the ESP32 Node (e.g., `SOS_Node_A`).
7. The status text will change from "Node disconnected" to "Connected to SAR Node" as data begins flowing into the mesh.
