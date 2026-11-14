package ro.unihack.smartwaste.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.repository.WasteRepository
import com.google.gson.JsonParser
import java.io.IOException

data class AppState(val restoring: Boolean = true, val busy: Boolean = false, val user: User? = null,
    val bins: List<Bin> = emptyList(), val incidents: List<Incident> = emptyList(), val users: List<User> = emptyList(),
    val error: String? = null, val message: String? = null,
    val route: CollectionRoute? = null, val proofs: Map<Int, IncidentProof> = emptyMap())

class WasteViewModel(private val repository: WasteRepository) : ViewModel() {
    private val mutable = MutableStateFlow(AppState())
    val state = mutable.asStateFlow()
    private var job: Job? = null

    init {
        launch {
            if (repository.hasSession) {
                val user = repository.api.me()
                mutable.update { it.copy(user = user) }
                load()
            }
        }
    }

    private fun launch(block: suspend () -> Unit) {
        if (job?.isActive == true) return
        mutable.update { it.copy(busy = true, error = null, message = null) }
        job = viewModelScope.launch {
            try { block() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if (e is HttpException && e.code() == 401) {
                    repository.clearSession()
                    mutable.value = AppState(restoring = false, error = "Autentificare invalidă sau sesiune expirată.")
                } else mutable.update { it.copy(error = errorMessage(e)) }
            } finally { mutable.update { it.copy(busy = false, restoring = false) } }
        }
    }

    private suspend fun load() {
        if (mutable.value.user == null) return
        val user = repository.api.me()
        mutable.update { it.copy(user = user, route = null, proofs = emptyMap()) }
        // Server validates active status and assignments on every request.
        mutable.update { it.copy(bins = emptyList(), incidents = emptyList(), users = emptyList()) }
        if (user.role == "Admin") {
            val users = repository.api.users()
            mutable.update { it.copy(users = users) }
        }
        val incidents = repository.api.incidents()
        mutable.update { it.copy(incidents = incidents) }
        val bins = repository.api.bins()
        mutable.update { it.copy(bins = bins) }
    }

    fun login(username: String, password: String) = launch {
        val user = repository.login(username.trim(), password)
        mutable.update { it.copy(user = user) }
        load()
    }
    fun refresh() = launch {
        if (mutable.value.user == null && repository.hasSession) {
            val user = repository.api.me()
            mutable.update { it.copy(user = user) }
        }
        load()
    }
    fun logout() {
        job?.cancel()
        job = null
        launch {
            var serverRevoked = true
            try { repository.logout() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                serverRevoked = false
                if (ro.unihack.smartwaste.BuildConfig.DEBUG) android.util.Log.w("SmartWaste", "Session revocation failed", e)
            }
            mutable.value = AppState(restoring = false,
                message = if (serverRevoked) null else "Sesiunea locală a fost ștearsă. Revocarea pe server nu a fost confirmată; tokenul expiră automat.")
        }
    }
    private fun mutate(done: () -> Unit, block: suspend () -> Unit) = launch {
        block()
        done()
        mutable.update { it.copy(message = "Modificarea a fost salvată.") }
        load()
    }
    fun damage(bin: Bin) = mutate({}) { repository.api.damage(bin.bin_id, DamageInput(bin.fill_category != 4)) }
    fun hq(id: Int, input: HQInput, done: () -> Unit) = mutate(done) { repository.api.hq(id, input) }
    fun generateRoute() = launch {
        mutable.update { it.copy(route = null) }
        val route = repository.api.route()
        mutable.update { it.copy(route = route) }
    }
    fun proof(id: Int) = launch {
        val proof = repository.api.proof(id)
        mutable.update { it.copy(proofs = it.proofs + (id to proof)) }
    }
    fun report(input: IncidentInput, done: () -> Unit) = mutate(done) { repository.api.report(input) }
    fun status(id: Int, status: String) = mutate({}) { repository.api.status(id, StatusInput(status)) }
    fun collect(bin: Bin) = launch {
        repository.api.collect(bin.bin_id)
        mutable.update { it.copy(message = "Colectare confirmată. Nivelul se actualizează la următoarea măsurătoare.") }
        load()
    }
    fun createUser(input: UserCreate, done: () -> Unit) = mutate(done) { repository.api.createUser(input) }
    fun editUser(id: Int, input: UserEdit, done: () -> Unit) = mutate(done) { repository.api.editUser(id, input) }
    fun saveBin(input: BinInput, editing: Boolean, done: () -> Unit) = mutate(done) {
        if (editing) repository.api.editBin(input.bin_id, input) else repository.api.createBin(input)
    }
    fun assignments(id: Int, done: (List<String>) -> Unit) = launch { done(repository.api.assignments(id)) }
    fun assign(id: Int, bins: List<String>, done: () -> Unit) = mutate(done) { repository.api.assign(id, Assignments(bins)) }
    fun password(current: String, new: String, done: () -> Unit) = launch {
        repository.api.password(PasswordChange(current, new))
        repository.clearSession()
        done()
        mutable.value = AppState(restoring = false, message = "Parola a fost schimbată. Autentifică-te din nou.")
    }

    companion object {
        fun factory(repository: WasteRepository) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = WasteViewModel(repository) as T
        }
    }
}

fun errorMessage(e: Exception): String = when (e) {
    is IOException -> "Serverul nu poate fi contactat. Verifică rețeaua și conexiunea la Raspberry Pi."
    is HttpException -> when (e.code()) {
        403 -> "Nu ai permisiunea pentru această operație."
        404 -> "Resursa nu mai este disponibilă. Dacă serverul nu are /api/v1, instalează extensia backend."
        422 -> "Verifică datele introduse și câmpurile obligatorii."
        else -> runCatching {
            val detail = JsonParser.parseString(e.response()?.errorBody()?.string()).asJsonObject["detail"]
            if (detail.isJsonPrimitive) detail.asString else "Cerere nereușită (${e.code()})."
        }.getOrDefault("Cerere nereușită (${e.code()}). Reîncearcă.")
    }
    else -> "Operația nu a reușit. Reîncearcă."
}
