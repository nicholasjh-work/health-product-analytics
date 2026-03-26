"""
Health product analytics on Fitbit data via PostgreSQL.
Feature engagement, health outcomes, cohort retention, and experiment analysis.
"""

import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _get_engine():
    from sqlalchemy import create_engine
    db = os.getenv("PGDATABASE", "health_product_analytics")
    user = os.getenv("PGUSER", "postgres")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    pw = os.getenv("PGPASSWORD", "")
    return create_engine(f"postgresql://{user}:{pw}@{host}:{port}/{db}")


def _query(sql: str) -> pd.DataFrame:
    from sqlalchemy import text
    engine = _get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def _try_query(mart_sql: str, raw_sql: str) -> pd.DataFrame:
    for sql in [mart_sql, raw_sql]:
        try:
            return _query(sql)
        except Exception:
            continue
    logger.warning("Both mart and raw queries failed")
    return pd.DataFrame()


def load_feature_engagement() -> pd.DataFrame:
    mart = "SELECT * FROM marts.fct_feature_engagement ORDER BY week_start, feature"
    raw = """
    WITH sleep_eng AS (
        SELECT id as member_id,
            date_trunc('week', to_date(split_part(sleep_day,' ',1), 'MM/DD/YYYY'))::date as week_start,
            'sleep_tracking' as feature, count(*) as interactions
        FROM raw.sleep_day WHERE sleep_day IS NOT NULL GROUP BY 1, 2
    ),
    activity_eng AS (
        SELECT id as member_id,
            date_trunc('week', to_date(activity_date, 'MM/DD/YYYY'))::date as week_start,
            'activity_tracking' as feature, count(*) as interactions
        FROM raw.daily_activity WHERE activity_date IS NOT NULL GROUP BY 1, 2
    ),
    hr_eng AS (
        SELECT id as member_id,
            date_trunc('week', to_date(split_part(time,' ',1), 'MM/DD/YYYY'))::date as week_start,
            'heart_rate_monitoring' as feature, count(*) as interactions
        FROM raw.heartrate_seconds WHERE time IS NOT NULL GROUP BY 1, 2
    ),
    combined AS (
        SELECT * FROM sleep_eng UNION ALL SELECT * FROM activity_eng UNION ALL SELECT * FROM hr_eng
    )
    SELECT week_start::text, feature,
        COUNT(DISTINCT member_id) as unique_users,
        SUM(interactions) as total_interactions
    FROM combined GROUP BY 1, 2 ORDER BY 1, 2
    """
    return _try_query(mart, raw)


def load_health_outcomes() -> pd.DataFrame:
    mart = "SELECT * FROM marts.fct_health_outcomes ORDER BY member_id, week_start"
    raw = """
    WITH weekly_activity AS (
        SELECT id as member_id,
            date_trunc('week', to_date(activity_date, 'MM/DD/YYYY'))::date as week_start,
            ROUND(AVG(total_steps)::numeric, 0) as avg_daily_steps,
            ROUND(AVG(very_active_minutes + fairly_active_minutes)::numeric, 0) as avg_active_minutes,
            ROUND(AVG(calories)::numeric, 0) as avg_calories
        FROM raw.daily_activity WHERE activity_date IS NOT NULL GROUP BY 1, 2
    ),
    weekly_sleep AS (
        SELECT id as member_id,
            date_trunc('week', to_date(split_part(sleep_day,' ',1), 'MM/DD/YYYY'))::date as week_start,
            ROUND(AVG(total_minutes_asleep / 60.0)::numeric, 1) as avg_hours_asleep,
            ROUND(AVG(CASE WHEN total_time_in_bed > 0
                THEN total_minutes_asleep * 100.0 / total_time_in_bed ELSE NULL END)::numeric, 1) as avg_sleep_efficiency
        FROM raw.sleep_day WHERE sleep_day IS NOT NULL GROUP BY 1, 2
    )
    SELECT COALESCE(a.member_id, s.member_id) as member_id,
        COALESCE(a.week_start, s.week_start)::text as week_start,
        a.avg_daily_steps, a.avg_active_minutes, a.avg_calories,
        s.avg_hours_asleep, s.avg_sleep_efficiency
    FROM weekly_activity a
    FULL OUTER JOIN weekly_sleep s ON a.member_id = s.member_id AND a.week_start = s.week_start
    ORDER BY 1, 2
    """
    return _try_query(mart, raw)


