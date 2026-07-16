from datetime import date
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader

####
# Adding rules:
# Add summary path
# Load summary
# Add variable with prepare_rule function
# Add variable to template render call



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
RANGE_SUMMARY_PATH = RESULTS_DIRECTORY / "range"/"range_rule_summary.csv"
RELATIONAL_SUMMARY_PATH = (
    RESULTS_DIRECTORY / "relational_conformance"/ "relational_conformance_summary.csv"
)

TEMPLATE_DIRECTORY = REPORT_DIRECTORY / "templates"
TEMPLATE_PATH = REPORT_DIRECTORY /"templates"/  "report_template.html"
OUTPUT_PATH = REPORT_DIRECTORY / "data_quality_report.html"

## Completeness summary paths

COMPLETENESS_RESULTS_DIRECTORY = RESULTS_DIRECTORY/ "completeness"

COMPLETENESS_SUMMARY_PATH = (
    COMPLETENESS_RESULTS_DIRECTORY / "completeness_summary.csv"
)

FORM_PRESENCE_SUMMARY_PATH = (
    COMPLETENESS_RESULTS_DIRECTORY / "form_presence_summary.csv"
)

COMPLETENESS_PER_FORM_PATH = (
    COMPLETENESS_RESULTS_DIRECTORY / "completeness_per_form.csv"
)

COMPLETENESS_PER_PATIENT_PATH = (
    COMPLETENESS_RESULTS_DIRECTORY / "completeness_per_patient.csv"
)

REPORT_ASSETS_DIRECTORY = REPORT_DIRECTORY / "assets"
REPORT_ASSETS_DIRECTORY.mkdir(exist_ok=True)
FORM_CHART_PATH = (
    REPORT_ASSETS_DIRECTORY / "completeness_by_form.png"
)

PATIENT_CHART_PATH = (
    REPORT_ASSETS_DIRECTORY / "patient_completeness_distribution.png"
)
####

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


# LOADS
metadata = pd.read_csv(
    METADATA_PATH,
    sep=";",
    encoding="utf-8",
)
## Summary Loads
long_summary = pd.read_csv(
    LONG_SUMMARY_PATH,
    sep=";",
)
value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)
import_summary = pd.read_csv(
    IMPORT_SUMMARY_PATH,
    sep=";",
)
calc_summary = pd.read_csv(
    CALC_SUMMARY_PATH,
    sep=";",
)
dates_summary = pd.read_csv(
    DATES_SUMMARY_PATH,
    sep=";",
)
range_summary = pd.read_csv(
    RANGE_SUMMARY_PATH,
    sep=";",
)
value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)
value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)
value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)
value_summary = pd.read_csv(
    VALUE_SUMMARY_PATH,
    sep=";",
)
relational_summary = pd.read_csv(
    RELATIONAL_SUMMARY_PATH,
    sep=";",
)

### Prepare rules

boolean = prepare_rule(
    "Boolean_conformance",
    metadata,
    value_summary,
)

float = prepare_rule(
    "Float_conformance",
    metadata,
    value_summary,
)

integer = prepare_rule(
    "Integer_conformance",
    metadata,
    value_summary,
)

permissible_values = prepare_rule(
    "Permissible_values_conformance",
    metadata,
    value_summary,
)

date_format = prepare_rule(
    "Date_format_conformance",
    metadata,
    value_summary,
)

single_choice = prepare_rule(
    "Single_choice_conformance",
    metadata,
    value_summary,
)
numeric_range = prepare_rule(
    "range_conformance",
                             metadata,
                             range_summary
    
    )


### Calculations section

def prepare_calculation_section(metadata, calc_summary):
    calc_summary = calc_summary.copy()

    calc_summary["assessed_elements"] = pd.to_numeric(
        calc_summary["assessed_elements"]
    )

    calc_summary["total_violations"] = pd.to_numeric(
        calc_summary["total_violations"]
    )

    calc_summary["violation_rate"] = (
        calc_summary["total_violations"]
        / calc_summary["assessed_elements"]
        * 100
    )

    metadata_row = metadata.loc[
        metadata["rule_type"] == "calculation_check"
    ].iloc[0]

    total_assessed = calc_summary["assessed_elements"].sum()
    total_violations = calc_summary["total_violations"].sum()

    overall_violation_rate = (
        total_violations / total_assessed * 100
        if total_assessed > 0
        else None
    )

    table = calc_summary.copy()

    table["Calculation"] = table["rule_id"]

    table["Violation rate"] = table["violation_rate"].map(
        lambda value: f"{value:.2f}%"
    )

    table = table.rename(
        columns={
            "assessed_elements": "Assessed instances",
            "total_violations": "Violations",
        }
    )

    table = table[
        [
            "Calculation",
            "Assessed instances",
            "Violations",
            "Violation rate",
        ]
    ]

    calculation_table = table.to_html(
        index=False,
        classes="result-table",
        border=0,
    )

    return {
        "explanation": metadata_row["explanation"],
        "assessment_unit": metadata_row["assessment_unit"],
        "n_checks": len(calc_summary),
        "total_assessed": int(total_assessed),
        "total_violations": int(total_violations),
        "overall_violation_rate": overall_violation_rate,
        "table": calculation_table,
    }

