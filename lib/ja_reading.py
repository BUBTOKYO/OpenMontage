"""Japanese reading correction for TTS.

TTS engines misread kanji (朝 as ちょう, 肌 as き …) and bare digits
(ステップ1 as "one"). This module rewrites the text that is *spoken* into kana
while the written text stays untouched for captions:

1. Pronunciation dictionaries (shared ``lib/pronunciation_ja.yaml`` plus an
   optional per-project ``pronunciation_ja.yaml``) — matched on morpheme
   boundaries, so an entry for 朝 never fires inside 朝食.
2. Every remaining kanji word is replaced by its reading from the janome
   morphological analyser.
3. Numbers become kana, with counter euphony (1か所 → いっかしょ).

``to_spoken`` also returns, for every written character, the span of spoken
characters it became, so TTS character timings can be mapped back onto the
written text (``display_alignment``).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SHARED_DICTIONARY = Path(__file__).with_name("pronunciation_ja.yaml")
PROJECT_DICTIONARY_NAME = "pronunciation_ja.yaml"

_KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ]")
_KANA = re.compile(r"[぀-ヿ]")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_TAG = re.compile(r"<[^<>]+>")  # SSML such as <break time="0.6s"/> passes through untouched

_DIGITS = ["ぜろ", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"]
# Sound changes in front of 百 / 千.
_HUNDREDS = {1: "ひゃく", 3: "さんびゃく", 6: "ろっぴゃく", 8: "はっぴゃく"}
_THOUSANDS = {1: "せん", 3: "さんぜん", 8: "はっせん"}

# counter -> (default reading, {number: whole reading with euphony})
_COUNTERS: dict[str, tuple[str, dict[int, str]]] = {
    "か所": ("かしょ", {1: "いっかしょ", 6: "ろっかしょ", 8: "はっかしょ", 10: "じゅっかしょ"}),
    "箇所": ("かしょ", {1: "いっかしょ", 6: "ろっかしょ", 8: "はっかしょ", 10: "じゅっかしょ"}),
    "ヶ所": ("かしょ", {1: "いっかしょ", 6: "ろっかしょ", 8: "はっかしょ", 10: "じゅっかしょ"}),
    "カ所": ("かしょ", {1: "いっかしょ", 6: "ろっかしょ", 8: "はっかしょ", 10: "じゅっかしょ"}),
    "回": ("かい", {1: "いっかい", 6: "ろっかい", 8: "はっかい", 10: "じゅっかい"}),
    "個": ("こ", {1: "いっこ", 6: "ろっこ", 8: "はっこ", 10: "じゅっこ"}),
    "分": ("ふん", {1: "いっぷん", 3: "さんぷん", 4: "よんぷん", 6: "ろっぷん", 8: "はっぷん", 10: "じゅっぷん"}),
    "本": ("ほん", {1: "いっぽん", 3: "さんぼん", 6: "ろっぽん", 8: "はっぽん", 10: "じゅっぽん"}),
    "杯": ("はい", {1: "いっぱい", 3: "さんばい", 6: "ろっぱい", 8: "はっぱい", 10: "じゅっぱい"}),
    "枚": ("まい", {}),
    "秒": ("びょう", {}),
    "倍": ("ばい", {}),
    "度": ("ど", {}),
    "円": ("えん", {4: "よえん"}),
    "歳": ("さい", {1: "いっさい", 8: "はっさい", 10: "じゅっさい", 20: "はたち"}),
    "年": ("ねん", {4: "よねん"}),
    "時": ("じ", {4: "よじ", 7: "しちじ", 9: "くじ"}),
    "時間": ("じかん", {4: "よじかん", 7: "しちじかん", 9: "くじかん"}),
    "人": ("にん", {1: "ひとり", 2: "ふたり", 4: "よにん"}),
    "つ": ("", {1: "ひとつ", 2: "ふたつ", 3: "みっつ", 4: "よっつ", 5: "いつつ", 6: "むっつ",
               7: "ななつ", 8: "やっつ", 9: "ここのつ", 10: "とお"}),
    "%": ("ぱーせんと", {}),
    "％": ("ぱーせんと", {}),
}


def number_reading(text: str) -> str:
    """Kana reading of a non-negative integer or decimal written in digits."""
    text = unicodedata.normalize("NFKC", text)
    if "." in text:
        whole, frac = text.split(".", 1)
        return number_reading(whole) + "てん" + "".join(_DIGITS[int(d)] for d in frac)
    n = int(text)
    if n == 0:
        return _DIGITS[0]
    if n >= 10**12:
        return "".join(_DIGITS[int(d)] for d in str(n))
    parts = []
    for unit_value, unit in ((10**8, "おく"), (10**4, "まん")):
        if n >= unit_value:
            parts.append(_below_10000(n // unit_value) + unit)
            n %= unit_value
    if n:
        parts.append(_below_10000(n))
    return "".join(parts)


def _below_10000(n: int) -> str:
    out = ""
    th, n = divmod(n, 1000)
    if th:
        out += _THOUSANDS.get(th, _DIGITS[th] + "せん")
    hu, n = divmod(n, 100)
    if hu:
        out += _HUNDREDS.get(hu, _DIGITS[hu] + "ひゃく")
    te, n = divmod(n, 10)
    if te:
        out += ("" if te == 1 else _DIGITS[te]) + "じゅう"
    if n:
        out += _DIGITS[n]
    return out


def _hiragana(katakana: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in katakana)


def load_dictionaries(paths: list[str | Path] | None = None) -> dict[str, str]:
    """Merge the shared dictionary with ``paths``; later files win."""
    merged: dict[str, str] = {}
    for path in [SHARED_DICTIONARY, *(paths or [])]:
        path = Path(path)
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path}: pronunciation dictionary must be a mapping of written: reading")
        merged.update({str(k): str(v) for k, v in data.items()})
    return merged


def find_project_dictionary(output_path: str | Path | None) -> Path | None:
    """The nearest ``pronunciation_ja.yaml`` above an output path inside projects/<id>/."""
    if not output_path:
        return None
    for parent in Path(output_path).resolve().parents:
        candidate = parent / PROJECT_DICTIONARY_NAME
        if candidate.is_file():
            return candidate
        if parent.parent.name == "projects":
            break
    return None


def needs_reading_fix(text: str, language_code: str | None) -> bool:
    if language_code:
        return language_code.lower().startswith("ja")
    return bool(_KANA.search(text))


@dataclass
class SpokenText:
    written: str
    spoken: str
    # span[i] = (start, end) of the spoken characters produced by written[i]
    span: list[tuple[int, int]]
    replacements: list[dict[str, str]] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


def to_spoken(text: str, dictionary: dict[str, str] | None = None) -> SpokenText:
    """Rewrite ``text`` into the kana form a Japanese TTS voice should read."""
    try:
        from janome.tokenizer import Tokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Japanese reading correction needs janome (pip install -r requirements.txt); "
            "pass reading_fix='off' to send the text unchanged"
        ) from exc

    dictionary = dictionary or {}
    out = SpokenText(written=text, spoken="", span=[])
    tokenizer = Tokenizer()
    pos = 0
    for tag in [*_TAG.finditer(text), None]:
        end = tag.start() if tag else len(text)
        if end > pos:
            _convert(text[pos:end], dictionary, tokenizer, out)
        if tag:
            _emit(out, tag.group(), tag.group(), "kept")
            pos = tag.end()
    return out


def _emit(out: SpokenText, written: str, spoken: str, source: str) -> None:
    start = len(out.spoken)
    out.spoken += spoken
    out.span.extend([(start, len(out.spoken))] * len(written))
    if written != spoken:
        out.replacements.append({"written": written, "spoken": spoken, "source": source})


def _convert(text: str, dictionary: dict[str, str], tokenizer: Any, out: SpokenText) -> None:
    tokens: list[tuple[str, str]] = []
    for t in tokenizer.tokenize(text):
        # The analyser splits decimals ("1", ".", "5"); join them back.
        if (len(tokens) >= 2 and tokens[-1][0] in (".", "．") and t.surface.isdigit()
                and tokens[-2][0].isdigit()):
            tokens[-2:] = [(tokens[-2][0] + tokens[-1][0] + t.surface, "*")]
            continue
        tokens.append((t.surface, t.reading))

    def emit(written: str, spoken: str, source: str) -> None:
        _emit(out, written, spoken, source)

    i = 0
    while i < len(tokens):
        # 1. Dictionary: longest run of whole tokens that matches an entry.
        hit = None
        joined = ""
        for j in range(i, min(i + 8, len(tokens))):
            joined += tokens[j][0]
            if joined in dictionary:
                hit = (j, joined)
        if hit:
            j, written = hit
            emit(written, dictionary[written], "dictionary")
            i = j + 1
            continue

        surface, reading = tokens[i]
        # 2. Numbers, joined with a following counter when there is one.
        if _NUMBER.fullmatch(unicodedata.normalize("NFKC", surface)):
            nxt = tokens[i + 1][0] if i + 1 < len(tokens) else ""
            counter = next((c for c in sorted(_COUNTERS, key=len, reverse=True) if nxt.startswith(c)), None)
            value = unicodedata.normalize("NFKC", surface)
            if counter and nxt == counter:
                default, special = _COUNTERS[counter]
                whole = special.get(int(float(value))) if "." not in value else None
                emit(surface + nxt, whole or number_reading(value) + default, "number")
                i += 2
            else:
                emit(surface, number_reading(value), "number")
                i += 1
            continue
        # 3. Kanji words: use the analyser's reading.
        if _KANJI.search(surface):
            if reading and reading != "*":
                emit(surface, _hiragana(reading), "analyzer")
            else:
                out.unknown.append(surface)
                emit(surface, surface, "unknown")
        else:
            emit(surface, surface, "kept")
        i += 1


def display_alignment(alignment: dict[str, Any], spoken: SpokenText) -> dict[str, Any] | None:
    """Map ElevenLabs character timings of the spoken text onto the written text.

    Returns an alignment dict in the same shape (characters / start / end lists),
    or None when the service normalised the spoken text so indices no longer match.
    """
    if "".join(alignment["characters"]) != spoken.spoken:
        return None
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    chars, st, en = [], [], []
    last_end = 0.0
    for ch, (a, b) in zip(spoken.written, spoken.span):
        if b > a:
            st.append(starts[a])
            en.append(ends[b - 1])
            last_end = ends[b - 1]
        else:  # written character with no spoken counterpart
            st.append(last_end)
            en.append(last_end)
        chars.append(ch)
    return {"characters": chars, "character_start_times_seconds": st, "character_end_times_seconds": en}
