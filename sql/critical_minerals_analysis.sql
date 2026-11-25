-- ===========================================================================
-- CRITICAL MINERALS SUPPLY-CHAIN RISK ANALYTICS: INDIA'S Ni-Co-Mn EXPOSURE
-- Complete SQL analysis layer, SQLite
-- ===========================================================================
--
-- Source data   : Critical_Minerals_NiCoMn_Dataset.xlsx, 7 data sheets
-- Database      : critical_minerals.db, 8 tables, built by load_data.py
-- Queries below : 5, each writing one CSV into outputs/
--
-- HOW THIS FILE IS RUN
-- run_sql.py splits the file on the -- @query: <name> markers and executes each
-- section separately, so one file still produces one CSV per query. The markers
-- are ordinary SQL comments, so the whole file also opens and runs section by
-- section in DB Browser for SQLite, DBeaver or the sqlite3 shell.
--
-- CONTENTS
--   1  country_production_rank    rank producers per mineral, window functions
--   2  import_dependence          CTE join, dependence proxy, explicit gap row
--   3  state_mn_resource_rank     rank 11 states, running total, reconciliation
--   4  resource_vs_production     LEFT JOIN, zero division handled by label
--   5  cr3_hhi_concentration      CR3 and HHI in SQL, cross checked against Python
--
-- THREE RULES HOLD THROUGHOUT
--   No figure is invented. Everything traces to a workbook cell or to arithmetic
--   on workbook cells.
--   Aggregate rows are never treated as detail. The Other bucket is not a country
--   and INDIA TOTAL is not a state, so both are tagged at load time and filtered
--   by row_type here.
--   Gaps are published as gaps. A missing manganese import table produces a
--   labelled row, never a zero.
-- ===========================================================================




-- =========================================================================
-- @query: 01_country_production_rank
-- ---------------------------------------------------------------------------
-- 01  Country production ranking per mineral, world mine production 2024
-- ---------------------------------------------------------------------------
-- Source table: global_mining_2024 (USGS Mineral Commodity Summaries 2025 and
-- USGS derived country estimates, loaded from Global_Mining_2024).
--
-- The Other bucket is excluded from the ranking because it is an aggregate of
-- many unnamed producers and is not a country. The WORLD TOTAL row is excluded
-- from the ranking for the same reason but is kept as a denominator.
--
-- Two share columns are reported on purpose and they answer different questions:
--   share_of_named_pct  = the SUM() OVER (PARTITION BY mineral) basis, so the
--                         named countries in this ranking sum to 100 percent.
--   share_of_world_pct  = the same production over the workbook WORLD TOTAL,
--                         which still includes the Other bucket. This is the
--                         basis used for CR3 and HHI in analysis.py, so the SQL
--                         and the Python reconcile exactly.
-- ---------------------------------------------------------------------------

WITH world AS (
    SELECT mineral,
           production_t AS world_production_t
    FROM   global_mining_2024
    WHERE  row_type = 'world_total'
),
named AS (
    SELECT mineral,
           country,
           production_t
    FROM   global_mining_2024
    WHERE  row_type = 'country'          -- drops Other and WORLD TOTAL
)
SELECT
    n.mineral,
    RANK() OVER (PARTITION BY n.mineral ORDER BY n.production_t DESC) AS production_rank,
    n.country,
    n.production_t,
    ROUND(100.0 * n.production_t
          / SUM(n.production_t) OVER (PARTITION BY n.mineral), 2)      AS share_of_named_pct,
    ROUND(100.0 * n.production_t / w.world_production_t, 2)            AS share_of_world_pct,
    ROUND(SUM(n.production_t) OVER (PARTITION BY n.mineral), 0)        AS named_countries_total_t,
    w.world_production_t,
    ROUND(100.0 * (w.world_production_t - SUM(n.production_t) OVER (PARTITION BY n.mineral))
          / w.world_production_t, 2)                                   AS other_bucket_share_of_world_pct,
    CASE
        WHEN RANK() OVER (PARTITION BY n.mineral ORDER BY n.production_t DESC) <= 3
        THEN 'top_3'
        ELSE 'rest'
    END                                                                AS cr3_member
FROM named n
JOIN world w ON w.mineral = n.mineral
ORDER BY n.mineral, production_rank;


