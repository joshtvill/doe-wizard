param(
  [string]$CollapsedOut="artifacts"
)
Write-Host "S3 Smoke — Roles + Collapse"
python - << 'PY'
print("TODO: load active table, apply roles/collapse, write modeling_ready.csv & datacard.json")
PY
