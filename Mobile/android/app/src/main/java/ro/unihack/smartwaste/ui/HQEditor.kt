package ro.unihack.smartwaste.ui
import androidx.compose.material3.*
import androidx.compose.runtime.*
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.viewmodel.*
@Composable fun HQEditor(user: User, state: AppState, vm: WasteViewModel, close: () -> Unit) {
    var latitude by remember { mutableStateOf(user.hq_latitude?.toString() ?: "") }
    var longitude by remember { mutableStateOf(user.hq_longitude?.toString() ?: "") }
    val lat = latitude.trim().replace(',', '.').toDoubleOrNull()
    val lon = longitude.trim().replace(',', '.').toDoubleOrNull()
    val valid = (latitude.isBlank() && longitude.isBlank()) ||
        (lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0)
    FormDialog("HQ: ${user.display_name}", state.busy, state.error, valid, close,
        { vm.hq(user.id, HQInput(lat, lon), close) }) {
        Text("Coordonatele sediului de unde pleacÄƒ agenÈ›ii. LasÄƒ ambele cÃ¢mpuri goale pentru a È™terge HQ.")
        OutlinedTextField(latitude, { latitude = it }, label = { Text("Latitudine HQ") }, singleLine = true)
        OutlinedTextField(longitude, { longitude = it }, label = { Text("Longitudine HQ") }, singleLine = true)
    }
}
