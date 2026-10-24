import sys
from contextlib import contextmanager

import pandas as pd
import plotly.express as px
import streamlit as st
from tzlocal import get_localzone

from dashboard_data import (
    get_period_changes,
    get_latest_private_stats,
    get_overview_data,
    get_snapshot_count,
    get_snapshot_management_data,
    get_work_count,
    get_work_history,
    get_work_events,
    get_system_health,
)


class DashboardProgressStream:
    def __init__(
        self,
        placeholder,
        original_stream,
        logger,
        log_level="info",
        max_lines=18,
    ):
        self.placeholder = placeholder
        self.original_stream = (
            original_stream
        )
        self.logger = logger
        self.log_level = log_level
        self.max_lines = max_lines

        self.buffer = ""
        self.lines = []

    def _publish_line(
        self,
        line,
    ):
        line = line.rstrip()

        if not line:
            return

        self.lines.append(
            line
        )

        self.lines = self.lines[
            -self.max_lines:
        ]

        self.placeholder.code(
            "\n".join(
                self.lines
            ),
            language=None,
        )

        log_method = getattr(
            self.logger,
            self.log_level,
        )

        log_method(
            line
        )

    def write(self, text):
        if not text:
            return 0

        self.original_stream.write(
            text
        )

        self.original_stream.flush()

        self.buffer += text

        while "\n" in self.buffer:
            line, self.buffer = (
                self.buffer.split(
                    "\n",
                    1,
                )
            )

            self._publish_line(
                line
            )

        return len(text)

    def flush(self):
        self.original_stream.flush()

        if self.buffer:
            self._publish_line(
                self.buffer
            )

            self.buffer = ""

    def isatty(self):
        return self.original_stream.isatty()


@contextmanager
def capture_dashboard_progress(
    placeholder,
    logger,
):
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    stdout_stream = (
        DashboardProgressStream(
            placeholder,
            original_stdout,
            logger,
            log_level="info",
        )
    )

    stderr_stream = (
        DashboardProgressStream(
            placeholder,
            original_stderr,
            logger,
            log_level="error",
        )
    )

    sys.stdout = stdout_stream
    sys.stderr = stderr_stream

    try:
        yield

    finally:
        stdout_stream.flush()
        stderr_stream.flush()

        sys.stdout = original_stdout
        sys.stderr = original_stderr

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


def render_overview(
    overview,
    changes,
    window_label,
):
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

    available = (
        changes["baseline_collected_at"]
        .notna()
        .sum()
    )

    total_works = len(changes)

    full_coverage = (
        total_works > 0
        and available == total_works
    )

    if full_coverage:
        total_hits_change = int(
            changes["hits_change"].sum()
        )

        total_kudos_change = int(
            changes["kudos_change"].sum()
        )

        total_comments_change = int(
            changes["comments_change"].sum()
        )

        total_bookmarks_change = int(
            changes["bookmarks_change"].sum()
        )

    else:
        total_hits_change = None
        total_kudos_change = None
        total_comments_change = None
        total_bookmarks_change = None

    st.subheader("Overview")

    render_system_health()

    st.divider()


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

    st.subheader(
        f"Growth in the last {window_label}"
    )

    growth1, growth2, growth3, growth4 = (
        st.columns(4)
    )

    with growth1:
        st.metric(
            "Hits gained",
            display_change(
                total_hits_change
            ),
        )

    with growth2:
        st.metric(
            "Kudos gained",
            display_change(
                total_kudos_change
            ),
        )

    with growth3:
        st.metric(
            "Comments gained",
            display_change(
                total_comments_change
            ),
        )

    with growth4:
        st.metric(
            "Bookmarks gained",
            display_change(
                total_bookmarks_change
            ),
        )

    if not full_coverage:
        st.info(
            f"Portfolio totals are unavailable "
            f"for this window because only "
            f"{available} of {total_works} works "
            f"have a baseline at least "
            f"{window_label.lower()} old."
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

    render_period_changes(
        changes,
        window_label,
    )

    st.divider()

    st.subheader(
        f"Hits gained by work — {window_label}"
    )

    growth_chart_data = changes[
        [
            "title",
            "hits_change",
        ]
    ].copy()

    growth_chart_data = (
        growth_chart_data.dropna(
            subset=["hits_change"]
        )
    )

    growth_chart_data = (
        growth_chart_data.sort_values(
            by="hits_change",
            ascending=True,
        )
    )

    if growth_chart_data.empty:
        st.info(
            "No works currently have enough "
            "historical data for this window."
        )

    else:
        growth_figure = px.bar(
            growth_chart_data,
            x="hits_change",
            y="title",
            orientation="h",
            labels={
                "hits_change": "Hits gained",
                "title": "Work",
            },
        )

        growth_figure.update_layout(
            yaxis_title=None,
            xaxis_title="Hits gained",
        )

        growth_figure.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Hits gained: %{x:+,}"
                "<extra></extra>"
            )
        )

        st.plotly_chart(
            growth_figure,
            use_container_width=True,
        )

    st.divider()

    st.subheader("Total hits by work")

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


