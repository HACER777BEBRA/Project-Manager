from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .config import AppConfig, GitHubConfig
from .git_utils import resolve_github_token, run_git


@dataclass
class CommitStat:
    sha: str
    author: str
    date: str
    subject: str
    additions: int
    deletions: int
    branches: list[str] = field(default_factory=list)


@dataclass
class PullRequestStat:
    number: int
    title: str
    state: str
    author: str
    url: str
    additions: int
    deletions: int
    changed_files: int
    created_at: str
    updated_at: str
    merged_at: str | None
    draft: bool


@dataclass
class IssueStat:
    number: int
    title: str
    state: str
    author: str
    url: str
    created_at: str
    closed_at: str | None


@dataclass
class ProjectReport:
    repo: str
    generated_at: datetime
    since: datetime
    until: datetime
    timezone_name: str
    branches_total: int
    active_branches: list[str]
    commits: list[CommitStat]
    open_prs: list[PullRequestStat]
    prs_opened: list[PullRequestStat]
    prs_merged: list[PullRequestStat]
    prs_updated: list[PullRequestStat]
    issues_opened: list[IssueStat]
    issues_closed: list[IssueStat]
    open_issues_count: int
    default_branch: str
    latest_default_sha: str
    stars: int
    forks: int
    open_prs_total: int


