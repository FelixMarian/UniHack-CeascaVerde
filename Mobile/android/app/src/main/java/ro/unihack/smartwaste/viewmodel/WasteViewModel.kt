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
import kotlinx.coroutines.delay
import retrofit2.HttpException
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.repository.WasteRepository
import com.google.gson.JsonParser
import java.io.IOException

data class AppState(val restoring: Boolean = true, val busy: Boolean = false, val user: User? = null,
    val bins: List<Bin> = emptyList(), val incidents: List<Incident> = emptyList(), val users: List<User> = emptyList(),
    val error: String? = null, val message: String? = null,
    val route: CollectionRoute? = null, val proofs: Map<Int, IncidentProof> = emptyMap(),
    val statistics: CompanyStats? = null, val routes: List<CollectionRoute> = emptyList())

class WasteViewModel(private val repository: WasteRepository) : ViewModel() {
    private val mutable = MutableStateFlow(AppState())
    val state = mutable.asStateFlow()
    private var job: Job? = null
    private var pendingReport: IncidentInput? = null

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
                if (ro.unihack.smartwaste.BuildConfig.DEBUG) android.util.Log.w("SmartWaste", "Request failed (${e.javaClass.simpleName})", e)
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
    fun generateRoute(consumption: Double) = launch {
        mutable.update { it.copy(route = null) }
        val route = repository.api.optimize(RouteInput(consumption))
        mutable.update { it.copy(route = route) }
    }
    fun proof(id: Int) = launch {
        val proof = repository.api.proof(id)
        mutable.update { it.copy(proofs = it.proofs + (id to proof)) }
    }
    fun loadStatistics() = launch { val stats = repository.api.statistics(); mutable.update { it.copy(statistics = stats) } }
    fun loadRoutes() = launch {
        val routes = repository.api.routes()
        mutable.update { it.copy(routes = routes, route = it.route ?: routes.firstOrNull { r -> r.status == "started" }) }
    }
    fun selectRoute(route: CollectionRoute) { mutable.update { it.copy(route = route) } }
    fun startRoute(route: CollectionRoute, done: () -> Unit) = launch {
        repository.api.startRoute(route.id)
        mutable.update { it.copy(route = route.copy(status = "started")) }
        done()
    }
    fun finishRoute(route: CollectionRoute, km: Double, done: () -> Unit) = launch {
        repository.api.finishRoute(route.id, FinishInput(km))
        mutable.update { it.copy(route = route.copy(status = "completed"), message = "Cursă finalizată. Kilometrajul declarat este inclus în statistici.") }
        done()
    }
    private suspend fun waitProof(id: Int) {
        repeat(25) {
            val proof = repository.api.blockchain(id)
            mutable.update { it.copy(proofs = it.proofs + (id to proof)) }
            if (proof.status == "verified") {
                mutable.update { it.copy(message = "Sesizarea #$id a fost salvată și verificată pe Solana Devnet.") }
                return
            }
            if (proof.status == "failed") {
                mutable.update { it.copy(message = null, error = "${proof.error_code}: sesizarea #$id este salvată, dar verificarea blockchain a eșuat: ${proof.message ?: proof.error_code}") }
                return
            }
            delay(2000)
        }
        mutable.update { it.copy(message = null, error = "SOLANA_CONFIRMATION_PENDING: sesizarea #$id este salvată, dar confirmarea nu a sosit încă. Verificarea continuă pe Raspberry Pi.") }
    }
    fun retryProof(id: Int) = launch { repository.api.retryProof(id); waitProof(id) }
    fun report(input: IncidentInput, done: () -> Unit) = launch {
        val previous = pendingReport
        val request = if (previous != null && previous.copy(request_id = null) == input.copy(request_id = null)) previous
            else input.copy(request_id = java.util.UUID.randomUUID().toString())
        pendingReport = request
        val incident = repository.api.report(request)
        pendingReport = null
        mutable.update { it.copy(incidents = listOf(incident) + it.incidents.filterNot { row -> row.id == incident.id }) }
        done()
        mutable.update { it.copy(message = "Sesizarea #${incident.id} este salvată. Raspberry Pi verifică automat Solana…") }
        try { waitProof(incident.id) }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { mutable.update { it.copy(message = null, error = "SOLANA_STATUS_UNAVAILABLE: sesizarea #${incident.id} este salvată, dar rezultatul verificării nu poate fi citit. Reîncearcă din lista sesizărilor.") } }
    }
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
