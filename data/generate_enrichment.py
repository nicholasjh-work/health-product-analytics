"""
Generate enrichment data for health product analytics.
Creates member profiles (synthetic attributes tied to real Fitbit device IDs)
and A/B experiment results calibrated on real engagement distributions.
"""

import logging
import math
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

np.random.seed(42)
random.seed(42)

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw" / "fitbit_core"

HEALTH_GOALS = [
    "improve_sleep", "increase_fitness", "manage_stress", "lose_weight",
    "monitor_heart_health", "track_recovery", "hormonal_health", "general_wellness",
]

PLANS = {"free_trial": 0.15, "monthly": 0.35, "annual": 0.40, "family": 0.10}

EXPERIMENTS = [
    {"name": "sleep_coaching_v2", "feature": "sleep_tracking",
     "start": "2016-04", "end": "2016-04",
     "control_rate": 0.65, "treatment_rate": 0.73,
     "metric": "7d_sleep_score_improvement"},
    {"name": "activity_nudge_timing", "feature": "activity_tracking",
     "start": "2016-04", "end": "2016-05",
     "control_rate": 0.52, "treatment_rate": 0.61,
     "metric": "daily_step_goal_completion"},
    {"name": "recovery_insight_card", "feature": "recovery_score",
     "start": "2016-04", "end": "2016-05",
     "control_rate": 0.38, "treatment_rate": 0.47,
     "metric": "weekly_recovery_check_rate"},
    {"name": "heart_rate_alert_threshold", "feature": "heart_rate_monitoring",
     "start": "2016-04", "end": "2016-05",
     "control_rate": 0.42, "treatment_rate": 0.55,
     "metric": "hr_alert_engagement_30d"},
]


def get_fitbit_user_ids() -> list[int]:
    """Extract unique user IDs from Fitbit daily activity data."""
    activity_file = RAW_DIR / "dailyActivity_merged.csv"
    if activity_file.exists():
        df = pd.read_csv(activity_file, usecols=["Id"])
        return sorted(df["Id"].unique().tolist())
    # Fallback: known Fitbit dataset IDs (30 users)
    return [
        1503960366, 1624580081, 1644430081, 1844505072, 1927972279,
        2022484408, 2026352035, 2320127002, 2347167796, 2873212765,
        3372868164, 3977333714, 4020332650, 4057192912, 4319703577,
        4388161847, 4445114986, 4558609924, 4702921684, 5553957443,
        5577150313, 6117666160, 6290855005, 6775888955, 6962181067,
        7007744171, 7086361926, 8053475328, 8378563200, 8877689391,
    ]


def generate_member_profiles(user_ids: list[int]) -> pd.DataFrame:
    """Create member profiles with synthetic attributes for real Fitbit user IDs."""
    logger.info("Generating member profiles for %d users...", len(user_ids))
    records = []
    plans = list(PLANS.keys())
    plan_weights = list(PLANS.values())

    for uid in user_ids:
        signup_offset = random.randint(0, 90)
        signup_date = pd.Timestamp("2016-03-12") - pd.Timedelta(days=signup_offset)
        plan = random.choices(plans, weights=plan_weights, k=1)[0]
        age = random.randint(22, 62)
        goal = random.choice(HEALTH_GOALS)
        engagement = round(np.random.beta(3, 2), 3)

        records.append({
            "member_id": uid,
            "signup_date": signup_date.date(),
            "plan_type": plan,
            "age": age,
            "primary_health_goal": goal,
            "engagement_level": engagement,
        })

    return pd.DataFrame(records)


def generate_experiments(user_ids: list[int]) -> pd.DataFrame:
    """Generate A/B test results calibrated on real user count."""
    logger.info("Generating experiment results...")
    records = []

    for exp in EXPERIMENTS:
        n = len(user_ids)
        n_control = n // 2
        n_treatment = n - n_control

        control_successes = np.random.binomial(n_control, exp["control_rate"])
        treatment_successes = np.random.binomial(n_treatment, exp["treatment_rate"])

        cr = control_successes / n_control
        tr = treatment_successes / n_treatment
        lift = (tr - cr) / cr * 100 if cr > 0 else 0

        pooled = (control_successes + treatment_successes) / (n_control + n_treatment)
        se = math.sqrt(pooled * (1 - pooled) * (1 / n_control + 1 / n_treatment)) if pooled > 0 else 1
        z = (tr - cr) / se
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

        records.append({
            "experiment_name": exp["name"],
            "feature": exp["feature"],
            "metric": exp["metric"],
            "start_month": exp["start"],
            "end_month": exp["end"],
            "control_size": n_control,
            "treatment_size": n_treatment,
            "control_rate": round(cr, 4),
            "treatment_rate": round(tr, 4),
            "absolute_lift": round(tr - cr, 4),
            "relative_lift_pct": round(lift, 2),
            "p_value": round(p_val, 4),
            "significant": p_val < 0.05,
        })

    return pd.DataFrame(records)


def load_to_postgres(df: pd.DataFrame, table: str) -> None:
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=os.getenv("PGDATABASE", "health_product_analytics"),
            user=os.getenv("PGUSER", "postgres"),
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
        )
        cur = conn.cursor()
        cur.execute(f"TRUNCATE raw.{table};")
        cols = df.columns.tolist()
        placeholders = ", ".join(["%s"] * len(cols))
        insert = f"INSERT INTO raw.{table} ({', '.join(cols)}) VALUES ({placeholders})"
        for _, row in df.iterrows():
            cur.execute(insert, tuple(row))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Loaded %s to PostgreSQL (%d rows)", table, len(df))
    except Exception as e:
        logger.warning("Could not load to PostgreSQL: %s", e)


def main() -> None:
    logger.info("=== Health Product Analytics Enrichment Generator ===")
    user_ids = get_fitbit_user_ids()
    logger.info("Found %d Fitbit user IDs", len(user_ids))

    profiles = generate_member_profiles(user_ids)
    profiles.to_csv(DATA_DIR / "member_profiles.csv", index=False)
    logger.info("Saved member_profiles.csv")

    experiments = generate_experiments(user_ids)
    experiments.to_csv(DATA_DIR / "experiments.csv", index=False)
    logger.info("Saved experiments.csv")

    try:
        load_to_postgres(profiles, "member_profiles")
        load_to_postgres(experiments, "experiments")
    except Exception as e:
        logger.warning("PostgreSQL load skipped: %s", e)

    logger.info("Done. %d profiles, %d experiments", len(profiles), len(experiments))


if __name__ == "__main__":
    main()
