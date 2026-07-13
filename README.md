# Project Manager

Ежедневный отчёт по активности Git/GitHub-репозитория в Telegram.

Бот собирает статистику за выбранный период (коммиты, ветки, PR, issues) и отправляет сводку в чат. Можно запустить разово, в режиме dry-run или через планировщик Windows.

## Возможности

- Коммиты по всем веткам: количество, `+/−` строк, разбивка по авторам
- Активные ветки за период
- Open / opened / merged / updated pull requests
- Opened / closed issues
- Состояние репозитория: default branch, stars, forks

## Требования

- Python 3.10+
- Git
- Telegram-бот ([@BotFather](https://t.me/BotFather))
- Токен GitHub (Personal Access Token) **или** авторизация через [`gh auth login`](https://cli.github.com/)

## Установка

```powershell
cd C:\Users\HACER777BEBRA\Documents\GitHub\Project-Manager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Скопируйте пример конфига и заполните значения:

```powershell
Copy-Item config.example.yaml config.yaml
```

### Конфигурация (`config.yaml`)

| Секция | Параметры |
|--------|-----------|
| `telegram` | `bot_token`, `chat_id` |
| `github` | `repo` (`owner/name`), `token` (можно оставить пустым, если есть `gh`) |
| `report` | `lookback_hours`, `timezone`, `send_at_hour`, `send_at_minute` |
| `paths` | `mirror_dir` — локальное зеркало репозитория для анализа git |

`config.yaml` в git не коммитится (см. `.gitignore`).

## Запуск

Разовая отправка в Telegram:

```powershell
.\run.ps1
# или
python main.py
```

Только сбор отчёта в консоль (без Telegram):

```powershell
python main.py --dry-run
```

Фоновый цикл (отправка каждый день в время из конфига):

```powershell
python main.py --schedule
```

Другой путь к конфигу:

```powershell
python main.py --config path\to\config.yaml
```

## Планировщик Windows

Регистрация ежедневной задачи (по умолчанию 09:00):

```powershell
.\install_scheduler.ps1
.\install_scheduler.ps1 -Time "09:30" -TaskName "GitDailyReportBot"
```

Перед этим заполните `config.yaml`. Скрипт вызывает `run.ps1`, который при необходимости создаёт `.venv` и ставит зависимости.

