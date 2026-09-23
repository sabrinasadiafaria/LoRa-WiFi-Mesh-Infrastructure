package com.sar.rescue.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sar.rescue.api.RetrofitClient
import com.sar.rescue.api.StateResponse
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun DashboardScreen() {
    val coroutineScope = rememberCoroutineScope()
    var state by remember { mutableStateOf<StateResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    
    LaunchedEffect(Unit) {
        while (true) {
            try {
                state = RetrofitClient.api.getState()
                error = null
            } catch (e: Exception) {
                error = "Connection lost"
            }
            delay(3000)
        }
    }
    
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        if (error != null) {
            Text("Status: $error", color = MaterialTheme.colorScheme.error)
        } else {
            Text("Status: Connected to Mesh", color = MaterialTheme.colorScheme.primary)
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Button(onClick = {
            coroutineScope.launch {
                try { RetrofitClient.api.sendSos() } catch (e: Exception) {}
            }
        }, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
            Text("SEND SOS BROADCAST")
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        Text("Nodes Status", style = MaterialTheme.typography.titleLarge)
        
        state?.let { s ->
            LazyColumn {
                items(s.nodes) { node ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Node: ${node.id}")
                            Text("Online: ${node.online}")
                            Text("RSSI: ${node.rssi ?: "N/A"}")
                        }
                    }
                }
            }
        } ?: run {
            Text("Loading...")
        }
    }
}
