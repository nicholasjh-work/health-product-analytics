#!/usr/bin/env bash
# setup.sh - Downloads Fitbit datasets, loads into PostgreSQL, generates experiment enrichment
set -euo pipefail

DB_NAME="${PGDATABASE:-health_product_analytics}"
DB_USER="${PGUSER:-postgres}"
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DATA_DIR="$(cd "$(dirname "$0")" && pwd)/data/raw"

echo "=== Health Product Analytics Setup ==="

# --- Step 1: Download Fitbit datasets from Kaggle ---
echo "[1/4] Downloading Fitbit datasets from Kaggle..."
mkdir -p "$DATA_DIR/fitbit_core" "$DATA_DIR/lifesnaps"

if [ ! -f "$DATA_DIR/fitbit_core/dailyActivity_merged.csv" ]; then
    kaggle datasets download -d arashnic/fitbit -p "$DATA_DIR/fitbit_core"
    cd "$DATA_DIR/fitbit_core" && unzip -o *.zip && rm -f *.zip && cd -
    # Flatten: Fitabase data lives in a subdirectory
    find "$DATA_DIR/fitbit_core" -name "*.csv" -not -path "$DATA_DIR/fitbit_core/*.csv" \
        -exec mv {} "$DATA_DIR/fitbit_core/" \;
    echo "    Downloaded Fitbit Fitness Tracker (arashnic)"
else
    echo "    Fitbit core data already exists"
fi

if [ ! -d "$DATA_DIR/lifesnaps/fitbit" ]; then
    kaggle datasets download -d skywescar/lifesnaps-fitbit-dataset -p "$DATA_DIR/lifesnaps"
    cd "$DATA_DIR/lifesnaps" && unzip -o *.zip && rm -f *.zip && cd -
    echo "    Downloaded Lifesnaps Fitbit dataset"
else
    echo "    Lifesnaps data already exists"
fi

# --- Step 2: Create PostgreSQL database and schema ---
echo "[2/4] Creating PostgreSQL schema..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -tc \
    "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<'SQL'
DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

-- Fitbit Core: Daily Activity
CREATE TABLE raw.daily_activity (
    id                      BIGINT,
    activity_date           VARCHAR(20),
    total_steps             INTEGER,
    total_distance          DOUBLE PRECISION,
    tracker_distance        DOUBLE PRECISION,
    logged_activities_distance DOUBLE PRECISION,
    very_active_distance    DOUBLE PRECISION,
    moderately_active_distance DOUBLE PRECISION,
    light_active_distance   DOUBLE PRECISION,
    sedentary_active_distance DOUBLE PRECISION,
    very_active_minutes     INTEGER,
    fairly_active_minutes   INTEGER,
    lightly_active_minutes  INTEGER,
    sedentary_minutes       INTEGER,
    calories                INTEGER
);

-- Fitbit Core: Sleep
CREATE TABLE raw.sleep_day (
    id                      BIGINT,
    sleep_day               VARCHAR(30),
    total_sleep_records     INTEGER,
    total_minutes_asleep    INTEGER,
    total_time_in_bed       INTEGER
);

-- Fitbit Core: Heart Rate (per second, sampled)
CREATE TABLE raw.heartrate_seconds (
    id                      BIGINT,
    time                    VARCHAR(30),
    value                   INTEGER
);

-- Fitbit Core: Daily Intensities
CREATE TABLE raw.daily_intensities (
    id                      BIGINT,
    activity_day            VARCHAR(20),
    sedentary_minutes       INTEGER,
    lightly_active_minutes  INTEGER,
    fairly_active_minutes   INTEGER,
    very_active_minutes     INTEGER,
    sedentary_active_distance DOUBLE PRECISION,
    light_active_distance   DOUBLE PRECISION,
    moderately_active_distance DOUBLE PRECISION,
    very_active_distance    DOUBLE PRECISION
);

-- Fitbit Core: Daily Calories
CREATE TABLE raw.daily_calories (
    id                      BIGINT,
    activity_day            VARCHAR(20),
    calories                INTEGER
);

-- Fitbit Core: METs (Metabolic Equivalent)
CREATE TABLE raw.minute_mets (
    id                      BIGINT,
    activity_minute         VARCHAR(30),
    mets                    INTEGER
);

-- Enrichment: Experiment results (generated)
CREATE TABLE raw.experiments (
    experiment_name         VARCHAR(100),
    feature                 VARCHAR(50),
    metric                  VARCHAR(100),
    start_month             VARCHAR(7),
    end_month               VARCHAR(7),
    control_size            INTEGER,
    treatment_size          INTEGER,
    control_rate            DOUBLE PRECISION,
    treatment_rate          DOUBLE PRECISION,
    absolute_lift           DOUBLE PRECISION,
    relative_lift_pct       DOUBLE PRECISION,
    p_value                 DOUBLE PRECISION,
    significant             BOOLEAN
);

-- Enrichment: Member profiles (derived from device IDs + synthetic attributes)
CREATE TABLE raw.member_profiles (
    member_id               BIGINT,
    signup_date             DATE,
    plan_type               VARCHAR(20),
    age                     INTEGER,
    primary_health_goal     VARCHAR(50),
    engagement_level        DOUBLE PRECISION
);

CREATE INDEX idx_daily_activity_id ON raw.daily_activity(id);
CREATE INDEX idx_sleep_id ON raw.sleep_day(id);
CREATE INDEX idx_heartrate_id ON raw.heartrate_seconds(id);
SQL
echo "    Schema created"

# --- Step 3: Load CSVs ---
echo "[3/4] Loading Fitbit CSVs into PostgreSQL..."
load_csv() {
    local table=$1
    local file=$2
    if [ -f "$file" ]; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
            "\\copy raw.$table FROM '$file' WITH (FORMAT csv, HEADER true, NULL '')"
        echo "    Loaded $table ($(wc -l < "$file") rows)"
    else
        echo "    WARNING: $file not found"
    fi
}

load_csv "daily_activity"    "$DATA_DIR/fitbit_core/dailyActivity_merged.csv"
load_csv "sleep_day"         "$DATA_DIR/fitbit_core/sleepDay_merged.csv"
load_csv "daily_intensities" "$DATA_DIR/fitbit_core/dailyIntensities_merged.csv"
load_csv "daily_calories"    "$DATA_DIR/fitbit_core/dailyCalories_merged.csv"

# Heart rate is large; load sample if full file exists
HR_FILE="$DATA_DIR/fitbit_core/heartrate_seconds_merged.csv"
if [ -f "$HR_FILE" ]; then
    echo "    Loading heartrate_seconds (sampling every 60th row for performance)..."
    head -1 "$HR_FILE" > /tmp/hr_sample.csv
    awk 'NR % 60 == 0' "$HR_FILE" >> /tmp/hr_sample.csv
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
        "\\copy raw.heartrate_seconds FROM '/tmp/hr_sample.csv' WITH (FORMAT csv, HEADER true, NULL '')"
    rm /tmp/hr_sample.csv
    echo "    Loaded heartrate_seconds (sampled)"
fi

# --- Step 4: Generate enrichment data ---
echo "[4/4] Generating enrichment data..."
python3 data/generate_enrichment.py

echo ""
echo "=== Setup complete ==="
echo "Database: $DB_NAME"
echo "Run 'dbt build' to create analytics models"
echo "Run 'streamlit run dashboard/app.py' for the dashboard"
