#!/usr/bin/env bash
# Установка/обновление Streamlit-приложения «Секундомер САМУР» на Ubuntu/Debian VPS.
#
# Что делает скрипт:
#   1. Устанавливает system-пакеты (python3-venv, git, ufw).
#   2. Клонирует или обновляет репозиторий в APP_DIR.
#   3. Создаёт virtualenv и ставит зависимости.
#   4. Создаёт systemd-юнит, запускает и включает автозапуск.
#   5. (Опционально) ставит Caddy и настраивает HTTPS для DOMAIN.
#   6. Открывает нужные порты в UFW, если UFW активен.
#
# Запуск (на VPS под root):
#   curl -fsSL https://raw.githubusercontent.com/Mirzoevmurad/workout-stopwatch-app/main/scripts/deploy_vps.sh -o deploy.sh
#   sudo bash deploy.sh                            # HTTP на :8501
#   sudo DOMAIN=stopwatch.example.com bash deploy.sh  # HTTPS через Caddy
#
# Повторный запуск безопасен — скрипт идемпотентен (обновит код и перезапустит сервис).

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Mirzoevmurad/workout-stopwatch-app.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/workout-stopwatch-app}"
APP_USER="${APP_USER:-samur}"
APP_PORT="${APP_PORT:-8501}"
SERVICE_NAME="${SERVICE_NAME:-workout-stopwatch}"
DOMAIN="${DOMAIN:-}"   # задайте, чтобы включить Caddy + HTTPS

log() { echo -e "\033[1;34m[deploy]\033[0m $*"; }
die() { echo -e "\033[1;31m[error]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Запустите скрипт под root (sudo)."

log "Обновляю apt и ставлю зависимости..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git ufw ca-certificates

if ! id -u "$APP_USER" >/dev/null 2>&1; then
    log "Создаю системного пользователя $APP_USER..."
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

if [[ -d "$APP_DIR/.git" ]]; then
    log "Обновляю репозиторий в $APP_DIR..."
    sudo -u "$APP_USER" git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
    sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
    log "Клонирую $REPO_URL → $APP_DIR..."
    mkdir -p "$APP_DIR"
    chown "$APP_USER:$APP_USER" "$APP_DIR"
    sudo -u "$APP_USER" git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

log "Устанавливаю Python-зависимости в venv..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

BIND_ADDR="0.0.0.0"
if [[ -n "$DOMAIN" ]]; then
    BIND_ADDR="127.0.0.1"   # за Caddy биндим только локально
fi

log "Пишу systemd-юнит /etc/systemd/system/${SERVICE_NAME}.service..."
cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<UNIT
[Unit]
Description=Workout Stopwatch (Streamlit)
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
# HOME must point to a writable path so Streamlit can create ~/.streamlit
# (under ProtectHome=true the real /home/${APP_USER} is hidden from the service).
Environment=HOME=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/streamlit run ${APP_DIR}/streamlit_app.py \\
    --server.address=${BIND_ADDR} \\
    --server.port=${APP_PORT} \\
    --server.headless=true \\
    --browser.gatherUsageStats=false
Restart=on-failure
RestartSec=3
# базовая sandbox-настройка
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${APP_DIR}

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

if ufw status 2>/dev/null | grep -q "Status: active"; then
    if [[ -n "$DOMAIN" ]]; then
        log "UFW активен — открываю 80/tcp и 443/tcp..."
        ufw allow 80/tcp  || true
        ufw allow 443/tcp || true
    else
        log "UFW активен — открываю ${APP_PORT}/tcp..."
        ufw allow "${APP_PORT}/tcp" || true
    fi
fi

if [[ -n "$DOMAIN" ]]; then
    log "Ставлю Caddy и настраиваю HTTPS для ${DOMAIN}..."
    if ! command -v caddy >/dev/null 2>&1; then
        apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
        curl -1sSLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
            | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sSLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
            | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
        apt-get update -y
        apt-get install -y caddy
    fi
    cat >/etc/caddy/Caddyfile <<CADDY
${DOMAIN} {
    encode zstd gzip
    reverse_proxy 127.0.0.1:${APP_PORT} {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
CADDY
    systemctl enable --now caddy
    systemctl reload caddy || systemctl restart caddy
fi

PUBLIC_IP="$(curl -s -m 3 https://ifconfig.me || hostname -I | awk '{print $1}')"
echo
echo "============================================================"
log "Готово. Сервис: systemctl status ${SERVICE_NAME}"
if [[ -n "$DOMAIN" ]]; then
    echo "Приложение доступно по https://${DOMAIN}/"
    echo "  (убедитесь, что A-запись ${DOMAIN} → ${PUBLIC_IP})"
else
    echo "Приложение доступно по http://${PUBLIC_IP}:${APP_PORT}/"
    echo "Для HTTPS перезапустите с DOMAIN=ваш.домен."
fi
echo "Логи:   journalctl -u ${SERVICE_NAME} -f"
echo "Обнова: sudo bash $(readlink -f "$0")"
echo "============================================================"
