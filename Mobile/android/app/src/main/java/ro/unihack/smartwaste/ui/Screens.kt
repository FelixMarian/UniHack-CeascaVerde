package ro.unihack.smartwaste.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import ro.unihack.smartwaste.BuildConfig
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.viewmodel.*

val categories = linkedMapOf("damaged" to "Tomberon deteriorat", "overflow" to "Deșeuri lângă tomberon",
    "missed_collection" to "Colectare neefectuată", "other" to "Altă problemă")
val statuses = linkedMapOf("open" to "Deschisă", "in_progress" to "În lucru", "resolved" to "Rezolvată")

@Composable fun LoginScreen(state: AppState, vm: WasteViewModel) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Surface(Modifier.fillMaxSize().safeDrawingPadding()) {
        Page {
            Spacer(Modifier.height(48.dp))
            Text("UNIHACK 2026", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Heading("SmartWaste", "Un oraș mai curat începe cu informații la timp.")
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(username, { username = it }, label = { Text("Utilizator") }, singleLine = true, modifier = Modifier.fillMaxWidth(), enabled = !state.busy)
            OutlinedTextField(password, { password = it }, label = { Text("Parolă") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), enabled = !state.busy)
            Button(onClick = { vm.login(username, password); password = "" }, enabled = !state.busy && username.isNotBlank() && password.isNotEmpty(), modifier = Modifier.fillMaxWidth()) {
                Text(if (state.busy) "Se conectează…" else "Autentificare")
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error); TextButton(onClick = vm::refresh, enabled = !state.busy) { Text("Reîncearcă sesiunea") } }
            state.message?.let { Text(it) }
            Text("Conectează telefonul la rețeaua serverului.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable fun DashboardScreen(state: AppState, vm: WasteViewModel) {
    var editing by remember { mutableStateOf<Bin?>(null) }
    var creating by remember { mutableStateOf(false) }
    var collecting by remember { mutableStateOf<Bin?>(null) }
    val admin = state.user?.role == "Admin"
    Page {
        Heading(if (admin) "Tomberoane" else "Tomberoanele tale", "${state.bins.size} înregistrate • ${state.bins.count { (it.fill_level ?: 0) >= 80 }} necesită colectare")
        if (admin) Button(onClick = { creating = true }, enabled = !state.busy) { Text("Înregistrează tomberon") }
        if (state.bins.isEmpty() && !state.busy) Empty("Nu există tomberoane disponibile. Asignările sunt gestionate de administrator.")
        state.bins.forEach { bin ->
            BinCard(bin) {
                if (admin) TextButton(onClick = { editing = bin }, enabled = !state.busy) { Text("Editează / Companie") }
                if (state.user?.role in listOf("Company", "Admin")) OutlinedButton(onClick = { collecting = bin }, enabled = !state.busy) { Text("Confirmă colectarea") }
            }
        }
    }
    if (creating || editing != null) BinEditor(editing, state, vm) { editing = null; creating = false }
    collecting?.let { bin ->
        AlertDialog(onDismissRequest = { collecting = null }, title = { Text("Confirmi colectarea?") },
            text = { Text("${bin.name} (${bin.bin_id}). Confirmă doar după golire. Nivelul afișat se schimbă la următoarea măsurătoare a senzorului.") },
            confirmButton = { TextButton(onClick = { collecting = null; vm.collect(bin) }, enabled = !state.busy) { Text("Confirmă") } },
            dismissButton = { TextButton(onClick = { collecting = null }) { Text("Anulează") } })
    }
}

@Composable fun ReportScreen(state: AppState, vm: WasteViewModel, done: () -> Unit) {
    var binId by remember { mutableStateOf<String?>(null) }
    var category by remember { mutableStateOf("damaged") }
    var comment by remember { mutableStateOf("") }
    Page {
        Heading("Raportează o problemă", "Sesizarea ajunge la compania responsabilă de tomberon.")
        if (state.bins.isEmpty()) Empty("Nu ai tomberoane asignate. Contactează administratorul.")
        Choice("Tomberon", state.bins.map { it.bin_id }, binId, { id -> state.bins.find { it.bin_id == id }?.let { "${it.name} ($id)" } ?: id }) { binId = it }
        Choice("Categorie", categories.keys.toList(), category, { categories.getValue(it) }) { category = it }
        OutlinedTextField(comment, { if (it.length <= 2000) comment = it }, label = { Text("Comentariu obligatoriu") }, minLines = 4, modifier = Modifier.fillMaxWidth())
        Text("${comment.length}/2000", style = MaterialTheme.typography.labelSmall)
        Button(onClick = { vm.report(IncidentInput(binId!!, category, comment.trim()), done) },
            enabled = !state.busy && state.bins.any { it.bin_id == binId } && comment.isNotBlank()) { Text("Trimite sesizarea") }
    }
}

@Composable fun IncidentsScreen(state: AppState, vm: WasteViewModel) {
    Page {
        Heading(if (state.user?.role == "Resident") "Sesizările mele" else "Incidente", "Urmărește statusul problemelor raportate.")
        if (state.incidents.isEmpty() && !state.busy) Empty("Nu există sesizări.")
        state.incidents.forEach { incident ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(categories[incident.category] ?: incident.category, style = MaterialTheme.typography.titleMedium)
                    Text("#${incident.id} • ${incident.bin_id} • ${dateLabel(incident.created_at)}", style = MaterialTheme.typography.labelMedium)
                    Text(incident.comment)
                    Text(statuses[incident.status] ?: incident.status, color = MaterialTheme.colorScheme.primary)
                    if (state.user?.role != "Resident") {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (incident.status != "in_progress") TextButton(onClick = { vm.status(incident.id, "in_progress") }, enabled = !state.busy) { Text("În lucru") }
                            if (incident.status != "resolved") TextButton(onClick = { vm.status(incident.id, "resolved") }, enabled = !state.busy) { Text("Rezolvă") }
                            if (incident.status == "resolved") TextButton(onClick = { vm.status(incident.id, "open") }, enabled = !state.busy) { Text("Redeschide") }
                        }
                    }
                }
            }
        }
    }
}

@Composable fun ProfileScreen(state: AppState, vm: WasteViewModel) {
    var changing by remember { mutableStateOf(false) }
    Page {
        Heading(state.user?.display_name ?: "Profil", "${state.user?.username} • ${state.user?.role}")
        if (state.user?.demo == true) Text("Cont demonstrativ. Schimbă parola înainte de utilizarea reală.")
        OutlinedButton(onClick = { changing = true }, enabled = !state.busy) { Text("Schimbă parola") }
        Button(onClick = vm::logout) { Text("Deconectare") }
    }
    if (changing) {
        var current by remember { mutableStateOf("") }
        var new by remember { mutableStateOf("") }
        FormDialog("Schimbă parola", state.busy, state.error, new.length in 8..128 && current.isNotEmpty(),
            { changing = false }, { vm.password(current, new) { changing = false } }) {
            OutlinedTextField(current, { current = it }, label = { Text("Parola curentă") }, visualTransformation = PasswordVisualTransformation())
            OutlinedTextField(new, { new = it }, label = { Text("Parola nouă (min. 8 caractere)") }, visualTransformation = PasswordVisualTransformation())
        }
    }
}
