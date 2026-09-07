# Versie 0.3.0

## Intern netwerk
API bereikbaar op http://192.168.72.23:8787 met het bestaande token.
Windows portproxy luistert alleen op 192.168.72.23 en stuurt door naar localhost:8787.
Firewallregel Media Monster API LAN: Private, TCP 8787, bron 192.168.72.0/24.
Geen wijziging van Docker-poortkoppelingen.
LAN-test vanaf pc: zonder token HTTP 401; met token twaalf containers.
Tailscale-adres blijft http://100.108.14.95:8787.

## Meldingen
Onder Verbinding zijn twee schakelaars toegevoegd: gestopt/ongezond en update beschikbaar.
Android-toestemming vereist. WorkManager controleert circa iedere vijftien minuten; Android kan dit uitstellen.
Per container en soort melding wordt alleen de overgang naar een probleem gemeld. Eerste waargenomen probleem meldt ook.
Herstel wist de melding en maakt een volgende melding mogelijk. Onbekende updatestatus wist de eerdere toestand niet.
Bij netwerkfouten wordt opnieuw geprobeerd, zonder ten onrechte containers als gestopt te melden.
Het opgeslagen API-adres wordt gebruikt: met een LAN-adres werkt monitoring alleen op het thuisnetwerk (of via een geschikte VPN-route).
Voor buitenshuis: Tailscale-adres gebruiken en Tailscale ingeschakeld houden.
Token wordt AES-GCM-versleuteld opgeslagen met een sleutel in Android Keystore; nooit in WorkManager-invoer.
APK-installatie over de vorige versie behoudt de instellingen. Eén keer opnieuw verbinden slaat het token op.

## Icoon
Adaptief groen-gouden MM-monogram op donker vlak met monsterhoorntjes; eigen monochroom meldingsicoon.

## Verificatie
assembleDebug, lintDebug en APK-handtekeningcontrole geslaagd.
LAN-authenticatie live gecontroleerd.
Periodieke aflevering van Android-meldingen en het launcher-icoon moeten nog op het fysieke toestel worden gecontroleerd.
Documentatie planning: https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work
