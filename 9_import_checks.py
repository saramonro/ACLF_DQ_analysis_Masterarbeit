import pandas as pd
from pathlib import Path


#
# For each import rule:
# only evaluate PID × episode_date where target value exists
# retrieve source value from same PID × episode_date
# compare source vs target
# write only evaluated rows
# write mismatches to violationsggg


# Paths

BASE_DIR = Path.cwd()

EXPORT_PATH = BASE_DIR / "data" / "processed" / "export_long_clean.csv"
IMPORT_RULES_PATH = BASE_DIR / "metadata" / "contextual" / "imports" / "import_rules.csv"
DATA_DICTIONARY_PATH = (
    BASE_DIR
    / "metadata"
    / "processed"
    / "data_dictionary.csv"
)
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

VIOLATIONS_PATH = RESULTS_DIR / "import_conformance_violations.csv"
SUMMARY_PATH = RESULTS_DIR / "import_conformance_summary.csv"
PATIENT_SUMMARY_PATH = RESULTS_DIR / "import_conformance_patient_summary.csv"

# Load data

def load_data():
    export = pd.read_csv(EXPORT_PATH, sep=";", dtype=object)
    import_rules = pd.read_csv(IMPORT_RULES_PATH, sep=";", dtype=object)
    data_dictionary = pd.read_csv(
        DATA_DICTIONARY_PATH,
        sep=";",
        dtype=object,
    )
    return export, import_rules, data_dictionary



# Form lookup
## Added 14.07.26 because of testing results showing an error when the source variable is basic and the target is longutidinal

