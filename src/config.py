from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class GitHubConfig:
    repo: str
    token: str

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.repo.split("/", 1)[1]


@dataclass(frozen=True)
class ReportConfig:
    lookback_hours: int
    timezone: str
    send_at_hour: int
    send_at_minute: int


@dataclass(frozen=True)
class PathsConfig:
    mirror_dir: Path


@dataclass(frozen=True)
class AppConfig:
    telegram: TelegramConfig
    github: GitHubConfig
    report: ReportConfig
    paths: PathsConfig
    root: Path


def _require(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    path = []
    for key in keys:
        path.append(key)
        if not isinstance(cur, dict) or key not in cur:
            raise ValueError(f"В конфиге не хватает ключа: {'.'.join(path)}")
        cur = cur[key]
    return cur


def load_config(path: Path | None = None) -> AppConfig:
    root = Path(__file__).resolve().parent.parent
    config_path = path or (root / "config.yaml")
    if not config_path.exists():
        example = root / "config.example.yaml"
        raise FileNotFoundError(
            f"Не найден {config_path.name}. Скопируйте {example.name} в config.yaml и заполните токены."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    mirror = Path(str(_require(raw, "paths", "mirror_dir")))
    if not mirror.is_absolute():
        mirror = root / mirror

    return AppConfig(
        telegram=TelegramConfig(
            bot_token=str(_require(raw, "telegram", "bot_token")).strip(),
            chat_id=str(_require(raw, "telegram", "chat_id")).strip(),
        ),
        github=GitHubConfig(
            repo=str(_require(raw, "github", "repo")).strip(),
            token=str(raw.get("github", {}).get("token") or "").strip(),
        ),
        report=ReportConfig(
            lookback_hours=int(_require(raw, "report", "lookback_hours")),
            timezone=str(_require(raw, "report", "timezone")),
            send_at_hour=int(raw.get("report", {}).get("send_at_hour", 9)),
            send_at_minute=int(raw.get("report", {}).get("send_at_minute", 0)),
        ),
        paths=PathsConfig(mirror_dir=mirror),
        root=root,
    )
