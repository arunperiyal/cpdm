# CPDM Supported Schemas

The canonical persisted-document registry is defined in
`src/cpdm/core/document_schemas.py`. This page is generated from that
registry during release preparation and records the supported document kinds:

| Kind | Current version | Migration coverage |
| --- | ---: | --- |
| recipe | 2 | v1 → v2 |
| scale-map | 1 | current |
| pipeline | 1 | current |
| analysis-result | 1 | current |
| profile-result | 1 | current |

Loaders must continue to reject unknown kinds and invalid versions rather than
silently accepting incompatible documents.
