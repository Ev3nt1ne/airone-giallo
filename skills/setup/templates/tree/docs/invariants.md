---
title: Invariants
description: The rules the code depends on that a change could break, each with why it holds and what breaks without it.
type: invariants
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [invariants]
---

# Invariants

The rules {{name}}'s code depends on that a change could break. Each entry says the rule, why it holds, and what
breaks if a change violates it. Every session loads this file before it works on the code.

{{#invariants}}
{{invariants}}
{{/invariants}}
{{^invariants}}
No invariant is recorded yet.
{{/invariants}}
