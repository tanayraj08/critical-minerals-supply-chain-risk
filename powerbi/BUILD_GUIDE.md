# Power BI build guide

Everything needed to build the report: the data, the model, the theme and a visual by
visual specification for five pages. Follow it top to bottom and the result matches
`mockup/report-mockup.html`, which is a static picture of the finished report that you
can open in any browser as a build target.

**On a Mac.** Power BI Desktop has no macOS build. Two routes work:

- Windows through Parallels, Boot Camp or a cloud VM, then Power BI Desktop. This is the
  full experience and the only one where the theme JSON imports in one click.
- The browser at `app.powerbi.com`. Upload `Critical_Minerals_PowerBI.xlsx` to a
  workspace, then build the report in the web editor. Most of this guide applies. Theme
  import and a few formatting panes are reduced in the web editor, so where a step is
  Desktop only it says so.

---

## 1. Load the data

1. Open Power BI Desktop and choose **Blank report**.
2. **Home** ribbon, **Get data**, **Excel workbook**, then pick
   `powerbi/Critical_Minerals_PowerBI.xlsx`.
3. In the Navigator, tick all 17 sheets and click **Load**. Do not click Transform. The
   export is already clean because every cleaning rule ran upstream in Python.
4. Wait for the load, then open **Model view** from the left rail.

The 17 tables split three ways and the prefix tells you which is which. `dim_` tables are
dimensions you filter and slice by. `fact_` tables hold the measurable rows. `ref_` tables
hold aggregates, framework inputs and known correct answers that must never be mixed into
a fact table.

---

## 2. Build the relationships

Power BI will guess some of these. Delete every auto detected relationship first so the
model is deliberate rather than inherited. In **Model view**, select each auto created
line and press Delete.

Create these nine by dragging the first field onto the second. All are **one to many**,
single direction, with the dimension on the one side.

| From (one side) | To (many side) |
|---|---|
| `dim_mineral[mineral_key]` | `fact_world_mining[mineral_key]` |
| `dim_mineral[mineral_key]` | `fact_nico_resources[mineral_key]` |
| `dim_mineral[mineral_key]` | `fact_imports[mineral_key]` |
| `dim_mineral[mineral_key]` | `fact_demand[mineral_key]` |
| `dim_mineral[mineral_key]` | `fact_refining[mineral_key]` |
| `dim_mineral[mineral_key]` | `ref_world_totals[mineral_key]` |
| `dim_mineral[mineral_key]` | `ref_concentration[mineral_key]` |
| `dim_mineral[mineral_key]` | `ref_vulnerability[mineral_key]` |
| `dim_mineral[mineral_key]` | `ref_demand_cagr[mineral_key]` |

Then these four:

| From (one side) | To (many side) |
|---|---|
| `dim_country[country_key]` | `fact_world_mining[country_key]` |
| `dim_country[country_key]` | `fact_refining[country_key]` |
| `dim_state[state_key]` | `fact_mn_resources[state_key]` |
| `dim_state[state_key]` | `fact_mn_production[state_key]` |
| `dim_year[year_key]` | `fact_demand[year_key]` |

**Why `ref_world_totals` is a separate table and not a column on the fact.** The world
total and the Other bucket are a different grain from a country row. If they sat inside
`fact_world_mining`, any visual showing production by country would include a bar for
WORLD TOTAL and double count the entire world. Splitting by grain makes that mistake
impossible rather than merely discouraged. The same reasoning puts the India national
total in `ref_india_totals` instead of inside `fact_mn_resources`. Say this out loud in
an interview, because it is the modelling decision that separates someone who has built a
model from someone who has dragged fields onto a canvas.

Then set the sort order so minerals never appear alphabetically:

1. **Data view**, select `dim_mineral`, click the `mineral` column.
2. **Column tools** ribbon, **Sort by column**, choose `sort_order`.

---

## 3. Apply the theme

**Desktop only.** **View** ribbon, **Themes** dropdown, **Browse for themes**, then pick
`powerbi/theme/critical-minerals-vibrant.json`.

The canvas turns near black, cards and visuals pick up a dark slate background with a
rounded border, and the categorical colours become the eight vibrant hues. Those eight
were generated at a fixed lightness and then checked for colourblind separation against
the dark canvas, so the palette is vivid without being a guess. Nickel, cobalt and
manganese sit on the first three slots and clear every separation check as a trio.

In the web editor there is no theme browse, so set the page background to `#0E1016` and
the visual backgrounds to `#171A24` manually under **Format page** and **Format visual**,
and set series colours per visual from the table in step 4.

Mineral colours, used consistently on every page:

