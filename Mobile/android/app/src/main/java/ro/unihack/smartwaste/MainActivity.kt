package ro.unihack.smartwaste

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import ro.unihack.smartwaste.api.api
import ro.unihack.smartwaste.auth.SessionStore
import ro.unihack.smartwaste.repository.WasteRepository
import ro.unihack.smartwaste.ui.SmartWasteTheme
import ro.unihack.smartwaste.navigation.WasteApp
import ro.unihack.smartwaste.viewmodel.WasteViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val repository = remember {
                val store = SessionStore(applicationContext)
                WasteRepository(api(BuildConfig.API_BASE_URL, store), store)
            }
            val vm: WasteViewModel = viewModel(factory = WasteViewModel.factory(repository))
            SmartWasteTheme { WasteApp(vm) }
        }
    }
}
