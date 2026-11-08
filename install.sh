#!/usr/bin/env bash
# Installe meteo-wallpaper pour l'utilisateur courant, sans sudo.
#
# Usage : ./install.sh [options]
#   --ville VILLE      ville passée à wttr.in (défaut : Lyon)
#   --dossier DIR      dossier des fonds d'écran (défaut : ~/Images/paint-weather)
#   --proxy URL        proxy HTTP(S), ex. http://proxy.exemple.fr:8080
#   --images DIR       copie des images existantes au lieu de les générer
#   --regenerer        régénère les images même si elles existent déjà
#   --force            réécrit la config existante
#   --desinstaller     retire le script, le timer et le générateur
#   -h, --help         affiche cette aide
#
# Sans option et dans un terminal, le script pose les questions.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/meteo-wallpaper"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/meteo-wallpaper"
CONF="$CONF_DIR/config"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m/!\\\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mErreur :\033[0m %s\n' "$*" >&2; exit 1; }
aide() { sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"; }

ville="" dossier="" proxy="" proxy_fixe=0 images="" regenerer=0 force=0 desinstaller=0
while (($#)); do
    case "$1" in
        --ville)        ville="$2"; shift 2 ;;
        --dossier)      dossier="$2"; shift 2 ;;
        --proxy)        proxy="$2"; proxy_fixe=1; shift 2 ;;
        --images)       images="$2"; shift 2 ;;
        --regenerer)    regenerer=1; shift ;;
        --force)        force=1; shift ;;
        --desinstaller) desinstaller=1; shift ;;
        -h|--help)      aide; exit 0 ;;
        *)              die "option inconnue : $1 (voir --help)" ;;
    esac
done

[[ $EUID -ne 0 ]] || die "lance ce script avec ton utilisateur, pas en root"

# ---------------------------------------------------------------- désinstallation
if ((desinstaller)); then
    info "Arrêt du timer"
    systemctl --user disable --now meteo-wallpaper.timer 2>/dev/null || true
    rm -f "$UNITS/meteo-wallpaper.service" "$UNITS/meteo-wallpaper.timer" "$BIN/meteo-wallpaper"
    rm -rf "$SHARE"
    systemctl --user daemon-reload 2>/dev/null || true
    info "Désinstallé. Config ($CONF_DIR) et images conservées : supprime-les à la main si besoin."
    exit 0
fi

# ---------------------------------------------------------------- prérequis
for f in meteo-wallpaper gen_wallpapers.py meteo-wallpaper.service meteo-wallpaper.timer; do
    [[ -f "$SRC/$f" ]] || die "fichier manquant à côté de install.sh : $f"
done
command -v gsettings >/dev/null || die "gsettings introuvable : ce script vise GNOME"
command -v curl >/dev/null || command -v wget >/dev/null || die "ni curl ni wget disponible"
systemctl --user show-environment >/dev/null 2>&1 || die "systemd utilisateur indisponible"

# ---------------------------------------------------------------- configuration
# Valeurs actuelles si une config existe déjà
CITY="Lyon" WALLPAPER_DIR="$HOME/Images/paint-weather" PROXY=""
# shellcheck source=/dev/null
[[ -f "$CONF" ]] && source "$CONF"

demander() {  # demander <question> <défaut> -> réponse
    local rep
    if [[ -t 0 ]]; then
        read -r -p "$1 [$2] : " rep
        echo "${rep:-$2}"
    else
        echo "$2"
    fi
}

ecrire_config=1
if [[ -f "$CONF" && $force -eq 0 && -z "$ville$dossier" && $proxy_fixe -eq 0 ]]; then
    info "Config existante conservée : $CONF (--force pour la refaire)"
    ecrire_config=0
else
    [[ -n "$ville" ]]   || ville="$(demander "Ville pour la météo" "$CITY")"
    [[ -n "$dossier" ]] || dossier="$(demander "Dossier des fonds d'écran" "$WALLPAPER_DIR")"
    ((proxy_fixe))      || proxy="$(demander "Proxy (vide si aucun)" "$PROXY")"
    CITY="$ville" WALLPAPER_DIR="${dossier/#\~/$HOME}" PROXY="$proxy"
fi

