package ro.unihack.smartwaste.ui

import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalUriHandler
import ro.unihack.smartwaste.viewmodel.*

@Composable fun ProofPanel(id: Int, state: AppState, vm: WasteViewModel) {
    val uri = LocalUriHandler.current
    OutlinedButton(onClick = { vm.proof(id) }, enabled = !state.busy) { Text("Verifică pe Solana") }
    state.proofs[id]?.let { proof ->
        Text(when (proof.status) {
            "verified" -> "Verificat pe Solana Devnet • conținutul coincide cu hash-ul publicat."
            "prepared" -> "Hash pregătit. Publicarea pe Devnet așteaptă serviciul Solana al serverului."
            "pending" -> "Tranzacția nu este încă finalizată sau nu a fost găsită."
            "content_changed" -> "Conținutul sesizării diferă de dovada pregătită."
            "invalid" -> "Tranzacția nu confirmă această sesizare."
            else -> "Solana nu este disponibilă momentan. Reîncearcă."
        })
        proof.sha256?.let { SelectionContainer { Text("SHA-256: $it", style = MaterialTheme.typography.bodySmall) } }
        proof.signature?.let { signature ->
            if (signature.matches(Regex("[1-9A-HJ-NP-Za-km-z]{64,100}"))) {
                TextButton(onClick = { uri.openUri("https://explorer.solana.com/tx/$signature?cluster=devnet") }) { Text("Vezi tranzacția Devnet") }
            }
        }
        Text("Dovada confirmă integritatea sesizării, nu adevărul problemei raportate.", style = MaterialTheme.typography.bodySmall)
    }
}
