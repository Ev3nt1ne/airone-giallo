
**The kit author's rules, opted in at setup.**

{{#four_hands}}
- Comments state invariants and reasons; history, item IDs and citations of what does not ship go in the commit. *A
  comment citing what its reader cannot open is dead for that reader.*
{{/four_hands}}
- Every fix comes with a test named for what went wrong; a check not run is reported as not run. *A skipped check
  read as passed is a false result.*
- An irreversible act is offered only as irreversible, with why now; copy and compare before deleting an original.
  *The copy nobody checked is the one that is lost.*
