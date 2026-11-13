package ro.unihack.smartwaste.repository

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ro.unihack.smartwaste.api.SmartWasteApi
import ro.unihack.smartwaste.auth.TokenStore
import ro.unihack.smartwaste.model.LoginRequest

class WasteRepository(val api: SmartWasteApi, private val store: TokenStore) {
    val hasSession get() = store.token != null
    suspend fun login(username: String, password: String) = api.login(LoginRequest(username, password)).also {
        withContext(Dispatchers.IO) { store.token = it.access_token }
    }.user
    suspend fun clearSession() = withContext(Dispatchers.IO) { store.token = null }
    suspend fun logout() {
        try { api.logout() } finally { clearSession() }
    }
}
