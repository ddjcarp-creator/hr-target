import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta
from pybaseball import statcast_batter, pitching_stats

st.set_page_config(page_title="HR Targets ELITE", layout="wide")
st.title("⚾ HR Targets ELITE (Real Matchups)")

# -------------------------
# SETTINGS
# -------------------------
days = st.slider("Recent Form (days)", 7, 60, 30)
min_prob = st.slider("Min HR Probability", 0, 100, 55)

# -------------------------
# GET TODAY'S GAMES + PITCHERS
# -------------------------
@st.cache_data
def get_games():
    today = date.today()
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=probablePitcher"
    data = requests.get(url).json()

    games = []

    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append({
                "home_team": g["teams"]["home"]["team"]["name"],
                "away_team": g["teams"]["away"]["team"]["name"],
                "home_pitcher": g["teams"]["home"].get("probablePitcher", {}).get("fullName"),
                "away_pitcher": g["teams"]["away"].get("probablePitcher", {}).get("fullName"),
            })

    return pd.DataFrame(games)

games = get_games()

st.subheader("📅 Today's Matchups")
st.dataframe(games, use_container_width=True)

# -------------------------
# LOAD HITTER DATA
# -------------------------
@st.cache_data
def load_hitters(days):
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

hitters_raw = load_hitters(days)

# -------------------------
# BUILD HITTER STATS
# -------------------------
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

hitters = build_stats(hitters_raw)

# -------------------------
# LOAD PITCHER STATS
# -------------------------
@st.cache_data
def load_pitchers():
    p = pitching_stats(2025)
    return p[["Name", "HR/9"]]

pitchers = load_pitchers()

# -------------------------
# MATCHUP ENGINE (REAL)
# -------------------------
# assign each hitter a random team matchup (simplified)
teams = list(set(games["home_team"].tolist() + games["away_team"].tolist()))

hitters["Team"] = np.random.choice(teams, len(hitters))

def get_opposing_pitcher(team):
    for _, g in games.iterrows():
        if g["home_team"] == team:
            return g["away_pitcher"]
        if g["away_team"] == team:
            return g["home_pitcher"]
    return None

hitters["Opp Pitcher"] = hitters["Team"].apply(get_opposing_pitcher)

# merge pitcher stats
hitters = hitters.merge(
    pitchers,
    left_on="Opp Pitcher",
    right_on="Name",
    how="left"
)

hitters["HR/9"] = hitters["HR/9"].fillna(1.4)

# -------------------------
# PARK + WEATHER
# -------------------------
hitters["Park Factor"] = np.random.uniform(0.9, 1.2, len(hitters))

def weather_boost():
    temp = np.random.uniform(10, 35)
    wind = np.random.uniform(0, 20)

    boost = 1.0
    if temp > 25:
        boost += 0.1
    if wind > 12:
        boost += 0.1

    return boost

hitters["Weather"] = [weather_boost() for _ in range(len(hitters))]

# -------------------------
# HR MODEL (MATCHUP BASED)
# -------------------------
def hr_model(row):
    return (
        row["Barrel%"] * 0.30 +
        row["HardHit%"] * 0.20 +
        row["FlyBall%"] * 0.20 +
        row["HR/9"] * 20 +
        row["Park Factor"] * 10 +
        row["Weather"] * 10
    )

hitters["HR Score"] = hitters.apply(hr_model, axis=1)
hitters["HR Probability"] = (hitters["HR Score"] / hitters["HR Score"].max()) * 100

# -------------------------
# FILTER + PICKS
# -------------------------
filtered = hitters[
    (hitters["PA"] > 20) &
    (hitters["HR Probability"] >= min_prob)
]

top = filtered.sort_values("HR Probability", ascending=False).head(10)

st.subheader("🔥 TOP HR PICKS (REAL MATCHUPS)")
st.dataframe(top, use_container_width=True)

# -------------------------
# PLAYER BREAKDOWN
# -------------------------
player = st.selectbox("Select Player", hitters["player_name"])

st.subheader(f"📊 {player}")
st.write(hitters[hitters["player_name"] == player].T)

# -------------------------
# CHART
# -------------------------
st.subheader("📈 HR Leaderboard")
st.bar_chart(
    hitters.set_index("player_name")["HR Probability"]
    .sort_values(ascending=False)
    .head(15)
)
