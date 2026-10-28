"""Places: where a statement of the graph holds.

The places come from the axes declared in the graph file's `meta.axes`. Each axis has a name and an ordered list of
values; an axis may be marked `interfaces` (the boundary between two of its values is a place) and `ordered` (the
move between two adjacent values is a place). The places are:

  a cell          one value per axis, joined by dots, in axis order       Z2.BETA
  an interface    two cells that differ on one `interfaces` axis only     Z1.BETA~Z2.BETA
  a transition    a cell and the next value up on one `ordered` axis      Z2.BETA>PROD

A domain is a list of tokens: a place, a wildcard (`*` for any value of an axis: `Z2.*`, `*.BETA`, `Z1.*~Z2.*`,
`*.BETA>PROD`) or `all` (every cell). With no axes there is exactly one place, named `all`.
"""
import itertools
import re

ALL = "all"
VALUE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class DomainError(ValueError):
    pass


class Axis:
    def __init__(self, spec):
        if not isinstance(spec, dict) or "name" not in spec or "values" not in spec:
            raise DomainError(f"an axis needs a name and values: {spec!r}")
        self.name = str(spec["name"])
        self.values = [str(v) for v in spec["values"]]
        self.interfaces = bool(spec.get("interfaces", False))
        self.ordered = bool(spec.get("ordered", False))
        if not self.values:
            raise DomainError(f"axis {self.name} has no values")
        if len(set(self.values)) != len(self.values):
            raise DomainError(f"axis {self.name} names a value twice")
        for v in self.values:
            if not VALUE_RE.match(v) or v == ALL:
                raise DomainError(f"axis {self.name}: {v!r} is not a usable value (letters, digits, _ and -)")
        self.steps = set(zip(self.values, self.values[1:]))


class Grid:
    """The places of a graph, from `meta.axes`."""

    def __init__(self, axes=()):
        self.axes = [a if isinstance(a, Axis) else Axis(a) for a in (axes or [])]
        seen = {}
        for a in self.axes:
            for v in a.values:
                if v in seen:
                    raise DomainError(f"value {v} is on two axes ({seen[v]}, {a.name}); a value names one axis")
                seen[v] = a.name
        self._axis_of = seen

    # ---- names --------------------------------------------------------------------------------------------
    def _join(self, parts):
        return ".".join(parts) if self.axes else ALL

    def _split(self, cell):
        return cell.split(".") if self.axes else []

    def _cell(self, tok):
        """The values each axis takes in a cell pattern (a list per axis)."""
        if not self.axes:
            if tok not in (ALL, "*"):
                raise DomainError(f"not a cell: {tok!r}")
            return []
        parts = tok.split(".")
        if len(parts) != len(self.axes):
            raise DomainError(f"not a cell: {tok!r}")
        out = []
        for a, p in zip(self.axes, parts):
            if p == "*":
                out.append(list(a.values))
            elif p in a.values:
                out.append([p])
            else:
                raise DomainError(f"unknown {a.name} in {tok!r}")
        return out

    def _cells(self, choice):
        return [self._join(c) for c in itertools.product(*choice)]

    # ---- domains ------------------------------------------------------------------------------------------
    def expand(self, tok):
        tok = str(tok).strip()
        if tok == ALL:
            return set(self.everywhere())
        if "~" in tok:
            return self._interface(tok)
        if ">" in tok:
            return self._transition(tok)
        return set(self._cells(self._cell(tok)))

    def _interface(self, tok):
        a, b = tok.split("~", 1)
        ca, cb = self._cell(a), self._cell(b)
        pa, pb = self._split(a), self._split(b)
        iface = [i for i, ax in enumerate(self.axes) if ax.interfaces]
        names = " or ".join(self.axes[i].name + "s" for i in iface) or "values of an axis with interfaces"
        differ = [i for i in iface if pa[i] != pb[i]]
        if len(differ) != 1 or len(ca[differ[0]]) != 1 or len(cb[differ[0]]) != 1:
            raise DomainError(f"an interface joins two different {names}: {tok!r}")
        k = differ[0]
        for i, ax in enumerate(self.axes):
            if i != k and pa[i] != pb[i]:
                raise DomainError(f"an interface stays on one {ax.name}: {tok!r}")
        ax = self.axes[k]
        lo, hi = sorted([ca[k][0], cb[k][0]], key=ax.values.index)
        out = set()
        for combo in itertools.product(*[c for i, c in enumerate(ca) if i != k]):
            rest = list(combo)
            left = rest[:k] + [lo] + rest[k:]
            right = rest[:k] + [hi] + rest[k:]
            out.add(f"{self._join(left)}~{self._join(right)}")
        return out

    def _transition(self, tok):
        c, v2 = tok.split(">", 1)
        choice = self._cell(c)
        name = self._axis_of.get(v2)
        k = next((i for i, ax in enumerate(self.axes) if ax.name == name and ax.ordered), None)
        label = name or next((ax.name for ax in self.axes if ax.ordered), "value")
        if k is None or len(choice[k]) != 1 or (choice[k][0], v2) not in self.axes[k].steps:
            raise DomainError(f"a transition joins two adjacent {label}s, upward: {tok!r}")
        return {f"{cell}>{v2}" for cell in self._cells(choice)}

    def domain(self, tokens):
        if isinstance(tokens, str):
            tokens = [tokens]
        out = set()
        for tok in tokens:
            out |= self.expand(str(tok))
        return out

    def everywhere(self):
        """Every cell."""
        return set(self._cells([a.values for a in self.axes]))

    def places(self):
        """Every place: the cells, every interface and every transition."""
        out = self.everywhere()
        for k, ax in enumerate(self.axes):
            others = [a.values for i, a in enumerate(self.axes) if i != k]
            for combo in itertools.product(*others):
                rest = list(combo)

                def cell(v):
                    return self._join(rest[:k] + [v] + rest[k:])
                if ax.interfaces:
                    for i, a in enumerate(ax.values):
                        for b in ax.values[i + 1:]:
                            out.add(f"{cell(a)}~{cell(b)}")
                if ax.ordered:
                    for lo, hi in zip(ax.values, ax.values[1:]):
                        out.add(f"{cell(lo)}>{hi}")
        return out

    # ---- reading a place ----------------------------------------------------------------------------------
    def sides(self, e):
        """The cells a place joins: two for an interface or a transition, itself for a cell."""
        if "~" in e:
            return set(e.split("~"))
        if ">" in e:
            c, v2 = e.split(">")
            k = next(i for i, ax in enumerate(self.axes) if ax.name == self._axis_of[v2])
            parts = self._split(c)
            parts[k] = v2
            return {c, self._join(parts)}
        return {e}

    def covers(self, d, e):
        """Is place e covered by domain d? Yes when e is in d; when e is a boundary and d holds on one of its
        sides; when e is a cell and d holds on a boundary of it. A node holding on a cell is read on that cell's
        boundaries, and a boundary rule may rest on statements about either side."""
        if e in d:
            return True
        if is_boundary(e):
            return any(s in d for s in self.sides(e))
        return any(e in self.sides(x) for x in d if is_boundary(x))


def is_boundary(e):
    return "~" in e or ">" in e
