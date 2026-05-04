import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta
from pybaseball import statcast_batter

st.set_page_config(page_title="HR Targets Clone", layout="wide")
st.title("⚾ MLB HR Targets Clone")

# -----------------------------
# SETTINGS
# -----------------------------
days = st.slider("Recent Form (Days)", 7, 60, 30)
min_prob = st.slider("Min HR Probability", 0, 100, 55)
min_pa = st.slider("Minimum Plate Appearances", 10, 100, 20)

# -----------------------------
# MLB SCHEDULE (TODAY)
# -----------------------------
@st.cache_data
def get_schedule():
    today = date.today()
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    data = requests.get(url).json()

    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append({
                "Away": g["teams"]["away"]["team"]["name"],
                "Home": g["teams"]["home"]["team"]["name"]
            })
    return pd.DataFrame(games)

schedule = get_schedule()

st.subheader("📅 Today's Games")
st.dataframe(schedule, use_container_width=True)

# -----------------------------
# LOAD STATCAST DATA
# -----------------------------
@st.cache_data
def load_data(days):
    end = date.today()
    start = end - timedelta(days=days)

    df = statcast_batter(start_dt=start, end_dt=end)

    df = df[[
        "player_name",
        "launch_speed",
        "launch_angle",
        "events"
    ]].copy()

    df["HR"] = df["events"] == "home_run"
    return df

raw = load_data(days)

# -----------------------------
# HITTER METRICS
# -----------------------------
def build_stats(df):
    g = df.groupby("player_name")

    stats = pd.DataFrame()
    stats["PA"] = g.size()

    stats["Barrel%"] = g.apply(
        lambda x: np.mean(
            (x["launch_speed"] > 98) & (x["launch_angle"].between(26, 30))
        )
    ) * 100

    stats["HardHit%"] = g.apply(
        lambda x: np.mean(x["launch_speed"] >= 95)
    ) * 100

    stats["FlyBall%"] = g.apply(
        lambda x: np.mean(x["launch_angle"] > 25)
    ) * 100

    stats = stats.reset_index()
    return stats

stats = build_stats(raw)

# -----------------------------
# SIMULATED MATCHUPS
# -----------------------------
np.random.seed(42)

stats["Pitcher HR/9"] = np.random.uniform(1.0, 2.2, len(stats))

# Park factors
park_values = [1.25, 1.15, 1.05, 0.95, 0.85]
stats["Park Factor"] = np.random.choice(park_values, len(stats))

# Weather boost
def weather():
    temp = np.random.uniform(10, 35)
    wind = np.random.uniform(0, 20)

    boost = 1.0
    if temp > 25:
        boost += 0.1
    if wind > 12:
        boost += 0.1

    return boost

stats["Weather Boost"] = [weather() for _ in range(len(stats))]

# -----------------------------
# HR MODEL
# -----------------------------
def model(row):
    return (
        row["Barrel%"] * 0.30 +
        row["HardHit%"] * 0.20 +
        row["FlyBall%"] * 0.20 +
        row["Pitcher HR/9"] * 18 +
        row["Park Factor"] * 12 +
        row["Weather Boost"] * 10
    )

stats["HR Score"] = stats.apply(model, axis=1)
stats["HR Probability"] = (stats["HR Score"] / stats["HR Score"].max()) * 100

# -----------------------------
# FILTERS
# -----------------------------
filtered = stats[
    (stats["PA"] >= min_pa) &
    (stats["HR Probability"] >= min_prob)
]

# -----------------------------
# TOP PICKS
# -----------------------------
st.subheader("🔥 Top HR Picks Today")

top = filtered.sort_values("HR Probability", ascending=False).head(10)
st.dataframe(top, use_container_width=True)

# -----------------------------
# PLAYER VIEW
# -----------------------------
player = st.selectbox("Select Player", stats["player_name"])

st.subheader(f"📊 {player} Breakdown")
st.write(stats[stats["player_name"] == player].T)

# -----------------------------
# CHART
# -----------------------------
st.subheader("📈 HR Leaderboard")
st.bar_chart(
    stats.set_index("player_name")["HR Probability"]
    .sort_values(ascending=False)
    .head(15)
)
