package ro.unihack.smartwaste.model

data class User(val id: Int, val username: String, val role: String, val display_name: String, val active: Boolean, val demo: Boolean = false, val hq_latitude: Double? = null, val hq_longitude: Double? = null)
data class Bin(val bin_id: String, val name: String, val latitude: Double?, val longitude: Double?,
    val company_id: Int?, val fill_level: Int?, val recorded_at: String?, val battery: Int? = null, val demo: Boolean = false,
    val fill_category: Int? = null)
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

enum class FillState { UNKNOWN, NORMAL, WARNING, FULL, DAMAGED }
fun fillState(level: Int?): FillState = when {
    level == null -> FillState.UNKNOWN
    level >= 80 -> FillState.FULL
    level >= 60 -> FillState.WARNING
    else -> FillState.NORMAL
}

fun binState(bin: Bin): FillState = when (bin.fill_category) {
    null -> fillState(bin.fill_level)
    1 -> FillState.NORMAL
    2 -> FillState.WARNING
    3 -> FillState.FULL
    4 -> FillState.DAMAGED
    else -> FillState.UNKNOWN
}

fun binLevelLabel(bin: Bin): String = when (bin.fill_category) {
    null -> bin.fill_level?.let { "$it%" } ?: "Fără date"
    1 -> "Gol"
    2 -> "Mediu"
    3 -> "Plin"
    4 -> "Deteriorat"
    else -> "Stare necunoscută"
}

data class HQInput(val latitude: Double?, val longitude: Double?)
data class DamageInput(val damaged: Boolean)
data class CollectionRoute(val hq_latitude: Double, val hq_longitude: Double,
    val stops: List<Bin>, val straight_line_meters: Long, val skipped_bin_ids: List<String>)
data class IncidentProof(val sha256: String?, val signature: String?, val network: String,
    val status: String, val explorer_url: String?)
