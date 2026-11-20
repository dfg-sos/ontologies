"""Consistency checks of one vocabulary against itself, the other vocabularies and its releases."""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import OWL, RDF, RDFS, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS

from .model import BASE, VERSION, Vocabulary, local, pinned_release, uris, version_key

HEADER_PROPERTIES = [OWL.versionInfo, OWL.versionIRI, DCTERMS.title, DCTERMS.license]
EXTERNAL_PARENTS = {OWL.Thing}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check(vocab: Vocabulary, vocabularies: dict[str, Vocabulary], require_released: bool = False) -> Report:
    report = Report()
    check_header(vocab, report)
    check_terms(vocab, report)
    check_references(vocab, vocabularies, report)
    check_releases(vocab, report, require_released)
    return report


def check_header(vocab: Vocabulary, report: Report) -> None:
    if (vocab.iri, RDF.type, OWL.Ontology) not in vocab.graph:
        report.errors.append(f"no owl:Ontology {vocab.iri}")
    for prop in HEADER_PROPERTIES:
        if not vocab.header(prop):
            report.errors.append(f"ontology header lacks {vocab.graph.qname(prop)}")
    if not VERSION.fullmatch(vocab.version):
        report.errors.append(f"owl:versionInfo {vocab.version!r} is not MAJOR.MINOR.PATCH")
    elif vocab.graph.value(vocab.iri, OWL.versionIRI) != vocab.release_iri(vocab.version):
        report.errors.append(f"owl:versionIRI should be {vocab.release_iri(vocab.version)}")


def check_terms(vocab: Vocabulary, report: Report) -> None:
    for term in sorted(vocab.terms, key=str):
        if not term.startswith(vocab.namespace):
            report.errors.append(f"{term} is outside the namespace {vocab.namespace}")
        if vocab.graph.value(term, RDFS.label) is None:
            report.errors.append(f"{local(term)} has no rdfs:label")
    used = uris(p for p in vocab.graph.predicates() if str(p).startswith(vocab.namespace))
    for prop in sorted(used - vocab.terms, key=str):
        report.errors.append(f"property {prop} is used but not declared")
    for subject, obj in vocab.graph.subject_objects(RDFS.seeAlso):
        if isinstance(obj, Literal) and str(obj).startswith(("http://", "https://")):
            report.warnings.append(f"{local(subject)} rdfs:seeAlso is a literal URL, use rdf:resource: {obj}")


def imported(vocab: Vocabulary, vocabularies: dict[str, Vocabulary], report: Report) -> list[Vocabulary]:
    """The versions of the SOS vocabularies that `vocab` imports. An import must be a release
    copy (the vocabulary IRI serves HTML), or the current version if it is released together."""
    result = []
    for iri in sorted(i for i in vocab.imports if i.startswith(BASE)):
        pinned = pinned_release(iri)
        other = vocabularies.get(pinned[0]) if pinned else None
        if pinned is None or other is None:
            report.errors.append(f"owl:imports {iri}: import a release copy, {BASE}releases/<name>/<version>/<name>.owl")
            continue
        name, version = pinned
        if version in other.releases:
            result.append(other.release(version))
        elif version == other.version:
            result.append(other)
        else:
            report.errors.append(f"owl:imports {name} {version}, which is neither released nor the current version")
            continue
        if version != other.version:
            report.warnings.append(f"imports {name} {version}; the latest version is {other.version}")
    return result


def check_references(vocab: Vocabulary, vocabularies: dict[str, Vocabulary], report: Report) -> None:
    """A term of another SOS vocabulary (a parent class, an annotation value) must be declared
    there, and only if this vocabulary imports it."""
    scope = [vocab, *imported(vocab, vocabularies, report)]
    known = {t for v in scope for t in v.terms}
    classes = {c for v in scope for c in uris(v.graph.subjects(RDF.type, OWL.Class))}
    for child, parent in vocab.graph.subject_objects(RDFS.subClassOf):
        if parent not in classes and parent not in EXTERNAL_PARENTS:
            report.errors.append(f"{local(child)} rdfs:subClassOf undefined class {parent} (not declared or not imported)")
    for subject, obj in vocab.graph.subject_objects():
        if isinstance(obj, URIRef) and obj.startswith(BASE) and "#" in obj and obj not in known:
            report.errors.append(f"{local(subject)} refers to {obj}, which is not declared here or in an imported vocabulary")


def check_releases(vocab: Vocabulary, report: Report, require_released: bool) -> None:
    """`<name>.owl` is served as the latest version, so it may only grow: every term of every
    release stays declared (deprecate with owl:deprecated instead of removing) and keeps its parents."""
    if not VERSION.fullmatch(vocab.version):
        return
    if vocab.version not in vocab.releases:
        message = f"version {vocab.version} is not released: run scripts/build.py release {vocab.name} {vocab.version}"
        (report.errors if require_released else report.warnings).append(message)
    for version in vocab.releases:
        old = vocab.release(version)
        if version == vocab.version:
            if not isomorphic(old.graph, vocab.graph):
                report.errors.append(f"{vocab.name}.owl differs from release {version}: raise owl:versionInfo")
            continue
        if version_key(version) > version_key(vocab.version):
            report.errors.append(f"owl:versionInfo {vocab.version} is lower than release {version}")
        for term in sorted(old.terms - vocab.terms, key=str):
            report.errors.append(f"{local(term)} of release {version} was removed; mark it owl:deprecated instead")
        for child, parent in old.graph.subject_objects(RDFS.subClassOf):
            if (child, RDFS.subClassOf, parent) not in vocab.graph:
                report.errors.append(f"{local(child)} is no longer rdfs:subClassOf {local(parent)} (release {version})")
