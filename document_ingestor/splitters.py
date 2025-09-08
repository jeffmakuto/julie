from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class SplitOptions:
    chunk_size: int = 1000
    chunk_overlap: int = 150
    length_function = len


class SimpleSplitter:
    def __init__(self, opts: SplitOptions):
        self.opts = opts

    def split_text(self, text: str) -> List[str]:
        size = self.opts.chunk_size
        overlap = self.opts.chunk_overlap
        if size <= 0:
            raise ValueError("chunk_size must be > 0")

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if len(text) <= size:
            return [text]

        chunks: List[str] = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + size
            if end >= text_len:
                chunks.append(text[start:text_len].strip())
                break

            # try to find newline or punctuation boundary
            split_at = text.rfind("\n", start, end)
            if split_at == -1:
                for delim in ('.', '!', '?', ';'):
                    split_at = text.rfind(delim, start, end)
                    if split_at != -1:
                        split_at += 1
                        break
            if split_at == -1 or split_at <= start:
                split_at = end

            chunk = text[start:split_at].strip()
            chunks.append(chunk)
            start = max(split_at - overlap, split_at)
        return chunks