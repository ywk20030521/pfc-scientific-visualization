# Scientific Figure Composition

`scripts/charts/publication.py` uses a deterministic content-aware layout. It
does not add blank placeholder images.

The Viewer's `exportCompositePanels()` uses the same odd/even layout family on
its Canvas export. It processes all chart entries and draws `(a)`, `(b)`, …
plus each chart title and source status. It does not silently truncate after
eight charts or force a two-column grid.

## Layout families

| Count | Preferred behavior |
|---:|---|
| 1 | Single full panel |
| 2 | Balanced 1 x 2 |
| 3 | Primary panel plus two supporting panels |
| 4 | 2 x 2 |
| 5 | Weighted 2 + 3 layout with a larger first panel |
| 6 | 3 x 2 or 2 x 3 according to page aspect |
| 7 | Primary panel plus 3 + 3 supporting panels |
| 8 | 4 x 2 or 2 x 4 according to page aspect |
| Other | Aspect-aware balanced rows; short final rows expand available cells |

An explicit `columns` value is treated as a user override. Otherwise the layout
is automatic.

## Content rules

- A primary scene or relationship may occupy a larger cell.
- Directly comparable panels keep common size and scale.
- Representative SVGs remain vector.
- The optional scene PNG is embedded only when supplied.
- Panel labels are bold lowercase `(a)`, `(b)`, etc.
- Axes, legends and labels retain space through internal gaps.
- Read order is row-major.

## Export strategy

- SVG: native output.
- PNG: rasterize the composed SVG at the requested size.
- PDF: convert the composed SVG using a local vector converter. No PDF backend
  is bundled and the Viewer never downloads one.

The plan reports `pdf_status=NOT_SUPPORTED_WITHOUT_LOCAL_VECTOR_CONVERTER` when
that converter has not been supplied.