def load_member_retention() -> pd.DataFrame:
    mart = "SELECT * FROM marts.fct_member_retention ORDER BY engagement_tier, tenure_weeks"
    raw = """
    WITH member_info AS (
        SELECT member_id,
            CASE WHEN engagement_level >= 0.7 THEN 'high'
                 WHEN engagement_level >= 0.4 THEN 'medium' ELSE 'low' END as engagement_tier,
            signup_date
        FROM raw.member_profiles
    ),
    member_weeks AS (
        SELECT DISTINCT id as member_id,
            date_trunc('week', to_date(activity_date, 'MM/DD/YYYY'))::date as active_week
        FROM raw.daily_activity WHERE activity_date IS NOT NULL
    ),
    joined AS (
        SELECT mi.engagement_tier, (mw.active_week - mi.signup_date) / 7 as tenure_weeks, mi.member_id
        FROM member_weeks mw INNER JOIN member_info mi ON mw.member_id = mi.member_id
        WHERE mw.active_week >= mi.signup_date
    ),
    sizes AS (SELECT engagement_tier, COUNT(DISTINCT member_id) as cohort_size FROM member_info GROUP BY 1),
    counts AS (
        SELECT engagement_tier, tenure_weeks, COUNT(DISTINCT member_id) as active_count
        FROM joined WHERE tenure_weeks BETWEEN 0 AND 12 GROUP BY 1, 2
    )
    SELECT r.engagement_tier, r.tenure_weeks::int, s.cohort_size, r.active_count,
        ROUND(r.active_count * 100.0 / NULLIF(s.cohort_size, 0), 2) as retention_rate
    FROM counts r INNER JOIN sizes s USING (engagement_tier)
    ORDER BY 1, 2
    """
    return _try_query(mart, raw)


def load_experiments() -> pd.DataFrame:
    try:
        return _query("SELECT * FROM raw.experiments ORDER BY experiment_name")
    except Exception:
        from pathlib import Path
        csv = Path(__file__).parent.parent / "data" / "experiments.csv"
        if csv.exists():
            return pd.read_csv(csv)
        return pd.DataFrame()


def load_sleep_quality_distribution() -> pd.DataFrame:
    raw = """
    SELECT
        CASE WHEN total_minutes_asleep >= 420 AND total_minutes_asleep <= 540 THEN 'optimal'
             WHEN total_minutes_asleep >= 360 THEN 'adequate'
             WHEN total_minutes_asleep >= 300 THEN 'insufficient'
             ELSE 'poor' END as sleep_quality,
        COUNT(*) as nights,
        ROUND(AVG(total_minutes_asleep / 60.0)::numeric, 1) as avg_hours,
        ROUND(AVG(CASE WHEN total_time_in_bed > 0
            THEN total_minutes_asleep * 100.0 / total_time_in_bed ELSE NULL END)::numeric, 1) as avg_efficiency
    FROM raw.sleep_day WHERE sleep_day IS NOT NULL
    GROUP BY 1 ORDER BY avg_hours DESC
    """
    try:
        return _query(raw)
    except Exception:
        return pd.DataFrame()


def load_activity_distribution() -> pd.DataFrame:
    raw = """
    SELECT
        CASE WHEN very_active_minutes >= 30 THEN 'high'
             WHEN (very_active_minutes + fairly_active_minutes) >= 20 THEN 'moderate'
             WHEN total_steps >= 5000 THEN 'light'
             ELSE 'sedentary' END as activity_level,
        COUNT(*) as days,
        ROUND(AVG(total_steps)::numeric, 0) as avg_steps,
        ROUND(AVG(calories)::numeric, 0) as avg_calories,
        ROUND(AVG(very_active_minutes + fairly_active_minutes)::numeric, 0) as avg_active_minutes
    FROM raw.daily_activity WHERE activity_date IS NOT NULL
    GROUP BY 1 ORDER BY avg_steps DESC
    """
    try:
        return _query(raw)
    except Exception:
        return pd.DataFrame()
