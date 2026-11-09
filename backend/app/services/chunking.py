import re


def chunk_text(text: str, max_chars: int = 600, overlap: int = 100) -> list[str]:
    """Split a CV into retrieval chunks.

    Paragraphs (blank-line separated blocks) are packed together up to ``max_chars``.
    A paragraph longer than ``max_chars`` is cut into windows that overlap by ``overlap``
    characters, so a sentence on the boundary is still searchable.
    """
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = re.sub(r"[ \t]+", " ", paragraph)
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            step = max_chars - overlap
            chunks.extend(
                paragraph[i : i + max_chars] for i in range(0, len(paragraph) - overlap, step)
            )
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks
