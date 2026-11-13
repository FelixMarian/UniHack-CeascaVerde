package ro.unihack.smartwaste.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.*
import ro.unihack.smartwaste.BuildConfig
import ro.unihack.smartwaste.viewmodel.AppState

@Composable fun MapScreen(state: AppState) {
    val located = state.bins.filter { it.latitude != null && it.longitude != null }
    var selectedId by remember { mutableStateOf<String?>(null) }
    val selected = state.bins.find { it.bin_id == selectedId }
    if (!BuildConfig.MAPS_CONFIGURED) {
        Page { Heading("Harta nu este configurată", "Adaugă cheia Google Maps în local.properties și reconstruiește aplicația. Datele tomberoanelor sunt disponibile în dashboard.") }
        return
    }
    val camera = rememberCameraPositionState()
    var loaded by remember { mutableStateOf(false) }
    LaunchedEffect(located, loaded) {
        if (loaded && located.isNotEmpty()) {
            val points = located.map { LatLng(it.latitude!!, it.longitude!!) }
            if (points.size == 1) camera.animate(CameraUpdateFactory.newLatLngZoom(points.first(), 15f))
            else {
                val bounds = LatLngBounds.builder().apply { points.forEach { include(it) } }.build()
                camera.animate(CameraUpdateFactory.newLatLngBounds(bounds, 80))
            }
        }
    }
    Column(Modifier.fillMaxSize()) {
        if (located.size < state.bins.size) Text("${state.bins.size - located.size} tomberoane fără coordonate", Modifier.padding(12.dp))
        if (located.isEmpty()) Text("Nu există tomberoane cu coordonate disponibile.", Modifier.padding(12.dp))
        GoogleMap(Modifier.weight(1f).fillMaxWidth(), cameraPositionState = camera, onMapLoaded = { loaded = true }) {
            located.forEach { bin -> key(bin.bin_id, bin.latitude, bin.longitude) {
                Marker(state = rememberMarkerState(position = LatLng(bin.latitude!!, bin.longitude!!)),
                    title = bin.name, snippet = bin.fill_level?.let { "$it% ocupare" } ?: "Fără măsurători",
                    onClick = { selectedId = bin.bin_id; false })
            } }
        }
        selected?.let { bin -> Box(Modifier.padding(12.dp)) { BinCard(bin) } }
    }
}
