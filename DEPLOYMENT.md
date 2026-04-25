# Развёртывание на собственном VPS

Для Ubuntu/Debian VPS. Тестировалось на Ubuntu 22.04 / 24.04.

## Быстрый старт (HTTP на `:8501`)

SSH на VPS и выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/Mirzoevmurad/workout-stopwatch-app/main/scripts/deploy_vps.sh -o deploy.sh
sudo bash deploy.sh
```

После завершения откройте `http://<ip-адрес-vps>:8501/`.

## HTTPS + домен (через Caddy)

Направьте A-запись домена на IP VPS, затем:

```bash
sudo DOMAIN=stopwatch.example.com bash deploy.sh
```

Caddy получит Let's Encrypt-сертификат автоматически. Приложение будет доступно по `https://stopwatch.example.com/`.

## Что делает скрипт

- Ставит `python3-venv`, `git`, `ufw`, при необходимости — `caddy`.
- Создаёт системного пользователя `samur` без shell.
- Клонирует репозиторий в `/opt/workout-stopwatch-app` (идемпотентно — при повторном запуске обновляет код).
- Делает venv, ставит `streamlit==1.53.1`.
- Создаёт systemd-юнит `workout-stopwatch.service`, запускает и включает автозапуск.
- При активном UFW открывает нужные порты (`8501` без домена; `80/443` с доменом).

## Управление сервисом

```bash
sudo systemctl status  workout-stopwatch    # состояние
sudo systemctl restart workout-stopwatch    # перезапуск
sudo systemctl stop    workout-stopwatch    # остановить
sudo journalctl -u workout-stopwatch -f     # смотреть логи в реальном времени
```

## Обновление после изменений в репозитории

```bash
sudo bash /root/deploy.sh        # повторный запуск — безопасно
# или одной командой:
curl -fsSL https://raw.githubusercontent.com/Mirzoevmurad/workout-stopwatch-app/main/scripts/deploy_vps.sh | sudo bash
```

## Переменные окружения скрипта

| Переменная | По умолчанию | Описание |
|---|---|---|
| `REPO_URL` | `https://github.com/Mirzoevmurad/workout-stopwatch-app.git` | Откуда клонировать |
| `BRANCH` | `main` | Ветка для деплоя |
| `APP_DIR` | `/opt/workout-stopwatch-app` | Куда ставить |
| `APP_USER` | `samur` | Под кем запускать |
| `APP_PORT` | `8501` | Порт Streamlit |
| `SERVICE_NAME` | `workout-stopwatch` | Имя systemd-юнита |
| `DOMAIN` | _пусто_ | Если задан — ставится Caddy + HTTPS |

Пример:

```bash
sudo APP_PORT=9000 BRANCH=main bash deploy.sh
```

## Примечания

- У Streamlit нет встроенной авторизации. Если приложение должно быть закрытым, добавьте basic-auth на уровне Caddy (директива `basicauth`) или используйте VPN.
- На firewall провайдера может понадобиться отдельно открыть `80/443` (или `8501` без домена).
- Для мобильного доступа к микрофону/автоплею аудио в некоторых браузерах нужен HTTPS — используйте вариант с `DOMAIN`.
