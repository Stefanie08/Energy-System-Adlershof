# coding: utf-8
r"""
Inputs
-------
postprocessed : str
    ``results/{scenario}/postprocessed/``: path to the directory containing the input data
    that can be plotted
plotted : str
    ``results/{scenario}/plotted/dispatch/``: path where a new directory is created and
    the plots are saved
logfile : str
    ``results/{scenario}/{scenario}.log``: path to logfile

Outputs
---------
* Static dispatch plots.
* Interactive plotly dispatch plot in html-format.

Description
-------------
The script creates dispatch plots based on plot_dispatch and plot_dispatch_plotly
functions in oemoflex.
The static plots are saved with a file format defined by the *plot_filetype* variable in
``oemof_b3/config/settings.yaml`` and the interactive plotly plots as html-files
in a new directory called dispatch within directory plotted.
Timeframes and the carrier for the plot can be chosen.
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import oemoflex.tools.plots as plots
import matplotlib.dates as mdates

from oemof_b3.config.config import LABELS, COLORS
from oemof_b3.config import config
from oemof_b3.tools import data_processing as dp


def prepare_dispatch_data(bus_file):
    """
    This function prepares data for the dispatch plot

    Parameters
    ----------
    bus_file: str
        File name of the bus file

    Returns
    -------
    df: pd.DataFrame
        Dataframe with data to be plotted
    df_demand: pd.DataFrame
        Dataframe with demand
    bus_name: str
        Name of the bus

    """
    bus_name = os.path.splitext(bus_file)[0]
    bus_path = os.path.join(bus_directory, bus_file)

    data = pd.read_csv(
        bus_path,
        header=[0, 1, 2],
        parse_dates=[0],
        index_col=[0],
        sep=config.settings.general.separator,
    )

    # convert data to SI-unit
    MW_to_W = 1e6
    data = data * MW_to_W

    # prepare dispatch data
    df, df_demand = plots.prepare_dispatch_data(
        data,
        bus_name=bus_name,
        demand_name="demand",
        labels_dict=LABELS,
    )

    return df, df_demand, bus_name


def plot_dispatch_data(df, df_demand, bus_name):
    """
    This function contains the plotting of dispatch data

    Parameters
    ----------
    df: pd.DataFrame
        Dataframe with data to be plotted
    df_demand: pd.DataFrame
        Dataframe with demand
    bus_name: str
        Name of the bus

    Returns
    -------

    """
    # change colors for demand in colors_odict to black
    for i in df_demand.columns:
        COLORS[i] = "#000000"

    # sort positive and negative flows from biggest to smallest

    pos_cols = df.columns[df.sum() > 0]
    neg_cols = df.columns[df.sum() <= 0]

    pos_sorted = df[pos_cols].sum().sort_values(ascending=True).index
    neg_sorted = df[neg_cols].sum().sort_values(ascending=False).index

    df = df[list(pos_sorted) + list(neg_sorted)]

    # interactive plotly dispatch plot
    fig_plotly = plots.plot_dispatch_plotly(
        df=df, df_demand=df_demand, unit="W", colors_odict=COLORS
    )
    file_name = bus_name + "_dispatch_interactive" + ".html"
    fig_plotly.write_html(
        file=os.path.join(plotted, file_name),
        # The following parameters are set according to
        # https://plotly.github.io/plotly.py-docs/generated/plotly.io.write_html.html
        # The files are much smaller now because a script tag containing the plotly.js source
        # code (~3MB) is not included in the output anymore. It is refered to plotlyjs via a
        # link in div of the plot.
        include_plotlyjs="cdn",
        full_html=False,
    )

    # merge excess/shortage pairs into one legend entry
    simple_labels_dict = {
        "Strom shortage / Abregelung": ["Strom shortage", "Abregelung"],
        "zen. Wärme mismatch": ["zen. Wärmeüberschuss", "zen. Wärme shortage"],
        "dez. Wärme mismatch": ["dez. Wärmeüberschuss", "dez. Wärme shortage"],
    }

    year = df.index[0].year

    # daily resample of values
    df_daily = df.resample("D").mean()
    df_demand_daily = df_demand.resample("D").mean()

    if not df_daily.empty:
        fig, ax = plt.subplots(figsize=(25, 10))
        plots.plot_dispatch(
            ax=ax,
            df=df_daily,
            df_demand=df_demand_daily,
            unit="W",
            colors_odict=COLORS,
        )
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.set_xlabel("Monat", fontsize=18)
        ax.set_ylabel("Erzeugte Leistung", fontsize=18)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)

        handles, labels = reduce_labels(ax=ax, simple_labels_dict=simple_labels_dict)
        ax.legend(
            handles=handles,
            labels=labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            fancybox=True,
            ncol=4,
            fontsize=18,
        )
        fig.subplots_adjust(bottom=0.3)  # fixer Platz für Legende unten
        file_name = bus_name + "_year" + config.settings.general.plot_filetype
        fig.savefig(os.path.join(plotted, file_name), bbox_inches="tight")
        plt.close(fig)

    # plots for specific months
    timeframe = [
        (f"{year}-01-01 00:00:00", f"{year}-01-31 23:00:00"),
        (f"{year}-04-01 00:00:00", f"{year}-04-30 23:00:00"),
        (f"{year}-07-01 00:00:00", f"{year}-07-31 23:00:00"),
        (f"{year}-10-01 00:00:00", f"{year}-10-31 23:00:00"),
    ]

    if "heat_decentral" in bus_name:
        timeframe += [
            (f"{year}-02-15 00:00:00", f"{year}-02-15 23:00:00"),  # Winterwoche
            (f"{year}-07-10 00:00:00", f"{year}-07-10 23:00:00"),  # Sommertag
        ]

    if "electricity" in bus_name:
        timeframe += [
            (f"{year}-01-01 00:00:00", f"{year}-01-31 23:00:00"),  # anderer Wintertag
            (f"{year}-07-10 00:00:00", f"{year}-07-10 23:00:00"),  # anderer Sommertag
        ]

    for start_date, end_date in timeframe:
        df_time_filtered = plots.filter_timeseries(df, start_date, end_date)
        df_demand_time_filtered = plots.filter_timeseries(
            df_demand, start_date, end_date
        )

        if df_time_filtered.empty:
            logger.warning(f"Data for bus '{bus_name}' is empty, cannot plot.")
            continue

        fig, ax = plt.subplots(figsize=(20, 8))
        plots.plot_dispatch(
            ax=ax,
            df=df_time_filtered,
            df_demand=df_demand_time_filtered,
            unit="W",
            colors_odict=COLORS,
        )
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.set_xlabel("Datum (MM-TT)", fontsize=18)
        ax.set_ylabel("Erzeugte Leistung", fontsize=18)
        # NACHHER — Dauer des Zeitraums berechnen und Formatter anpassen:
        duration_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days

        if duration_days <= 1:
            # Tagesplot: nur Uhrzeit
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            ax.set_xlabel("Uhrzeit (HH:MM)", fontsize=18)
        elif duration_days <= 7:
            # Wochenplot: Wochentag + Uhrzeit
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            ax.set_xlabel("Datum", fontsize=18)
        else:
            # Monatsplot: wie bisher
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.set_xlabel("Datum (MM-TT)", fontsize=18)
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)

        handles, labels = reduce_labels(ax=ax, simple_labels_dict=simple_labels_dict)
        ax.legend(
            handles=handles,
            labels=labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            fancybox=True,
            ncol=4,
            fontsize=18,
        )
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.3)  # fixer Platz für Legende unten
        file_name = (
            bus_name + "_" + start_date[5:7] + config.settings.general.plot_filetype
        )
        fig.savefig(os.path.join(plotted, file_name), bbox_inches="tight")
        plt.close(fig)


def get_df_for_aggregation(list_with_dfs):
    """
    This function adds DataFrames from a list in to a new Dataframe

    Parameters
    ----------
    list_with_dfs: list
        List containing DataFrames to be added to Dataframe `df_concatenated`

    Returns
    -------
    df_concatenated: pd.DataFrame
        Result DataFrame with concatenated DataFrames

    """
    df_concatenated = pd.concat(list_with_dfs, axis=0, ignore_index=True)

    return df_concatenated


def reduce_labels(ax, simple_labels_dict):
    """
    Replaces two labels by one as defined in a dictionary.

    Parameters
    ----------
    ax: matplotlib.axes
        The axes containing the plot for which the labels shall be simplified
    simple_labels_dict:
        dictionary which contains the simplified label as a key
        and for every key a list of two labels
        which shall be replaced by the simplified label as value

    Returns
    -------

    """
    handles, labels = ax.get_legend_handles_labels()

    for key, value in simple_labels_dict.items():
        if value[0] in labels and value[1] in labels:
            labels = [
                key if item == value[0] else "_Hidden" if item == value[1] else item
                for item in labels
            ]
    return handles, labels


def aggregate_by_region(bus_files, carrier):
    """
    This function aggregates data of busses and demand by region

    Parameters
    ----------
    bus_files: pd.DataFrame
        Dataframe with bus data from ``results/{scenario}/postprocessed/sequences/bus``

    Returns
    -------
    df_aggregated: pd.DataFrame
        Dataframe with aggregated data

    df_demand_aggregated: pd.DataFrame
        Dataframe with aggregated demands

    bus_name: str
        Name of the bus

    """

    # Add list for stacked DataFrames
    list_df_stacked = []
    list_df_demand_stacked = []

    # Find all files where carrier is same and hence multiple regions exist
    busses_to_be_aggregated = [file for file in bus_files if carrier in file]
    if len(busses_to_be_aggregated) > 1:
        for bus_to_be_aggregated in busses_to_be_aggregated:
            df, df_demand, bus_name = prepare_dispatch_data(bus_to_be_aggregated)

            list_df_stacked.append(dp.stack_timeseries(df))
            list_df_demand_stacked.append(dp.stack_timeseries(df_demand))

        df_stacked = get_df_for_aggregation(list_df_stacked)
        df_demand_stacked = get_df_for_aggregation(list_df_demand_stacked)

        # Exchange region from bus_name with "ALL"
        bus_name = "ALL_" + carrier

        # Aggregate bus data and demand
        df_aggregated = dp.aggregate_timeseries(
            df_stacked, columns_to_aggregate="region"
        )
        df_demand_aggregated = dp.aggregate_timeseries(
            df_demand_stacked, columns_to_aggregate="region"
        )
        # Unstack aggregated bus data and demand
        df_aggregated = dp.unstack_timeseries(df_aggregated)
        df_demand_aggregated = dp.unstack_timeseries(df_demand_aggregated)

        return df_aggregated, df_demand_aggregated, bus_name


if __name__ == "__main__":
    postprocessed = sys.argv[1]
    plotted = sys.argv[2]

    logger = config.add_snake_logger("plot_dispatch")

    # create the directory plotted where all plots are saved
    if not os.path.exists(plotted):
        os.makedirs(plotted)

    bus_directory = os.path.join(postprocessed, "sequences/bus/")
    bus_files = os.listdir(bus_directory)

    # select carrier
    carriers = ["electricity", "heat_central", "heat_decentral"]

    selected_bus_files = [
        file for file in bus_files for carrier in carriers if carrier in file
    ]
    for carrier in carriers:
        try:
            df_aggregated, df_demand_aggregated, bus_name = aggregate_by_region(
                bus_files, carrier
            )
            plot_dispatch_data(df_aggregated, df_demand_aggregated, bus_name)
        except Exception:
            logger.warning(f"Could not plot dispatch for carrier {carrier}")

    for bus_file in selected_bus_files:
        df, df_demand, bus_name = prepare_dispatch_data(bus_file)
        plot_dispatch_data(df, df_demand, bus_name)
