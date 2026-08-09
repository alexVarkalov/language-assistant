from __future__ import annotations

import re

CYRILLIC_PATTERN = re.compile(r"[Ѐ-ӿ]")

# ISO 639-1 codes DeepL supports whose primary script is Cyrillic.
CYRILLIC_LANGUAGES = frozenset({"RU", "UK", "BG", "SR"})


class UnsupportedLanguagePairError(ValueError):
    pass


def _script_group(lang: str) -> str:
    return "cyrillic" if lang.upper() in CYRILLIC_LANGUAGES else "latin"


def validate_language_pair(lang_a: str, lang_b: str) -> None:
    if _script_group(lang_a) == _script_group(lang_b):
        msg = (
            f"Cannot auto-detect direction for {lang_a}/{lang_b}: both languages use the same script. "
            "Script-based detection currently supports one Cyrillic-script language paired with one "
            "Latin-script language (e.g. PL/RU)."
        )
        raise UnsupportedLanguagePairError(msg)


def detect_source_lang(text: str, lang_a: str, lang_b: str) -> str:
    cyrillic_lang = lang_a if _script_group(lang_a) == "cyrillic" else lang_b
    latin_lang = lang_b if cyrillic_lang == lang_a else lang_a
    return cyrillic_lang if CYRILLIC_PATTERN.search(text) else latin_lang


def resolve_direction(text: str, lang_a: str, lang_b: str) -> tuple[str, str]:
    source = detect_source_lang(text, lang_a, lang_b)
    target = lang_b if source == lang_a else lang_a
    return source, target
