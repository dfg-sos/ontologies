"""Check the vocabularies, build the GitHub Pages site, and make release copies.

    uv run scripts/build.py check                      # consistency checks only
    uv run scripts/build.py build                      # checks, then write the site to _site/
    uv run scripts/build.py release eo-formats 1.1.0   # immutable copy of the current version
    uv run scripts/build.py --require-releases build   # CI on main: the current versions must be released

The Turtle sources `<name>.ttl` are edited. A release writes its fixed copy
`releases/<name>/<version>/<name>.owl` (RDF/XML, generated) and `<name>.ttl` next to it; both are
committed and never change. The site (the latest `<name>.owl`, HTML) is generated into _site/ by CI.
The code lives in scripts/vocab/: model.py, checks.py and site.py.
"""

from __future__ import annotations

import argparse
import shutil
import sys

from vocab.checks import check
from vocab.model import ROOT, VOCABULARIES, Vocabulary, load_all, to_rdf_xml
from vocab.site import build_site


def release(vocab: Vocabulary, version: str) -> int:
    if vocab.version != version:
        print(f"error   {vocab.name}.ttl has owl:versionInfo {vocab.version}, not {version}")
        return 1
    target = vocab.release_dir(version)
    if target.exists():
        print(f"error   {target.relative_to(ROOT)} exists; released versions are never changed")
        return 1
    target.mkdir(parents=True)
    vocab.release_source(version).write_text(to_rdf_xml(vocab.graph))
    shutil.copy2(vocab.source, vocab.release_turtle(version))
    print(f"wrote   {target.relative_to(ROOT)}/ ({vocab.name}.owl and {vocab.name}.ttl)")
    return 0


def check_all(vocabularies: dict[str, Vocabulary], require_released: bool) -> bool:
    """Print every warning and error; True if there is no error."""
    ok = True
    for vocab in vocabularies.values():
        report = check(vocab, vocabularies, require_released)
        for warning in report.warnings:
            print(f"warning [{vocab.name}] {warning}")
        for error in report.errors:
            print(f"error   [{vocab.name}] {error}")
        ok &= not report.errors
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the vocabularies, build the site, and make release copies.")
    parser.add_argument("--require-releases", action="store_true", help="fail if a current version has no release copy")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("build")
    release_parser = sub.add_parser("release")
    release_parser.add_argument("name", choices=VOCABULARIES)
    release_parser.add_argument("version")
    args = parser.parse_args()

    vocabularies = load_all()
    # A release is made from a version that is not released yet, so it cannot be required then.
    if not check_all(vocabularies, args.require_releases and args.command != "release"):
        return 1
    if args.command == "build":
        build_site(vocabularies)
    elif args.command == "release":
        return release(vocabularies[args.name], args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
