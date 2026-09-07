package nl.mediamonster.app

import android.Manifest
import android.app.Notification
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

object PushRegistration {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun sync(context: Context) {
        FirebaseMessaging.getInstance().token.addOnSuccessListener { firebaseToken ->
            register(context.applicationContext, firebaseToken)
        }
    }

    fun register(context: Context, firebaseToken: String) {
        val prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val address = prefs.getString("address", "").orEmpty()
        val apiToken = Credentials.read(context)
        if (address.isBlank() || apiToken.isBlank() || firebaseToken.isBlank()) return
        val payload = JSONObject()
            .put("token", firebaseToken)
            .put("notifyStopped", prefs.getBoolean("notifyStopped", false))
            .put("notifyUpdates", prefs.getBoolean("notifyUpdates", false))
            .put("platform", "android")
        scope.launch {
            runCatching { request(address, apiToken, "/v1/push/register", post = true, payload = payload) }
                .onSuccess { prefs.edit().putLong("lastPushRegistration", System.currentTimeMillis()).apply() }
        }
    }

    fun test(context: Context, callback: (String) -> Unit) {
        val prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val address = prefs.getString("address", "").orEmpty()
        val apiToken = Credentials.read(context)
        FirebaseMessaging.getInstance().token
            .addOnFailureListener { callback("Push-token niet beschikbaar") }
            .addOnSuccessListener { firebaseToken ->
                scope.launch {
                    val result = runCatching {
                        request(address, apiToken, "/v1/push/test", post = true,
                            payload = JSONObject().put("token", firebaseToken))
                        "Testmelding verzonden"
                    }.getOrElse { it.message ?: "Testmelding mislukt" }
                    withContext(Dispatchers.Main) { callback(result) }
                }
            }
    }

    fun unregister(context: Context) {
        val prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val address = prefs.getString("address", "").orEmpty()
        val apiToken = Credentials.read(context)
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            val firebaseToken = if (task.isSuccessful) task.result else null
            if (firebaseToken.isNullOrBlank()) {
                FirebaseMessaging.getInstance().deleteToken()
                return@addOnCompleteListener
            }
            scope.launch {
                try {
                    request(address, apiToken, "/v1/push/unregister", post = true,
                        payload = JSONObject().put("token", firebaseToken))
                } finally {
                    FirebaseMessaging.getInstance().deleteToken()
                }
            }
        }
    }
}

class MediaMonsterMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        PushRegistration.register(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val body = data["body"] ?: return
        val manager = Monitoring.channel(applicationContext)
        if (!manager.areNotificationsEnabled() ||
            (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)) return

        val name = data["container"].orEmpty()
        val kind = data["kind"].orEmpty()
        if (kind != "test" && name.isNotBlank() && kind.isNotBlank() &&
            !Monitoring.claimEvent(applicationContext, name, kind)) return

        val open = PendingIntent.getActivity(
            applicationContext,
            0,
            Intent(applicationContext, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        manager.notify((data["eventId"] ?: body).hashCode(), Notification.Builder(applicationContext, "containers")
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(data["title"] ?: "Media Monster")
            .setContentText(body)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build())
    }
}
