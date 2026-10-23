# Superstore sales dashboard

One-page BI dashboard for the iCourse "superstore-sales.csv" assignment
(missions/8c3d9817). Built from the raw CSV; nothing is typed in by hand.

## How it is put together

    superstore-sales.csv
            │
            ├──► build.py ── pandas ──► reference.json   (the numbers, for checking)
            │                    └────► out/dashboard.html (CSV embedded in the page)
            │
            └──► assets/app.js ── browser recomputes every figure from that CSV
                              └────► SVG charts, KPI cards, slicers
                                          │
                                          └──► Chrome headless ──► out/dashboard.pdf
                                                              └──► out/dashboard.png

Two independent implementations of the same aggregation: pandas in Python and
plain JavaScript in the browser. The page prints `✓ 5/5 figures match the pandas
reference` in the footer and `verify.py` re-checks it from the exported DOM, so
the numbers on the screenshot cannot drift from the numbers in the CSV.

## Rebuild

```powershell
.\rebuild.ps1              # HTML + PDF + PNG
.\rebuild.ps1 -NoExport    # HTML only, ~1s, while editing charts
.\rebuild.ps1 -Verify      # also diff the rendered KPIs against pandas
```

`Rebuild from data` in the dashboard header does the same thing in the browser:
it re-reads the embedded CSV, re-aggregates and re-renders every panel, and
reports how long it took. `dashboard.html?rebuild=1` fires it automatically so
the button's handler can be tested headlessly.

## Files

| file | role |
|---|---|
| `build.py` | data layer: CSV → aggregates → single-file HTML |
| `assets/app.js` | client layer: CSV parser, aggregation, seven SVG charts, slicers, rebuild |
| `assets/style.css` | fixed 1680×1050 canvas, print-first styling |
| `template.html` | page skeleton with the data and reference slots |
| `verify.py` | compares the rendered DOM against `reference.json` |
| `rebuild.ps1` | the pipeline: build → PDF → PNG → verify |
| `out/dashboard.pdf` | **deliverable** — A4-free custom page, vector text |
| `out/dashboard.png` | **deliverable** — 3360×2100 fallback |
| `out/dashboard.html` | the interactive dashboard (open it in a browser) |

## Figures (all data, no filters)

| # | question | answer |
|---|---|---|
| 1.1 | total sales | $278,312.01 |
| 1.2 | total profit | $27,147.41 |
| 1.3 | orders | 553 |
| 1.4 | profit margin | 9.75 % |
| 1.5 | top region by sales | West ($78,100.93) |
| 1.6 | top category by profit | Office Supplies ($13,969.17) |
| 1.7 | worst sub-category | Tables (−$2,824.56) |
| 1.8 | best year by profit | 2016 ($8,682.73) |

## Notes

- **Geo view is a tile grid map**, not a shapefile choropleth: every tile is a
  state, colour = sales, layout approximates the real map. No basemap is needed
  at render time, so the export never depends on the network.
- **Slicers** (year / region / category / segment) filter all seven panels live in
  the browser. The exported PDF is a snapshot of the unfiltered state; the filter
  widgets are visible there but a PDF cannot be clicked.
- **Chrome needs to run outside the DSH sandbox** — it opens named pipes for its
  IPC, which the sandbox blocks. That is why `rebuild.ps1` is the only path that
  exports PDF/PNG.
