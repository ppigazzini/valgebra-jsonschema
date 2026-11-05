# Changelog

## [Unreleased]

### Added

- `compile_schema` reads JSON Schema drafts 2020-12, 07, 06 and 04 into valgebra's sets over
  the values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read.
- Draft 2019-09 reads through `upgrade`, and a document naming any other dialect raises
  `UnsupportedDialect`, a kind of `Unsupported`, whose message says it is not supported.
- `read_tool` reads an MCP server's tool listing into its two contracts.
- `assert_format=True` reads `date`, `duration`, `ipv4`, `uuid`, `date-time`, `time`, `email`,
  `hostname` and `ipv6` as assertions, and refuses any other `format`. It is off by default.
