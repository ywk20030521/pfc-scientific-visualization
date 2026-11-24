# Analysis Engine and Channel Registry

The analysis engine derives quantities only from explicit fields. It never uses
a History name as physical evidence by itself.

## Registry scope

The registry covers Ball position/radius/velocity/acceleration, Wall geometry,
contact network/force, fracture events/orientation, sample strain/stress and
native Histories.

Contact network and contact force are `NOT_CAPTURED` in the preserved baseline
because the raw schema stores Wall aggregate contact force, not contact
endpoints or per-contact force vectors.

For PFC2D, force per unit out-of-plane thickness is a line load in N/m. It is
never reported as a three-dimensional stress in Pa. Nominal Pa stress is
generated only when a PFC3D area basis exists.

## Formula gates

| Quantity | Formula | Required evidence |
|---|---|---|
| Ball displacement | `||x_i(t)-x_i(t_first)||` | Same Ball ID and real positions |
| Ball velocity | `(x(t2)-x(t1))/(t2-t1)` | Consecutive observations of the same ID |
| Ball acceleration | `(v(t2)-v(t1))/(t2-t1)` | At least three observations of the same ID |
| Platen shortening | `H0-H(t)` | Same-frame top/bottom platen distance |
| Engineering strain | `(H0-H)/H0` | Positive initial height |
| Mean load | `0.5*(|F_top|+|F_bottom|)` | Both force channels |
| PFC2D line load | `mean_load/W0` (N/m) | Initial transverse width and both force channels |
| PFC3D nominal stress | `mean_load/A0` (Pa) | Two transverse extents and both force channels |
| Crack count | `count(event.cycle <= frame.cycle)` | Fracture event Cycle |
| Fracture direction | Angle from captured normal | Non-zero finite normal |

The first observed position of a later-added Ball is used as its displacement
reference and explicitly identified as such. No frame is inserted between
observations.

## Statistics

Generated statistics include count, mean, standard deviation, minimum, maximum,
median and 5/95 percentiles. Histograms report bin edges and counts. Correlation
uses frame-aligned native samples and reports its sample count.

## Multi-Case comparison

Case comparisons use native/final summaries. They do not resample cases onto a
common time axis. If aligned-time comparison is later required, it must be a
separate, explicitly labeled operation with its interpolation policy.

## Histories

The preserved capture stores native History rows. The analysis engine exposes
the values but leaves their physical interpretation unconfirmed until project
metadata supplies a meaning and unit.

## Display formatting and units

- `scripts/analysis/formatting.py` chooses scientific notation for very small or
  large magnitudes and formats axes, tooltip values and labels separately.
- `scripts/analysis/units.py` converts only compatible known dimensions and
  returns an explicit conversion record.
- Formatted strings and display-scaled values are kept separate from analysis
  arrays. Tooltips may retain greater precision than axes.
