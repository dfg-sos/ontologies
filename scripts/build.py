"""Check the vocabularies, build the GitHub Pages site, and make release copies.

    uv run scripts/build.py check            # consistency checks only
    uv run scripts/build.py build            # checks, then write the site to _site/
    uv run scripts/build.py release eo-formats 1.0.0

Only the RDF/XML files (`<name>.owl` and `releases/<name>/<version>/<name>.owl`) are committed.
The site (Turtle, HTML and the .owl files themselves) is generated from them into _site/ by CI.
"""

from __future__ import annotations

import argparse
import html
import shutil
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
BASE = "https://dfg-sos.github.io/ontologies/"
VOCABULARIES = ["eo-formats", "cwl"]
TERM_TYPES = [OWL.Class, OWL.DatatypeProperty, OWL.ObjectProperty, OWL.AnnotationProperty]
EXTERNAL_PARENTS = {OWL.Thing}


def load(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="xml")
    return graph


def ontology_iri(name: str) -> URIRef:
    return URIRef(BASE + name)


def namespace(name: str) -> str:
    return f"{BASE}{name}#"


def check(name: str, graph: Graph) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one vocabulary."""
    errors: list[str] = []
    warnings: list[str] = []
    ns = namespace(name)
    onto = ontology_iri(name)
    if (onto, RDF.type, OWL.Ontology) not in graph:
        errors.append(f"no owl:Ontology {onto}")
    for prop in (OWL.versionInfo, OWL.versionIRI, DCTERMS.title, DCTERMS.license):
        if graph.value(onto, prop) is None:
            errors.append(f"ontology header lacks {graph.qname(prop)}")
    version = graph.value(onto, OWL.versionInfo)
    expected_version_iri = URIRef(f"{BASE}releases/{name}/{version}/{name}.owl")
    if version is not None and graph.value(onto, OWL.versionIRI) != expected_version_iri:
        errors.append(f"owl:versionIRI should be {expected_version_iri}")

    declared = {s for t in TERM_TYPES for s in graph.subjects(RDF.type, t)}
    for term in sorted(declared):
        if not str(term).startswith(ns):
            errors.append(f"{term} is outside the namespace {ns}")
        if graph.value(term, RDFS.label) is None:
            errors.append(f"{local(term)} has no rdfs:label")
    classes = set(graph.subjects(RDF.type, OWL.Class))
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if parent not in classes and parent not in EXTERNAL_PARENTS:
            errors.append(f"{local(child)} rdfs:subClassOf undefined class {parent}")
    used = {p for p in graph.predicates() if str(p).startswith(ns)}
    for prop in sorted(used - declared):
        errors.append(f"property {prop} is used but not declared")
    for subject, obj in graph.subject_objects(RDFS.seeAlso):
        if isinstance(obj, Literal) and str(obj).startswith(("http://", "https://")):
            warnings.append(f"{local(subject)} rdfs:seeAlso is a literal URL, use rdf:resource: {obj}")
    return errors, warnings


def local(term: URIRef) -> str:
    text = str(term)
    return text.rsplit("#", 1)[-1] if "#" in text else text


def render_html(name: str, graph: Graph) -> str:
    onto = ontology_iri(name)
    title = str(graph.value(onto, DCTERMS.title) or name)
    description = str(graph.value(onto, DCTERMS.description) or "")
    version = str(graph.value(onto, OWL.versionInfo) or "")
    ns = namespace(name)

    def text(value: object) -> str:
        return html.escape(str(value))

    def link(value: object) -> str:
        value_s = str(value)
        if value_s.startswith(ns):
            return f'<a href="#{text(local(URIRef(value_s)))}">{text(local(URIRef(value_s)))}</a>'
        if value_s.startswith(("http://", "https://")):
            return f'<a href="{text(value_s)}">{text(value_s)}</a>'
        return text(value_s)

    def predicate_label(pred: URIRef) -> str:
        label = graph.value(pred, RDFS.label)
        return str(label) if label is not None else graph.qname(pred)

    sections = []
    for term_type, heading in ((OWL.Class, "Classes"), (OWL.DatatypeProperty, "Properties")):
        terms = sorted(graph.subjects(RDF.type, term_type), key=lambda t: local(t).lower())
        if not terms:
            continue
        rows = []
        for term in terms:
            props = []
            for pred, obj in sorted(graph.predicate_objects(term), key=lambda po: (str(po[0]), str(po[1]))):
                if pred in (RDF.type, RDFS.label):
                    continue
                props.append(f"<dt>{text(predicate_label(pred))}</dt><dd>{link(obj)}</dd>")
            children = sorted(graph.subjects(RDFS.subClassOf, term), key=local)
            if children:
                props.append("<dt>subclasses</dt><dd>" + ", ".join(link(c) for c in children) + "</dd>")
            rows.append(
                f'<section id="{text(local(term))}"><h3>{text(graph.value(term, RDFS.label) or local(term))}</h3>'
                f"<p><code>{text(term)}</code></p><dl>{''.join(props)}</dl></section>"
            )
        sections.append(f"<h2>{heading}</h2>" + "".join(rows))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{text(title)}</title>
<link rel="alternate" type="application/rdf+xml" href="{name}.owl">
<link rel="alternate" type="text/turtle" href="{name}.ttl">
<style>
:root {{ --fg: #1d1d1f; --muted: #5f6368; --bg: #fff; --line: #e3e3e3; --accent: #0b57d0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg: #e8eaed; --muted: #9aa0a6; --bg: #17181a; --line: #303134; --accent: #8ab4f8; }} }}
body {{ font: 16px/1.5 system-ui, sans-serif; color: var(--fg); background: var(--bg); max-width: 60rem; margin: 0 auto; padding: 1rem; }}
a {{ color: var(--accent); }} code {{ font-size: .9em; word-break: break-all; }}
section {{ border-top: 1px solid var(--line); padding: .5rem 0; }} section:target {{ background: color-mix(in srgb, var(--accent) 10%, transparent); }}
dl {{ display: grid; grid-template-columns: minmax(8rem, max-content) 1fr; gap: .2rem 1rem; margin: 0; }}
dt {{ color: var(--muted); }} dd {{ margin: 0; overflow-wrap: anywhere; }}
</style></head><body>
<h1>{text(title)}</h1>
<p>{text(description)}</p>
<p>Namespace <code>{text(ns)}</code> · version {text(version)} ·
<a href="{name}.owl">RDF/XML</a> · <a href="{name}.ttl">Turtle</a> ·
<a href="releases/{name}/{text(version)}/{name}.owl">this version (fixed)</a></p>
{"".join(sections)}
<p><small>Generated from {name}.owl by scripts/build.py.</small></p>
</body></html>
"""


