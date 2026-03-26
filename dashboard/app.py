"""
Health Product Analytics Dashboard
Interactive analytics for a wearable health platform.
Data: Fitbit Fitness Tracker + Lifesnaps (Kaggle) + synthetic enrichment.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.health_analytics import (
    load_activity_distribution,
    load_experiments,
    load_feature_engagement,
    load_health_outcomes,
    load_member_retention,
    load_sleep_quality_distribution,
)

st.set_page_config(page_title="Health Product Analytics", layout="wide", page_icon="💚")


@st.cache_data(ttl=600)
def get_data():
    engagement = load_feature_engagement()
    outcomes = load_health_outcomes()
    retention = load_member_retention()
    experiments = load_experiments()
    sleep_dist = load_sleep_quality_distribution()
    activity_dist = load_activity_distribution()
    return engagement, outcomes, retention, experiments, sleep_dist, activity_dist


engagement, outcomes, retention, experiments, sleep_dist, activity_dist = get_data()

if engagement.empty and outcomes.empty:
    st.error("No data available. Run setup.sh to load Fitbit data into PostgreSQL.")
    st.stop()

# --- Header ---
st.title("💚 Health Product Analytics")
st.markdown("*Real wearable data (Fitbit) with health-specific KPIs, behavior change tracking, and experimentation*")

# --- KPI Cards ---
col1, col2, col3, col4 = st.columns(4)
if not outcomes.empty:
    latest_outcomes = outcomes[outcomes["week_start"] == outcomes["week_start"].max()]
    col1.metric("Avg Daily Steps", f"{latest_outcomes['avg_daily_steps'].mean():,.0f}")
    col2.metric("Avg Hours Asleep", f"{latest_outcomes['avg_hours_asleep'].mean():.1f}")
    col3.metric("Avg Active Minutes", f"{latest_outcomes['avg_active_minutes'].mean():.0f}")
    col4.metric("Avg Calories", f"{latest_outcomes['avg_calories'].mean():,.0f}")

st.divider()

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Feature Engagement", "Health Outcomes", "Sleep & Activity",
    "Member Retention", "Experiments"
])

with tab1:
    st.subheader("Feature Engagement by Health Domain")
    if not engagement.empty:
        fig = px.line(engagement, x="week_start", y="unique_users", color="feature",
                      labels={"unique_users": "Unique Users", "week_start": "Week"},
                      template="plotly_white")
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

        # Feature adoption summary
        feature_totals = engagement.groupby("feature").agg(
            total_unique_users=("unique_users", "sum"),
            avg_weekly_users=("unique_users", "mean"),
        ).round(0).sort_values("total_unique_users", ascending=False)
        st.subheader("Feature Adoption Summary")
        st.dataframe(feature_totals, use_container_width=True)

with tab2:
    st.subheader("Health Outcomes Over Time")
    if not outcomes.empty:
        # Aggregate to weekly across all members
        weekly_agg = outcomes.groupby("week_start").agg({
            "avg_daily_steps": "mean",
            "avg_hours_asleep": "mean",
            "avg_active_minutes": "mean",
            "avg_calories": "mean",
        }).reset_index()

        metric = st.selectbox("Select metric", [
            "avg_daily_steps", "avg_hours_asleep", "avg_active_minutes", "avg_calories"
        ], format_func=lambda x: x.replace("avg_", "").replace("_", " ").title())

        fig = px.line(weekly_agg, x="week_start", y=metric,
                      labels={metric: metric.replace("avg_", "").replace("_", " ").title(),
                              "week_start": "Week"},
                      template="plotly_white")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        # Behavior change: compare first week vs last week
        if len(weekly_agg) >= 2:
            first = weekly_agg.iloc[0]
            last = weekly_agg.iloc[-1]
            st.subheader("Behavior Change: First Week vs Last Week")
            c1, c2, c3 = st.columns(3)
            for col_widget, m in zip([c1, c2, c3], ["avg_daily_steps", "avg_hours_asleep", "avg_active_minutes"]):
                delta = last[m] - first[m]
                pct = (delta / first[m] * 100) if first[m] != 0 else 0
                col_widget.metric(m.replace("avg_", "").replace("_", " ").title(),
                                  f"{last[m]:,.1f}", f"{pct:+.1f}%")

with tab3:
    st.subheader("Sleep Quality Distribution")
    if not sleep_dist.empty:
        colors = {"optimal": "#2ecc71", "adequate": "#3498db", "insufficient": "#e67e22", "poor": "#e74c3c"}
        fig_sleep = px.bar(sleep_dist, x="sleep_quality", y="nights",
                           color="sleep_quality", color_discrete_map=colors,
                           labels={"nights": "Number of Nights", "sleep_quality": "Sleep Quality"},
                           template="plotly_white")
        fig_sleep.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_sleep, use_container_width=True)
        st.dataframe(sleep_dist, use_container_width=True, hide_index=True)

    st.subheader("Activity Level Distribution")
    if not activity_dist.empty:
        act_colors = {"high": "#2ecc71", "moderate": "#3498db", "light": "#e67e22", "sedentary": "#e74c3c"}
        fig_act = px.bar(activity_dist, x="activity_level", y="days",
                         color="activity_level", color_discrete_map=act_colors,
                         labels={"days": "Number of Days", "activity_level": "Activity Level"},
                         template="plotly_white")
        fig_act.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_act, use_container_width=True)
        st.dataframe(activity_dist, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Member Retention by Engagement Tier")
    if not retention.empty:
        fig_ret = px.line(retention, x="tenure_weeks", y="retention_rate",
                          color="engagement_tier",
                          labels={"tenure_weeks": "Tenure (Weeks)",
                                  "retention_rate": "Retention %",
                                  "engagement_tier": "Engagement Tier"},
                          template="plotly_white")
        fig_ret.update_layout(height=450)
        st.plotly_chart(fig_ret, use_container_width=True)

        st.info("Higher engagement tiers correlate with stronger retention. "
                "This validates investment in features that drive daily active usage.")

with tab5:
    st.subheader("A/B Experiment Results")
    if not experiments.empty:
        for _, exp in experiments.iterrows():
            with st.expander(f"{'✅' if exp['significant'] else '⚠️'} {exp['experiment_name']}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Control Rate", f"{exp['control_rate']:.1%}")
                c2.metric("Treatment Rate", f"{exp['treatment_rate']:.1%}")
                c3.metric("Relative Lift", f"{exp['relative_lift_pct']:+.1f}%")
                c4.metric("p-value", f"{exp['p_value']:.4f}",
                           "Significant" if exp['significant'] else "Not Significant")

                fig_exp = go.Figure()
                fig_exp.add_trace(go.Bar(x=["Control", "Treatment"],
                                        y=[exp["control_rate"], exp["treatment_rate"]],
                                        marker_color=["#95a5a6", "#2ecc71" if exp["significant"] else "#e67e22"]))
                fig_exp.update_layout(height=250, template="plotly_white",
                                      yaxis_title=exp["metric"], yaxis_tickformat=".0%")
                st.plotly_chart(fig_exp, use_container_width=True)
    else:
        st.info("No experiments loaded. Run data/generate_enrichment.py to create experiment data.")

st.divider()
st.caption("Data: Fitbit Fitness Tracker (Kaggle, CC0) + Lifesnaps + synthetic enrichment | "
           "Stack: PostgreSQL, dbt, Python, Streamlit, Plotly | "
           "Built by Nicholas Hidalgo")
