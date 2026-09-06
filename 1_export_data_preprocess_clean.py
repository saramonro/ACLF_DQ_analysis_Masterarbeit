"""
Preprocess the raw OSSE export into a cleaned long-format export.

This script creates data/processed/export_long_clean.csv.

Main steps:
- Load the raw OSSE export and the processed data dictionary.
- Standardize column names.
- Use the data dictionary to separate basic and longitudinal data elements.
- Remove test-location rows and "No Data" rows.
- Remove rows/patients without real registry data.
- Forward-fill episode context within patients.
- Create separate long-format outputs for basic and longitudinal variables.
- Remove duplicate empty rows while preserving true missingness.
- Combine both outputs into export_long_clean.
"""

import csv
from pathlib import Path

import pandas as pd


# Paths will be added to config.py later
DATA_PATH = Path("data/raw/ACLF_2026-02-12_MDAT.csv")
DATA_DICTIONARY_PATH = Path("metadata/processed/data_dictionary_with_versions.csv")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "export_long_clean.csv"


TECHNICAL_COLUMNS = [
    "PID",
    "Location",
    "Episode",
    "Episode_Date",
    "Episode_Description",
    "IX",
    "patient repeat number",
    "Unique ID (Form_Record_DataElement):",
]


def load_raw_export(path):
    """Load the raw OSSE export without the metadata rows above the header."""
    df = pd.read_csv(path, dtype="object", sep=";", skiprows=7)
    df.columns = df.columns.str.strip()
    return df


def load_data_dictionary(path):
    """Load the processed data dictionary used to identify basic and longitudinal elements."""
    dd = pd.read_csv(path, dtype="object", sep=";")
    dd.columns = dd.columns.str.strip()
    return dd


# Rename columns to match the naming convention used by the pipeline
def rename_columns(df):
    df = df.rename(
        columns={
            "Episode number": "Episode",
            "Episode date": "Episode_Date",
            "Episode description": "Episode_Description",
        }
    )
    return df


