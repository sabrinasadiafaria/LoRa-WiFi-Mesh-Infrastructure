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
    var ipAddress by remember { mutableStateOf("10.42.0.1") }
    
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Settings", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = ipAddress,
            onValueChange = { 
                ipAddress = it 
                com.sar.rescue.api.RetrofitClient.updateBaseUrl(it)
            },
            label = { Text("Command Centre IP Address") },
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text("Default is 10.42.0.1 (Pi WiFi Access Point)", style = MaterialTheme.typography.bodySmall)
    }
}
