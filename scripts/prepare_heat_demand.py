# coding: utf-8
r"""
Inputs
-------
in_path1 : str
    ``raw/weatherdata``: path of input directory with regional heat load time series as .csv
in_path2 : str
    ``raw/scalars/demands.csv``: path of scalar data with yearly heat demands as .csv
out_path1 : str
    ``results/_resources/scal_load_heat.csv``: path of output file with aggregated scalar data as
    .csv
out_path2 : str
    ``results/_resources/ts_load_heat.csv``: path of output file with timeseries data as .csv

Outputs
---------
scal_load_heat.csv : pandas.DataFrame
    Aggregated yearly heat demands per region, scenario and carrier.
ts_load_heat.csv : pandas.DataFrame
    Hourly heat demand profiles in oemof-B3 timeseries format, one row per
    region-scenario-carrier combination.

Description
-------------
Prepares hourly heat demand profiles for central and decentral heat per region and scenario.
Regional load time series (1h resolution) are read and scaled to match the total yearly
heat demands from the scalar data. Sectors (sfh, mfh, ghd, dc, lab) are aggregated into
central and decentral heat demand profiles. Aggregated yearly scalar demands are also written
as output.
"""
import datetime
import itertools
import os
import sys

import numpy as np
import pandas as pd

import oemof_b3.tools.data_processing as dp
from oemof_b3.config import config


def get_shares_building_distribution(path, region):
    """
    This function calculates the share of single family houses (Einfamilienhaus: efh),
    multi-family houses (Mehrfamilienhaus: mfh), labs, datacenter, and commercial,
    trade, and services (GHD) from the building distribution in input data

    Parameters
    ----------
    path : str
        Path to data

    region : str
        Region (eg. Adlershof)

    Returns
    -------
    shares : dict[str, float]
        Mapping from building type ('sfh', 'mfh', 'lab', 'dc', 'ghd')
        to its relative share in the total building distribution.
    """
    # Get share of EFH and MFH from distribution of households
    distribution_building = pd.read_csv(path)
    distribution_building_area = distribution_building[
        distribution_building["region"] == region
    ]

    shares = distribution_building_area.set_index("region").to_dict(orient="index")[
        region
    ]

    return shares


def find_regional_files(path, region):
    """
    This function returns a list of file names in a directory that match the specified region.

    Parameters
    ----------
    path : str
        Path to data

    region : str
        Region (eg. Adlershos)

    Returns
    -------
    files_region : list
        List of file names matching region
    """
    files_region = [file for file in os.listdir(path) if f"_{region}_" in file]
    files_region = sorted(files_region)

    if not files_region:
        raise FileNotFoundError(
            f"No data of region {region} could be found in directory: {path}."
        )

    return files_region


def get_year(file_name):
    """
    This function returns a year from file name

    Parameters
    ----------
    file_name : str
        Name of file with year in it

    Returns
    -------
    year : int
        Year
    """
    # Add array with years to be searched for in file name
    years_search_array = np.arange(1990, 2051)
    newline = "\n"

    year_in_file = [
        year_searched
        for year_searched in years_search_array
        if str(year_searched) in file_name
    ]
    if len(year_in_file) == 1:
        year = year_in_file[0]
    else:
        raise ValueError(
            f"Your file {file_name} is missing a year or has multiple years "
            f"in its name." + newline + "Please provide data for a single year "
            "with that year in the file name."
        )

    return year


def check_central_decentral(demands, value, consumer, carrier):
    """
    This function adds yearly demands per consumer and carrier to existing column
    in DataFrame and otherwise to a new column in this DataFrame

    Parameters
    ----------
    demands : pd.DataFrame
         DataFrame that contains yearly demands
    value : float
         Value of the yearly demand
    consumer : str
         Name of the consumer (eg.: ghd, efh, mfh)
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)

    Returns
    -------
    demands : pd.DataFrame
         Updated DataFrame that contains yearly demands
    """
    col_name = consumer + "_" + carrier

    if col_name in demands.columns:
        demands[col_name].values[0] = np.add(demands[col_name].values[0], value)
    else:
        demands[col_name] = [value]
    return demands


