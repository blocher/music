import re
from difflib import SequenceMatcher

TIMESTAMP = re.compile(r"\[(?P<minutes>\d{1,3}):(?P<seconds>\d{2})(?:[.:](?P<fraction>\d{1,3}))?\]")


def parse_lrc(value: str) -> list[dict]:
    cues = []
    for line in value.splitlines():
        matches = list(TIMESTAMP.finditer(line))
        if not matches:
            continue
        text = TIMESTAMP.sub("", line).strip()
        for match in matches:
            fraction = (match.group("fraction") or "0").ljust(3, "0")[:3]
            start_ms = (int(match.group("minutes")) * 60 + int(match.group("seconds"))) * 1000 + int(fraction)
            cues.append({"start_ms": start_ms, "end_ms": None, "text": text, "words": []})
    cues.sort(key=lambda cue: cue["start_ms"])
    for index, cue in enumerate(cues[:-1]):
        cue["end_ms"] = max(cue["start_ms"], cues[index + 1]["start_ms"] - 1)
    return cues


def to_lrc(cues: list[dict]) -> str:
    lines = []
    for cue in cues:
        total = int(cue.get("start_ms", 0))
        minutes, remainder = divmod(total, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        lines.append(f"[{minutes:02d}:{seconds:02d}.{milliseconds // 10:02d}]{cue.get('text', '')}")
    return "\n".join(lines)


def _milliseconds(value) -> int:
    return max(0, round(float(value or 0) * 1000))


def normalize_suno_alignment(payload: dict) -> tuple[list[dict], dict]:
    """Normalize Suno's seconds-based alignment into the app's millisecond schema."""
    source = payload.get("aligned_lyrics") or payload.get("lyrics") or []
    cues = []
    for line in source:
        if not isinstance(line, dict):
            continue
        start_ms = line.get("start_ms")
        end_ms = line.get("end_ms")
        if start_ms is None:
            start_ms = _milliseconds(line.get("start_s") or line.get("start"))
        if end_ms is None and (line.get("end_s") is not None or line.get("end") is not None):
            end_ms = _milliseconds(line.get("end_s") if line.get("end_s") is not None else line.get("end"))
        words = []
        for word in line.get("words") or []:
            if not isinstance(word, dict):
                continue
            words.append(
                {
                    "text": word.get("text") or word.get("word") or "",
                    "start_ms": word.get("start_ms", _milliseconds(word.get("start_s") or word.get("start"))),
                    "end_ms": word.get("end_ms", _milliseconds(word.get("end_s") or word.get("end"))),
                }
            )
        cues.append(
            {
                "start_ms": int(start_ms or 0),
                "end_ms": int(end_ms) if end_ms is not None else None,
                "text": line.get("text") or line.get("lyric") or "",
                "words": words,
                **({"section": line["section"]} if line.get("section") else {}),
            }
        )
    cues.sort(key=lambda cue: cue["start_ms"])
    confidence = 1.0
    if payload.get("hoot_cer") is not None:
        confidence = max(0.0, min(1.0, 1.0 - float(payload["hoot_cer"])))
    complete = bool(cues) and all(cue["text"].strip() and cue["end_ms"] is not None for cue in cues)
    return cues, {"confidence": confidence, "complete": complete, "line_count": len(cues), "hoot_cer": payload.get("hoot_cer")}


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9']", "", value.lower())


def lyric_text_similarity(cues: list[dict], lyrics: str) -> float:
    expected = [_token(word) for word in lyrics.split() if _token(word)]
    aligned = [_token(word) for cue in cues for word in str(cue.get("text", "")).split() if _token(word)]
    if not expected or not aligned:
        return 1.0 if aligned else 0.0
    return round(SequenceMatcher(None, expected, aligned, autojunk=False).ratio(), 4)


def align_transcription_to_lyrics(transcription: dict, lyrics: str) -> tuple[list[dict], float]:
    """Map canonical lyric lines onto OpenAI word timestamps.

    Exact/matching words anchor the result; unmatched words interpolate from
    their nearest anchors so edited lyrics still receive reviewable timing.
    """
    transcript_words = [
        {
            "text": str(word.get("word") or word.get("text") or "").strip(),
            "start_ms": _milliseconds(word.get("start")),
            "end_ms": _milliseconds(word.get("end")),
        }
        for word in transcription.get("words", [])
        if _token(str(word.get("word") or word.get("text") or ""))
    ]
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    if not lines:
        lines = [str(segment.get("text", "")).strip() for segment in transcription.get("segments", []) if str(segment.get("text", "")).strip()]
    lyric_words = []
    line_ranges = []
    for line in lines:
        start = len(lyric_words)
        lyric_words.extend([word for word in line.split() if _token(word)])
        line_ranges.append((start, len(lyric_words), line))
    if not transcript_words or not lyric_words:
        return [], 0.0

    matcher = SequenceMatcher(None, [_token(word) for word in lyric_words], [_token(word["text"]) for word in transcript_words], autojunk=False)
    mapping = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapping[block.a + offset] = block.b + offset

    duration = max(transcript_words[-1]["end_ms"], 1)
    cues = []
    for line_start, line_end, line in line_ranges:
        matched = [mapping[index] for index in range(line_start, line_end) if index in mapping]
        if matched:
            first, last = min(matched), max(matched)
        else:
            first = min(len(transcript_words) - 1, round(line_start / max(len(lyric_words), 1) * len(transcript_words)))
            last = min(len(transcript_words) - 1, max(first, round(line_end / max(len(lyric_words), 1) * len(transcript_words)) - 1))
        start_ms = transcript_words[first]["start_ms"]
        end_ms = transcript_words[last]["end_ms"] or min(duration, start_ms + 1000)
        words = []
        for lyric_index in range(line_start, line_end):
            transcript_index = mapping.get(lyric_index)
            if transcript_index is not None:
                timed = transcript_words[transcript_index]
                words.append({"text": lyric_words[lyric_index], "start_ms": timed["start_ms"], "end_ms": timed["end_ms"]})
        cues.append({"start_ms": start_ms, "end_ms": end_ms, "text": line, "words": words})
    return cues, round(matcher.ratio(), 4)


def timed_lyrics_payload(track) -> dict:
    from django.contrib.contenttypes.models import ContentType

    from .models import PlatformLink

    links = PlatformLink.objects.filter(content_type=ContentType.objects.get_for_model(track), object_id=str(track.pk))
    return {
        "artist": track.artist.name,
        "title": track.title,
        "release_date": track.release_date.isoformat() if track.release_date else None,
        "isrc": track.isrc,
        "too_lost_track_id": track.too_lost_track_id,
        "plain_lyrics": track.lyrics,
        "timed_lyrics": track.timed_lyrics,
        "platform_ids": {link.platform: link.external_id for link in links if link.external_id},
    }
