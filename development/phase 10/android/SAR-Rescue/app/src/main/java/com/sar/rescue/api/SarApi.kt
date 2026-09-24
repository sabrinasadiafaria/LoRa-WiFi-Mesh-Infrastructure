package com.sar.rescue.api

import retrofit2.http.*

data class StateResponse(
    val now: Double,
    val nodes: List<NodeState>,
    val positions: Map<String, PositionState>,
    val messages: List<MessageState>,
    val reports: List<ReportState>,
    val sos: List<SosState>
)

data class NodeState(val id: String, val last_seen: Double, val rssi: Int?, val online: Boolean)
data class PositionState(val lat: Double, val lon: Double, val ts: Double)
data class MessageState(val ts: Double, val src: String, val dest: String, val text: String, val direction: String)
data class ReportState(val ts: Double, val id: String, val code: String, val team: String?)
data class SosState(val ts: Double, val victim: String, val msg: String, val cleared: Boolean)

data class StatusResponse(val peers: List<PeerState>)
data class PeerState(val id: String, val up: Int?, val rssi: Int?)

data class MessagesResponse(val messages: List<MessageState>)
data class SendResponse(val ok: Boolean, val chunks: Int?)

interface SarApi {
    @GET("/api/state")
    suspend fun getState(): StateResponse
    
    @GET("/api/status")
    suspend fun getStatus(): StatusResponse

    @GET("/api/messages")
    suspend fun getMessages(): MessagesResponse

    @POST("/api/loc")
    suspend fun sendLoc(@Query("lat") lat: Double, @Query("lon") lon: Double, @Query("acc") acc: Int)
    
    @POST("/api/send")
    suspend fun sendMessage(@Body req: SendRequest): SendResponse
    
    @POST("/api/report")
    suspend fun sendReport(@Query("code") code: String)
    
    @POST("/api/sos")
    suspend fun sendSos()
}

data class SendRequest(val dest: String, val text: String)
