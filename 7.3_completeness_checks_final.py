from pathlib import Path
import pandas as pd


EXPECTED_ELEMENTS_PATH = Path("metadata/processed/expected_elements.csv")
EXPORT_PATH = Path("data/processed/export_long_clean.csv")
CORE_ELEMENTS_PATH = Path("metadata/raw/core_elements.csv")
OUTPUT_DIR = Path("results/completeness")
COMPLETENESS_OUTPUT_PATH = OUTPUT_DIR / "completeness_row_level.csv"


def create_completeness_table(expected, export):
    """Join expected data elements per patient to their source values."""

    expected = expected.copy()
    export = export.copy()
    export = export.rename(columns={"Episode_Date": "episode_date"})

    # Include only patients present in the clean export (remove test patients).
    valid_pids = export["PID"].dropna().astype(str).unique()
    expected = expected[expected["PID"].astype(str).isin(valid_pids)].copy()

    expected_basic = expected[expected["form_type"].eq("basic")].copy()
    expected_long = expected[expected["form_type"].eq("longitudinal")].copy()

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


def add_form_presence_flag(completeness):
    """Flag forms where at least one expected element has a value."""

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

    return pd.concat(
        [completeness_basic, completeness_long],
        ignore_index=True
    )


def add_core_flag(completeness, core_elements):
    """Add a version-aware core flag to the completeness table."""

    completeness = completeness.copy()
    core_elements = core_elements.copy()

    completeness["dataelement_base_urn"] = (
        completeness["dataelement_urn"]
        .astype("string")
        .str.replace(r":\d+$", "", regex=True)
    )
    core_elements["dataelement_base_urn"] = (
        core_elements["dataelement_urn"]
        .astype("string")
        .str.replace(r":\d+$", "", regex=True)
    )

    merge_columns = ["form_id", "form_version", "dataelement_base_urn"]
    for df in [completeness, core_elements]:
        df["form_id"] = df["form_id"].astype("string")
        df["form_version"] = df["form_version"].astype("string")

    core_elements = core_elements[merge_columns].drop_duplicates()
    core_elements["is_core"] = True

    completeness = completeness.merge(
        core_elements,
        on=merge_columns,
        how="left"
    )
    completeness["is_core"] = completeness["is_core"].fillna(False).astype(bool)

    return completeness


def empty_expected_forms(completeness):
    """Create tables of empty expected basic and longitudinal forms."""

    basic_forms = (
        completeness[completeness["form_type"].eq("basic")]
        .groupby(["PID", "form_id", "form_version"], dropna=False)
        .agg(
            form_has_any_value=("is_filled", "any"),
            n_expected_elements=("source_id", "count"),
            n_filled_elements=("is_filled", "sum")
        )
        .reset_index()
    )

    longitudinal_forms = (
        completeness[completeness["form_type"].eq("longitudinal")]
        .groupby(
            ["PID", "episode_date", "form_id", "form_version"],
            dropna=False
        )
        .agg(
            form_has_any_value=("is_filled", "any"),
            n_expected_elements=("source_id", "count"),
            n_filled_elements=("is_filled", "sum")
        )
        .reset_index()
    )

    empty_basic = basic_forms[~basic_forms["form_has_any_value"]].copy()
    empty_longitudinal = longitudinal_forms[
        ~longitudinal_forms["form_has_any_value"]
    ].copy()

    return empty_basic, empty_longitudinal


def percent(numerator, denominator):
    if denominator == 0:
        return pd.NA
    return round((numerator / denominator) * 100, 2)


def completeness_summary(completeness_present_forms_only):
    """Summarize general, core and mandatory element completeness."""

    overall = completeness_present_forms_only
    basic = overall[overall["form_type"].eq("basic")]
    longitudinal = overall[overall["form_type"].eq("longitudinal")]

    overall_mandatory = (
        overall["mandatory"].astype("string").str.strip().str.lower()
        .isin(["true", "1", "yes"])
    )
    basic_mandatory = (
        basic["mandatory"].astype("string").str.strip().str.lower()
        .isin(["true", "1", "yes"])
    )
    longitudinal_mandatory = (
        longitudinal["mandatory"].astype("string").str.strip().str.lower()
        .isin(["true", "1", "yes"])
    )

    rows = [
        {
            "metric": "Overall element completeness",
            "general_completeness_percent": percent(
                overall["is_filled"].sum(), len(overall)
            ),
            "core_completeness_percent": percent(
                overall.loc[overall["is_core"], "is_filled"].sum(),
                overall["is_core"].sum()
            ),
            "mandatory_completeness_percent": percent(
                overall.loc[overall_mandatory, "is_filled"].sum(),
                overall_mandatory.sum()
            )
        },
        {
            "metric": "Basic form completeness",
            "general_completeness_percent": percent(
                basic["is_filled"].sum(), len(basic)
            ),
            "core_completeness_percent": percent(
                basic.loc[basic["is_core"], "is_filled"].sum(),
                basic["is_core"].sum()
            ),
            "mandatory_completeness_percent": percent(
                basic.loc[basic_mandatory, "is_filled"].sum(),
                basic_mandatory.sum()
            )
        },
        {
            "metric": "Longitudinal form completeness",
            "general_completeness_percent": percent(
                longitudinal["is_filled"].sum(), len(longitudinal)
            ),
            "core_completeness_percent": percent(
                longitudinal.loc[
                    longitudinal["is_core"], "is_filled"
                ].sum(),
                longitudinal["is_core"].sum()
            ),
            "mandatory_completeness_percent": percent(
                longitudinal.loc[
                    longitudinal_mandatory, "is_filled"
                ].sum(),
                longitudinal_mandatory.sum()
            )
        }
    ]

    return pd.DataFrame(rows)


