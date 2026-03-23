# coding: utf-8
r"""
Inputs
-------
in_path1 : str
    ``raw/scalars/demands.csv``: path of scalar data as .csv
in_path2 : str
    ``raw/weatherdata``: path of input directory with weather data
in_path3 : str
    path to river temperature timeseries directory
out_path : str
    ``results/_resources/ts_heatpump.csv``: path of output file
logfile : str
    ``results/_resources/ts_heatpump.log``: path to logfile

Outputs
---------
pandas.DataFrame
    with timeseries of COPs of air-source, river-source, and ground-source heat pumps

Description
-------------
The script calculates COP timeseries for three heat pump types:
    - Air-water HP (small scale, decentralized)
    - River-water HP (uses measured river temperature timeseries)
    - Ground-source HP (uses constant temperature for mitteltiefe Geothermie)

Quality grades per oemof-B3 settings.yaml:
    - Air source:    0.40
    - Water source:  0.50
    - Ground source: 0.55

Sink temperature is assumed to be 50°C for air and ground source HPs,
and 88°C for the river HP (central district heating).
"""

import datetime
import os
import sys
import pandas as pd
import numpy as np
from oemof_b3.config.config import load_yaml
from oemof_b3 import model
import oemof_b3.tools.data_processing as dp
from oemof_b3.config import config

# Load quality grades for heatpump time series calculation
QG_AIR_SOURCE = config.settings.prepare_cop_timeseries.quality_grade_air_source
QG_GROUND_SOURCE = config.settings.prepare_cop_timeseries.quality_grade_ground_source
QG_WATER_SOURCE = config.settings.prepare_cop_timeseries.quality_grade_water_source

# Constant ground temperature for mitteltiefe Geothermie
# aus https://www.lfu.bayern.de/buerger/doc/uw_20_erdwaerme.pdf
GROUND_TEMP = config.settings.prepare_cop_timeseries.ground_source_temperature

# Sink temperatures
TEMP_HIGH_DECENTRAL = 50  # °C for air + ground source (decentralized)
TEMP_HIGH_CENTRAL = 88  # °C for river HP (district heating / central)

SCENARIO = config.settings.prepare_cop_timeseries.scenario


def find_regional_files(path, region):
    files_region = [file for file in os.listdir(path) if f"_{region}_" in file]
    files_region = sorted(files_region)
    if not files_region:
        raise FileNotFoundError(
            f"No data of region {region} could be found in directory: {path}."
        )
    return files_region


def get_year(file_name):
    years_search_array = np.arange(1990, 2051)
    year_in_file = [y for y in years_search_array if str(y) in file_name]
    if len(year_in_file) == 1:
        return year_in_file[0]
    else:
        raise ValueError(
            f"Your file {file_name} is missing a year or has multiple years in its name."
        )


def calc_cops(temp_high, temp_low, quality_grade):
    """
    Carnot-based COP calculation.

    Parameters
    ----------
    temp_high : list or pd.Series
        Sink temperature in °C
    temp_low : list or pd.Series
        Source temperature in °C
    quality_grade : float
        Scale-down factor from ideal Carnot process

    Returns
    -------
    list of COP values
    """
    if not isinstance(temp_low, (list, pd.Series)):
        raise TypeError("Argument 'temp_low' is not of type list or pd.Series!")
    if not isinstance(temp_high, (list, pd.Series)):
        raise TypeError("Argument 'temp_high' is not of type list or pd.Series!")
    if len(temp_high) != len(temp_low):
        if (len(temp_high) != 1) and (len(temp_low) != 1):
            raise IndexError(
                "Arguments 'temp_low' and 'temp_high' must be same length "
                "or one must have length 1!"
            )

    length = max([len(temp_high), len(temp_low)])
    list_temp_high_K = (
        [temp_high[0] + 273.15] * length
        if len(temp_high) == 1
        else [t + 273.15 for t in temp_high]
    )
    list_temp_low_K = (
        [temp_low[0] + 273.15] * length
        if len(temp_low) == 1
        else [t + 273.15 for t in temp_low]
    )

    cops = [
        quality_grade * t_h / (t_h - t_l)
        for t_h, t_l in zip(list_temp_high_K, list_temp_low_K)
    ]
    return cops


