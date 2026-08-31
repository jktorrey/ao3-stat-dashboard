import pandas as pd
import plotly.express as px
import streamlit as st
from tzlocal import get_localzone

from dashboard_data import (
    get_24_hour_changes,
    get_latest_private_stats,
    get_overview_data,
    get_snapshot_count,
    get_work_count,
    get_work_history,
)


st.set_page_config(
    page_title="AO3 Stats Dashboard",
    page_icon="📚",
    layout="wide",
)


LOCAL_TIMEZONE = get_localzone()


SOURCE_LABELS = {
    "ao3_public": "Live AO3",
    "manual": "Manual entry",
    "csv_import": "Historical CSV",
}


def display_number(value):
    if value is None or pd.isna(value):
        return "—"

    return f"{int(value):,}"


def display_change(value):
    if value is None or pd.isna(value):
        return "—"

    value = int(value)

    if value > 0:
        return f"+{value:,}"

    return f"{value:,}"


def metric_delta(value):
    if value is None or pd.isna(value):
        return None

    value = int(value)

    if value > 0:
        return f"+{value:,} vs prior baseline"

    return f"{value:,} vs prior baseline"


def display_source(source):
    return SOURCE_LABELS.get(
        source,
        source,
    )


def display_timestamp(value):
    if value is None or pd.isna(value):
        return "—"

    timestamp = pd.to_datetime(
        value,
        format="mixed",
        utc=True,
    )

    timestamp = timestamp.tz_convert(
        LOCAL_TIMEZONE
    )

    return timestamp.strftime(
        "%b %d, %Y %I:%M %p %Z"
    )


def render_overview(overview, changes):
    work_count = get_work_count()
    snapshot_count = get_snapshot_count()

    total_hits = int(
        overview["hits"].fillna(0).sum()
    )

    total_kudos = int(
        overview["kudos"].fillna(0).sum()
    )

    total_comments = int(
        overview["comments"].fillna(0).sum()
    )

    total_bookmarks = int(
        overview["public_bookmarks"]
        .fillna(0)
        .sum()
    )

    st.subheader("Overview")

    column1, column2, column3 = st.columns(3)

    with column1:
        st.metric(
            "Works tracked",
            f"{work_count:,}",
        )

    with column2:
        st.metric(
            "Total hits",
            f"{total_hits:,}",
        )

    with column3:
        st.metric(
            "Total kudos",
            f"{total_kudos:,}",
        )

    column4, column5, column6 = st.columns(3)

    with column4:
        st.metric(
            "Comments",
            f"{total_comments:,}",
        )

    with column5:
        st.metric(
            "Public bookmarks",
            f"{total_bookmarks:,}",
        )

    with column6:
        st.metric(
            "Historical snapshots",
            f"{snapshot_count:,}",
        )

    st.divider()

    st.subheader("Current stats by work")

    table_data = overview[
        [
            "title",
            "hits",
            "kudos",
            "comments",
            "public_bookmarks",
            "word_count",
            "chapters_published",
            "chapters_total",
        ]
    ].copy()

    table_data["chapters"] = (
        table_data["chapters_published"]
        .fillna(0)
        .astype(int)
        .astype(str)
        + "/"
        + table_data["chapters_total"]
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    table_data = table_data.drop(
        columns=[
            "chapters_published",
            "chapters_total",
        ]
    )

    table_data = table_data.rename(
        columns={
            "title": "Work",
            "hits": "Hits",
            "kudos": "Kudos",
            "comments": "Comments",
            "public_bookmarks": "Bookmarks",
            "word_count": "Words",
            "chapters": "Chapters",
        }
    )

    st.dataframe(
        table_data,
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    render_24_hour_changes(changes)

    st.divider()

    st.subheader("Hits by work")

    chart_data = overview[
        [
            "title",
            "hits",
        ]
    ].copy()

    chart_data["hits"] = (
        chart_data["hits"].fillna(0)
    )

    chart_data = chart_data.sort_values(
        by="hits",
        ascending=True,
    )

    figure = px.bar(
        chart_data,
        x="hits",
        y="title",
        orientation="h",
        labels={
            "hits": "Hits",
            "title": "Work",
        },
    )

    figure.update_layout(
        yaxis_title=None,
        xaxis_title="Hits",
    )

    figure.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Hits: %{x:,}"
            "<extra></extra>"
        )
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )


