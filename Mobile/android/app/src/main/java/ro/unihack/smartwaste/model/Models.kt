package ro.unihack.smartwaste.model

data class User(val id: Int, val username: String, val role: String, val display_name: String, val active: Boolean, val demo: Boolean = false)
data class Bin(val bin_id: String, val name: String, val latitude: Double?, val longitude: Double?,
    val company_id: Int?, val fill_level: Int?, val recorded_at: String?, val battery: Int? = null, val demo: Boolean = false)
data class Incident(val id: Int, val bin_id: String, val user_id: Int, val category: String, val comment: String,
    val status: String, val created_at: String, val updated_at: String)
data class LoginRequest(val username: String, val password: String)
data class LoginResponse(val access_token: String, val expires_at: String, val user: User)
data class UserCreate(val username: String, val password: String, val display_name: String, val role: String)
data class UserEdit(val display_name: String, val active: Boolean, val password: String? = null)
data class PasswordChange(val current_password: String, val new_password: String)
data class BinInput(val bin_id: String, val name: String, val latitude: Double?, val longitude: Double?, val company_id: Int?)
data class Assignments(val bin_ids: List<String>)
data class IncidentInput(val bin_id: String, val category: String, val comment: String)
data class StatusInput(val status: String)

enum class FillState { UNKNOWN, NORMAL, WARNING, FULL }
fun fillState(level: Int?): FillState = when {
    level == null -> FillState.UNKNOWN
    level >= 80 -> FillState.FULL
    level >= 60 -> FillState.WARNING
    else -> FillState.NORMAL
}
