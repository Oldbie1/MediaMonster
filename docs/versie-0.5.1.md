# Media Monster 0.5.1

## Inloggen

- Een serveradres zonder protocol wordt automatisch aangevuld.
- Lokale adressen, zoals `192.168.72.23:8787`, gebruiken automatisch `http://`.
- Publieke domeinen, zoals `mm.tenhaaf.nu`, gebruiken automatisch `https://`.
- Het inlogscherm vraagt om een wachtwoord in plaats van het technische API-token.
- Na een geslaagde login bewaart Android alleen de bestaande API-toegang versleuteld; het wachtwoord wordt niet opgeslagen.

## Wachtwoord beheren

Een ingelogde gebruiker kan via **Instellingen > Nieuw inlogwachtwoord** zelf een wachtwoord van minimaal tien tekens instellen of wijzigen. De server bewaart uitsluitend een PBKDF2-SHA256-hash met een willekeurige salt. Na vijf mislukte pogingen wordt inloggen vanaf dat adres vijf minuten geblokkeerd.

## Controle

- 35 server- en beveiligingstests slagen op de NUC.
- De Android-build slaagt.
- APK-versie: 0.5.1, versiecode 10.
- De APK gebruikt dezelfde handtekening als 0.5.0 en kan daarom als update worden geïnstalleerd.
