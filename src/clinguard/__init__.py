"""ClinGuard: safety-first building blocks for clinical voice AI in low-resource languages and dialects."""
from .normalize import normalize, strip_marks
from .lexicon import Entry, Lexicon, Match
from .safety import DangerRules, STARTER_ENGLISH_KEYWORDS
from .learning import SuggestionStore
from .pipeline import Assessment, ClinGuard, HIGH, LOW, NONE

__version__ = "0.1.0"

__all__ = [
    "normalize", "strip_marks",
    "Entry", "Lexicon", "Match",
    "DangerRules", "STARTER_ENGLISH_KEYWORDS",
    "SuggestionStore",
    "Assessment", "ClinGuard", "HIGH", "LOW", "NONE",
    "__version__",
]