-- =========================================================================
-- @query: 02_import_dependence
-- ---------------------------------------------------------------------------
-- 02  Import dependence proxy for nickel and cobalt
-- ---------------------------------------------------------------------------
-- WHAT THIS IS: a structural proxy, not a customs volume calculation.
--
-- The workbook reports India holding 189 Mt of nickel ore resources and 45 Mt of
-- cobalt ore resources with ZERO active mining leases for both (India_NiCo_
-- Resources, National Mineral Inventory as on 01.04.2020). Zero active leases
-- means zero domestic mine supply, so every tonne consumed is imported and the
-- import dependence is 100 percent by construction.
--
-- It is NOT computed as imported volume divided by apparent consumption, because
-- the workbook carries no customs volume series for nickel and only an
-- approximate volume note for cobalt. The import VALUES below are indicative,
-- order-of-magnitude figures (the source sheet says they are not customs-audited)
-- and are labelled with currency and calendar year. extension/ replaces this
-- proxy with DGCIS customs volumes.
--
-- Manganese is carried as an explicit gap row. The workbook has no manganese
-- import table, so no manganese dependence figure is produced here.
-- ---------------------------------------------------------------------------

WITH domestic_supply AS (
    -- domestic mine production is zero wherever there are no active leases
    SELECT
        mineral,
        total_resources_mt,
        active_mining_leases,
        CASE WHEN active_mining_leases = 0 THEN 0 ELSE NULL END AS domestic_mine_production_t,
        CASE WHEN active_mining_leases = 0
             THEN 'zero active mining leases in the workbook, so domestic mine supply is 0'
             ELSE 'active leases present, domestic production not quantified in the workbook'
        END AS domestic_supply_basis
    FROM india_nico_resources
),
dependence AS (
    SELECT
        i.mineral,
        i.year                                  AS import_year,
        i.currency,
        i.import_value_usd,
        i.import_volume_note,
        d.total_resources_mt,
        d.active_mining_leases,
        d.domestic_mine_production_t,
        d.domestic_supply_basis,
        CASE
            WHEN d.domestic_mine_production_t = 0 AND i.import_value_usd > 0 THEN 100.0
            ELSE NULL
        END AS import_dependence_pct,
        i.source
    FROM india_nico_imports i
    JOIN domestic_supply  d ON d.mineral = i.mineral
)
SELECT
    mineral,
    import_year,
    currency,
    import_value_usd,
    ROUND(import_value_usd / 1000000.0, 2) AS import_value_usd_million,
    import_volume_note,
    total_resources_mt,
    active_mining_leases,
    domestic_mine_production_t,
    import_dependence_pct,
    'PROXY: derived from zero active mining leases, not from customs volume over apparent consumption'
        AS dependence_method,
    domestic_supply_basis,
    source
FROM dependence

UNION ALL

-- explicit gap row so manganese is never silently treated as zero dependence
SELECT
    'Manganese'                AS mineral,
    NULL                       AS import_year,
    NULL                       AS currency,
    NULL                       AS import_value_usd,
    NULL                       AS import_value_usd_million,
    'NOT IN WORKBOOK'          AS import_volume_note,
    (SELECT ROUND(total_resources_kt / 1000.0, 3)
       FROM india_mn_resources_by_state
      WHERE row_type = 'national_total') AS total_resources_mt,
    NULL                       AS active_mining_leases,
    (SELECT qty_2021_22_t
       FROM india_mn_production_by_state
      WHERE row_type = 'national_total')  AS domestic_mine_production_t,
    NULL                       AS import_dependence_pct,
    'DATA GAP: the workbook contains no manganese import table, so no dependence figure is computed'
        AS dependence_method,
    'India does mine manganese domestically, so a zero supply assumption would be wrong'
        AS domestic_supply_basis,
    'n/a'                      AS source

ORDER BY mineral;


-- =========================================================================
-- @query: 03_state_mn_resource_rank
-- ---------------------------------------------------------------------------
-- 03  Indian states ranked by manganese total resource share
-- ---------------------------------------------------------------------------
-- Source table: india_mn_resources_by_state (IBM National Mineral Inventory as
-- on 01.04.2020, quantities in thousand tonnes).
--
-- The INDIA TOTAL row is tagged row_type = 'national_total' at load time and is
-- excluded here, so the 11 state rows are ranked on their own and their shares
-- sum to 100 percent. The audited national total is carried alongside as a check
-- column: recomputed state sum and the workbook INDIA TOTAL must agree.
-- ---------------------------------------------------------------------------

