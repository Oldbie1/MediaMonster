package nl.mediamonster.app

import android.os.Bundle
import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.os.Build
import android.content.Context
import android.os.SystemClock
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.Image
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.activity.compose.setContent
import androidx.fragment.app.FragmentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import kotlin.math.abs

private val Green = Color(0xFF77E1AC)
private val Yellow = Color(0xFFF2CB69)
private val Red = Color(0xFFFF8585)

private data class StatusPalette(val green: Color, val yellow: Color, val red: Color)
private fun statusPalette(name: String) = when (name) {
    "bright" -> StatusPalette(Color(0xFF00E676), Color(0xFFFFD600), Color(0xFFFF4055))
    "accessible" -> StatusPalette(Color(0xFF2EC4B6), Color(0xFF4D9DE0), Color(0xFFFF6B35))
    else -> StatusPalette(Green, Yellow, Red)
}

private fun accentColor(name: String) = when (name) {
    "blue" -> Color(0xFF64B5F6)
    "purple" -> Color(0xFFB39DDB)
    "orange" -> Color(0xFFFFB74D)
    "pink" -> Color(0xFFF48FB1)
    "cyan" -> Color(0xFF4DD0E1)
    else -> Green
}

internal suspend fun request(
    base: String,
    token: String,
    path: String,
    post: Boolean = false,
    payload: JSONObject? = null
): JSONObject =
    withContext(Dispatchers.IO) {
        val normalized = normalizeAddress(base)
        val uri = URI(normalized)
        require(uri.scheme in listOf("http", "https") && uri.host != null && uri.userInfo == null &&
                uri.query == null && uri.fragment == null && uri.path in listOf("", "/")) {
            "Gebruik een serveradres zoals http://100.x.x.x:8787"
        }
        require(token.length >= 32) { "Vul het API-token in (minimaal 32 tekens)" }
        val connection = URI(normalized + path).toURL().openConnection() as HttpURLConnection
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10000
            connection.readTimeout = if (post) 900000 else 45000
            connection.requestMethod = if (post) "POST" else "GET"
            connection.setRequestProperty("Authorization", "Bearer $token")
            if (payload != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            val json = runCatching { JSONObject(body) }.getOrElse { JSONObject() }
            check(code in 200..299) { json.optString("error", "Verbindingsfout ($code)") }
            json
        } finally { connection.disconnect() }
    }

internal fun normalizeAddress(value: String): String {
    val trimmed = value.trim().trimEnd('/')
    require(trimmed.isNotBlank()) { "Vul het serveradres in" }
    if ("://" in trimmed) return trimmed
    val host = trimmed.substringBefore(':').lowercase()
    val privateAddress = host == "localhost" || host.startsWith("127.") || host.startsWith("10.") ||
        host.startsWith("192.168.") || Regex("""172\.(1[6-9]|2\d|3[01])\..+""").matches(host)
    val localName = !host.contains('.') || host.endsWith(".local")
    return (if (privateAddress || localName) "http://" else "https://") + trimmed
}

internal fun validPassword(value: String) =
    value.length in 8..256 && value.any { it.isLetter() } && value.any { it.isDigit() }

internal suspend fun authenticate(base: String, password: String): String =
    withContext(Dispatchers.IO) {
        val normalized = normalizeAddress(base)
        require(validPassword(password)) { "Gebruik minimaal 8 tekens, 1 letter en 1 cijfer" }
        val uri = URI(normalized)
        require(uri.scheme in listOf("http", "https") && uri.host != null && uri.userInfo == null &&
                uri.query == null && uri.fragment == null && uri.path in listOf("", "/")) {
            "Gebruik een serveradres zoals 192.168.72.23:8787 of mm.tenhaaf.nu"
        }
        val connection = URI(normalized + "/v1/login").toURL().openConnection() as HttpURLConnection
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10000
            connection.readTimeout = 45000
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            val payload = JSONObject().put("password", password).toString().toByteArray(Charsets.UTF_8)
            connection.outputStream.use { it.write(payload) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            val json = runCatching { JSONObject(body) }.getOrElse { JSONObject() }
            check(code in 200..299) { json.optString("error", "Inloggen mislukt ($code)") }
            json.optString("token").also {
                check(it.length >= 32) { "De server gaf geen geldige toegang terug" }
            }
        } finally { connection.disconnect() }
    }

private fun objects(json: JSONObject?, key: String): List<JSONObject> {
    val array = json?.optJSONArray(key) ?: return emptyList()
    return (0 until array.length()).map { array.getJSONObject(it) }
}
private fun space(bytes: Double): String = if (bytes >= 1e12) "%.2f TB".format(bytes / 1e12) else "%.1f GB".format(bytes / 1e9)
private fun dateTime(seconds: Long): String = java.text.DateFormat.getDateTimeInstance(
    java.text.DateFormat.SHORT, java.text.DateFormat.SHORT).format(java.util.Date(seconds * 1000))
