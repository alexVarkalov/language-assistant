from __future__ import annotations

import json
from pathlib import Path

from vocab_bot.wordbank import Section, Topic, WordEntry, find_topic, load_wordbank

SAMPLE_DATA = [
    {
        "title": "основные понятия | часть 1",
        "topics": [
            {
                "number": 1,
                "title": "Местоимения",
                "words": [{"ru": "я", "pl": "ja", "ipa": "[ja]"}, {"ru": "ты", "pl": "ty", "ipa": "[tɨ]"}],
            }
        ],
    },
    {
        "title": "питание",
        "topics": [{"number": 3, "title": "Продукты", "words": [{"ru": "хлеб", "pl": "chleb (m)", "ipa": "[hlep]"}]}],
    },
]


def test_load_wordbank_builds_frozen_structures(tmp_path: Path) -> None:
    data_file = tmp_path / "dict.json"
    data_file.write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")

    sections = load_wordbank(str(data_file))

    assert sections == (
        Section(
            title="основные понятия | часть 1",
            topics=(
                Topic(
                    number=1,
                    title="Местоимения",
                    words=(WordEntry(ru="я", pl="ja", ipa="[ja]"), WordEntry(ru="ты", pl="ty", ipa="[tɨ]")),
                ),
            ),
        ),
        Section(
            title="питание",
            topics=(Topic(number=3, title="Продукты", words=(WordEntry(ru="хлеб", pl="chleb (m)", ipa="[hlep]"),)),),
        ),
    )


def test_find_topic_hit_and_miss(tmp_path: Path) -> None:
    data_file = tmp_path / "dict.json"
    data_file.write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")
    sections = load_wordbank(str(data_file))

    found = find_topic(sections, 3)
    assert found is not None
    section, topic = found
    assert section.title == "питание"
    assert topic.title == "Продукты"

    assert find_topic(sections, 999) is None
