"""Command line:  clinguard check LEXICON "text"   |   clinguard validate LEXICON"""
import argparse
import json
import sys

from . import __version__
from .lexicon import Lexicon
from .pipeline import ClinGuard
from .safety import DangerRules


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="clinguard", description=__doc__)
    parser.add_argument("--version", action="version", version=f"clinguard {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Assess one transcribed sentence against a lexicon")
    check.add_argument("lexicon", help="Lexicon file (.json or .csv)")
    check.add_argument("text", help="What the patient said (speech-recognition output)")
    check.add_argument("--rules", help="Danger-sign rules file (.json)")
    check.add_argument("--language", default="", help="Language code, e.g. yo")
    check.add_argument("--threshold", type=float, default=0.75)

    validate = sub.add_parser("validate", help="Check a lexicon for clashing entries")
    validate.add_argument("lexicon")
    validate.add_argument("--threshold", type=float, default=0.75)

    args = parser.parse_args(argv)
    lexicon = Lexicon.from_file(args.lexicon, threshold=args.threshold)

    if args.command == "validate":
        problems = lexicon.self_check()
        print(f"{len(lexicon)} entries checked, {len(problems)} problem(s).")
        for p in problems:
            print("  -", p)
        return 1 if problems else 0

    rules = DangerRules.from_file(args.rules) if args.rules else DangerRules()
    a = ClinGuard(lexicon, rules, language=args.language).assess(args.text)
    print(json.dumps({
        "said": a.said, "meaning": a.meaning, "clinical_term": a.clinical_term,
        "confidence": a.confidence, "score": round(a.score, 2),
        "danger": a.danger, "danger_reasons": a.danger_reasons,
        "needs_review": a.needs_review, "banners": a.banners(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
