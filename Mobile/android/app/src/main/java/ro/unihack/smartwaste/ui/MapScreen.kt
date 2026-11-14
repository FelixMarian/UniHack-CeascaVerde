package ro.unihack.smartwaste.ui

import android.content.Intent
import android.net.Uri
import android.graphics.Color
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.XYTileSource
import org.osmdroid.util.GeoPoint
import org.osmdroid.util.BoundingBox
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polyline
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.viewmodel.*

fun mapsSegmentUrl(points: List<Pair<Double, Double>>, offset: Int): String {
    val part = points.drop(offset).take(4)
    require(part.isNotEmpty())
    fun coordinate(p: Pair<Double, Double>) = "${p.first},${p.second}"
    return "https://www.google.com/maps/dir/?api=1&travelmode=driving&dir_action=navigate&destination=" +
        coordinate(part.last()) + if (part.size > 1) "&waypoints=" + part.dropLast(1).joinToString("%7C") { coordinate(it) } else ""
}

@Composable fun WasteMap(state: AppState) {
    val context = LocalContext.current
    val uri = LocalUriHandler.current
    val map = remember {
        Configuration.getInstance().apply {
            userAgentValue = "ro.unihack.smartwaste/1.3.0 (Android hackathon demo)"
            osmdroidBasePath = java.io.File(context.cacheDir, "osm")
            osmdroidTileCache = java.io.File(context.cacheDir, "osm/tiles")
        }
        MapView(context).apply {
            setTileSource(XYTileSource("OpenStreetMap", 0, 19, 256, ".png", arrayOf("https://tile.openstreetmap.org/"), "© OpenStreetMap contributors"))
            setMultiTouchControls(true)
            controller.setZoom(13.0)
            controller.setCenter(GeoPoint(45.7489, 21.2087))
        }
    }
    DisposableEffect(map) { map.onResume(); onDispose { map.onPause(); map.onDetach() } }
    val user = state.user
    val route = state.route
    LaunchedEffect(state.bins, user?.hq_latitude, user?.hq_longitude, route?.id) {
        map.overlays.clear()
        val points = mutableListOf<GeoPoint>()
        fun marker(point: GeoPoint, name: String, detail: String, color: Int) {
            points.add(point)
            map.overlays.add(Marker(map).apply {
                position = point; title = name; snippet = detail
                icon = android.graphics.drawable.GradientDrawable().apply {
                    shape = android.graphics.drawable.GradientDrawable.OVAL
                    setColor(color); setStroke(3, Color.WHITE)
                    val size = (18 * context.resources.displayMetrics.density).toInt()
                    setSize(size, size)
                }
                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            })
        }
        state.bins.filter { it.latitude != null && it.longitude != null }.forEach {
            val color = when (binState(it)) { FillState.NORMAL -> Color.rgb(35,130,65); FillState.WARNING -> Color.rgb(210,150,0); FillState.FULL -> Color.rgb(195,45,45); FillState.DAMAGED -> Color.rgb(130,60,170); else -> Color.GRAY }
            marker(GeoPoint(it.latitude!!, it.longitude!!), it.name, "${it.bin_id} • ${binLevelLabel(it)}", color)
        }
        if (user?.hq_latitude != null && user.hq_longitude != null)
            marker(GeoPoint(user.hq_latitude, user.hq_longitude), "HQ", "Punct de plecare și întoarcere", Color.BLUE)
        route?.geometry?.takeIf { it.size > 1 }?.let { geometry ->
            val line = geometry.map { GeoPoint(it[0], it[1]) }
            points.addAll(line)
            map.overlays.add(0, Polyline(map).apply { setPoints(line); outlinePaint.color = Color.rgb(30, 110, 65); outlinePaint.strokeWidth = 9f })
        }
        if (points.isNotEmpty()) map.post {
            if (points.distinctBy { it.latitude to it.longitude }.size == 1) map.controller.setCenter(points.first())
            else map.zoomToBoundingBox(BoundingBox.fromGeoPoints(points), false, 60)
        }
        map.invalidate()
    }
    AndroidView(factory = { map }, modifier = Modifier.fillMaxWidth().height(360.dp).clipToBounds())
    TextButton(onClick = { uri.openUri("https://www.openstreetmap.org/copyright") }) { Text("© OpenStreetMap contributors") }
    Text("Verde: gol • galben: mediu • roșu: plin • mov: deteriorat • albastru: HQ", style = MaterialTheme.typography.bodySmall)
    Text("Harta necesită internet. Traseu: openrouteservice / © OpenStreetMap contributors.", style = MaterialTheme.typography.bodySmall)
}

