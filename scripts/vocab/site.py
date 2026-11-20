"""The GitHub Pages site: per vocabulary the latest version and every release, as .owl, .ttl and HTML."""

from __future__ import annotations

import html
import shutil
from pathlib import Path

from rdflib import OWL, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS
from rdflib.term import Node

from .model import ROOT, Vocabulary, local, pinned_release, to_rdf_xml, uris

SITE = ROOT / "_site"
STYLE = Path(__file__).with_name("style.css")
SECTIONS = [
    (OWL.Class, "Classes"),
    (OWL.ObjectProperty, "Properties"),
    (OWL.DatatypeProperty, "Properties (values)"),
    (OWL.AnnotationProperty, "Annotation properties"),
]


def esc(value: object) -> str:
    return html.escape(str(value))


def page(title: str, body: str, root: str, head: str = "") -> str:
    """`root` is the relative path from the page to the site root."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>{head}
<link rel="stylesheet" href="{root}style.css"></head><body>
{body}
</body></html>
"""


def version_links(vocab: Vocabulary, root: str) -> str:
    links = [f'<a href="{root}releases/{vocab.name}/{v}/">{v}</a>' for v in vocab.releases]
    return ", ".join(links) or "none yet"


class Renderer:
    """Renders one version of a vocabulary. `root` is the relative path to the site root."""

    def __init__(self, vocab: Vocabulary, vocabularies: dict[str, Vocabulary], root: str) -> None:
        self.vocab, self.vocabularies, self.root = vocab, vocabularies, root

    def link(self, value: Node) -> str:
        text, name = str(value), esc(local(value))
        if text.startswith(self.vocab.namespace):
            return f'<a href="#{name}">{name}</a>'
        for other in self.vocabularies.values():
            if text.startswith(other.namespace):
                return f'<a href="{self.root}{other.name}#{name}">{esc(other.name)}:{name}</a>'
        if text.startswith(("http://", "https://")):
            return f'<a href="{esc(text)}">{esc(text)}</a>'
        return esc(text)

    def label(self, pred: Node) -> str:
        for graph in (self.vocab.graph, *(v.graph for v in self.vocabularies.values())):
            found = graph.value(pred, RDFS.label)
            if found is not None:
                return str(found)
        try:
            return self.vocab.graph.qname(str(pred))
        except ValueError:
            return str(pred)

    def term(self, term: URIRef) -> str:
        graph = self.vocab.graph
        rows = [
            f"<dt>{esc(self.label(pred))}</dt><dd>{self.link(obj)}</dd>"
            for pred, obj in sorted(graph.predicate_objects(term), key=lambda po: (str(po[0]), str(po[1])))
            if pred not in (RDF.type, RDFS.label)
        ]
        children = sorted(uris(graph.subjects(RDFS.subClassOf, term)), key=local)
        if children:
            rows.append("<dt>subclasses</dt><dd>" + ", ".join(self.link(c) for c in children) + "</dd>")
        # Links to this term from other terms, e.g. the measures that apply to a format.
        incoming: dict[str, list[URIRef]] = {}
        for subject, pred in graph.subject_predicates(term):
            if pred not in (RDF.type, RDFS.subClassOf) and isinstance(subject, URIRef):
                incoming.setdefault(self.label(pred), []).append(subject)
        for label, subjects in sorted(incoming.items()):
            links = ", ".join(self.link(s) for s in sorted(subjects, key=local))
            rows.append(f"<dt>{esc(label)} (inverse)</dt><dd>{links}</dd>")
        return (
            f'<section id="{esc(local(term))}"><h3>{esc(graph.value(term, RDFS.label) or local(term))}</h3>'
            f"<p><code>{esc(term)}</code></p><dl>{''.join(rows)}</dl></section>"
        )

    def sections(self) -> str:
        out = []
        for term_type, heading in SECTIONS:
            terms = sorted(uris(self.vocab.graph.subjects(RDF.type, term_type)), key=lambda t: local(t).lower())
            if terms:
                out.append(f"<h2>{heading}</h2>" + "".join(self.term(t) for t in terms))
        return "".join(out)

    def imports(self) -> str:
        links = []
        for iri in sorted(self.vocab.imports):
            pinned = pinned_release(iri)
            if pinned:
                links.append(f'<a href="{self.root}releases/{pinned[0]}/{pinned[1]}/">{pinned[0]} {pinned[1]}</a>')
            else:
                links.append(f'<a href="{esc(iri)}">{esc(iri)}</a>')
        return f"<p>Imports {', '.join(links)}.</p>" if links else ""

    def status(self, latest: Vocabulary) -> str:
        vocab, name, root = self.vocab, self.vocab.name, self.root
        if root:
            return (
                f'<p class="note">Release {esc(vocab.version)}, fixed: this file never changes. '
                f'Latest version: <a href="{root}{name}">{esc(latest.version)}</a>.</p>'
            )
        fixed = (
            f'<a href="releases/{name}/{esc(vocab.version)}/{name}.owl">fixed copy</a>'
            if vocab.version in vocab.releases
            else "not released yet"
        )
        return (
            f'<p class="note">Latest version {esc(vocab.version)} ({fixed}). '
            f"<code>{name}.owl</code> always serves the latest version and only grows: terms are never "
            f"removed or moved. To pin a version, use its release copy.</p>"
        )

    def render(self, latest: Vocabulary) -> str:
        """`latest` is the current version of the vocabulary; a release page links to it."""
        vocab, name, root = self.vocab, self.vocab.name, self.root
        title = vocab.header(DCTERMS.title) or name
        body = f"""<h1>{esc(title)}</h1>
{self.status(latest)}
<p>{esc(vocab.header(DCTERMS.description))}</p>
<p>Namespace <code>{esc(vocab.namespace)}</code> · version {esc(vocab.version)} ·
<a href="{name}.owl">RDF/XML</a> · <a href="{name}.ttl">Turtle</a></p>
<p>Releases: {version_links(latest, root)}</p>
{self.imports()}
{self.sections()}
<p><small>Generated by scripts/build.py. <a href="{root}">All vocabularies</a>.</small></p>"""
        head = (
            f'\n<link rel="alternate" type="application/rdf+xml" href="{name}.owl">'
            f'\n<link rel="alternate" type="text/turtle" href="{name}.ttl">'
        )
        return page(title, body, root, head)


