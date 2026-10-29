# Contributing to this repository with an agent

This file is for an agent working **on Airone Giallo itself**: fixing a tool, changing a skill, adding a part. It is not
the instruction file a project gets when it adopts Airone Giallo; that one is written by the setup skill into the
adopting project, from the template in `skills/setup/`.

- **Read the folder's README before touching it.** Each folder (`graph/`, `skills/`, `tools/`) says what it is, why
  it exists and how it is used. A change that contradicts the README changes the README too.
- **Airone Giallo may require any of its parts; a part that stands alone requires nothing outside its folder.** The
  skills, the setup and the tools assume each other's vocabulary and files, and a tool may import another. The graph
  stands alone: nothing in `graph/` imports or needs the rest, and Airone Giallo reaches it by its command and its
  file. A part joins this repository when it serves the long project; what does not, gets a repository of its own. A
  part is called standalone only when its folder passes the graph's test.
- **Configuration is data.** A tool reads a project's values from that project's own files (the graph file's
  `meta`, the status file's `status-meta` block) or from arguments, never from constants in its code. A tool with a
  particular project's vocabulary in it is not done.
- **Tests travel with the code.** A change to a tool comes with its tests, and a new test has been seen to fail for
  the right reason before it counts.
- **A rule carries its reason.** In a skill, each rule is one sentence of rule and one of reason, with a general
  example where it helps. No history, no incidents, no names of the projects the rule came from.
- **Documents are corrected, never silently rewritten.** The `markdown-docs` skill in `skills/` says how; it binds
  here too.
- **An agent commits locally and never pushes, tags or publishes.** Those are the maintainer's acts.
