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

Description
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
from scripts.prepare_heat_demand import get_year, find_regional_files, get_shares_building_distribution


def prepare_electricity_load_data(load, year):
    """
    This function reads the load data from the given file, changes the format of the datetime column to
    yyyy-mm-dd hh:mm:ss, sets the datetime column as index and converts the load from kW to MW.

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
    load = load.rename(columns={"Zone 1 (kW)": "electricity_demand"})

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


def calc_electricity_load(electricity_load, shares, yearly_demands, sector, carrier):
    """
    This function calculates the electricity load for each sector and carrier by multiplying
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
    # Calculate electricity load profile of year
    electricity_load_sector = pd.DataFrame(
        index=pd.date_range(
            datetime.datetime(year, 1, 1, 0), periods=len(electricity_load), freq="h"
        )
    )

    electricity_load_sector[sector + "_" + carrier] = (
            electricity_load["electricity_demand"]
            * shares[sector]
            * yearly_demands[carrier].values
    )

    return electricity_load_sector


if __name__ == "__main__":
    electricity_ts_data = sys.argv[1]
    scalars = sys.argv[2]
    building_share = sys.argv[3]
    output_file = sys.argv[4]

    # initialize data frame
    time_series_df = pd.DataFrame()

    # download raw time series from OPSD
    ts_raw = pd.read_csv(opsd_ts_data, index_col=0)
    ts_raw.index = pd.to_datetime(ts_raw.index, utc=True)
    # filter for 50hertz actual load
    ts_raw = ts_raw[[config.settings.prepare_electricity_demand.col_select]]

    # prepare time series for each year and region
    for year in config.settings.prepare_electricity_demand.opsd_years:
        for region in config.settings.prepare_electricity_demand.regions:
            # prepare opsd 50hertz actual load time series
            load_ts = prepare_load_profile_time_series(
                ts_raw=ts_raw, year=year, region=region
            )

            # add time series to `time_series_df`
            time_series_df = pd.concat([time_series_df, load_ts], axis=0)

    # set index
    time_series_df.reset_index(drop=True, inplace=True)
    time_series_df.index.name = config.settings.general.ts_index_name

    # create output directory in case it does not exist, yet and save data to `output_file`
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    dp.save_df(time_series_df, output_file)
