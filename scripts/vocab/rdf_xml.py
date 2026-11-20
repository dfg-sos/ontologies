"""Deterministic RDF/XML for the published .owl files.

rdflib's RDF/XML output depends on Python's hash seed (order of prefixes and subjects), so the same
graph gives different bytes on every build. This writer sorts everything: the ontology header first,
then the terms by type and IRI, their properties in a fixed order. It handles what the vocabularies
use: IRIs and literals (plain, typed, language-tagged), no blank nodes.
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

TYPE_ORDER = [OWL.Ontology, OWL.AnnotationProperty, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Class]
PREDICATE_ORDER = [
    OWL.versionInfo, OWL.versionIRI, OWL.priorVersion, OWL.imports,
    DCTERMS.title, RDFS.label, RDFS.subClassOf, DCTERMS.description, RDFS.comment,
]  # fmt: skip
CORE = {"rdf": str(RDF), "rdfs": str(RDFS), "owl": str(OWL), "xsd": "http://www.w3.org/2001/XMLSchema#"}


def serialize(graph: Graph) -> str:
    if any(not isinstance(node, URIRef | Literal) for triple in graph for node in triple):
        raise ValueError("blank nodes are not supported")
    prefixes = {**CORE, **{p: str(ns) for p, ns in graph.namespaces() if p and str(ns) not in CORE.values()}}

    def qname(iri: URIRef) -> str:
        for prefix, ns in sorted(prefixes.items(), key=lambda pn: -len(pn[1])):
            rest = str(iri)[len(ns) :]
            if str(iri).startswith(ns) and rest and rest.replace("_", "a").replace("-", "a").isalnum():
                return f"{prefix}:{rest}"
        raise ValueError(f"no prefix for {iri}; declare one in the Turtle source")

    def subject_key(subject: URIRef) -> tuple[int, str]:
        types = set(graph.objects(subject, RDF.type))
        return (min((i for i, t in enumerate(TYPE_ORDER) if t in types), default=len(TYPE_ORDER)), str(subject))

    def predicate_key(po: tuple) -> tuple[int, str, str]:
        pred, obj = po
        rank = PREDICATE_ORDER.index(pred) if pred in PREDICATE_ORDER else len(PREDICATE_ORDER)
        return (rank, str(pred), str(obj))

    def element(pred: URIRef, obj: URIRef | Literal) -> str:
        name = qname(pred)
        if isinstance(obj, URIRef):
            return f"    <{name} rdf:resource={quoteattr(str(obj))}/>"
        attrs = f" rdf:datatype={quoteattr(str(obj.datatype))}" if obj.datatype else ""
        attrs += f" xml:lang={quoteattr(obj.language)}" if obj.language else ""
        return f"    <{name}{attrs}>{escape(str(obj))}</{name}>"

    used = {qname(p).split(":")[0] for p in graph.predicates()} | {qname(t).split(":")[0] for t in graph.objects(None, RDF.type)}
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<rdf:RDF"]
    lines += [f"  xmlns:{p}={quoteattr(ns)}" for p, ns in prefixes.items() if p in used | {"rdf"}]
    lines.append(">")
    for subject in sorted({s for s in graph.subjects() if isinstance(s, URIRef)}, key=subject_key):
        types = sorted(graph.objects(subject, RDF.type), key=lambda t: (t not in TYPE_ORDER, str(t)))
        tag = qname(types[0]) if types else "rdf:Description"
        rest = [(RDF.type, t) for t in types[1:]]
        props = [(p, o) for p, o in graph.predicate_objects(subject) if p != RDF.type] + rest
        lines.append(f"  <{tag} rdf:about={quoteattr(str(subject))}>")
        lines += [element(p, o) for p, o in sorted(props, key=predicate_key)]
        lines.append(f"  </{tag}>")
    lines.append("</rdf:RDF>")
    return "\n".join(lines) + "\n"
