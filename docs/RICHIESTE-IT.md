# Cosa serve dall'IT (e dal DBA) per il deploy

Elenco operativo da girare all'IT Camperio. Ogni voce dice **cosa serve**, **perché** e
**dove finisce**, così chi risponde non deve indovinare. I riferimenti A1/B1/B2 sono i
codici delle richieste nel repo di pianificazione.

Riferimenti tecnici: `docs/DEPLOY.md` (runbook), `docs/SECRETS.md` (canale di consegna).
**Consegna dei valori: mai per email** — Passwordstate, canale cifrato o di persona.

---

## 1 · Entra ID — app registration (richiesta B2)

L'autenticazione è delegata a Entra tramite `oauth2-proxy`. Serve un'app registration
dedicata alla piattaforma.

### Valori da consegnare

| Valore | Dove finisce nella configurazione |
|---|---|
| Tenant ID | `OAUTH2_PROXY_OIDC_ISSUER_URL=https://login.microsoftonline.com/<TENANT_ID>/v2.0` |
| Client ID | `OAUTH2_PROXY_CLIENT_ID` |
| Client secret | `OAUTH2_PROXY_CLIENT_SECRET` (+ **data di scadenza** e titolare del rinnovo) |

### Configurazioni da fare nell'app registration

Senza queste due, i valori qui sopra non bastano.

1. **Redirect URI** registrato, esattamente:
   `https://app-ai.camperiosim.com/oauth2/callback`
   Una differenza anche minima (schema, slash finale) fa fallire il login *dopo*
   l'autenticazione, con un errore poco leggibile.

2. **Assegnazione utenti**, in Applicazioni aziendali → app-ai: Proprietà →
   "Assegnazione obbligatoria" = **Sì**, poi Utenti e gruppi → aggiungere solo gli
   utenti che devono entrare.
   È il punto che si dimentica più spesso. L'autorizzazione della piattaforma è per
   utente assegnato, non per dominio email: senza "Assegnazione obbligatoria" = Sì,
   **chiunque** nel tenant entra dopo il login. Nota: l'assegnazione a **gruppi**
   richiede Azure AD Premium P1 (non disponibile su questo tenant) — si assegnano
   singoli utenti. Per il collaudo servono due utenti noti: uno **assegnato** (deve
   entrare) e uno **non assegnato** (Entra deve rifiutarlo già in fase di login, prima
   di tornare all'app). La prova con l'utente non assegnato è una voce obbligatoria
   della checklist di esposizione.

---

## 2 · Certificato TLS per `app-ai.camperiosim.com` (richiesta B1)

Certificato AD CS interno, usato da nginx: è l'unico punto di terminazione TLS.

- Formato preferito: **`.pfx`**, con la **password consegnata separatamente**.
- Deve includere la **catena intermedia**, non solo il certificato foglia. Verifica
  lato nostro: `grep -c "BEGIN CERTIFICATE" fullchain.pem` deve dare **almeno 2**; se
  dà 1 manca l'intermedio e i client mostreranno errori di catena.
- Servono **data di scadenza** e **titolare del rinnovo**.

Destinazione: `/etc/camperio/tls/fullchain.pem` e `/etc/camperio/tls/privkey.pem`
(chiave a 600).

---

## 3 · DNS

Record **A**: `app-ai.camperiosim.com` → indirizzo IP della VM.

**Stato attuale: il record non esiste.** Verificato da client in VPN: gli altri host
interni risolvono regolarmente (es. `selmora01.ad.camperiosim.com`), mentre
`app-ai.camperiosim.com` non risolve, né in varianti sotto la zona `ad.camperiosim.com`.

Finché manca si può lavorare per indirizzo IP, ma non si può esporre: il nome è quello
su cui è intestato il certificato e su cui è impostato il redirect di Entra.

---

## 4 · Aperture di rete

### In ingresso verso la VM

| Porta | Da | Perché |
|---|---|---|
| 443/tcp | reti dei client VPN | è l'unica porta esposta della piattaforma |

Nessun'altra porta va aperta: l'app e oauth2-proxy non sono raggiungibili dall'esterno
per costruzione.

### In uscita dalla VM

| Destinazione | Porta | Perché |
|---|---|---|
| `selmora01.ad.camperiosim.com` | 1521/tcp | lettura dati Oracle; senza, l'app risponde 503 |
| `login.microsoftonline.com` | 443/tcp | autenticazione Entra; senza, nessuno entra |
| `www.ishares.com` | 443/tcp | job schedulato del giovedì: scarica 9 CSV holdings ETF |
| PyPI e Docker Hub | 443/tcp | costruzione dell'immagine e test di collaudo |

---

## 5 · Accesso alla VM

- Utenza di servizio non-root sulla VM, **nel gruppo `docker`** (permette di operare lo
  stack senza `sudo`; è anche il motivo dei permessi `root:docker 640` sul file dei
  segreti).
- Accesso SSH per Bernardino, preferibilmente a chiave pubblica.
- **Impronta della chiave host SSH**, per poterla confrontare alla prima connessione
  invece di accettarla alla cieca.

---

## 6 · Dal DBA (richiesta A1)

- Utenza Oracle di servizio in **sola lettura** → `ORA_USER`, `ORA_PWD`.
- **Service name** del database, per completare
  `ORA_DSN=selmora01.ad.camperiosim.com:1521/<service_name>`.

---

## Non serve chiederli: li mette Bernardino

- `OAUTH2_PROXY_COOKIE_SECRET` — generato sul posto (`openssl rand -base64 32`).
- `ANTHROPIC_API_KEY` — dalla console Anthropic.
- Deploy key SSH read-only per GitHub — generata sulla VM, una per macchina.
