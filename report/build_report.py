from datetime import date
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader


# This example assumes that all three files are in the same folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

REPORT_DIRECTORY = PROJECT_ROOT / "report"
RESULTS_DIRECTORY = PROJECT_ROOT / "results"

METADATA_PATH = REPORT_DIRECTORY / "report_metadata.csv"
# Summary paths
VALUE_SUMMARY_PATH = RESULTS_DIRECTORY / "value_conformance_summary.csv"
LONG_SUMMARY_PATH = RESULTS_DIRECTORY / "longitudinal_plausibility_summary.csv"
IMPORT_SUMMARY_PATH = RESULTS_DIRECTORY / "import_conformance_summary.csv"
CALC_SUMMARY_PATH = RESULTS_DIRECTORY / "computational_conformance_summary.csv"
DATES_SUMMARY_PATH = RESULTS_DIRECTORY / "dates"/"date_rule_summary.csv"
RANGE_SUMMARY_PATH = REPORT_DIRECTORY / "range"/"range_rule_summary.csv"

TEMPLATE_PATH = REPORT_DIRECTORY /"templates"/  "report_template.html"
OUTPUT_PATH = REPORT_DIRECTORY / "data_quality_report.html"



def prepare_rule(rule_id, metadata, summary):
    metadata_row = metadata.loc[
        metadata["rule_id"] == rule_id
    ].iloc[0]

    summary_row = summary.loc[
        summary["rule_id"] == rule_id
    ].iloc[0]

    assessed = int(summary_row["assessed_elements"])
    violations = int(summary_row["total_violations"])

    violation_rate = (
        violations / assessed * 100
        if assessed > 0
        else None
    )

    return {
        "explanation": metadata_row["explanation"],
        "assessment_unit": metadata_row["assessment_unit"],
        "assessed_elements": assessed,
        "total_violations": violations,
        "violation_rate": violation_rate,
    }

metadata = pd.read_csv(
    METADATA_PATH,
    sep=";",
    encoding="cp1252",
)

value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)


boolean = prepare_rule(
    "Boolean_conformance",
    metadata,
    value_summary,
)

float_rule = prepare_rule(
    "Float_conformance",
    metadata,
    value_summary,
)


environment = Environment(
    loader=FileSystemLoader(TEMPLATE_PATH)
)

template = environment.get_template(
    "report_template.html"
)

completed_html = template.render(
    generated_date=date.today().strftime("%d %B %Y"),
    boolean=boolean,
    float_rule=float_rule,
)

OUTPUT_PATH.write_text(
    completed_html,
    encoding="utf-8",
)

print(f"Report created: {OUTPUT_PATH}")
