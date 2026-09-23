package com.sar.rescue.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sar.rescue.api.RetrofitClient
import kotlinx.coroutines.launch

@Composable
fun MessagesScreen() {
    var messageText by remember { mutableStateOf("") }
    var destination by remember { mutableStateOf("*") }
    val coroutineScope = rememberCoroutineScope()
    
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Send Message", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = destination,
            onValueChange = { destination = it },
            label = { Text("Destination (e.g. *, PI, A, B)") },
            modifier = Modifier.fillMaxWidth()
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        OutlinedTextField(
            value = messageText,
            onValueChange = { messageText = it },
            label = { Text("Message body") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Button(onClick = {
            coroutineScope.launch {
                try {
                    RetrofitClient.api.sendMessage(com.sar.rescue.api.SendRequest(destination, messageText))
                    messageText = ""
                } catch (e: Exception) {
                    // handle error
                }
            }
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Send")
        }
    }
}
