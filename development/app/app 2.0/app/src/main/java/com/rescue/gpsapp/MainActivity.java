package com.rescue.gpsapp;

import android.Manifest;
import android.content.pm.PackageManager;
import android.location.Location;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.Locale;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.widget.Toast;

public class MainActivity extends AppCompatActivity {
    private static final String TAG = "SAR_GPS_APP_V2";
    private static final int PERMISSION_REQUEST_LOCATION = 1001;
    private static final String NODE_URL = "http://192.168.4.1/api/loc";

    private TextView tvStatus;
    private TextView tvLocation;
    private TextView tvStats;
    private Button btnToggle;
    private Button btnSos, btnNeedHelp, btnInjured, btnFoundVictim, btnSafe;

    private FusedLocationProviderClient fusedLocationClient;
    private LocationCallback locationCallback;
    private boolean isSharing = false;
    private int packetCount = 0;
    private String lastTransmission = "--";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        tvStatus = findViewById(R.id.tvStatus);
        tvLocation = findViewById(R.id.tvLocation);
        tvStats = findViewById(R.id.tvStats);
        btnToggle = findViewById(R.id.btnToggle);

        btnSos = findViewById(R.id.btnSos);
        btnNeedHelp = findViewById(R.id.btnNeedHelp);
        btnInjured = findViewById(R.id.btnInjured);
        btnFoundVictim = findViewById(R.id.btnFoundVictim);
        btnSafe = findViewById(R.id.btnSafe);

        btnSos.setOnLongClickListener(v -> {
            sendMessageToNode("/api/sos", null);
            return true;
        });
        
        btnSos.setOnClickListener(v -> {
            Toast.makeText(this, "Hold to activate SOS", Toast.LENGTH_SHORT).show();
        });

        btnNeedHelp.setOnClickListener(v -> sendTextMsg("NEED HELP"));
        btnInjured.setOnClickListener(v -> sendTextMsg("INJURED"));
        btnFoundVictim.setOnClickListener(v -> sendTextMsg("FOUND VICTIM"));
        btnSafe.setOnClickListener(v -> sendTextMsg("SAFE"));

        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this);

        locationCallback = new LocationCallback() {
            @Override
            public void onLocationResult(@NonNull LocationResult locationResult) {
                if (locationResult == null) {
                    return;
                }
                for (Location location : locationResult.getLocations()) {
                    if (location != null) {
                        handleNewLocation(location);
                    }
                }
            }
        };

        btnToggle.setOnClickListener(v -> {
            if (isSharing) {
                stopLocationUpdates();
            } else {
                startLocationUpdates();
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
            tvStatus.setText("Waiting for location...");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_LOCATION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                tvStatus.setText("Waiting for location...");
            } else {
                tvStatus.setText("Location permission denied!");
                btnToggle.setEnabled(false);
            }
        }
    }

    private void startLocationUpdates() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            checkPermissions();
            return;
        }

        LocationRequest locationRequest = new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 5000)
                .setMinUpdateIntervalMillis(5000)
                .build();

        try {
            fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper());
            isSharing = true;
            btnToggle.setText("STOP GPS SHARING");
            btnToggle.setBackgroundColor(0xFFDC3545); // Red color
            tvStatus.setText("Waiting for location...");
        } catch (SecurityException e) {
            tvStatus.setText("Permission error!");
        }
    }

    private void stopLocationUpdates() {
        fusedLocationClient.removeLocationUpdates(locationCallback);
        isSharing = false;
        btnToggle.setText("START GPS SHARING");
        btnToggle.setBackgroundColor(0xFF28A745); // Green color
        tvStatus.setText("Stopped.");
    }

    private void handleNewLocation(Location location) {
        double lat = location.getLatitude();
        double lon = location.getLongitude();
        float acc = location.getAccuracy();

        // Update UI exactly as requested: "Accuracy: ±100 m"
        String locText = String.format(Locale.US, "Latitude: %.6f\nLongitude: %.6f\nAccuracy: ±%.0f m", lat, lon, acc);
        tvLocation.setText(locText);
        
        // Indicate sharing is active
        tvStatus.setText("● GPS sharing active\nSending to node...");

        sendLocationToNode(lat, lon, acc);
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
                final String resultText = (responseCode == 200) ? "● GPS sharing active\n● Connected to SAR Node" : "● GPS sharing active\n● Node disconnected (HTTP " + responseCode + ")";
                
                if (responseCode == 200) {
                    InputStream in = conn.getInputStream();
                    byte[] buffer = new byte[1024];
                    in.read(buffer);
                    in.close();

                    packetCount++;
                    java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("HH:mm:ss", Locale.US);
                    lastTransmission = sdf.format(new java.util.Date());
                }

                conn.disconnect();

                new Handler(Looper.getMainLooper()).post(() -> {
                    updateStats();
                    if (isSharing) {
                        tvStatus.setText(resultText);
                    }
                });
            } catch (Exception e) {
                Log.e(TAG, "Failed to send GPS", e);
                new Handler(Looper.getMainLooper()).post(() -> {
                    updateStats();
                    if (isSharing) {
                        tvStatus.setText("● GPS sharing active\n● Node disconnected");
                    }
                });
            }
        }).start();
    }

    private int getBatteryPercentage() {
        IntentFilter iFilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        Intent batteryStatus = registerReceiver(null, iFilter);
        if (batteryStatus != null) {
            int level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
            if (level != -1 && scale != -1) {
                return (int) ((level / (float) scale) * 100);
            }
        }
        return -1;
    }

    private void updateStats() {
        int bat = getBatteryPercentage();
        String batStr = (bat >= 0) ? bat + "%" : "--";
        if (tvStats != null) {
            tvStats.setText(String.format(Locale.US, "Packets: %d\nLast: %s\nBattery: %s", packetCount, lastTransmission, batStr));
        }
    }

    private void sendTextMsg(String text) {
        try {
            String query = "text=" + URLEncoder.encode(text, "UTF-8");
            sendMessageToNode("/api/msg", query);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void sendMessageToNode(String path, String query) {
        new Thread(() -> {
            try {
                String urlString = "http://192.168.4.1" + path + (query != null ? "?" + query : "");
                URL url = new URL(urlString);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);

                int responseCode = conn.getResponseCode();
                if (responseCode == 200) {
                    InputStream in = conn.getInputStream();
                    byte[] buffer = new byte[1024];
                    in.read(buffer);
                    in.close();
                }
                conn.disconnect();
                
                new Handler(Looper.getMainLooper()).post(() -> {
                    String msg = "SOS";
                    if (query != null) {
                        try {
                            msg = java.net.URLDecoder.decode(query.replace("text=",""), "UTF-8");
                        } catch (Exception ex) {
                            msg = "Message";
                        }
                    }
                    Toast.makeText(MainActivity.this, "Sent: " + msg, Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                new Handler(Looper.getMainLooper()).post(() -> {
                    Toast.makeText(MainActivity.this, "Failed to send to Node", Toast.LENGTH_SHORT).show();
                });
            }
        }).start();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (isSharing) {
            stopLocationUpdates();
        }
    }
}
