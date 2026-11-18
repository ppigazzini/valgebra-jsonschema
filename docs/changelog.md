---
description: Every released version, what it changed, and what counts as a break.
---

## Versioning, and what counts as a break

The version follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Below `0.1.0`
there is no minor number to carry a break, so every `0.0.x` release may break, and its notes say
where. A break is a public name removed or changed, a value a schema held that it no longer
holds or the reverse, or an inclusion decided one way that is now decided the other; an inclusion
left undecided that is now decided is not one. Each release takes valgebra's newest `0.0.x`,
and the range it requires says which.

<!-- The repository's CHANGELOG.md, served verbatim: one list, rendered in two places. -->

--8<-- "CHANGELOG.md"
