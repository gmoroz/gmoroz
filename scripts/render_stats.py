#!/usr/bin/env python3
"""Render GitHub profile statistics as self-contained SVG cards."""

from dataclasses import dataclass
import html
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/graphql"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

QUERY = """
query {
  viewer {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
          }
        }
      }
    }
    publicRepositories: repositories(first: 1, privacy: PUBLIC) {
      totalCount
    }
    privateRepositories: repositories(first: 1, privacy: PRIVATE) {
      totalCount
    }
  }
}
"""


@dataclass(frozen=True)
class Stats:
    """Данные статистики GitHub-профиля для карточки."""

    contributions: int
    active_days: int
    total_days: int
    public_repositories: int
    private_repositories: int

    @property
    def repositories(self) -> int:
        """Возвращает общее число публичных и приватных репозиториев."""
        return self.public_repositories + self.private_repositories


def fetch_stats(token: str) -> Stats:
    """Получает статистику профиля одним GraphQL-запросом.

    Параметры:
        token: GitHub token с доступом к нужным данным.

    Возврат:
        Статистика контрибуций и репозиториев.
    """
    request = Request(
        API_URL,
        data=json.dumps({"query": QUERY}).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL HTTP {error.code}: {details}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Не удалось получить данные GitHub GraphQL: {error}") from error

    if payload.get("errors"):
        messages = "; ".join(
            error.get("message", "Неизвестная ошибка GraphQL")
            for error in payload["errors"]
        )
        raise RuntimeError(f"GitHub GraphQL вернул ошибку: {messages}")

    viewer = payload.get("data", {}).get("viewer")
    if not viewer:
        raise RuntimeError("GitHub GraphQL вернул пустые данные viewer")

    calendar = viewer["contributionsCollection"]["contributionCalendar"]
    contribution_days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    return Stats(
        contributions=calendar["totalContributions"],
        active_days=sum(day["contributionCount"] > 0 for day in contribution_days),
        total_days=len(contribution_days),
        public_repositories=viewer["publicRepositories"]["totalCount"],
        private_repositories=viewer["privateRepositories"]["totalCount"],
    )


def render_svg(stats: Stats, *, dark: bool) -> str:
    """Строит SVG-карточку статистики в светлой или тёмной теме.

    Параметры:
        stats: Данные статистики GitHub-профиля.
        dark: Включить тёмную цветовую схему.

    Возврат:
        Содержимое самодостаточного SVG-файла.
    """
    colors = {
        "background": "#0d1117" if dark else "#ffffff",
        "text": "#e6edf3" if dark else "#1f2328",
        "accent": "#58a6ff" if dark else "#0969da",
        "border": "#30363d" if dark else "#d0d7de",
    }
    rows = (
        ("Contributions (last year)", f"{stats.contributions:,}"),
        ("Active days", f"{stats.active_days} of {stats.total_days}"),
        ("Repositories", f"{stats.repositories} ({stats.public_repositories} public)"),
    )
    title = "GitHub profile statistics"
    description = "; ".join(f"{label}: {value}" for label, value in rows)
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)

    text_lines = "\n".join(
        f'  <text x="24" y="{y}" fill="{colors["text"]}" font-family="-apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif" font-size="16">'
        f'<tspan>{html.escape(label)}</tspan>'
        f'<tspan x="376" text-anchor="end" fill="{colors["accent"]}" font-weight="700">{html.escape(value)}</tspan>'
        "</text>"
        for y, (label, value) in zip((43, 83, 123), rows)
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="150" viewBox="0 0 400 150" role="img" aria-labelledby="title desc">
  <title id="title">{escaped_title}</title>
  <desc id="desc">{escaped_description}</desc>
  <rect x="0.5" y="0.5" width="399" height="149" rx="12" fill="{colors["background"]}" stroke="{colors["border"]}" />
{text_lines}
</svg>
'''


def main() -> int:
    """Получает данные и записывает светлую и тёмную SVG-карточки."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("Ошибка: переменная окружения GITHUB_TOKEN не задана или пуста.", file=sys.stderr)
        return 1

    try:
        stats = fetch_stats(token)
    except RuntimeError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1

    (REPOSITORY_ROOT / "assets/stats-light.svg").write_text(
        render_svg(stats, dark=False), encoding="utf-8"
    )
    (REPOSITORY_ROOT / "assets/stats-dark.svg").write_text(
        render_svg(stats, dark=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
