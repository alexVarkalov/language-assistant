"""Parse the T&P Books "Русско-польский тематический словарь" PDF into JSON.

Dev-only tool. Requires `pdftotext` (poppler) on PATH. The source PDF and the
generated JSON are both copyrighted/derived content and must never be committed
to this public repo (see .gitignore) — regenerate locally and deploy the JSON
file directly to the target host instead.

Usage:
    python scripts/parse_ru_pl_dictionary.py <source.pdf> <output.json>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

BODY_START_MARKER = "ОСНОВНЫЕ ПОНЯТИЯ"

# The 28 section headings in the book, matched by exact stripped-line equality
# (not position) so the parser stays correct if pdftotext's output shifts.
SECTION_HEADINGS = frozenset(
    {
        "основные понятия | часть 1",
        "основные понятия | часть 2",
        "человек | тело человека",
        "одежда | аксессуары",
        "питание",
        "семья | родственники | окружающие",
        "человек | чувства | разное",
        "медицина",
        "город",
        "жилище",
        "работа | бизнес | часть 1",
        "работа | бизнес | часть 2",
        "профессии | занятия",
        "спорт",
        "образование",
        "искусство",
        "отдых | развлечения | туризм",
        "техника",
        "транспорт",
        "автомобиль",
        "события в жизни человека",
        "планета | часть 1",
        "планета | часть 2",
        "фауна",
        "флора",
        "страны | национальности",
        "термины общего характера",
        "основные глаголы | 550 слов",
    }
)

TOPIC_RE = re.compile(r"^\s*(\d+)\.\s+(\S.*?)\s*$")
FOOTER_RE = re.compile(r"^T&P Books\.")
PAGE_NUM_ONLY_RE = re.compile(r"^\s*\d+\s*$")
WORD_ENTRY_RE = re.compile(r"^(.+?)\s{2,}(\S.*?)\s{2,}(\[.*\])\s*$")


def parse_dictionary_text(text: str) -> list[dict]:
    """Parse pdftotext -layout output into [{title, topics: [{number, title, words}]}]."""
    lines = [line.lstrip("\x0c") for line in text.splitlines()]

    body_start_candidates = [i for i, line in enumerate(lines) if line.strip() == BODY_START_MARKER]
    if not body_start_candidates:
        msg = f"could not find body start marker {BODY_START_MARKER!r}"
        raise ValueError(msg)
    body = lines[body_start_candidates[-1] :]

    sections: list[dict] = []
    current_section: dict | None = None
    current_topic: dict | None = None

    for raw_line in body:
        stripped = raw_line.strip()
        if not stripped or FOOTER_RE.match(stripped) or PAGE_NUM_ONLY_RE.match(stripped):
            continue

        if stripped in SECTION_HEADINGS:
            current_section = {"title": stripped, "topics": []}
            sections.append(current_section)
            current_topic = None
            continue

        topic_match = TOPIC_RE.match(stripped)
        if topic_match and current_section is not None:
            current_topic = {"number": int(topic_match.group(1)), "title": topic_match.group(2), "words": []}
            current_section["topics"].append(current_topic)
            continue

        entry_match = WORD_ENTRY_RE.match(raw_line.rstrip())
        if entry_match and current_topic is not None:
            ru, pl, ipa = (part.strip() for part in entry_match.groups())
            current_topic["words"].append({"ru": ru, "pl": pl, "ipa": ipa})

    return sections


def _extract_pdf_text(pdf_path: str) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source.pdf> <output.json>", file=sys.stderr)
        raise SystemExit(2)

    pdf_path, output_path = sys.argv[1], sys.argv[2]
    text = _extract_pdf_text(pdf_path)
    sections = parse_dictionary_text(text)

    topic_count = sum(len(s["topics"]) for s in sections)
    word_count = sum(len(t["words"]) for s in sections for t in s["topics"])
    print(f"Parsed {len(sections)} sections, {topic_count} topics, {word_count} words.")

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(sections, handle, ensure_ascii=False, indent=1)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