def get_heat_demand(scalars, scenario, carrier, region):
    """
    This function returns ghd and hh demands together with their unit of a given region and a
    given scenario

    Parameters
    ----------
    scalars : DataFrame
        Dataframe with scalars
    scenario : str
        Scenario e.g. "2040-el_eff"
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)
    region : str
        Region (eg. Adlershos)

    Returns
    -------
    demands : DataFrame
        Dataframe with total yearly demand of central and decentral heat per consumer
        (eg.: ghd, hh)
    demand_unit : list of str
        Unit(s) of total demands (eg. ['GWh'])

    """
    consumers = ["ghd", "hh", "dc", "lab"]
    demands = pd.DataFrame()

    sc_filtered = dp.filter_df(scalars, "type", "load")
    sc_filtered = dp.filter_df(sc_filtered, "carrier", carrier)
    sc_filtered = dp.filter_df(sc_filtered, "region", region)
    sc_filtered = dp.filter_df(sc_filtered, "scenario_key", scenario)
    if sc_filtered.empty or sc_filtered["var_value"].isna().all():
        raise ValueError(
            f"No scalar data found that matches "
            f"scenario='{scenario}', "
            f"carrier='{carrier}', "
            f"region='{region}'"
        )

    if not (sc_filtered["var_unit"].values[0] == sc_filtered["var_unit"].values).all():
        raise ValueError(
            f"Unit mismatch in scalar data of heat demands. "
            f"Please make sure units match in the scalar input data."
        )

    demand_unit = list(set(sc_filtered["var_unit"]))

    for consumer in consumers:
        sc_filtered_consumer = sc_filtered[sc_filtered["tech"].str.contains(consumer)]

        if len(sc_filtered_consumer) > 1:
            logger.warning(
                f"There is duplicate demand of carrier '{carrier}', consumer "
                f"'{consumer}', region '{region}' and scenario '{scenario}' in {in_path2}."
                + "\n"
                + "The demand is going to be summed up. "
                "Otherwise you have to rerun the calculation and provide only one demand of the "
                "same carrier, consumer, region and scenario."
            )

        for demand_value in sc_filtered_consumer["var_value"].values:
            check_central_decentral(demands, demand_value, consumer, carrier)

    return demands, demand_unit


def calculate_heat_load(sector, carrier, heat_load, yearly_demands):
    """
    This function calculates a heat load profile of a consumer
    (eg.: ghd, sfh, mfh) using heat_load data.

    Parameters
    ----------
    sector : str
        Name of sector (eg. hh, ghd)
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)
    heat_load : DataFrame
         DataFrame of heat load profile
    yearly_demands: DataFrame
         DataFrame with yearly demands per consumer

    Returns
    -------
    heat_load_total : pd.DataFrame
         DataFrame with total heat load in year for a consumer
         (eg.: ghd, sfh)

    """
    # Calculate heat load profile of year
    heat_load_sector = pd.DataFrame(
        index=pd.date_range(
            datetime.datetime(year, 1, 1, 0), periods=len(heat_load), freq="h"
        )
    )

    if carrier == "heat_decentral":
        if sector == "sfh":
            heat_load_sector[f"sfh_{carrier}"] = (
                heat_load["heat_demand"] * yearly_demands["hh" + "_" + carrier][0]
            )
        elif sector == "mfh":
            heat_load_sector[f"mfh_{carrier}"] = (
                heat_load["heat_demand"] * yearly_demands["hh" + "_" + carrier][0]
            )
        else:
            return pd.DataFrame()

    elif carrier == "heat_central":
        if sector in ["sfh", "mfh"]:
            return pd.DataFrame()
        elif sector in ["ghd", "dc", "lab"]:
            heat_load_sector[f"{sector}_{carrier}"] = (
                heat_load["heat_demand"] * yearly_demands[sector + "_" + carrier][0]
            )
        else:
            raise ValueError(
                f"Sector '{sector}' not recognized. Please check the demand file name."
            )

    else:
        raise ValueError(f"Carrier '{carrier}' not recognized.")

    return heat_load_sector


def prepare_heat_load_data(load, year):
    """
    Reads a regional heat load CSV file and returns a DataFrame indexed by datetime.

    Parameters
    ----------
    load : str
        Path to the CSV file with heat load data.
    year : int
        Year to assign to the datetime index.

    Returns
    -------
    load : pd.DataFrame
        DataFrame with columns 'heat_demand', 'cold_demand', 'electricity_demand' in MW,
        indexed by hourly datetime.
    """
    load = pd.read_csv(load, delimiter=",")
    load = load.rename(columns={"Wärme gesamt (kW)": "heat_demand"})
    load = load.rename(columns={"Zeit (TT-MM hh:mm)": "datetime"})
    load = load.rename(columns={"Kälte gesamt (kW)": "cold_demand"})
    load = load.rename(columns={"Strom gesamt (kW)": "electricity_demand"})

    # change format of datetime col to yyyy-mm-dd hh:mm:ss
    load["datetime"] = pd.to_datetime(load["datetime"], format="%d-%m %H:%M")
    load["datetime"] = load["datetime"].apply(lambda x: x.replace(year=year))
    load = load.set_index(load["datetime"])
    load = load.drop(["datetime"], axis=1)

    load["heat_demand"] = load["heat_demand"] / 1000

    return load


