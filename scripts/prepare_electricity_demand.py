# coding: utf-8
r"""
Inputs
-------
opsd_ts_data : str
    raw opsd timeseries data including electricity load as .csv.
output_file : str
    ``results/_resources/ts_load_electricity.csv``: path of output file with prepared
    timeseries data as .csv.

Outputs
---------
pandas.DataFrame
    with normalized load data of 50Hertz region in Germany from the years 2015, 2016, 2017, 2018
    and 2019. The data is normalized with the total electricity demand of the corresponding year.

Description Todo:Change description
-------------
The corresponding snakemake rule of the preparation of the electricity demand profile
downloads the 60 min timeseries data from OPSD and keeps it locally.
The script takes this data and filters for the load data of the 50Hertz region in Germany.
The load data is normalized with the total electricity demand of the corresponding year and put
into the timeseries template format. The years 2015 to 2019 (including) are available.
Note: the electricity demand profile for electric vehicle charging is prepared in
`prepare_vehicle_charging_demand.py`.

"""

import sys
import os
import datetime
import itertools

import pandas as pd
import oemof_b3.tools.data_processing as dp

from oemof_b3.config import config
from scripts.prepare_heat_demand import (
    get_year,
    find_regional_files,
    get_shares_building_distribution,
)


def prepare_electricity_load_data(load, year):
    """
    This function reads the load data, changes the format of the datetime column to
    yyyy-mm-dd hh:mm:ss, and sets the datetime column as index and converts the load from kW to MW.

    Parameters
    ----------
    load : DataFrame
        Dataframe electricity load data
    year : str
        Year e.g. "2050"

    Returns
    -------
    load : DataFrame
        Dataframe with renamed header and datetime column as index, load in MW
    """
    load = pd.read_csv(load, delimiter=",")
    load = load.rename(columns={"Zeit (TT-MM hh:mm)": "datetime"})
    load = load.rename(columns={"Strom gesamt (kW)": "electricity_demand"})

    # change format of datetime col to yyyy-mm-dd hh:mm:ss
    load["datetime"] = pd.to_datetime(load["datetime"], format="%d-%m %H:%M")
    load["datetime"] = load["datetime"].apply(lambda x: x.replace(year=year))
    load = load.set_index(load["datetime"])
    load = load.drop(["datetime"], axis=1)

    # convert from kW to MW
    load["electricity_demand"] = load["electricity_demand"] / 1000

    return load


def get_electricity_demand(scalars, scenario, carrier, region):
    """
    This function returns the electricity demands together with their unit of a given region and a
    given scenario.

    Parameters
    ----------
    scalars : DataFrame
        Dataframe with scalars
    scenario : str
        Scenario e.g. "2040-el_eff"
    carrier : str
         Name of carrier (eg.: electricity)
    region : str
        Region (eg. Adlershof

    Returns
    -------
    demands : DataFrame
        Dataframe with total yearly demand of electricity demand for a region.
    demand_unit : str
        Unit of total demands (eg. GWh)

    """
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
            f"Please make sure units match in {scalars}."
        )

    demand_unit = list(set(sc_filtered["var_unit"]))
    demands[carrier] = sc_filtered["var_value"].values

    return demands, demand_unit


def calc_electricity_load(electricity_load, yearly_demands, sector, carrier):
    """
    This function calculates the electricity load by multiplying
    the load profile with the share of the sector in the building distribution and the total
    yearly demand of the sector.

    Parameters
    ----------
    load_data : pd.DataFrame
        DataFrame with load profile data

    shares : dict[str, float]
        Mapping from building type ('sfh', 'mfh', 'lab', 'uni', 'office', 'ghd')
        to its relative share in the total building distribution.
    yearly_demands : dict[str, float]
        Mapping from sector name to total yearly demand of the sector in the region and scenario.
    sector : str
        Sector name (eg. 'sfh', 'mfh', 'lab', 'uni
        'office', 'ghd')

    Returns
    -------
    electricity_load : pd.DataFrame
        DataFrame with electricity load for each sector and carrier.
    """
    # calculate electricity load profile of year
    electricity_load_sector = pd.DataFrame(
        index=pd.date_range(
            datetime.datetime(year, 1, 1, 0), periods=len(electricity_load), freq="h"
        )
    )

    electricity_load_sector[sector + "_" + carrier] = (
        electricity_load["electricity_demand"] * yearly_demands[carrier].values
    )

    return electricity_load_sector


if __name__ == "__main__":
    electricity_ts_data = sys.argv[1]
    scalars = sys.argv[2]
    output_file = sys.argv[3]

    # initialize data frame
    time_series_df = pd.DataFrame()

    # Read state demand of all sectors
    sc = dp.load_b3_scalars(scalars)

    CARRIERS = ["electricity"]

    # filter for electricity data
    sc_filtered = dp.filter_df(sc, "type", "load")

    sc_filtered = dp.filter_df(sc_filtered, "carrier", CARRIERS)

    sc_filtered = dp.filter_df(sc_filtered, "tech", "demand")

    # get regions from data
    regions = sc_filtered.loc[:, "region"].unique()

    scenarios = sc_filtered.loc[:, "scenario_key"].unique()

    # create empty data frame for results / output
    ex_df = pd.DataFrame()
    total_electricity_load = pd.DataFrame(columns=dp.HEADER_B3_TS)

    ts_data = pd.DataFrame(
        index=pd.date_range(datetime.datetime(2050, 1, 1, 0), periods=8760, freq="h")
    )

    # prepare time series for each year and region
    for region, scenario in itertools.product(regions, scenarios):
        demand_file_names = find_regional_files(electricity_ts_data, region)

        for demand_file_name, carrier in itertools.product(demand_file_names, CARRIERS):
            # read year from weather file name
            year = get_year(demand_file_name)

            # get heat demand in region and scenario
            yearly_demands, sc_demand_unit = get_electricity_demand(
                sc_filtered, scenario, carrier, region
            )

            # get sector name from file
            sector = demand_file_name.split("_", 1)[0]

            electricity_load_ts_info = {
                "region": region,
                "scenario_key": scenario,
                "var_unit": sc_demand_unit,
            }

            # rename col names of load data
            electricity_load_data = prepare_electricity_load_data(
                os.path.join(electricity_ts_data, demand_file_name), year
            )

            # calculate the electricity load for the sector
            electricity_load = calc_electricity_load(
                electricity_load_data, yearly_demands, sector, carrier
            )

            ex_df[sector + "_" + carrier] = (
                electricity_load.get("electricity_demand", 0) + electricity_load
            )
        # sum up all sectors to get total electricity demand
        ts_data["electricity-demand-profile"] = ex_df.sum(axis=1)

        frames = []
        frames.append(
            dp.prepare_b3_timeseries(
                ts_data[["electricity-demand-profile"]],
                **electricity_load_ts_info,
            )
        )

        total_electricity_load = pd.concat(
            [total_electricity_load, *frames], ignore_index=True
        )

        # set index
        total_electricity_load.reset_index(drop=True, inplace=True)
        total_electricity_load.index.name = config.settings.general.ts_index_name

        # create output directory in case it does not exist, yet and save data to `output_file`
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    dp.save_df(total_electricity_load, output_file)
