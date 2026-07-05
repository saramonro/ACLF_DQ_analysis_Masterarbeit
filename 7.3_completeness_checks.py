from pathlib import Path
import json
import pandas as pd

expected_elements_path = Path("metadata/processed/expected_elements.csv")

COMPLETENESS_OUTPUT_PATH = Path("results/completeness/completeness_row_level.csv")
empty_forms_path = Path("results/completeness/empty_forms.csv")

expected = pd.read_csv(expected_elements_path, dtype="object")
export = pd.read_csv("data/processed/export_long_clean.csv", sep=";", dtype="object")
# Preprocessing



def create_completeness_table(expected, export):
   
   # creates completeness dataframe, by joining expected data elements per patient to their source_value

    expected = expected.copy()
    export = export.copy()

    export = export.rename(
        columns={"Episode_Date": "episode_date"}
    )

    
# Include only Patients present in the clean export (remove test patients zB)
    valid_pids = export["PID"].dropna().astype(str).unique()
    expected=expected[expected["PID"].astype(str).isin(valid_pids)].copy()


# Basic and Longitudinal subsets
    expected_basic = expected[
        expected["form_type"].eq("basic")
    ].copy()

    expected_long = expected[
        expected["form_type"].eq("longitudinal")
    ].copy()

    basic_completeness = expected_basic.merge(
        export[["PID", "source_id", "source_value"]],
        on=["PID", "source_id"],
        how="left"
    )

    long_completeness = expected_long.merge(
        export[["PID", "episode_date", "source_id", "source_value"]],
        on=["PID", "episode_date", "source_id"],
        how="left"
    )

    completeness = pd.concat(
        [basic_completeness, long_completeness],
        ignore_index=True
    )

    completeness["is_filled"] = (
        completeness["source_value"].notna()
        & completeness["source_value"].astype(str).str.strip().ne("")
    )

    return completeness



# Filter by Form presence: per patient, only consider data elements in forms for which at least one data element has been filled out
## complete form missingness shouldn´t affect individual elements´missingness

def add_form_presence_flag(completeness):
  

    completeness = completeness.copy()

    basic_mask = completeness["form_type"].eq("basic")
    long_mask = completeness["form_type"].eq("longitudinal")

    basic_presence = (
        completeness[basic_mask]
        .groupby(["PID", "form_id"])["is_filled"]
        .any()
        .reset_index(name="form_has_any_value")
    )

    long_presence = (
        completeness[long_mask]
        .groupby(["PID", "episode_date", "form_id"])["is_filled"]
        .any()
        .reset_index(name="form_has_any_value")
    )

    completeness_basic = completeness[basic_mask].merge(
        basic_presence,
        on=["PID", "form_id"],
        how="left"
    )

    completeness_long = completeness[long_mask].merge(
        long_presence,
        on=["PID", "episode_date", "form_id"],
        how="left"
    )

    completeness_with_presence = pd.concat(
        [completeness_basic, completeness_long],
        ignore_index=True
    )

    return completeness_with_presence


def empty_expected_forms(completeness):

    basic_empty_forms = (
    completeness[completeness["form_type"].eq("basic")]
    .groupby(["PID", "form_id", "form_version"], dropna=False)
    .agg(
        form_has_any_value=("is_filled", "any"),
        n_expected_elements=("source_id", "count"),
        n_filled_elements=("is_filled", "sum")
    )
    .reset_index()
    )

    basic_empty_forms = basic_empty_forms[
    ~basic_empty_forms["form_has_any_value"]
    ].copy()

    n_basic_empty_forms = len(basic_empty_forms)

    print(n_basic_empty_forms)
    return basic_empty_forms




def percent(numerator, denominator):
    if denominator == 0:
        return pd.NA
    return round((numerator / denominator) * 100, 2)


def summarize_subset(df, metric_name, denominator_label, numerator_label):
    denominator = len(df)
    numerator = df["is_filled"].sum()

    return {
        "metric": metric_name,
        "denominator_definition": denominator_label,
        "numerator_definition": numerator_label,
        "denominator_n": denominator,
        "numerator_n": numerator,
        "completeness_percent": percent(numerator, denominator)
    }


def general_completeness_summary(completeness_present_forms_only):
    """
    Registry-level general completeness metrics.
    Uses only expected elements in non-empty form instances.
    """

    df = completeness_present_forms_only.copy()

    rows = []

    rows.append(
        summarize_subset(
            df,
            "Overall element completeness",
            "All expected elements in non-empty forms",
            "Filled expected elements"
        )
    )

    rows.append(
        summarize_subset(
            df[df["form_type"].eq("basic")],
            "Basic form completeness",
            "Expected elements in non-empty basic forms",
            "Filled expected basic elements"
        )
    )

    rows.append(
        summarize_subset(
            df[df["form_type"].eq("longitudinal")],
            "Longitudinal form completeness",
            "Expected elements in non-empty longitudinal forms",
            "Filled expected longitudinal elements"
        )
    )

    return pd.DataFrame(rows)


def completeness_per_form(completeness_present_forms_only):
    """
    Completeness per form_id.
    """

    result = (
        completeness_present_forms_only
        .groupby(["form_id"], dropna=False)
        .agg(
            denominator_n=("source_id", "count"),
            numerator_n=("is_filled", "sum"),
            n_patients=("PID", "nunique")
        )
        .reset_index()
    )

    result["metric"] = "Completeness per form"
    result["completeness_percent"] = (
        result["numerator_n"] / result["denominator_n"] * 100
    ).round(2)

    return result.sort_values("completeness_percent")


