package ro.unihack.smartwaste.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.viewmodel.*

@Composable fun UsersScreen(state: AppState, vm: WasteViewModel, role: String) {
    var creating by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<User?>(null) }
    var assigning by remember { mutableStateOf<User?>(null) }
    var selectedBins by remember { mutableStateOf<List<String>>(emptyList()) }
    Page {
        Heading(if (role == "Resident") "Locatari" else "Companii", "Conturi și acces la sistem")
        Button(onClick = { creating = true }, enabled = !state.busy) { Text("Creează cont") }
        val users = state.users.filter { it.role == role }
        if (users.isEmpty() && !state.busy) Empty("Niciun cont înregistrat.")
        users.forEach { user ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(user.display_name, style = MaterialTheme.typography.titleMedium)
                    Text("${user.username} • ${if (user.active) "Activ" else "Dezactivat"}")
                    Row {
                        TextButton(onClick = { editing = user }, enabled = !state.busy) { Text("Editează") }
                        if (role == "Resident" && user.active) TextButton(onClick = {
                            vm.assignments(user.id) { selectedBins = it; assigning = user }
                        }, enabled = !state.busy) { Text("Asignează tomberoane") }
                    }
                }
            }
        }
    }
    if (creating || editing != null) UserEditor(editing, role, state, vm) { creating = false; editing = null }
    assigning?.let { user ->
        FormDialog("Tomberoane: ${user.username}", state.busy, state.error, dismiss = { assigning = null },
            save = { vm.assign(user.id, selectedBins) { assigning = null } }) {
            Text("Selectează toate tomberoanele la care locatarul trebuie să aibă acces. Debifarea retrage accesul.")
            state.bins.forEach { bin ->
                Row {
                    Checkbox(checked = bin.bin_id in selectedBins, onCheckedChange = { checked ->
                        selectedBins = if (checked) selectedBins + bin.bin_id else selectedBins - bin.bin_id
                    })
                    Text("${bin.name} (${bin.bin_id})", Modifier.padding(top = 12.dp))
                }
            }
        }
    }
}

@Composable private fun UserEditor(user: User?, role: String, state: AppState, vm: WasteViewModel, close: () -> Unit) {
    var username by remember { mutableStateOf(user?.username ?: "") }
    var name by remember { mutableStateOf(user?.display_name ?: "") }
    var password by remember { mutableStateOf("") }
    var active by remember { mutableStateOf(user?.active ?: true) }
    val valid = name.isNotBlank() && name.length <= 120 &&
        (user != null || username.matches(Regex("[a-zA-Z0-9_.-]{3,80}"))) &&
        (password.length in 8..128 || (user != null && password.isEmpty()))
    FormDialog(if (user == null) "Cont $role nou" else "Editează ${user.username}", state.busy, state.error,
        valid, close, {
            if (user == null) vm.createUser(UserCreate(username, password, name.trim(), role), close)
            else vm.editUser(user.id, UserEdit(name.trim(), active, password.ifEmpty { null }), close)
        }) {
        OutlinedTextField(username, { username = it }, label = { Text("Username") }, enabled = user == null, singleLine = true)
        OutlinedTextField(name, { name = it }, label = { Text("Nume afișat") }, singleLine = true)
        OutlinedTextField(password, { password = it }, label = { Text(if (user == null) "Parolă (min. 8)" else "Parolă nouă (opțional)") },
            visualTransformation = PasswordVisualTransformation(), singleLine = true)
        if (user != null) Row { Switch(active, { active = it }); Text("Cont activ", Modifier.padding(12.dp)) }
    }
}

@Composable fun BinEditor(bin: Bin?, state: AppState, vm: WasteViewModel, close: () -> Unit) {
    var id by remember { mutableStateOf(bin?.bin_id ?: "") }
    var name by remember { mutableStateOf(bin?.name ?: "") }
    var latitude by remember { mutableStateOf(bin?.latitude?.toString() ?: "") }
    var longitude by remember { mutableStateOf(bin?.longitude?.toString() ?: "") }
    var companyId by remember { mutableIntStateOf(bin?.company_id ?: -1) }
    val lat = latitude.toDoubleOrNull()
    val lon = longitude.toDoubleOrNull()
    val coordinatesValid = (latitude.isBlank() && longitude.isBlank()) ||
        (lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0)
    val companies = state.users.filter { it.role == "Company" && (it.active || it.id == companyId) }
    FormDialog(if (bin == null) "Înregistrează tomberon" else "Editează tomberon", state.busy, state.error,
        coordinatesValid && id.matches(Regex("[a-zA-Z0-9_-]{1,80}")) && name.isNotBlank() && name.length <= 120, close, {
            vm.saveBin(BinInput(id, name.trim(), lat, lon, companyId.takeIf { it != -1 }), bin != null, close)
        }) {
        OutlinedTextField(id, { id = it }, label = { Text("ID tomberon") }, enabled = bin == null, singleLine = true)
        OutlinedTextField(name, { name = it }, label = { Text("Nume / adresă") }, singleLine = true)
        OutlinedTextField(latitude, { latitude = it }, label = { Text("Latitudine (opțional)") }, singleLine = true)
        OutlinedTextField(longitude, { longitude = it }, label = { Text("Longitudine (opțional)") }, singleLine = true)
        if (!coordinatesValid) Text("Completează ambele coordonate valide, cu punct zecimal.", color = MaterialTheme.colorScheme.error)
        Choice("Companie", listOf(-1) + companies.map { it.id }, companyId,
            { value -> companies.find { it.id == value }?.display_name ?: "Fără companie" }) { companyId = it }
    }
}
