from __future__ import annotations

from collections import defaultdict

from .collector import ProjectReport


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _sum_lines(items: list) -> tuple[int, int]:
    additions = sum(getattr(i, "additions", 0) for i in items)
    deletions = sum(getattr(i, "deletions", 0) for i in items)
    return additions, deletions


def format_report(report: ProjectReport) -> str:
    commit_add, commit_del = _sum_lines(report.commits)
    open_pr_add, open_pr_del = _sum_lines(report.open_prs)
    opened_pr_add, opened_pr_del = _sum_lines(report.prs_opened)
    merged_pr_add, merged_pr_del = _sum_lines(report.prs_merged)

    by_author: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for c in report.commits:
        by_author[c.author][0] += 1
        by_author[c.author][1] += c.additions
        by_author[c.author][2] += c.deletions

    period = (
        f"{report.since.strftime('%d.%m %H:%M')} → "
        f"{report.until.strftime('%d.%m %H:%M')} ({report.timezone_name})"
    )

    lines: list[str] = [
        f"<b>Daily report</b>: <code>{_esc(report.repo)}</code>",
        f"<i>{_esc(period)}</i>",
        "",
        "<b>Состояние репозитория</b>",
        f"• Default: <code>{_esc(report.default_branch)}</code> @ <code>{_esc(report.latest_default_sha)}</code>",
        f"• Веток: {_fmt_int(report.branches_total)} | активных за период: {_fmt_int(len(report.active_branches))}",
        f"• Open PRs: {_fmt_int(report.open_prs_total)} | Open issues: {_fmt_int(report.open_issues_count)}",
        f"• Stars: {_fmt_int(report.stars)} | Forks: {_fmt_int(report.forks)}",
        "",
        "<b>Код за период (все ветки)</b>",
        f"• Коммитов: {_fmt_int(len(report.commits))}",
        f"• Строк: +{_fmt_int(commit_add)} / −{_fmt_int(commit_del)} "
        f"(нетто {commit_add - commit_del:+d})",
    ]

    if report.active_branches:
        preview = ", ".join(_esc(b) for b in report.active_branches[:8])
        more = "" if len(report.active_branches) <= 8 else f" (+{len(report.active_branches) - 8})"
        lines.append(f"• Активные ветки: {preview}{more}")

    if by_author:
        lines.append("")
        lines.append("<b>Авторы коммитов</b>")
        ranked = sorted(by_author.items(), key=lambda x: x[1][1] + x[1][2], reverse=True)
        for author, (count, add, delete) in ranked[:8]:
            lines.append(
                f"• {_esc(author)}: {count} commit(s), +{_fmt_int(add)} / −{_fmt_int(delete)}"
            )

    lines.extend(
        [
            "",
            "<b>Pull requests</b>",
            f"• Открыто за период: {_fmt_int(len(report.prs_opened))} "
            f"(+{_fmt_int(opened_pr_add)} / −{_fmt_int(opened_pr_del)})",
            f"• Смержено: {_fmt_int(len(report.prs_merged))} "
            f"(+{_fmt_int(merged_pr_add)} / −{_fmt_int(merged_pr_del)})",
            f"• Обновлено: {_fmt_int(len(report.prs_updated))}",
            f"• Сейчас открыты: {_fmt_int(len(report.open_prs))} "
            f"(суммарно в diff +{_fmt_int(open_pr_add)} / −{_fmt_int(open_pr_del)})",
        ]
    )

    def _pr_block(title: str, prs: list, limit: int = 5) -> None:
        if not prs:
            return
        lines.append("")
        lines.append(f"<b>{title}</b>")
        for pr in prs[:limit]:
            draft = " [draft]" if pr.draft else ""
            lines.append(
                f'• <a href="{_esc(pr.url)}">#{pr.number}</a> '
                f"{_esc(pr.title[:80])}{draft} "
                f"(+{_fmt_int(pr.additions)}/−{_fmt_int(pr.deletions)}, {_esc(pr.author)})"
            )
        if len(prs) > limit:
            lines.append(f"• …ещё {len(prs) - limit}")

    _pr_block("Новые PR", report.prs_opened)
    _pr_block("Смерженные PR", report.prs_merged)
    _pr_block("Открытые PR (топ по размеру)", sorted(report.open_prs, key=lambda p: p.additions + p.deletions, reverse=True))

    lines.extend(
        [
            "",
            "<b>Issues</b>",
            f"• Открыто: {_fmt_int(len(report.issues_opened))} | закрыто: {_fmt_int(len(report.issues_closed))}",
        ]
    )

    if report.commits:
        lines.append("")
        lines.append("<b>Последние коммиты</b>")
        for c in report.commits[:6]:
            short = c.sha[:7]
            lines.append(
                f"• <code>{short}</code> {_esc(c.subject[:70])} "
                f"(+{_fmt_int(c.additions)}/−{_fmt_int(c.deletions)}, {_esc(c.author)})"
            )
        if len(report.commits) > 6:
            lines.append(f"• …ещё {len(report.commits) - 6}")

    return "\n".join(lines)
