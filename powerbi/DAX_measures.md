# DAX measures

Every measure the report needs, grouped by the page that uses it. Create a blank
table called `_Measures` first and put all of them in it, so the field list stays
readable.

```
Home ribbon -> Enter data -> name it _Measures -> Load
Then right click _Measures -> New measure for each one below.
```

Delete the placeholder `Column1` once the first measure exists.

---

## Before you trust any of these

`ref_concentration` carries the CR3 and HHI values that the SQL layer and the Python
layer of this project both produce and agree on. The measures below are meant to
reproduce those numbers from the raw fact tables. Build the validation visual in step 9
of the build guide and confirm every difference reads zero before you present anything.
That table is the test harness for the model.

Expected values:

| Mineral | CR3 % | HHI |
|---|---|---|
| Cobalt | 88.52 | 5,857 |
| Nickel | 74.97 | 3,798 |
| Manganese | 73.00 | 2,021 |

---

## Core production measures

```dax
Production (t) =
SUM ( fact_world_mining[production_t] )
```

```dax
World Production (t) =
SUM ( ref_world_totals[world_production_t] )
```

```dax
Share of World % =
DIVIDE ( [Production (t)], [World Production (t)] )
```

```dax
Other Bucket Share % =
DIVIDE (
    SUM ( ref_world_totals[other_bucket_t] ),
    [World Production (t)]
)
```

---

## Concentration measures

CR3 is the combined share of world mine production held by the top three named
countries. `TOPN` is taken over the countries present in the current filter context, so
the measure returns the right answer inside a per mineral visual without any extra
logic.

```dax
CR3 % =
VAR Countries =
    SUMMARIZE ( fact_world_mining, dim_country[country] )
VAR Top3 =
    TOPN ( 3, Countries, CALCULATE ( [Production (t)] ), DESC )
VAR Top3Production =
    SUMX ( Top3, CALCULATE ( [Production (t)] ) )
RETURN
    DIVIDE ( Top3Production, [World Production (t)] )
```

HHI is the sum of squared percentage shares on the 0 to 10,000 scale. Only named
countries contribute a term, which is what makes the result a lower bound.

```dax
HHI (lower bound) =
VAR World = [World Production (t)]
RETURN
    SUMX (
        SUMMARIZE ( fact_world_mining, dim_country[country] ),
        VAR SharePct = DIVIDE ( CALCULATE ( [Production (t)] ), World ) * 100
        RETURN SharePct * SharePct
    )
```

```dax
HHI Read =
VAR H = [HHI (lower bound)]
RETURN
    SWITCH (
        TRUE (),
        H > 2500, "Highly concentrated",
        H > 1500, "Moderately concentrated",
        "Unconcentrated"
    )
```

```dax
Top Producer =
VAR Countries =
    SUMMARIZE ( fact_world_mining, dim_country[country] )
RETURN
    MAXX ( TOPN ( 1, Countries, CALCULATE ( [Production (t)] ), DESC ), dim_country[country] )
```

Validation measures. Both should read 0.00 for every mineral.

```dax
CR3 Check =
ROUND ( [CR3 %] * 100, 2 ) - ROUND ( SUM ( ref_concentration[cr3_named_pct] ), 2 )
```

```dax
HHI Check =
ROUND ( [HHI (lower bound)], 0 ) - ROUND ( SUM ( ref_concentration[hhi_named_lower_bound] ), 0 )
```

The workbook's own figures, for the correction visual:

```dax
CR3 Workbook % =
DIVIDE ( SUM ( ref_concentration[cr3_pct_workbook] ), 100 )
```

```dax
CR3 Gap (pp) =
[CR3 %] * 100 - SUM ( ref_concentration[cr3_pct_workbook] )
```

---

## India resource and production measures

```dax
Mn Resources (Mt) =
SUM ( fact_mn_resources[total_resources_mt] )
```

```dax
Mn Resources Share % =
DIVIDE (
    SUM ( fact_mn_resources[total_resources_kt] ),
    CALCULATE (
        SUM ( fact_mn_resources[total_resources_kt] ),
        REMOVEFILTERS ( dim_state )
    )
)
```

```dax
Top 2 States Share % =
VAR States =
    SUMMARIZE ( fact_mn_resources, dim_state[state] )
VAR Top2 =
    TOPN ( 2, States, CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ) ), DESC )
VAR Top2Total =
    SUMX ( Top2, CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ) ) )
VAR National =
    CALCULATE (
        SUM ( fact_mn_resources[total_resources_kt] ),
        REMOVEFILTERS ( dim_state )
    )
RETURN
    DIVIDE ( Top2Total, National )
```

```dax
Mn Production (t) =
SUM ( fact_mn_production[production_t] )
```

```dax
Mn Production FY2021-22 (t) =
CALCULATE (
    SUM ( fact_mn_production[production_t] ),
    fact_mn_production[fiscal_year] = "2021-22"
)
```

The ratio that must never divide by zero. A state with no production row and a state
reporting zero are different facts and the measure says which is which.

