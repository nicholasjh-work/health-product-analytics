-- stg_sleep.sql
-- Clean and derive sleep quality metrics from Fitbit sleep data

with source as (
    select * from {{ source('raw', 'sleep_day') }}
),

cleaned as (
    select
        id                                                       as member_id,
        to_date(split_part(sleep_day, ' ', 1), 'MM/DD/YYYY')    as sleep_date,
        date_trunc('week',
            to_date(split_part(sleep_day, ' ', 1), 'MM/DD/YYYY'))::date as sleep_week,
        total_sleep_records,
        total_minutes_asleep,
        total_time_in_bed,
        round(total_minutes_asleep / 60.0, 1)                   as hours_asleep,
        -- Sleep efficiency: % of time in bed actually sleeping
        case
            when total_time_in_bed > 0
            then round(total_minutes_asleep * 100.0 / total_time_in_bed, 1)
            else null
        end                                                      as sleep_efficiency_pct,
        -- Sleep quality tier
        case
            when total_minutes_asleep >= 420 and total_minutes_asleep <= 540 then 'optimal'   -- 7-9 hours
            when total_minutes_asleep >= 360 then 'adequate'                                   -- 6-7 hours
            when total_minutes_asleep >= 300 then 'insufficient'                               -- 5-6 hours
            else 'poor'                                                                        -- < 5 hours
        end                                                      as sleep_quality
    from source
    where sleep_day is not null
)

select * from cleaned
