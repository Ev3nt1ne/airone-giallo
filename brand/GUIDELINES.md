# Airone Giallo · mark guidelines

**The mark.** The standing yellow heron in a Notte circle (`airone-standing-circle-notte.svg`), the figure
centred on its bounding box. Backup: the climbing heron, built the same way (`airone-climbing-*.svg`). For avatars, favicons and
app icons, use the tight crop (`airone-standing-tight-circle-notte.svg`): the same drawing closer up, the whole figure inside the circle with a small margin.
The lockup puts the mark left of the wordmark *Airone Giallo* (EB Garamond, outlined;
SIL Open Font License): `lockup-light.svg` and `lockup-dark.svg`.

**specgraph's mark.** The climbing heron as the hub of a graph: faint edges run from behind its body to nodes, in a
tone of Notte that never touches the heron (`specgraph.svg`; `graph/.claude-plugin/icon.png` is its 512 px render).
Its one-colour and reversed versions drop the graph (`specgraph-mono-black.svg`, `specgraph-mono-white.svg`). At 16 px
the graph fades and the pose tells it from Airone Giallo's standing heron, so Airone Giallo keeps the standing one.

## Colours

| Name | HEX | RGB | Use |
|---|---|---|---|
| Giallo | `#F5C232` | 245 194 50 | the heron, only |
| Notte | `#1E2D45` | 30 45 69 | the circle; the wordmark on light grounds |
| Carta | `#F4F1EA` | 244 241 234 | the wordmark on dark grounds |

Measured WCAG contrast: Giallo on Notte 8.34:1 · Notte on white 13.85:1 · Carta on Notte 12.28:1 · Giallo on GitHub
dark 11.4:1 · **Giallo on white 1.66:1 (fails)** · Notte on GitHub dark 1.37:1 (the circle fades on very dark
grounds, where the heron carries the mark).

## Clear space and minimum size

- **Clear space:** keep one quarter of the circle's diameter free on every side. In the lockup, the gap between mark and
  wordmark is the same quarter.
- **Minimum, screen:** the tight circle down to 16 px. The standard circle from 32 px. The lockup from a mark 48 px tall,
  where the wordmark's capitals are about 15 px.
- **Minimum, print:** the circle at 10 mm diameter. The leg is then 0.3 mm wide.

## One colour and reversed

- **One ink:** use the knockout (`*-circle-knockout-black.svg`), a solid disc with the heron as a hole. Where a disc is
  not wanted, use the figure alone (`*-figure-black.svg`).
- **Dark grounds:** use the white knockout (`*-circle-knockout-white.svg`) or the white figure (`*-figure-white.svg`).
  The full-colour circle also works there, with the caveat above.
- **Squares:** where a circle cannot be used, use a square with the circle's area (side 0.886 of the circle's diameter), so the mark
  keeps the same visual size.

## Do not

1. Recolour the heron. It is Giallo, or one ink in the one-colour versions.
2. Put the yellow heron on white or light grounds without its circle (1.66:1).
3. Stretch, rotate, redraw or re-pose the heron, or move it off its bounding-box centre.
4. Fill a square to the edge with Notte in place of the equal-area square. It reads 27 % heavier.
5. Add outlines, shadows, gradients or effects, or set the wordmark in another typeface.