if __name__ == "__main__":
    in_path1 = sys.argv[1]  # path to weather data
    in_path2 = sys.argv[2]  # path to csv with b3 scalars
    out_path1 = sys.argv[3]
    out_path2 = sys.argv[4]

    logger = config.add_snake_logger("prepare_heat_demand")

    CARRIERS = ["heat_central", "heat_decentral"]

    # Read state heat demands of ghd and hh sectors
    sc = dp.load_b3_scalars(in_path2)

    # filter for heat demand data
    sc_filtered = dp.filter_df(sc, "type", "load")

    sc_filtered = dp.filter_df(sc_filtered, "carrier", CARRIERS)

    # get regions from data
    regions = sc_filtered.loc[:, "region"].unique()

    scenarios = sc_filtered.loc[:, "scenario_key"].unique()

    # Create empty data frame for results / output
    total_heat_load = pd.DataFrame(columns=dp.HEADER_B3_TS)

    # create empty data frame for yearly demands
    heat_load_consumer_total = pd.DataFrame(
        index=pd.date_range(datetime.datetime(2050, 1, 1, 0), periods=8760, freq="h")
    )

    for region, scenario in itertools.product(regions, scenarios):
        demand_file_names = find_regional_files(in_path1, region)

        for demand_file_name, carrier in itertools.product(demand_file_names, CARRIERS):
            # Read year from weather file name
            year = get_year(demand_file_name)

            # Get heat demand in region and scenario
            yearly_demands, sc_demand_unit = get_heat_demand(
                sc, scenario, carrier, region
            )

            # Get sector name from file
            sector = demand_file_name.split("_", 1)[0]

            heat_load_ts_info = {
                "region": region,
                "scenario_key": scenario,
                "var_unit": sc_demand_unit,
            }

            # Rename col names of load data
            heat_load = prepare_heat_load_data(
                os.path.join(in_path1, demand_file_name), year
            )

            # Calculate heat load profile for consumer and carrier
            heat_load_consumer = calculate_heat_load(
                sector,
                carrier,
                heat_load,
                yearly_demands,
            )

            if heat_load_consumer.empty:
                continue

            heat_load_consumer = heat_load_consumer.reindex(
                heat_load_consumer_total.index
            )

            for col in heat_load_consumer.columns:
                heat_load_consumer_total[col] = (
                    heat_load_consumer_total.get(col, 0) + heat_load_consumer[col]
                )

        frames = []

        # Sum up and format the central heat demand
        central_cols = [
            c for c in heat_load_consumer_total if c.endswith("_heat_central")
        ]
        if central_cols:
            frames.append(
                dp.prepare_b3_timeseries(
                    heat_load_consumer_total[central_cols]
                    .sum(axis=1)
                    .to_frame("heat_central-demand-profile"),
                    **heat_load_ts_info,
                )
            )

        # Sum up and format the decentral heat demand (sfh + mfh)
        decentral_cols = [
            c for c in heat_load_consumer_total if c.endswith("_heat_decentral")
        ]
        if decentral_cols:
            frames.append(
                dp.prepare_b3_timeseries(
                    heat_load_consumer_total[decentral_cols]
                    .sum(axis=1)
                    .to_frame("heat_decentral-demand-profile"),
                    **heat_load_ts_info,
                )
            )

        total_heat_load = pd.concat([total_heat_load, *frames], ignore_index=True)

    # Aggregate heat demand for different sectors
    demand_per_sector = dp.filter_df(
        sc,
        "tech",
        ["demand_hh", "demand_ghd", "demand_dc", "demand_lab"],
    )
    aggregated_demands = dp.aggregate_scalars(
        demand_per_sector,
        "tech",
        {
            "var_value": sum,
            "var_unit": dp.aggregate_units,
            "source": dp.aggregate_units,
        },
    )
    aggregated_demands.loc[:, "tech"] = "demand"

    aggregated_demands.loc[:, "name"] = aggregated_demands.apply(
        lambda x: "-".join([x["region"], x["carrier"], x["tech"]]), 1
    )

    dp.save_df(aggregated_demands, out_path1)

    # Rearrange stacked time series
    head_load = dp.format_header(
        df=total_heat_load,
        header=dp.HEADER_B3_TS,
        index_name=config.settings.general.ts_index_name,
    )
    dp.save_df(head_load, out_path2)
