package ro.unihack.smartwaste.api

import ro.unihack.smartwaste.model.*
import retrofit2.http.*

interface SmartWasteApi {
    @PUT("api/v1/companies/{id}/hq") suspend fun hq(@Path("id") id: Int, @Body request: HQInput): User
    @PATCH("api/v1/bins/{id}/damage") suspend fun damage(@Path("id") id: String, @Body request: DamageInput): Map<String, Any>
    @POST("api/v1/company/route") suspend fun route(): CollectionRoute
    @POST("api/v1/company/route/optimize") suspend fun optimize(@Body input: RouteInput): CollectionRoute
    @GET("api/v1/company/routes") suspend fun routes(): List<CollectionRoute>
    @POST("api/v1/company/routes/{id}/start") suspend fun startRoute(@Path("id") id: String): Map<String, String>
    @POST("api/v1/company/routes/{id}/complete") suspend fun finishRoute(@Path("id") id: String, @Body input: FinishInput): Map<String, String>
    @GET("api/v1/company/statistics") suspend fun statistics(): CompanyStats
    @GET("api/v1/incidents/{id}/blockchain") suspend fun blockchain(@Path("id") id: Int): IncidentProof
    @POST("api/v1/incidents/{id}/blockchain/retry") suspend fun retryProof(@Path("id") id: Int): IncidentProof
    @POST("api/v1/incidents/{id}/proof") suspend fun proof(@Path("id") id: Int): IncidentProof
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
