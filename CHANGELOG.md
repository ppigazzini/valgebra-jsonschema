# Changelog

All notable changes to valgebra-jsonschema are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.1] - 2026-11-12

### Added

- `compile_schema` reads JSON Schema drafts 2020-12, 07, 06 and 04 into valgebra's sets over
  the values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read.
- Draft 2019-09 reads through `upgrade`, and a document naming any other dialect raises
  `UnsupportedDialect`, a kind of `Unsupported`, whose message says it is not supported.
- `read_tool` reads an MCP server's tool listing into its two contracts.
- `patternProperties` up to four patterns, and a `propertyNames` of words, are clauses over keys
  narrowed by a pattern, so a relation reads them.
- `assert_format=True` reads `date`, `duration`, `ipv4`, `uuid`, `date-time`, `time`, `email`,
  `hostname` and `ipv6` as assertions, and refuses any other `format`. It is off by default.
- The package requires valgebra 0.0.25 or later and below 0.1, since a `0.0.x` minor of
  valgebra is a breaking release here.

[Unreleased]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/ppigazzini/valgebra-jsonschema/releases/tag/v0.0.1
