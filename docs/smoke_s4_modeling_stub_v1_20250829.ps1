param(
  [string]$ModelOut="artifacts"
)
Write-Host "S4 Smoke — Modeling"
python - << 'PY'
print("TODO: train baselines, write model_compare.csv & champion_bundle.json")
PY
