-- stg_heartrate.sql
-- Aggregate heart rate data to daily level with HRV-proxy and zone metrics

with source as (
    select * from {{ source('raw', 'heartrate_seconds') }}
),

daily_hr as (
    select
        id                                                       as member_id,
        to_date(split_part(time, ' ', 1), 'MM/DD/YYYY')         as hr_date,
        round(avg(value)::numeric, 0)                            as avg_hr,
        min(value)                                               as min_hr,
        max(value)                                               as max_hr,
        -- HRV proxy: standard deviation of heart rate (SDNN-like)
        round(stddev(value)::numeric, 1)                         as hr_variability,
        count(*)                                                 as reading_count,
        -- Heart rate zones (based on standard zones)
        round(sum(case when value < 60 then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 1)                            as pct_resting,
        round(sum(case when value between 60 and 100 then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 1)                            as pct_light,
        round(sum(case when value between 100 and 140 then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 1)                            as pct_moderate,
        round(sum(case when value > 140 then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 1)                            as pct_vigorous
    from source
    where time is not null
      and value between 30 and 220  -- physiological bounds
    group by 1, 2
)

select * from daily_hr
