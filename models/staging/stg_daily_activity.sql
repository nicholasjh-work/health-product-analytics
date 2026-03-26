-- stg_daily_activity.sql
-- Clean and standardize Fitbit daily activity data

with source as (
    select * from {{ source('raw', 'daily_activity') }}
),

cleaned as (
    select
        id                                                       as member_id,
        to_date(activity_date, 'MM/DD/YYYY')                     as activity_date,
        date_trunc('week', to_date(activity_date, 'MM/DD/YYYY'))::date as activity_week,
        total_steps,
        round(total_distance::numeric, 2)                        as total_distance_km,
        very_active_minutes,
        fairly_active_minutes,
        lightly_active_minutes,
        sedentary_minutes,
        (very_active_minutes + fairly_active_minutes)            as moderate_plus_minutes,
        calories,
        -- Activity level classification
        case
            when very_active_minutes >= 30 then 'high'
            when (very_active_minutes + fairly_active_minutes) >= 20 then 'moderate'
            when total_steps >= 5000 then 'light'
            else 'sedentary'
        end                                                      as activity_level,
        -- Step goal (10K benchmark)
        (total_steps >= 10000)                                   as met_step_goal
    from source
    where activity_date is not null
)

select * from cleaned