private fun startedLabel(value: String): String = runCatching {
    val started = java.time.Instant.parse(value)
    val duration = java.time.Duration.between(started, java.time.Instant.now())
    val days = duration.toDays()
    val hours = duration.minusDays(days).toHours()
    when {
        days > 0 -> "$days dagen en $hours uur"
        duration.toHours() > 0 -> "${duration.toHours()} uur"
        else -> "${duration.toMinutes().coerceAtLeast(0)} minuten"
    }
}.getOrDefault("Onbekend")

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("connection", MODE_PRIVATE)
        setContent {
            var paletteName by remember { mutableStateOf(prefs.getString("palette", "monster") ?: "monster") }
            var accentName by remember { mutableStateOf(prefs.getString("accent", "green") ?: "green") }
            var amoled by remember { mutableStateOf(prefs.getBoolean("amoled", false)) }
            val palette = statusPalette(paletteName)
            val accent = accentColor(accentName)
            MaterialTheme(colorScheme = darkColorScheme(
                primary = accent,
                background = if (amoled) Color.Black else Color(0xFF101817),
                surface = if (amoled) Color(0xFF090909) else Color(0xFF1A2523),
                onBackground = Color(0xFFF0F5EF), onSurface = Color(0xFFF0F5EF)
            )) {
                var address by remember { mutableStateOf(prefs.getString("address", "") ?: "") }
                var token by remember { mutableStateOf(Credentials.read(this@MainActivity)) }
                var password by remember { mutableStateOf("") }
                var passwordVisible by remember { mutableStateOf(false) }
                var newPassword by remember { mutableStateOf("") }
                var settings by remember { mutableStateOf(false) }
                var configuration by remember { mutableStateOf(false) }
                var showColorPicker by remember { mutableStateOf(false) }
                var showLampPicker by remember { mutableStateOf(false) }
                var showSortPicker by remember { mutableStateOf(false) }
                var showPasswordEditor by remember { mutableStateOf(false) }
                var configFeedback by remember { mutableStateOf<String?>(null) }
                var passwordFeedback by remember { mutableStateOf<String?>(null) }
                var appUpdate by remember { mutableStateOf<JSONObject?>(null) }
                var showAppUpdate by remember { mutableStateOf(false) }
                var updateFeedback by remember { mutableStateOf<String?>(null) }
                var showStorage by remember { mutableStateOf(prefs.getBoolean("showStorage", true)) }
                var showStatus by remember { mutableStateOf(prefs.getBoolean("showStatus", false)) }
                var sortMode by remember { mutableStateOf(prefs.getString("sortMode", "az") ?: "az") }
                var data by remember { mutableStateOf<JSONObject?>(null) }
                var busy by remember { mutableStateOf(false) }
                var error by remember { mutableStateOf<String?>(null) }
                var message by remember { mutableStateOf<String?>(null) }
                var logs by remember { mutableStateOf<String?>(null) }
                var activityLog by remember { mutableStateOf<String?>(null) }
                var activityOffset by remember { mutableStateOf(0) }
                var activityHasMore by remember { mutableStateOf(false) }
                var maintenance by remember { mutableStateOf<JSONObject?>(null) }
                var details by remember { mutableStateOf<JSONObject?>(null) }
                var pending by remember { mutableStateOf<Pair<String, String>?>(null) }
                var showMaintenancePicker by remember { mutableStateOf(false) }
                var confirmUpdateAll by remember { mutableStateOf(false) }
                var notifyStopped by remember { mutableStateOf(prefs.getBoolean("notifyStopped", false)) }
                var notifyUpdates by remember { mutableStateOf(prefs.getBoolean("notifyUpdates", false)) }
                var notifyAutomaticUpdates by remember { mutableStateOf(prefs.getBoolean("notifyAutomaticUpdates", true)) }
                var automaticUpdates by remember { mutableStateOf(false) }
                var automaticRecovery by remember { mutableStateOf(true) }
                var showEasterEgg by remember { mutableStateOf(false) }
                val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
                    if (!granted) {
                        notifyStopped = false; notifyUpdates = false; notifyAutomaticUpdates = false
                        prefs.edit().putBoolean("notifyStopped", false).putBoolean("notifyUpdates", false)
                            .putBoolean("notifyAutomaticUpdates", false).apply()
                    }
                    Monitoring.schedule(this@MainActivity)
                }
                fun saveNotifications(stopped: Boolean, updates: Boolean, automatic: Boolean) {
                    prefs.edit().putBoolean("notifyStopped", stopped).putBoolean("notifyUpdates", updates)
                        .putBoolean("notifyAutomaticUpdates", automatic).apply()
                    Monitoring.channel(this@MainActivity)
                    if (Build.VERSION.SDK_INT >= 33 && (stopped || updates || automatic))
                        permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    Monitoring.schedule(this@MainActivity)
                    PushRegistration.sync(this@MainActivity)
                }
                val scope = rememberCoroutineScope()
                @Suppress("DEPRECATION")
                fun currentVersionCode() = packageManager.getPackageInfo(packageName, 0).versionCode
                fun inspectAppUpdate(manual: Boolean = false) {
                    scope.launch {
                        if (manual) {
                            busy = true
                            updateFeedback = null
                        }
                        try {
                            val release = request(address, token, "/v1/app/update")
                            if (release.optInt("versionCode") > currentVersionCode()) {
                                appUpdate = release
                                showAppUpdate = !manual
                                updateFeedback = "Versie " + release.optString("versionName") + " is beschikbaar"
                            } else if (manual) {
                                appUpdate = null
                                updateFeedback = "Je hebt de nieuwste versie"
                            }
                        } catch (e: Exception) {
                            if (manual) updateFeedback = e.message ?: "Updatecontrole mislukt"
                        } finally {
                            if (manual) busy = false
                        }
                    }
                }
                fun downloadAppUpdate(release: JSONObject) {
                    val url = release.optString("downloadUrl")
                    if (url.startsWith("https://mm.tenhaaf.nu/")) {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    }
                }
                fun openNotificationSettings() {
                    startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
                }
                fun load(withPassword: Boolean = false) {
                    scope.launch {
                        busy = true; error = null
                        try {
                            val normalized = normalizeAddress(address)
                            if (withPassword || token.isBlank()) {
                                token = authenticate(normalized, password)
                                password = ""
                            }
                            val snapshot = request(normalized, token, "/v1/status")
                            data = snapshot
                            automaticUpdates = snapshot.optJSONObject("automaticUpdates")
                                ?.optBoolean("enabled") == true
                            if (automaticUpdates && (notifyUpdates || !notifyAutomaticUpdates)) {
                                notifyUpdates = false
                                notifyAutomaticUpdates = true
                                saveNotifications(notifyStopped, false, true)
                            } else if (!automaticUpdates &&
                                (notifyAutomaticUpdates || !notifyUpdates)) {
                                notifyUpdates = true
                                notifyAutomaticUpdates = false
                                saveNotifications(notifyStopped, true, false)
                            }
                            automaticRecovery = snapshot.optJSONObject("automaticRecovery")
                                ?.optBoolean("enabled") != false
                            address = normalized
                            prefs.edit().putString("address", normalized).apply()
                            Credentials.save(this@MainActivity, token)
                            Monitoring.schedule(this@MainActivity)
                            PushRegistration.sync(this@MainActivity)
                            settings = false
                            inspectAppUpdate()
                        } catch (e: Exception) {
                            error = e.message ?: "NUC niet bereikbaar"
                            data = null
                        } finally { busy = false }
                    }
                }
                fun refreshAndCheckUpdates() {
                    scope.launch {
                        busy = true
                        error = null
                        val names = objects(data, "containers").mapNotNull {
                            it.optString("name").takeIf(String::isNotBlank)
                        }
                        message = if (names.isEmpty()) "Gegevens vernieuwen…"
                            else "Updates controleren…"
                        try {
                            var failedChecks = 0
                            for (name in names) {
                                try {
                                    request(address, token,
                                        "/v1/containers/$name/check-update", post = true)
                                } catch (_: Exception) {
                                    failedChecks++
                                }
                            }
                            val snapshot = request(address, token, "/v1/status")
                            data = snapshot
                            val available = objects(snapshot, "containers").count {
                                it.optJSONObject("update")?.optBoolean("available") == true
                            }
                            val feedback = when {
                                failedChecks > 0 ->
                                    "Updatecontrole afgerond · $failedChecks niet gelukt"
                                available == 0 -> "Updatecontrole afgerond · alles is actueel"
                                available == 1 -> "Updatecontrole afgerond · 1 update beschikbaar"
                                else -> "Updatecontrole afgerond · $available updates beschikbaar"
                            }
                            message = feedback
                            scope.launch {
                                delay(5000)
                                if (message == feedback) message = null
                            }
                        } catch (e: Exception) {
                            error = e.message ?: "Vernieuwen mislukt"
                            message = null
                        } finally {
                            busy = false
                        }
                    }
                }
                fun saveLoginPassword() {
                    scope.launch {
                        busy = true; passwordFeedback = null
                        try {
                            request(address, token, "/v1/password", post = true,
                                payload = JSONObject().put("password", newPassword))
                            newPassword = ""
                            passwordFeedback = "Wachtwoord opgeslagen"
                        } catch (e: Exception) {
                            passwordFeedback = e.message ?: "Wachtwoord opslaan mislukt"
                        } finally { busy = false }
                    }
                }
                fun setAutomaticUpdates(enabled: Boolean) {
                    scope.launch {
                        busy = true; configFeedback = null
                        try {
                            val state = request(address, token, "/v1/updates/settings", post = true,
                                payload = JSONObject().put("enabled", enabled))
                            val updatesEnabled = state.optBoolean("enabled")
                            if (updatesEnabled) {
                                notifyUpdates = false
                                notifyAutomaticUpdates = true
                                saveNotifications(notifyStopped, false, true)
                            } else {
                                notifyUpdates = true
                                notifyAutomaticUpdates = false
                                saveNotifications(notifyStopped, true, false)
                            }
                            automaticUpdates = updatesEnabled
                            val snapshot = data ?: JSONObject()
                            snapshot.put("automaticUpdates", state)
                            data = JSONObject(snapshot.toString())
                            configFeedback = if (automaticUpdates)
                                "Automatische containerupdates staan aan"
                            else "Automatische containerupdates staan uit"
                        } catch (e: Exception) {
                            configFeedback = e.message ?: "Instelling kon niet worden opgeslagen"
                        } finally { busy = false }
                    }
                }
                fun setAutomaticRecovery(enabled: Boolean) {
                    scope.launch {
                        busy = true; configFeedback = null
                        try {
                            val state = request(address, token, "/v1/recovery/settings", post = true,
                                payload = JSONObject().put("enabled", enabled))
                            automaticRecovery = state.optBoolean("enabled")
                            configFeedback = if (automaticRecovery) "Automatisch herstarten staat aan"
                                else "Automatisch herstarten staat uit"
                        } catch (e: Exception) {
                            configFeedback = e.message ?: "Instelling kon niet worden opgeslagen"
                        } finally { busy = false }
                    }
                }
                fun setMaintenance(minutes: Int) {
                    scope.launch {
                        busy = true; error = null
                        try {
                            val state = request(address, token, "/v1/maintenance", post = true,
                                payload = JSONObject().put("minutes", minutes))
                            val snapshot = data ?: JSONObject()
                            snapshot.put("maintenance", state)
                            data = JSONObject(snapshot.toString())
                            val feedback = if (state.optBoolean("active"))
                                "Onderhoudsmodus actief tot ${dateTime(state.optLong("until"))}"
                            else "Onderhoudsmodus uitgeschakeld"
                            message = feedback
                            scope.launch { delay(5000); if (message == feedback) message = null }
                        } catch (e: Exception) {
                            error = e.message ?: "Onderhoudsmodus instellen mislukt"
                        } finally { busy = false }
                    }
                }
                fun updateAll() {
                    scope.launch {
                        busy = true; error = null; message = "Beschikbare updates worden uitgevoerd…"
                        try {
                            val result = request(address, token, "/v1/containers/update-all", post = true,
                                payload = JSONObject())
                            val updated = result.optJSONArray("updated")?.length() ?: 0
                            val failed = result.optJSONArray("failed")
                            val failures = failed?.let { array ->
                                (0 until array.length()).joinToString(", ") { array.optString(it) }
                            }.orEmpty()
                            val feedback = when {
                                failures.isNotBlank() -> "$updated bijgewerkt · Mislukt: $failures"
                                updated == 0 -> "Er waren geen beschikbare updates"
                                updated == 1 -> "1 container bijgewerkt"
                                else -> "$updated containers bijgewerkt"
                            }
                            message = feedback
                            scope.launch { delay(5000); if (message == feedback) message = null }
                            data = request(address, token, "/v1/status")
                        } catch (e: Exception) {
                            error = e.message ?: "Containers bijwerken mislukt"
                        } finally { busy = false }
                    }
                }
                fun loadActivity(offset: Int = 0) {
                    scope.launch {
                        busy = true
                        try {
                            val result = request(address, token, "/v1/activity?offset=$offset")
                            val entries = result.optJSONArray("entries")
                            val page = (0 until (entries?.length() ?: 0)).joinToString("\n\n") { index ->
                                val entry = entries!!.getJSONObject(index)
                                val name = entry.optString("container").takeIf { it.isNotBlank() }?.let { " · $it" }.orEmpty()
                                val detail = entry.optString("detail").takeIf { it.isNotBlank() }?.let { "\n$it" }.orEmpty()
                                dateTime(entry.optLong("at")) + " · " + entry.optString("event") + name + detail
                            }
                            activityLog = if (offset == 0) page.ifBlank { "Nog geen activiteiten geregistreerd." }
                                else listOfNotNull(activityLog, page.takeIf { it.isNotBlank() }).joinToString("\n\n")
                            activityHasMore = result.optBoolean("hasMore")
                            activityOffset = result.optInt("nextOffset", offset + (entries?.length() ?: 0))
                        } catch (e: Exception) {
                            error = e.message ?: "Logboek kon niet worden geladen"
                        } finally { busy = false }
                    }
                }
                LaunchedEffect(Unit) {
                    prefs.edit().remove("biometric").apply()
                    if (address.isNotBlank() && token.isNotBlank()) load()
                }
                fun execute(name: String, action: String) {
                    scope.launch {
                        busy = true; error = null; message = null
                        try {
                            val result = request(address, token, "/v1/containers/$name/$action", action != "logs")
                            if (action == "logs") logs = result.optString("logs", "Geen logs")
                            else {
                                val feedback = if (action == "check-update" && result.isNull("available"))
                                    "Updatecontrole niet beschikbaar voor $name" else "Actie afgerond voor $name"
                                message = feedback
                                scope.launch {
                                    delay(5000)
                                    if (message == feedback) message = null
                                }
                                data = request(address, token, "/v1/status")
                            }
                        } catch (e: Exception) {
                            error = e.message ?: "Actie mislukt"
                        } finally { busy = false }
                    }
                }
                Box(Modifier.fillMaxSize()) {
                Surface(Modifier.fillMaxSize()) {
                    PullToRefreshBox(
                        isRefreshing = busy,
                        onRefresh = {
                            if (!busy && token.isNotBlank()) refreshAndCheckUpdates()
                        },
                        modifier = Modifier.fillMaxSize()
                    ) {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding(),
                            contentPadding = PaddingValues(20.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                        stickyHeader {
                            Surface(Modifier.fillMaxWidth()) {
                                Row(Modifier.fillMaxWidth().padding(vertical = 10.dp),
                                    verticalAlignment = Alignment.CenterVertically) {
                                    Column(Modifier.weight(1f)) {
                                        MonsterTitle()
                                        Text("Jouw mediaserver. Onder controle.", color = accent)
                                        if (busy) {
                                            LinearProgressIndicator(
                                                Modifier.fillMaxWidth().padding(top = 6.dp, end = 12.dp))
                                        } else {
                                            message?.let { Text(it, color = Red,
                                                style = MaterialTheme.typography.bodySmall) }
                                        }
                                    }
                                    if (!settings) {
                                        IconButton(onClick = { configuration = true; configFeedback = null }) {
                                            Text("⚙", style = MaterialTheme.typography.headlineSmall)
                                        }
                                    }
                                }
                            }
                        }
                        if (settings) item {
                            Card {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Text("Verbinding instellen", style = MaterialTheme.typography.titleLarge)
                                    OutlinedTextField(address, { address = it }, label = { Text("API-adres") },
                                        singleLine = true, modifier = Modifier.fillMaxWidth(), enabled = !busy)
                                    OutlinedTextField(password, { password = it }, label = { Text("Wachtwoord") },
                                        singleLine = true,
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, autoCorrectEnabled = false),
                                        visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                                        trailingIcon = { TextButton(onClick = { passwordVisible = !passwordVisible }) {
                                            Text(if (passwordVisible) "Verbergen" else "Tonen")
                                        } },
                                        supportingText = { Text("Minimaal 8 tekens, met een letter en een cijfer") },
                                        modifier = Modifier.fillMaxWidth(), enabled = !busy)
                                    Text("Je mag mm.tenhaaf.nu of 192.168.72.23:8787 invullen; http(s):// wordt automatisch toegevoegd. Je wachtwoord wordt niet opgeslagen.",
                                        style = MaterialTheme.typography.bodySmall)
                                    Button(onClick = { load(withPassword = password.isNotBlank() || token.isBlank()) },
                                        enabled = !busy && (token.isNotBlank() || validPassword(password))) {
                                        Text("Opslaan en verbinden")
                                    }
                                }
                            }
                        }
                        error?.let { detail -> item { Text(detail, color = palette.red) } }
                        data?.let { snapshot ->
                            item {
                                Text(if (snapshot.optBoolean("docker")) "● NUC verbonden · Docker online"
                                    else "● NUC verbonden · Docker niet bereikbaar",
                                    color = if (snapshot.optBoolean("docker")) accent else palette.red)
                                Text("Momentopname · " + java.text.DateFormat.getTimeInstance().format(
                                    java.util.Date(snapshot.optLong("timestamp") * 1000)),
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            snapshot.optJSONObject("maintenance")?.takeIf { it.optBoolean("active") }?.let { state ->
                                item {
                                    Card(colors = CardDefaults.cardColors(
                                        containerColor = accent.copy(alpha = 0.14f))) {
                                        Column(Modifier.fillMaxWidth().padding(14.dp)) {
                                            Text("Onderhoudsmodus actief", fontWeight = FontWeight.Bold, color = accent)
                                            Text("Geen automatische controles of meldingen tot ${dateTime(state.optLong("until"))}",
                                                style = MaterialTheme.typography.bodySmall)
                                        }
                                    }
                                }
                            }
                            if (showStorage) {
                                item { Text("OPSLAG", fontWeight = FontWeight.Bold) }
                                objects(snapshot, "storage").forEach { disk ->
                                    item {
                                        Card(Modifier.fillMaxWidth()) {
                                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                                Text(disk.getString("name"), fontWeight = FontWeight.Bold)
                                                if (disk.optBoolean("online")) {
                                                    val free = disk.optDouble("free")
                                                    val total = disk.optDouble("total")
                                                    val freeRatio = free / total
                                                    Text(space(free) + " vrij van " + space(total))
                                                    LinearProgressIndicator(
                                                        progress = { (1 - freeRatio).toFloat().coerceIn(0f, 1f) },
                                                        color = when {
                                                            freeRatio <= 0.1 -> palette.red
                                                            freeRatio <= 0.2 -> palette.yellow
                                                            else -> palette.green
                                                        },
                                                        modifier = Modifier.fillMaxWidth())
                                                } else Text("Niet bereikbaar of niet aangekoppeld", color = palette.red)
                                            }
                                        }
                                    }
                                }
                            }
                            item {
                                Text("CONTAINERS", fontWeight = FontWeight.Bold)
                                Text("Groen: actief · Geel: update · Rood: aandacht",
                                    style = MaterialTheme.typography.bodySmall)
                                val updateCount = objects(snapshot, "containers").count {
                                    it.optJSONObject("update")?.optBoolean("available") == true
                                }
                                if (updateCount > 0) {
                                    Spacer(Modifier.height(8.dp))
                                    Button(onClick = { confirmUpdateAll = true }, enabled = !busy,
                                        modifier = Modifier.fillMaxWidth()) {
                                        Text(if (updateCount == 1) "1 update uitvoeren"
                                            else "Alle $updateCount updates uitvoeren")
                                    }
                                }
                            }
                            item {
                                Card(Modifier.fillMaxWidth()) {
                                    Column {
                                        val listedContainers = when (sortMode) {
                                            "za" -> objects(snapshot, "containers").sortedByDescending { it.getString("name").lowercase() }
                                            "nuc" -> objects(snapshot, "containers")
                                            else -> objects(snapshot, "containers").sortedBy { it.getString("name").lowercase() }
                                        }
                                        listedContainers
                                            .forEach { container ->
                                            val name = container.getString("name")
                                            Row(
                                                Modifier.fillMaxWidth().padding(start = 12.dp, end = 4.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                if (showStatus) {
                                                    Column(Modifier.weight(1f).padding(vertical = 8.dp)) {
                                                        Text(name, maxLines = 1, overflow = TextOverflow.Ellipsis,
                                                            fontWeight = FontWeight.SemiBold)
                                                        Text(statusLabel(container), style = MaterialTheme.typography.bodySmall)
                                                    }
                                                } else {
                                                    Text(name, modifier = Modifier.weight(1f).padding(vertical = 8.dp),
                                                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                                                        fontWeight = FontWeight.SemiBold)
                                                }
                                                if (automaticUpdates) {
                                                    Spacer(Modifier.width(28.dp))
                                                    StatusLamp("Groen", palette.green,
                                                        container.optString("color") == "green")
                                                } else {
                                                    StatusLamp("Groen", palette.green,
                                                        container.optString("color") == "green")
                                                    StatusLamp("Geel", palette.yellow,
                                                        container.optString("color") == "yellow")
                                                }
                                                StatusLamp("Rood", palette.red, container.optString("color") !in listOf("green", "yellow"))
                                                IconButton(
                                                    onClick = { details = container },
                                                    enabled = !busy,
                                                    modifier = Modifier.size(42.dp).semantics {
                                                        contentDescription = "Informatie over $name"
                                                    }
                                                ) { Text("ⓘ", style = MaterialTheme.typography.titleLarge, color = accent) }
                                                IconButton(
                                                    onClick = { maintenance = container },
                                                    enabled = !busy,
                                                    modifier = Modifier.size(42.dp).semantics {
                                                        contentDescription = "Onderhoud van $name"
                                                    }
                                                ) { Text("⚙", style = MaterialTheme.typography.headlineSmall) }
                                            }
                                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.35f))
                                        }
                                        if (objects(snapshot, "containers").isEmpty()) {
                                            Text("Geen containers beschikbaar", Modifier.padding(16.dp))
                                        }
                                    }
                                }
                            }
                        }
                        }
                    }
                    details?.let { container ->
                        val update = container.optJSONObject("update")
                        val ports = container.optJSONArray("ports")?.let { array ->
                            (0 until array.length()).joinToString(", ") { array.optString(it) }
                        }.orEmpty()
                        AlertDialog(
                            onDismissRequest = { details = null },
                            title = { Text("Info · ${container.optString("name")}") },
                            text = {
                                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    item { DetailLine("Status", statusLabel(container)) }
                                    item { DetailLine("Image", container.optString("image", "Onbekend")) }
                                    item { DetailLine("Actief sinds", startedLabel(container.optString("startedAt"))) }
                                    item { DetailLine("Herstarts", container.optInt("restartCount").toString()) }
                                    item { DetailLine("Poorten", ports.ifBlank { "Geen openbare poorten" }) }
                                    item { DetailLine("Container-ID", container.optString("id", "Onbekend")) }
                                    if (container.optString("composeProject").isNotBlank())
                                        item { DetailLine("Compose", container.optString("composeProject") + " · " +
                                            container.optString("composeService")) }
                                    item { DetailLine("Update", when {
                                        update == null || update.isNull("available") -> "Nog niet gecontroleerd"
                                        update.optBoolean("available") -> "Beschikbaar"
                                        else -> "Actueel"
                                    }) }
                                    if (update?.optLong("checkedAt", 0) ?: 0 > 0)
                                        item { DetailLine("Laatst gecontroleerd", dateTime(update!!.optLong("checkedAt"))) }
                                }
                            },
                            confirmButton = { TextButton(onClick = { details = null }) { Text("Sluiten") } }
                        )
                    }
                    maintenance?.let { container ->
                        val name = container.getString("name")
                        val state = container.optString("state")
                        AlertDialog(
                            onDismissRequest = { maintenance = null },
                            title = { Text("Onderhoud · $name") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(statusLabel(container))
                                    val update = container.optJSONObject("update")
                                    Text(when {
                                        update == null || update.isNull("available") -> "Updatecontrole nog niet beschikbaar"
                                        update.optBoolean("available") -> "Update beschikbaar"
                                        else -> "Geen update bij laatste controle"
                                    })
                                    listOf(
                                        "start" to "Starten",
                                        "stop" to "Stoppen",
                                        "restart" to "Herstarten",
                                        "check-update" to "Update controleren",
                                        "update" to "Updaten",
                                        "logs" to "Logs bekijken"
                                    ).forEach { (operation, label) ->
                                        val allowed = when (operation) {
                                            "start" -> state in listOf("exited", "created")
                                            "stop", "restart" -> state == "running"
                                            "update" -> update?.optBoolean("available") == true
                                            else -> true
                                        }
                                        TextButton(
                                            enabled = !busy && allowed,
                                            modifier = Modifier.fillMaxWidth(),
                                            onClick = {
                                                maintenance = null
                                                if (operation in listOf("logs", "check-update")) execute(name, operation)
                                                else pending = name to operation
                                            }
                                        ) { Text(label) }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { maintenance = null }) { Text("Sluiten") }
                            }
                        )
                    }
                    pending?.let { (name, operation) ->
                        AlertDialog(
                            onDismissRequest = { pending = null },
                            title = { Text("$name: $operation") },
                            text = { Text(if (operation == "update")
                                "De nieuwe image wordt opgehaald en deze container wordt opnieuw aangemaakt. Dit onderbreekt de service."
                                else "Deze actie wordt op je NUC uitgevoerd.") },
                            confirmButton = { TextButton(onClick = { pending = null; execute(name, operation) }) { Text("Uitvoeren") } },
                            dismissButton = { TextButton(onClick = { pending = null }) { Text("Annuleren") } }
                        )
                    }
                    if (confirmUpdateAll) {
                        val count = data?.let { snapshot -> objects(snapshot, "containers").count {
                            it.optJSONObject("update")?.optBoolean("available") == true
                        }} ?: 0
                        AlertDialog(
                            onDismissRequest = { confirmUpdateAll = false },
                            title = { Text("Alles bijwerken?") },
                            text = { Text("$count beschikbare ${if (count == 1) "update wordt" else "updates worden"} achter elkaar uitgevoerd. Diensten kunnen kort onderbroken worden.") },
                            confirmButton = {
                                TextButton(onClick = { confirmUpdateAll = false; updateAll() }) { Text("Bijwerken") }
                            },
                            dismissButton = {
                                TextButton(onClick = { confirmUpdateAll = false }) { Text("Annuleren") }
                            }
                        )
                    }
                    logs?.let { value ->
                        AlertDialog(onDismissRequest = { logs = null }, title = { Text("Laatste logregels") },
                            text = { LazyColumn { item { Text(value, style = MaterialTheme.typography.bodySmall) } } },
                            confirmButton = { TextButton(onClick = { logs = null }) { Text("Sluiten") } })
                    }
                    activityLog?.let { value ->
                        AlertDialog(onDismissRequest = { activityLog = null }, title = { Text("Activiteitenlogboek") },
                            text = { LazyColumn { item { Text(value, style = MaterialTheme.typography.bodySmall) } } },
                            confirmButton = {
                                Row {
                                    if (activityHasMore) TextButton(onClick = { loadActivity(activityOffset) }, enabled = !busy) {
                                        Text("Oudere activiteiten laden")
                                    }
                                    TextButton(onClick = { activityLog = null }) { Text("Sluiten") }
                                }
                            })
                    }
                    if (showAppUpdate) {
                        appUpdate?.let { release ->
                            AlertDialog(
                                onDismissRequest = { showAppUpdate = false },
                                title = { Text("App-update beschikbaar") },
                                text = { Text("Media Monster " + release.optString("versionName") + " staat klaar.") },
                                confirmButton = {
                                    TextButton(onClick = {
                                        showAppUpdate = false
                                        downloadAppUpdate(release)
                                    }) { Text("Update downloaden") }
                                },
                                dismissButton = {
                                    TextButton(onClick = { showAppUpdate = false }) { Text("Later") }
                                }
                            )
                        }
                    }
                    if (showMaintenancePicker) {
                        val active = data?.optJSONObject("maintenance")?.optBoolean("active") == true
                        AlertDialog(
                            onDismissRequest = { showMaintenancePicker = false; configuration = true },
                            title = { Text("Onderhoudsmodus") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("Tijdens deze periode voert Media Monster geen automatische controles uit en verstuurt het geen statusmeldingen.",
                                        style = MaterialTheme.typography.bodySmall)
                                    listOf(
                                        30 to "30 minuten",
                                        60 to "1 uur",
                                        120 to "2 uur",
                                        240 to "4 uur",
                                        480 to "8 uur",
                                        1440 to "24 uur",
                                        10080 to "7 dagen"
                                    ).forEach { (minutes, label) ->
                                        OutlinedButton(onClick = {
                                            showMaintenancePicker = false
                                            setMaintenance(minutes)
                                        }, modifier = Modifier.fillMaxWidth()) { Text(label) }
                                    }
                                    if (active) {
                                        TextButton(onClick = {
                                            showMaintenancePicker = false
                                            setMaintenance(0)
                                        }, modifier = Modifier.fillMaxWidth()) { Text("Nu uitschakelen") }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { showMaintenancePicker = false; configuration = true }) {
                                    Text("Terug")
                                }
                            }
                        )
                    }
                    if (showColorPicker) {
                        AlertDialog(
                            onDismissRequest = { showColorPicker = false; configuration = true },
                            title = { Text("Kleur wijzigen") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    listOf(
                                        "green" to "Groen (standaard)",
                                        "blue" to "Blauw",
                                        "purple" to "Paars",
                                        "orange" to "Oranje",
                                        "pink" to "Roze",
                                        "cyan" to "Turquoise"
                                    ).forEach { (key, label) ->
                                        ChoiceRow(label, accentName == key) {
                                            accentName = key
                                            prefs.edit().putString("accent", key).apply()
                                        }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { showColorPicker = false; configuration = true }) { Text("Klaar") }
                            }
                        )
                    }
                    if (showLampPicker) {
                        AlertDialog(
                            onDismissRequest = { showLampPicker = false; configuration = true },
                            title = { Text("Statuslampen") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    listOf(
                                        "monster" to "Monster",
                                        "bright" to "Helder",
                                        "accessible" to "Kleurenblindvriendelijk"
                                    ).forEach { (key, label) ->
                                        ChoiceRow(label, paletteName == key) {
                                            paletteName = key
                                            prefs.edit().putString("palette", key).apply()
                                        }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { showLampPicker = false; configuration = true }) { Text("Klaar") }
                            }
                        )
                    }
                    if (showSortPicker) {
                        AlertDialog(
                            onDismissRequest = { showSortPicker = false; configuration = true },
                            title = { Text("Volgorde containers") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    listOf("az" to "A–Z", "za" to "Z–A", "nuc" to "NUC-bestand").forEach { (key, label) ->
                                        ChoiceRow(label, sortMode == key) {
                                            sortMode = key
                                            prefs.edit().putString("sortMode", key).apply()
                                        }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { showSortPicker = false; configuration = true }) { Text("Klaar") }
                            }
                        )
                    }
                    if (showPasswordEditor) {
                        AlertDialog(
                            onDismissRequest = { showPasswordEditor = false; configuration = true },
                            title = { Text("Wachtwoord wijzigen") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    OutlinedTextField(
                                        value = newPassword,
                                        onValueChange = { newPassword = it },
                                        label = { Text("Nieuw wachtwoord") },
                                        singleLine = true,
                                        visualTransformation = PasswordVisualTransformation(),
                                        supportingText = { Text("Minimaal 8 tekens, met een letter en een cijfer") },
                                        modifier = Modifier.fillMaxWidth(),
                                        enabled = !busy
                                    )
                                    passwordFeedback?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { saveLoginPassword() },
                                    enabled = !busy && validPassword(newPassword)) { Text("Opslaan") }
                            },
                            dismissButton = {
                                TextButton(onClick = { showPasswordEditor = false; configuration = true }) { Text("Terug") }
                            }
                        )
                    }
                    if (configuration) {
                        val appVersion = packageManager.getPackageInfo(packageName, 0).versionName ?: "1.0.13"
                        val pushRegistered = prefs.getLong("lastPushRegistration", 0L) > 0L
                        val maintenanceState = data?.optJSONObject("maintenance")
                        AlertDialog(
                            onDismissRequest = { configuration = false },
                            title = { Text("Instellingen") },
                            text = {
                                LazyColumn(
                                    modifier = Modifier.heightIn(max = 620.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    item { Text("WEERGAVE", fontWeight = FontWeight.Bold, color = accent) }
                                    item {
                                        SettingSwitch("AMOLED-zwart", amoled) {
                                            amoled = it; prefs.edit().putBoolean("amoled", it).apply()
                                        }
                                    }
                                    item {
                                        SettingSwitch("Opslag tonen", showStorage) {
                                            showStorage = it; prefs.edit().putBoolean("showStorage", it).apply()
                                        }
                                    }
                                    item {
                                        SettingSwitch("Status onder containernaam", showStatus) {
                                            showStatus = it; prefs.edit().putBoolean("showStatus", it).apply()
                                        }
                                    }
                                    item {
                                        OutlinedButton(onClick = {
                                            configuration = false
                                            showColorPicker = true
                                        }, modifier = Modifier.fillMaxWidth()) {
                                            Text("Kleur wijzigen")
                                        }
                                    }
                                    item {
                                        OutlinedButton(onClick = {
                                            configuration = false
                                            showLampPicker = true
                                        }, modifier = Modifier.fillMaxWidth()) {
                                            Text("Statuslampen wijzigen")
                                        }
                                    }
                                    item {
                                        OutlinedButton(onClick = {
                                            configuration = false
                                            showSortPicker = true
                                        }, modifier = Modifier.fillMaxWidth()) {
                                            Text("Volgorde containers")
                                        }
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("ONDERHOUDSMODUS", fontWeight = FontWeight.Bold, color = accent) }
                                    item {
                                        Text(if (maintenanceState?.optBoolean("active") == true)
                                            "Actief tot ${dateTime(maintenanceState.optLong("until"))}"
                                            else "Niet actief", style = MaterialTheme.typography.bodySmall)
                                    }
                                    item {
                                        OutlinedButton(onClick = {
                                            configuration = false
                                            showMaintenancePicker = true
                                        }, enabled = !busy && token.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                                            Text("Onderhoudsmodus instellen")
                                        }
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("AUTOMATISERING", fontWeight = FontWeight.Bold, color = accent) }
                                    item {
                                        SettingSwitch("Automatisch herstarten", automaticRecovery) {
                                            setAutomaticRecovery(it)
                                        }
                                    }
                                    item {
                                        Text("Herstart onverwachte stops. Na vijf crashes in tien minuten blijft een container uit.",
                                            style = MaterialTheme.typography.bodySmall)
                                    }
                                    item {
                                        SettingSwitch("Automatisch bijwerken", automaticUpdates) {
                                            setAutomaticUpdates(it)
                                        }
                                    }
                                    item {
                                        Text(if (automaticUpdates)
                                            "De NUC werkt beschikbare containerupdates zelf bij."
                                        else
                                            "Updates krijgen een geel lampje en je werkt ze zelf bij.",
                                            style = MaterialTheme.typography.bodySmall)
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("MELDINGEN", fontWeight = FontWeight.Bold, color = accent) }
                                    item {
                                        SettingSwitch("Container gestopt", notifyStopped) {
                                            notifyStopped = it; saveNotifications(it, notifyUpdates, notifyAutomaticUpdates)
                                        }
                                    }
                                    item {
                                        SettingSwitch("Update beschikbaar", notifyUpdates, enabled = !automaticUpdates) {
                                            notifyUpdates = it; saveNotifications(notifyStopped, it, notifyAutomaticUpdates)
                                        }
                                    }
                                    item {
                                        SettingSwitch("Automatisch bijgewerkt", notifyAutomaticUpdates,
                                            enabled = automaticUpdates) {
                                            notifyAutomaticUpdates = it
                                            saveNotifications(notifyStopped, notifyUpdates, it)
                                        }
                                    }
                                    item {
                                        OutlinedButton(onClick = {
                                            val blocked = Monitoring.blockedReason(this@MainActivity)
                                            if (blocked != null) configFeedback = blocked
                                            else {
                                                configFeedback = "Testmelding wordt verzonden…"
                                                PushRegistration.test(this@MainActivity) { configFeedback = it }
                                            }
                                        }, modifier = Modifier.fillMaxWidth()) { Text("Test pushmelding") }
                                    }
                                    item {
                                        OutlinedButton(onClick = { openNotificationSettings() },
                                            modifier = Modifier.fillMaxWidth()) {
                                            Text("Android-meldingsrechten")
                                        }
                                    }
                                    configFeedback?.let { feedback ->
                                        item { Text(feedback, style = MaterialTheme.typography.bodySmall) }
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("ACTIVITEIT", fontWeight = FontWeight.Bold, color = accent) }
                                    item {
                                        OutlinedButton(onClick = { loadActivity() }, enabled = !busy,
                                            modifier = Modifier.fillMaxWidth()) { Text("Activiteitenlogboek") }
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("APP-UPDATE", fontWeight = FontWeight.Bold, color = accent) }
                                    item { Text("Geïnstalleerd: " + appVersion, style = MaterialTheme.typography.bodySmall) }
                                    item {
                                        OutlinedButton(onClick = { inspectAppUpdate(manual = true) }, enabled = !busy,
                                            modifier = Modifier.fillMaxWidth()) {
                                            Text("Controleren op update")
                                        }
                                    }
                                    appUpdate?.let { release ->
                                        item {
                                            OutlinedButton(onClick = { downloadAppUpdate(release) },
                                                modifier = Modifier.fillMaxWidth()) {
                                                Text("Versie " + release.optString("versionName") + " downloaden")
                                            }
                                        }
                                    }
                                    updateFeedback?.let { feedback ->
                                        item { Text(feedback, style = MaterialTheme.typography.bodySmall) }
                                    }
                                    item { HorizontalDivider() }
                                    item { Text("DIAGNOSE", fontWeight = FontWeight.Bold, color = accent) }
                                    item { Text("App: $appVersion", style = MaterialTheme.typography.bodySmall) }
                                    item { Text("Docker: " + if (data?.optBoolean("docker") == true) "online" else "niet verbonden", style = MaterialTheme.typography.bodySmall) }
                                    item { Text("Pushregistratie: " + if (pushRegistered) "actief" else "nog niet bevestigd", style = MaterialTheme.typography.bodySmall) }
                                    item { HorizontalDivider() }
                                    item { Text("VERBINDING EN ACCOUNT", fontWeight = FontWeight.Bold, color = accent) }
                                    item { Text(address, style = MaterialTheme.typography.bodySmall) }
                                    item {
                                        OutlinedButton(onClick = {
                                            newPassword = ""
                                            passwordFeedback = null
                                            configuration = false
                                            showPasswordEditor = true
                                        }, modifier = Modifier.fillMaxWidth()) {
                                            Text("Wachtwoord wijzigen")
                                        }
                                    }
                                    item {
                                        OutlinedButton(onClick = { configuration = false; settings = true },
                                            modifier = Modifier.fillMaxWidth()) {
                                            Text("Verbinding wijzigen")
                                        }
                                    }
                                    item {
                                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
                                            IconButton(onClick = {
                                                configuration = false
                                                showEasterEgg = true
                                            }) {
                                                Text("🥚", style = MaterialTheme.typography.titleLarge)
                                            }
                                        }
                                    }
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { configuration = false }) { Text("Sluiten") }
                            }
                        )
                    }
                    if (showEasterEgg) EasterEgg { showEasterEgg = false }
                }
                }
            }
        }
    }
}

