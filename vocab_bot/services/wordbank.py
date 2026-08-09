from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from vocab_bot.config import Settings
from vocab_bot.repositories import CardRepository
from vocab_bot.wordbank import Section, Topic, find_topic


@dataclass(frozen=True)
class WordbankAddResult:
    topic_title: str
    added: int
    skipped: int


class WordbankService:
    def __init__(self, sections: tuple[Section, ...], card_repo: CardRepository, settings: Settings) -> None:
        self._sections = sections
        self._card_repo = card_repo
        self._settings = settings

    def list_sections(self) -> tuple[Section, ...]:
        return self._sections

    def get_topic(self, topic_number: int) -> tuple[Section, Topic] | None:
        return find_topic(self._sections, topic_number)

    async def add_topic_words(self, *, user_id: int, topic_number: int) -> WordbankAddResult | None:
        found = find_topic(self._sections, topic_number)
        if found is None:
            return None
        _, topic = found

        # The dictionary data is always RU->PL; map it onto whichever of this
        # deployment's two configured languages is actually RU vs PL.
        if self._settings.source_lang == "RU" and self._settings.target_lang == "PL":
            pairs = [(word.ru, word.pl) for word in topic.words]
        elif self._settings.source_lang == "PL" and self._settings.target_lang == "RU":
            pairs = [(word.pl, word.ru) for word in topic.words]
        else:
            return WordbankAddResult(topic_title=topic.title, added=0, skipped=len(topic.words))

        first_review = datetime.now(tz=UTC) + timedelta(minutes=self._settings.short_review_interval_minutes)
        added = 0
        for source_text, target_text in pairs:
            inserted = await self._card_repo.insert_if_missing(
                user_id=user_id,
                source_lang=self._settings.source_lang,
                target_lang=self._settings.target_lang,
                source_text=source_text,
                target_text=target_text,
                ease_factor=2.5,
                interval_days=0.0,
                repetition=0,
                next_review_at=first_review,
            )
            if inserted:
                added += 1

        return WordbankAddResult(topic_title=topic.title, added=added, skipped=len(topic.words) - added)
