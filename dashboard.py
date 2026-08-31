import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_data import (
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


def display_number(value):
    if pd.isna(value):
        return "—"

    return f"{int(value):,}"


st.title("AO3 Stats Dashboard")

st.caption(
    "Historical statistics for tracked "
    "Archive of Our Own works."
)


overview = get_overview_data()

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


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

st.subheader("Overview")


column1, column2, column3 = st.columns(3)

with column1:
    st.metric(
        label="Works tracked",
        value=f"{work_count:,}",
    )

with column2:
    st.metric(
        label="Total hits",
        value=f"{total_hits:,}",
    )

with column3:
    st.metric(
        label="Total kudos",
        value=f"{total_kudos:,}",
    )


column4, column5, column6 = st.columns(3)

with column4:
    st.metric(
        label="Comments",
        value=f"{total_comments:,}",
    )

with column5:
    st.metric(
        label="Public bookmarks",
        value=f"{total_bookmarks:,}",
    )

with column6:
    st.metric(
        label="Historical snapshots",
        value=f"{snapshot_count:,}",
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


st.subheader("Hits by work")


chart_data = overview[
    [
        "title",
        "hits",
    ]
].copy()


chart_data["hits"] = (
    chart_data["hits"]
    .fillna(0)
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


st.plotly_chart(
    figure,
    use_container_width=True,
)


# --------------------------------------------------
# WORK DETAIL
# --------------------------------------------------

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
    format_func=lambda work_id: title_by_id[work_id],
)


selected_row = overview[
    overview["work_id"] == selected_work_id
].iloc[0]


st.subheader(selected_row["title"])


public1, public2, public3, public4 = st.columns(4)

with public1:
    st.metric(
        "Hits",
        display_number(selected_row["hits"]),
    )

with public2:
    st.metric(
        "Kudos",
        display_number(selected_row["kudos"]),
    )

with public3:
    st.metric(
        "Comments",
        display_number(selected_row["comments"]),
    )

with public4:
    st.metric(
        "Public bookmarks",
        display_number(
            selected_row["public_bookmarks"]
        ),
    )


public5, public6, public7 = st.columns(3)

with public5:
    st.metric(
        "Words",
        display_number(selected_row["word_count"]),
    )

with public6:
    chapters_published = display_number(
        selected_row["chapters_published"]
    )

    chapters_total = display_number(
        selected_row["chapters_total"]
    )

    st.metric(
        "Chapters",
        f"{chapters_published}/{chapters_total}",
    )

with public7:
    public_timestamp = selected_row["collected_at"]

    st.metric(
        "Latest public snapshot",
        str(public_timestamp),
    )


st.subheader("Logged-in statistics")


private_stats = get_latest_private_stats(
    selected_work_id
)


if private_stats is None:
    st.info(
        "No manual or imported logged-in "
        "statistics are available for this work."
    )

else:
    private1, private2, private3 = st.columns(3)

    with private1:
        st.metric(
            "Subscriptions",
            display_number(
                private_stats["subscriptions"]
            ),
        )

    with private2:
        st.metric(
            "Total bookmarks",
            display_number(
                private_stats["total_bookmarks"]
            ),
        )

    with private3:
        st.metric(
            "Comment threads",
            display_number(
                private_stats["comment_threads"]
            ),
        )

    st.caption(
        "Latest logged-in observation: "
        f"{private_stats['collected_at']} "
        f"({private_stats['source']})"
    )


st.divider()


st.subheader("Historical growth")


history = get_work_history(
    selected_work_id
)


metric_fields = {
    "Hits": "hits",
    "Kudos": "kudos",
    "Comments": "comments",
    "Public bookmarks": "public_bookmarks",
    "Subscriptions": "subscriptions",
    "Total bookmarks": "total_bookmarks",
    "Comment threads": "comment_threads",
    "Word count": "word_count",
}


private_fields = {
    "subscriptions",
    "total_bookmarks",
    "comment_threads",
}


selected_metrics = st.multiselect(
    "Metrics",
    options=list(metric_fields.keys()),
    default=[
        "Hits",
        "Kudos",
    ],
)


if not selected_metrics:
    st.info(
        "Select at least one metric to display."
    )

elif history.empty:
    st.info(
        "No historical snapshots are available."
    )

else:
    chart_frames = []

    for metric_label in selected_metrics:
        field = metric_fields[metric_label]

        metric_history = history.copy()

        if field in private_fields:
            metric_history = metric_history[
                metric_history["source"]
                != "ao3_public"
            ]

        metric_history = metric_history[
            [
                "collected_at",
                "source",
                field,
            ]
        ].copy()

        metric_history = metric_history.rename(
            columns={
                field: "value",
            }
        )

        metric_history["Metric"] = metric_label

        chart_frames.append(metric_history)


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
        hover_data=[
            "source",
        ],
        labels={
            "collected_at": "Date",
            "value": "Value",
            "source": "Source",
        },
    )


    historical_figure.update_traces(
        line_shape="hv"
    )


    historical_figure.update_layout(
        xaxis_title="Date",
        yaxis_title=None,
        hovermode="x unified",
    )


    st.plotly_chart(
        historical_figure,
        use_container_width=True,
    )


    st.caption(
        "Historical values use a stepped line "
        "because the database records observations "
        "at specific points in time rather than "
        "continuous changes between observations."
    )