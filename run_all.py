"""Run the data-quality check pipeline.

Reads config.yaml (via config.py) and executes each enabled check script in
order. Individual scripts can be activated or deactivated in config.yaml under the
'scripts' section.

 
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
# Name of the folder with the scripts
CHECKS_DIR = PROJECT_ROOT / "scripts"

# Execution order
SCRIPT_ORDER = [
    "1_mdr_metadata_fetch",
    "2_create_data_dictionary",
    "3_export_data_preprocess_clean",
    "4_value-conformance",
    "5_daterules",
    "6_ranges",
    "7.1_Form_versioning_JSON_to_CSV",
    "7.2_expected_elements_per_patient_with_versions",
    "7.3_completeness_checks",
    "8_calculations",
    "9_import_checks",
    "10_longitudinal_plausibility",
    "11_relational_conformance",
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="SCRIPT_ID",
        help="Run only these script ids (ignores the enabled flags in config).",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to an alternate config file (sets SARA_CONFIG).",
    )
    return parser.parse_args(argv)


def run_script(script_id):
    script_path = CHECKS_DIR / f"{script_id}.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    banner = f" RUNNING {script_id} "
    print("\n" + banner.center(70, "="))
    sys.stdout.flush()

    # Run each script in a fresh subprocess so its memory is fully reclaimed
    # before the next script starts (important for the memory-heavy steps), and
    # so its output streams to the console in real time. 
    result = subprocess.run([sys.executable, str(script_path)], cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"{script_id} exited with code {result.returncode}"
        )


def main(argv=None):
    args = parse_args(argv)

    # Print progress in real time. When stdout is captured/redirected (not a
    # terminal), Python block-buffers it, so the banners below and the child
    # scripts' prints would only appear at the very end, making the pipeline
    # look frozen. Line-buffering flushes each line as it is produced.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    # --config must be applied before importing config, because config.py reads
    # the file at import time.
    if args.config:
        os.environ["SARA_CONFIG"] = str(Path(args.config).expanduser().resolve())

    # Make sure the project root is importable so scripts can 'import config'.
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    import config

    if args.only:
        selected = args.only
        unknown = [s for s in selected if s not in SCRIPT_ORDER]
        if unknown:
            print(f"Warning: unknown script id(s): {', '.join(unknown)}")
    else:
        selected = SCRIPT_ORDER

    ran, skipped = [], []
    for script_id in selected:
        if not args.only and not config.is_enabled(script_id):
            print(f"\nSKIPPED {script_id} (disabled in config.yaml)")
            skipped.append(script_id)
            continue

        try:
            run_script(script_id)
        except Exception as exc:
            print(f"\nERROR while running {script_id}: {exc}", file=sys.stderr)
            print(
                f"\nPipeline stopped at '{script_id}'. "
                f"Ran: {ran or 'none'}. Skipped: {skipped or 'none'}.",
                file=sys.stderr,
            )
            return 1
        ran.append(script_id)

    print("\n" + " PIPELINE COMPLETE ".center(70, "="))
    print(f"Ran ({len(ran)}): {', '.join(ran) or 'none'}")
    print(f"Skipped ({len(skipped)}): {', '.join(skipped) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
