"""Session-ordered funnel analysis of synthetic events, not retention analysis.

Import safely, then call load_data(), analyze(), or plot_dashboard(). Only
main() exports files. Events are not interchangeable with sessions or people.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_DIR = Path(__file__).resolve().parents[1]
FUNNEL_STAGES = ("page_view", "add_to_cart", "checkout", "purchase")
REQUIRED_COLUMNS = ("user_id", "event_type", "event_time", "device", "region", "session_id")
SESSION_METADATA = (
    "session_id", "user_id", "device", "region", "event_count",
    "observed_start", "observed_end", "duration_minutes",
)


def safe_ratio(numerator, denominator):
    """Undefined ratios are NaN, never infinity or an invented zero."""
    return numerator / denominator if denominator else np.nan


def prepare_data(df):
    """Validate session identity, remove exact duplicate events, and sort by time."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    data = df.copy()
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Required event fields cannot be missing.")
    data["event_time"] = pd.to_datetime(data["event_time"], errors="raise")
    if data["event_time"].isna().any():
        raise ValueError("event_time cannot be NaT.")
    # A globally unique session_id must belong to one user and one device/region.
    for column in ("user_id", "device", "region"):
        if data.groupby("session_id", sort=True)[column].nunique().gt(1).any():
            raise ValueError(f"Each session_id must have exactly one {column}.")
    data = data.drop_duplicates(subset=list(REQUIRED_COLUMNS))
    return data.sort_values(
        ["session_id", "event_time", "event_type"], kind="mergesort"
    ).reset_index(drop=True)


def load_data(path=None):
    """Read and validate events without removing rows until analyze() deduplicates."""
    path = Path(path) if path is not None else PROJECT_DIR / "data" / "user_events.csv"
    data = pd.read_csv(path)
    # Validate now, but preserve the original row count for duplicate diagnostics.
    prepare_data(data)
    data["event_time"] = pd.to_datetime(data["event_time"], errors="raise")
    return data


def match_ordered_funnel(df, stages=FUNNEL_STAGES):
    """One row per session, matching the earliest complete prefix of stages.

    Each matched timestamp must be strictly later than the preceding stage.
    Equal timestamps do not prove order and cannot advance the funnel. Repeated
    views or cart events never count the same session more than once per stage;
    stages in different sessions are never joined.
    """
    stages = tuple(stages)
    if not stages or len(set(stages)) != len(stages):
        raise ValueError("stages must be a nonempty sequence of distinct event names.")
    if set(stages).intersection(SESSION_METADATA):
        raise ValueError("Stage names cannot collide with session metadata columns.")
    data = prepare_data(df)
    records = []
    for session_id, events in data.groupby("session_id", sort=True):
        first = events.iloc[0]
        start, end = events["event_time"].min(), events["event_time"].max()
        row = {
            "session_id": session_id,
            "user_id": first["user_id"],
            "device": first["device"],
            "region": first["region"],
            "event_count": len(events),
            "observed_start": start,
            "observed_end": end,
            "duration_minutes": (end - start).total_seconds() / 60,
            **{stage: False for stage in stages},
        }
        previous_time = None
        for stage in stages:
            eligible = events["event_type"].eq(stage)
            if previous_time is not None:
                eligible &= events["event_time"].gt(previous_time)
            matched_times = events.loc[eligible, "event_time"]
            if matched_times.empty:
                break
            previous_time = matched_times.iloc[0]
            row[stage] = True
        records.append(row)
    sessions = pd.DataFrame(records, columns=[*SESSION_METADATA, *stages])
    for stage in stages:
        sessions[stage] = sessions[stage].astype(bool)
    sessions["event_count"] = sessions["event_count"].astype("int64")
    sessions["duration_minutes"] = sessions["duration_minutes"].astype(float)
    return sessions


def summarize_funnel(sessions, stages=FUNNEL_STAGES):
    """Count matched sessions, with explicit step and entry-session denominators."""
    stages = tuple(stages)
    entry_count = int(sessions[stages[0]].sum())
    previous_count = len(sessions)
    records = []
    for stage in stages:
        count = int(sessions[stage].sum())
        records.append({
            "stage": stage,
            "sessions": count,
            "eligible_sessions": previous_count,
            "step_conversion_pct": safe_ratio(count, previous_count) * 100,
            "entry_conversion_pct": safe_ratio(count, entry_count) * 100,
        })
        previous_count = count
    return pd.DataFrame(records)


