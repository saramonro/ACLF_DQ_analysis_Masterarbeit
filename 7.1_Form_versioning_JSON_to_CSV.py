import json
import pandas as pd
from pathlib import Path

# Config
INPUT_PATH = Path("metadata/raw/forms_details.json")
OUTPUT_PATH = Path("metadata/processed/form_elements_versioned_v3.csv")
OUTPUT_PATH_EXTENDED = Path("metadata/processed/form_elements_versioned_extended.csv")
DATA_DICTIONARY_PATH = Path("metadata/processed/data_dictionary_with_versions.csv")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def extract_form_elements(input_path):
    """
    Extract data elements from the OSSE Form Editor JSON export.

    Parameters
    input_path : str or Path
        Path to the Form Editor JSON file.

    Returns
    pd.DataFrame
        Table containing versioned form metadata.
        Limitation: only contains superficial metadata for records
    """

    with open(input_path, "r", encoding="utf-8") as f:
        forms = json.load(f)

    rows = []

    for form_key, form in forms.items():

        form_id = form.get("id")
        form_version = form.get("version")
        form_label = form.get("label") or form.get("name")

        for item in form.get("items", []):

            mdr_id = item.get("mdrId")

            if not isinstance(mdr_id, str):
                continue

            # Ignore rich text but include records
            if "dataelement" in mdr_id:
                item_type= "dataelement"
            elif "record" in mdr_id:
                item_type = "record"
            else:
                continue


            rows.append({
                "form_key": form_key,
                "form_id": form_id,
                "form_version": form_version,
                "form_label": form_label,
                "urn": mdr_id,
                "type": item_type,
                "element_label": item.get("label"),
                "mandatory": item.get("mandatory"),
                "repeatable": item.get("repeatable"),
                "position": item.get("position")
            })

    return pd.DataFrame(rows)


def expand_form_versioning_with_data_dictinoary(form_items, data_dictionary):
    # Expand information on records, attaching the corresponding data elements
    # Keep direct data elements
    # Add source_id

    form_items = form_items.copy()
    data_dictionary = data_dictionary.copy()

    #Split form_id from form version
    data_dictionary[["form_id", "form_version"]] = (data_dictionary["form_id"].astype(str).str.split(":",n=1,expand=True))

    # filtering obsolete forms by removing forms not present in the data dictionary
    valid_forms = data_dictionary[["form_id"]].drop_duplicates()
    form_items["form_id"] = form_items["form_id"].astype(str)

    valid_forms["form_id"] = valid_forms["form_id"].astype(str)
    form_items = form_items.merge(valid_forms, on="form_id", how="inner")



    #standardize merge columns
    for df in [form_items, data_dictionary]:
        df["form_id"] = df["form_id"].astype(str)
        df["form_version"] = df["form_version"].astype(str)

    form_items["type"] = form_items["type"].str.lower()

    # Case 1: direct data elements only need extension of source_id
    direct = (
        form_items[form_items["type"].eq("dataelement")].copy().rename(columns={"urn" : "dataelement_urn"})
    )

    direct = direct.merge(
    data_dictionary[
        ["form_id", "dataelement_urn_mdr", "source_id"]
    ].drop_duplicates(),
    left_on=["form_id", "dataelement_urn"],
    right_on=["form_id", "dataelement_urn_mdr"],
    how="left"
)

## For mapping resolved vs unresolved
    direct["record_urn"] = pd.NA
    direct["resolution_status"] = direct["source_id"].notna().map({
        True: "direct_resolved",
        False: "direct_unresolved"
    })  

    # Case 2: records expanded by fetching data element information from data dictionary

    records = ( form_items[form_items["type"].eq("record")].copy().rename(columns={"urn":"record_urn"}))

    records = records.merge(data_dictionary[["form_id", "record_urn", "dataelement_urn", "source_id"]
                                            ], on=["form_id", "record_urn"], how= "left")
    
    records["resolution_status"] = records["source_id"].notna().map({
        True: "record_resolved",
        False: "record_unresolved"
    })  

    # Combine

    output_columns = [
        "form_key",
        "form_id",
        "form_version",
        "form_label",
        "type",
        "record_urn",
        "dataelement_urn",
        "source_id",
        "mandatory",
        "repeatable",
        "position",
        "resolution_status"
    ]

    result = pd.concat(
        [
            direct.reindex(columns=output_columns),
            records.reindex(columns=output_columns)
        ],
        ignore_index=True
    )
    resolved = result[result["source_id"].notna()].copy()
    unresolved = result[result["source_id"].isna()].copy()

    resolved.to_csv(
        "metadata/processed/form_elements_versioned_resolved_only.csv",
        index=False
    )

    unresolved.to_csv(
     "metadata/processed/form_elements_versioned_unresolved.csv",
     index=False
    )
    return result

def main():

    df_form_elements = extract_form_elements(INPUT_PATH)

    df_form_elements.to_csv(OUTPUT_PATH, index=False)

    data_dictionary = pd.read_csv(DATA_DICTIONARY_PATH, dtype="object", sep=";")

    df_form_elements_extended_records = expand_form_versioning_with_data_dictinoary(df_form_elements, data_dictionary)

    df_form_elements_extended_records.to_csv(OUTPUT_PATH_EXTENDED, index=False)

    print(f"Saved {len(df_form_elements)} rows.")


if __name__ == "__main__":
    main()