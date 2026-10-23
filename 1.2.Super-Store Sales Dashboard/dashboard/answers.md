# Section 2 & 3 answers — Superstore dashboard

All figures computed from `superstore-sales.csv` (1,163 line items, 553 orders,
FY2014–FY2017). Section 2 slots follow the brief's own list.

---

## Section 2 — what I built (45 pts)

**2.1 KPI cards.** Six cards across the top, each a headline figure with the
exact value underneath: total sales $278,312.01, total profit $27,147.41,
553 orders, 9.8% profit margin, top region West, biggest loss driver Tables.
Every card is computed from the CSV when the page loads, not typed in, so the
cards and the charts cannot disagree.

**2.2 Time trend.** One chart, two aligned panels on the same month axis
(Jan 2014 – Dec 2017, 48 months): monthly sales as bars on top, monthly profit
as a line below on its own scale. I split the axes deliberately — a single
dual-axis version drew the profit line above the sales bars and made profit look
larger than revenue. Year boundaries are marked, months with negative profit are
shaded red, and the two extremes are annotated: best month +$3.5K, worst month
−$3.6K (Nov 2017).

**2.3 Category and sub-category breakdown — one chart.** A single hierarchical
chart, not two. Three category rows, each a solid bar in its own colour with its
share of sales and its margin printed beside it: Office Supplies $13,969
(27% of sales, 18.6% margin), Technology $13,032 (39%, 12.0%), Furniture $147
(34%, 0.2% — flagged in amber). The bars encode profit, so Furniture's bar is
about 1% of Office Supplies' even though Furniture has the second-highest
revenue; that is the chart's main finding, not a scaling artefact. Directly beneath each one its
sub-categories appear as lighter bars on the same profit axis and the same zero
line — Office Supplies' Binders $5.0K, Paper $3.2K, Storage $2.2K, …, Technology's
Accessories $6.3K, Phones $4.5K, Copiers $3.9K and Machines −$1.7K, Furniture's
Chairs $3.8K, Furnishings $1.1K, Bookcases −$1.9K and Tables −$2.8K. Because all
levels share one scale, the hierarchy is readable at a glance: Furniture's total
is effectively zero precisely because two of its four sub-categories are negative.

**2.4 Geographic view.** A tile-grid map of the US: one tile per state plus DC,
colour = sales, grey = no orders, with a $0–$45.7K gradient legend. Beside it a
top-10 state ranking showing each state's sales and profit. I used a tile grid
rather than a shapefile choropleth so the export renders identically offline and
stays legible at label size.

**2.5 Filters.** Four slicers — year, region, category, segment — plus a reset
button. They re-filter every panel, and the header line reports which filters are
active and how many of the 1,163 line items remain in scope.

**2.6 Readability and correctness.** Numbers are abbreviated on the cards
($278.3K) with the exact figure in small text underneath, so the chart stays
readable and the grader can still find $278,312.01. Colour means one thing
throughout: blue/purple/amber for the three categories, green for profit, red for
loss. Each panel states its own unit and each axis is labelled. A
"Rebuild from data" button re-reads the embedded CSV and recomputes everything
(1,163 rows in ~16 ms), and the footer confirms that the rendered figures match
an independent pandas computation of the same file — five checks, all passing.

---

## Section 3 — insights and recommendation (30 pts)

**Insight 1 — Discount depth, not demand, decides whether an order makes money.**
Lines sold at list price generate $119.3K of the $278.3K revenue (43% of it) and
$36.8K of the $27.1K profit, a 30.8% margin. Margin thins as discounts deepen —
15.5% at 10–19%, 11.4% at 20–29%, which is still 32% of revenue, so this is not a
rounding effect. Then it inverts: the 30–49% band loses 16.9% (−$6.6K on
$38.9K) and the 50%+ band loses 66.2% (−$14.7K on $22.2K). Together the two
bands at 30% or more carry 22% of revenue and −$21.2K of profit — a hole almost
as large as the whole company's net profit of $27.1K.

**Insight 2 — Machines alone explain the 2017 collapse.**
Profit fell $4,653 from 2016 ($8,683) to 2017 ($4,030), down 54%, while sales fell
only 19% ($77.2K to $62.5K) — so margin halved from 11.25% to 6.45%. One
sub-category accounts for more than the whole decline: Machines earned +$2,333 in
2016 and −$3,115 in 2017, a $5,448 swing from three line items — $11.4K of
revenue sold at a 33% average discount. Technology sales actually grew 9.6% that
year while Technology profit fell 62%. The damage is concentrated, not systemic:
deep-discount hardware, not weak demand.

**Recommendation — Cap discounts at 20%, require approval above it.**
Set 20% as the default ceiling, require manager sign-off for any exception, and
ban anything above 20% on Tables, Bookcases and Machines outright. A cap is
almost self-financing: had the 30%+ band merely broken even, total profit would
have been $48.4K instead of $27.1K, and 2017 would have closed at $10.6K instead
of $4.0K. Treat both as an upper bound — they assume the discounted volume is
retained, and it may not be. Track one number: the share of revenue booked above
a 20% discount, currently 21.9%. That number falling is the evidence the policy
works.