| Mineral | Hex | Why this one |
|---|---|---|
| Nickel | `#378DFF` electric blue | largest import value, the volume story |
| Cobalt | `#FA04A6` hot magenta | most concentrated mineral, the risk story |
| Manganese | `#DB6B04` burnt orange | the domestic story |

Colour follows the mineral, never the chart position. Set it per series on every visual
so a filter that drops a mineral never repaints the survivors.

---

## 4. Page 1: Executive Overview

Rename the page tab to **Overview**. Page size stays 16:9.

1. **Title textbox** across the top. Text: `Critical Minerals Supply-Chain Risk
   Analytics`, 28 pt, `#F4F6FB`. Below it a second line at 11 pt in `#A7B0C4`:
   `India's nickel, cobalt and manganese exposure. Mining concentration, domestic
   resources, import dependence and projected demand.`
2. **Six KPI cards** in a row under the title. Use the **Card** visual for each.

   | Card | Field or measure | Category label |
   |---|---|---|
   | 1 | `[HHI (lower bound)]` filtered to Cobalt | Cobalt HHI, lower bound |
   | 2 | `[CR3 %]` filtered to Cobalt | Cobalt CR3 |
   | 3 | `[Import Value (US$)]` filtered to Nickel | Nickel imports CY2024 |
   | 4 | `[Import Value (US$)]` filtered to Cobalt | Cobalt imports CY2023 |
   | 5 | `[Demand CAGR 2025-2030]` filtered to Cobalt | Cobalt demand CAGR |
   | 6 | `[Top 2 States Share %]` | Odisha + Karnataka, Mn |

   Filter a card by dropping `dim_mineral[mineral]` into its **Filters on this visual**
   well and selecting the one mineral. Check card 1 reads 5,857 and card 6 reads 58.67%.

3. **Clustered bar chart**, title `Mining concentration by mineral`.
   Y axis `dim_mineral[mineral]`, X axis `[HHI (lower bound)]`.
   Turn **Data labels** on. Add a constant line at 2,500 under **Analytics** and label it
   `Highly concentrated threshold`. Colour the line `#A7B0C4`, dashed.
4. **Clustered bar chart**, title `CR3 by mineral`.
   Y axis `dim_mineral[mineral]`, X axis `[CR3 %]`. Data labels on.
   Do not put CR3 and HHI on one chart with two axes. They are two different scales and a
   dual axis chart invites a comparison that does not exist.
5. **Line chart**, title `India projected demand, tonnes a year`.
   X axis `dim_year[year]`, Y axis `[Demand (t)]`, Legend `dim_mineral[mineral]`.
   Turn the Y axis to **Log** scale under Format, **Y axis**, **Scale type**. Cobalt runs
   17 t to 3,878 t while nickel runs 2,629 t to 17,492 t, and on a linear axis the cobalt
   line is flat against the floor. A log axis is the honest way to put two series of
   different magnitude on one chart, and it is the only reason this is one visual rather
   than two.
   Add a textbox under it: `2028 and 2029 are absent from the source, so the line steps
   from 2027 to 2030.`
6. **Mineral slicer**, `dim_mineral[mineral]`, **Format** as horizontal tile. Place it top
   right. Leave it unfiltered by default.

---

## 5. Page 2: Global Supply Concentration

Rename the tab to **Global supply**.

1. **Filled map**, title `World mine production share 2024`.
   Location `dim_country[country_for_map]`, Tooltips `[Share of World %]` and
   `[Production (t)]`, Legend empty.
   Under **Format**, **Fill colours**, click the **fx** button, set **Format style** to
   **Gradient**, field `[Share of World %]`, minimum `#0E2338` and maximum `#378DFF`.
   A sequential ramp is one hue from light to dark, never a rainbow.
   Add the mineral slicer so the map changes per mineral.
2. **Clustered bar chart**, title `Production share by country`.
   Y axis `dim_country[country]`, X axis `[Share of World %]`, data labels on.
   Under **Format**, **Columns**, **Colour**, click **fx**, **Format style** to
   **Rules**, field `fact_world_mining[is_top_3]`, rule: if value is True then `#378DFF`,
   else `#6E7891`. The top three carry the colour and the rest recede.
3. **Textbox** beside the bar chart:
   `The Other bucket is an aggregate of many unnamed producers and is not a country. It
   is excluded from CR3 and from every HHI term, which makes the HHI a lower bound. Other
   holds 8.21% of world nickel, 11.48% of cobalt and 27.00% of manganese.`
4. **Clustered bar chart**, title `Where the workbook's own figures go wrong`.
   Y axis `dim_mineral[mineral]`, X axis both `[CR3 %]` and
   `ref_concentration[cr3_pct_workbook]` as two series. Set the first to the mineral
   colour and the second to `#6E7891`. Data labels on.
   **Textbox** under it:
   `The source workbook appends its own CR3 and HHI block. That formula ranks the Other
   bucket as if it were a country, which puts an aggregate second in cobalt and produces
   a CR3 of 97% against a true named country figure of 88.52%.`
   This visual is the strongest thing in the report. Do not bury it.