WITH national AS (
    SELECT total_resources_kt AS india_total_kt
    FROM   india_mn_resources_by_state
    WHERE  row_type = 'national_total'
),
states AS (
    SELECT state,
           reserves_kt,
           remaining_resources_kt,
           total_resources_kt,
           share_of_india_total_pct AS workbook_share_pct
    FROM   india_mn_resources_by_state
    WHERE  row_type = 'state'
),
ranked AS (
    -- the two window functions are computed here so the running total in the
    -- outer query can build on share_pct without nesting SUM() inside SUM()
    SELECT
        RANK() OVER (ORDER BY total_resources_kt DESC)        AS resource_rank,
        state,
        reserves_kt,
        remaining_resources_kt,
        total_resources_kt,
        workbook_share_pct,
        100.0 * total_resources_kt
            / SUM(total_resources_kt) OVER ()                 AS share_of_india_pct,
        SUM(total_resources_kt) OVER ()                       AS states_sum_kt
    FROM states
)
SELECT
    r.resource_rank,
    r.state,
    r.reserves_kt,
    r.remaining_resources_kt,
    r.total_resources_kt,
    ROUND(r.total_resources_kt / 1000.0, 3)                   AS total_resources_mt,
    ROUND(r.share_of_india_pct, 2)                            AS share_of_india_pct,
    ROUND(SUM(r.share_of_india_pct) OVER (
              ORDER BY r.total_resources_kt DESC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2)
                                                              AS cumulative_share_pct,
    ROUND(r.workbook_share_pct, 2)                            AS workbook_share_pct,
    r.states_sum_kt,
    n.india_total_kt                                          AS workbook_india_total_kt,
    CASE WHEN r.states_sum_kt = n.india_total_kt
         THEN 'match' ELSE 'MISMATCH' END                     AS total_reconciliation
FROM ranked r
CROSS JOIN national n
ORDER BY r.resource_rank;


-- =========================================================================
-- @query: 04_resource_vs_production
-- ---------------------------------------------------------------------------
-- 04  Manganese resource base against FY2021-22 production, by state
-- ---------------------------------------------------------------------------
-- Joins india_mn_resources_by_state (thousand tonnes, as on 01.04.2020) to
-- india_mn_production_by_state (tonnes, FY2021-22). Resources are converted to
-- tonnes before the ratio so both sides share one unit.
--
-- resource_t_per_t_production answers: for every tonne mined in FY2021-22, how
-- many tonnes sit in the resource base. A high number means a large endowment is
-- barely being worked.
--
-- No state is divided by zero and no missing state is dropped. A LEFT JOIN keeps
-- all 11 resource states and each untouched state is labelled:
--   no_production_row   Goa, Gujarat and West Bengal have resources but no row
--                       at all in the production table.
--   zero_production     Jharkhand appears in the production table with 0 tonnes
--                       in FY2021-22 (it reported 4,785 t in 2019-20).
-- ---------------------------------------------------------------------------

WITH resources AS (
    SELECT state,
           total_resources_kt,
           total_resources_kt * 1000.0 AS total_resources_t
    FROM   india_mn_resources_by_state
    WHERE  row_type = 'state'
),
production AS (
    SELECT state,
           qty_2019_20_t,
           qty_2020_21_t,
           qty_2021_22_t
    FROM   india_mn_production_by_state
    WHERE  row_type = 'state'
)
SELECT
    r.state,
    ROUND(r.total_resources_kt / 1000.0, 3)      AS total_resources_mt,
    r.total_resources_t,
    p.qty_2019_20_t                              AS production_2019_20_t,
    p.qty_2020_21_t                              AS production_2020_21_t,
    p.qty_2021_22_t                              AS production_2021_22_t,
    CASE
        WHEN p.state IS NULL           THEN 'no_production_row'
        WHEN p.qty_2021_22_t = 0       THEN 'zero_production'
        ELSE 'producing'
    END                                          AS production_status,
    CASE
        WHEN p.state IS NULL OR p.qty_2021_22_t = 0 THEN NULL
        ELSE ROUND(r.total_resources_t / p.qty_2021_22_t, 1)
    END                                          AS resource_t_per_t_production,
    CASE
        WHEN p.state IS NULL
            THEN 'resources held but no production row in the workbook for any year, ratio not defined'
        WHEN p.qty_2021_22_t = 0
            THEN 'in the production table but reported 0 t in FY2021-22, ratio not defined'
        ELSE 'ratio computed from FY2021-22 production'
    END                                          AS ratio_note
FROM resources r
LEFT JOIN production p ON p.state = r.state
ORDER BY
    CASE WHEN p.state IS NULL OR p.qty_2021_22_t = 0 THEN 1 ELSE 0 END,
    resource_t_per_t_production DESC,
    r.total_resources_kt DESC;


-- =========================================================================
-- @query: 05_cr3_hhi_concentration
-- ---------------------------------------------------------------------------
-- 05  CR3 and HHI per mineral, computed in SQL
-- ---------------------------------------------------------------------------
-- The same two concentration metrics that analysis.py computes, built here with
-- window functions so the result can be cross checked across both layers. The
-- pipeline asserts that the SQL and the Python agree to two decimal places.
--
--   CR3 = combined share of world mine production held by the top 3 NAMED
--         countries.
--   HHI = sum of squared percentage shares of the named countries, on the
--         0 to 10,000 scale.
--
-- Both use the workbook WORLD TOTAL as the denominator, which is the same basis
-- the workbook uses for its own Share of World column. The Other bucket sits in
-- that denominator but contributes no term of its own, because it aggregates
-- many unnamed producers and is not a country. Counting it as one producer
-- would square a sum instead of summing squares and overstate concentration.
--
-- The consequence is carried in the output: the HHI below is a LOWER BOUND.
-- Splitting Other into its real constituent countries could only add positive
-- squared terms. The size of the omission is reported as
-- other_share_of_world_pct on every row.
--
-- Two ranking functions are used on purpose. RANK is reported because it is the
-- honest competition rank and shows ties, while ROW_NUMBER draws the top 3 cut
-- so that a tie on the third position cannot pull four countries into CR3.
--
-- The last three columns compare this result against the CR3/HHI block printed
-- inside the workbook itself. That block sorts the Other bucket in with the
-- countries, so its cobalt CR3 of 97 percent is built by ranking an aggregate
-- second, above Indonesia. The difference is reported rather than hidden.
-- ---------------------------------------------------------------------------

WITH world AS (
    SELECT mineral,
           production_t AS world_production_t
    FROM   global_mining_2024
    WHERE  row_type = 'world_total'
),
other AS (
    SELECT mineral,
           production_t AS other_production_t
    FROM   global_mining_2024
    WHERE  row_type = 'other_bucket'
),
shares AS (
    SELECT
        n.mineral,
        n.country,
        n.production_t,
        100.0 * n.production_t / w.world_production_t AS share_pct,
        RANK()       OVER (PARTITION BY n.mineral ORDER BY n.production_t DESC) AS production_rank,
        ROW_NUMBER() OVER (PARTITION BY n.mineral
                           ORDER BY n.production_t DESC, n.country)             AS cut_position
    FROM   global_mining_2024 n
    JOIN   world w ON w.mineral = n.mineral
    WHERE  n.row_type = 'country'        -- drops Other and WORLD TOTAL
),
metrics AS (
    SELECT
        mineral,
        COUNT(*)                                                        AS named_countries,
        SUM(production_t)                                               AS named_production_t,
        SUM(CASE WHEN cut_position <= 3 THEN share_pct ELSE 0 END)      AS cr3_named_pct,
        SUM(share_pct * share_pct)                                      AS hhi_named_lower_bound,
        MAX(CASE WHEN cut_position = 1 THEN country END)                AS top_1_country,
        MAX(CASE WHEN cut_position = 2 THEN country END)                AS top_2_country,
        MAX(CASE WHEN cut_position = 3 THEN country END)                AS top_3_country,
        -- flags a mineral where two countries share a rank, so the ROW_NUMBER
        -- cut above is doing real work rather than agreeing with RANK by luck
        MAX(CASE WHEN production_rank <> cut_position THEN 1 ELSE 0 END) AS has_rank_tie
    FROM shares
    GROUP BY mineral
)
SELECT
    m.mineral,
    m.named_countries,
    m.named_production_t,
    w.world_production_t,
    o.other_production_t,
    ROUND(100.0 * o.other_production_t / w.world_production_t, 2) AS other_share_of_world_pct,
    ROUND(m.cr3_named_pct, 2)                                     AS cr3_named_pct,
    m.top_1_country,
    m.top_2_country,
    m.top_3_country,
    m.has_rank_tie,
    ROUND(m.hhi_named_lower_bound, 0)                             AS hhi_named_lower_bound,
    CASE WHEN m.hhi_named_lower_bound > 2500
         THEN 'highly concentrated (US DOJ/FTC threshold 2500)'
         ELSE 'moderately concentrated'
    END                                                           AS concentration_read,
    'LOWER BOUND: the Other bucket contributes no HHI term'       AS hhi_caveat,
    ROUND(wb.cr3_pct_workbook, 2)                                 AS cr3_pct_workbook,
    ROUND(m.cr3_named_pct - wb.cr3_pct_workbook, 2)               AS cr3_difference_pp,
    ROUND(wb.hhi_workbook, 0)                                     AS hhi_workbook,
    ROUND(m.hhi_named_lower_bound - wb.hhi_workbook, 0)           AS hhi_difference,
    'workbook counts the Other bucket as one country in both metrics'
                                                                  AS reason_for_difference
FROM metrics m
JOIN world w  ON w.mineral  = m.mineral
JOIN other o  ON o.mineral  = m.mineral
LEFT JOIN global_mining_concentration_workbook wb ON wb.mineral = m.mineral
ORDER BY m.hhi_named_lower_bound DESC;
