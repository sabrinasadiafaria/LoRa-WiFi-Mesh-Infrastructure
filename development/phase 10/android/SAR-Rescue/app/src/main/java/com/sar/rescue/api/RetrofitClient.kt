package com.sar.rescue.api

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private var baseUrl = "http://10.42.0.1:8080"
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    var api: SarApi = createApi()

    fun updateBaseUrl(ip: String) {
        baseUrl = "http://$ip:8080"
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