def render_period_changes(
    changes,
    window_label,
):
    st.subheader(
        f"{window_label} change"
    )

    st.caption(
        "Each work is compared with the newest "
        "available snapshot at or before the "
        f"{window_label.lower()} cutoff."
    )

    change_table = changes[
        [
            "title",
            "hits_change",
            "kudos_change",
            "comments_change",
            "bookmarks_change",
            "baseline_collected_at",
            "baseline_hours",
        ]
    ].copy()

    change_table["Hits Δ"] = (
        change_table["hits_change"]
        .apply(display_change)
    )

    change_table["Kudos Δ"] = (
        change_table["kudos_change"]
        .apply(display_change)
    )

    change_table["Comments Δ"] = (
        change_table["comments_change"]
        .apply(display_change)
    )

    change_table["Bookmarks Δ"] = (
        change_table["bookmarks_change"]
        .apply(display_change)
    )

    change_table["Baseline"] = (
        change_table["baseline_collected_at"]
        .apply(display_timestamp)
    )

    change_table["Actual window"] = (
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
            "Actual window",
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
            f"A {window_label.lower()} baseline "
            f"is currently available for "
            f"{available} of {total} works."
        )

def render_work_detail(
    overview,
    changes,
    window_label,
):
    from app_logging import (
        get_file_logger,
    )

    from collection_lock import (
        CollectionAlreadyRunning,
    )

    from scheduled_collection import (
        run_single_work_collection,
    )

    st.divider()

    st.header(
        "Work Detail"
    )

    work_ids = (
        overview[
            "work_id"
        ].tolist()
    )

    title_by_id = dict(
        zip(
            overview["work_id"],
            overview["title"],
        )
    )

    selected_work_id = (
        st.selectbox(
            "Work",
            options=work_ids,
            format_func=lambda work_id: (
                title_by_id[
                    work_id
                ]
            ),
        )
    )

    selected_row = overview[
        overview["work_id"]
        == selected_work_id
    ].iloc[0]

    selected_title = (
        selected_row[
            "title"
        ]
    )

    selected_ao3_work_id = int(
        selected_row[
            "ao3_work_id"
        ]
    )

    selected_url = (
        "https://archiveofourown.org"
        f"/works/"
        f"{selected_ao3_work_id}"
    )

    selected_changes = changes[
        changes["work_id"]
        == selected_work_id
    ]

    if selected_changes.empty:
        change_row = None

    else:
        change_row = (
            selected_changes.iloc[0]
        )

    st.subheader(
        selected_title
    )

    work_collection_notice = (
        st.session_state.pop(
            "work_collection_notice",
            None,
        )
    )

    if (
        work_collection_notice
        and work_collection_notice.get(
            "work_id"
        )
        == selected_work_id
    ):
        notice_type = (
            work_collection_notice.get(
                "type"
            )
        )

        notice_message = (
            work_collection_notice.get(
                "message",
                "",
            )
        )

        if notice_type == "success":
            st.success(
                notice_message
            )

        elif notice_type == "warning":
            st.warning(
                notice_message
            )

        else:
            st.error(
                notice_message
            )

    st.caption(
        "Refresh only this work from AO3. "
        "This does not reset the automatic "
        "collection interval, run discovery, "
        "or trigger a database backup."
    )

    if st.button(
        "Collect this work now",
        key=(
            "collect_work_"
            f"{selected_work_id}"
        ),
    ):
        logger = (
            get_file_logger()
        )

        logger.info(
            "Manual single-work "
            "collection requested for "
            f'"{selected_title}".'
        )

        try:
            progress_output = (
                st.empty()
            )

            with st.spinner(
                f'Collecting '
                f'"{selected_title}"...'
            ):
                with (
                    capture_dashboard_progress(
                        progress_output,
                        logger,
                    )
                ):
                    result = (
                        run_single_work_collection(
                            work_id=(
                                selected_work_id
                            ),
                            ao3_work_id=(
                                selected_ao3_work_id
                            ),
                            title=(
                                selected_title
                            ),
                            url=(
                                selected_url
                            ),
                        )
                    )

            if (
                result.get(
                    "saved",
                    0,
                )
                == 1
            ):
                events_created = (
                    result.get(
                        "events_created",
                        0,
                    )
                )

                message = (
                    f'"{selected_title}" '
                    "collected successfully — "
                    "1 snapshot saved, "
                    f"{events_created} events "
                    "created."
                )

                logger.info(
                    message
                )

                notice_type = (
                    "success"
                )

            else:
                failed_work = (
                    result.get(
                        "failed_work"
                    )
                    or {}
                )

                error_message = (
                    failed_work.get(
                        "error",
                        "Unknown collection "
                        "error.",
                    )
                )

                message = (
                    f'"{selected_title}" '
                    "collection failed: "
                    f"{error_message}"
                )

                logger.error(
                    message
                )

                notice_type = (
                    "error"
                )

            st.session_state[
                "work_collection_notice"
            ] = {
                "work_id":
                    selected_work_id,
                "type":
                    notice_type,
                "message":
                    message,
            }

        except CollectionAlreadyRunning:
            message = (
                "A collection is already "
                "in progress."
            )

            logger.info(
                "Manual single-work "
                "collection was skipped "
                "because another collection "
                "is already running."
            )

            st.session_state[
                "work_collection_notice"
            ] = {
                "work_id":
                    selected_work_id,
                "type":
                    "warning",
                "message":
                    message,
            }

        except Exception as error:
            logger.exception(
                "Manual single-work "
                "collection failed."
            )

            st.session_state[
                "work_collection_notice"
            ] = {
                "work_id":
                    selected_work_id,
                "type":
                    "error",
                "message": (
                    "Manual collection failed: "
                    f"{error}"
                ),
            }

        st.rerun()

    public1, public2, public3, public4 = (
        st.columns(4)
    )

    with public1:
        st.metric(
            "Hits",
            display_number(
                selected_row[
                    "hits"
                ]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "hits_change"
                    ]
                )
            ),
        )

    with public2:
        st.metric(
            "Kudos",
            display_number(
                selected_row[
                    "kudos"
                ]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "kudos_change"
                    ]
                )
            ),
        )

    with public3:
        st.metric(
            "Comments",
            display_number(
                selected_row[
                    "comments"
                ]
            ),
            delta=(
                None
                if change_row is None
                else metric_delta(
                    change_row[
                        "comments_change"
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
                        "bookmarks_change"
                    ]
                )
            ),
        )

    st.caption(
        "Changes shown for the selected "
        f"{window_label.lower()} window."
    )

    public5, public6 = (
        st.columns(2)
    )

    with public5:
        st.metric(
            "Words",
            display_number(
                selected_row[
                    "word_count"
                ]
            ),
        )

    with public6:
        chapters_published = (
            display_number(
                selected_row[
                    "chapters_published"
                ]
            )
        )

        chapters_total = (
            display_number(
                selected_row[
                    "chapters_total"
                ]
            )
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

    render_snapshot_management(
        selected_work_id,
        selected_title,
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
    history = get_work_history(work_id)
    events = get_work_events(work_id)

    st.subheader("Historical growth")

    if history.empty:
        st.info(
            "No historical snapshots are available "
            "for this work."
        )
        return

    metric_options = {
        "Hits": "hits",
        "Kudos": "kudos",
        "Comments": "comments",
        "Public bookmarks": "public_bookmarks",
        "Subscriptions": "subscriptions",
        "Total bookmarks": "total_bookmarks",
        "Comment threads": "comment_threads",
        "Word count": "word_count",
    }

    selected_label = st.selectbox(
        "Metric",
        list(metric_options.keys()),
    )

    selected_metric = metric_options[
        selected_label
    ]

    chart_data = history.copy()

    private_metrics = {
        "subscriptions",
        "total_bookmarks",
        "comment_threads",
    }

    if selected_metric in private_metrics:
        chart_data = chart_data[
            chart_data["source"] != "ao3_public"
        ].copy()

    chart_data = chart_data.dropna(
        subset=[selected_metric]
    )

    if chart_data.empty:
        st.info(
            f"No historical {selected_label.lower()} "
            f"data is available for this work."
        )
        return

    chart_data["display_time"] = (
        chart_data["collected_at"]
        .dt.tz_convert(LOCAL_TIMEZONE)
    )

    figure = px.line(
        chart_data,
        x="display_time",
        y=selected_metric,
        markers=True,
        line_shape="hv",
        labels={
            "display_time": "Date",
            selected_metric: selected_label,
        },
        hover_data={
            "source": True,
            "display_time": False,
        },
    )

    figure.update_layout(
        xaxis_title=None,
        yaxis_title=selected_label,
    )

    has_date_only_events = False

    if not events.empty:
        event_labels = {
            "work_published": "Published",
            "chapter_published": "Chapter",
            "work_completed": "Completed",
            "note": "Note",
        }

        for _, event in events.iterrows():
            event_type = event["event_type"]

            if (
                event_type == "chapter_published"
                and pd.notna(
                    event["chapter_number"]
                )
            ):
                label = (
                    f"Ch. "
                    f"{int(event['chapter_number'])}"
                )

            elif event_type == "note":
                if (
                    pd.notna(event["description"])
                    and event["description"]
                ):
                    label = event["description"]

                else:
                    label = "Note"

            else:
                label = event_labels.get(
                    event_type,
                    event_type,
                )

            if event["date_precision"] == "date":
                has_date_only_events = True

                parsed_event = pd.to_datetime(
                    event["occurred_at"],
                    format="mixed",
                )

                event_date = parsed_event.date()

                event_time = pd.Timestamp(
                    event_date
                ).tz_localize(
                    LOCAL_TIMEZONE
                )

                event_time = (
                    event_time
                    + pd.Timedelta(hours=12)
                )

                chart_label = (
                    f"{label} (date)"
                )

            else:
                event_time = pd.to_datetime(
                    event["occurred_at"],
                    format="mixed",
                    utc=True,
                )

                event_time = (
                    event_time.tz_convert(
                        LOCAL_TIMEZONE
                    )
                )

                chart_label = label

            figure.add_vline(
                x=event_time,
                line_dash="dot",
                opacity=0.6,
            )

            figure.add_annotation(
                x=event_time,
                y=1,
                yref="paper",
                text=chart_label,
                showarrow=False,
                textangle=-90,
                xanchor="left",
                yanchor="top",
            )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    if has_date_only_events:
        st.caption(
            "Events marked “(date)” have only a "
            "calendar date available. They are "
            "positioned at noon for visualization; "
            "the actual event time is unknown."
        )

    if not events.empty:
        with st.expander("Events on this chart"):
            event_table = events.copy()

            def format_event_date(row):
                if (
                    row["date_precision"]
                    == "date"
                ):
                    parsed_date = pd.to_datetime(
                        row["occurred_at"],
                        format="mixed",
                    )

                    return (
                        parsed_date.strftime(
                            "%b %d, %Y"
                        )
                        + " (date only)"
                    )

                return display_timestamp(
                    row["occurred_at"]
                )

            event_table["Date"] = (
                event_table.apply(
                    format_event_date,
                    axis=1,
                )
            )

            event_table["Event"] = (
                event_table["event_type"]
                .map({
                    "work_published":
                        "Work published",
                    "chapter_published":
                        "Chapter published",
                    "work_completed":
                        "Work completed",
                    "note":
                        "Note",
                })
                .fillna(
                    event_table["event_type"]
                )
            )

            event_table["Chapter"] = (
                event_table["chapter_number"]
            )

            event_table["Description"] = (
                event_table["description"]
            )

            event_table["Source"] = (
                event_table["source"]
                .map({
                    "manual":
                        "Manual",
                    "ao3_detected":
                        "AO3 detected",
                    "ao3_backfill":
                        "AO3 backfill",
                })
                .fillna(
                    event_table["source"]
                )
            )

            event_table["Date source"] = (
                event_table["date_source"]
                .map({
                    "manual":
                        "Manual",
                    "ao3_published":
                        "AO3 published date",
                    "ao3_chapter_date":
                        "AO3 chapter date",
                    "ao3_updated":
                        "AO3 updated date",
                    "ao3_completed":
                        "AO3 completed date",
                    "collector_detected":
                        "Collector detection",
                })
                .fillna(
                    event_table["date_source"]
                )
            )

            event_table["Detected"] = (
                event_table["detected_at"]
                .apply(
                    lambda value:
                        display_timestamp(value)
                        if pd.notna(value)
                        and value
                        else "—"
                )
            )

            event_table = event_table[
                [
                    "Date",
                    "Event",
                    "Chapter",
                    "Description",
                    "Source",
                    "Date source",
                    "Detected",
                ]
            ]

            st.dataframe(
                event_table,
                hide_index=True,
                use_container_width=True,
            )


def render_snapshot_management(
    work_id,
    work_title,
):
    from app_logging import (
        get_file_logger,
    )

    from database import (
        delete_snapshots,
    )

    snapshots = (
        get_snapshot_management_data(
            work_id
        )
    )

    st.divider()

    notice = st.session_state.get(
        "snapshot_delete_notice"
    )

    if (
        notice
        and notice.get(
            "work_id"
        )
        == work_id
    ):
        st.success(
            notice.get(
                "message",
                "Snapshot deletion complete.",
            )
        )

        del st.session_state[
            "snapshot_delete_notice"
        ]

    if snapshots.empty:
        st.info(
            "No snapshots are available "
            "for this work."
        )
        return

    snapshot_table = (
        snapshots.copy()
        .reset_index(
            drop=True
        )
    )

    snapshot_table[
        "snapshot_id"
    ] = (
        snapshot_table[
            "snapshot_id"
        ]
        .astype(int)
    )

    latest_snapshot_id = int(
        snapshot_table.iloc[0][
            "snapshot_id"
        ]
    )

    display_table = pd.DataFrame(
        index=snapshot_table.index
    )

    display_table[
        "Latest"
    ] = ""

    display_table.loc[
        0,
        "Latest",
    ] = "✓"

    display_table[
        "Collected"
    ] = (
        snapshot_table[
            "collected_at"
        ]
        .apply(
            display_timestamp
        )
    )

    display_table[
        "Source"
    ] = (
        snapshot_table[
            "source"
        ]
        .apply(
            display_source
        )
    )

    display_table[
        "Hits"
    ] = (
        snapshot_table[
            "hits"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Kudos"
    ] = (
        snapshot_table[
            "kudos"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Comments"
    ] = (
        snapshot_table[
            "comments"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Public bookmarks"
    ] = (
        snapshot_table[
            "public_bookmarks"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Words"
    ] = (
        snapshot_table[
            "word_count"
        ]
        .apply(
            display_number
        )
    )

    def format_chapters(
        row,
    ):
        published = row[
            "chapters_published"
        ]

        total = row[
            "chapters_total"
        ]

        if pd.isna(
            published
        ):
            return "—"

        published = int(
            published
        )

        if pd.isna(
            total
        ):
            return (
                f"{published}/?"
            )

        return (
            f"{published}/"
            f"{int(total)}"
        )

    display_table[
        "Chapters"
    ] = (
        snapshot_table.apply(
            format_chapters,
            axis=1,
        )
    )

    display_table[
        "Subscriptions"
    ] = (
        snapshot_table[
            "subscriptions"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Total bookmarks"
    ] = (
        snapshot_table[
            "total_bookmarks"
        ]
        .apply(
            display_number
        )
    )

    display_table[
        "Comment threads"
    ] = (
        snapshot_table[
            "comment_threads"
        ]
        .apply(
            display_number
        )
    )

    pending_key = (
        "snapshot_delete_pending_"
        f"{work_id}"
    )

    generation_key = (
        "snapshot_selection_generation_"
        f"{work_id}"
    )

    if generation_key not in (
        st.session_state
    ):
        st.session_state[
            generation_key
        ] = 0

    selection_generation = (
        st.session_state[
            generation_key
        ]
    )

    selector_key = (
        "snapshot_selector_"
        f"{work_id}_"
        f"{selection_generation}"
    )

    with st.expander(
        (
            "Manage snapshots "
            f"({len(snapshot_table)})"
        ),
        expanded=False,
    ):
        st.caption(
            "Select one or more rows to "
            "delete. Deletion is permanent "
            "and requires confirmation."
        )

        selection_event = (
            st.dataframe(
                display_table,
                hide_index=True,
                use_container_width=True,
                key=selector_key,
                on_select="rerun",
                selection_mode=(
                    "multi-row"
                ),
            )
        )

        selected_positions = list(
            selection_event
            .selection
            .rows
        )

        if selected_positions:
            selected_ids = (
                snapshot_table
                .iloc[
                    selected_positions
                ][
                    "snapshot_id"
                ]
                .astype(int)
                .tolist()
            )

        else:
            selected_ids = []

        selected_count = len(
            selected_ids
        )

        if selected_count:
            st.caption(
                f"{selected_count} snapshot"
                f"{'s' if selected_count != 1 else ''} "
                "selected."
            )

        if st.button(
            (
                "Delete selected "
                f"snapshot"
                f"{'s' if selected_count != 1 else ''}"
            ),
            key=(
                "delete_snapshots_"
                f"{work_id}"
            ),
            disabled=(
                selected_count == 0
            ),
        ):
            st.session_state[
                pending_key
            ] = list(
                selected_ids
            )

            # Force the selection table to
            # get a brand-new widget identity
            # on the confirmation rerun.
            st.session_state[
                generation_key
            ] += 1

            st.rerun()

    pending_ids = list(
        st.session_state.get(
            pending_key,
            [],
        )
    )

    if not pending_ids:
        return

    current_ids = set(
        snapshot_table[
            "snapshot_id"
        ]
        .astype(int)
        .tolist()
    )

    invalid_ids = [
        snapshot_id
        for snapshot_id
        in pending_ids
        if snapshot_id
        not in current_ids
    ]

    if invalid_ids:
        st.error(
            "The pending snapshot selection "
            "no longer matches the current "
            "work data. Nothing was deleted."
        )

        del st.session_state[
            pending_key
        ]

        return

    pending_mask = (
        snapshot_table[
            "snapshot_id"
        ]
        .isin(
            pending_ids
        )
    )

    pending_rows = (
        display_table.loc[
            pending_mask,
            [
                "Latest",
                "Collected",
                "Source",
                "Hits",
                "Kudos",
                "Comments",
                "Public bookmarks",
                "Words",
                "Chapters",
            ],
        ]
        .copy()
    )

    pending_count = len(
        pending_ids
    )

    st.warning(
        (
            f"Delete {pending_count} "
            f"snapshot"
            f"{'s' if pending_count != 1 else ''} "
            f'from "{work_title}"? '
            "This cannot be undone."
        )
    )

    st.caption(
        "The following snapshots will "
        "be deleted:"
    )

    st.dataframe(
        pending_rows,
        hide_index=True,
        use_container_width=True,
    )

    if (
        latest_snapshot_id
        in pending_ids
    ):
        st.warning(
            "The selection includes the "
            "latest snapshot for this work. "
            "After deletion, the previous "
            "snapshot will become current."
        )

    confirm_column, cancel_column = (
        st.columns(2)
    )

    with confirm_column:
        if st.button(
            "Confirm deletion",
            type="primary",
            key=(
                "confirm_snapshot_delete_"
                f"{work_id}"
            ),
        ):
            # Revalidate immediately before
            # performing the destructive call.
            current_snapshot_ids = set(
                get_snapshot_management_data(
                    work_id
                )[
                    "snapshot_id"
                ]
                .astype(int)
                .tolist()
            )

            still_valid = all(
                snapshot_id
                in current_snapshot_ids
                for snapshot_id
                in pending_ids
            )

            if not still_valid:
                st.error(
                    "Snapshot data changed "
                    "before deletion. Nothing "
                    "was deleted."
                )

                del st.session_state[
                    pending_key
                ]

                st.session_state[
                    generation_key
                ] += 1

                st.rerun()

            deleted = (
                delete_snapshots(
                    pending_ids
                )
            )

            logger = (
                get_file_logger()
            )

            logger.info(
                "Deleted "
                f"{deleted} snapshot"
                f"{'s' if deleted != 1 else ''} "
                f'from "{work_title}" '
                "through the dashboard."
            )

            st.session_state[
                "snapshot_delete_notice"
            ] = {
                "work_id":
                    work_id,
                "message": (
                    f"Deleted {deleted} "
                    f"snapshot"
                    f"{'s' if deleted != 1 else ''} "
                    f'from "{work_title}".'
                ),
            }

            del st.session_state[
                pending_key
            ]

            st.session_state[
                generation_key
            ] += 1

            st.rerun()

    with cancel_column:
        if st.button(
            "Cancel",
            key=(
                "cancel_snapshot_delete_"
                f"{work_id}"
            ),
        ):
            del st.session_state[
                pending_key
            ]

            # New key on rerun guarantees
            # that Cancel really means an
            # empty selection.
            st.session_state[
                generation_key
            ] += 1

            st.rerun()
            

def render_system_health():
    from app_logging import (
        get_file_logger,
    )

    from collection_lock import (
        CollectionAlreadyRunning,
    )

    from scheduled_collection import (
        run_collection_cycle,
    )

    health = get_system_health()

    with st.expander(
        "System health",
        expanded=True,
    ):
        collection_notice = (
            st.session_state.pop(
                "collection_notice",
                None,
            )
        )

        if collection_notice:
            notice_type = (
                collection_notice[
                    "type"
                ]
            )

            notice_message = (
                collection_notice[
                    "message"
                ]
            )

            if notice_type == "success":
                st.success(
                    notice_message
                )

            elif notice_type == "warning":
                st.warning(
                    notice_message
                )

            else:
                st.error(
                    notice_message
                )

            failed_works = (
                collection_notice.get(
                    "failed_works",
                    [],
                )
            )

            successful_works = (
                collection_notice.get(
                    "successful_works",
                    [],
                )
            )

            if successful_works:
                with st.expander(
                    f"Successful works "
                    f"({len(successful_works)})",
                    expanded=bool(failed_works),
                ):
                    success_table = (
                        pd.DataFrame(
                            successful_works
                        )
                    )

                    success_table = (
                        success_table.rename(
                            columns={
                                "title": "Work",
                                "ao3_work_id":
                                    "AO3 Work ID",
                                "hits": "Hits",
                                "kudos": "Kudos",
                                "comments": "Comments",
                                "public_bookmarks":
                                    "Bookmarks",
                            }
                        )
                    )

                    st.dataframe(
                        success_table,
                        hide_index=True,
                        use_container_width=True,
                    )

            if failed_works:
                with st.expander(
                    f"Failed works "
                    f"({len(failed_works)})",
                    expanded=True,
                ):
                    failure_table = (
                        pd.DataFrame(
                            failed_works
                        )
                    )

                    failure_table = (
                        failure_table.rename(
                            columns={
                                "title":
                                    "Work",
                                "ao3_work_id":
                                    "AO3 Work ID",
                                "error":
                                    "Error",
                            }
                        )
                    )

                    st.dataframe(
                        failure_table,
                        hide_index=True,
                        use_container_width=True,
                    )

        column1, column2 = (
            st.columns(2)
        )

        with column1:
            st.metric(
                "Latest live snapshot",
                (
                    display_timestamp(
                        health[
                            "latest_public_snapshot"
                        ]
                    )
                    if health[
                        "latest_public_snapshot"
                    ]
                    else "—"
                ),
            )

            interval = health[
                "collection_interval_hours"
            ]

            if interval is not None:
                st.caption(
                    "Configured collection "
                    f"interval: {interval} hours"
                )

        with column2:
            st.metric(
                "Last collection cycle",
                (
                    display_timestamp(
                        health[
                            "last_scheduled_collection"
                        ]
                    )
                    if health[
                        "last_scheduled_collection"
                    ]
                    else "—"
                ),
            )

        column3, column4 = (
            st.columns(2)
        )

        with column3:
            st.metric(
                "Last daily email",
                (
                    display_timestamp(
                        health[
                            "last_daily_summary"
                        ]
                    )
                    if health[
                        "last_daily_summary"
                    ]
                    else "—"
                ),
            )

        with column4:
            st.metric(
                "Latest database backup",
                (
                    display_timestamp(
                        health[
                            "latest_backup"
                        ]
                    )
                    if health[
                        "latest_backup"
                    ]
                    else "—"
                ),
            )

            st.caption(
                "Stored backups: "
                f"{health['backup_count']}"
            )

            if health[
                "latest_backup_name"
            ]:
                st.caption(
                    health[
                        "latest_backup_name"
                    ]
                )

        st.divider()

        st.caption(
            "Run the normal AO3 collection "
            "cycle immediately. This also "
            "checks for new works and resets "
            "the automatic collection interval."
        )

        if st.button(
            "Run collection now",
            type="primary",
        ):
            logger = get_file_logger()

            logger.info(
                "Manual dashboard collection "
                "requested."
            )

            try:
                progress_output = st.empty()

                with st.spinner(
                    "Collecting AO3 stats..."
                ):
                    with capture_dashboard_progress(
                        progress_output,
                        logger,
                    ):
                        result = (
                            run_collection_cycle(
                                trigger="manual"
                            )
                        )

                collection_result = (
                    result.get(
                        "collection"
                    )
                    or {}
                )

                discovery_result = (
                    result.get(
                        "discovery"
                    )
                    or {}
                )

                saved = (
                    collection_result.get(
                        "saved",
                        0,
                    )
                )

                failed = (
                    collection_result.get(
                        "failed",
                        0,
                    )
                )

                failed_works = (
                    collection_result.get(
                        "failed_works",
                        [],
                    )
                )

                successful_works = (
                    collection_result.get(
                        "successful_works",
                        [],
                    )
                )

                events_created = (
                    collection_result.get(
                        "events_created",
                        0,
                    )
                )

                new_works = (
                    discovery_result.get(
                        "new",
                        0,
                    )
                )

                added = (
                    discovery_result.get(
                        "added",
                        0,
                    )
                )

                message = (
                    "Collection complete — "
                    f"{saved} snapshots saved, "
                    f"{failed} failed, "
                    f"{events_created} events "
                    "created. "
                    f"{new_works} new works "
                    f"found, {added} added."
                )

                logger.info(
                    "Manual dashboard "
                    f"{message.lower()}"
                )

                if failed == 0:
                    notice_type = "success"

                elif saved ==0:
                    notice_type = "error"

                else:
                    notice_type = "warning"

                st.session_state[
                    "collection_notice"
                ] = {
                    "type": notice_type,
                    "message": message,
                    "successful_works":
                        successful_works,
                    "failed_works":
                        failed_works,
                }

            except CollectionAlreadyRunning:
                logger.info(
                    "Manual dashboard collection "
                    "was skipped because another "
                    "collection is already running."
                )

                st.session_state[
                    "collection_notice"
                ] = {
                    "type": "warning",
                    "message": (
                        "A collection is already "
                        "in progress."
                    ),
                    "failed_works": [],
                    "successful_works": [],
                }

            except Exception as error:
                logger.exception(
                    "Manual dashboard collection "
                    "failed."
                )

                st.session_state[
                    "collection_notice"
                ] = {
                    "type": "error",
                    "message": (
                        "Manual collection failed: "
                        f"{error}"
                    ),
                    "failed_works": [],
                }

            st.rerun()

        st.divider()

        if health[
            "latest_log_activity"
        ]:
            st.caption(
                "Latest operational log "
                "activity: "
                + display_timestamp(
                    health[
                        "latest_log_activity"
                    ]
                )
            )

        latest_error = health[
            "latest_error"
        ]

        if latest_error:
            st.warning(
                "Most recent logged error:\n\n"
                f"{latest_error}"
            )

        else:
            st.success(
                "No ERROR-level entries "
                "found in the current "
                "operational log."
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

    window_options = {
        "24 hours": 24,
        "7 days": 24 * 7,
        "30 days": 24 * 30,
    }

    window_label = st.radio(
        "Change window",
        options=list(
            window_options.keys()
        ),
        horizontal=True,
    )

    window_hours = (
        window_options[window_label]
    )

    changes = get_period_changes(
        window_hours
    )

    render_overview(
        overview,
        changes,
        window_label,
    )

    render_work_detail(
        overview,
        changes,
        window_label,
    )


if __name__ == "__main__":
    main()