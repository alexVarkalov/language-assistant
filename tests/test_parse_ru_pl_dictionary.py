from __future__ import annotations

from scripts.parse_ru_pl_dictionary import parse_dictionary_text

SAMPLE_TEXT = """T&P Books. Русско-польский тематический словарь - 9000 слов                       16

СОДЕРЖАНИЕ

 1. Местоимения                                                16
ОСНОВНЫЕ ПОНЯТИЯ

основные понятия | часть 1

 1. Местоимения

я                                       ja                     [ja]
ты                                      ty                     [tɨ]

 2. Приветствия

Привет!                                 Cześć!                 [ʧɛɕʧ]
T&P Books. Русско-польский тематический словарь - 9000 слов                       17

Пока!                                   Na razie!              [na 'raʒe]

питание

 3. Продукты

хлеб                                    chleb (m)              [hlep]
"""


def test_parse_dictionary_text_extracts_sections_topics_words() -> None:
    sections = parse_dictionary_text(SAMPLE_TEXT)

    assert [s["title"] for s in sections] == ["основные понятия | часть 1", "питание"]

    first_section = sections[0]
    assert [t["number"] for t in first_section["topics"]] == [1, 2]
    assert first_section["topics"][0]["title"] == "Местоимения"
    assert first_section["topics"][0]["words"] == [
        {"ru": "я", "pl": "ja", "ipa": "[ja]"},
        {"ru": "ты", "pl": "ty", "ipa": "[tɨ]"},
    ]

    second_topic = first_section["topics"][1]
    assert second_topic["title"] == "Приветствия"
    # words split across a page-footer boundary still land in the same topic
    assert second_topic["words"] == [
        {"ru": "Привет!", "pl": "Cześć!", "ipa": "[ʧɛɕʧ]"},
        {"ru": "Пока!", "pl": "Na razie!", "ipa": "[na 'raʒe]"},
    ]

    second_section = sections[1]
    assert second_section["title"] == "питание"
    assert second_section["topics"][0]["words"] == [{"ru": "хлеб", "pl": "chleb (m)", "ipa": "[hlep]"}]


def test_parse_dictionary_text_ignores_table_of_contents() -> None:
    sections = parse_dictionary_text(SAMPLE_TEXT)
    # the TOC line " 1. Местоимения ... 16" (before the body-start marker) would
    # match the topic regex if it weren't excluded — must not create a phantom topic
    total_topics = sum(len(s["topics"]) for s in sections)
    total_words = sum(len(t["words"]) for s in sections for t in s["topics"])
    assert total_topics == 3
    assert total_words == 5
