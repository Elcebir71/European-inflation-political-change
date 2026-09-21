# European Inflation & Political Change

Data-driven analysis of inflation, migration pressure, macroeconomic conditions, and government changes across European countries.

## Research question

> **To what extent are the 2021–2023 inflation shock and increased migration pressure associated with subsequent political changes in European countries?**

This project studies statistical associations between economic and migration-related indicators and a binary government-change outcome. The analysis does **not** claim that inflation or migration causes governments to change.

## Project scope

- 63 election observations
- 28 European countries
- 31 observations with a government change
- Election data from ParlGov
- European inflation, unemployment, GDP and migration data from Eurostat
- UK GDP data from the Office for National Statistics (ONS)
- UK 2024 migration data uses an explicitly documented Home Office source bridge
- Logistic regression models implemented with Python and statsmodels
- .NET 8 Minimal API for serving model and data results
- Docker support
- GitHub Actions CI/CD configuration

## Data pipeline

The Python preparation script:

`data_prep_v14_english.py`

collects and prepares the source data and produces:

- `panel_dataset.csv` — election-level analytical panel
- `inflation_series.csv` — monthly inflation series
- `models.json` — fitted logistic-regression model results

The visualization script:

`visualize_results_v2.py`

produces the project charts in the `charts/` directory.

## Variables

### Outcome

`govt_change`

Binary indicator representing a government change under the project's operational definition.

The UK 2024 election is explicitly handled as a government change following the Conservative-to-Labour change after the 4 July 2024 election.

### Economic variables

- `inflation_12m_avg` — 12-month average annual HICP inflation
- `unemployment_rate` — 12-month average unemployment rate
- `gdp_growth` — latest available GDP growth observation before the election

GDP is selected using the latest observation available on or before the election month to avoid using post-election information.

### Migration variables

- `asylum_per_100k` — asylum applications per 100,000 population
- `ukraine_tp_per_100k` — Ukrainians under temporary protection per 100,000 population
- `migration_pressure_index` — standardized composite of the asylum and temporary-protection measures

The migration-pressure index should not be interpreted as total immigration. It combines a 12-month asylum flow measure with a temporary-protection stock measure.

## Models

Four logistic-regression specifications are estimated:

### V1 — Inflation

`govt_change ~ inflation_12m_avg`

### V2 — Macro controls

`govt_change ~ inflation_12m_avg + unemployment_rate + gdp_growth`

### V3 — Migration components

`govt_change ~ inflation_12m_avg + asylum_per_100k + ukraine_tp_per_100k + unemployment_rate + gdp_growth`

### V4 — Migration-pressure index

`govt_change ~ inflation_12m_avg + migration_pressure_index + unemployment_rate + gdp_growth`

## Final model results

All four models use the complete dataset of 63 election observations.

| Model | N | Government changes | AIC | Pseudo-R² |
|---|---:|---:|---:|---:|
| V1 | 63 | 31 | 91.32 | 0.000 |
| V2 | 63 | 31 | 94.40 | 0.011 |
| V3 | 63 | 31 | 98.27 | 0.012 |
| V4 | 63 | 31 | 96.32 | 0.011 |

### Main estimates

| Model | Variable | Odds ratio | 95% CI | p-value |
|---|---|---:|---|---:|
| V1 | Inflation | 0.9964 | 0.8780–1.1307 | 0.9553 |
| V2 | Inflation | 1.0076 | 0.8801–1.1536 | 0.9129 |
| V2 | Unemployment | 1.0196 | 0.9146–1.1367 | 0.7262 |
| V2 | GDP growth | 1.1295 | 0.8474–1.5055 | 0.4061 |
| V3 | Inflation | 1.0546 | 0.9726–1.1422 | 0.7267 |
| V3 | Asylum | 0.9998 | 0.9967–1.0029 | 0.8863 |
| V3 | Ukraine temporary protection | 1.0004 | 0.9974–1.0039 | 0.7446 |
| V4 | Inflation | 1.0256 | 0.8547–1.2308 | 0.7855 |
| V4 | Migration-pressure index | 0.8772 | 0.3567–1.5750 | 0.7755 |

## Interpretation

Across the 63 election observations in 28 European countries, the fitted logistic-regression models did not detect statistically significant associations between inflation, migration-pressure measures, and the occurrence of government change.

The estimates have relatively wide confidence intervals. Therefore, these results should be interpreted as evidence of limited statistical detectability in this sample, **not** as evidence that inflation, migration, unemployment, or GDP growth have no effect on political outcomes.

The models estimate **associations rather than causal effects**.

The relatively small number of observations and government-change events also limits statistical power and increases uncertainty around the estimates.

## API

The project includes a .NET 8 Minimal API.

Available endpoints include:

- `GET /api/health`
- `GET /api/models`
- `GET /api/inflation/{countryCode}`
- `GET /api/risk/{countryCode}`

The API's probability endpoint should be interpreted as:

> **Estimated probability under the fitted model**

It is not a political prediction or a causal estimate.

## Running the Python pipeline

Create and activate a virtual environment, install the required Python packages, and run:

```bash
python data_prep_v14_english.py
```

Then generate the charts:

```bash
python visualize_results_v2.py
```

## Running the API

Build and run the .NET application:

```bash
dotnet run
```

The API reads the generated analytical files.

## Docker

The repository includes:

- `Dockerfile`
- `docker-compose.yml`
- `dockerignore`

The generated data files can be mounted into the API container as read-only data.

## CI/CD

GitHub Actions configuration is included in:

`ci-cd.yml`

The workflow is designed to:

1. Build the .NET API
2. Check for placeholder model coefficients
3. Build and publish the Docker image
4. Deploy the application to Azure Container Apps when the required GitHub secrets are configured

## Data sources

- ParlGov — election and cabinet data
- Eurostat — HICP inflation, unemployment, asylum applications, temporary protection and GDP
- UK Office for National Statistics — UK GDP
- UK Home Office — UK asylum data used for the 2024 source bridge

## Limitations

- This is an observational cross-country analysis.
- Statistical association does not establish causation.
- The sample contains only 63 election observations.
- The number of government-change events is 31.
- V3 and V4 include several predictors relative to the sample size.
- The migration-pressure index combines flow and stock measures and is therefore an analytical composite rather than a direct measure of total migration.
- Historical macroeconomic data can be revised by statistical agencies.
- UK and EU statistical definitions are not perfectly identical for every variable.
- The analysis should not be interpreted as a forecasting system for elections or government changes.

## Technology stack

- Python
- Pandas
- NumPy
- Statsmodels
- Eurostat
- ONS API
- ParlGov
- .NET 8
- C#
- Docker
- GitHub Actions
- Azure Container Apps
