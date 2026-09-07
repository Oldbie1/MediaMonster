# Media Monster 0.4.0

- Firebase Cloud Messaging is aan de Android-app gekoppeld voor meldingen via internet, ook zonder Tailscale.
- De app registreert automatisch het toestel en de twee meldingsvoorkeuren bij de Media Monster-API.
- De lokale controle om de 15 minuten blijft als reserve actief.
- De NUC controleert iedere 30 seconden op nieuwe containerstoringen en gebruikt de bestaande updatecontrole.
- Een melding wordt eenmaal verstuurd wanneer een storing of update ontstaat. Na herstel kan een volgende gebeurtenis opnieuw worden gemeld.
- De pushregistratie is beschermd met hetzelfde API-token als de rest van de app.

Voor het werkelijk verzenden is op de NUC nog een Firebase-serviceaccountbestand nodig op:

`/home/marco/mediamonster/firebase-service-account.json`

Het serviceaccountbestand bevat een geheime sleutel en hoort niet in deze projectmap of in Git.
