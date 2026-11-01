"""Generate and load a text bank with `python -m app.commands.load_texts`."""

from __future__ import annotations

import argparse

from app.services.texts_handler import TextFacade
from app.services.texts_handler.load import load_phrases
from app.text_constants import DEFAULT_TEXT_LANGUAGE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and load typing phrases")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and classify without database access"
    )
    args = parser.parse_args(argv)
    phrases = TextFacade().generate_phrases()
    if args.dry_run:
        summary = load_phrases(phrases, DEFAULT_TEXT_LANGUAGE, dry_run=True)
    else:
        from app.database import SessionLocal

        with SessionLocal() as db:
            summary = load_phrases(phrases, DEFAULT_TEXT_LANGUAGE, dry_run=False, db=db)
    print(
        f"generated={summary.generated} stored={summary.stored} "
        f"duplicates={summary.duplicates} rejected={summary.rejected} "
        f"dry_run_accepted={summary.accepted_in_dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
