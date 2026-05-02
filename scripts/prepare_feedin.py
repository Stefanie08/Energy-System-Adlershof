# coding: utf-8
r"""
Inputs
-------
filename_wind : str
    ``raw/time_series/ninja_wind_country_DE_current_merra-2_nuts-2_corrected.csv``: Path incl. file
    name of wind feed-in time series of renewables ninja
filename_pv : str
    ``raw/time_series/ninja_pv_country_DE_merra-2_nuts-2_corrected.csv``: Path incl. file name of pv
    feed-in time series of renewables ninja
filename_ror : str
    ``raw/time_series/DIW_Hydro_availability.csv``: Path incl. file name of feed-in time series of
    run-of-river power plants
output_file : str
    ``results/_resources/ts_feedin.csv``: Path incl. file name of prepared time series

Outputs
---------
pd.DataFrame
    Prepared feed-in time series of pv, wind and hydropower

Description
-------------
This script prepares wind, pv and run-of-the-river (ror) feed-in time series for the regions Berlin
and Brandenburg. Raw data is read from csv-files from https://www.renewables.ninja/ (wind+pv) and
https://zenodo.org/record/1044463 (ror) and is then formatted to fit the time series template of
oemof-B3 (`schema/timeseries.csv`).

"""

import sys
import pandas as pd
import os
import oemof_b3.tools.data_processing as dp
from oemof_b3.config import config


# Load config settings for pv feedin
CFG = config.settings.prepare_feedin


def prepare_pv_time_series(filename_ts, year, type):
    r"""
    Prepares and formats time series of `type` `pv roof` or 'pv facade' for region 'AD'.

    Parameters
    ----------
    filename_ts : str
        Path including file name to pv time series of GSEE
    year : int
        Year for which time series is extracted from raw data in `filename_ts`
    type : str
        Type of time series like 'solar-pv_roof'; used for column 'var_name' in output

    Returns
    -------
    ts_prepared : pd.DataFrame
        Contains time series in the format of time series template of oemof-B3

    """
    # load roof data
    total_roof_area = CFG.total_roof_area
    ghd_mfh = CFG.ghd_mfh_roof_area
    efh = CFG.efh_roof_area

    # define weights for feedin
    weights = {
        "90": (ghd_mfh / 3 + efh / 4) / total_roof_area,  # east
        "135": (efh / 4) / total_roof_area,  # southeast
        "180": (ghd_mfh / 3) / total_roof_area,  # south
        "225": (efh / 4) / total_roof_area,  # southwest
        "270": (ghd_mfh / 3 + efh / 4) / total_roof_area,  # west
    }

    assert (
        abs(sum(weights.values()) - 1.0) < 1e-9
    ), f"Weights of feedin != 1: {sum(weights.values())}"

    # load raw time series and copy data frame
    ts_raw = pd.read_csv(filename_ts, index_col=0, parse_dates=True)
    time_series = ts_raw.copy()

    # extract one specific `year`
    time_series = time_series[time_series.index.year == year]

    time_series_regions = time_series.loc[:, list(weights.keys())]

    # create empty dataframe for total_feedin
    total_feedin = pd.DataFrame(index=ts_raw.index)

    # multiplies each azimuth column with its weight and sums up to total feedin
    total_feedin[CFG.region] = time_series_regions.mul(weights).sum(axis=1)

    # bring time series to oemof-B3 format with `stack_timeseries()` and `format_header()`
    ts_stacked = dp.stack_timeseries(total_feedin).rename(
        columns={"var_name": "region"}
    )
    ts_prepared = dp.format_header(
        df=ts_stacked,
        header=dp.HEADER_B3_TS,
        index_name=config.settings.general.ts_index_name,
    )

    # add additional information as required by template
    ts_prepared.loc[:, "var_unit"] = config.settings.prepare_feedin.ts_var_unit
    ts_prepared.loc[:, "var_name"] = f"{type}-profile"
    ts_prepared.loc[:, "source"] = config.settings.prepare_feedin.ts_source
    ts_prepared.loc[:, "comment"] = config.settings.prepare_feedin.ts_comment
    ts_prepared.loc[
        :, "scenario_key"
    ] = "ALL"  # The profile is not varied in different scenarios

    return ts_prepared