5. **Table**, title `Concentration metrics`.
   Columns `dim_mineral[mineral]`, `[CR3 %]`, `[HHI (lower bound)]`, `[HHI Read]`,
   `[Top Producer]`, `[Other Bucket Share %]`.

---

## 6. Page 3: India's Domestic Position

Rename the tab to **India position**.

1. **Filled map**, title `Manganese resources by state`.
   Location `dim_state[state]`, Colour saturation `[Mn Resources (Mt)]`, gradient
   `#0E2338` to `#DB6B04`. If the map cannot resolve the states, use a **Treemap** with
   Category `dim_state[state]` and Values `[Mn Resources (Mt)]` instead. A treemap is a
   fair substitute here because the question is share of a whole.
2. **Clustered bar chart**, title `Manganese resource share by state`.
   Y axis `dim_state[state]`, X axis `[Mn Resources Share %]`, sorted descending, data
   labels on. Colour by rule on `fact_mn_resources[resource_rank]`: rank less than or
   equal to 2 gets `#DB6B04`, everything else `#6E7891`.
   Odisha reads 34.06% and Karnataka 24.62%.
3. **Table**, title `Resource base against FY2021-22 production`.
   Columns `dim_state[state]`, `[Mn Resources (Mt)]`, `[Mn Production FY2021-22 (t)]`,
   `[Resource t per t Production]`, `[Production Status]`.
   Under **Format**, **Cell elements**, add **Background colour** on the Production
   Status column with rules: `No production row in source` to `#3A2A12`,
   `Zero production FY2021-22` to `#3A1A1A`, `Producing` to transparent.
   Four states carry a blank ratio and that is correct. Goa, Gujarat and West Bengal have
   no production row at all and Jharkhand reported zero. A blank is the honest output and
   a zero would be a lie.
4. **Two cards**: `[Domestic Resources (Mt)]` filtered to Nickel, and the same filtered to
   Cobalt. Category labels `Nickel ore resources` and `Cobalt ore resources`.
5. **Textbox** beside them, 14 pt, `#FA04A6`:
   `0 active mining leases for both. A resource base that is not being mined supplies
   nothing.`

---

## 7. Page 4: Import Exposure and Demand

Rename the tab to **Import exposure**.

1. **Clustered bar chart**, title `Import value by mineral`.
   Y axis `dim_mineral[mineral]`, X axis `[Import Value (US$)]`, data labels on, colour
   per mineral.
   The manganese row carries no value on purpose. Add a **textbox** immediately beside
   the empty row reading `Manganese: no import table in the source`. An absent bar reads
   as a zero unless it is labelled, and manganese import exposure is unknown rather than
   nil.
2. **Multi row card**, title `Import detail`.
   Fields `dim_mineral[mineral]`, `[Import Value Label]`, `fact_imports[import_volume_note]`,
   `fact_imports[dependence_basis]`.
   The dependence basis text appears on every row on purpose. The 100 percent figure is a
   structural proxy from zero active mining leases, not a customs volume calculation, and
   the label travels with the number instead of sitting in a footnote.
3. **Gauge or card** for `[Import Dependence %]` filtered to Nickel, then another for
   Cobalt. If you use a gauge set minimum 0 and maximum 1.
4. **Line chart**, title `Projected annual requirement 2025 to 2030`.
   X axis `dim_year[year]`, Y axis `[Demand (t)]`, Legend `dim_mineral[mineral]`, log
   scale, markers on, data labels on.
5. **Two cards** for `[Demand CAGR 2025-2030]`, one filtered to each mineral. Cobalt reads
   196.23% and nickel 46.09%.
6. **Clustered bar chart**, title `Growth multiple 2025 to 2030`.
   Y axis `dim_mineral[mineral]`, X axis `[Growth Multiple]`, data labels on.
   Cobalt reads 228.12x and nickel 6.65x.
   Indexing both series to 2025 = 100 does not rescue them onto one linear axis either,
   because the growth rates themselves differ by a factor of 34. A multiple is the honest
   single number comparison, and the log line chart above already carries the shape.
   `fact_demand[index_2025_base_100]` is in the model if you want to try the indexed line
   anyway, but check what it looks like before you keep it.

---

## 8. Page 5: Risk Framework and Data Quality

Rename the tab to **Risk framework**.

1. **Textbox** at the top, 16 pt:
   `Strategic Vulnerability Score = 0.40 x import dependence + 0.35 x (mining HHI / 100)
   + 0.25 x refining leader share. All inputs are normalised to a 0 to 100 scale before
   weighting. The score is not computed for any mineral.`
