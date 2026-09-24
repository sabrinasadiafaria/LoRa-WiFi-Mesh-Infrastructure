package com.sar.rescue.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sar.rescue.api.MessageState
import com.sar.rescue.api.RetrofitClient
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val LORA_MAX_TEXT = 100

@Composable
fun MessagesScreen() {
    var messageText by remember { mutableStateOf("") }
    var destination by remember { mutableStateOf("*") }
    var errorText by remember { mutableStateOf<String?>(null) }
    var successText by remember { mutableStateOf<String?>(null) }
    var messages by remember { mutableStateOf<List<MessageState>>(emptyList()) }
    var isSending by remember { mutableStateOf(false) }
    val coroutineScope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val charCount = messageText.length
    val chunkCount = if (charCount <= LORA_MAX_TEXT) 1
                     else (charCount + LORA_MAX_TEXT - 1) / LORA_MAX_TEXT

    // Poll for messages
    LaunchedEffect(Unit) {
        while (true) {
            try {
                val resp = RetrofitClient.api.getMessages()
                messages = resp.messages
                errorText = null
            } catch (e: Exception) {
                // Try from /api/state as fallback
                try {
                    val state = RetrofitClient.api.getState()
                    messages = state.messages
                    errorText = null
                } catch (e2: Exception) {
                    errorText = "Cannot connect to server"
                }
            }
            delay(4000)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Header
        Surface(tonalElevation = 2.dp) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Messages", style = MaterialTheme.typography.titleLarge)
                if (errorText != null) {
                    Text(errorText!!, color = MaterialTheme.colorScheme.error,
                         style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        // Message list
        LazyColumn(
            modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
            state = listState,
            reverseLayout = true,
            contentPadding = PaddingValues(vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            if (messages.isEmpty()) {
                item {
                    Text("No messages yet",
                         modifier = Modifier.fillMaxWidth().padding(32.dp),
                         textAlign = TextAlign.Center,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            items(messages) { msg ->
                val isOutgoing = msg.direction == "out"
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = if (isOutgoing) Arrangement.End else Arrangement.Start
                ) {
                    Column(
                        modifier = Modifier
                            .widthIn(max = 300.dp)
                            .clip(RoundedCornerShape(
                                topStart = 12.dp, topEnd = 12.dp,
                                bottomStart = if (isOutgoing) 12.dp else 4.dp,
                                bottomEnd = if (isOutgoing) 4.dp else 12.dp
                            ))
                            .background(
                                if (isOutgoing) MaterialTheme.colorScheme.primaryContainer
                                else MaterialTheme.colorScheme.surfaceVariant
                            )
                            .padding(10.dp)
                    ) {
                        Text(
                            "${msg.src} → ${msg.dest}",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (isOutgoing) MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
                                    else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                        )
                        Text(
                            msg.text,
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isOutgoing) MaterialTheme.colorScheme.onPrimaryContainer
                                    else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            formatTimestamp(msg.ts),
                            style = MaterialTheme.typography.labelSmall,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            color = if (isOutgoing) MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.5f)
                                    else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                        )
                    }
                }
            }
        }

        // Compose area
        Surface(tonalElevation = 3.dp) {
            Column(modifier = Modifier.padding(12.dp)) {
                // Success message
                if (successText != null) {
                    Text(successText!!, color = MaterialTheme.colorScheme.primary,
                         style = MaterialTheme.typography.bodySmall,
                         modifier = Modifier.padding(bottom = 4.dp))
                }

                // Destination + char counter row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = destination,
                        onValueChange = { destination = it },
                        label = { Text("To") },
                        modifier = Modifier.width(100.dp),
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.End) {
                        Text(
                            "$charCount chars",
                            style = MaterialTheme.typography.labelSmall,
                            fontFamily = FontFamily.Monospace,
                            color = when {
                                charCount > LORA_MAX_TEXT * 5 -> MaterialTheme.colorScheme.error
                                charCount > LORA_MAX_TEXT -> MaterialTheme.colorScheme.tertiary
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            }
                        )
                        if (chunkCount > 1) {
                            Text(
                                "→ $chunkCount LoRa packets",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.tertiary
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // Message input + send
                Row(verticalAlignment = Alignment.Bottom) {
                    OutlinedTextField(
                        value = messageText,
                        onValueChange = { messageText = it; successText = null },
                        label = { Text("Message") },
                        modifier = Modifier.weight(1f),
                        minLines = 1,
                        maxLines = 4
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            if (messageText.isNotBlank() && !isSending) {
                                isSending = true
                                coroutineScope.launch {
                                    try {
                                        val resp = RetrofitClient.api.sendMessage(
                                            com.sar.rescue.api.SendRequest(destination, messageText)
                                        )
                                        if (resp.ok) {
                                            val chunks = resp.chunks ?: 1
                                            successText = if (chunks > 1) "Sent ($chunks packets)" else "Sent"
                                            messageText = ""
                                            errorText = null
                                        }
                                    } catch (e: Exception) {
                                        errorText = "Send failed"
                                    }
                                    isSending = false
                                }
                            }
                        },
                        enabled = messageText.isNotBlank() && !isSending,
                        modifier = Modifier.height(56.dp)
                    ) {
                        Text(if (isSending) "..." else "Send")
                    }
                }

                // LoRa limit hint
                Text(
                    "LoRa limit: $LORA_MAX_TEXT chars/packet • Dest: A, B, C, R, or * (all)",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }
    }
}

private fun formatTimestamp(ts: Double): String {
    val date = java.util.Date((ts * 1000).toLong())
    val fmt = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
    return fmt.format(date)
}
