# {{name}}: instructions for a contributor's agent

{{name}} is {{purpose}}. This file is for an agent working in this repository on a contributor's behalf. The
skills and commands it cites come from Airone Giallo, its plugin (`/airone-giallo:<skill>`) and its Python packages,
at https://github.com/Ev3nt1ne/airone-giallo.

## Where things are

| The question | The answer |
|---|---|
| What the system is and what breaks it; the decision record, each decision and its reason | `{{c_docs}}` |
{{#c_glossary}}
| What a term means | `{{c_glossary}}` |
{{/c_glossary}}
{{#c_graph}}
| What rests on what: requirements, evidence, and a node for each recorded decision that something technical rests on | `{{c_graph}}` |
{{/c_graph}}
{{#c_plan}}
| What gets built, in what order, to which milestones | `{{c_plan}}` |
{{/c_plan}}
| The checks, zero errors before every commit | {{c_checks}} |

## The rules

- This repository is the public side of the project: a text in it cites only what is in it. *A citation of what the
  reader cannot open is a dead link to them, or a leak.*
- Each document sits on its rung of the ladder and cites only rungs at or below it (`doc-discipline` §1). *A
  rung that cited upward could never stand on its own.*
- Run the checks before every commit, and report one not run as not run. *A skipped check read as passed is a false
  result.*
{{#gated}}
- Outward acts (pushes, tags, releases, issues, pull requests, comments, posts) are prepared as a local branch or a
  draft and handed to the person you work for, who sends them. *An act outside the repository cannot be taken back.*
{{/gated}}
{{#free}}
- Outward acts (pushes, tags, releases, issues, pull requests, comments, posts) are done{{#attribution}} with the
  trailer `{{attribution}}`{{/attribution}} and reported. *An act outside the repository cannot be taken back.*
{{/free}}
