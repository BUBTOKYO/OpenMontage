"""Japanese TTS reading correction (lib/ja_reading.py)."""

from __future__ import annotations

import pytest

pytest.importorskip("janome")

from lib.ja_reading import (  # noqa: E402
    display_alignment,
    find_project_dictionary,
    load_dictionaries,
    needs_reading_fix,
    number_reading,
    to_spoken,
)


@pytest.mark.parametrize(
    "digits,reading",
    [("0", "ぜろ"), ("10", "じゅう"), ("300", "さんびゃく"), ("8000", "はっせん"),
     ("2026", "にせんにじゅうろく"), ("123456", "じゅうにまんさんぜんよんひゃくごじゅうろく"),
     ("1.5", "いちてんご"), ("３", "さん")],
)
def test_number_reading(digits, reading):
    assert number_reading(digits) == reading


def test_kanji_and_numbers_become_kana():
    spoken = to_spoken("ステップ1、肌を整える。5か所に置いて").spoken
    assert spoken == "ステップいち、はだをととのえる。ごかしょにおいて"


@pytest.mark.parametrize(
    "text,spoken",
    [("1か所", "いっかしょ"), ("3本", "さんぼん"), ("4分", "よんぷん"), ("2人", "ふたり"),
     ("3つ", "みっつ"), ("20歳", "はたち"), ("1.5倍", "いちてんごばい")],
)
def test_counter_euphony(text, spoken):
    assert to_spoken(text).spoken == spoken


def test_dictionary_matches_whole_morphemes_only():
    dictionary = {"朝": "あさ", "日焼け止め": "ひやけどめ"}
    assert to_spoken("朝スキンケア", dictionary).spoken == "あさスキンケア"
    # 朝食 is one morpheme, so the 朝 entry must not split it.
    assert to_spoken("朝食", dictionary).spoken == "ちょうしょく"
    # Multi-morpheme entries (日焼け + 止め) match too.
    result = to_spoken("最後に日焼け止め", dictionary)
    assert result.spoken.endswith("ひやけどめ")
    assert {"written": "日焼け止め", "spoken": "ひやけどめ", "source": "dictionary"} in result.replacements


def test_span_maps_written_characters_to_spoken():
    result = to_spoken("朝のケア", {"朝": "あさ"})
    assert result.spoken == "あさのケア"
    assert len(result.span) == len(result.written)
    assert result.span[0] == (0, 2)  # 朝 -> あさ
    assert result.span[1] == (2, 3)  # の


def test_display_alignment_times_written_text():
    result = to_spoken("朝のケア", {"朝": "あさ"})
    chars = list(result.spoken)
    alignment = {
        "characters": chars,
        "character_start_times_seconds": [i * 0.1 for i in range(len(chars))],
        "character_end_times_seconds": [(i + 1) * 0.1 for i in range(len(chars))],
    }
    shown = display_alignment(alignment, result)
    assert shown["characters"] == list("朝のケア")
    assert shown["character_start_times_seconds"][0] == 0.0
    assert shown["character_end_times_seconds"][0] == pytest.approx(0.2)  # end of さ
    assert shown["character_start_times_seconds"][1] == pytest.approx(0.2)
    # Normalised by the service -> cannot map.
    assert display_alignment(dict(alignment, characters=["x"] * len(chars)), result) is None


def test_needs_reading_fix():
    assert needs_reading_fix("hello", "ja")
    assert not needs_reading_fix("こんにちは", "en")
    assert needs_reading_fix("こんにちは", None)
    assert not needs_reading_fix("Hello world", None)


def test_dictionaries_merge_shared_then_project(tmp_path):
    project = tmp_path / "projects" / "demo"
    (project / "assets" / "audio").mkdir(parents=True)
    path = project / "pronunciation_ja.yaml"
    path.write_text("朝: ちょう\n商品名: しょうひんめい\n", encoding="utf-8")

    assert find_project_dictionary(project / "assets" / "audio" / "n.mp3") == path
    merged = load_dictionaries([path])
    assert merged["朝"] == "ちょう"  # project overrides the shared あさ
    assert merged["肌"] == "はだ"  # shared entries still present


def test_ssml_tags_pass_through():
    result = to_spoken('朝<break time="0.6s"/>ステップ2')
    assert result.spoken == 'あさ<break time="0.6s"/>ステップに'
    assert len(result.span) == len(result.written)
