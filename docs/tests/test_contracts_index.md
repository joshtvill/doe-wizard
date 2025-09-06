# Test Contracts Index

This page maps **each contract** to its **owning test(s)**.

## JSON Schemas

- schemas/json/schemas_modeling_settings.json  
  → tests/unit/test_schemas_modeling_settings.py::test_required_keys  
  → tests/unit/test_schemas_modeling_settings.py::test_timestamp_fields_local_utc

- schemas/json/schemas_champion_bundle.json  
  → tests/unit/test_schemas_champion_bundle.py::test_required_keys  
  → tests/unit/test_schemas_champion_bundle.py::test_data_fingerprint_consistency

- schemas/json/schemas_optimization_settings.json  
  → tests/unit/test_schemas_optimization_settings.py::test_bounds_snapshot  
  → tests/unit/test_schemas_optimization_settings.py::test_safeguards_defaults

- schemas/json/schemas_screen_log.json  
  → tests/unit/test_schemas_screen_log.py::test_log_event_fields

## Tabular Schemas

- schemas/tables/schemas_proposals_csv.md  
  → tests/unit/test_proposals_schema.py::test_columns_and_types  
  → tests/e2e/test_s5_to_s6_integration.py::test_proposals_unchanged_in_export_pack

- schemas/tables/schemas_run_plan_csv.md  
  → tests/unit/test_run_plan_schema.py::test_columns_and_types

## Screen Contracts

- docs/screens/screen5_optimization_contract_v2.md  
  → tests/e2e/test_screen5_e2e.py::test_defaults_and_safeguards

- docs/screens/screen6_handoff_contract_v2.md  
  → tests/e2e/test_screen6_e2e_pack_write.py::test_export_pack_contents

## Global

- docs/system/state_and_artifacts.md  
  → tests/unit/test_state_and_artifacts.py::test_slug_prefixed_paths  
  → tests/unit/test_state_and_artifacts.py::test_local_utc_presence
