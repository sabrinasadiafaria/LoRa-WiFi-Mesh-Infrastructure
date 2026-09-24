package com.sar.rescue.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun MapScreen() {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Map View", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))
        Text("Note: Map rendering requires osmdroid configuration. As a simplified implementation, node coordinates can be viewed in the Dashboard.")
    }
}

@Composable
fun SettingsScreen() {
    // Default to the ESP32 node AP IP (192.168.4.1, port 80).
    // Users can switch to the Pi's IP (e.g. 10.42.0.1 for Pi hotspot,
    // or 192.168.1.x for LAN) and the port auto-adjusts to 8000.
    var ipAddress by remember { mutableStateOf("192.168.4.1") }
    var connectionInfo by remember { mutableStateOf("Node WiFi (port 80)") }
    
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Settings", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = ipAddress,
            onValueChange = { 
                ipAddress = it 
                com.sar.rescue.api.RetrofitClient.updateBaseUrl(it)
                connectionInfo = when {
                    it.startsWith("10.42.") -> "Pi hotspot (port 8000)"
                    it.startsWith("192.168.1.") -> "Pi on LAN (port 8000)"
                    it.startsWith("192.168.4.") -> "Node WiFi (port 80)"
                    it.contains(":") -> "Custom (port in URL)"
                    else -> "Node WiFi (port 80)"
                }
            },
            label = { Text("Server IP Address") },
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(connectionInfo, style = MaterialTheme.typography.bodySmall,
             color = MaterialTheme.colorScheme.primary)
        Spacer(modifier = Modifier.height(16.dp))
        
        Text("Quick Connect", style = MaterialTheme.typography.titleMedium)
        Spacer(modifier = Modifier.height(8.dp))
        
        OutlinedButton(
            onClick = {
                ipAddress = "192.168.4.1"
                com.sar.rescue.api.RetrofitClient.updateBaseUrl("192.168.4.1")
                connectionInfo = "Node WiFi (port 80)"
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Connect to Node (192.168.4.1)")
        }
        
        Spacer(modifier = Modifier.height(8.dp))
        
        OutlinedButton(
            onClick = {
                ipAddress = "10.42.0.1"
                com.sar.rescue.api.RetrofitClient.updateBaseUrl("10.42.0.1")
                connectionInfo = "Pi hotspot (port 8000)"
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Connect to Pi Hotspot (10.42.0.1)")
        }
    }
}