2. **Table**, title `Score inputs and why the score is withheld`.
   Columns `dim_mineral[mineral]`,
   `ref_vulnerability[input_import_dependence_pct]`,
   `ref_vulnerability[quality_import_dependence]`,
   `ref_vulnerability[input_mining_hhi_scaled_0_100]`,
   `ref_vulnerability[quality_mining_hhi]`,
   `ref_vulnerability[input_refining_leader_pct]`,
   `ref_vulnerability[quality_refining_leader]`,
   `[Score Status]`,
   `ref_vulnerability[score_blocked_reason]`.
   Conditional format the three quality columns: `complete` to `#05AB58`, `proxy` and
   `partial` and `lower_bound` to `#A98D07`, `missing` to `#FF3434`.
   Conditional format `[Score Status]` to `#FF3434` so NOT COMPUTED reads as a decision
   rather than a blank.
3. **Card** showing `[Inputs Missing]` with category label `Minerals with an absent
   input`. It reads 1, which is manganese.
4. **Table**, title `Data quality findings in the source workbook`.
   Columns `ref_data_quality[severity]`, `ref_data_quality[table]`,
   `ref_data_quality[finding]`, `ref_data_quality[impact]`,
   `ref_data_quality[handled_by]`.
   Conditional format severity: `high` to `#FF3434`, `medium` to `#A98D07`, `low` to
   `#6E7891`.
5. **Textbox** at the bottom, 11 pt, `#A7B0C4`:
   `Sources as cited in the workbook: IBM National Mineral Inventory and Indian Minerals
   Yearbook; Ministry of Mines reply in Rajya Sabha, PIB Delhi 05-Aug-2024; UN COMTRADE
   via Trading Economics (nickel, CY2024); IndexBox (cobalt, CY2023); USGS Mineral
   Commodity Summaries 2025; USGS Global Maps of Critical Mineral Production 2023.
   Import values are US dollars. Resource position is as on 01.04.2020.`

---

## 9. Validate the model before you present it

Add a temporary **Table** visual anywhere with these columns:

`dim_mineral[mineral]`, `[CR3 %]`, `ref_concentration[cr3_named_pct]`, `[CR3 Check]`,
`[HHI (lower bound)]`, `ref_concentration[hhi_named_lower_bound]`, `[HHI Check]`

Both check columns must read 0 on all three rows. The reference values come from this
project's SQL layer and Python layer, which independently compute the same numbers and
agree, so if the DAX disagrees the DAX is wrong.

Expected:

| Mineral | CR3 % | HHI |
|---|---|---|
| Cobalt | 88.52 | 5,857 |
| Nickel | 74.97 | 3,798 |
| Manganese | 73.00 | 2,021 |

Also confirm:

- Odisha 34.06%, Karnataka 24.62%, top two together 58.67%
- India manganese total 503.624 Mt across 11 states
- Nickel 189 Mt and cobalt 45 Mt of ore resources, 0 active leases for both
- Nickel imports US$1,260,000,000 and cobalt US$45,000,000
- Cobalt demand CAGR 196.23% and nickel 46.09%
- Four states blank on `[Resource t per t Production]`, never zero

Delete the validation visual once it passes, or move it to a hidden page. Right click the
page tab and choose **Hide page**. Keeping it in the file is better than deleting it,
because a reviewer who finds a hidden test page thinks more of the work rather than less.

---

## 10. Publish

1. **File**, **Save as**, name it `Critical_Minerals_Supply_Chain_Risk.pbix` and save it
   into the `powerbi/` folder of the repo.
2. **Home**, **Publish**, pick a workspace. Power BI Service gives you a shareable link.
3. For the GitHub repo, take a screenshot of each page and put them in `powerbi/screens/`,
   then link them from the README. A `.pbix` file on GitHub cannot be previewed, so
   without screenshots nobody sees the work.

---

## Things not to do

**No dual axis charts.** Two measures on two y scales invite a comparison that the
geometry does not support. Where two series differ by orders of magnitude, use a log axis
or index both to a common base. Both are specified above.

**No pie or donut for the concentration story.** Share of world production across nine
nickel producers is a ranking question, and angle is the hardest encoding to compare. The
bar chart already answers it.

**Do not let a colour change meaning between pages.** Nickel is blue everywhere, cobalt is
magenta everywhere, manganese is orange everywhere. Set the colour per series rather than
accepting the default slot order, because a filter that drops one mineral will otherwise
repaint the other two.

**Do not fill the manganese gaps to make the visuals look complete.** The empty import bar
and the blank ratios are findings. A dashboard that hides them is worse than one that
shows them, and the gap is what justifies the vulnerability score being withheld.
