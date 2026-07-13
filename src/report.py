from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .collector import IssueStat, ProjectReport, PullRequestStat


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _project_name(repo: str) -> str:
    return repo.split("/", 1)[-1] if repo else repo


def _format_period(since: datetime, until: datetime) -> str:
    same_day = since.date() == until.date()
    if same_day:
        return (
            f"{since.strftime('%d.%m.%Y')}, "
            f"{since.strftime('%H:%M')}–{until.strftime('%H:%M')}"
        )
    return (
        f"{since.strftime('%d.%m %H:%M')} — {until.strftime('%d.%m %H:%M')}"
    )


def _change_volume(additions: int, deletions: int) -> str:
    total = additions + deletions
    if total == 0:
        return "без изменения объёма кода"
    if total < 50:
        size = "небольшие правки"
    elif total < 300:
        size = "средний объём правок"
    elif total < 1000:
        size = "крупные правки"
    else:
        size = "очень крупный объём правок"
    return f"{size} (+{_fmt_int(additions)} / −{_fmt_int(deletions)} строк)"


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return many
    if n1 == 1:
        return one
    if 2 <= n1 <= 4:
        return few
    return many


def _changes_word(n: int) -> str:
    return _plural_ru(n, "изменение", "изменения", "изменений")


def _requests_word(n: int) -> str:
    return _plural_ru(n, "запрос", "запроса", "запросов")


def _people_word(n: int) -> str:
    return _plural_ru(n, "человек", "человека", "человек")


def format_report(report: ProjectReport) -> str:
    name = _project_name(report.repo)
    period = _format_period(report.since, report.until)

    by_author: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for c in report.commits:
        by_author[c.author][0] += 1
        by_author[c.author][1] += c.additions
        by_author[c.author][2] += c.deletions

    commit_add = sum(c.additions for c in report.commits)
    commit_del = sum(c.deletions for c in report.commits)
    n_commits = len(report.commits)
    n_authors = len(by_author)
    n_open_prs = len(report.open_prs)
    n_open_issues = report.open_issues_count

    lines: list[str] = [
        f"<b>Сводка по проекту «{_esc(name)}»</b>",
        f"<i>{_esc(period)}</i>",
        "",
        "<b>Кратко</b>",
    ]

    if n_commits == 0 and not report.prs_opened and not report.prs_merged and not report.issues_opened and not report.issues_closed:
        lines.append("• За период заметной активности не было")
    else:
        if n_commits:
            lines.append(
                f"• Сделано {_fmt_int(n_commits)} {_changes_word(n_commits)}"
                f" — {_change_volume(commit_add, commit_del)}"
            )
            if n_authors:
                lines.append(
                    f"• Работали: {_fmt_int(n_authors)} {_people_word(n_authors)}"
                )
        else:
            lines.append("• Новых изменений в коде не было")

        lines.append(
            f"• На проверке сейчас: {_fmt_int(n_open_prs)}"
        )
        lines.append(
            f"• Открытых задач: {_fmt_int(n_open_issues)}"
        )

        if report.prs_merged:
            n_merged = len(report.prs_merged)
            lines.append(
                f"• Влито в основную ветку: {_fmt_int(n_merged)} "
                f"{_requests_word(n_merged)}"
            )
        if report.issues_closed:
            n_closed = len(report.issues_closed)
            lines.append(
                f"• Закрыто задач: {_fmt_int(n_closed)}"
            )

    if by_author:
        lines.append("")
        lines.append("<b>Кто работал</b>")
        ranked = sorted(
            by_author.items(),
            key=lambda x: (x[1][0], x[1][1] + x[1][2]),
            reverse=True,
        )
        for author, (count, _add, _delete) in ranked[:10]:
            lines.append(
                f"• {_esc(author)} — {_fmt_int(count)} {_changes_word(count)}"
            )

    if report.commits:
        lines.append("")
        lines.append("<b>Что сделали</b>")
        for c in report.commits[:8]:
            subject = (c.subject or "без описания").strip()
            lines.append(f"• {_esc(subject[:90])} — {_esc(c.author)}")
        if len(report.commits) > 8:
            rest = len(report.commits) - 8
            lines.append(f"• …и ещё {_fmt_int(rest)} {_changes_word(rest)}")

    def _pr_section(title: str, prs: list[PullRequestStat], limit: int = 5) -> None:
        if not prs:
            return
        lines.append("")
        lines.append(f"<b>{title}</b>")
        for pr in prs[:limit]:
            draft = " (черновик)" if pr.draft else ""
            lines.append(
                f'• <a href="{_esc(pr.url)}">{_esc(pr.title[:80])}</a>'
                f"{draft} — {_esc(pr.author)}"
            )
        if len(prs) > limit:
            lines.append(f"• …ещё {_fmt_int(len(prs) - limit)}")

    _pr_section("Новые запросы на проверку", report.prs_opened)
    _pr_section("Принято и влито", report.prs_merged)

    waiting = [pr for pr in report.open_prs if not pr.draft]
    drafts = [pr for pr in report.open_prs if pr.draft]
    _pr_section("Ждут вашей проверки", waiting)
    _pr_section("Черновики (ещё не готовы)", drafts)

    def _issue_section(title: str, issues: list[IssueStat], limit: int = 5) -> None:
        if not issues:
            return
        lines.append("")
        lines.append(f"<b>{title}</b>")
        for issue in issues[:limit]:
            lines.append(
                f'• <a href="{_esc(issue.url)}">{_esc(issue.title[:80])}</a>'
                f" — {_esc(issue.author)}"
            )
        if len(issues) > limit:
            lines.append(f"• …ещё {_fmt_int(len(issues) - limit)}")

    _issue_section("Новые задачи", report.issues_opened)
    _issue_section("Закрытые задачи", report.issues_closed)

    return "\n".join(lines)
