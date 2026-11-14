package ro.unihack.smartwaste.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

interface TokenStore {
    var token: String?
}

/** Only an AES-GCM ciphertext is persisted. The key never leaves Android Keystore. */
class SessionStore(context: Context) : TokenStore {
    private val preferences = context.getSharedPreferences("session", Context.MODE_PRIVATE)
    private val alias = "smartwaste_session_v1"
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
        }.generateKey()
    }
    @Volatile private var cached: String? = runCatching {
        val encoded = preferences.getString("ciphertext", null) ?: return@runCatching null
        val parts = encoded.split(":")
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)))
        String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), Charsets.UTF_8)
    }.getOrElse { preferences.edit().clear().commit(); null }

    override var token: String?
        get() = cached
        @Synchronized set(value) {
            if (value == null) {
                cached = null
                check(preferences.edit().clear().commit()) { "Sesiunea nu a putut fi ștearsă." }
            } else {
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.ENCRYPT_MODE, key())
                val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
                val data = Base64.encodeToString(cipher.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
                check(preferences.edit().putString("ciphertext", "$iv:$data").commit()) { "Sesiunea nu a putut fi salvată." }
                cached = value
            }
        }
}
