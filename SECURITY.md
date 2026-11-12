# Security policy

valgebra-jsonschema is **pre-alpha**, and the code has not been independently audited: do not
place it on a trust boundary in production before a stable release and an external review.

## Supported versions

Only the latest published release receives fixes. A fix ships as the next release rather than as a
backport to an earlier one.

## What is a security issue

A caller trusts two things: that a compiled schema admits a value only if the JSON Schema it was
read from does, and that a `subset` answer is a proof. Please report, privately:

- **A value admitted that the schema refuses.** `is_valid` returns `True`, or `validate` does not
  raise, on a schema compiled without `Unsupported`, for a value the specification says the schema
  refuses, outside the differences
  [`docs/03-conformance.md`](docs/03-conformance.md#differences-ledger) records.
- **A wrong inclusion proof.** `relation_to` answers `"subset"` where a value of the first schema is
  outside the second.
- **A read beyond the document.** Compiling reads nothing but the document: a `$ref` outside it is
  refused, never fetched. Any network or file access while compiling is in scope.
- **A crash or unbounded cost within the bounds.** A document within `MAX_NESTING`, or a value
  checked against one, that crashes the interpreter, raises past Python's recursion limit, or takes
  time or memory without bound.

A defect in valgebra's own deciding is reported to valgebra, under its
[security policy](https://github.com/ppigazzini/valgebra/blob/main/SECURITY.md); a report here that
turns out to be one moves there.

## What is not a security issue

- **`undecided`.** valgebra proves the relation neither way, and nothing here reads it as true or
  false.
- **A wrong `"not_subset"`.** It is a defect to report as an issue: a refutation sends a caller to
  check a value, never past the check.
- **`Unsupported`.** A keyword this package does not read is refused by design, since skipping it
  would admit values the schema refuses.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability. Use GitHub's private vulnerability
reporting, the **Report a vulnerability** button under the repository's *Security* tab, which opens
a private advisory with the maintainer, or email the maintainer at the address valgebra's
[security policy](https://github.com/ppigazzini/valgebra/blob/main/SECURITY.md#reporting-a-vulnerability)
gives, with "valgebra-jsonschema security" in the subject.

Include the schema, the value or the second schema, the answer given, and the answer the
specification requires.

## Process

This is a solo, pre-release project, so timelines are best effort: an acknowledgment within
**7 days**, an assessment within **30 days**, and a fix and an advisory published together,
crediting the reporter unless anonymity is asked for.
