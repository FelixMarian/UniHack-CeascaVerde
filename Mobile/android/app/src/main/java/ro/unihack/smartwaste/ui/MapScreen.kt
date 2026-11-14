package ro.unihack.smartwaste.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import android.os.CancellationSignal
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.*
import kotlinx.coroutines.delay
import ro.unihack.smartwaste.BuildConfig
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.viewmodel.*

@Composable fun MapScreen(state: AppState, vm: WasteViewModel) {
    val context = LocalContext.current
    var location by remember { mutableStateOf<Location?>(null) }
    var gpsMessage by remember { mutableStateOf("Locația telefonului este folosită doar în acest ecran.") }
    var locating by remember { mutableStateOf(false) }
    var cancellation by remember { mutableStateOf<CancellationSignal?>(null) }
    var editingHQ by remember { mutableStateOf(false) }
    fun locate() {
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val fine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) { gpsMessage = "Permite accesul la locație pentru a vedea poziția telefonului."; return }
        val provider = listOfNotNull(if (fine) LocationManager.GPS_PROVIDER else null, LocationManager.NETWORK_PROVIDER)
            .firstOrNull { manager.isProviderEnabled(it) }
        if (provider == null) { gpsMessage = "Activează localizarea telefonului. Pentru GPS permite locația precisă."; return }
        cancellation?.cancel()
        val signal = CancellationSignal()
        cancellation = signal
        locating = true
        location = null
        gpsMessage = "Se caută poziția telefonului…"
        try {
            LocationManagerCompat.getCurrentLocation(manager, provider, signal, ContextCompat.getMainExecutor(context)) { result ->
                if (!signal.isCanceled) {
                    locating = false
                    location = result
                    gpsMessage = result?.let { "Poziție: ${it.latitude}, ${it.longitude} • precizie aproximativă ${it.accuracy.toInt()} m" }
                        ?: "Poziția nu este disponibilă. Reîncearcă lângă o fereastră sau în exterior."
                }
            }
        } catch (_: SecurityException) { locating = false; gpsMessage = "Accesul la locație a fost retras." }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { permissions ->
        if (permissions.values.any { it }) locate()
        else gpsMessage = "Locația nu a fost permisă. Poți continua fără GPS sau activa permisiunea în setările aplicației."
    }
    DisposableEffect(Unit) { onDispose { cancellation?.cancel() } }
    LaunchedEffect(locating) {
        if (locating) {
            delay(20000)
            cancellation?.cancel()
            locating = false
            gpsMessage = "Localizarea a durat prea mult. Verifică GPS-ul și reîncearcă."
        }
    }
    val user = state.user ?: return
    val located = state.bins.filter { it.latitude != null && it.longitude != null }
    val route = state.route
    val hq = if (user.hq_latitude != null && user.hq_longitude != null) LatLng(user.hq_latitude, user.hq_longitude) else null
    Page {
        Heading("Hartă și colectare", "Planifică opririle de la sediul companiei (HQ).")
        Text(if (hq == null) "HQ neconfigurat" else "HQ: ${hq.latitude}, ${hq.longitude}")
        OutlinedButton(onClick = { editingHQ = true }, enabled = !state.busy) { Text("Configurează HQ") }
        Button(onClick = {
            permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        }, enabled = !locating) { Text(if (locating) "Se localizează…" else "Localizează-mă") }
        Text(gpsMessage)
        if (BuildConfig.MAPS_CONFIGURED) {
            val camera = rememberCameraPositionState()
            var loaded by remember { mutableStateOf(false) }
            val points = located.map { LatLng(it.latitude!!, it.longitude!!) } + listOfNotNull(hq, location?.let { LatLng(it.latitude, it.longitude) })
            LaunchedEffect(points, loaded) {
                if (loaded && points.isNotEmpty()) {
                    if (points.distinct().size == 1) camera.animate(CameraUpdateFactory.newLatLngZoom(points.first(), 15f))
                    else camera.animate(CameraUpdateFactory.newLatLngBounds(LatLngBounds.builder().apply { points.forEach { include(it) } }.build(), 70))
                }
            }
            GoogleMap(Modifier.fillMaxWidth().height(320.dp), cameraPositionState = camera, onMapLoaded = { loaded = true }) {
                located.forEach { bin -> key(bin.bin_id, bin.latitude, bin.longitude) {
                    Marker(rememberMarkerState(position = LatLng(bin.latitude!!, bin.longitude!!)), title = bin.name, snippet = binLevelLabel(bin))
                } }
                hq?.let { key(it) { Marker(rememberMarkerState(position = it), title = "HQ • sediul companiei") } }
                location?.let { key(it.latitude, it.longitude) {
                    Marker(rememberMarkerState(position = LatLng(it.latitude, it.longitude)), title = "Poziția telefonului")
                } }
                route?.takeIf { it.stops.isNotEmpty() }?.let {
                    val start = LatLng(it.hq_latitude, it.hq_longitude)
                    Polyline(points = listOf(start) + it.stops.map { bin -> LatLng(bin.latitude!!, bin.longitude!!) } + start)
                }
            }
        } else Text("Harta Google va fi activată după configurarea cheii Maps. GPS-ul, sediul HQ și lista opririlor funcționează deja.")
        Button(onClick = vm::generateRoute, enabled = !state.busy) { Text("Generare rută") }
        Text("Se includ tomberoanele pline ale companiei. Cele deteriorate necesită reparație și sunt excluse. Ordinea este aproximativă, după distanța directă; nu reprezintă navigație pe străzi.")
        route?.let {
            Text("Plecare: HQ → ${it.stops.size} opriri → întoarcere la HQ")
            if (it.stops.isEmpty()) Text("Niciun tomberon plin cu coordonate disponibile.")
            it.stops.forEachIndexed { index, bin ->
                Text("${index + 1}. ${bin.name} (${bin.bin_id}) • ${bin.latitude}, ${bin.longitude}")
            }
            Text("Distanță în linie dreaptă, cu întoarcere: ${it.straight_line_meters} m")
            if (it.skipped_bin_ids.isNotEmpty()) Text("Omise: lipsesc coordonatele pentru ${it.skipped_bin_ids.joinToString()}.")
        }
    }
    if (editingHQ) HQEditor(user, state, vm) { editingHQ = false }
}

@Composable fun HQEditor(user: User, state: AppState, vm: WasteViewModel, close: () -> Unit) {
    var latitude by remember { mutableStateOf(user.hq_latitude?.toString() ?: "") }
    var longitude by remember { mutableStateOf(user.hq_longitude?.toString() ?: "") }
    val lat = latitude.trim().replace(',', '.').toDoubleOrNull()
    val lon = longitude.trim().replace(',', '.').toDoubleOrNull()
    val valid = (latitude.isBlank() && longitude.isBlank()) ||
        (lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0)
    FormDialog("HQ: ${user.display_name}", state.busy, state.error, valid, close,
        { vm.hq(user.id, HQInput(lat, lon), close) }) {
        Text("Coordonatele sediului de unde pleacă agenții. Lasă ambele câmpuri goale pentru a șterge HQ.")
        OutlinedTextField(latitude, { latitude = it }, label = { Text("Latitudine HQ") }, singleLine = true)
        OutlinedTextField(longitude, { longitude = it }, label = { Text("Longitudine HQ") }, singleLine = true)
    }
}
