#!/usr/bin/env bash
# Construye el front (repo hermano CALCULADORA_FLUJOS_COMERCIALES = la shell
# Geopolitikapp) y copia el build a web/, SIN los tiles (que viven en
# Cloudflare R2). web/ se versiona en este repo para que Railway lo sirva.
# Uso: ./deploy_web.sh   (luego: git add web && git commit && git push)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FRONT="$(cd "$HERE/../CALCULADORA_FLUJOS_COMERCIALES" && pwd)"
WEB="$HERE/web"

echo "1/3 build del front en $FRONT"
( cd "$FRONT" && npm run build )

echo "2/3 regenerando $WEB"
rm -rf "$WEB"
mkdir -p "$WEB/assets"

echo "3/3 copiando build sin la carpeta tiles (esos van a R2)"
cp "$FRONT/dist/index.html" "$WEB/index.html"
cp -R "$FRONT/dist/assets/." "$WEB/assets/"
if [ -f "$FRONT/dist/favicon.svg" ]; then
  cp "$FRONT/dist/favicon.svg" "$WEB/favicon.svg"
fi

echo "OK web listo:"
ls -1 "$WEB"