### Imports section

def prepare_imports_section(metadata, import_summary):
    import_summary = import_summary.copy()

    import_summary["assessed_elements"] = pd.to_numeric(
        import_summary["assessed_elements"]
    )

    import_summary["total_violations"] = pd.to_numeric(
        import_summary["total_violations"]
    )

    import_summary["violation_rate"] = (
        import_summary["total_violations"]
        / import_summary["assessed_elements"]
        * 100
    )

    metadata_row = metadata.loc[
        metadata["rule_type"] == "import_check"
    ].iloc[0]

    total_assessed = import_summary["assessed_elements"].sum()
    total_violations = import_summary["total_violations"].sum()

    overall_violation_rate = (
        total_violations / total_assessed * 100
        if total_assessed > 0
        else None
    )



    return {
        "explanation": metadata_row["explanation"],
        "assessment_unit": metadata_row["assessment_unit"],
        "n_checks": len(import_summary),
        "total_assessed": int(total_assessed),
        "total_violations": int(total_violations),
        "overall_violation_rate": overall_violation_rate,
    }




calculation_section = prepare_calculation_section(
    metadata,
    calc_summary,
)

imports = prepare_imports_section(metadata,import_summary)

environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIRECTORY)
)
# COMPLETENESS section
## Loads
completeness_summary = pd.read_csv(
    COMPLETENESS_SUMMARY_PATH, sep=";"

)

form_presence_summary = pd.read_csv(
    FORM_PRESENCE_SUMMARY_PATH,sep=";"
)

completeness_per_form = pd.read_csv(
    COMPLETENESS_PER_FORM_PATH,sep=";"

)

completeness_per_patient = pd.read_csv(
    COMPLETENESS_PER_PATIENT_PATH,sep=";"

)

# Atemporal Plausibility
def prepare_longitudinal_section(metadata, long_summary):
    long_summary = long_summary.copy()

    long_summary["assessed_elements"] = pd.to_numeric(
        long_summary["assessed_elements"]
    )

    long_summary["total_violations"] = pd.to_numeric(
        long_summary["total_violations"]
    )

    metadata_row = metadata.loc[
        metadata["rule_type"] == "longitudinal_plausibility"
    ].iloc[0]

    total_assessed = long_summary["assessed_elements"].sum()
    total_violations = long_summary["total_violations"].sum()

    pooled_violation_rate = (
        total_violations / total_assessed * 100
        if total_assessed > 0
        else None
    )

    return {
        "explanation": metadata_row["explanation"],
        "assessment_unit": metadata_row["assessment_unit"],
        "n_checks": len(long_summary),
        "total_assessed": int(total_assessed),
        "total_violations": int(total_violations),
        "pooled_violation_rate": pooled_violation_rate,
    }
longitudinal_section = prepare_longitudinal_section(
    metadata,
    long_summary,
)

# Temporal Plausibility
def prepare_temporal_section(metadata, dates_summary):
    dates_summary = dates_summary.copy()

    dates_summary["assessed_elements"] = pd.to_numeric(
        dates_summary["assessed_elements"]
    )

    dates_summary["total_violations"] = pd.to_numeric(
        dates_summary["total_violations"]
    )

    metadata_row = metadata.loc[
        metadata["rule_type"] == "temporal_plausibility"
    ].iloc[0]

    total_assessed = dates_summary["assessed_elements"].sum()
    total_violations = dates_summary["total_violations"].sum()

    pooled_violation_rate = (
        total_violations / total_assessed * 100
        if total_assessed > 0
        else None
    )

    return {
        "explanation": metadata_row["explanation"],
        "assessment_unit": metadata_row["assessment_unit"],
        "n_checks": len(dates_summary),
        "total_assessed": int(total_assessed),
        "total_violations": int(total_violations),
        "pooled_violation_rate": pooled_violation_rate,
    }
temporal_section = prepare_temporal_section(
    metadata,
    dates_summary,
)

