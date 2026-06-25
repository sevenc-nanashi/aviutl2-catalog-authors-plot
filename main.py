from __future__ import annotations

import argparse
import fnmatch
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import matplotlib
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

DEFAULT_URL = "https://github.com/Neosku/aviutl2-catalog-data/raw/main/index.json"
DEFAULT_OUTPUT = Path("authors.png")
DEFAULT_TOP = 10
UNKNOWN_AUTHOR = "Unknown"
OTHERS_AUTHOR = "Others"
OTHERS_COLOR = "#9ca3af"
TYPE_ALIASES = {
    "プラグイン": ("MOD", "*プラグイン"),
}
FONT_CANDIDATES = [
    "Droid Sans Fallback",
    "Noto Sans CJK JP",
    "Yu Gothic",
    "Hiragino Sans",
    "DejaVu Sans",
]


class CatalogItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author: Annotated[str | None, Field(default=None)]
    item_type: Annotated[str | None, Field(default=None, validation_alias="type")]


CatalogItems = TypeAdapter(list[CatalogItem])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an author distribution pie chart from aviutl2-catalog-data.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"JSON URL to fetch. Default: {DEFAULT_URL}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output PNG path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"Number of top authors to show before grouping the rest. Default: {DEFAULT_TOP}",
    )
    parser.add_argument(
        "--type",
        dest="item_type",
        help='Catalog item type to include. "プラグイン" includes MOD and *プラグイン.',
    )
    return parser.parse_args()


def fetch_json(url: str) -> Any:
    try:
        with urlopen(url, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Failed to fetch JSON: HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"Failed to fetch JSON: {error.reason}") from error
    except TimeoutError as error:
        raise RuntimeError("Failed to fetch JSON: request timed out") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Failed to parse JSON: {error}") from error


def normalize_author(author: str | None) -> str:
    if author is None:
        return UNKNOWN_AUTHOR

    normalized = author.strip()
    if normalized == "":
        return UNKNOWN_AUTHOR

    return normalized


def normalize_item_type(item_type: str | None) -> str | None:
    if item_type is None:
        return None

    normalized = item_type.strip()
    if normalized == "":
        return None

    return normalized


def item_type_patterns(item_type: str | None) -> tuple[str, ...] | None:
    normalized = normalize_item_type(item_type)
    if normalized is None:
        return None

    return TYPE_ALIASES.get(normalized, (normalized,))


def matches_item_type(item: CatalogItem, patterns: tuple[str, ...] | None) -> bool:
    if patterns is None:
        return True

    item_type = normalize_item_type(item.item_type)
    if item_type is None:
        return False

    return any(fnmatch.fnmatchcase(item_type, pattern) for pattern in patterns)


def count_authors(data: Any, item_type: str | None) -> Counter[str]:
    items = CatalogItems.validate_python(data)
    patterns = item_type_patterns(item_type)
    return Counter(
        normalize_author(item.author) for item in items if matches_item_type(item, patterns)
    )


def top_author_counts(author_counts: Counter[str], top: int) -> list[tuple[str, int]]:
    if top < 1:
        raise ValueError("--top must be greater than or equal to 1")

    top_counts = author_counts.most_common(top)
    top_total = sum(count for _, count in top_counts)
    others_total = author_counts.total() - top_total

    if others_total > 0:
        top_counts.append((OTHERS_AUTHOR, others_total))

    return top_counts


def autopct_with_counts(values: list[int]) -> Any:
    total = sum(values)
    if total == 0:
        raise ValueError("Cannot render a chart from empty data")

    def format_label(percent: float) -> str:
        count = math.floor((percent * total / 100) + 0.5)
        return f"{percent:.1f}%\n({count})"

    return format_label


def available_font_families() -> list[str]:
    families = []
    for font in FONT_CANDIDATES:
        try:
            font_manager.findfont(font, fallback_to_default=False)
        except ValueError:
            continue

        families.append(font)

    if not families:
        raise RuntimeError("No usable Matplotlib font was found")

    return families


def chart_colors(labels: list[str]) -> list[str]:
    default_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    colors = []
    default_index = 0

    for label in labels:
        if label == OTHERS_AUTHOR:
            colors.append(OTHERS_COLOR)
            continue

        colors.append(default_colors[default_index % len(default_colors)])
        default_index += 1

    return colors


def plot_author_pie(author_counts: list[tuple[str, int]], output: Path) -> None:
    labels = [author for author, _ in author_counts]
    values = [count for _, count in author_counts]
    colors = chart_colors(labels)

    output.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.family"] = available_font_families()
    figure, axis = plt.subplots(figsize=(12, 8), constrained_layout=True)
    wedges, _, autotexts = axis.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=autopct_with_counts(values),
        startangle=90,
        counterclock=False,
        pctdistance=0.72,
        labeldistance=1.08,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        textprops={"fontsize": 10},
    )

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontsize(9)
        autotext.set_weight("bold")

    axis.set_title("AviUtl2 Catalog Authors", fontsize=16, pad=18)
    axis.axis("equal")
    axis.legend(
        wedges,
        [f"{label}: {value}" for label, value in author_counts],
        title="Authors",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=9,
    )
    figure.savefig(output, dpi=160)
    plt.close(figure)


def main() -> int:
    args = parse_args()

    try:
        data = fetch_json(args.url)
        author_counts = count_authors(data, args.item_type)
        plotted_counts = top_author_counts(author_counts, args.top)
        plot_author_pie(plotted_counts, args.output)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