@Composable
private fun EasterEgg(onDismiss: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var tiltX by remember { mutableStateOf(0f) }
    var tiltY by remember { mutableStateOf(0f) }
    var sick by remember { mutableStateOf(false) }
    DisposableEffect(context) {
        val manager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val listener = object : SensorEventListener {
            var sampleX = 0f
            var sampleY = 0f
            var sampleAt = 0L
            var wobbleStartedAt = 0L
            var lastWobbleAt = 0L
            override fun onSensorChanged(event: SensorEvent) {
                val x = event.values[0].coerceIn(-5f, 5f)
                val y = event.values[1].coerceIn(-5f, 5f)
                val now = SystemClock.elapsedRealtime()
                tiltX = x
                tiltY = y
                if (sampleAt == 0L) {
                    sampleX = x; sampleY = y; sampleAt = now
                    return
                }
                if (now - sampleAt >= 120L) {
                    val moved = abs(x - sampleX) + abs(y - sampleY) > 0.24f
                    sampleX = x; sampleY = y; sampleAt = now
                    if (moved) {
                        if (now - lastWobbleAt > 850L) wobbleStartedAt = now
                        lastWobbleAt = now
                        if (now - wobbleStartedAt >= 10_000L) sick = true
                    } else if (now - lastWobbleAt > 850L) {
                        wobbleStartedAt = 0L
                        sick = false
                    }
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
        }
        manager.registerListener(listener, manager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER),
            SensorManager.SENSOR_DELAY_GAME)
        onDispose { manager.unregisterListener(listener) }
    }
    Surface(Modifier.fillMaxSize().pointerInput(Unit) { detectTapGestures { onDismiss() } },
        color = MaterialTheme.colorScheme.background) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Box(Modifier.fillMaxWidth(0.88f).aspectRatio(1f), contentAlignment = Alignment.Center) {
                Image(painter = painterResource(R.drawable.ic_monster), contentDescription = "Media Monster",
                    modifier = Modifier.fillMaxSize())
                Row(Modifier.offset(x = 0.dp, y = (-54).dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    GooglyEye(tiltX, tiltY, green = sick)
                    GooglyEye(tiltX, tiltY, green = sick)
                }
            }
            Text("Tik om te sluiten", Modifier.align(Alignment.BottomCenter).padding(32.dp),
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.65f))
        }
    }
}

