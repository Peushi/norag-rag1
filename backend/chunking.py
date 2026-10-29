def chunk_text(text, chunk_size=800, overlap=80):
    """split text into fixed-size chunks with overlapping characters."""

    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Overlap must be between 0 and chunk_size - 1")

    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]

        if chunk.strip():
            chunks.append(
                {
                    "text": chunk,
                    "start": start,
                    "position": len(chunks),
                }
            )

        if start + chunk_size >= len(text):
            break

    return chunks
