package nl.mediamonster.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.app.NotificationManager.IMPORTANCE_NONE
import androidx.work.*
import kotlinx.coroutines.CancellationException
import java.time.LocalTime
import java.util.concurrent.TimeUnit

internal fun quietPeriod(now: LocalTime = LocalTime.now()): Boolean {
    val minute = now.hour * 60 + now.minute
    return minute in 75 until 90 || minute in 225 until 270
}

object Monitoring {
    private const val STATE_PREFS = "notification-state"

    private fun eventKey(context: Context, name: String, kind: String): String {
        val address = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
            .getString("address", "").orEmpty()
        return "$address|$name|$kind"
    }

    @Synchronized
    fun claimEvent(context: Context, name: String, kind: String): Boolean {
        val seen = context.getSharedPreferences(STATE_PREFS, Context.MODE_PRIVATE)
        val key = eventKey(context, name, kind)
        if (seen.getBoolean(key, false)) return false
        return seen.edit().putBoolean(key, true).commit()
    }

    @Synchronized
    fun clearEvent(context: Context, name: String, kind: String) {
        context.getSharedPreferences(STATE_PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(eventKey(context, name, kind), false).commit()
    }

    fun schedule(context: Context) {
        val prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val manager = WorkManager.getInstance(context)
        if (!prefs.getBoolean("notifyStopped", false) && !prefs.getBoolean("notifyUpdates", false)) {
            manager.cancelUniqueWork("container-monitor")
            return
        }
        val work = PeriodicWorkRequestBuilder<ContainerMonitor>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        manager.enqueueUniquePeriodicWork("container-monitor", ExistingPeriodicWorkPolicy.UPDATE, work)
    }
    fun channel(context: Context): NotificationManager {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("containers", "Containerstatus", NotificationManager.IMPORTANCE_DEFAULT))
        return manager
    }
    fun blockedReason(context: Context): String? {
        val manager = channel(context)
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            return "Android-meldingsrechten zijn niet toegestaan"
        if (!manager.areNotificationsEnabled())
            return "Meldingen voor Media Monster staan uit in Android"
        if (manager.getNotificationChannel("containers")?.importance == IMPORTANCE_NONE)
            return "Het Android-meldingskanaal Containerstatus staat uit"
        return null
    }
}

class ContainerMonitor(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        if (quietPeriod()) return Result.success()
        val prefs = applicationContext.getSharedPreferences("connection", Context.MODE_PRIVATE)
        val token = Credentials.read(applicationContext)
        val address = prefs.getString("address", "").orEmpty()
        if (token.isBlank() || address.isBlank()) return Result.success()
        val manager = Monitoring.channel(applicationContext)
        if (Monitoring.blockedReason(applicationContext) != null) return Result.success()
        return try {
            val data = request(address, token, "/v1/status")
            if (!data.optBoolean("docker")) return Result.retry()
            if (data.optJSONObject("maintenance")?.optBoolean("active") == true) return Result.success()
            val containers = data.getJSONArray("containers")
            for (i in 0 until containers.length()) {
                val c = containers.getJSONObject(i)
                val name = c.getString("name")
                val state = c.optString("state")
                if (state == "unknown") continue
                val stopped = state in listOf("exited", "dead", "created") || c.optString("health") == "unhealthy"
                val update = c.optJSONObject("update")
                val events = mutableListOf<Pair<String, Boolean>>()
                if (prefs.getBoolean("notifyStopped", false)) events += "stopped" to stopped
                if (prefs.getBoolean("notifyUpdates", false) && update != null && !update.isNull("available"))
                    events += "update" to update.optBoolean("available")
                for ((kind, active) in events) {
                    val key = address + "|" + name + "|" + kind
                    if (active && Monitoring.claimEvent(applicationContext, name, kind)) {
                        val open = PendingIntent.getActivity(applicationContext, 0,
                            Intent(applicationContext, MainActivity::class.java),
                            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                        val message = if (kind == "stopped") "$name is gestopt of ongezond" else "Update beschikbaar voor $name"
                        manager.notify(key.hashCode(), Notification.Builder(applicationContext, "containers")
                            .setSmallIcon(R.drawable.ic_notification)
                            .setContentTitle("Media Monster").setContentText(message)
                            .setContentIntent(open).setAutoCancel(true).build())
                    }
                    if (!active) {
                        manager.cancel(key.hashCode())
                        Monitoring.clearEvent(applicationContext, name, kind)
                    }
                }
            }
            prefs.edit().putLong("lastMonitorSuccess", System.currentTimeMillis()).apply()
            Result.success()
        } catch (e: CancellationException) { throw e }
          catch (_: Exception) { Result.retry() }
    }
}
