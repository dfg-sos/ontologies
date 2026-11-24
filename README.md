# SOS vocabularies

Vocabularies of the DFG project SOS, published with GitHub Pages at
**https://dfg-sos.github.io/ontologies/**.

| Vocabulary | Namespace (prefix) | Files |
|---|---|---|
| EO vocabulary | `https://dfg-sos.github.io/ontologies/eo-formats#` (`eo`) | [`eo-formats.ttl`](eo-formats.ttl) (source) · [`.owl`](https://dfg-sos.github.io/ontologies/eo-formats.owl) · [docs](https://dfg-sos.github.io/ontologies/eo-formats) |
| CWL file metadata | `https://dfg-sos.github.io/ontologies/cwl#` (`sos`) | [`cwl.ttl`](cwl.ttl) (source) · [`.owl`](https://dfg-sos.github.io/ontologies/cwl.owl) · [docs](https://dfg-sos.github.io/ontologies/cwl) |
| Resource demand | `https://dfg-sos.github.io/ontologies/resource-demand#` (`rd`) | [`resource-demand.ttl`](resource-demand.ttl) (source) · [`.owl`](https://dfg-sos.github.io/ontologies/resource-demand.owl) · [docs](https://dfg-sos.github.io/ontologies/resource-demand) |

The **EO vocabulary** covers Earth Observation and GIS files:
- **file formats**: a taxonomy of `GeoTIFF`, `COG`, `Shapefile`, `GeoJSON`, … under the abstract
  classes `Raster` and `Vector`. Format compatibility follows `rdfs:subClassOf`: a `COG` is a
  `GeoTIFF` is a `Raster`;
- **file metadata**: `expectedCRS` and `expectedGeometryType`, fields for CWL File ports that state
  metadata a file must have beyond its format. They are defined in the `cwl#` namespace (`cwl.ttl`),
  which the EO vocabulary imports;
- **measures** (since 1.1.0): quantities probed from raster and vector files (`PixelCount`,
  `BandCount`, `ValidPixelCount`, `FeatureCount`, `VertexCount`), each tied with `rd:appliesToFormat`
  to the formats it can be taken from and marked with `rd:readsContent` if the probe reads the whole file.
  They are `rd:Measure`s, for use as complexity variables.

The vocabulary keeps its published file `eo-formats.owl` and namespace `eo-formats#` from 1.0.0,
so existing references keep working.

The **resource demand** vocabulary states how the resource demand of a CWL tool grows with its
inputs (parametric dependencies). Input parameters declare `complexityVariables` (a symbol and a
`Measure`: `Value`, `ArrayLength`, `FileSize`, `DerivedMeasure` computed by a `probe` tool, or a
domain measure such as `eo:PixelCount`); `ResourceRequirement` states `ramDemand` and `timeDemand`
as a sum of terms, each a product of factors, each a variable with a `ComplexityClass` (`Constant`,
`Logarithmic`, `Linear`, `Linearithmic`, `Quadratic`, `Cubic`, `Exponential`). Only the shape is
annotated; coefficients come from measurements.

## Use in CWL
```yaml
cwlVersion: v1.2
$namespaces:
  eo: "https://dfg-sos.github.io/ontologies/eo-formats#"
  sos: "https://dfg-sos.github.io/ontologies/cwl#"
$schemas:
  - https://dfg-sos.github.io/ontologies/eo-formats.owl
class: CommandLineTool
inputs:
  roads: {type: File, format: eo:Vector}          # accepts Shapefile, GeoJSON, ...
outputs:
  raster: {type: File, format: eo:GeoTIFF, sos:expectedCRS: "EPSG:4326", outputBinding: {glob: out.tif}}
```

Resource demand (with `rd: "https://dfg-sos.github.io/ontologies/resource-demand#"` added to
`$namespaces`), here O(n + d log d) time for a raster with n pixels, d of them valid:
```yaml
hints:
  ResourceRequirement:
    rd:timeDemand:
      - factors: [{variable: n, complexity: rd:Linear}]
      - factors: [{variable: d, complexity: rd:Linearithmic}]
inputs:
  mask:
    type: File
    format: eo:GeoTIFF
    rd:complexityVariables:
      - {symbol: n, measure: eo:PixelCount}
      - {symbol: d, measure: eo:ValidPixelCount}
```
Keys inside these fields must not be `id`, `name`, `type` or `format`: CWL's loader rewrites them.

`eo-formats.owl` is required in `$schemas`: CWL uses it for `format` checks, e.g. to accept a
`Shapefile` where a `Vector` is expected. CWL does not follow `owl:imports`, and it does not need
the other vocabularies: fields like `sos:expectedCRS` or `rd:timeDemand` are valid CWL as soon as
their prefix is declared in `$namespaces`; CWL ignores them and does not check them against a
schema. `$schemas` must point at the `.owl` files. The namespace IRI itself opens the HTML documentation.

## Versions
Each vocabulary is served in two ways:
- `https://dfg-sos.github.io/ontologies/<name>.owl` is the **latest version**. It only grows: terms
  are never removed (only marked `owl:deprecated true`) and never moved in the class hierarchy, so
  documents that use it keep working;
- `https://dfg-sos.github.io/ontologies/releases/<name>/<version>/<name>.owl` is a **fixed copy** of
  a release that never changes, e.g.
  `https://dfg-sos.github.io/ontologies/releases/eo-formats/1.0.0/eo-formats.owl`. Use it to pin a
  version. `releases/<name>/<version>/` opens the documentation of that version, and the index page
  lists all releases.

Each file states its own fixed copy in `owl:versionIRI`, and the one it replaces, if any, in
`owl:priorVersion`.
`owl:imports` points at the fixed copy of the imported vocabulary, e.g.
`…/releases/resource-demand/1.0.0/resource-demand.owl`: the vocabulary IRI serves HTML, so OWL tools
such as Protégé could not load it, and the fixed copy pins what a release depends on. To use a newer
release of an imported vocabulary, update the import and release the importing vocabulary too.
Term IRIs do not contain a version: `eo:GeoTIFF` is the same term in every release.

## Layout
```
<name>.ttl                           latest version (Turtle), edit this
releases/<name>/<version>/<name>.owl released copy (RDF/XML), immutable
releases/<name>/<version>/<name>.ttl its Turtle source (missing in releases made before Turtle)
scripts/build.py                     command line: check, build, release
scripts/vocab/                       model.py, checks.py, site.py (+ style.css), rdf_xml.py
.github/workflows/ci.yml             checks on push/PR, Pages deploy from main
```
The vocabularies are written in Turtle. CI generates the latest `<name>.owl` (RDF/XML) and the HTML
docs from them and deploys them with the Turtle files and the release copies to GitHub Pages. The
RDF/XML is written by `scripts/vocab/rdf_xml.py`, which sorts everything, so the same graph always
gives the same file. Turtle comments are kept in the `.ttl` but not in the `.owl`.

Protégé opens and saves Turtle: save as "Turtle Syntax" to `<name>.ttl`. Protégé reorders the
file and drops the comments; `uv run scripts/build.py check` still checks it.

## Editing and releasing
```sh
uv run scripts/build.py check                # consistency checks
uv run scripts/build.py build                # checks, then build the site into _site/ (not committed)
```
The checks reject:
- terms outside the namespace;
- terms without `rdfs:label`;
- `rdfs:subClassOf` targets that are not defined here or in a vocabulary listed with `owl:imports`;
- references to terms of another SOS vocabulary that is not imported, or that do not exist there;
- an `owl:imports` of an SOS vocabulary that does not point at a release copy
  (`…/releases/<name>/<version>/<name>.owl`), or names a version that is neither released nor the
  current one being released (an import of an older release is only a warning);
- undeclared properties in the namespace;
- a header missing `owl:versionInfo`, `owl:versionIRI`, `dcterms:title` or `dcterms:license`, or an
  `owl:versionIRI` that does not match `owl:versionInfo`;
- a term of an earlier release that was removed, or that lost an `rdfs:subClassOf` parent;
- a `<name>.ttl` that differs from the release copy of the same version (compared as graphs);
- on pushes to `main` (`--require-releases`): a version without its release copy.

CI runs `build` on every push and pull request, rejects changes to existing files in `releases/`,
and deploys `_site/` to GitHub Pages on pushes to `main`.

To release a new version, for example `eo-formats` 1.2.0:
1. In `eo-formats.ttl`, set `owl:versionInfo` to `1.2.0`, `owl:versionIRI` to
   `https://dfg-sos.github.io/ontologies/releases/eo-formats/1.2.0/eo-formats.owl` and
   `owl:priorVersion` to the previous release copy.
2. Run `uv run scripts/build.py release eo-formats 1.2.0`. It writes
   `releases/eo-formats/1.2.0/eo-formats.owl` (RDF/XML) and a copy of `eo-formats.ttl` next to it.
3. Commit and push to `main`. CI deploys the release copy with the site, at
   `https://dfg-sos.github.io/ontologies/releases/eo-formats/1.2.0/eo-formats.owl`.

## License
[CC BY 4.0](LICENSE).