def render_24_hour_changes(changes):
    st.subheader("24-hour change")

    st.caption(
        "Each work is compared with the newest "
        "available snapshot at or before 24 hours "
        "prior to its latest current observation."
    )

    change_table = changes[
        [
            "title",
            "hits_change_24h",
            "kudos_change_24h",
            "comments_change_24h",
            "bookmarks_change_24h",
            "baseline_collected_at",
            "baseline_hours",
        ]
    ].copy()

    change_table["Hits Δ"] = (
        change_table["hits_change_24h"]
        .apply(display_change)
    )

    change_table["Kudos Δ"] = (
        change_table["kudos_change_24h"]
        .apply(display_change)
    )

    change_table["Comments Δ"] = (
        change_table["comments_change_24h"]
        .apply(display_change)
    )

    change_table["Bookmarks Δ"] = (
        change_table["bookmarks_change_24h"]
        .apply(display_change)
    )

    change_table["Baseline"] = (
        change_table["baseline_collected_at"]
        .apply(display_timestamp)
    )

    change_table["Window"] = (
        change_table["baseline_hours"]
        .apply(
            lambda value: (
                "—"
                if value is None or pd.isna(value)
                else f"{value:.1f} hrs"
            )
        )
    )

    change_table = change_table[
        [
            "title",
            "Hits Δ",
            "Kudos Δ",
            "Comments Δ",
            "Bookmarks Δ",
            "Baseline",
            "Window",
        ]
    ]

    change_table = change_table.rename(
        columns={
            "title": "Work",
        }
    )

    st.dataframe(
        change_table,
        hide_index=True,
        use_container_width=True,
    )

    available = (
        changes["baseline_collected_at"]
        .notna()
        .sum()
    )

    total = len(changes)

    if available < total:
        st.caption(
            f"24-hour baselines are currently "
            f"available for {available} of "
            f"{total} works."
        )


def render_work_detail(
    overview,
    changes,
):
    st.divider()

    st.header("Work Detail")

    work_ids = overview["work_id"].tolist()

    title_by_id = dict(
        zip(
            overview["work_id"],
            overview["title"],
        )
    )

    selected_work_id = st.selectbox(
        "Work",
        options=work_ids,
        format_func=lambda work_id: (
            title_by_id[work_id]
        ),
    )

    selected_row = overview[
        overview["work_id"]
        == selected_work_id
    ].iloc[0]

    selected_changes = changes[
        changes["work_id"]
        == selected_work_id
    ]

    if selected_changes.empty:
        change_row = None
    else:
        change_row = selected_changes.iloc[0]

    st.subheader(
        selected_row["title"]
    )

    public1, public2, public3, public4 = (
        st.columns(4)
    )

    with public1:
        st.metric(
            "Hits",
            display_number(
                selected_row["hits"]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "hits_change_24h"
                    ]
                )
            ),
        )

    with public2:
        st.metric(
            "Kudos",
            display_number(
                selected_row["kudos"]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "kudos_change_24h"
                    ]
                )
            ),
        )

    with public3:
        st.metric(
            "Comments",
            display_number(
                selected_row["comments"]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "comments_change_24h"
                    ]
                )
            ),
        )

    with public4:
        st.metric(
            "Public bookmarks",
            display_number(
                selected_row[
                    "public_bookmarks"
                ]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "bookmarks_change_24h"
                    ]
                )
            ),
        )

    public5, public6 = st.columns(2)

    with public5:
        st.metric(
            "Words",
            display_number(
                selected_row["word_count"]
            ),
        )

    with public6:
        chapters_published = display_number(
            selected_row[
                "chapters_published"
            ]
        )

        chapters_total = display_number(
            selected_row[
                "chapters_total"
            ]
        )

        st.metric(
            "Chapters",
            (
                f"{chapters_published}/"
                f"{chapters_total}"
            ),
        )

    st.caption(
        "Current public observation: "
        f"{display_timestamp(selected_row['collected_at'])} "
        f"• {display_source(selected_row['source'])}"
    )

    if (
        change_row is not None
        and not pd.isna(
            change_row[
                "baseline_collected_at"
            ]
        )
    ):
        st.caption(
            "Change baseline: "
            f"{display_timestamp(change_row['baseline_collected_at'])} "
            f"({change_row['baseline_hours']:.1f} hours earlier)"
        )

    render_private_stats(
        selected_work_id
    )

    render_history(
        selected_work_id
    )