def form_presence_summary(completeness):
    """Summarize registry-level expected form presence."""

    basic_instances = (
        completeness[completeness["form_type"].eq("basic")]
        .groupby(["PID", "form_id", "form_version"], dropna=False)
        ["is_filled"].any()
    )
    longitudinal_instances = (
        completeness[completeness["form_type"].eq("longitudinal")]
        .groupby(
            ["PID", "episode_date", "form_id", "form_version"],
            dropna=False
        )["is_filled"].any()
    )
    all_instances = pd.concat([basic_instances, longitudinal_instances])

    rows = [
        {
            "metric": "Form presence completeness",
            "denominator_n": len(all_instances),
            "numerator_n": all_instances.sum(),
            "percent": percent(all_instances.sum(), len(all_instances))
        },
        {
            "metric": "Empty expected basic forms",
            "denominator_n": len(basic_instances),
            "numerator_n": (~basic_instances).sum(),
            "percent": percent((~basic_instances).sum(), len(basic_instances))
        },
        {
            "metric": "Empty expected longitudinal forms",
            "denominator_n": len(longitudinal_instances),
            "numerator_n": (~longitudinal_instances).sum(),
            "percent": percent(
                (~longitudinal_instances).sum(),
                len(longitudinal_instances)
            )
        }
    ]

    return pd.DataFrame(rows)

def completeness_per_patient(df):
    """Calculate general and core completeness per patient."""

    general = (
        df.groupby("PID", dropna=False)
        .agg(
            general_expected_n=("source_id", "count"),
            general_filled_n=("is_filled", "sum")
        )
        .reset_index()
    )
    general["general_completeness_percent"] = (
        general["general_filled_n"] / general["general_expected_n"] * 100
    ).round(2)

    core = (
        df[df["is_core"]]
        .groupby("PID", dropna=False)
        .agg(
            core_expected_n=("source_id", "count"),
            core_filled_n=("is_filled", "sum")
        )
        .reset_index()
    )
    core["core_completeness_percent"] = (
        core["core_filled_n"] / core["core_expected_n"] * 100
    ).round(2)

    result = general.merge(core, on="PID", how="left")
    result[["core_expected_n", "core_filled_n"]] = result[
        ["core_expected_n", "core_filled_n"]
    ].fillna(0).astype(int)

    return result.sort_values("general_completeness_percent")


def completeness_per_form(df):
    """Calculate general and core completeness per form."""

    group_columns = ["form_id", "form_label"]
    general = (
    df.groupby("form_id", dropna=False)
    .agg(
        form_label=("form_label", "first"),
        general_expected_n=("source_id", "count"),
        general_filled_n=("is_filled", "sum"),
        n_patients=("PID", "nunique")
    )
    .reset_index()
)
    general["general_completeness_percent"] = (
        general["general_filled_n"] / general["general_expected_n"] * 100
    ).round(2)

    core = (
    df[df["is_core"]]
    .groupby("form_id", dropna=False)
    .agg(
        core_expected_n=("source_id", "count"),
        core_filled_n=("is_filled", "sum")
    )
    .reset_index()
)
    core["core_completeness_percent"] = (
        core["core_filled_n"] / core["core_expected_n"] * 100
    ).round(2)

    result = general.merge(core, on="form_id", how="left")
    result[["core_expected_n", "core_filled_n"]] = result[
        ["core_expected_n", "core_filled_n"]
    ].fillna(0).astype(int)

    columns = [
        "form_id", "form_label", "general_expected_n", "general_filled_n",
        "general_completeness_percent", "core_expected_n", "core_filled_n",
        "core_completeness_percent", "n_patients"
    ]
    return result[columns].sort_values("general_completeness_percent")


