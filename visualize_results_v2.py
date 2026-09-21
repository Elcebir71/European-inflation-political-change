#!/usr/bin/env python3
"""Create portfolio-ready charts for the European political change project."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DATA = Path("panel_dataset.csv")
MODELS = Path("models.json")
OUT = Path("charts")
OUT.mkdir(exist_ok=True)

panel = pd.read_csv(DATA, parse_dates=["election_date"])
panel["govt_change_label"] = panel["govt_change"].map({0: "No government change", 1: "Government change"})

# 1. Migration pressure components by election outcome
fig, ax = plt.subplots(figsize=(10, 6))
for label, group in panel.dropna(subset=["asylum_per_100k", "govt_change_label"]).groupby("govt_change_label"):
    ax.scatter(group["asylum_per_100k"], group["ukraine_tp_per_100k"], alpha=0.75, label=label)
ax.set_title("Asylum applications and Ukrainian temporary protection")
ax.set_xlabel("Asylum applicants per 100,000 (12-month total)")
ax.set_ylabel("Ukrainians under temporary protection per 100,000")
ax.legend()
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(OUT / "05_migration_components.png", dpi=180)
plt.close(fig)

# 2. Composite migration-pressure index vs government change
fig, ax = plt.subplots(figsize=(10, 6))
plot_df = panel.dropna(subset=["migration_pressure_index", "govt_change"])
for outcome, group in plot_df.groupby("govt_change"):
    y = np.full(len(group), outcome, dtype=float) + np.random.default_rng(42).uniform(-0.07, 0.07, len(group))
    ax.scatter(group["migration_pressure_index"], y, alpha=0.75, label="Government change" if outcome == 1 else "No government change")
ax.set_title("Migration pressure index around elections")
ax.set_xlabel("Standardized migration-pressure index")
ax.set_yticks([0, 1], ["No government change", "Government change"])
ax.legend()
ax.grid(axis="x", alpha=0.2)
fig.tight_layout()
fig.savefig(OUT / "06_migration_pressure_vs_government_change.png", dpi=180)
plt.close(fig)

# 3. Migration pressure by country, latest election observation
latest = panel.sort_values("election_date").groupby("country_code").tail(1).dropna(subset=["migration_pressure_index"])
latest = latest.sort_values("migration_pressure_index")
fig, ax = plt.subplots(figsize=(10, 9))
ax.barh(latest["country_code"], latest["migration_pressure_index"])
ax.axvline(0, linewidth=1)
ax.set_title("Migration-pressure index by country")
ax.set_xlabel("Standardized index (latest election observation)")
fig.tight_layout()
fig.savefig(OUT / "07_migration_pressure_by_country.png", dpi=180)
plt.close(fig)

# 4. V4 migration coefficient with 95% confidence interval
with MODELS.open(encoding="utf-8") as f:
    models = json.load(f)
v4 = next(m for m in models if m["name"] == "V4")
coef = v4["coefficients"]["migration_pressure_index"]
ci = v4["confidence_intervals"]["migration_pressure_index"]
lo, hi = ci
or_value = np.exp(coef)
or_lo, or_hi = np.exp(lo), np.exp(hi)

fig, ax = plt.subplots(figsize=(8, 5))
ax.errorbar([or_value], ["V4"], xerr=[[or_value - or_lo], [or_hi - or_value]], fmt="o", capsize=5)
ax.axvline(1, linewidth=1, linestyle="--")
ax.set_xscale("log")
ax.set_title("V4: migration-pressure index coefficient")
ax.set_xlabel("Odds ratio (log scale), 95% confidence interval")
fig.tight_layout()
fig.savefig(OUT / "08_v4_migration_odds_ratio.png", dpi=180)
plt.close(fig)

print(f"Created 4 migration-focused charts in {OUT}/")
print(f"V4 migration-pressure OR: {or_value:.4f} [{or_lo:.4f}, {or_hi:.4f}]")