if ((ecrire_config)); then
    mkdir -p "$CONF_DIR"
    {
        echo "# Config de meteo-wallpaper, relue à chaque exécution"
        echo "# Ville passée à wttr.in (nom, code aéroport, coordonnées \"45.76,4.84\"...)"
        printf 'CITY=%q\n' "$CITY"
        echo "# Dossier des fonds d'écran (éviter les espaces dans le chemin)"
        printf 'WALLPAPER_DIR=%q\n' "$WALLPAPER_DIR"
        echo "# Proxy HTTP(S), vide si aucun"
        printf 'PROXY=%q\n' "$PROXY"
    } >"$CONF"
    info "Config écrite : $CONF"
fi

# ---------------------------------------------------------------- fichiers
info "Installation des fichiers"
install -Dm755 "$SRC/meteo-wallpaper" "$BIN/meteo-wallpaper"
install -Dm644 "$SRC/gen_wallpapers.py" "$SHARE/gen_wallpapers.py"
install -Dm644 "$SRC/meteo-wallpaper.service" "$UNITS/meteo-wallpaper.service"
install -Dm644 "$SRC/meteo-wallpaper.timer" "$UNITS/meteo-wallpaper.timer"

# ---------------------------------------------------------------- images
python_pillow() {  # affiche un interpréteur Python qui a Pillow, ou échoue
    if python3 -c 'import PIL' 2>/dev/null; then
        echo python3; return
    fi
    if [[ -x "$SHARE/venv/bin/python" ]] && "$SHARE/venv/bin/python" -c 'import PIL' 2>/dev/null; then
        echo "$SHARE/venv/bin/python"; return
    fi
    info "Installation de Pillow dans $SHARE/venv" >&2
    if python3 -m venv "$SHARE/venv" >&2 2>/dev/null \
       && "$SHARE/venv/bin/pip" install -q ${PROXY:+--proxy "$PROXY"} pillow >&2; then
        echo "$SHARE/venv/bin/python"; return
    fi
    rm -rf "$SHARE/venv"
    return 1
}

mkdir -p "$WALLPAPER_DIR"
shopt -s nullglob
existantes=("$WALLPAPER_DIR"/soleil-jour.*)
shopt -u nullglob

if [[ -n "$images" ]]; then
    [[ -d "$images" ]] || die "dossier d'images introuvable : $images"
    info "Copie des images depuis $images"
    # nullglob : sans lui, un motif sans correspondance reste littéral et fait échouer cp
    shopt -s nullglob
    imgs=("$images"/*.{png,jpg,jpeg,webp})
    shopt -u nullglob
    ((${#imgs[@]})) || die "aucune image png/jpg/webp dans $images"
    cp -- "${imgs[@]}" "$WALLPAPER_DIR"/
elif ((${#existantes[@]})) && ((regenerer == 0)); then
    info "Images déjà présentes dans $WALLPAPER_DIR (--regenerer pour les refaire)"
elif PY="$(python_pillow)"; then
    # Résolution de l'écran, 1920x1080 si xrandr est absent
    taille="$(xrandr --current 2>/dev/null | sed -nE 's/.*current ([0-9]+) x ([0-9]+).*/\1 \2/p' | head -n1 || true)"
    read -r largeur hauteur <<<"${taille:-1920 1080}"
    info "Génération des fonds d'écran en ${largeur}x${hauteur}"
    "$PY" "$SHARE/gen_wallpapers.py" "$WALLPAPER_DIR" --largeur "$largeur" --hauteur "$hauteur" >/dev/null
else
    warn "Pillow indisponible (python3-venv manquant ?) : images non générées."
    warn "Dépose tes images dans $WALLPAPER_DIR ou relance avec --images DIR."
fi

# ---------------------------------------------------------------- activation
info "Activation du timer (toutes les 30 min)"
systemctl --user daemon-reload
systemctl --user enable --now meteo-wallpaper.timer >/dev/null
if systemctl --user start meteo-wallpaper.service; then
    info "Premier changement de fond d'écran effectué"
else
    warn "Le premier lancement a échoué : journalctl --user -u meteo-wallpaper"
fi

case ":$PATH:" in
    *":$BIN:"*) ;;
    *) warn "$BIN n'est pas dans ton PATH : le timer marche, mais pour lancer meteo-wallpaper à la main ajoute-le à ton ~/.profile" ;;
esac

cat <<EOF

Installé.
  Tester une variante :  meteo-wallpaper --code 389 --nuit
  Voir les logs :        journalctl --user -u meteo-wallpaper
  Modifier la config :   $CONF
  Retoucher les images : $SRC/gen_wallpapers.py (dictionnaire VISAGES), puis ./install.sh --regenerer
  Tout retirer :         ./install.sh --desinstaller
EOF