## Completeness functions
def prepare_completeness_tables(
    completeness_summary,
    form_presence_summary,
):
    # Table 1: overall overview
    overall = form_presence_summary.loc[
        form_presence_summary["metric"]
        == "Form presence completeness"
    ].copy()

    element_results = completeness_summary[
        [
            "metric",
            "general_completeness_percent",
        ]
    ].copy()

    element_results = element_results.rename(
        columns={
            "general_completeness_percent": "Completeness"
        }
    )

    overall = overall.rename(
        columns={
            "percent": "Completeness",
        }
    )

    overall = overall[
        ["metric", "Completeness"]
    ]

    overview_table = pd.concat(
        [overall, element_results],
        ignore_index=True,
    )

    overview_table["Completeness"] = (
        overview_table["Completeness"]
        .map(lambda value: f"{value:.2f}%")
    )

    overview_table = overview_table.rename(
        columns={
            "metric": "Metric",
        }
    )

    # Table 2: general, core and mandatory
    layers_table = completeness_summary.copy()

    layers_table = layers_table.rename(
        columns={
            "metric": "Assessment level",
            "general_completeness_percent": "General",
            "core_completeness_percent": "Core",
            "mandatory_completeness_percent": "Mandatory",
        }
    )

    layers_table = layers_table[
        [
            "Assessment level",
            "General",
            "Core",
            "Mandatory",
        ]
    ]

    for column in ["General", "Core", "Mandatory"]:
        layers_table[column] = layers_table[column].map(
            lambda value: (
                f"{value:.2f}%"
                if pd.notna(value)
                else "Not applicable"
            )
        )

    return {
        "overview_table": overview_table.to_html(
            index=False,
            classes="result-table",
            border=0,
        ),
        "layers_table": layers_table.to_html(
            index=False,
            classes="result-table",
            border=0,
        ),
    }

completeness = prepare_completeness_tables(
    completeness_summary,
    form_presence_summary,
)
empty_forms_table = form_presence_summary.loc[
    form_presence_summary["metric"].isin(
        [
            "Empty expected basic forms",
            "Empty expected longitudinal forms",
        ]
    )
].copy()

empty_forms_table = empty_forms_table.rename(
    columns={
        "metric": "Form type",
        "denominator_n": "Expected forms",
        "numerator_n": "Empty forms",
        "percent": "Empty-form rate",
    }
)

empty_forms_table["Form type"] = (
    empty_forms_table["Form type"]
    .replace(
        {
            "Empty expected basic forms": "Basic forms",
            "Empty expected longitudinal forms":
                "Longitudinal forms",
        }
    )
)

empty_forms_table["Empty-form rate"] = (
    empty_forms_table["Empty-form rate"]
    .map(lambda value: f"{value:.2f}%")
)

empty_forms_table = empty_forms_table[
    [
        "Form type",
        "Expected forms",
        "Empty forms",
        "Empty-form rate",
    ]
]

completeness["empty_forms_table"] = (
    empty_forms_table.to_html(
        index=False,
        classes="result-table",
        border=0,
    )
)


### Horizontal form-completenss chart
def create_form_completeness_chart(
    completeness_per_form,
    output_path,
):
    chart_data = completeness_per_form.sort_values(
        "general_completeness_percent"
    )

    labels = (
    chart_data["form_label"]
    + " ("
    + chart_data["form_id"].astype(str)
    + ")"
)

    fig, ax = plt.subplots(figsize=(9, 7))

    ax.barh(
        labels,
        chart_data["general_completeness_percent"],
    )

    ax.set_xlabel("Completeness (%)")
    ax.set_ylabel("")
    ax.set_title("General completeness by form")
    ax.set_xlim(0, 100)

    fig.tight_layout()
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)

create_form_completeness_chart(
    completeness_per_form,
    FORM_CHART_PATH,
)

### Patient completeness distributuon
def create_patient_completeness_chart(
    completeness_per_patient,
    output_path,
):
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.hist(
        completeness_per_patient[
            "general_completeness_percent"
        ],
        bins=10,
    )

    ax.set_xlabel("Patient completeness (%)")
    ax.set_ylabel("Number of patients")
    ax.set_title(
        "Distribution of patient-level completeness"
    )
    ax.set_xlim(0, 100)

    fig.tight_layout()
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)

create_patient_completeness_chart(
    completeness_per_patient,
    PATIENT_CHART_PATH,
)


