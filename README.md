# SOS vocabularies

Vocabularies of the DFG project SOS, published with GitHub Pages at
**https://dfg-sos.github.io/ontologies/**.

| Vocabulary | Namespace | Files |
|---|---|---|
| EO file formats | `https://dfg-sos.github.io/ontologies/eo-formats#` | [`eo-formats.owl`](eo-formats.owl) · [`.ttl`](https://dfg-sos.github.io/ontologies/eo-formats.ttl) · [docs](https://dfg-sos.github.io/ontologies/eo-formats) |
| CWL extensions | `https://dfg-sos.github.io/ontologies/cwl#` | [`cwl.owl`](cwl.owl) · [`.ttl`](https://dfg-sos.github.io/ontologies/cwl.ttl) · [docs](https://dfg-sos.github.io/ontologies/cwl) |

The **EO file formats** ontology is a standalone taxonomy of Earth Observation and GIS file formats:
`GeoTIFF`, `COG`, `Shapefile`, `GeoJSON`, … under the abstract classes `Raster` and `Vector`.
Format compatibility follows `rdfs:subClassOf`: a `COG` is a `GeoTIFF` is a `Raster`.

The **CWL extensions** define `expectedCRS` and `expectedGeometryType`, fields for CWL File ports
that state metadata a file must have beyond its format.

## Use in CWL
```yaml
cwlVersion: v1.2
$namespaces:
  eo: "https://dfg-sos.github.io/ontologies/eo-formats#"
  sos: "https://dfg-sos.github.io/ontologies/cwl#"
$schemas:
  - https://dfg-sos.github.io/ontologies/eo-formats.owl
  - https://dfg-sos.github.io/ontologies/cwl.owl   # optional, see below
class: CommandLineTool
inputs:
  roads: {type: File, format: eo:Vector}          # accepts Shapefile, GeoJSON, ...
outputs:
  raster: {type: File, format: eo:GeoTIFF, sos:expectedCRS: "EPSG:4326", outputBinding: {glob: out.tif}}
```
`$schemas` must point at the `.owl` files. The namespace IRI itself opens the HTML documentation.

`eo-formats.owl` is required: CWL uses it for `format` checks, e.g. to accept a `Shapefile` where a
`Vector` is expected. `cwl.owl` is not required. Fields like `sos:expectedCRS` are valid CWL as soon
as their prefix is declared in `$namespaces`; CWL ignores them and does not check them against the
schema. Listing `cwl.owl` only documents where the fields are defined.

To pin a fixed version, use the release copy, which is never changed after publication:
`https://dfg-sos.github.io/ontologies/releases/eo-formats/1.0.0/eo-formats.owl`.

## Layout
```
<name>.owl                           source (RDF/XML), edit this
releases/<name>/<version>/<name>.owl released copies, immutable
scripts/build.py                     checks, site generation, release copies
.github/workflows/ci.yml             checks on push/PR, Pages deploy from main
```
Only the `.owl` files are committed. CI generates the Turtle (`.ttl`) and HTML docs and deploys them
with the `.owl` files to GitHub Pages.

## Editing and releasing
```sh
uv run scripts/build.py check                # consistency checks
uv run scripts/build.py build                # checks, then build the site into _site/ (not committed)
```
The checks reject:
- terms outside the namespace;
- terms without `rdfs:label`;
- `rdfs:subClassOf` targets that are not defined;
- undeclared properties in the namespace;
- a header missing `owl:versionInfo`, `owl:versionIRI`, `dcterms:title` or `dcterms:license`.

CI runs `build` on every push and pull request, rejects changes to existing files in `releases/`,
and deploys `_site/` to GitHub Pages on pushes to `main`.

To release a new version, for example `eo-formats` 1.1.0:
1. In `eo-formats.owl`, set `owl:versionInfo` to `1.1.0` and `owl:versionIRI` to
   `https://dfg-sos.github.io/ontologies/releases/eo-formats/1.1.0/eo-formats.owl`.
2. Run `uv run scripts/build.py release eo-formats 1.1.0`.
3. Commit and push to `main`. CI deploys the release copy with the site, at
   `https://dfg-sos.github.io/ontologies/releases/eo-formats/1.1.0/eo-formats.owl`.

Class IRIs never change between versions. Remove a class only by marking it `owl:deprecated true`.

## License
[CC BY 4.0](LICENSE).
