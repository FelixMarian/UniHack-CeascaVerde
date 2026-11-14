package ro.unihack.smartwaste.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ro.unihack.smartwaste.viewmodel.*

@Composable fun StatisticsScreen(state: AppState, vm: WasteViewModel) {
    LaunchedEffect(Unit) { vm.loadStatistics() }
    Page {
        Heading("Statistici companie", "Date din PostgreSQL / Tiger Cloud • fus orar București")
        OutlinedButton(onClick = vm::loadStatistics, enabled = !state.busy) { Text("Actualizează statisticile") }
        state.statistics?.let { stats ->
            if (stats.has_demo_data) Text("Include date DEMO sintetice. Nu reprezintă activitate reală.", color = MaterialTheme.colorScheme.error)
            stats.periods.forEach { p ->
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(when (p.period) { "day" -> "Astăzi"; "week" -> "Săptămâna curentă (de luni)"; else -> "Luna curentă" }, style = MaterialTheme.typography.titleMedium)
                    Text("${p.collections} colectări • ${p.completed_routes} curse finalizate")
                    Text("${p.reported_km} km declarați • ${p.estimated_fuel_liters} L estimați")
                } }
            }
            Text("Colectări în ultimele 14 zile", style = MaterialTheme.typography.titleLarge)
            val maximum = stats.daily.maxOfOrNull { it.collections }?.coerceAtLeast(1) ?: 1
            stats.daily.forEach { day ->
                Text("${day.date}: ${day.collections}", style = MaterialTheme.typography.bodySmall)
                LinearProgressIndicator(progress = { day.collections.toFloat()/maximum }, modifier = Modifier.fillMaxWidth())
            }
            Text("Tomberoane • ultimele ${stats.history_days} zile", style = MaterialTheme.typography.titleLarge)
            Text("Ordine după trecerile observate de la gol/mediu la plin. Repetarea aceleiași măsurători nu numără o umplere nouă.")
            stats.bins.forEach { b ->
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(b.name + if (b.demo) " • DEMO" else "", style = MaterialTheme.typography.titleMedium)
                    Text("${b.bin_id}: ${b.full_events} umpleri • ${b.collections} colectări")
                    Text(b.average_collection_hours?.let { "Interval mediu între colectări: $it ore" } ?: "Interval indisponibil: sunt necesare cel puțin 2 colectări.")
                    Text("Ultima colectare: ${b.last_collection?.let { dateLabel(it) } ?: "fără date"}")
                } }
            }
            Text("Numărăm evenimente de colectare, nu kilograme: nu există cântar. Kilometrii sunt declarați la finalizarea cursei; combustibilul = km × consum/100. Calcularea unei rute nu mărește aceste totaluri.")
        } ?: Text(if (state.busy) "Se încarcă…" else "Statisticile nu au fost încă încărcate.")
    }
}
