# Adding New Check Scripts

The pipeline is driven by three files at the project root:
`config.yaml` (user settings + script toggles), `config.py` (translator), and
`run_all.py` (runner). To add a new check script, there are three touch points.

## 1. Create the script in `checks/`

- Name it with a numeric prefix reflecting its order, e.g. `12_my_new_check.py`.
- Give it a `main()` function and the standard entry guard, since the runner
  executes each file with `run_name="__main__"`:

```python
if __name__ == "__main__":
    main()
```

- If it needs any configurable values (`NAMESPACE`, `REGISTRY_NAME`,
  `URL`, `RAW_EXPORT_PATH`), add the `sys.path` shim and import from
  `config`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import REGISTRY_NAME  # or whatever it needs
```

If it only uses paths derived from `PROJECT_ROOT`, no config import is needed.

## 2. Register it in `run_all.py`

Add the script id (filename without `.py`) to the `SCRIPT_ORDER` list at the
position where it should run:

```python
SCRIPT_ORDER = [
    "1_mdr_metadata_fetch",
    ...
    "11_relational_conformance",
    "12_my_new_check",
]
```

The id must exactly match the filename stem.

## 3. Add a toggle in `config.yaml`

Add an entry under `scripts:` so it can be enabled/disabled:

```yaml
scripts:
  ...
  "12_my_new_check": true
```

## Notes on the toggle

`is_enabled()` in `config.py` defaults unknown script ids to `True`, so a script
added to `SCRIPT_ORDER` but not listed in `config.yaml` still runs. You must add
the `config.yaml` entry if you want to be able to disable it.

## Summary

| Step | File | Required? |
|------|------|-----------|
| Create script with `main()` + entry guard | `checks/<id>.py` | Yes |
| Add config imports (if it needs configurable values) | `checks/<id>.py` | Only if needed |
| Add id to `SCRIPT_ORDER` | `run_all.py` | Yes (else runner ignores it) |
| Add toggle entry | `config.yaml` | Recommended (needed to disable it) |

If a new configurable value is required (not already in `config.yaml`), also add
it to `config.yaml` and expose it in `config.py` alongside the existing
`NAMESPACE`/`REGISTRY_NAME`/etc.