# Changelog

## [Unreleased]

### Added

- `compile_schema` reads JSON Schema drafts 2020-12, 07, 06 and 04 into valgebra's sets over
  the values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read.
