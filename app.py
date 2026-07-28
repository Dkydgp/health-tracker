"""
app.py - Personal Daily Health & Nutrition Tracker
"""

import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

from sheets_client import append_log, get_history, has_entry_for_today
from nutrition_ai import estimate_full_day

load_dotenv()

st.set_page_config(page_title="🥗 My Daily Health Log", layout="wide")
st.title("🥗 My Daily Health Log")

# ── Session state for the estimate step ──────────────────────────
if "estimate" not in st.session_state:
    st.session_state.estimate = None
if "form_data" not in st.session_state:
    st.session_state.form_data = {}

tab_log, tab_history = st.tabs(["📝 Today's Log", "📊 History & Trends"])

# ══════════════════════════════════════════════════════════════════
# TAB 1: TODAY'S LOG
# ══════════════════════════════════════════════════════════════════
with tab_log:

    already_logged = False
    try:
        already_logged = has_entry_for_today()
    except Exception as e:
        st.warning(f"⚠️ Couldn't check today's status: {e}")

    if already_logged:
        st.info("✅ You've already logged today. Submitting again will add a duplicate row.")

    st.subheader("⚖️ Weight")
    weight = st.number_input("Today's weight (kg)", min_value=0.0, max_value=400.0, step=0.1, format="%.1f")

    st.subheader("🍽️ What did you eat?")
    col1, col2 = st.columns(2)
    with col1:
        breakfast = st.text_area("Breakfast", placeholder="e.g. 2 boiled eggs, 2 slices toast, black coffee")
        dinner = st.text_area("Dinner", placeholder="e.g. Grilled chicken breast, rice, salad")
    with col2:
        lunch = st.text_area("Lunch", placeholder="e.g. Dal, roti x2, sabzi")
        snacks = st.text_area("Snacks", placeholder="e.g. Apple, handful of almonds")

    st.subheader("🏋️ Exercise & Activity")
    col3, col4 = st.columns(2)
    with col3:
        exercise = st.text_area("Gym / exercise done today", placeholder="e.g. Chest + triceps, 45 min, bench press 4x8 @60kg")
    with col4:
        steps = st.number_input("Steps walked yesterday", min_value=0, max_value=100000, step=100)

    st.markdown("---")

    # Step 1: Estimate nutrition
    if st.button("🔍 Estimate Nutrition", type="primary", use_container_width=True):
        with st.spinner("Estimating calories, protein, carbs, fat..."):
            result = estimate_full_day(breakfast, lunch, dinner, snacks)
            st.session_state.estimate = result
            st.session_state.form_data = {
                "weight": weight,
                "breakfast": breakfast,
                "lunch": lunch,
                "dinner": dinner,
                "snacks": snacks,
                "exercise": exercise,
                "steps": steps,
            }

    # Step 2: Show estimate + allow save
    if st.session_state.estimate:
        totals = st.session_state.estimate["totals"]
        breakdown = st.session_state.estimate["breakdown"]

        st.subheader("📊 Estimated Nutrition")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Calories", f"{totals['calories']} kcal")
        m2.metric("Protein", f"{totals['protein_g']} g")
        m3.metric("Carbs", f"{totals['carbs_g']} g")
        m4.metric("Fat", f"{totals['fat_g']} g")

        with st.expander("🔎 Per-meal breakdown"):
            for meal, data in breakdown.items():
                if data["calories"] > 0:
                    st.markdown(f"**{meal.capitalize()}**: {data['calories']} kcal | "
                                f"P: {data['protein_g']}g | C: {data['carbs_g']}g | F: {data['fat_g']}g")
                    if data.get("notes"):
                        st.caption(f"💭 {data['notes']}")

        st.markdown("---")

        if st.button("💾 Save Today's Log", type="primary", use_container_width=True):
            fd = st.session_state.form_data
            entry = {
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Weight (kg)": fd["weight"],
                "Breakfast": fd["breakfast"],
                "Lunch": fd["lunch"],
                "Dinner": fd["dinner"],
                "Snacks": fd["snacks"],
                "Calories": totals["calories"],
                "Protein (g)": totals["protein_g"],
                "Carbs (g)": totals["carbs_g"],
                "Fat (g)": totals["fat_g"],
                "Exercise": fd["exercise"],
                "Steps (yesterday)": fd["steps"],
            }
            try:
                append_log(entry)
                st.success("✅ Saved to your Google Sheet!")
                st.session_state.estimate = None
                st.session_state.form_data = {}
            except Exception as e:
                st.error(f"❌ Failed to save: {e}")

# ══════════════════════════════════════════════════════════════════
# TAB 2: HISTORY & TRENDS
# ══════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📊 Your History")

    try:
        history = get_history(limit=60)
    except Exception as e:
        history = []
        st.error(f"❌ Couldn't load history: {e}")

    if not history:
        st.info("No logs yet — fill out today's log to get started!")
    else:
        df = pd.DataFrame(history)

        # Weight trend
        if "Weight (kg)" in df.columns:
            st.markdown("### ⚖️ Weight Over Time")
            weight_df = df[["Date", "Weight (kg)"]].dropna()
            weight_df["Weight (kg)"] = pd.to_numeric(weight_df["Weight (kg)"], errors="coerce")
            st.line_chart(weight_df.set_index("Date"))

        # Calories/macros trend
        st.markdown("### 🍽️ Calories & Macros Over Time")
        macro_cols = ["Calories", "Protein (g)", "Carbs (g)", "Fat (g)"]
        available_macro_cols = [c for c in macro_cols if c in df.columns]
        if available_macro_cols:
            macro_df = df[["Date"] + available_macro_cols].copy()
            for c in available_macro_cols:
                macro_df[c] = pd.to_numeric(macro_df[c], errors="coerce")
            st.line_chart(macro_df.set_index("Date")[["Calories"]])
            st.line_chart(macro_df.set_index("Date")[[c for c in available_macro_cols if c != "Calories"]])

        # Steps trend
        if "Steps (yesterday)" in df.columns:
            st.markdown("### 👣 Steps Over Time")
            steps_df = df[["Date", "Steps (yesterday)"]].dropna()
            steps_df["Steps (yesterday)"] = pd.to_numeric(steps_df["Steps (yesterday)"], errors="coerce")
            st.bar_chart(steps_df.set_index("Date"))

        # Raw table
        with st.expander("📋 View Raw Log Table"):
            st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)

        # Averages
        st.markdown("### 📈 Recent Averages (last 7 entries)")
        recent = df.tail(7)
        a1, a2, a3, a4 = st.columns(4)
        if "Calories" in recent.columns:
            a1.metric("Avg Calories", f"{pd.to_numeric(recent['Calories'], errors='coerce').mean():.0f}")
        if "Protein (g)" in recent.columns:
            a2.metric("Avg Protein", f"{pd.to_numeric(recent['Protein (g)'], errors='coerce').mean():.1f}g")
        if "Steps (yesterday)" in recent.columns:
            a3.metric("Avg Steps", f"{pd.to_numeric(recent['Steps (yesterday)'], errors='coerce').mean():.0f}")
        if "Weight (kg)" in recent.columns:
            a4.metric("Avg Weight", f"{pd.to_numeric(recent['Weight (kg)'], errors='coerce').mean():.1f}kg")
