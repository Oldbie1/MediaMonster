# Installatie en gebruik

## Android
Open de map android in Android Studio, of bouw met JDK 17 en Android SDK 36:
    gradlew.bat assembleDebug

De ontwikkelbuild staat na compilatie in app/build/outputs/apk/debug/app-debug.apk.
Installeer die APK op een Android-telefoon (Android 8 of nieuwer).

## API op de NUC
De API is nog niet als permanente service geïnstalleerd. De tests gebruiken /tmp/mediamonster-dev.
Gebruik Python 3.11+ onder dezelfde Linux/WSL-gebruiker die Docker mag bedienen.
Bewaar server.py bijvoorbeeld in /home/marco/mediamonster.
Genereer een token met:
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
Stel dit in via MM_TOKEN en start:
    python3 server.py

Standaard luistert de API uitsluitend op 127.0.0.1:8787. Kies MM_BIND voor een lokaal/Tailscale-adres dat
daadwerkelijk op de WSL-host bestaat, of gebruik een eigen HTTPS/Tailscale-proxy naar localhost.
Een Windows-Tailscale-adres is niet automatisch een bindbaar WSL-adres.
De netwerkpublicatie moet nog op de werkelijke Tailscale/WSL-inrichting worden getest.
Zet deze beheer-API niet via port-forwarding open op internet.

Vul in de app het API-adres en hetzelfde token in. Het adres wordt onthouden; het token alleen tijdens de sessie.
HTTP is beschikbaar voor het eigen LAN/Tailscale. Gebruik HTTPS als transport buiten die vertrouwde omgeving.

## Gedrag
- Vernieuwen haalt een nieuwe momentopname op; geen achtergrondmeldingen.
- Containers zonder healthcheck tonen "Actief".
- Controleer update vergelijkt de registry-image met de draaiende/lokaal aanwezige image zonder pull.
- Onbereikbare registry geeft onbekende updatestatus.
- Update haalt via de bestaande Compose-configuratie de image op en maakt alleen de gekozen service opnieuw aan.
- Een mislukte update wordt gemeld; automatische rollback is nog niet ingebouwd.
- Containeracties zijn globaal geserialiseerd.
- De API heeft de Docker-rechten van de uitvoerende gebruiker. Het token geeft toegang tot de toegestane containeracties.
- De backend start of stopt niets uit zichzelf.

## Verificatie
    cd backend
    python3 -m unittest -v

Live status is alleen-lezen getest op de NUC. Start/stop/update zijn nog niet op productiecontainers getest.
Een test op de telefoon en permanente API-installatie zijn nog nodig voordat dit dagelijks gebruikt kan worden.

## Bouwreferenties
- https://developer.android.com/build/releases/gradle-plugin
- https://developer.android.com/develop/ui/compose/bom