def load_river_temp(path, year):
    """
    Load and preprocess river temperature timeseries for a given year.

    Parameters
    ----------
    path : str
        Path to directory containing river temperature CSV files
    year : int
        Year to load

    Returns
    -------
    pd.Series
        Hourly river temperature in °C indexed by datetime
    """
    # Find the file matching the year
    files = [f for f in os.listdir(path) if str(year) in f and f.endswith(".csv")]
    if not files:
        raise FileNotFoundError(
            f"No river temperature file found for year {year} in {path}."
        )

    filepath = os.path.join(path, files[0])
    data = pd.read_csv(filepath, sep=",", decimal=".", index_col=0)

    return data["water_temperature"]


if __name__ == "__main__":
    in_path1 = sys.argv[1]
    in_path2 = sys.argv[2]
    in_path3 = sys.argv[3]
    out_path = sys.argv[4]

    logger = config.add_snake_logger("prepare_cop_timeseries")

    # Read scalar demand and get regions
    sc = dp.load_b3_scalars(in_path1)
    sc_filtered = dp.filter_df(sc, "carrier", ["heat_decentral", "heat_central"])
    regions = sc_filtered.loc[:, "region"].unique()

    # Get efficiency column names from component_attrs_update.yml
    component_attrs_update = load_yaml(
        os.path.join(model.here, "component_attrs_update.yml")
    )
    eff_col_name_air = component_attrs_update["electricity-heatpump_small"][
        "foreign_keys"
    ]["efficiency"]
    eff_col_name_river = component_attrs_update["electricity-heatpump_river_large"][
        "foreign_keys"
    ]["efficiency"]
    eff_col_name_ground = component_attrs_update["electricity-heatpump_geo_large"][
        "foreign_keys"
    ]["efficiency"]

    # create empty data frame for results / output
    final_cops = pd.DataFrame(columns=dp.HEADER_B3_TS)

    for region in regions:
        weather_file_names = find_regional_files(in_path2, region)

        for weather_file_name in weather_file_names:
            year = get_year(weather_file_name)

            # read weather data
            path_weather_data = os.path.join(in_path2, weather_file_name)
            temperature = pd.read_csv(
                path_weather_data,
                usecols=["temp_air"],
                header=0,
            )

            date_index = pd.date_range(
                datetime.datetime(year, 1, 1, 0),
                periods=len(temperature),
                freq="h",
            )

            cops_ts_info = {
                "region": region,
                "scenario_key": SCENARIO,
                "var_unit": ["-"],
            }

            # prepare air source heatpump time series
            cops_air = pd.DataFrame(index=date_index)
            cops_air[eff_col_name_air] = calc_cops(
                temp_high=[TEMP_HIGH_DECENTRAL],
                temp_low=temperature["temp_air"],
                quality_grade=QG_AIR_SOURCE,
            )
            cops_air = dp.prepare_b3_timeseries(cops_air, **cops_ts_info)
            final_cops = pd.concat(
                [final_cops, cops_air], ignore_index=True, sort=False
            )

            # prepare river heatpump time series
            try:
                river_temp = load_river_temp(in_path3, year)

                # calculate COP
                cop_values = calc_cops(
                    temp_high=[TEMP_HIGH_CENTRAL],
                    temp_low=river_temp,
                    quality_grade=QG_WATER_SOURCE,
                )

                cops_river = pd.DataFrame(index=date_index)
                cops_river[eff_col_name_river] = cop_values

                # set COP to 0 where river temperature is below 8°C (HP is off)
                cops_river.loc[river_temp.values < 8, eff_col_name_river] = 0

                n_off = (river_temp < 8).sum()
                logger.info(
                    f"River Heatpump offline for {n_off} hours ({n_off / 8760 * 100:.1f}%) due to temp < 8°C"
                )

                cops_river = dp.prepare_b3_timeseries(cops_river, **cops_ts_info)
                final_cops = pd.concat(
                    [final_cops, cops_river], ignore_index=True, sort=False
                )

            except FileNotFoundError as e:
                logger.warning(f"River temperature data not found for year {year}: {e}")

            # prepare GSHP time series
            ground_temp_series = pd.Series(GROUND_TEMP, index=date_index)

            cops_ground = pd.DataFrame(index=date_index)
            cops_ground[eff_col_name_ground] = calc_cops(
                temp_high=[TEMP_HIGH_CENTRAL],
                temp_low=ground_temp_series,
                quality_grade=QG_GROUND_SOURCE,
            )
            cops_ground = dp.prepare_b3_timeseries(cops_ground, **cops_ts_info)
            final_cops = pd.concat(
                [final_cops, cops_ground], ignore_index=True, sort=False
            )

    # Rearrange stacked time series
    final_cops = dp.format_header(
        df=final_cops,
        header=dp.HEADER_B3_TS,
        index_name=config.settings.general.ts_index_name,
    )

    dp.save_df(final_cops, out_path)
