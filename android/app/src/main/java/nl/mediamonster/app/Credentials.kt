package nl.mediamonster.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object Credentials {
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("media-monster-token", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("media-monster-token",
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun save(context: Context, token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        context.getSharedPreferences("connection", Context.MODE_PRIVATE).edit()
            .putString("tokenCipher", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString("tokenIv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP)).apply()
    }
    fun clear(context: Context) {
        context.getSharedPreferences("connection", Context.MODE_PRIVATE).edit()
            .remove("tokenCipher").remove("tokenIv").apply()
    }
    fun read(context: Context): String = runCatching {
        val prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val encrypted = prefs.getString("tokenCipher", null) ?: return ""
        val iv = prefs.getString("tokenIv", null) ?: return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
        }
        String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), Charsets.UTF_8)
    }.getOrDefault("")
}