def create_form_type_lookup(data_dictionary):
    required_columns = [
        "source_id",
        "form_type",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data_dictionary.columns
    ]

    if missing_columns:
        raise ValueError(
            "Data dictionary is missing columns: "
            f"{missing_columns}"
        )

    form_types = data_dictionary[
        required_columns
    ].copy()

    form_types["source_id"] = (
        form_types["source_id"]
        .astype(str)
        .str.strip()
    )

    form_types["form_type"] = (
        form_types["form_type"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    form_types = form_types.drop_duplicates()

    # Detect source IDs with contradictory classifications
    conflicting = (
        form_types
        .groupby("source_id")["form_type"]
        .nunique()
    )

    conflicting = conflicting[
        conflicting > 1
    ]

    if not conflicting.empty:
        raise ValueError(
            "Some source_ids have multiple form types: "
            f"{conflicting.index.tolist()}"
        )

    return (
        form_types
        .drop_duplicates(subset=["source_id"])
        .set_index("source_id")["form_type"]
        .to_dict()
    )

# Preprocess data

def preprocess_export(export):
    export = export.copy()

    if "Episode_Date" in export.columns and "episode_date" not in export.columns:
        export = export.rename(columns={"Episode_Date": "episode_date"})

    required_columns = ["PID", "episode_date", "source_id", "source_value"]

    missing_columns = [
        col for col in required_columns
        if col not in export.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required export columns: {missing_columns}")

    return export[required_columns].copy()


def preprocess_import_rules(import_rules):
    import_rules = import_rules.copy()

    if "include" in import_rules.columns:
        import_rules = import_rules[
            import_rules["include"].astype(str).str.lower().eq("yes")
        ].copy()

    required_columns = [
        "rule_id",
        "source_label",
        "source_source_id",
        "target_label",
        "target_source_id"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in import_rules.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required import rule columns: {missing_columns}")

    return import_rules


# Create lookup tables

def create_value_lookup(export):
    """
    Creates a fast lookup table for PID x episode_date x source_id.

    If repeated identical values exist, they are collapsed.
    If different values exist for the same key, the value is marked
    as MULTIPLE_VALUES.
    """

    collapsed = (
        export
        .dropna(subset=["source_value"])
        .groupby(["PID", "episode_date", "source_id"], dropna=False)["source_value"]
        .agg(lambda values: collapse_values(values))
        .reset_index()
    )

    lookup = collapsed.set_index(
        ["PID", "episode_date", "source_id"]
    )["source_value"]

    return lookup


def create_patient_value_lookup(
    export,
    basic_source_ids,
):
    basic_export = export[
        export["source_id"].isin(
            basic_source_ids
        )
    ].copy()

    collapsed = (
        basic_export
        .dropna(subset=["source_value"])
        .groupby(
            [
                "PID",
                "source_id",
            ],
            dropna=False,
        )["source_value"]
        .agg(collapse_values)
        .reset_index()
    )

    return collapsed.set_index(
        [
            "PID",
            "source_id",
        ]
    )["source_value"]

def create_context_lookup(export):
    """
    Creates a dictionary:
    source_id -> unique PID x episode_date contexts where this source_id exists.
    """

    context_lookup = {
        source_id: group[["PID", "episode_date"]].drop_duplicates()
        for source_id, group in export.groupby("source_id", dropna=False)
    }

    return context_lookup


def collapse_values(values):
    unique_values = pd.Series(values).dropna().astype(str).unique()

    if len(unique_values) == 0:
        return None

    if len(unique_values) > 1:
        return "MULTIPLE_VALUES"

    return unique_values[0]


# Helper functions

def get_value(lookup, pid, episode_date, source_id):
    key = (pid, episode_date, source_id)

    try:
        value = lookup.loc[key]
    except KeyError:
        return None

    if pd.isna(value):
        return None

    return value

def get_patient_value(
    patient_value_lookup,
    pid,
    source_id,
):
    key = (
        pid,
        source_id,
    )

    try:
        value = patient_value_lookup.loc[key]
    except KeyError:
        return None

    if pd.isna(value):
        return None

    return value


def values_equal(source_value, target_value):
    """
    Compares numeric values numerically when possible.
    Otherwise compares as stripped strings.
    """

    try:
        source_num = float(str(source_value).replace(",", "."))
        target_num = float(str(target_value).replace(",", "."))
        return source_num == target_num

    except ValueError:
        return str(source_value).strip() == str(target_value).strip()


# Run import conformance checks

def run_import_conformance_checks(import_rules, value_lookup, context_lookup,form_type_lookup, patient_value_lookup):
    violations = []
    summary_rows = []

    for _, rule in import_rules.iterrows():

        rule_id = rule["rule_id"]
        source_label = rule["source_label"]
        source_source_id = rule["source_source_id"]
        target_label = rule["target_label"]
        target_source_id = rule["target_source_id"]
        source_form_type = form_type_lookup.get(
        source_source_id)

        target_form_type = form_type_lookup.get(
        target_source_id)



        target_contexts = context_lookup.get(target_source_id)

        if target_contexts is None or target_contexts.empty:
            summary_rows.append({
                "rule_id": rule_id,
                "source_label": source_label,
                "target_label": target_label,
                "source_source_id": source_source_id,
                "target_source_id": target_source_id,
                "n_evaluated": 0,
                "n_violations": 0,
                "n_skipped_missing_source": 0,
                "n_skipped_multiple_source": 0,
                "n_skipped_multiple_target": 0
            })
            continue

        n_evaluated = 0
        n_violations = 0
        n_skipped_missing_source = 0
        n_skipped_multiple_source = 0
        n_skipped_multiple_target = 0

        for _, context in target_contexts.iterrows():

            pid = context["PID"]
            episode_date = context["episode_date"]

            if (
                source_form_type == "longitudinal"
                and target_form_type == "longitudinal"
):
    # Compare source and target within the same episode
                 source_value = get_value(
                  value_lookup,
                 pid,
                 episode_date,
                 source_source_id,
    )

            elif (
                source_form_type == "basic"
                and target_form_type == "longitudinal"
):
    # Reuse the patient's basic value for every
    # longitudinal target episode
                 source_value = get_patient_value(
                 patient_value_lookup,
                 pid,
                 source_source_id,
    )

            else:
               raise ValueError(
        f"Unsupported form-type combination "
        f"for rule {rule_id}: "
        f"source={source_form_type}, "
        f"target={target_form_type}"
    )
            

            target_value = get_value(
                value_lookup,
                pid,
                episode_date,
                target_source_id
            )

            # Target exists by construction, but keep this for safety
            if target_value is None:
                continue

            if source_value is None:
                n_skipped_missing_source += 1
                continue

            if source_value == "MULTIPLE_VALUES":
                n_skipped_multiple_source += 1
                continue

            if target_value == "MULTIPLE_VALUES":
                n_skipped_multiple_target += 1
                continue

            n_evaluated += 1

            if not values_equal(source_value, target_value):
                n_violations += 1

                violations.append({
                    "PID": pid,
                    "episode_date": episode_date,
                    "rule_id": rule_id,
                    "source_label": source_label,
                    "target_label": target_label,
                    "source_source_id": source_source_id,
                    "target_source_id": target_source_id,
                    "source_value": source_value,
                    "target_value": target_value,
                    "violation": True
                })

        summary_rows.append({
            "rule_id": rule_id,
            "source_label": source_label,
            "target_label": target_label,
            "source_source_id": source_source_id,
            "target_source_id": target_source_id,
            "assessed_elements": n_evaluated,
            "total_violations": n_violations,
            "n_skipped_missing_source": n_skipped_missing_source,
            "n_skipped_multiple_source": n_skipped_multiple_source,
            "n_skipped_multiple_target": n_skipped_multiple_target
        })

    violations_df = pd.DataFrame(violations)
    summary_df = pd.DataFrame(summary_rows)

    return violations_df, summary_df

# Patient summary

def create_patient_summary(violations_df):

    if violations_df.empty:
        return pd.DataFrame(
            columns=[
                "PID",
                "n_violations",
                "n_failed_rules",
                "failed_rules"
            ]
        )

    patient_summary = (
        violations_df
        .groupby("PID", dropna=False)
        .agg(
            n_violations=("rule_id", "size"),
            n_failed_rules=("rule_id", "nunique"),
            failed_rules=(
                "rule_id",
                lambda values: ", ".join(sorted(set(values)))
            )
        )
        .reset_index()
        .sort_values(
            ["n_violations", "PID"],
            ascending=[False, True]
        )
    )

    return patient_summary
# Save outputs

def save_outputs(
    violations_df,
    summary_df,
    patient_summary_df
):
    violations_df.to_csv(VIOLATIONS_PATH, sep=";", index=False)
    summary_df.to_csv(SUMMARY_PATH, sep=";", index=False)
    patient_summary_df.to_csv(
    PATIENT_SUMMARY_PATH,
    sep=";",
    index=False
)


# Main

def main():
    export, import_rules, data_dictionary = (
    load_data()
)
    export = preprocess_export(export)
   
    import_rules = preprocess_import_rules(import_rules)
    form_type_lookup = create_form_type_lookup(
    data_dictionary
)       
    basic_source_ids = {
    source_id
    for source_id, form_type
    in form_type_lookup.items()
    if form_type == "basic"
}
    value_lookup = create_value_lookup(export)
    patient_value_lookup = (
    create_patient_value_lookup(
        export,
        basic_source_ids,
    )
)
    context_lookup = create_context_lookup(export)

    (violations_df, summary_df) = run_import_conformance_checks(
        import_rules=import_rules,
        value_lookup=value_lookup,
        patient_value_lookup=patient_value_lookup,
        context_lookup=context_lookup,
        form_type_lookup=form_type_lookup,
)
    patient_summary_df = create_patient_summary(
    violations_df
)
    save_outputs(
        violations_df,
        summary_df,
        patient_summary_df
    )
    print("Import conformance check finished.")
    print(f"Violations saved to: {VIOLATIONS_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    print(f"Number of violations: {len(violations_df)}")


if __name__ == "__main__":
    main()