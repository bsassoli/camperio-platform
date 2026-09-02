#!/usr/bin/env bash
# CA interna provvisoria per app-ai.camperiosim.com (in attesa del certificato AD CS).
#
# Produce, negli stessi percorsi che nginx.conf gia' legge:
#   $TLS_DIR/fullchain.pem   certificato server + CA
#   $TLS_DIR/privkey.pem     chiave privata del server (600)
#   $TLS_DIR/ca.crt          certificato della CA: e' il file da installare sui client
#   $TLS_DIR/ca/             chiave e certificato della CA (la chiave resta solo qui)
#
# Idempotente: se la CA esiste la riusa e riemette solo il certificato server
# (e' anche il modo per rinnovarlo alla scadenza). Quando arriva il certificato
# AD CS basta sovrascrivere fullchain.pem e privkey.pem e ricaricare nginx.
#
# Uso (sulla VM):  sudo deploy/tls/genera-ca-interna.sh
# Variabili:       TLS_DIR (default /etc/camperio/tls), FQDN (default app-ai.camperiosim.com)
set -euo pipefail

TLS_DIR="${TLS_DIR:-/etc/camperio/tls}"
FQDN="${FQDN:-app-ai.camperiosim.com}"
CA_DIR="$TLS_DIR/ca"
CA_GIORNI=1825   # 5 anni
SRV_GIORNI=365   # 1 anno: rilanciare lo script prima della scadenza

umask 077
mkdir -p "$CA_DIR"

if [[ ! -f "$CA_DIR/ca.key" ]]; then
  echo ">> creo la CA interna in $CA_DIR"
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout "$CA_DIR/ca.key" -out "$CA_DIR/ca.crt" -days "$CA_GIORNI" \
    -subj "/O=Camperio SIM/CN=Camperio CA interna" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1
else
  echo ">> CA gia' presente in $CA_DIR: la riuso"
fi

echo ">> emetto il certificato server per $FQDN"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout "$TMP/privkey.pem" -out "$TMP/server.csr" -subj "/CN=$FQDN" >/dev/null 2>&1
cat > "$TMP/ext.cnf" <<EXT
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$FQDN
EXT
openssl x509 -req -in "$TMP/server.csr" -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" \
  -CAcreateserial -days "$SRV_GIORNI" -extfile "$TMP/ext.cnf" -out "$TMP/server.crt" >/dev/null 2>&1

# foglia + CA: nginx serve la catena completa, come farebbe con AD CS
cat "$TMP/server.crt" "$CA_DIR/ca.crt" > "$TLS_DIR/fullchain.pem"
install -m 600 "$TMP/privkey.pem" "$TLS_DIR/privkey.pem"
install -m 644 "$CA_DIR/ca.crt" "$TLS_DIR/ca.crt"
chmod 644 "$TLS_DIR/fullchain.pem"

echo ">> controllo della catena"
openssl verify -CAfile "$CA_DIR/ca.crt" "$TLS_DIR/fullchain.pem"

cat <<MSG

Fatto. File scritti in $TLS_DIR:
  fullchain.pem  privkey.pem  ca.crt

Scadenza del certificato server:
  $(openssl x509 -in "$TLS_DIR/fullchain.pem" -noout -enddate)

Da distribuire sui client (IT via GPO, o import manuale nei browser):
  scp <utente>@$FQDN:$TLS_DIR/ca.crt .
Finche' la CA non e' installata sul client il browser rifiuta il sito
(HSTS non consente di proseguire comunque).
MSG