def analyze(df):
    """Return session funnels, DAU, and observed durations, without any exports."""
    data = prepare_data(df)
    sessions = match_ordered_funnel(data)
    device_rows = []
    for device, group in sessions.groupby("device", sort=True):
        counts = {stage: int(group[stage].sum()) for stage in FUNNEL_STAGES}
        device_rows.append({
            "device": device,
            "sessions": len(group),
            **{f"{stage}_sessions": count for stage, count in counts.items()},
            "purchase_conversion_pct": safe_ratio(counts["purchase"], counts["page_view"]) * 100,
        })
    device_summary = pd.DataFrame(device_rows, columns=[
        "device", "sessions", *(f"{stage}_sessions" for stage in FUNNEL_STAGES),
        "purchase_conversion_pct",
    ])
    dates = data.assign(date=data["event_time"].dt.strftime("%Y-%m-%d"))
    daily_active = dates.groupby("date", sort=True).agg(
        active_users=("user_id", "nunique")
    ).reset_index()
    events = data.groupby("event_type", sort=True).size().rename("events").reset_index()
    overview = pd.DataFrame([{
        "input_event_rows": len(df),
        "deduplicated_events": len(data),
        "exact_duplicates_removed": len(df) - len(data),
        "unique_users": data["user_id"].nunique(),
        "sessions": len(sessions),
        "entry_sessions": int(sessions["page_view"].sum()),
        "completed_purchase_sessions": int(sessions["purchase"].sum()),
    }])
    return {
        "overview": overview,
        "funnel_analysis": summarize_funnel(sessions),
        "device_conversion": device_summary,
        "daily_active_users": daily_active,
        "session_activity": sessions[list(SESSION_METADATA)].copy(),
        "session_matches": sessions,
        "event_counts": events,
    }


def plot_dashboard(results):
    """Build a headless dashboard with session-based, not event-based, conversion."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    funnel = results["funnel_analysis"]
    axes[0, 0].bar(funnel["stage"], funnel["sessions"], color="steelblue")
    axes[0, 0].set(title="Ordered funnel (distinct sessions)", ylabel="Sessions")
    axes[0, 0].tick_params(axis="x", rotation=20)
    for position, count in enumerate(funnel["sessions"]):
        axes[0, 0].text(position, count, str(count), ha="center", va="bottom")

    device = results["device_conversion"]
    if not device.empty:
        axes[0, 1].bar(device["device"], device["purchase_conversion_pct"], color="coral")
        for position, value in enumerate(device["purchase_conversion_pct"]):
            if pd.isna(value):
                axes[0, 1].text(position, 1, "n/a", ha="center")
        axes[0, 1].set_ylim(0, 105)
    else:
        axes[0, 1].text(0.5, 0.5, "No sessions", ha="center", transform=axes[0, 1].transAxes)
    axes[0, 1].set(title="Device conversion (purchase / entry sessions)", ylabel="Conversion (%)")

    daily = results["daily_active_users"]
    if not daily.empty:
        axes[1, 0].plot(daily["date"], daily["active_users"], marker="o", color="seagreen")
        axes[1, 0].tick_params(axis="x", rotation=45)
    else:
        axes[1, 0].text(0.5, 0.5, "No dated events", ha="center", transform=axes[1, 0].transAxes)
    axes[1, 0].set(title="Daily active users (any observed event)", xlabel="Date", ylabel="Distinct users")

    activity = results["session_activity"]
    if not activity.empty:
        axes[1, 1].hist(activity["duration_minutes"], bins=min(10, len(activity)), color="mediumpurple", edgecolor="white")
    else:
        axes[1, 1].text(0.5, 0.5, "No observed durations", ha="center", transform=axes[1, 1].transAxes)
    axes[1, 1].set(title="Observed session span (last - first event)", xlabel="Minutes", ylabel="Sessions")
    fig.suptitle("User behavior | synthetic demonstration data", fontsize=15)
    fig.text(0.5, 0.01, "Small event sample: no retention, repeat-purchase, spending, or abandonment-timeout evidence.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    return fig


def main(data_path=None, output_dir=None):
    """Export corrected session tables and behavior_dashboard.png."""
    results = analyze(load_data(data_path))
    destination = Path(output_dir) if output_dir is not None else PROJECT_DIR / "output"
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        table.to_csv(destination / f"{name}.csv", index=False, float_format="%.6f", encoding="utf-8", lineterminator="\n")
    figure = plot_dashboard(results)
    figure.savefig(destination / "behavior_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    for name in ("overview", "funnel_analysis", "device_conversion", "daily_active_users"):
        print(f"\n=== {name} ===\n{results[name].to_string(index=False)}")
    print("\nAll funnel conversions use same-session ordered prefixes. Undefined ratios are blank/NaN.")
    print(f"Outputs saved to {destination}")
    return results


if __name__ == "__main__":
    main()