def completeness_per_form_version(completeness_present_forms_only):
    """
    Completeness per form_id/form_version.
    """

    result = (
        completeness_present_forms_only
        .groupby(["form_id", "form_version"], dropna=False)
        .agg(
            denominator_n=("source_id", "count"),
            numerator_n=("is_filled", "sum"),
            n_patients=("PID", "nunique")
        )
        .reset_index()
    )

    result["metric"] = "Completeness per form version"
    result["completeness_percent"] = (
        result["numerator_n"] / result["denominator_n"] * 100
    ).round(2)

    return result.sort_values("completeness_percent")


def form_presence_completeness(completeness):
    """
    Form-level presence metrics.
    Uses all expected form instances, including empty forms.
    """

    basic_instances = (
        completeness[completeness["form_type"].eq("basic")]
        .groupby(["PID", "form_id", "form_version"], dropna=False)
        .agg(form_has_any_value=("is_filled", "any"))
        .reset_index()
    )

    long_instances = (
        completeness[completeness["form_type"].eq("longitudinal")]
        .groupby(["PID", "episode_date", "form_id", "form_version"], dropna=False)
        .agg(form_has_any_value=("is_filled", "any"))
        .reset_index()
    )

    all_instances = pd.concat(
        [
            basic_instances.assign(form_type="basic"),
            long_instances.assign(form_type="longitudinal")
        ],
        ignore_index=True
    )

    rows = []

    rows.append({
        "metric": "Form presence completeness",
        "denominator_definition": "Expected form instances",
        "numerator_definition": "Form instances with at least one value",
        "denominator_n": len(all_instances),
        "numerator_n": all_instances["form_has_any_value"].sum(),
        "completeness_percent": percent(
            all_instances["form_has_any_value"].sum(),
            len(all_instances)
        )
    })

    rows.append({
        "metric": "Empty expected basic forms",
        "denominator_definition": "Expected basic form instances",
        "numerator_definition": "Basic form instances with no value at all",
        "denominator_n": len(basic_instances),
        "numerator_n": (~basic_instances["form_has_any_value"]).sum(),
        "completeness_percent": percent(
            (~basic_instances["form_has_any_value"]).sum(),
            len(basic_instances)
        )
    })

    rows.append({
        "metric": "Empty expected longitudinal forms",
        "denominator_definition": "Expected longitudinal form instances",
        "numerator_definition": "Episode/form instances with no value at all",
        "denominator_n": len(long_instances),
        "numerator_n": (~long_instances["form_has_any_value"]).sum(),
        "completeness_percent": percent(
            (~long_instances["form_has_any_value"]).sum(),
            len(long_instances)
        )
    })

    return pd.DataFrame(rows), all_instances


def completeness_per_patient(completeness_present_forms_only):
    """
    Completeness per patient.
    """

    result = (
        completeness_present_forms_only
        .groupby("PID", dropna=False)
        .agg(
            denominator_n=("source_id", "count"),
            numerator_n=("is_filled", "sum")
        )
        .reset_index()
    )

    result["metric"] = "Completeness per patient"
    result["completeness_percent"] = (
        result["numerator_n"] / result["denominator_n"] * 100
    ).round(2)

    return result.sort_values("completeness_percent")


def least_complete_elements(completeness_present_forms_only):
    """
    Completeness per source_id / element.
    """

    group_cols = ["source_id"]

    if "element_label" in completeness_present_forms_only.columns:
        group_cols.append("element_label")

    if "dataelement_urn" in completeness_present_forms_only.columns:
        group_cols.append("dataelement_urn")

    result = (
        completeness_present_forms_only
        .groupby(group_cols, dropna=False)
        .agg(
            denominator_n=("PID", "count"),
            numerator_n=("is_filled", "sum")
        )
        .reset_index()
    )

    result["metric"] = "Least complete elements"
    result["completeness_percent"] = (
        result["numerator_n"] / result["denominator_n"] * 100
    ).round(2)

    return result.sort_values(["completeness_percent", "denominator_n"], ascending=[True, False])


def main():
    COMPLETENESS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)



    completeness = create_completeness_table(expected, export)
    completeness_form_presence = add_form_presence_flag(completeness)

    completeness_present_forms_only = completeness_form_presence[
    completeness_form_presence["form_has_any_value"]
].copy()
    
    completeness_present_forms_only.to_csv(COMPLETENESS_OUTPUT_PATH, index=False)
    basic_empty_forms = empty_expected_forms(completeness)
    basic_empty_forms.to_csv(empty_forms_path, index=False)
    print(f"Saved {len(completeness)} completeness rows to {COMPLETENESS_OUTPUT_PATH}")
    metrics_dir = Path("results/completeness/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    summary = general_completeness_summary(completeness_present_forms_only)
    summary.to_csv(metrics_dir / "general_completeness_summary.csv", index=False)

    per_form = completeness_per_form(completeness_present_forms_only)
    per_form.to_csv(metrics_dir / "completeness_per_form.csv", index=False)

    per_form_version = completeness_per_form_version(completeness_present_forms_only)
    per_form_version.to_csv(metrics_dir / "completeness_per_form_version.csv", index=False)

    form_presence_summary, form_instances = form_presence_completeness(completeness_form_presence)
    form_presence_summary.to_csv(metrics_dir / "form_presence_summary.csv", index=False)
    form_instances.to_csv(metrics_dir / "form_instances_presence.csv", index=False)

    per_patient = completeness_per_patient(completeness_present_forms_only)
    per_patient.to_csv(metrics_dir / "completeness_per_patient.csv", index=False)

    least_complete = least_complete_elements(completeness_present_forms_only)
    least_complete.to_csv(metrics_dir / "least_complete_elements.csv", index=False)


if __name__ == "__main__":
    main()