@Composable fun MapScreen(state: AppState, vm: WasteViewModel) {
    val context = LocalContext.current
    val user = state.user ?: return
    var editingHQ by remember { mutableStateOf(false) }
    var completing by remember { mutableStateOf(false) }
    var consumption by rememberSaveable { mutableStateOf("20") }
    val rate = consumption.replace(',', '.').toDoubleOrNull()
    val route = state.route
    var checkpoint by rememberSaveable(route?.id) { mutableIntStateOf(0) }
    var lastSegmentSize by rememberSaveable(route?.id) { mutableIntStateOf(1) }
    var navigationError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { vm.loadRoutes() }
    fun open(url: String, packageName: String?) {
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            if (packageName != null) intent.setPackage(packageName)
            try { context.startActivity(intent) }
            catch (_: android.content.ActivityNotFoundException) { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
        } catch (_: Exception) { navigationError = "Nu există o aplicație care poate deschide navigarea. Instalează Google Maps sau Waze." }
    }
    Page {
        Heading("Hartă și rută", "Plecare din HQ • colectarea tomberoanelor pline")
        WasteMap(state)
        Text(if (user.hq_latitude == null) "HQ neconfigurat" else "HQ: ${user.hq_latitude}, ${user.hq_longitude}")
        OutlinedButton(onClick = { editingHQ = true }, enabled = !state.busy) { Text("Configurează HQ") }
        OutlinedTextField(consumption, { consumption = it }, label = { Text("Consum estimat (litri / 100 km)") }, singleLine = true)
        Button(onClick = { vm.generateRoute(rate!!) }, enabled = !state.busy && rate != null && rate.isFinite() && rate in 1.0..100.0) { Text("Generează ruta cu Gemini") }
        Text("Gemini propune ordinea, iar openrouteservice furnizează distanțele și traseul pe drumuri. Se exclud tomberoanele deteriorate. Nu este garantat optimul global sau accesul unui camion.", style = MaterialTheme.typography.bodySmall)
        if (state.routes.any { it.status != "completed" }) Choice("Rută salvată", state.routes.filter { it.status != "completed" }, route,
            { "${it.id.take(8)} • ${it.stops.size} opriri • ${it.status}" }) { vm.selectRoute(it) }
        route?.let { r ->
            Text("${r.planner} • ${"%.2f".format(r.distance_meters/1000)} km • ${"%.0f".format(r.duration_seconds/60)} min de condus")
            Text("Combustibil estimat: ${"%.2f".format(r.estimated_fuel_liters)} L • fără timpul de colectare")
            Text("HQ → ${r.stops.size} opriri → HQ")
            r.stops.forEachIndexed { index, bin -> Text("${index+1}. ${bin.name} (${bin.bin_id})") }
            if (r.skipped_bin_ids.isNotEmpty()) Text("Fără coordonate, excluse: ${r.skipped_bin_ids.joinToString()}")
            val points = r.stops.map { it.latitude!! to it.longitude!! } + (r.hq_latitude to r.hq_longitude)
            if (r.status != "completed" && checkpoint < points.size) {
                Text("Navigare de la poziția curentă din Maps/Waze. Planul pornește din HQ; mergi întâi la HQ dacă nu ești acolo.")
                Button(onClick = { vm.startRoute(r) {
                    lastSegmentSize = minOf(4, points.size-checkpoint)
                    open(mapsSegmentUrl(points, checkpoint), "com.google.android.apps.maps")
                } }, enabled = !state.busy) { Text("Începe navigarea în Google Maps") }
                OutlinedButton(onClick = { vm.startRoute(r) {
                    lastSegmentSize = 1
                    val p = points[checkpoint]
                    open("https://waze.com/ul?ll=${p.first},${p.second}&navigate=yes", "com.waze")
                } }, enabled = !state.busy) { Text("Waze → următoarea oprire") }
                Text("Google Maps: maximum 4 opriri pe segment. Waze: o oprire. După parcurgere revino aici; colectarea se confirmă separat în Tomberoane.", style = MaterialTheme.typography.bodySmall)
                if (r.status == "started") OutlinedButton(onClick = { checkpoint = minOf(points.size, checkpoint+lastSegmentSize) }) { Text("Am parcurs segmentul → următorul") }
            }
            if (r.status == "started") Button(onClick = { completing = true }, enabled = !state.busy) { Text("Finalizează cursa / kilometraj") }
            if (r.status == "completed") Text("Cursă finalizată")
        }
        navigationError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
    if (editingHQ) HQEditor(user, state, vm) { editingHQ = false }
    if (completing && route != null) {
        var kilometers by remember { mutableStateOf("") }
        val km = kilometers.replace(',', '.').toDoubleOrNull()
        FormDialog("Finalizează cursa", state.busy, state.error, km != null && km.isFinite() && km in 0.0..10000.0,
            { completing = false }, { vm.finishRoute(route, km!!) { completing = false } }) {
            Text("Introdu kilometrii efectiv parcurși, calculați din kilometrajul mașinii. Aplicația nu urmărește GPS-ul. Consumul rămâne o estimare.")
            OutlinedTextField(kilometers, { kilometers = it }, label = { Text("Kilometri parcurși") }, singleLine = true)
        }
    }
}
