-- fct_health_outcomes.sql
-- Weekly health outcome trends: sleep quality, activity levels, heart health
-- Tracks behavior change over member tenure

with member_tenure as (
    select
        member_id,
        signup_date,
        engagement_level,
        primary_health_goal
    from {{ source('raw', 'member_profiles') }}
),

weekly_sleep as (
    select
        member_id,
        sleep_week                                   as week_start,
        round(avg(hours_asleep)::numeric, 1)         as avg_hours_asleep,
        round(avg(sleep_efficiency_pct)::numeric, 1) as avg_sleep_efficiency
    from {{ ref('stg_sleep') }}
    group by 1, 2
),

weekly_activity as (
    select
        member_id,
        activity_week                                as week_start,
        round(avg(total_steps)::numeric, 0)          as avg_daily_steps,
        round(avg(moderate_plus_minutes)::numeric, 0) as avg_active_minutes,
        round(avg(calories)::numeric, 0)             as avg_calories,
        round(avg(case when met_step_goal then 1 else 0 end) * 100, 1) as step_goal_pct
    from {{ ref('stg_daily_activity') }}
    group by 1, 2
),

weekly_hr as (
    select
        member_id,
        date_trunc('week', hr_date)::date            as week_start,
        round(avg(avg_hr)::numeric, 0)               as avg_resting_hr,
        round(avg(hr_variability)::numeric, 1)       as avg_hrv
    from {{ ref('stg_heartrate') }}
    group by 1, 2
),

combined as (
    select
        coalesce(s.member_id, a.member_id, h.member_id) as member_id,
        coalesce(s.week_start, a.week_start, h.week_start) as week_start,
        s.avg_hours_asleep,
        s.avg_sleep_efficiency,
        a.avg_daily_steps,
        a.avg_active_minutes,
        a.avg_calories,
        a.step_goal_pct,
        h.avg_resting_hr,
        h.avg_hrv
    from weekly_sleep s
    full outer join weekly_activity a on s.member_id = a.member_id and s.week_start = a.week_start
    full outer join weekly_hr h on coalesce(s.member_id, a.member_id) = h.member_id
        and coalesce(s.week_start, a.week_start) = h.week_start
)

select
    c.*,
    m.primary_health_goal,
    m.engagement_level,
    -- Tenure in weeks
    (c.week_start - m.signup_date) / 7               as tenure_weeks
from combined c
left join member_tenure m on c.member_id = m.member_id
order by c.member_id, c.week_start