def render_index(vocabularies: dict[str, Vocabulary]) -> str:
    rows = []
    for vocab in vocabularies.values():
        name = vocab.name
        rows.append(
            f'<tr><td><a href="{name}">{esc(vocab.header(DCTERMS.title) or name)}</a><br>'
            f"<code>{esc(vocab.namespace)}</code></td>"
            f'<td>{esc(vocab.version)}<br><a href="{name}.owl">RDF/XML</a> · <a href="{name}.ttl">Turtle</a></td>'
            f"<td>{version_links(vocab, '')}</td></tr>"
        )
    body = f"""<h1>SOS vocabularies</h1>
<p>Vocabularies of the DFG project SOS. Source: <a href="https://github.com/dfg-sos/ontologies">github.com/dfg-sos/ontologies</a>.</p>
<p><code>&lt;name&gt;.owl</code> is the latest version. Each release has a fixed copy at
<code>releases/&lt;name&gt;/&lt;version&gt;/&lt;name&gt;.owl</code> that never changes.</p>
<table><thead><tr><th>Vocabulary</th><th>Latest</th><th>Releases</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>"""
    return page("SOS vocabularies", body, "")


def write(target: Path, content: Path | str) -> None:
    """Copy a file or write a text to `target`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, Path):
        shutil.copy2(content, target)
    else:
        target.write_text(content)


def build_site(vocabularies: dict[str, Vocabulary]) -> None:
    """Write _site/: per vocabulary its latest version as <name>.owl (generated), <name>.ttl (the
    source) and <name>.html, and per release releases/<name>/<version>/ with the committed .owl, its
    .ttl and index.html; plus index.html and style.css."""
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    write(SITE / "style.css", STYLE)
    for vocab in vocabularies.values():
        name = vocab.name
        write(SITE / f"{name}.owl", to_rdf_xml(vocab.graph))
        write(SITE / f"{name}.ttl", vocab.source)
        write(SITE / f"{name}.html", Renderer(vocab, vocabularies, "").render(vocab))
        for version in vocab.releases:
            released, target = vocab.release(version), SITE / "releases" / name / version
            turtle = vocab.release_turtle(version)
            write(target / f"{name}.owl", vocab.release_source(version))
            write(target / f"{name}.ttl", turtle if turtle.exists() else released.graph.serialize(format="turtle"))
            write(target / "index.html", Renderer(released, vocabularies, "../../../").render(vocab))
    (SITE / "index.html").write_text(render_index(vocabularies))
    print(f"wrote   {SITE.relative_to(ROOT)}/")
