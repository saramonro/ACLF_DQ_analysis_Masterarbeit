import pandas as pd
from pathlib import Path



# Configuration

EXPORT_PATH = Path("data/processed/export_long_clean.csv")
DATA_DICTIONARY_PATH = Path("metadata/processed/data_dictionary.csv")
EXPECTED_ELEMENTS_PATH = Path("metadata/processed/expected_elements.csv")
FORM_ELEMENTS_PATH = Path(
    "metadata/processed/form_elements_versioned_resolved_only.csv"
)

OUTPUT_DIR = Path("results/relational_conformance")
VIOLATIONS_OUTPUT_PATH = (
    OUTPUT_DIR / "relational_conformance_violations.csv"
)
SUMMARY_OUTPUT_PATH = (
    OUTPUT_DIR / "relational_conformance_summary.csv"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



# Loading

def load_csv(path, sep):
    """Load a CSV file as text so identifiers are not converted."""
    return pd.read_csv(path, dtype="object", sep=sep)


def clean_text_columns(df, columns):
    """Strip whitespace from identifier columns."""
    out = df.copy()

    for column in columns:
        if column in out.columns:
            out[column] = out[column].astype("string").str.strip()

    return out


def prepare_export(df_export):
    """Prepare the export columns used by the relational checks."""
    export = clean_text_columns(
        df_export,
        ["PID", "Episode_Date", "source_id"],
    )

    export["Episode_Date"] = export["Episode_Date"].replace("", pd.NA)

    return export


def prepare_expected_elements(df_expected):
    """Prepare expected patient-element assignments."""
    expected = df_expected.rename(
        columns={"episode_date": "Episode_Date"}
    )

    expected = clean_text_columns(
        expected,
        [
            "PID",
            "Episode_Date",
            "source_id",
            "form_id",
            "form_version",
            "form_type",
        ],
    )

    if "Episode_Date" in expected.columns:
        expected["Episode_Date"] = expected["Episode_Date"].replace(
            "",
            pd.NA,
        )

    if "form_type" in expected.columns:
        expected["form_type"] = (
            expected["form_type"]
            .astype("string")
            .str.strip()
            .str.lower()
        )

    return expected


def prepare_form_elements(df_form_elements):
    """Prepare the versioned Form Editor structure metadata."""
    return clean_text_columns(
        df_form_elements,
        ["form_id", "form_version"],
    )


# Shared output helpers

def make_violation(
    df,
    rule_id,
    expected,
    observed_col,
):
    """Add standard rule-result columns to failed assessment units."""
    out = df.copy()

    out["rule_id"] = rule_id
    out["rule_type"] = "relational_conformance"
    out["expected"] = expected
    out["observed"] = out[observed_col]

    output_columns = [
        "PID",
        "Episode_Date",
        "source_id",
        "form_id",
        "form_version",
        "rule_id",
        "rule_type",
        "expected",
        "observed",
    ]

    return out.reindex(columns=output_columns)


def make_summary(rule_id, assessed_elements, violations):
    """Create one summary row for a relational rule."""
    return {
        "rule_type": "relational_conformance",
        "rule_id": rule_id,
        "assessed_elements": int(assessed_elements),
        "total_violations": int(len(violations)),
    }



# Relational conformance checks

def check_source_id_exists(df_export, df_dictionary):
    """
    Check that every source_id in the export exists in the data dictionary.

    Assessment unit:
        unique exported source_id
    """
    observed = (
        df_export[["source_id"]]
        .dropna(subset=["source_id"])
        .drop_duplicates()
    )

    valid_source_ids = (
        clean_text_columns(df_dictionary, ["source_id"])[["source_id"]]
        .dropna(subset=["source_id"])
        .drop_duplicates()
        .assign(source_id_exists=True)
    )

    checked = observed.merge(
        valid_source_ids,
        on="source_id",
        how="left",
    )

    failed = checked[checked["source_id_exists"].isna()].copy()
    failed["observed_source_id"] = failed["source_id"]

    violations = make_violation(
        failed,
        rule_id="Source_id_exists",
        expected="source_id exists in the data dictionary",
        observed_col="observed_source_id",
    )

    return violations, len(observed)



def check_pid_mapping_conformance(df_export, df_expected):
    """
    Check that patient identifiers map between the export and the
    expected-elements metadata in both directions.
The patient identifiers in the export must match the  patient identifiers in the expected-elements MD.
    """
    export_pids = (
        df_export[["PID"]]
        .dropna(subset=["PID"])
        .drop_duplicates()
        .assign(present_in_export=True)
    )

    expected_pids = (
        df_expected[["PID"]]
        .dropna(subset=["PID"])
        .drop_duplicates()
        .assign(present_in_expected=True)
    )

    checked = export_pids.merge(
        expected_pids,
        on="PID",
        how="outer",
    )

    failed = checked[
        checked["present_in_export"].isna()
        | checked["present_in_expected"].isna()
    ].copy()

    failed["observed_mapping"] = pd.NA

    failed.loc[
        failed["present_in_expected"].isna(),
        "observed_mapping",
    ] = "PID present in export but absent from expected-elements metadata"

    failed.loc[
        failed["present_in_export"].isna(),
        "observed_mapping",
    ] = "PID present in expected-elements metadata but absent from export"

    violations = make_violation(
        failed,
        rule_id="PID_mapping_conformance",
        expected=(
            "PID is represented in both the export and expected-elements "
            "metadata"
        ),
        observed_col="observed_mapping",
    )

    assessed_elements = checked["PID"].nunique()

    return violations, assessed_elements



def check_element_expected_for_patient(df_export, df_expected):
    """
    Check that each observed patient-element combination is expected.

    Filters out empty values so they dont falsely count as observed values (empty values in export exist currently for elements in current registry version)
    """

    df_export = df_export[
    df_export["source_value"].notna()
    & df_export["source_value"].astype("string").str.strip().ne("")
].copy()
    
    #Tweak so that only PIDs present in Provenance MD are considered 
    provenance_pids = set(
    df_expected["PID"]
    .dropna()
    .unique()
)

    assessable_export = df_export[
    df_export["PID"].isin(provenance_pids)
].copy()

    basic_observed = (
        assessable_export[assessable_export["Episode_Date"].isna()]
        [["PID", "source_id"]]
        .dropna(subset=["PID", "source_id"])
        .drop_duplicates()
    )

    longitudinal_observed = (
        assessable_export[assessable_export["Episode_Date"].notna()]
        [["PID", "Episode_Date", "source_id"]]
        .dropna(subset=["PID", "Episode_Date", "source_id"])
        .drop_duplicates()
    )

    if "form_type" in df_expected.columns:
        basic_expected = df_expected[
            df_expected["form_type"].eq("basic")
        ]
        longitudinal_expected = df_expected[
            df_expected["form_type"].eq("longitudinal")
        ]
    else:
        basic_expected = df_expected[df_expected["Episode_Date"].isna()]
        longitudinal_expected = df_expected[
            df_expected["Episode_Date"].notna()
        ]

    valid_basic = (
        basic_expected[["PID", "source_id"]]
        .dropna(subset=["PID", "source_id"])
        .drop_duplicates()
        .assign(element_expected=True)
    )

    valid_longitudinal = (
        longitudinal_expected[["PID", "Episode_Date", "source_id"]]
        .dropna(subset=["PID", "Episode_Date", "source_id"])
        .drop_duplicates()
        .assign(element_expected=True)
    )

    checked_basic = basic_observed.merge(
        valid_basic,
        on=["PID", "source_id"],
        how="left",
    )

    checked_longitudinal = longitudinal_observed.merge(
        valid_longitudinal,
        on=["PID", "Episode_Date", "source_id"],
        how="left",
    )

    failed_basic = checked_basic[
        checked_basic["element_expected"].isna()
    ].copy()

    failed_longitudinal = checked_longitudinal[
        checked_longitudinal["element_expected"].isna()
    ].copy()

    failed = pd.concat(
        [failed_basic, failed_longitudinal],
        ignore_index=True,
    )

    failed["observed_combination"] = (
        failed["PID"].fillna("")
        + " | "
        + failed["Episode_Date"].fillna("basic")
        + " | "
        + failed["source_id"].fillna("")
    )

    violations = make_violation(
        failed,
        rule_id="Element_expected_for_patient",
        expected=(
            "patient-source_id combination exists in expected-elements "
            "metadata for the applicable basic or longitudinal instance"
        ),
        observed_col="observed_combination",
    )

    assessed_elements = len(basic_observed) + len(longitudinal_observed)

    return violations, assessed_elements


def check_form_version_exists(df_expected, df_form_elements):
    """
    Check that every form-version pair in expected-elements metadata
    exists in the versioned Form Editor metadata.

    Assessment unit:
        unique form_id + form_version
    """
    observed_versions = (
        df_expected[["form_id", "form_version"]]
        .dropna(subset=["form_id", "form_version"])
        .drop_duplicates()
    )

    valid_versions = (
        df_form_elements[["form_id", "form_version"]]
        .dropna(subset=["form_id", "form_version"])
        .drop_duplicates()
        .assign(form_version_exists=True)
    )

    checked = observed_versions.merge(
        valid_versions,
        on=["form_id", "form_version"],
        how="left",
    )

    failed = checked[
        checked["form_version_exists"].isna()
    ].copy()

    failed["observed_form_version"] = (
        failed["form_id"] + " | version " + failed["form_version"]
    )

    violations = make_violation(
        failed,
        rule_id="Form_version_exists",
        expected=(
            "form_id and form_version combination exists in versioned "
            "Form Editor metadata"
        ),
        observed_col="observed_form_version",
    )

    return violations, len(observed_versions)


# Apply rules

def apply_rules(
    df_export,
    df_dictionary,
    df_expected,
    df_form_elements,
):
    """Run all relational conformance checks."""
    rule_results = [
        (
            "Source_id_exists",
            *check_source_id_exists(
                df_export,
                df_dictionary,
            ),
        ),
        (
    "PID_mapping_conformance",
    *check_pid_mapping_conformance(
        df_export,
        df_expected,
    ),
),
        (
            "Element_expected_for_patient",
            *check_element_expected_for_patient(
                df_export,
                df_expected,
            ),
        ),
        (
            "Form_version_exists",
            *check_form_version_exists(
                df_expected,
                df_form_elements,
            ),
        ),
        
    ]

    violation_tables = []
    summary_rows = []

    for rule_id, violations, assessed_elements in rule_results:
        summary_rows.append(
            make_summary(
                rule_id=rule_id,
                assessed_elements=assessed_elements,
                violations=violations,
            )
        )

        if not violations.empty:
            violation_tables.append(violations)

    if violation_tables:
        all_violations = pd.concat(
            violation_tables,
            ignore_index=True,
        )
    else:
        all_violations = pd.DataFrame(
            columns=[
                "PID",
                "Episode_Date",
                "source_id",
                "form_id",
                "form_version",
                "rule_id",
                "rule_type",
                "expected",
                "observed",
            ]
        )

    summary = pd.DataFrame(summary_rows)

    return all_violations, summary


# Main

def main():
    df_export = load_csv(EXPORT_PATH, sep=";")
    df_dictionary = load_csv(DATA_DICTIONARY_PATH, sep=";")

    df_expected = load_csv(EXPECTED_ELEMENTS_PATH, sep=";")
    df_form_elements = load_csv(FORM_ELEMENTS_PATH, sep=",")

    df_export = prepare_export(df_export)
    df_expected = prepare_expected_elements(df_expected)
    df_form_elements = prepare_form_elements(df_form_elements)

    violations, summary = apply_rules(
        df_export=df_export,
        df_dictionary=df_dictionary,
        df_expected=df_expected,
        df_form_elements=df_form_elements,
    )

    violations.to_csv(
        VIOLATIONS_OUTPUT_PATH,
        index=False,
        sep=";",
    )

    summary.to_csv(
        SUMMARY_OUTPUT_PATH,
        index=False,
        sep=";",
    )

    print(summary.to_string(index=False))
    print(f"\nTotal relational violations: {len(violations)}")
    print(f"Violations saved to: {VIOLATIONS_OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
