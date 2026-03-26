-- fct_member_retention.sql
-- Weekly retention by engagement tier and health goal

with member_info as (
    select
        member_id,
        signup_date,
        primary_health_goal,
        case
            when engagement_level >= 0.7 then 'high'
            when engagement_level >= 0.4 then 'medium'
            else 'low'
        end as engagement_tier
    from {{ source('raw', 'member_profiles') }}
),

member_weeks_active as (
    select distinct
        member_id,
        activity_week as active_week
    from {{ ref('stg_daily_activity') }}
),

joined as (
    select
        mi.member_id,
        mi.signup_date,
        mi.primary_health_goal,
        mi.engagement_tier,
        mw.active_week,
        (mw.active_week - mi.signup_date) / 7 as tenure_weeks
    from member_weeks_active mw
    inner join member_info mi using (member_id)
    where mw.active_week >= mi.signup_date
),

cohort_sizes as (
    select
        engagement_tier,
        primary_health_goal,
        count(distinct member_id) as cohort_size
    from member_info
    group by 1, 2
),

retention_counts as (
    select
        engagement_tier,
        primary_health_goal,
        tenure_weeks,
        count(distinct member_id) as active_count
    from joined
    where tenure_weeks between 0 and 12
    group by 1, 2, 3
)

select
    r.engagement_tier,
    r.primary_health_goal,
    r.tenure_weeks,
    c.cohort_size,
    r.active_count,
    round(r.active_count * 100.0 / nullif(c.cohort_size, 0), 2) as retention_rate
from retention_counts r
inner join cohort_sizes c
    on r.engagement_tier = c.engagement_tier
    and r.primary_health_goal = c.primary_health_goal
order by r.engagement_tier, r.primary_health_goal, r.tenure_weeks
