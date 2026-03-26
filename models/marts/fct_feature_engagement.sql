-- fct_feature_engagement.sql
-- Weekly engagement by health domain (sleep, activity, heart rate)
-- Maps to WHOOP's feature adoption analytics

with sleep_engagement as (
    select
        member_id,
        sleep_week                                   as week_start,
        'sleep_tracking'                             as feature,
        count(*)                                     as interactions,
        round(avg(hours_asleep)::numeric, 1)         as avg_metric_value
    from {{ ref('stg_sleep') }}
    group by 1, 2
),

activity_engagement as (
    select
        member_id,
        activity_week                                as week_start,
        'activity_tracking'                          as feature,
        count(*)                                     as interactions,
        round(avg(total_steps)::numeric, 0)          as avg_metric_value
    from {{ ref('stg_daily_activity') }}
    group by 1, 2
),

hr_engagement as (
    select
        member_id,
        date_trunc('week', hr_date)::date            as week_start,
        'heart_rate_monitoring'                      as feature,
        count(*)                                     as interactions,
        round(avg(avg_hr)::numeric, 0)               as avg_metric_value
    from {{ ref('stg_heartrate') }}
    group by 1, 2
),

-- Derive recovery feature from sleep efficiency + HR variability
recovery_engagement as (
    select
        s.member_id,
        s.sleep_week                                 as week_start,
        'recovery_score'                             as feature,
        count(*)                                     as interactions,
        round(avg(
            (coalesce(s.sleep_efficiency_pct, 80) * 0.5) +
            (coalesce(h.hr_variability, 10) * 0.5)
        )::numeric, 1)                               as avg_metric_value
    from {{ ref('stg_sleep') }} s
    left join {{ ref('stg_heartrate') }} h
        on s.member_id = h.member_id
        and s.sleep_date = h.hr_date
    group by 1, 2
),

combined as (
    select * from sleep_engagement
    union all
    select * from activity_engagement
    union all
    select * from hr_engagement
    union all
    select * from recovery_engagement
)

select
    week_start,
    feature,
    count(distinct member_id)                        as unique_users,
    sum(interactions)                                 as total_interactions,
    round(avg(avg_metric_value)::numeric, 1)         as avg_metric_value
from combined
group by 1, 2
order by 1, 2
