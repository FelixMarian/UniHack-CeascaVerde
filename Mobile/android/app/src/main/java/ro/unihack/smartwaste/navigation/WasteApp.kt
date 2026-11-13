package ro.unihack.smartwaste.navigation

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.*
import ro.unihack.smartwaste.ui.*
import ro.unihack.smartwaste.viewmodel.WasteViewModel

fun routesFor(role: String): List<Pair<String, String>> = when (role) {
    "Resident" -> listOf("dashboard" to "Tomberoane", "report" to "Sesizare", "incidents" to "Sesizările mele", "profile" to "Profil")
    "Company" -> listOf("dashboard" to "Tomberoane", "map" to "Hartă", "incidents" to "Incidente", "profile" to "Profil")
    "Admin" -> listOf("users" to "Locatari", "companies" to "Companii", "dashboard" to "Tomberoane", "incidents" to "Incidente", "profile" to "Profil")
    else -> emptyList()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun WasteApp(vm: WasteViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    if (state.restoring) { Box(Modifier.fillMaxSize().safeDrawingPadding()) { CircularProgressIndicator(Modifier.padding(32.dp)) }; return }
    val user = state.user
    if (user == null) { LoginScreen(state, vm); return }
    key(user.id) {
        val nav = rememberNavController()
        val routes = routesFor(user.role)
        val entry by nav.currentBackStackEntryAsState()
        Scaffold(topBar = {
            Column {
                TopAppBar(title = { Text("SmartWaste") }, actions = {
                    TextButton(onClick = vm::refresh, enabled = !state.busy) { Text("Actualizează") }
                })
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    routes.forEach { (route, label) ->
                        FilterChip(selected = entry?.destination?.route == route, label = { Text(label) },
                            onClick = { nav.navigate(route) { popUpTo(nav.graph.startDestinationId); launchSingleTop = true } })
                    }
                }
                if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error) }
                state.message?.let { Text(it, Modifier.padding(horizontal = 12.dp), color = MaterialTheme.colorScheme.primary) }
            }
        }) { padding ->
            NavHost(nav, startDestination = routes.first().first, modifier = Modifier.padding(padding)) {
                routes.forEach { (route, _) -> composable(route) {
                    when (route) {
                        "dashboard" -> DashboardScreen(state, vm)
                        "report" -> ReportScreen(state, vm) { nav.navigate("incidents") { popUpTo("dashboard") } }
                        "incidents" -> IncidentsScreen(state, vm)
                        "map" -> MapScreen(state)
                        "users" -> UsersScreen(state, vm, "Resident")
                        "companies" -> UsersScreen(state, vm, "Company")
                        "profile" -> ProfileScreen(state, vm)
                    }
                } }
            }
        }
    }
}