# Standardize key identifiers before grouping/merging/melting
def clean_identifier_columns(df, dd):
    df = df.copy()
    dd = dd.copy()

    for col in ["PID", "Episode", "Episode_Date"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    dd["source_id"] = dd["source_id"].astype(str).str.strip()
    dd["form_type"] = dd["form_type"].astype(str).str.strip().str.lower()

    return df, dd


# Use the data dictionary to determine which source IDs belong to basic or longitudinal forms
def get_source_ids_by_form_type(dd, data_columns):
    basic_ids = (
        dd.loc[dd["form_type"].eq("basic"), "source_id"]
        .dropna()
        .unique()
        .tolist()
    )

    longitudinal_ids = (
        dd.loc[dd["form_type"].eq("longitudinal"), "source_id"]
        .dropna()
        .unique()
        .tolist()
    )

    data_columns = set(data_columns)
    basic_ids_in_data = [source_id for source_id in basic_ids if source_id in data_columns]
    longitudinal_ids_in_data = [source_id for source_id in longitudinal_ids if source_id in data_columns]

    print(f"Basic source IDs in export: {len(basic_ids_in_data)}")
    print(f"Longitudinal source IDs in export: {len(longitudinal_ids_in_data)}")
    print(f"Basic source IDs missing from export: {len(set(basic_ids) - set(basic_ids_in_data))}")
    print(
        "Longitudinal source IDs missing from export: "
        f"{len(set(longitudinal_ids) - set(longitudinal_ids_in_data))}"
    )

    return basic_ids_in_data, longitudinal_ids_in_data


# Drop Test Patients / rows from Test Locations
def drop_test_data(df):
    if "Location" not in df.columns:
        return df

    mask_test = (
        df["Location"]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.contains("test location", na=False)
    )

    print(f"Dropped {mask_test.sum()} test rows")
    return df.loc[~mask_test].copy()


# Drop rows explicitly marked as No Data in the OSSE export
def drop_no_data_rows(df):
    uid_col = "Unique ID (Form_Record_DataElement):"

    if uid_col not in df.columns:
        return df

    mask_no_data = (
        df[uid_col]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("no data")
    )

    print(f"Dropped {mask_no_data.sum()} 'No Data' rows")
    return df.loc[~mask_no_data].copy()


# Treat empty strings as missing values in selected columns
def replace_empty_strings_with_na(df, columns):
    df = df.copy()
    existing_columns = [col for col in columns if col in df.columns]
    df[existing_columns] = df[existing_columns].replace({"": pd.NA, " ": pd.NA, "nan": pd.NA})
    return df


# Forward-fill episode context within each patient, because repeat rows may omit episode fields
def forward_fill_episode_context(df):
    df = replace_empty_strings_with_na(df, ["Episode", "Episode_Date"])

    df[["Episode", "Episode_Date"]] = (
        df.groupby("PID")[["Episode", "Episode_Date"]].ffill()
    )

    return df


# Keep only rows and patients with at least one actual registry data value
def drop_rows_and_patients_without_data(df, source_ids):
    data_cols = [col for col in source_ids if col in df.columns]

    if not data_cols:
        raise ValueError("No source_id columns from the data dictionary were found in the raw export.")

    df = replace_empty_strings_with_na(df, data_cols)

    df = df.loc[df[data_cols].notna().any(axis=1)].copy()

    valid_pids = (
        df.groupby("PID")[data_cols]
        .apply(lambda patient_df: patient_df.notna().any().any())
    )
    valid_pids = valid_pids.loc[valid_pids].index

    return df.loc[df["PID"].isin(valid_pids)].copy()


# Melt basic variables: for these, the true identifier is PID only
def create_basic_long(df, basic_ids_in_data):
    basic_long = pd.melt(
        df,
        id_vars=["PID"],
        value_vars=basic_ids_in_data,
        var_name="source_id",
        value_name="source_value",
    )

    basic_long["source_value"] = basic_long["source_value"].replace({"": pd.NA, " ": pd.NA})

    # Drop empty duplicate rows only where the same PID/source_id already has a value.
    # This preserves true missingness where no value exists at all.
    basic_long["has_any_value"] = basic_long.groupby(["PID", "source_id"])[
        "source_value"
    ].transform(lambda values: values.notna().any())

    basic_long_clean = basic_long.loc[
        basic_long["source_value"].notna() | ~basic_long["has_any_value"]
    ].copy()

    basic_long_clean = basic_long_clean.drop_duplicates(
        subset=["PID", "source_id", "source_value"]
    )

    basic_long_clean["Episode"] = "basic"
    basic_long_clean["Episode_Date"] = pd.NA
    basic_long_clean["IX"] = 1

    return basic_long_clean[
        ["PID", "Episode", "Episode_Date", "IX", "source_id", "source_value"]
    ]


# Melt longitudinal variables: for these, the identifier is PID + Episode + Episode_Date
def create_longitudinal_long(df, longitudinal_ids_in_data):
    longitudinal_source = df.dropna(subset=["Episode", "Episode_Date"]).copy()

    longitudinal_long = pd.melt(
        longitudinal_source,
        id_vars=["PID", "Episode", "Episode_Date"],
        value_vars=longitudinal_ids_in_data,
        var_name="source_id",
        value_name="source_value",
    )

    long_key = ["PID", "Episode", "Episode_Date", "source_id"]

    longitudinal_long["source_value"] = longitudinal_long["source_value"].replace(
        {"": pd.NA, " ": pd.NA}
    )

    # Drop empty duplicate rows only where the same longitudinal key already has a value.
    # This preserves true missingness where no value exists at all.
    longitudinal_long["has_any_value"] = longitudinal_long.groupby(long_key)[
        "source_value"
    ].transform(lambda values: values.notna().any())

    longitudinal_long_clean = longitudinal_long.loc[
        longitudinal_long["source_value"].notna()
        | ~longitudinal_long["has_any_value"]
    ].copy()

    longitudinal_long_clean["IX"] = (
        longitudinal_long_clean.groupby(long_key).cumcount().add(1)
    )

    return longitudinal_long_clean[
        ["PID", "Episode", "Episode_Date", "IX", "source_id", "source_value"]
    ]


# Build the cleaned long-format export
def create_export_long_clean(df, basic_ids_in_data, longitudinal_ids_in_data):
    all_source_ids = basic_ids_in_data + longitudinal_ids_in_data

    df = drop_test_data(df)
    df = drop_no_data_rows(df)
    df = forward_fill_episode_context(df)
    df = drop_rows_and_patients_without_data(df, all_source_ids)

    basic_long_clean = create_basic_long(df, basic_ids_in_data)
    longitudinal_long_clean = create_longitudinal_long(df, longitudinal_ids_in_data)

    export_long_clean = pd.concat(
        [basic_long_clean, longitudinal_long_clean],
        ignore_index=True,
    )

    return export_long_clean


def main():
    data_original = load_raw_export(DATA_PATH)
    dd = load_data_dictionary(DATA_DICTIONARY_PATH)

    data_cleaned = rename_columns(data_original)
    data_cleaned, dd = clean_identifier_columns(data_cleaned, dd)

    basic_ids_in_data, longitudinal_ids_in_data = get_source_ids_by_form_type(
        dd,
        data_cleaned.columns,
    )

    export_long_clean = create_export_long_clean(
        data_cleaned,
        basic_ids_in_data,
        longitudinal_ids_in_data,
    )

    print(f"export_long_clean rows: {export_long_clean.shape[0]}")
    print(f"export_long_clean columns: {export_long_clean.shape[1]}")
    print(f"Unique PIDs: {export_long_clean['PID'].nunique()}")
    print(f"Unique source IDs: {export_long_clean['source_id'].nunique()}")

    export_long_clean.to_csv(
        OUTPUT_PATH,
        index=False,
        sep=";",
        quoting=csv.QUOTE_ALL,
        encoding="UTF-8",
    )

    print(f"Saved cleaned long export to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
