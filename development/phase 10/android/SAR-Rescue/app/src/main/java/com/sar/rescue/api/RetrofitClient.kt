package com.sar.rescue.api

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // ESP32 node default AP IP on port 80 (standard HTTP).
    // When the phone joins a node's WiFi the gateway is 192.168.4.1.
    // When pointed at the Pi (10.42.x.x or LAN) we switch to port 8000.
    private var baseUrl = "http://192.168.4.1"
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    var api: SarApi = createApi()

    fun updateBaseUrl(ip: String) {
        baseUrl = when {
            ip.contains(":") -> "http://$ip"                // already has port
            ip.startsWith("10.42.") -> "http://$ip:8000"    // Pi hotspot
            ip.startsWith("192.168.1.") -> "http://$ip:8000" // Pi on LAN
            else -> "http://$ip"                            // node (port 80)
        }
        api = createApi()
    }

    private fun createApi(): SarApi {
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SarApi::class.java)
    }
}