def render_index(graphs: dict[str, Graph]) -> str:
    items = []
    for name, graph in graphs.items():
        onto = ontology_iri(name)
        title = html.escape(str(graph.value(onto, DCTERMS.title) or name))
        items.append(
            f'<li><a href="{name}">{title}</a> (<code>{html.escape(namespace(name))}</code>) · '
            f'<a href="{name}.owl">RDF/XML</a> · <a href="{name}.ttl">Turtle</a></li>'
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SOS vocabularies</title>
<style>
:root {{ --fg: #1d1d1f; --bg: #fff; --accent: #0b57d0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg: #e8eaed; --bg: #17181a; --accent: #8ab4f8; }} }}
body {{ font: 16px/1.5 system-ui, sans-serif; color: var(--fg); background: var(--bg); max-width: 60rem; margin: 0 auto; padding: 1rem; }}
a {{ color: var(--accent); }} code {{ font-size: .9em; word-break: break-all; }}
</style></head><body>
<h1>SOS vocabularies</h1>
<p>Vocabularies of the DFG project SOS. Source: <a href="https://github.com/dfg-sos/ontologies">github.com/dfg-sos/ontologies</a>.</p>
<ul>{"".join(items)}</ul>
</body></html>
"""


def build_site(graphs: dict[str, Graph]) -> None:
    """Write _site/: per vocabulary .owl, .ttl and .html; per release .owl and .ttl; an index."""
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    for name, graph in graphs.items():
        shutil.copy2(ROOT / f"{name}.owl", SITE / f"{name}.owl")
        (SITE / f"{name}.ttl").write_text(graph.serialize(format="turtle"))
        (SITE / f"{name}.html").write_text(render_html(name, graph))
    for owl in sorted(ROOT.glob("releases/*/*/*.owl")):
        target = SITE / owl.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(owl, target)
        target.with_suffix(".ttl").write_text(load(owl).serialize(format="turtle"))
    (SITE / "index.html").write_text(render_index(graphs))
    print(f"wrote   {SITE.relative_to(ROOT)}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("build")
    release = sub.add_parser("release")
    release.add_argument("name", choices=VOCABULARIES)
    release.add_argument("version")
    args = parser.parse_args()

    failed = False
    graphs = {}
    for name in VOCABULARIES:
        graphs[name] = graph = load(ROOT / f"{name}.owl")
        errors, warnings = check(name, graph)
        for w in warnings:
            print(f"warning [{name}] {w}")
        for e in errors:
            print(f"error   [{name}] {e}")
        failed |= bool(errors)
    if failed:
        return 1

    if args.command == "build":
        build_site(graphs)
    elif args.command == "release":
        graph = graphs[args.name]
        version = str(graph.value(ontology_iri(args.name), OWL.versionInfo))
        if version != args.version:
            print(f"error   {args.name}.owl has owl:versionInfo {version}, not {args.version}")
            return 1
        target = ROOT / "releases" / args.name / args.version
        if target.exists():
            print(f"error   {target.relative_to(ROOT)} exists; released versions are never changed")
            return 1
        target.mkdir(parents=True)
        shutil.copy2(ROOT / f"{args.name}.owl", target / f"{args.name}.owl")
        print(f"wrote   {target.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
