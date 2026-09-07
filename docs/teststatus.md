# Bouw- en teststatus — 5 september 2026

Eerste ontwikkelversie 0.1.0.
- APK: releases/MediaMonster-0.1.0-debug.apk (9.857.035 bytes).
- SHA256: 5FEC43F9D5717ED844A1F61496EBA6984997D62DB1D831D7F651707F7D00DA08
- Gradle assembleDebug: geslaagd.
- Gradle lintDebug: geslaagd.
- apksigner verify: geslaagd.
- Backend: 12 tests geslaagd, inclusief HTTP-authenticatie en geweigerde containeracties.
- Live alleen-lezen: 12 containers en C:/DS224/DS716 correct uitgelezen.
- Live registrycontrole Sonarr: update beschikbaar; gestopte container blijft rood.
- Geen productiecontainers gestart, gestopt of bijgewerkt.

Bouw: JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin 2.2.21, Compose BOM 2025.08.01, compile/target SDK 36.
De aanvankelijk gekozen Compose BOM 2026.08.00 vereiste SDK 37/AGP 9.1.
Daarom gebruikt deze eerste build de oudere compatibele BOM.

Nog open voor dagelijks gebruik:
- API permanent installeren en LAN/Tailscale/WSL-routing verifiëren.
- App op echte telefoon testen, inclusief schermindeling en netwerkfouten.
- Start/stop/update end-to-end testen op een geschikte testcontainer.
- Token veilig persistent bewaren; nu alleen in geheugen.
- Achtergrondmeldingen en automatische verversing ontbreken.
- Bij een updatefout volgt een melding; automatische rollback ontbreekt.

Tijdelijke bouwtools en build-cache: %TEMP%/mediamonster-build.
Tijdelijke API-tests op NUC: /tmp/mediamonster-dev (geen permanente service).
