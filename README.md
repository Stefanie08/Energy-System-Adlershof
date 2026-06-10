# Energy System Adlershof oemof-AD based on oemof-B3

This repo models the energy system of Adlershof in Berlin. It represents the sectors
electricity, central and decentral heat. The model is a single-node model of the Adlershof district.

<img src="docs/_img/model_structure.png" width="900"/>

The model is a perfect-foresight, cost minimizing linear optimization model that builds upon
[oemof.solph](https://github.com/oemof/oemof-solph),
[oemof.tabular](https://github.com/oemof/oemof-tabular),
and [oemoflex](https://github.com/rl-institut/oemoflex).

There are two scenarios available:
- `2050-100-plus` — 100% renewable energy supply with additional centralized heat supply
- `2050-100-greenfield` — 100% renewable energy supply, greenfield optimization

Both scenarios refer to the target year 2050 with a 100% reduction in CO2 emissions.

## Getting started

### Installation

Currently, oemof-AD needs python 3.8, 3.9 or 3.10 (newer versions may be supported, but installation can take very long).

Additionally, you need to install the python dependency manager [poetry](https://python-poetry.org/).
It is recommended to install poetry system-wide via the command below or
[pipx](https://python-poetry.org/docs/#installing-with-pipx):

    curl -sSL https://install.python-poetry.org | python3 -
    poetry install


**In order to install oemof-B3, proceed with the following steps:**

1. Clone oemof-B3 into local folder:

       git clone git@github.com:rl-institut/oemof-B3.git
2. Enter folder

       cd oemof-B3
3. Create virtual environment using conda:

       conda env create -f environment.yml
4. Activate environment:

       conda activate oemof-B3
5. Install oemof-B3 package using poetry, via:

       poetry install

Alternatively, you can create a virtual environment using other approaches, such as `virtualenv`.

To create reports oemof-B3 requires pandoc (version > 2). Pandoc is included in conda environment config (environment.yml). 
If environment is build otherwise, pandoc must be installed manually. It can be installed following instructions from [Pandoc Installation](https://pandoc.org/installing.html).

For the optimization, oemof-B3 needs a solver. Check out the [oemof.solph](https://oemof-solph.readthedocs.io/en/latest/readme.html#installing-a-solver) documentation for installation notes.

To test if everything works, you can run the [examples](https://oemof-b3.readthedocs.io/en/latest/examples.html).

For developers: Please activate pre-commit hooks (via `pre-commit install`) in order to follow our coding styles.

### How to run the model

To run a single scenario, execute:

    snakemake -j<NUMBER_OF_CPU_CORES> results/<scenario_name>/postprocessed

whereby `scenario_name` corresponds to the name of the YAML file in the `scenarios` directory
(e.g. `2050-100-plus`).

To force re-run a specific rule for a scenario:

    snakemake -j<NUMBER_OF_CPU_CORES> results/<scenario_name>/postprocessed --forcerun <rule_name>

For example, to force re-run the postprocessing step:

    snakemake -j1 results/2050-100-plus/postprocessed --forcerun postprocess

> **Note:** The debug mode is activated by default. This will execute only three time steps of
> the optimization. To turn it off, set `debug` to `false` in `oemof_b3/config/settings.yaml`.

> **Reproducing results:** The raw input data is not publicly available for download.
> To reproduce the results, the adapted raw data must be provided in the `raw` directory.
> Additionally, after the preprocessing step, the `amount` of the `heat_central` demand
> must be set to `1` manually in the scalar input data. This is due to a known issue in
> the preprocessing script.

### Documentation

Find the documentation [here](https://oemof-b3.readthedocs.io/).

## Contributing

Feedback is welcome. If you notice a bug, please open an 
[issue](https://github.com/rl-institut/oemof-B3/issues). 

### Build the docs locally

To build the docs locally, you have to install related dependencies via

    poetry install -E docs

Afterwards, navigate into the docs directory with
    
    cd docs/
    
and run

    make html

The output will then be located in `docs/_build/html` and can be opened with your favorite browser
