"""Text normalisation for noisy speech-recognition output in tonal and accented languages."""
import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")


def strip_marks(text: str) -> str:
    """Remove tone marks, accents and underdots: "Orí mi fọ́ mi" -> "Ori mi fo mi"."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Lower-case, strip tone marks and punctuation, collapse spaces.

    >>> normalize("Orí mi ń fọ́ mi!")
    'ori mi n fo mi'
    """
    return _SPACE.sub(" ", _PUNCT.sub(" ", strip_marks(text))).lower().strip()
