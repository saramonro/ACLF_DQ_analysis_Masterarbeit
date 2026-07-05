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


if __name__ == "__main__":
    main()