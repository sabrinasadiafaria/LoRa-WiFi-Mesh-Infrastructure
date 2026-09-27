package com.rescue.gpsapp;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

public class MainActivity extends AppCompatActivity {
    private static final String TAG = "SAR_GPS_APP";
    private static final int PERMISSION_REQUEST_LOCATION = 1001;
    private static final String NODE_URL = "http://192.168.4.1/api/loc";

    private TextView tvStatus;
    private TextView tvLocation;
    private Button btnToggle;

    private LocationManager locationManager;
    private boolean isSending = false;

    private final LocationListener locationListener = new LocationListener() {
        @Override
        public void onLocationChanged(@NonNull Location location) {
            double lat = location.getLatitude();
            double lon = location.getLongitude();
            float acc = location.getAccuracy();

            String locText = String.format(Locale.US, "Lat: %.6f\nLon: %.6f\nAcc: %.1f m", lat, lon, acc);
            tvLocation.setText(locText);
            tvStatus.setText("Sending to node...");

            sendLocationToNode(lat, lon, acc);
        }

        @Override
        public void onProviderEnabled(@NonNull String provider) { }

        @Override
        public void onProviderDisabled(@NonNull String provider) {
            tvStatus.setText("GPS provider disabled!");
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        tvStatus = findViewById(R.id.tvStatus);
        tvLocation = findViewById(R.id.tvLocation);
        btnToggle = findViewById(R.id.btnToggle);

        locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);

        btnToggle.setOnClickListener(v -> {
            if (isSending) {
                stopSending();
            } else {
                startSending();
            }
        });

        checkPermissions();
    }

    private void checkPermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
            }, PERMISSION_REQUEST_LOCATION);
        } else {
            tvStatus.setText("Ready to start.");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_LOCATION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                tvStatus.setText("Ready to start.");
            } else {
                tvStatus.setText("Location permission denied!");
                btnToggle.setEnabled(false);
            }
        }
    }

    private void startSending() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            checkPermissions();
            return;
        }

        try {
            // Request updates every 5000ms (5 seconds)
            locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000, 0, locationListener);
            locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 5000, 0, locationListener);
            
            isSending = true;
            btnToggle.setText("Stop Sending GPS");
            btnToggle.setBackgroundColor(0xFFDC3545); // Red color
            tvStatus.setText("Waiting for location fix...");
        } catch (SecurityException e) {
            tvStatus.setText("Permission error!");
        }
    }

    private void stopSending() {
        if (locationManager != null) {
            locationManager.removeUpdates(locationListener);
        }
        isSending = false;
        btnToggle.setText("Start Sending GPS");
        btnToggle.setBackgroundColor(0xFF28A745); // Green color
        tvStatus.setText("Stopped.");
    }

    private void sendLocationToNode(double lat, double lon, float acc) {
        new Thread(() -> {
            try {
                long timestamp = System.currentTimeMillis();
                String urlString = String.format(Locale.US, "%s?lat=%.6f&lon=%.6f&acc=%.1f&ts=%d", NODE_URL, lat, lon, acc, timestamp);
                URL url = new URL(urlString);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);

                int responseCode = conn.getResponseCode();
                final String resultText = (responseCode == 200) ? "✓ Sent successfully" : "Error: HTTP " + responseCode;
                
                if (responseCode == 200) {
                    InputStream in = conn.getInputStream();
                    byte[] buffer = new byte[1024];
                    in.read(buffer);
                    in.close();
                }

                conn.disconnect();

                new Handler(Looper.getMainLooper()).post(() -> {
                    if (isSending) {
                        tvStatus.setText(resultText);
                    }
                });
            } catch (Exception e) {
                Log.e(TAG, "Failed to send GPS", e);
                new Handler(Looper.getMainLooper()).post(() -> {
                    if (isSending) {
                        tvStatus.setText("Failed to connect to Node WiFi");
                    }
                });
            }
        }).start();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopSending();
    }
}