@Composable
private fun GooglyEye(x: Float, y: Float, green: Boolean) {
    val eyeColor by animateColorAsState(if (green) Color(0xFFC4E4AE) else Color.White, label = "eye color")
    val pupilColor by animateColorAsState(if (green) Color(0xFF3F6B43) else Color(0xFF15372F), label = "pupil color")
    Box(Modifier.size(40.dp).background(eyeColor, CircleShape), contentAlignment = Alignment.Center) {
        Box(Modifier.size(14.dp).offset(
            x = (x * -4f).coerceIn(-11f, 11f).dp,
            y = (y * 4f).coerceIn(-11f, 11f).dp
        )
            .background(pupilColor, CircleShape))
    }
}

@Composable
private fun MonsterTitle() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Image(painter = painterResource(R.drawable.ic_monster_m_green), contentDescription = null,
            modifier = Modifier.width(24.dp).height(31.dp))
        Text("EDIA", color = Green, style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Black)
        Spacer(Modifier.width(8.dp))
        Image(painter = painterResource(R.drawable.ic_monster_m_yellow), contentDescription = null,
            modifier = Modifier.width(24.dp).height(31.dp))
        Text("ONSTER", color = Yellow, style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Black)
    }
}

@Composable
private fun SettingSwitch(label: String, checked: Boolean, enabled: Boolean = true,
                          onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), color = if (enabled) LocalContentColor.current
            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f))
        Switch(checked = checked, onCheckedChange = onCheckedChange, enabled = enabled)
    }
}

