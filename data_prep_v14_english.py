#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_prep_v14_english.py ======================== Post-Brexit Inflation

and Political Change Panel Dataset (V1 + V2 + V3 + V4)

Features:
  - Fetches EU inflation from Eurostat (HICP) and UK inflation from ONS (CPIH).
  - Fetches migration & temporary protection metrics from Eurostat.
  - Fetches unemployment & quarterly GDP growth controls.
  - Dynamically fetches parliamentary election records from ParlGov with a 2024 UK override.
  - Fits V1, V2, V3, and V4 logistic regressions and exports models.json for .NET 8 API.
"""

import io
import json
import time
import warnings
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# COUNTRY CODES & CONSTANTS
# ---------------------------------------------------------------------------
UNITED_KINGDOM_GB = "GB"  # ISO 3166-1 alpha-2 (Primary code in panel)
EUROSTAT_UK_GEO = "UK"  # Eurostat geo code for UK
UKRAINE_UA = "UA"  # Ukraine country code for Temporary Protection

EU27_GEO_CODES = [
    "AT",
    "BE",
    "BG",
    "CY",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
]

WINDOW_MONTHS, MIN_PERIODS = 12, 6

GB_POPULATION_OVERRIDE = {
    2021: 67_000_000,
    2022: 67_100_000,
    2023: 67_300_000,
    2024: 68_300_000,
    2025: 68_900_000,
}

TIME_CANDIDATES = ("TIME_PERIOD", "time", "Time", "period", "TIME")

EUROSTAT_BASE = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{table}"
)


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def find_time_col(df: pd.DataFrame, table: str) -> str:
  for c in TIME_CANDIDATES:
    if c in df.columns:
      return c
  raise RuntimeError(
      f"[{table}] Time column not found. Available columns: {list(df.columns)}"
  )


def fetch_eurostat(table: str, params: dict, retries: int = 3) -> pd.DataFrame:
  """Fetches data from Eurostat dissemination API and returns a tidy DataFrame."""
  params = {"format": "JSON", "lang": "EN", **params}
  url = EUROSTAT_BASE.format(table=table)
  js = None
  for attempt in range(retries):
    try:
      r = requests.get(url, params=params, timeout=60)
      r.raise_for_status()
      js = r.json()
      break
    except Exception:
      if attempt == retries - 1:
        raise
      time.sleep(2**attempt)

  values = js.get("value") or {}
  if not values:
    raise RuntimeError(
        f"[{table}] Empty response (filters may not match): {params}. "
        f"Dimensions: {list(js.get('id', []))}"
    )

  dims = list(js["id"])
  sizes = js["size"]
  cats = {
      d: [
          key
          for key, _ in sorted(
              js["dimension"][d]["category"]["index"].items(),
              key=lambda item: item[1],
          )
      ]
      for d in dims
  }

  def unravel(idx: int) -> tuple:
    out, rem = [], idx
    for s in reversed(sizes):
      out.append(rem % s)
      rem //= s
    return tuple(reversed(out))

  rows = []
  for k, v in values.items():
    i = unravel(int(k))
    rows.append({d: cats[d][i[n]] for n, d in enumerate(dims)} | {"value": v})
  return pd.DataFrame(rows)


def to_monthly(df: pd.DataFrame, table: str = "?") -> pd.DataFrame:
  col = find_time_col(df, table)
  df = df.rename(columns={col: "month"})
  df["month"] = pd.PeriodIndex(
      df["month"].astype(str).str.replace("M", "-"), freq="M"
  )
  return df


def to_year(df: pd.DataFrame, table: str = "?") -> pd.DataFrame:
  col = find_time_col(df, table)
  df = df.rename(columns={col: "year"})
  df["year"] = df["year"].astype(str).str[:4].astype(int)
  return df


def to_quarter(df: pd.DataFrame, table: str = "?") -> pd.DataFrame:
  col = find_time_col(df, table)
  df = df.rename(columns={col: "quarter"})
  df["month"] = pd.PeriodIndex(
      df["quarter"].astype(str).str.replace("-Q", "Q", regex=False), freq="Q"
  ).asfreq("M")
  return df


def normalize_geo(df: pd.DataFrame) -> pd.DataFrame:
  return df.replace({"country_code": {EUROSTAT_UK_GEO: UNITED_KINGDOM_GB}})


# ---------------------------------------------------------------------------
# INFLATION DATA
# ---------------------------------------------------------------------------
def get_eu_inflation() -> pd.DataFrame:
    """Fetches monthly HICP annual inflation from Eurostat."""

    eurostat_geo_codes = [
        "EL" if geo == "GR" else geo
        for geo in EU27_GEO_CODES
    ]

    # Make sure Greece is explicitly included.
    if "EL" not in eurostat_geo_codes:
        eurostat_geo_codes.append("EL")

    df = fetch_eurostat(
        "prc_hicp_manr",
        {
            "geo": eurostat_geo_codes,
            "coicop": "CP00",
            "unit": "RCH_A",
        },
    )

    df = to_monthly(df, "prc_hicp_manr")

    df = df.rename(
        columns={
            "geo": "country_code",
            "value": "inflation_yoy",
        }
    )

    # Eurostat uses EL for Greece; the project uses GR.
    df["country_code"] = df["country_code"].replace(
        {"EL": "GR"}
    )

    return df[
        ["country_code", "month", "inflation_yoy"]
    ]


def get_uk_inflation_ons() -> pd.DataFrame:
  """Fetches UK CPIH 12-month rate directly from ONS v1 data endpoint."""
  url = "https://api.beta.ons.gov.uk/v1/data"
  params = {"uri": "/economy/inflationandpriceindices/timeseries/l55o/mm23"}
  r = requests.get(url, params=params, timeout=60)
  r.raise_for_status()
  payload = r.json()

  months = payload.get("months", [])
  if not months:
    raise RuntimeError(
        "[ONS L55O] Empty response from the ONS v1 data endpoint."
    )

  dates = pd.to_datetime(
      [m.get("date") for m in months], format="%Y %b", errors="coerce"
  )
  df = pd.DataFrame({
      "month": dates.to_period("M"),
      "inflation_yoy": pd.to_numeric(
          [m.get("value") for m in months], errors="coerce"
      ),
  }).dropna(subset=["month"])

  df["country_code"] = UNITED_KINGDOM_GB
  return df[["country_code", "month", "inflation_yoy"]]


def get_inflation() -> pd.DataFrame:
  df = pd.concat(
      [get_eu_inflation(), get_uk_inflation_ons()], ignore_index=True
  )
  dup = df.duplicated(subset=["country_code", "month"]).sum()
  assert dup == 0, f"Duplicate UK inflation rows: {dup}"
  return df


# ---------------------------------------------------------------------------
# MIGRATION DATA
# ---------------------------------------------------------------------------
def get_asylum() -> pd.DataFrame:
    """Fetch total monthly asylum applicants per country from Eurostat.

    Eurostat uses EL for Greece and UK for the United Kingdom.
    The project internally uses GR and GB.
    """
    frames = []
    # Fetch earlier asylum data so that 12-month election windows
    # are complete for elections held early in 2015.
    start_period = pd.Period("2014-01", freq="M")
    end_period = pd.Period("2026-06", freq="M")

    asylum_geo_codes = EU27_GEO_CODES + [UNITED_KINGDOM_GB]

    for geo in asylum_geo_codes:
        if geo == "GR":
            eurostat_geo = "EL"
        elif geo == UNITED_KINGDOM_GB:
            eurostat_geo = "UK"
        else:
            eurostat_geo = geo

        try:
            df = fetch_eurostat(
                "migr_asyappctzm",
                {
                    "geo": eurostat_geo,
                    "unit": "PER",
                    "citizen": "EXT_EU27_2020",
                    "sex": "T",
                    "applicant": "TOTAL",
                    "age": "TOTAL",
                },
            )

            df = to_monthly(df, "migr_asyappctzm")
            df["value"] = pd.to_numeric(
                df["value"],
                errors="coerce",
            )

            df = df[
                (df["month"] >= start_period)
                & (df["month"] <= end_period)
            ]

            if df.empty:
                print(
                    f"Warning: no asylum data for "
                    f"{geo} ({eurostat_geo})"
                )
                continue

            # Keep project-internal country code.
            df["geo"] = geo

            frames.append(
                df[
                    [
                        "geo",
                        "month",
                        "value",
                    ]
                ]
            )

            if geo == UNITED_KINGDOM_GB:
                print(
                    f"✓ UK asylum data added: {len(df)} monthly rows"
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch asylum data for "
                f"{geo} ({eurostat_geo})"
            ) from e

    if not frames:
        raise RuntimeError(
            "Failed to fetch asylum applicant data."
        )

    all_df = pd.concat(
        frames,
        ignore_index=True,
    )

    duplicates = all_df.duplicated(
        subset=["geo", "month"]
    ).sum()

    if duplicates:
        raise RuntimeError(
            f"Duplicate asylum observations detected: {duplicates}"
        )

    return (
        all_df
        .rename(
            columns={
                "geo": "country_code",
                "value": "asylum_applicants",
            }
        )
        [
            [
                "country_code",
                "month",
                "asylum_applicants",
            ]
        ]
    )
def get_temporary_protection() -> pd.DataFrame:
  # Use the end-of-month beneficiary stock, not monthly grants.
  # Eurostat identifies this series as migr_asytpsm.
  df = fetch_eurostat(
      "migr_asytpsm",
      {
          "geo": EU27_GEO_CODES,
          "unit": "PER",
          "citizen": UKRAINE_UA,
          "sex": "T",
          "age": "TOTAL",
      },
  )
  df = to_monthly(df, "migr_asytpsm")
  return df.rename(columns={"geo": "country_code", "value": "tp_ukrainians"})[
      ["country_code", "month", "tp_ukrainians"]
  ]


def get_population() -> pd.DataFrame:
    geo_codes = [
    "EL" if geo == "GR" else geo
    for geo in EU27_GEO_CODES
    ]
    df = fetch_eurostat("tps00001", {"geo": geo_codes + [EUROSTAT_UK_GEO]})
    df = to_year(df, "tps00001")
    df = df.rename(columns={"geo": "country_code", "value": "population"})
    # tps00001 is returned as a number of persons by the current Eurostat API.
    # Do not multiply by 1,000 here.
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    df = normalize_geo(df)
    # Eurostat uses EL for Greece; the project uses GR internally.
    df["country_code"] = df["country_code"].replace({"EL": "GR"})
    
    for y, pop in GB_POPULATION_OVERRIDE.items():
        mask = (df["country_code"] == UNITED_KINGDOM_GB) & (df["year"] == y)
        if mask.any():
            df.loc[mask, "population"] = pop
        else:
            df = pd.concat(
            [
                df,
                pd.DataFrame([{
                    "country_code": UNITED_KINGDOM_GB,
                    "year": y,
                    "population": pop,
                }]),
            ],
            ignore_index=True,
            )
    return df[["country_code", "year", "population"]]


# ---------------------------------------------------------------------------
# CONTROL VARIABLES
# ---------------------------------------------------------------------------
def get_uk_unemployment_ons() -> pd.DataFrame:
  """Fetches UK seasonally adjusted unemployment rate from ONS v1 API."""
  url = "https://api.beta.ons.gov.uk/v1/data"
  params = {
      "uri": (
          "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms"
      )
  }
  r = requests.get(url, params=params, timeout=60)
  r.raise_for_status()
  payload = r.json()

  months = payload.get("months", [])
  if not months:
    raise RuntimeError(
        "[ONS MGSX] Empty response from the ONS v1 data endpoint."
    )

  dates = pd.to_datetime(
      [m.get("date") for m in months], format="%Y %b", errors="coerce"
  )
  df = pd.DataFrame({
      "month": dates.to_period("M"),
      "unemployment_rate": pd.to_numeric(
          [m.get("value") for m in months], errors="coerce"
      ),
  }).dropna(subset=["month", "unemployment_rate"])

  df["country_code"] = UNITED_KINGDOM_GB
  return df[["country_code", "month", "unemployment_rate"]]


def get_unemployment() -> pd.DataFrame:
    """Fetches EU unemployment from Eurostat and UK unemployment from ONS."""
    eurostat_geo_codes = [
        "EL" if geo == "GR" else geo
        for geo in EU27_GEO_CODES
    ]
    df = fetch_eurostat(
        "une_rt_m",
        {
            "geo": eurostat_geo_codes,
            "sex": "T",
            "s_adj": "SA",
            "unit": "PC_ACT",
        },
    )

    if "age" in df.columns:
        df = df[df["age"].isin(["Y15-74", "TOTAL", "Y_GE15"])]

    df = to_monthly(df, "une_rt_m")
    df = df.rename(columns={"geo": "country_code", "value": "unemployment_rate"})
    df["country_code"] = df["country_code"].replace({"EL": "GR"})
    df = df.drop_duplicates(subset=["country_code", "month"])
    

    uk = get_uk_unemployment_ons()
    df = pd.concat([df, uk], ignore_index=True)

    dup = df.duplicated(subset=["country_code", "month"]).sum()
    if dup:
        raise RuntimeError(f"Duplicate unemployment observations detected: {dup}")

    return df
def get_gdp_growth() -> pd.DataFrame:
    """Fetches quarterly real GDP growth from Eurostat and ONS."""

    # Eurostat GDP: real GDP quarter-on-quarter growth
    df_eu = fetch_eurostat(
        "namq_10_gdp",
        {
            "geo": [
                "EL" if geo == "GR" else geo
                for geo in EU27_GEO_CODES
            ],
            "na_item": "B1GQ",
            "unit": "CLV_PCH_PRE",
        },
    )

    df_eu = to_quarter(df_eu, "namq_10_gdp")

    df_eu = df_eu.rename(
        columns={
            "geo": "country_code",
            "value": "gdp_growth",
        }
    )

    df_eu["country_code"] = df_eu["country_code"].replace(
        {"EL": "GR"}
    )

    df_eu = df_eu[
        ["country_code", "month", "gdp_growth"]
    ]

    # UK GDP from ONS.
    uri = "/economy/grossdomesticproductgdp/timeseries/ihyq/qna"

    response = requests.get(
        f"https://api.beta.ons.gov.uk/v1/data?uri={uri}",
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    uk_rows = []

    for item in payload["quarters"]:
        date = item.get("date")
        value = item.get("value")

        if not date or value in (None, ""):
            continue

        year, quarter = date.split()

        quarter_month = {
            "Q1": 3,
            "Q2": 6,
            "Q3": 9,
            "Q4": 12,
        }[quarter]

        uk_rows.append(
            {
                "country_code": "GB",
                "month": pd.Timestamp(
                    int(year),
                    quarter_month,
                    1,
                ),
                "gdp_growth": float(value),
            }
        )

    df_uk = pd.DataFrame(uk_rows)

    return pd.concat(
        [df_eu, df_uk],
        ignore_index=True,
    )
def test_uk_gdp_ons() -> pd.DataFrame:
    """Test the official ONS UK quarterly GDP growth series."""

    url = "https://api.beta.ons.gov.uk/v1/data"
    params = {
        "uri": "/economy/grossdomesticproductgdp/timeseries/ihyq/qna"
    }

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    payload = response.json()

    return payload

# ---------------------------------------------------------------------------
# ELECTION DATA
# ---------------------------------------------------------------------------
NAME2ISO = {
    "United Kingdom": UNITED_KINGDOM_GB,
    "Austria": "AT",
    "Belgium": "BE",
    "Bulgaria": "BG",
    "Cyprus": "CY",
    "Czech Republic": "CZ",
    "Germany": "DE",
    "Denmark": "DK",
    "Estonia": "EE",
    "Spain": "ES",
    "Finland": "FI",
    "France": "FR",
    "Greece": "GR",
    "Croatia": "HR",
    "Hungary": "HU",
    "Ireland": "IE",
    "Italy": "IT",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Latvia": "LV",
    "Malta": "MT",
    "Netherlands": "NL",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Sweden": "SE",
    "Slovenia": "SI",
    "Slovakia": "SK",
}

import os
import requests
import pandas as pd

def get_elections() -> pd.DataFrame:
    """
    Loads ParlGov election and cabinet data and derives one observation per
    parliamentary election.

    govt_change = 1 when BOTH the prime minister's party AND the prime
    minister (name) differ between the cabinet in office before the election
    and the first non-caretaker cabinet formed after it.

    Why not compare cabinet_id? ParlGov issues a new cabinet_id after every
    election, even when the same government continues, so that comparison is
    always "different" and the outcome never varies.
    Why both party and name? ParlGov sometimes re-labels a party id for the
    same alliance (e.g. Hungary 2022: Fi-MPSz -> Fi+KDNP, same PM), which a
    party-only test would count as a change; a name-only test misses
    same-party PM swaps, which we treat as continuity.
    """
    elections_url = "https://www.parlgov.org/data/parlgov-development_csv-utf-8/view_election.csv"
    cabinets_url = "https://www.parlgov.org/data/parlgov-development_csv-utf-8/view_cabinet.csv"
    elections_file = "parlgov_elections.csv"
    cabinets_file = "parlgov_cabinets.csv"

    def load_cached_csv(filename: str, url: str) -> pd.DataFrame:
        if os.path.exists(filename):
            print(f"✓ Loaded election data from local cache: '{filename}'")
            return pd.read_csv(filename)

        print(f"'{filename}' not found locally. Downloading from the official ParlGov data endpoint...")
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"✓ Successfully downloaded and cached '{filename}'")
        return pd.read_csv(io.BytesIO(response.content))

    elections = load_cached_csv(elections_file, elections_url)
    cabinets = load_cached_csv(cabinets_file, cabinets_url)

    required_election_columns = {
        "country_name", "election_type", "election_date",
        "election_id", "previous_cabinet_id",
    }
    missing = required_election_columns - set(elections.columns)
    if missing:
        raise RuntimeError(
            "[ParlGov elections] Missing required columns: " + ", ".join(sorted(missing))
        )

    required_cabinet_columns = {
        "cabinet_id", "cabinet_name", "election_id", "start_date",
        "caretaker", "prime_minister", "party_id",
    }
    missing = required_cabinet_columns - set(cabinets.columns)
    if missing:
        raise RuntimeError(
            "[ParlGov cabinets] Missing required columns: " + ", ".join(sorted(missing))
        )

    elections["election_date"] = pd.to_datetime(elections["election_date"], errors="coerce")
    elections["previous_cabinet_id"] = pd.to_numeric(
        elections["previous_cabinet_id"], errors="coerce"
    )
    cabinets["start_date"] = pd.to_datetime(cabinets["start_date"], errors="coerce")
    for col in ("cabinet_id", "caretaker", "prime_minister"):
        cabinets[col] = pd.to_numeric(cabinets[col], errors="coerce")
    cabinets["caretaker"] = cabinets["caretaker"].fillna(0)

    print(f"  ParlGov election data runs until {elections['election_date'].max().date()}")

    # Keep parliamentary elections; collapse party-level rows to one row per election.
    elections = elections[
        elections["election_type"].astype(str).str.contains("parliament", case=False, na=False)
    ].copy()
    election_base = (
        elections.sort_values(["country_name", "election_date"])
        .drop_duplicates(subset=["election_id"], keep="first")
        .copy()
    )

    # NOTE: NAME2ISO is keyed by full country names, so map country_name
    # (country_name_short holds 3-letter codes such as "DEU").
    election_base["country_code"] = election_base["country_name"].map(NAME2ISO)
    election_base = election_base.dropna(subset=["country_code", "election_date"])

    # Cabinet-level facts: PM name (cabinet name without the roman numeral),
    # PM party, start date, caretaker flag.
    cabinet_meta = (
        cabinets.drop_duplicates(subset=["cabinet_id"])
        .set_index("cabinet_id")[["cabinet_name", "election_id", "start_date", "caretaker"]]
        .copy()
    )
    cabinet_meta["pm_name"] = (
        cabinet_meta["cabinet_name"].astype(str)
        .str.strip()
        .str.replace(r"\s+[IVXLC]+$", "", regex=True)
        .str.strip()
    )
    pm_party = (
        cabinets[cabinets["prime_minister"] == 1]
        .groupby("cabinet_id")["party_id"].first()
    )

    # First NON-caretaker cabinet formed after each election.
    cabinet_after_election = (
        cabinet_meta[cabinet_meta["caretaker"] != 1]
        .reset_index()
        .sort_values(["election_id", "start_date"])
        .drop_duplicates(subset=["election_id"], keep="first")
        [["election_id", "cabinet_id"]]
        .rename(columns={"cabinet_id": "post_election_cabinet_id"})
    )
    election_base = election_base.merge(cabinet_after_election, on="election_id", how="left")

    no_post = election_base["post_election_cabinet_id"].isna()
    if no_post.any():
        print(
            f"  Dropped {int(no_post.sum())} election(s) with no non-caretaker "
            "cabinet in ParlGov (typically hung parliaments / snap re-elections)"
        )
    election_base = election_base[~no_post].copy()

    pre = election_base["previous_cabinet_id"]
    post = election_base["post_election_cabinet_id"]
    pm_changed = pre.map(cabinet_meta["pm_name"]) != post.map(cabinet_meta["pm_name"])
    party_changed = pre.map(pm_party) != post.map(pm_party)
    election_base["govt_change"] = (pm_changed & party_changed & pre.notna()).astype(int)

    # The ParlGov development release may not contain the UK general election
    # held on 2024-07-04, so keep the project-specific UK override explicit.
    uk_2024 = pd.DataFrame(
        [{
            "country_code": "GB",
            "election_date": pd.Timestamp("2024-07-04"),
            "govt_change": 1,
        }]
    )

    result = election_base[["country_code", "election_date", "govt_change"]].copy()
    result = pd.concat([result, uk_2024], ignore_index=True)
    result = result.drop_duplicates(
        subset=["country_code", "election_date"], keep="last"
    )
    result["month"] = result["election_date"].dt.to_period("M")

    print(
        f"✓ Processed {len(result)} parliamentary election records; "
        f"government changes: {int(result['govt_change'].sum())}"
    )
    return result[["country_code", "election_date", "month", "govt_change"]]

# ---------------------------------------------------------------------------
# AGGREGATION & PANEL BUILDING
# ---------------------------------------------------------------------------
def window_agg(
    monthly,
    elections,
    col,
    agg="mean",
    months_back=WINDOW_MONTHS,
    min_periods=MIN_PERIODS,
):
    """Aggregates monthly observations over the 12 months ending at each election month."""
    out = []
    for _, election in elections.iterrows():
        lower_bound = election["month"] - months_back
        upper_bound = election["month"]
        values = monthly[
            (monthly["country_code"] == election["country_code"])
            & (monthly["month"] > lower_bound)
            & (monthly["month"] <= upper_bound)
        ][col]

        aggregated = getattr(values, agg)() if len(values) >= min_periods else np.nan
        out.append({
            "country_code": election["country_code"],
            "election_date": election["election_date"],
            col: aggregated,
        })
    return pd.DataFrame(out)

def last_observed(monthly, elections, col, max_lag_months=15):

    """Uses the latest observation available on or before each election month."""

    out = []

    # Make sure the observation dates use monthly Period values.
    monthly = monthly.copy()
    monthly["month"] = pd.PeriodIndex(
        monthly["month"],
        freq="M"
    )

    for _, election in elections.iterrows():

        election_month = pd.Period(
            election["month"],
            freq="M"
        )

        values = monthly[
            (monthly["country_code"] == election["country_code"])
            & (monthly["month"] <= election_month)
            & (
                monthly["month"]
                > election_month - max_lag_months
            )
        ]

        value = (
            values.sort_values("month")[col].iloc[-1]
            if len(values)
            else np.nan
        )

        out.append({
            "country_code": election["country_code"],
            "election_date": election["election_date"],
            col: value,
        })

    return pd.DataFrame(out)

def build_panel(start="2015-01", end="2026-06"):
    print("Fetching Inflation...")
    infl = get_inflation()
    print("Fetching Unemployment...")
    unemp = get_unemployment()
    print("Fetching GDP Growth...")
    gdp = get_gdp_growth()
    print("Fetching Asylum & Temporary Protection...")
    asylum = get_asylum()
    # UK Eurostat asylum data ends in 2020.
    # For the 2024 UK election, use the official Home Office
    # 12-month figure ending June 2024, which includes main applicants
    # and dependants for Eurostat-comparable international reporting.
    uk_2024_asylum = pd.DataFrame(
        {
            "country_code": ["GB"],
            "month": [pd.Period("2024-07", freq="M")],
            "asylum_applicants": [97107.0],
        }
    )

    asylum = pd.concat(
        [asylum, uk_2024_asylum],
        ignore_index=True,
    )

    
    tp = get_temporary_protection()
    print("Fetching Population...")
    pop = get_population()
    print("Fetching Elections...")
    elections = get_elections()
    elections = elections[
        (elections["month"] >= pd.Period(start, freq="M"))
        & (elections["month"] <= pd.Period(end, freq="M"))
    ]

    infl12 = window_agg(infl, elections, "inflation_yoy", "mean")
    unemp12 = window_agg(unemp, elections, "unemployment_rate", "mean")
    asylum12 = window_agg(asylum, elections, "asylum_applicants", "sum")
    # UK source bridge:
    # Eurostat UK asylum data ends in 2020.
    # For the 2024-07-04 UK election, use the official Home Office
    # 12-month figure ending June 2024, including main applicants
    # and dependants for Eurostat-comparable reporting.
    uk_2024_mask = (
        (asylum12["country_code"] == "GB")
        & (asylum12["election_date"] == pd.Timestamp("2024-07-04"))
    )

    asylum12.loc[uk_2024_mask, "asylum_applicants"] = 97107.0   
    tp_last = last_observed(tp, elections, "tp_ukrainians")
    tp_last["tp_ukrainians"] = tp_last["tp_ukrainians"].fillna(0.0)

    gdp_last = last_observed(gdp, elections, "gdp_growth")

    panel = elections.copy()
    for d in (infl12, unemp12, asylum12, tp_last, gdp_last):
        panel = panel.merge(d, on=["country_code", "election_date"], how="left")

    panel["year"] = panel["election_date"].dt.year
    panel = panel.merge(pop, on=["country_code", "year"], how="left")
    panel["population"] = panel.groupby("country_code")["population"].ffill()
    panel["inflation_12m_avg"] = panel["inflation_yoy"]
    panel["asylum_per_100k"] = (
        panel["asylum_applicants"] / panel["population"] * 1e5
    )
    panel["ukraine_tp_per_100k"] = (
        panel["tp_ukrainians"] / panel["population"] * 1e5
    )

    # Standardized composite migration-pressure index. The two components have
    # different temporal meanings (12-month asylum flow vs. latest protection stock),
    # so standardization is preferable to adding their raw values. This index is
    # not a count of total immigrants.
    asylum_z = (
        panel["asylum_per_100k"] - panel["asylum_per_100k"].mean()
    ) / panel["asylum_per_100k"].std()
    tp_z = (
        panel["ukraine_tp_per_100k"] - panel["ukraine_tp_per_100k"].mean()
    ) / panel["ukraine_tp_per_100k"].std()
    panel["migration_pressure_index"] = (asylum_z + tp_z) / 2.0
   
    panel["is_eu_member"] = (
        panel["country_code"] != UNITED_KINGDOM_GB
    ).astype(int)

    cols = [
        "country_code",
        "is_eu_member",
        "election_date",
        "inflation_12m_avg",
        "asylum_per_100k",
        "ukraine_tp_per_100k",
        "migration_pressure_index",
        "unemployment_rate",
        "gdp_growth",
        "govt_change",
    ]
    return (
        panel[cols]
        .sort_values(["country_code", "election_date"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# MODEL FITTING & EXPORT
# ---------------------------------------------------------------------------
def fit_models(panel):
  import statsmodels.api as sm

  def logit(d, y, x_cols, tag):
    d = d.dropna(subset=x_cols + [y])
    print(f"{tag}: N={len(d)}, govt_change=1 -> {int(d[y].sum())}")
    if len(d) == 0 or d[y].nunique() < 2:
      raise RuntimeError(
          f"{tag}: cannot fit (N={len(d)}, distinct outcomes={d[y].nunique()}). "
          "Check the panel: missing predictors or a constant govt_change."
      )
    if len(d) < 30:
      print(f"  !! {tag} sample size small ({len(d)}); interpret carefully")
    X = sm.add_constant(d[x_cols])
    return sm.Logit(d[y], X).fit(disp=0), len(d)

  v1, n1 = logit(panel, "govt_change", ["inflation_12m_avg"], "V1")
  v2, n2 = logit(
      panel,
      "govt_change",
      ["inflation_12m_avg", "unemployment_rate", "gdp_growth"],
      "V2",
  )
  v3, n3 = logit(
      panel,
      "govt_change",
      [
          "inflation_12m_avg",
          "asylum_per_100k",
          "ukraine_tp_per_100k",
          "unemployment_rate",
          "gdp_growth",
      ],
      "V3",
  )
  v4, n4 = logit(
      panel,
      "govt_change",
      [
          "inflation_12m_avg",
          "migration_pressure_index",
          "unemployment_rate",
          "gdp_growth",
      ],
      "V4",
  )

  for tag, m in (("V1", v1), ("V2", v2), ("V3", v3), ("V4", v4)):
    ors = np.exp(m.params)
    ci = np.exp(m.conf_int())
    print(f"\n=== {tag} ===")
    print(
        pd.DataFrame({
            "coef": m.params,
            "odds_ratio": ors,
            "OR_lo": ci[0],
            "OR_hi": ci[1],
            "p": m.pvalues,
        }).round(4)
    )
    print(f"AIC={m.aic:.2f}  PseudoR2={m.prsquared:.3f}")
  return v1, v2, v3, v4


def export_models_json(v1, v2, v3, v4, path="models.json"):
  payload = []
  for name, m in (("V1", v1), ("V2", v2), ("V3", v3), ("V4", v4)):
    payload.append({
        "name": name,
        "intercept": float(m.params.get("const", 0.0)),
        "coefficients": {
            k: float(v) for k, v in m.params.items() if k != "const"
        },
        "aic": float(m.aic),
        "p_values": {k: float(v) for k, v in m.pvalues.items()},
        "confidence_intervals": {
            k: [float(v[0]), float(v[1])] for k, v in m.conf_int().iterrows()
        },
        "odds_ratios": {k: float(v) for k, v in np.exp(m.params).items()},
    })
  with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
  print(f"models.json written ({path})")


if __name__ == "__main__":
    panel = build_panel(start="2015-01", end="2026-06")
    panel.to_csv("panel_dataset.csv", index=False)
    print(
        f"\nElection observations: {len(panel)} | Countries:"
        f" {panel.country_code.nunique()} | govt_change=1:"
        f" {int(panel.govt_change.sum())}"
    )
    #print("\nMissing observations count:\n", panel.isna().sum())
   

    get_inflation().to_csv("inflation_series.csv", index=False)
    test_uk_gdp_ons()
    v1, v2, v3, v4 = fit_models(panel)
    export_models_json(v1, v2, v3, v4)