```dax
Resource t per t Production =
VAR Resource = SUM ( fact_mn_resources[total_resources_t] )
VAR Produced = [Mn Production FY2021-22 (t)]
RETURN
    IF ( Produced > 0, DIVIDE ( Resource, Produced ) )
```

```dax
Production Status =
VAR HasRow =
    NOT ISEMPTY (
        CALCULATETABLE ( fact_mn_production, fact_mn_production[fiscal_year] = "2021-22" )
    )
VAR Produced = [Mn Production FY2021-22 (t)]
RETURN
    SWITCH (
        TRUE (),
        NOT HasRow, "No production row in source",
        Produced = 0, "Zero production FY2021-22",
        "Producing"
    )
```

---

## Import exposure measures

```dax
Import Value (US$) =
SUM ( fact_imports[import_value_usd] )
```

```dax
Import Value Label =
VAR V = [Import Value (US$)]
VAR Period = SELECTEDVALUE ( fact_imports[period_label] )
RETURN
    IF (
        ISBLANK ( V ),
        "no data in source",
        IF ( V >= 1000000000,
             "US$" & FORMAT ( V / 1000000000, "0.00" ) & "B  " & Period,
             "US$" & FORMAT ( V / 1000000, "0" ) & "M  " & Period )
    )
```

```dax
Import Dependence % =
VAR Dep = AVERAGE ( fact_imports[import_dependence_pct] )
RETURN DIVIDE ( Dep, 100 )
```

```dax
Domestic Resources (Mt) =
SUM ( fact_nico_resources[total_resources_mt] )
```

```dax
Active Mining Leases =
SUM ( fact_nico_resources[active_mining_leases] )
```

```dax
Supply Gap Headline =
VAR Res = [Domestic Resources (Mt)]
VAR Leases = [Active Mining Leases]
RETURN
    IF (
        NOT ISBLANK ( Res ),
        FORMAT ( Res, "#,0" ) & " Mt of ore resources, " & FORMAT ( Leases, "0" ) & " active leases"
    )
```

---

## Demand measures

```dax
Demand (t) =
SUM ( fact_demand[demand_t] )
```

```dax
Demand 2025 (t) =
CALCULATE ( [Demand (t)], dim_year[year] = 2025 )
```

```dax
Demand 2030 (t) =
CALCULATE ( [Demand (t)], dim_year[year] = 2030 )
```

Five compounding periods between the two endpoints.

```dax
Demand CAGR 2025-2030 =
VAR Start = [Demand 2025 (t)]
VAR End = [Demand 2030 (t)]
RETURN
    IF (
        Start > 0 && End > 0,
        ( End / Start ) ^ ( 1 / 5 ) - 1
    )
```

```dax
Growth Multiple =
DIVIDE ( [Demand 2030 (t)], [Demand 2025 (t)] )
```

---

## Risk framework measures

The score is deliberately not computed. These measures make that visible in the report
rather than leaving an empty cell that reads like a bug.

```dax
Weighted Score (blocked) =
VAR AllComplete =
    CALCULATE (
        COUNTROWS ( ref_vulnerability ),
        ref_vulnerability[quality_import_dependence] = "complete",
        ref_vulnerability[quality_mining_hhi] = "complete",
        ref_vulnerability[quality_refining_leader] = "complete"
    )
RETURN
    IF (
        AllComplete > 0,
        0.40 * AVERAGE ( ref_vulnerability[input_import_dependence_pct] )
            + 0.35 * AVERAGE ( ref_vulnerability[input_mining_hhi_scaled_0_100] )
            + 0.25 * AVERAGE ( ref_vulnerability[input_refining_leader_pct] )
    )
```

```dax
Score Status =
IF (
    ISBLANK ( [Weighted Score (blocked)] ),
    "NOT COMPUTED",
    FORMAT ( [Weighted Score (blocked)], "0.0" )
)
```

```dax
Score Blocked Reason =
SELECTEDVALUE (
    ref_vulnerability[score_blocked_reason],
    "Inputs are incomplete for every mineral, so no score is published"
)
```

```dax
Inputs Missing =
VAR M =
    COUNTROWS (
        FILTER (
            ref_vulnerability,
            ref_vulnerability[quality_import_dependence] = "missing"
                || ref_vulnerability[quality_refining_leader] = "missing"
        )
    )
RETURN COALESCE ( M, 0 )
```

---

## Formatting to set on each measure

Select the measure, then use the Measure tools ribbon.

| Measure | Format | Decimals |
|---|---|---|
| Share of World %, CR3 %, Import Dependence %, Mn Resources Share %, Top 2 States Share %, Demand CAGR 2025-2030 | Percentage | 2 |
| HHI (lower bound), CR3 Check, HHI Check | Whole number with thousands separator | 0 |
| Production (t), World Production (t), Mn Production (t), Demand (t) | Whole number with thousands separator | 0 |
| Import Value (US$) | Currency, US dollar | 0 |
| Mn Resources (Mt), Domestic Resources (Mt), Resource t per t Production | Decimal | 1 |

Set `dim_mineral[mineral]` to sort by `dim_mineral[sort_order]` so Nickel, Cobalt and
Manganese keep that order on every visual. Select the column, then Column tools, then
Sort by column.