@Composable
private fun ChoiceRow(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        RadioButton(selected = selected, onClick = onClick)
        TextButton(onClick = onClick) { Text(label) }
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun statusLabel(container: JSONObject): String {
    val state = container.optString("state")
    val health = container.optString("health")
    return when {
        state == "unknown" -> "Status onbekend"
        state in listOf("exited", "created") -> "Gestopt"
        health == "unhealthy" -> "Ongezond"
        health == "starting" -> "Start op"
        container.optString("color") == "yellow" -> "Update beschikbaar"
        state == "running" && health == "healthy" -> "Gezond"
        state == "running" -> "Actief"
        else -> state
    }
}

@Composable
private fun StatusLamp(label: String, tint: Color, lit: Boolean) {
    Box(
        Modifier.width(28.dp).height(48.dp).semantics {
            contentDescription = label + if (lit) ": aan" else ": uit"
        },
        contentAlignment = Alignment.Center
    ) {
        Box(
            Modifier.size(if (lit) 18.dp else 14.dp)
                .background(if (lit) tint else tint.copy(alpha = 0.12f), CircleShape)
                .border(if (lit) 2.dp else 1.dp,
                    if (lit) Color.White.copy(alpha = 0.7f) else tint.copy(alpha = 0.25f), CircleShape)
        )
    }
}

