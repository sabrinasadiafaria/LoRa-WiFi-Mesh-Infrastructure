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
import com.sar.rescue.api.StatusResponse
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun DashboardScreen() {
    var state by remember { mutableStateOf<StateResponse?>(null) }
    var status by remember { mutableStateOf<StatusResponse?>(null) }
    var isFallback by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var connectionTarget by remember { mutableStateOf("") }
    val coroutineScope = rememberCoroutineScope()
    
    LaunchedEffect(Unit) {
        while (true) {
            // Try Pi's /api/state first (full data)
            try {
                state = RetrofitClient.api.getState()
                status = null
                isFallback = false
                error = null
                connectionTarget = "Command Centre"
            } catch (e: Exception) {
                // Fall back to node's /api/status (limited data)
                try {
                    status = RetrofitClient.api.getStatus()
                    state = null
                    isFallback = true
                    error = null
                    connectionTarget = "Field Node"
                } catch (e2: Exception) {
                    error = "Cannot connect. Check:\n" +
                            "• WiFi connected to a node or Pi?\n" +
                            "• Go to Settings to set the right IP"
                }
            }
            delay(3000)
        }
    }
    
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        // Connection status card
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = when {
                    error != null -> MaterialTheme.colorScheme.errorContainer
                    isFallback -> MaterialTheme.colorScheme.tertiaryContainer
                    else -> MaterialTheme.colorScheme.primaryContainer
                }
            )
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    when {
                        error != null -> "⚠ Disconnected"
                        isFallback -> "📡 Connected to $connectionTarget"
                        else -> "✅ Connected to $connectionTarget"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    color = when {
                        error != null -> MaterialTheme.colorScheme.onErrorContainer
                        isFallback -> MaterialTheme.colorScheme.onTertiaryContainer
                        else -> MaterialTheme.colorScheme.onPrimaryContainer
                    }
                )
                if (error != null) {
                    Text(error!!, 
                         style = MaterialTheme.typography.bodySmall,
                         color = MaterialTheme.colorScheme.onErrorContainer)
                }
                if (isFallback) {
                    Text("Limited data — node can show peers only.\nConnect to Pi for full dashboard.",
                         style = MaterialTheme.typography.bodySmall,
                         color = MaterialTheme.colorScheme.onTertiaryContainer)
                }
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // SOS button
        Button(
            onClick = {
                coroutineScope.launch {
                    try { RetrofitClient.api.sendSos() } catch (e: Exception) {}
                }
            },
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
            modifier = Modifier.fillMaxWidth().height(56.dp)
        ) {
            Text("🆘 SEND SOS BROADCAST", style = MaterialTheme.typography.titleMedium)
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        Text("Nodes", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(8.dp))
        
        if (state != null) {
            if (state!!.nodes.isEmpty()) {
                Text("No nodes reporting yet",
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                LazyColumn {
                    items(state!!.nodes) { node ->
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Row(modifier = Modifier.padding(16.dp).fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween) {
                                Column {
                                    Text("Node ${node.id}", 
                                         style = MaterialTheme.typography.titleSmall)
                                    Text("RSSI: ${node.rssi ?: "N/A"}", 
                                         style = MaterialTheme.typography.bodySmall)
                                }
                                Surface(
                                    shape = MaterialTheme.shapes.small,
                                    color = if (node.online) MaterialTheme.colorScheme.primaryContainer
                                            else MaterialTheme.colorScheme.errorContainer,
                                    modifier = Modifier.padding(4.dp)
                                ) {
                                    Text(
                                        if (node.online) " ONLINE " else " LOST ",
                                        style = MaterialTheme.typography.labelSmall,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        } else if (status != null) {
            if (status!!.peers.isEmpty()) {
                Text("No peers in range",
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                LazyColumn {
                    items(status!!.peers) { peer ->
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Row(modifier = Modifier.padding(16.dp).fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween) {
                                Column {
                                    Text("Node ${peer.id}", 
                                         style = MaterialTheme.typography.titleSmall)
                                    Text("RSSI: ${peer.rssi ?: "N/A"}", 
                                         style = MaterialTheme.typography.bodySmall)
                                }
                                Surface(
                                    shape = MaterialTheme.shapes.small,
                                    color = if (peer.up == 1) MaterialTheme.colorScheme.primaryContainer
                                            else MaterialTheme.colorScheme.errorContainer,
                                    modifier = Modifier.padding(4.dp)
                                ) {
                                    Text(
                                        if (peer.up == 1) " ONLINE " else " LOST ",
                                        style = MaterialTheme.typography.labelSmall,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        } else if (error == null) {
            CircularProgressIndicator(modifier = Modifier.padding(16.dp))
        }
    }
}


