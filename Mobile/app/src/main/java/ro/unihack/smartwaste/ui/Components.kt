package ro.unihack.smartwaste.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ro.unihack.smartwaste.model.*
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable fun SmartWasteTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF236B45), secondary = Color(0xFF526454),
        primaryContainer = Color(0xFFD5EBDC), onPrimaryContainer = Color(0xFF173D28),
        secondaryContainer = Color(0xFFDCE9DE), onSecondaryContainer = Color(0xFF253D2B),
        background = Color(0xFFF6F8F5), surface = Color(0xFFF6F8F5), surfaceContainer = Color(0xFFEAF0E8),
        surfaceContainerHighest = Color(0xFFE6ECE4), surfaceVariant = Color(0xFFE6ECE4)), content = content)
}

@Composable fun Page(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp), content = content)
}
@Composable fun Heading(title: String, description: String) {
    Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
    Text(description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
@Composable fun Empty(text: String) { Text(text, Modifier.padding(vertical = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
fun dateLabel(value: String?): String = value?.let {
    runCatching { OffsetDateTime.parse(it).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")) }.getOrDefault(it)
} ?: "Fără măsurători"

@Composable fun BinCard(bin: Bin, action: (@Composable () -> Unit)? = null) {
    val state = binState(bin)
    val color = when (state) {
        FillState.UNKNOWN -> Color.Gray
        FillState.NORMAL -> Color(0xFF27754A)
        FillState.WARNING -> Color(0xFFAA7800)
        FillState.FULL -> Color(0xFFBE3C37)
        FillState.DAMAGED -> Color(0xFF70509B)
    }
    val label = when (state) { FillState.UNKNOWN -> "Fără date"; FillState.NORMAL -> "Disponibil"; FillState.WARNING -> "Se umple"; FillState.FULL -> "Necesită colectare"; FillState.DAMAGED -> "Necesită reparație" }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {
                    Text(bin.name, style = MaterialTheme.typography.titleMedium)
                    Text(bin.bin_id + if (bin.demo) " • DEMO" else "", style = MaterialTheme.typography.labelMedium)
                }
                Text(binLevelLabel(bin), style = MaterialTheme.typography.headlineSmall, color = color)
            }
            if (bin.fill_category == null && bin.fill_level != null) LinearProgressIndicator(progress = { bin.fill_level.coerceIn(0, 100) / 100f },
                modifier = Modifier.fillMaxWidth(), color = color)
            Text(if (bin.fill_category != null) "Categorie: ${bin.fill_category} • ${binLevelLabel(bin)}" else label, color = color)
            Text("Actualizat: ${dateLabel(bin.recorded_at)}", style = MaterialTheme.typography.bodySmall)
            action?.invoke()
        }
    }
}

@Composable fun <T> Choice(label: String, values: List<T>, selected: T?, display: (T) -> String, onSelect: (T) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
            Text("$label: ${selected?.let(display) ?: "Selectează"}")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            values.forEach { value -> DropdownMenuItem(text = { Text(display(value)) }, onClick = { expanded = false; onSelect(value) }) }
        }
    }
}

@Composable fun FormDialog(title: String, busy: Boolean, error: String?, valid: Boolean = true,
    dismiss: () -> Unit, save: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    AlertDialog(onDismissRequest = { if (!busy) dismiss() }, title = { Text(title) }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            content()
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = save, enabled = !busy && valid) { Text(if (busy) "Se salvează…" else "Salvează") } },
        dismissButton = { TextButton(onClick = dismiss, enabled = !busy) { Text("Anulează") } })
}
