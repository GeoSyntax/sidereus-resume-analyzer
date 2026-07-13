import re


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MULTI_SPACE = re.compile(r"[ \t\u3000]+")
PAGE_NOISE = re.compile(r"^\s*(page\s*)?\d+\s*/\s*\d+\s*$", re.IGNORECASE)


def clean_text(text: str) -> str:
    text = CONTROL_CHARS.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\uf0b7", " ")

    cleaned_lines: list[str] = []
    previous_blank = False
    for raw_line in text.split("\n"):
        line = MULTI_SPACE.sub(" ", raw_line).strip()
        if PAGE_NOISE.match(line):
            continue
        if not line:
            if not previous_blank and cleaned_lines:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False

    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def split_sections(text: str, max_sections: int = 20) -> list[str]:
    sections = [section.strip() for section in re.split(r"\n\s*\n", text) if section.strip()]
    if len(sections) <= max_sections:
        return sections

    merged: list[str] = []
    current: list[str] = []
    for section in sections:
        current.append(section)
        if len("\n".join(current)) > 700:
            merged.append("\n".join(current))
            current = []
        if len(merged) >= max_sections - 1:
            break
    if current:
        merged.append("\n".join(current))
    return merged[:max_sections]