def render_private_stats(work_id):
    st.subheader(
        "Logged-in statistics"
    )

    private_stats = (
        get_latest_private_stats(
            work_id
        )
    )

    if private_stats is None:
        st.info(
            "No manual or imported logged-in "
            "statistics are available for this work."
        )
        return

    private1, private2, private3 = (
        st.columns(3)
    )

    with private1:
        st.metric(
            "Subscriptions",
            display_number(
                private_stats[
                    "subscriptions"
                ]
            ),
        )

    with private2:
        st.metric(
            "Total bookmarks",
            display_number(
                private_stats[
                    "total_bookmarks"
                ]
            ),
        )

    with private3:
        st.metric(
            "Comment threads",
            display_number(
                private_stats[
                    "comment_threads"
                ]
            ),
        )

    st.caption(
        "Latest logged-in observation: "
        f"{display_timestamp(private_stats['collected_at'])} "
        f"• {display_source(private_stats['source'])}"
    )


def render_history(work_id):
    st.divider()

    st.subheader(
        "Historical growth"
    )

    history = get_work_history(
        work_id
    )

    if history.empty:
        st.info(
            "No historical snapshots "
            "are available."
        )
        return

    history["collected_at"] = (
        history["collected_at"]
        .dt.tz_convert(
            LOCAL_TIMEZONE
        )
    )

    metric_fields = {
        "Hits": "hits",
        "Kudos": "kudos",
        "Comments": "comments",
        "Public bookmarks": (
            "public_bookmarks"
        ),
        "Subscriptions": "subscriptions",
        "Total bookmarks": (
            "total_bookmarks"
        ),
        "Comment threads": (
            "comment_threads"
        ),
        "Word count": "word_count",
    }

    private_fields = {
        "subscriptions",
        "total_bookmarks",
        "comment_threads",
    }

    selected_metrics = st.multiselect(
        "Metrics",
        options=list(
            metric_fields.keys()
        ),
        default=[
            "Hits",
            "Kudos",
        ],
    )

    if not selected_metrics:
        st.info(
            "Select at least one metric "
            "to display."
        )
        return

    chart_frames = []

    for metric_label in selected_metrics:
        field = metric_fields[
            metric_label
        ]

        metric_history = (
            history.copy()
        )

        if field in private_fields:
            metric_history = (
                metric_history[
                    metric_history[
                        "source"
                    ]
                    != "ao3_public"
                ]
            )

        metric_history = (
            metric_history[
                [
                    "collected_at",
                    "source",
                    field,
                ]
            ].copy()
        )

        metric_history = (
            metric_history.rename(
                columns={
                    field: "value",
                }
            )
        )

        metric_history[
            "Metric"
        ] = metric_label

        metric_history[
            "Source"
        ] = (
            metric_history["source"]
            .map(display_source)
        )

        chart_frames.append(
            metric_history
        )

    historical_chart_data = pd.concat(
        chart_frames,
        ignore_index=True,
    )

    historical_figure = px.line(
        historical_chart_data,
        x="collected_at",
        y="value",
        color="Metric",
        markers=True,
        hover_data={
            "Source": True,
            "source": False,
        },
        labels={
            "collected_at": "Date",
            "value": "Value",
        },
    )

    historical_figure.update_traces(
        line_shape="hv"
    )

    historical_figure.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        hovermode="x unified",
    )

    historical_figure.update_xaxes(
        tickformat="%b %d",
        hoverformat=(
            "%b %d, %Y %I:%M %p"
        ),
    )

    st.plotly_chart(
        historical_figure,
        use_container_width=True,
    )

    st.caption(
        "Historical values use a stepped line "
        "because snapshots record observations "
        "at specific points in time rather than "
        "continuous changes between observations."
    )


def main():
    st.title(
        "AO3 Stats Dashboard"
    )

    st.caption(
        "Historical statistics for tracked "
        "Archive of Our Own works."
    )

    st.caption(
        f"Times shown in "
        f"{LOCAL_TIMEZONE}."
    )

    overview = get_overview_data()
    changes = get_24_hour_changes()

    render_overview(
        overview,
        changes,
    )

    render_work_detail(
        overview,
        changes,
    )


if __name__ == "__main__":
    main()