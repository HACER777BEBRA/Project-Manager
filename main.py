from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Allow `python main.py` from project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.collector import collect_report
from src.config import load_config
from src.report import format_report
from src.telegram_sender import TelegramSender


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(encoding, errors="replace"))


def run_once(dry_run: bool = False, config_path: Path | None = None) -> int:
    cfg = load_config(config_path)
    _safe_print(f"Собираю отчёт по {cfg.github.repo}…")
    report = collect_report(cfg)
    text = format_report(report)

    if dry_run:
        _safe_print("\n===== DRY RUN =====\n")
        _safe_print(text)
        _safe_print("\n===== END =====")
        return 0

    if "YOUR_TELEGRAM_BOT_TOKEN" in cfg.telegram.bot_token or "YOUR_CHAT_ID" in cfg.telegram.chat_id:
        raise SystemExit(
            "Заполните telegram.bot_token и telegram.chat_id в config.yaml "
            "(или запустите с --dry-run)."
        )

    _safe_print("Отправляю в Telegram…")
    TelegramSender(cfg.telegram).send_message(text)
    _safe_print("Готово.")
    return 0


def run_schedule_loop(config_path: Path | None = None) -> int:
    cfg = load_config(config_path)
    tz = ZoneInfo(cfg.report.timezone)
    print(
        f"Планировщик: каждый день в "
        f"{cfg.report.send_at_hour:02d}:{cfg.report.send_at_minute:02d} ({cfg.report.timezone})"
    )
    last_sent_date = None
    while True:
        now = datetime.now(tz=tz)
        due = (
            now.hour > cfg.report.send_at_hour
            or (now.hour == cfg.report.send_at_hour and now.minute >= cfg.report.send_at_minute)
        )
        if due and last_sent_date != now.date():
            try:
                run_once(dry_run=False, config_path=config_path)
                last_sent_date = now.date()
            except Exception as exc:  # noqa: BLE001 — хотим жить дальше в цикле
                print(f"Ошибка отправки: {exc}", file=sys.stderr)
        time.sleep(30)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ежедневный отчёт по git/GitHub в Telegram",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Путь к config.yaml (по умолчанию ./config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Собрать отчёт и вывести в консоль без отправки в Telegram",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Держать процесс и слать отчёт каждый день в время из конфига",
    )
    args = parser.parse_args()

    if args.schedule:
        return run_schedule_loop(args.config)
    return run_once(dry_run=args.dry_run, config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