def prepare_solarthermal_time_series(filename_ts, year, type):
    r"""
    Prepares and formats time series of `type` `pv roof` or 'pv facade' for region 'AD'.

    Parameters
    ----------
    filename_ts : str
        Path including file name to pv time series of GSEE
    year : int
        Year for which time series is extracted from raw data in `filename_ts`
    type : str
        Type of time series like 'solar-pv_roof'; used for column 'var_name' in output

    Returns
    -------
    ts_prepared : pd.DataFrame
        Contains time series in the format of time series template of oemof-B3

    """
    # load roof data
    total_roof_area = CFG.total_roof_area
    ghd_mfh = CFG.ghd_mfh_roof_area
    efh = CFG.efh_roof_area

    # define weights for feedin
    weights = {
        "90": (ghd_mfh / 3 + efh / 4) / total_roof_area,  # east
        "135": (efh / 4) / total_roof_area,  # southeast
        "180": (ghd_mfh / 3) / total_roof_area,  # south
        "225": (efh / 4) / total_roof_area,  # southwest
        "270": (ghd_mfh / 3 + efh / 4) / total_roof_area,  # west
    }

    assert (
        abs(sum(weights.values()) - 1.0) < 1e-9
    ), f"Weights of feedin != 1: {sum(weights.values())}"

    # load raw time series and copy data frame
    ts_raw = pd.read_csv(filename_ts, index_col=0, parse_dates=True)
    time_series = ts_raw.copy()

    # extract one specific `year`
    time_series = time_series[time_series.index.year == year]

    time_series_regions = time_series.loc[:, list(weights.keys())]

    # create empty dataframe for total_feedin
    total_feedin = pd.DataFrame(index=ts_raw.index)

    # multiplies each azimuth column with its weight and sums up to total feedin
    total_feedin[CFG.region] = time_series_regions.mul(weights).sum(axis=1)

    # bring time series to oemof-B3 format with `stack_timeseries()` and `format_header()`
    ts_stacked = dp.stack_timeseries(total_feedin).rename(
        columns={"var_name": "region"}
    )
    ts_prepared = dp.format_header(
        df=ts_stacked,
        header=dp.HEADER_B3_TS,
        index_name=config.settings.general.ts_index_name,
    )

    # add additional information as required by template
    ts_prepared.loc[:, "var_unit"] = config.settings.prepare_feedin.ts_var_unit
    ts_prepared.loc[:, "var_name"] = f"{type}-profile"
    ts_prepared.loc[:, "source"] = config.settings.prepare_feedin.ts_source
    ts_prepared.loc[:, "comment"] = config.settings.prepare_feedin.ts_comment
    ts_prepared.loc[
        :, "scenario_key"
    ] = "ALL"  # The profile is not varied in different scenarios

    return ts_prepared


def prepare_pv_facade_time_series(filename_ts, year, type):
    ts_facade_raw = pd.read_csv(filename_ts, index_col=0, parse_dates=True)

    # extract one specific year and select only pv_facade column
    time_series = ts_facade_raw[ts_facade_raw.index.year == year][["pv_facade"]]

    total_facade_feedin = pd.DataFrame(index=time_series.index)
    total_facade_feedin[CFG.region] = time_series["pv_facade"]

    # bring to oemof-B3 format
    ts_stacked = dp.stack_timeseries(total_facade_feedin).rename(
        columns={"var_name": "region"}
    )
    ts_prepared = dp.format_header(
        df=ts_stacked,
        header=dp.HEADER_B3_TS,
        index_name=config.settings.general.ts_index_name,
    )

    # add additional information as required by template
    ts_prepared.loc[:, "var_unit"] = config.settings.prepare_feedin.ts_var_unit
    ts_prepared.loc[:, "var_name"] = f"{type}-profile"
    ts_prepared.loc[:, "source"] = config.settings.prepare_feedin.ts_source
    ts_prepared.loc[:, "comment"] = config.settings.prepare_feedin.ts_comment
    ts_prepared.loc[
        :, "scenario_key"
    ] = "ALL"  # The profile is not varied in different scenarios

    return ts_prepared


if __name__ == "__main__":
    filename_pv_facade = sys.argv[1]
    filename_pv = sys.argv[2]
    filename_solarthermal = sys.argv[3]
    output_file = sys.argv[4]

    # initialize data frame
    time_series_df = pd.DataFrame()

    # prepare time series for each year
    for year in config.settings.prepare_feedin.years:
        # prepare pv roof time series
        pv_roof_ts = prepare_pv_time_series(
            filename_ts=filename_pv, year=year, type="solar-pv_roof"
        )

        # prepare solarthermal time series with same azimuth distribution as pv roof
        solarthermal_ts = prepare_pv_time_series(
            filename_ts=filename_solarthermal, year=year, type="solar-solarthermal"
        )

        # prepare pv facade time series
        pv_facade_ts = prepare_pv_facade_time_series(
            filename_ts=filename_pv_facade, year=year, type="solar-pv_facade"
        )

        # add time series to `time_series_df`
        time_series_df = pd.concat(
            [time_series_df, pv_roof_ts, pv_facade_ts, solarthermal_ts], axis=0
        )

    # set index
    time_series_df.reset_index(drop=True, inplace=True)
    time_series_df.index.name = config.settings.general.ts_index_name

    # create output directory in case it does not exist, yet and save data to `output_file`
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    dp.save_df(time_series_df, output_file)