## Summary table for all violations 
def prepare_violation_section(summary_df, display_names):
    section = summary_df.copy()

    section["rule_id"] = section["rule_id"].str.strip()

    section["assessed_elements"] = pd.to_numeric(
        section["assessed_elements"]
    )

    section["total_violations"] = pd.to_numeric(
        section["total_violations"]
    )

    section["violation_rate"] = (
        section["total_violations"]
        / section["assessed_elements"]
        * 100
    )

    section["display_name"] = section["rule_id"].map(
        display_names
    )

    # section totals
    n_checks = len(section)
    total_assessed = section["assessed_elements"].sum()
    total_violations = section["total_violations"].sum()

    overall_violation_rate = (
        total_violations / total_assessed * 100
        if total_assessed > 0
        else None
    )

    # summary table for HTML
    table = section.copy()

    table = table.rename(
        columns={
            "display_name": "Check",
            "assessed_elements": "Assessed instances",
            "total_violations": "Violations",
        }
    )

    table["Violation rate"] = table["violation_rate"].map(
        lambda value: f"{value:.2f}%"
    )

    table = table[
        [
            "Check",
            "Assessed instances",
            "Violations",
            "Violation rate",
        ]
    ]

    table_html = table.to_html(
        index=False,
        classes="result-table",
        border=0,
    )

    return {
        "n_checks": n_checks,
        "total_assessed": int(total_assessed),
        "total_violations": int(total_violations),
        "overall_violation_rate": overall_violation_rate,
        "table": table_html,
        "chart_data": section,
    }

 ### Horizonal bar chart
 
def create_violation_rate_chart(section_df, output_path):
    chart_data = section_df.sort_values("violation_rate")

    fig, ax = plt.subplots(figsize=(9, 5))

    ax.barh(
        chart_data["display_name"],
        chart_data["violation_rate"],
    )

    ax.set_xlabel("Violation rate (%)")
    ax.set_ylabel("")
    ax.set_title("Violation rate by check")

    fig.tight_layout()
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)   


calculation_names = {
    "MELD_scores": "MELD score",
    "MELD_Na_scores": "MELD-Na score",
    "BMI_basic": "Body mass index",
    "MAP_aclf_examination": "Mean arterial pressure – ACLF examination",
    "MAP_physical_examination": "Mean arterial pressure – physical examination",
}

calculation_section = prepare_violation_section(
    calc_summary,
    calculation_names,
)

CALC_CHART_PATH = REPORT_DIRECTORY / "assets" / "calculation_violation_rates.png"
(REPORT_DIRECTORY / "assets").mkdir(exist_ok=True)

## Relational Conformance section
def prepare_relational_section(metadata, relational_summary):
    section = relational_summary.copy()

    section["assessed_elements"] = pd.to_numeric(
        section["assessed_elements"]
    )

    section["total_violations"] = pd.to_numeric(
        section["total_violations"]
    )

    section["violation_rate"] = (
        section["total_violations"]
        / section["assessed_elements"]
        * 100
    )

    metadata_row = metadata.loc[
        metadata["rule_type"] == "relational_conformance"
    ].iloc[0]

    display_names = {
        "Source_id_exists": "Source ID existence",
        "PID_mapping_conformance": "Patient ID mapping",
        "Element_expected_for_patient":
            "Element expected for patient",
        "Form_version_exists": "Form-version existence",
    }

    assessment_units = {
        "Source_id_exists": "Unique source IDs",
        "PID_mapping_conformance": "Unique patient IDs",
        "Element_expected_for_patient":
            "Recorded patient–element instances",
        "Form_version_exists": "Referenced form versions",
    }

    table = section.copy()

    table["Check"] = table["rule_id"].map(display_names)
    table["Assessment unit"] = table["rule_id"].map(
        assessment_units
    )

    table["Violation rate"] = table["violation_rate"].map(
        lambda value: f"{value:.2f}%"
    )

    table = table.rename(
        columns={
            "assessed_elements": "Assessed",
            "total_violations": "Violations",
        }
    )

    table = table[
        [
            "Check",
            "Assessment unit",
            "Assessed",
            "Violations",
            "Violation rate",
        ]
    ]

    return {
        "explanation": metadata_row["explanation"],
        "n_checks": len(section),
        "checks_with_violations": int(
            (section["total_violations"] > 0).sum()
        ),
        "total_violations": int(
            section["total_violations"].sum()
        ),
        "table": table.to_html(
            index=False,
            classes="result-table",
            border=0,
        ),
    }

relational_section = prepare_relational_section(
    metadata,
    relational_summary,
)

### Template Render Call + HTML completenement




template = environment.get_template("report_template.html")


completed_html = template.render(
    generated_date=date.today().strftime("%d %B %Y"),
    boolean=boolean,
    float=float,
    integer=integer,
    permissible_values=permissible_values,
    date_format=date_format,
    single_choice=single_choice,
    numeric_range=numeric_range,
        calculation=calculation_section,
            longitudinal=longitudinal_section,
    imports=imports,
     temporal=temporal_section,
completeness=completeness,
relational=relational_section,

    form_completeness_chart=(
        "assets/completeness_by_form.png"
    ),

    patient_completeness_chart=(
        "assets/patient_completeness_distribution.png"
    ),
)

OUTPUT_PATH.write_text(
    completed_html,
    encoding="utf-8",
)

print(f"Report created: {OUTPUT_PATH}")