class GitHubClient:
    def __init__(self, cfg: GitHubConfig):
        self.cfg = cfg
        self.token = resolve_github_token(cfg.token)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "git-daily-report-bot",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"https://api.github.com{path}"
        response = self.session.get(url, params=params, timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def paginate(self, path: str, params: dict[str, Any] | None = None, max_pages: int = 10) -> list[Any]:
        items: list[Any] = []
        page = 1
        params = dict(params or {})
        params.setdefault("per_page", 100)
        while page <= max_pages:
            params["page"] = page
            chunk = self.get(path, params=params)
            if not chunk:
                break
            if not isinstance(chunk, list):
                raise RuntimeError(f"Ожидался список от {path}, получено: {type(chunk)}")
            items.extend(chunk)
            if len(chunk) < params["per_page"]:
                break
            page += 1
        return items


def ensure_mirror(cfg: AppConfig, token: str) -> Path:
    mirror = cfg.paths.mirror_dir
    remote = f"https://github.com/{cfg.github.repo}.git"
    if token:
        remote = f"https://x-access-token:{token}@github.com/{cfg.github.repo}.git"

    if (mirror / "HEAD").exists() or (mirror / ".git").exists():
        run_git(["remote", "set-url", "origin", remote], cwd=str(mirror))
        run_git(["fetch", "--all", "--prune"], cwd=str(mirror))
        return mirror

    mirror.parent.mkdir(parents=True, exist_ok=True)
    run_git(["clone", "--mirror", remote, str(mirror)])
    return mirror


def _parse_numstat(numstat: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d = parts[0], parts[1]
        if a.isdigit():
            additions += int(a)
        if d.isdigit():
            deletions += int(d)
    return additions, deletions


def collect_commits(mirror: Path, since: datetime, until: datetime) -> list[CommitStat]:
    # Важно: передавать UTC с суффиксом Z. Без timezone git на Windows
    # (Russian Standard Time и т.п.) трактует дату как локальную и сдвигает окно.
    since_s = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    until_s = until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    log = run_git(
        [
            "log",
            "--all",
            f"--since={since_s}",
            f"--until={until_s}",
            "--date=iso-strict",
            "--pretty=format:%H%x00%an%x00%ad%x00%s",
        ],
        cwd=str(mirror),
    ).strip()

    commits: list[CommitStat] = []
    if not log:
        return commits

    for row in log.split("\n"):
        if not row.strip():
            continue
        sha, author, date, subject = row.split("\x00", 3)
        numstat = run_git(["show", "--numstat", "--format=", sha], cwd=str(mirror))
        additions, deletions = _parse_numstat(numstat)

        containing = run_git(
            ["branch", "-a", "--contains", sha],
            cwd=str(mirror),
        )
        branches = []
        for line in containing.splitlines():
            name = line.strip().lstrip("* ").removeprefix("remotes/")
            if name and name not in branches:
                branches.append(name)

        commits.append(
            CommitStat(
                sha=sha,
                author=author,
                date=date,
                subject=subject,
                additions=additions,
                deletions=deletions,
                branches=branches[:8],
            )
        )
    return commits


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _pr_from_api(item: dict[str, Any]) -> PullRequestStat:
    return PullRequestStat(
        number=int(item["number"]),
        title=str(item.get("title") or ""),
        state="merged" if item.get("merged_at") else str(item.get("state") or ""),
        author=str((item.get("user") or {}).get("login") or "unknown"),
        url=str(item.get("html_url") or ""),
        additions=int(item.get("additions") or 0),
        deletions=int(item.get("deletions") or 0),
        changed_files=int(item.get("changed_files") or 0),
        created_at=str(item.get("created_at") or ""),
        updated_at=str(item.get("updated_at") or ""),
        merged_at=item.get("merged_at"),
        draft=bool(item.get("draft")),
    )


def collect_pull_requests(
    client: GitHubClient,
    owner: str,
    repo: str,
    since: datetime,
    until: datetime,
) -> tuple[list[PullRequestStat], list[PullRequestStat], list[PullRequestStat], list[PullRequestStat], int]:
    open_items = client.paginate(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "open", "sort": "updated", "direction": "desc"},
    )
    open_prs: list[PullRequestStat] = []
    for item in open_items:
        detailed = client.get(f"/repos/{owner}/{repo}/pulls/{item['number']}") or item
        open_prs.append(_pr_from_api(detailed))

    # Недавние PR (open+closed), чтобы поймать созданные/смерженные за период
    recent = client.paginate(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc"},
        max_pages=5,
    )

    opened: list[PullRequestStat] = []
    merged: list[PullRequestStat] = []
    updated: list[PullRequestStat] = []
    seen: set[int] = set()

    for item in recent:
        number = int(item["number"])
        if number in seen:
            continue
        detailed = client.get(f"/repos/{owner}/{repo}/pulls/{number}") or item
        pr = _pr_from_api(detailed)
        seen.add(number)

        created = _parse_dt(pr.created_at)
        updated_at = _parse_dt(pr.updated_at)
        merged_at = _parse_dt(pr.merged_at)

        if created and since <= created <= until:
            opened.append(pr)
        if merged_at and since <= merged_at <= until:
            merged.append(pr)
        if updated_at and since <= updated_at <= until:
            updated.append(pr)

    return open_prs, opened, merged, updated, len(open_items)


def collect_issues(
    client: GitHubClient,
    owner: str,
    repo: str,
    since: datetime,
    until: datetime,
) -> tuple[list[IssueStat], list[IssueStat], int]:
    open_issues = client.paginate(
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "sort": "updated", "direction": "desc"},
    )
    # GitHub issues endpoint includes PRs — filter them out
    open_count = sum(1 for i in open_issues if "pull_request" not in i)

    recent = client.paginate(
        f"/repos/{owner}/{repo}/issues",
        params={
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        max_pages=3,
    )

    opened: list[IssueStat] = []
    closed: list[IssueStat] = []
    for item in recent:
        if "pull_request" in item:
            continue
        issue = IssueStat(
            number=int(item["number"]),
            title=str(item.get("title") or ""),
            state=str(item.get("state") or ""),
            author=str((item.get("user") or {}).get("login") or "unknown"),
            url=str(item.get("html_url") or ""),
            created_at=str(item.get("created_at") or ""),
            closed_at=item.get("closed_at"),
        )
        created = _parse_dt(issue.created_at)
        closed_at = _parse_dt(issue.closed_at)
        if created and since <= created <= until:
            opened.append(issue)
        if closed_at and since <= closed_at <= until:
            closed.append(issue)

    return opened, closed, open_count


def collect_report(cfg: AppConfig) -> ProjectReport:
    tz = ZoneInfo(cfg.report.timezone)
    until = datetime.now(tz=tz)
    since = until - timedelta(hours=cfg.report.lookback_hours)

    client = GitHubClient(cfg.github)
    mirror = ensure_mirror(cfg, client.token)

    repo_info = client.get(f"/repos/{cfg.github.owner}/{cfg.github.name}") or {}
    default_branch = str(repo_info.get("default_branch") or "main")

    branches_raw = run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=str(mirror))
    # mirror clone stores remotes as heads under refs/heads typically for --mirror it's refs/heads
    if not branches_raw.strip():
        branches_raw = run_git(["branch", "-a", "--format=%(refname:short)"], cwd=str(mirror))

    all_branches = [b.strip() for b in branches_raw.splitlines() if b.strip()]
    commits = collect_commits(mirror, since, until)

    active_branches: list[str] = []
    for c in commits:
        for b in c.branches:
            if b not in active_branches:
                active_branches.append(b)

    open_prs, prs_opened, prs_merged, prs_updated, open_prs_total = collect_pull_requests(
        client, cfg.github.owner, cfg.github.name, since, until
    )
    issues_opened, issues_closed, open_issues_count = collect_issues(
        client, cfg.github.owner, cfg.github.name, since, until
    )

    latest_sha = ""
    try:
        latest_sha = run_git(["rev-parse", f"{default_branch}"], cwd=str(mirror)).strip()[:7]
    except Exception:
        try:
            latest_sha = run_git(["rev-parse", f"origin/{default_branch}"], cwd=str(mirror)).strip()[:7]
        except Exception:
            latest_sha = "n/a"

    return ProjectReport(
        repo=cfg.github.repo,
        generated_at=until,
        since=since,
        until=until,
        timezone_name=cfg.report.timezone,
        branches_total=len(all_branches),
        active_branches=active_branches[:15],
        commits=commits,
        open_prs=open_prs,
        prs_opened=prs_opened,
        prs_merged=prs_merged,
        prs_updated=prs_updated,
        issues_opened=issues_opened,
        issues_closed=issues_closed,
        open_issues_count=open_issues_count,
        default_branch=default_branch,
        latest_default_sha=latest_sha,
        stars=int(repo_info.get("stargazers_count") or 0),
        forks=int(repo_info.get("forks_count") or 0),
        open_prs_total=open_prs_total,
    )
