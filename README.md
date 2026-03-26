# Health Product Analytics

**[Live Interactive Dashboard](https://healthmetrics.nicholashidalgo.com)**

Health-specific product analytics for a wearable wellness platform, built on real Fitbit data from 30+ users (Kaggle, CC0 license). Tracks feature engagement by health domain (sleep, activity, heart rate, recovery), health outcome trends, behavior change KPIs, cohort retention by engagement tier, and A/B experiment analysis.

## Why This Exists

This project demonstrates what a Health Product Analytics Manager delivers at a wearable health company: building health-specific KPIs, measuring feature adoption across wellness domains, connecting engagement intensity to retention, and running experiments that validate product decisions. Every analysis maps to a real product question: which health features drive engagement, are members actually improving their health behaviors, does higher engagement predict retention, and do new features move the needle.

## Architecture

```
Fitbit (Kaggle) ─► setup.sh ─► PostgreSQL ─► dbt models ─► Python analysis ─► Streamlit
Lifesnaps (Kaggle) ──┘              │
                       Enrichment   │
                       (profiles +  │
                        experiments)┘
```

```
health-product-analytics/
├── setup.sh                          # One-command setup
├── data/
│   ├── raw/                          # Fitbit CSVs (downloaded by setup.sh)
│   │   ├── fitbit_core/              # arashnic/fitbit dataset
│   │   └── lifesnaps/                # skywescar/lifesnaps-fitbit-dataset
│   ├── generate_enrichment.py        # Member profiles + experiments
│   ├── member_profiles.csv
│   └── experiments.csv
├── models/
│   ├── staging/
│   │   ├── sources.yml
│   │   ├── stg_daily_activity.sql    # Steps, distance, active minutes, calories
│   │   ├── stg_sleep.sql             # Sleep hours, efficiency, quality tier
│   │   └── stg_heartrate.sql         # Daily HR aggregates, HRV proxy, zones
│   └── marts/
│       ├── fct_feature_engagement.sql  # Weekly users by health domain
│       ├── fct_health_outcomes.sql     # Sleep + activity + HR trends over tenure
│       ├── fct_member_retention.sql    # Retention by engagement tier + goal
│       └── (experiments loaded from raw)
├── analysis/
│   └── health_analytics.py           # Query layer with mart/raw fallback
├── dashboard/
│   └── app.py                        # Streamlit dashboard (5 tabs)
├── dbt_project.yml
├── profiles.yml.example
├── .env.example
└── requirements.txt
```

## Data Sources

### Fitbit Fitness Tracker (Real Data, CC0 License)

30 consented Fitbit users, ~2 months of continuous wear data.

| Table | Records | Description |
|-------|---------|-------------|
| `daily_activity` | 940 | Steps, distance, intensity minutes, calories per day |
| `sleep_day` | 413 | Minutes asleep, time in bed, sleep records per day |
| `heartrate_seconds` | 2.4M | Per-second heart rate (sampled to per-minute for performance) |
| `daily_intensities` | 940 | Sedentary, light, fairly active, very active minutes |
| `daily_calories` | 940 | Total daily calorie burn |

### Lifesnaps Fitbit (Real Data, Supplemental)

Extended-duration Fitbit data with self-reported stress, mood, and lifestyle surveys. Used to enrich behavioral context.

### Enrichment Layer (Synthetic)

| Table | Description |
|-------|-------------|
| `member_profiles` | Health goals, plan type, age, engagement level (tied to real Fitbit user IDs) |
| `experiments` | 4 A/B test results calibrated on real engagement distributions |

## Analytics Modules

| Module | Business Question | Key Output |
|--------|-------------------|------------|
| **Feature Engagement** | Which health features do members use most? | Weekly unique users by sleep, activity, HR, recovery |
| **Health Outcomes** | Are members improving their health behaviors? | Steps, sleep hours, active minutes trends over tenure |
| **Sleep & Activity Distribution** | What does our member population look like? | Quality tier breakdown (optimal/adequate/insufficient/poor) |
| **Member Retention** | Does engagement predict retention? | Retention curves by high/medium/low engagement tier |
| **Experiments** | Do new features move the needle? | A/B test results with lift, p-value, significance |

## Health-Specific KPIs

Modeled after the KPIs a health product analytics team would track:

| KPI | Definition | Source |
|-----|-----------|--------|
| Sleep Score | Hours asleep + sleep efficiency weighted composite | `stg_sleep` |
| Recovery Score | Sleep efficiency (50%) + HR variability (50%) | `stg_sleep` + `stg_heartrate` |
| Activity Level | Tier based on active minutes and step count | `stg_daily_activity` |
| Step Goal Completion | % of days meeting 10K step benchmark | `stg_daily_activity` |
| HR Zone Distribution | % time in resting, light, moderate, vigorous zones | `stg_heartrate` |
| Feature Adoption | Weekly unique users per health feature | `fct_feature_engagement` |
| Behavior Change Delta | First week vs last week outcome comparison | `fct_health_outcomes` |

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Kaggle CLI (`pip install kaggle`)
- Kaggle API credentials (~/.kaggle/kaggle.json)

### Setup

```bash
git clone https://github.com/nicholasjh-work/health-product-analytics.git
cd health-product-analytics
pip install -r requirements.txt
cp .env.example .env  # Edit with your PostgreSQL credentials

# One-command setup: downloads Fitbit data, creates schema, loads CSVs
chmod +x setup.sh
./setup.sh

# Build dbt models
cp profiles.yml.example ~/.dbt/profiles.yml
dbt build

# Launch dashboard
streamlit run dashboard/app.py
```

## dbt Models

### Staging

| Model | Source | Key Transformations |
|-------|--------|-------------------|
| `stg_daily_activity` | `raw.daily_activity` | Date parsing, activity level classification, step goal flag |
| `stg_sleep` | `raw.sleep_day` | Sleep hours, efficiency %, quality tier (optimal/adequate/insufficient/poor) |
| `stg_heartrate` | `raw.heartrate_seconds` | Daily aggregation, HRV proxy (SDNN-like), HR zone distribution |

### Marts

| Model | Grain | Description |
|-------|-------|-------------|
| `fct_feature_engagement` | week x feature | Unique users and interactions by health domain |
| `fct_health_outcomes` | member x week | Sleep, activity, HR metrics with tenure tracking |
| `fct_member_retention` | engagement_tier x tenure_week | Retention rate by engagement level |

## Experiment Framework

Four experiments simulated on real Fitbit engagement distributions:

| Experiment | Feature | Metric | Lift | Significant |
|-----------|---------|--------|------|-------------|
| `sleep_coaching_v2` | Sleep Tracking | 7d sleep score improvement | ~12% | Yes |
| `activity_nudge_timing` | Activity Tracking | Daily step goal completion | ~17% | Yes |
| `recovery_insight_card` | Recovery Score | Weekly recovery check rate | ~24% | Yes |
| `heart_rate_alert_threshold` | Heart Rate Monitoring | HR alert engagement 30d | ~31% | Yes |

## Tech Stack

PostgreSQL, dbt, Python, pandas, SQLAlchemy, Streamlit, Plotly, matplotlib

Production target: Snowflake (profiles.yml.example includes Snowflake config)

## Related Repos

- [feature-adoption-retention](https://github.com/nicholasjh-work/feature-adoption-retention) - Feature engagement and retention cohorts
- [subscription-financial-model](https://github.com/nicholasjh-work/subscription-financial-model) - DTC subscription unit economics
- [fpna-forecasting-model](https://github.com/nicholasjh-work/fpna-forecasting-model) - Driver-based revenue forecasting

## Author

**Nicholas Hidalgo** - [nicholashidalgo.com](https://www.nicholashidalgo.com) | [LinkedIn](https://www.linkedin.com/in/nicholashidalgo/)
