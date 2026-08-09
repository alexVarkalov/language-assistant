from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class WordEntry:
    ru: str
    pl: str
    ipa: str


@dataclass(frozen=True)
class Topic:
    number: int
    title: str
    words: tuple[WordEntry, ...]


@dataclass(frozen=True)
class Section:
    title: str
    topics: tuple[Topic, ...]


def load_wordbank(path: str) -> tuple[Section, ...]:
    with open(path, encoding="utf-8") as handle:
        raw_sections = json.load(handle)

    return tuple(
        Section(
            title=raw_section["title"],
            topics=tuple(
                Topic(
                    number=raw_topic["number"],
                    title=raw_topic["title"],
                    words=tuple(WordEntry(**raw_word) for raw_word in raw_topic["words"]),
                )
                for raw_topic in raw_section["topics"]
            ),
        )
        for raw_section in raw_sections
    )


def find_topic(sections: tuple[Section, ...], topic_number: int) -> tuple[Section, Topic] | None:
    for section in sections:
        for topic in section.topics:
            if topic.number == topic_number:
                return section, topic
    return None
