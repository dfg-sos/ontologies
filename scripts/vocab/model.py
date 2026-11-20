"""The vocabularies of this repository: `<name>.owl` (the current version) and its release copies."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://dfg-sos.github.io/ontologies/"
VOCABULARIES = ["eo-formats", "cwl", "resource-demand"]
TERM_TYPES = [OWL.Class, OWL.DatatypeProperty, OWL.ObjectProperty, OWL.AnnotationProperty]
VERSION = re.compile(r"\d+\.\d+\.\d+")
RELEASE_IRI = re.compile(re.escape(BASE) + r"releases/([a-z0-9-]+)/(\d+\.\d+\.\d+)/\1\.owl")


def load(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="xml")
    return graph


def uris(nodes: Iterable[Node]) -> set[URIRef]:
    return {node for node in nodes if isinstance(node, URIRef)}


def declared(graph: Graph) -> set[URIRef]:
    """Classes and properties declared in `graph`."""
    return uris(s for t in TERM_TYPES for s in graph.subjects(RDF.type, t))


def local(term: Node) -> str:
    text = str(term)
    return text.rsplit("#", 1)[-1] if "#" in text else text


def pinned_release(iri: str) -> tuple[str, str] | None:
    """(name, version) if `iri` is the release copy of a vocabulary of this repository."""
    match = RELEASE_IRI.fullmatch(iri)
    return (match[1], match[2]) if match else None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@dataclass
class Vocabulary:
    """One version of a vocabulary."""

    name: str
    graph: Graph = field(repr=False)

    @property
    def iri(self) -> URIRef:
        return URIRef(BASE + self.name)

    @property
    def namespace(self) -> str:
        return f"{BASE}{self.name}#"

    def header(self, prop: URIRef) -> str:
        return str(self.graph.value(self.iri, prop) or "")

    @property
    def version(self) -> str:
        return self.header(OWL.versionInfo)

    @cached_property
    def terms(self) -> set[URIRef]:
        return declared(self.graph)

    @property
    def imports(self) -> set[str]:
        return {str(o) for o in self.graph.objects(self.iri, OWL.imports)}

    @property
    def source(self) -> Path:
        return ROOT / f"{self.name}.owl"

    def release_dir(self, version: str) -> Path:
        return ROOT / "releases" / self.name / version

    def release_source(self, version: str) -> Path:
        return self.release_dir(version) / f"{self.name}.owl"

    def release_iri(self, version: str) -> URIRef:
        return URIRef(f"{BASE}releases/{self.name}/{version}/{self.name}.owl")

    @cached_property
    def releases(self) -> list[str]:
        """Released versions, newest first."""
        found = [p.parent.name for p in (ROOT / "releases" / self.name).glob(f"*/{self.name}.owl")]
        return sorted((v for v in found if VERSION.fullmatch(v)), key=version_key, reverse=True)

    def release(self, version: str) -> Vocabulary:
        return Vocabulary(self.name, load(self.release_source(version)))


def load_all() -> dict[str, Vocabulary]:
    """The current version of every vocabulary, by name."""
    return {name: Vocabulary(name, load(ROOT / f"{name}.owl")) for name in VOCABULARIES}
