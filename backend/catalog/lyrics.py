import re

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