def completeness_per_form_version(df):
    """Calculate general and core completeness per form version."""

    group_columns = ["form_id", "form_version"]
    general = (
        df.groupby(group_columns, dropna=False)
        .agg(
            general_expected_n=("source_id", "count"),
            general_filled_n=("is_filled", "sum"),
            n_patients=("PID", "nunique")
        )
        .reset_index()
    )
    general["general_completeness_percent"] = (
        general["general_filled_n"] / general["general_expected_n"] * 100
    ).round(2)

    core = (
        df[df["is_core"]]
        .groupby(group_columns, dropna=False)
        .agg(
            core_expected_n=("source_id", "count"),
            core_filled_n=("is_filled", "sum")
        )
        .reset_index()
    )
    core["core_completeness_percent"] = (
        core["core_filled_n"] / core["core_expected_n"] * 100
    ).round(2)

    result = general.merge(core, on=group_columns, how="left")
    result[["core_expected_n", "core_filled_n"]] = result[
        ["core_expected_n", "core_filled_n"]
    ].fillna(0).astype(int)

    columns = [
        "form_id", "form_version", "general_expected_n", "general_filled_n",
        "general_completeness_percent", "core_expected_n", "core_filled_n",
        "core_completeness_percent", "n_patients"
    ]
    return result[columns].sort_values("general_completeness_percent")


def completeness_per_element(df):
    """Calculate general and core completeness per source element."""

    general = (
        df.groupby("source_id", dropna=False)
        .agg(
            general_expected_n=("PID", "count"),
            general_filled_n=("is_filled", "sum")
        )
        .reset_index()
    )
    general["general_completeness_percent"] = (
        general["general_filled_n"] / general["general_expected_n"] * 100
    ).round(2)

    core = (
        df[df["is_core"]]
        .groupby("source_id", dropna=False)
        .agg(
            core_expected_n=("PID", "count"),
            core_filled_n=("is_filled", "sum")
        )
        .reset_index()
    )
    core["core_completeness_percent"] = (
        core["core_filled_n"] / core["core_expected_n"] * 100
    ).round(2)

    result = general.merge(core, on="source_id", how="left")
    result[["core_expected_n", "core_filled_n"]] = result[
        ["core_expected_n", "core_filled_n"]
    ].fillna(0).astype(int)

    if "element_label" in df.columns:
        labels = (
            df[["source_id", "element_label"]]
            .dropna(subset=["element_label"])
            .drop_duplicates("source_id")
        )
        result = result.merge(labels, on="source_id", how="left")
        columns = ["source_id", "element_label"] + [
            column for column in result.columns
            if column not in ["source_id", "element_label"]
        ]
        result = result[columns]

    return result.sort_values(
        ["general_completeness_percent", "general_expected_n"],
        ascending=[True, False]
    )


def main():
    expected = pd.read_csv(EXPECTED_ELEMENTS_PATH, sep=";", dtype="object")
    export = pd.read_csv(EXPORT_PATH, sep=";", dtype="object")
    core_elements = pd.read_csv(CORE_ELEMENTS_PATH, sep=";",dtype="object")

    completeness = create_completeness_table(expected, export)
    completeness = add_core_flag(completeness, core_elements)
    completeness_form_presence = add_form_presence_flag(completeness)
    completeness_present_forms_only = completeness_form_presence[
        completeness_form_presence["form_has_any_value"]
    ].copy()

    summary = completeness_summary(completeness_present_forms_only)
    presence_summary = form_presence_summary(completeness_form_presence)
    per_patient = completeness_per_patient(completeness_present_forms_only)
    per_form = completeness_per_form(completeness_present_forms_only)
    per_form_version = completeness_per_form_version(
        completeness_present_forms_only
    )
    per_element = completeness_per_element(completeness_present_forms_only)
    empty_basic, empty_longitudinal = empty_expected_forms(
        completeness_form_presence
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    completeness_present_forms_only.to_csv(COMPLETENESS_OUTPUT_PATH, index=False)
    summary.to_csv(OUTPUT_DIR / "completeness_summary.csv", sep=";", index=False)
    presence_summary.to_csv(
        OUTPUT_DIR / "form_presence_summary.csv", sep=";",
        index=False
    )
    per_patient.to_csv(OUTPUT_DIR / "completeness_per_patient.csv",sep=";", index=False)
    per_form.to_csv(OUTPUT_DIR / "completeness_per_form.csv",sep=";", index=False)
    per_form_version.to_csv(
        OUTPUT_DIR / "completeness_per_form_version.csv",sep=";",
        index=False
    )
    per_element.to_csv(OUTPUT_DIR / "completeness_per_element.csv",sep=";", index=False)
    empty_basic.to_csv(OUTPUT_DIR / "empty_basic_forms.csv",sep=";", index=False)
    empty_longitudinal.to_csv(
        OUTPUT_DIR / "empty_longitudinal_forms.csv",sep=";",
        index=False
    )

    print(f"Saved {len(completeness_present_forms_only)} completeness rows.")


if __name__ == "__main__":
    main()


