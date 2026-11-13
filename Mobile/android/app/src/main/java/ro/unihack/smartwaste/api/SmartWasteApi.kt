package ro.unihack.smartwaste.api

import ro.unihack.smartwaste.model.*
import retrofit2.http.*

interface SmartWasteApi {
    @POST("api/v1/auth/login") suspend fun login(@Body request: LoginRequest): LoginResponse
    @GET("api/v1/auth/me") suspend fun me(): User
    @POST("api/v1/auth/logout") suspend fun logout()
    @POST("api/v1/auth/password") suspend fun password(@Body request: PasswordChange)
    @GET("api/v1/bins") suspend fun bins(): List<Bin>
    @GET("api/v1/incidents") suspend fun incidents(): List<Incident>
    @POST("api/v1/incidents") suspend fun report(@Body request: IncidentInput): Incident
    @PATCH("api/v1/incidents/{id}") suspend fun status(@Path("id") id: Int, @Body request: StatusInput): Incident
    @POST("api/v1/bins/{id}/collections") suspend fun collect(@Path("id") id: String): Map<String, Any>
    @GET("api/v1/admin/users") suspend fun users(): List<User>
    @POST("api/v1/admin/users") suspend fun createUser(@Body request: UserCreate): User
    @PUT("api/v1/admin/users/{id}") suspend fun editUser(@Path("id") id: Int, @Body request: UserEdit): User
    @POST("api/v1/admin/bins") suspend fun createBin(@Body request: BinInput): Bin
    @PUT("api/v1/admin/bins/{id}") suspend fun editBin(@Path("id") id: String, @Body request: BinInput): Bin
    @GET("api/v1/admin/users/{id}/bins") suspend fun assignments(@Path("id") id: Int): List<String>
    @PUT("api/v1/admin/users/{id}/bins") suspend fun assign(@Path("id") id: Int, @Body request: Assignments): List<String>
}
