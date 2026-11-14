package ro.unihack.smartwaste.api

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import ro.unihack.smartwaste.auth.TokenStore
import java.util.concurrent.TimeUnit

fun api(baseUrl: String, store: TokenStore): SmartWasteApi {
    val client = OkHttpClient.Builder()
        // Avoid stale idle sockets on Pi/hotspot links without retrying non-idempotent writes.
        .connectionPool(okhttp3.ConnectionPool(0, 1, TimeUnit.SECONDS))
        .connectTimeout(10, TimeUnit.SECONDS).readTimeout(90, TimeUnit.SECONDS)
        .callTimeout(100, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .followRedirects(false).followSslRedirects(false)
        .addInterceptor { chain ->
            val builder = chain.request().newBuilder()
            if (!chain.request().url.encodedPath.endsWith("/auth/login")) {
                store.token?.let { builder.header("Authorization", "Bearer $it") }
            }
            chain.proceed(builder.build())
        }.build()
    return Retrofit.Builder().baseUrl(baseUrl).client(client)
        .addConverterFactory(GsonConverterFactory.create()).build().create(SmartWasteApi::class.java)
}
