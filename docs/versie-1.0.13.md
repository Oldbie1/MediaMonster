# Media Monster 1.0.13

- De voortgangsbalk staat onder het volledige kopblok.
- Omlaag vegen vernieuwt de status en controleert alle containers op updates.
- Tijdens de controle verschijnt een voortgangsstatus; daarna blijft de uitslag vijf seconden zichtbaar.

Validatie: Android-build, unit-testtaak en lint succesvol.

## Backendcorrecties na 1.0.13
- Achtergrondupdatecontrole loopt ook als automatisch herstarten uit staat.
- Dubbele recoverydeclaraties en `/v1/recovery/settings`-routes opgeschoond.
- Standaardopslag van NUC 11 is `/`, gelijk aan `install-linux.sh`.

