param(
  [string]$Features="fixtures\features_small.csv",
  [string]$Response="fixtures\response_small.csv",
  [string]$Out="artifacts"
)
Write-Host "S2 Smoke — Join + Profile"
python - << 'PY'
print("TODO: load CSVs, call services.joiner/profiler, write profile.json")
PY
