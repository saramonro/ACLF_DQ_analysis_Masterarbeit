import pandas as pd
from pathlib import Path


BASIC_VERSIONS_PATH = Path("metadata/raw/aclf_caseforms.csv")
LONGITUDINAL_VERSIONS_PATH = Path("metadata/raw/aclf_episodeforms.csv")
FORM_ELEMENTS_PATH = Path("metadata/processed/form_elements_versioned_resolved_only.csv")

OUTPUT_PATH = Path("metadata/processed/expected_elements.csv")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
#summary
FORM_ITEMS_PATH = Path("metadata/processed/form_elements_versioned_v3.csv")
FORM_ELEMENTS_EXTENDED_PATH = Path("metadata/processed/form_elements_versioned_extended.csv")
SUMMARY_OUTPUT_PATH = Path("metadata/processed/summaries/expected_elements_summary.csv")
SUMMARY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def create_expected_elements(
    basic_versions,
    longitudinal_versions,
    form_elements_versioned
):
    """
    Expand patient-form-version assignments into
    patient-expected-element assignments.
    """

    basic_versions = basic_versions.rename(
        columns={
            "version": "form_version",
            "episode_name": "episode_date",
            "patient_id": "PID"
        }
    )

    longitudinal_versions = longitudinal_versions.rename(
        columns={
            "version": "form_version",
            "episode_name": "episode_date",
            "patient_id": "PID"
        }
    )


    expected_basic = basic_versions.merge(
        form_elements_versioned,
        on=["form_id", "form_version"],
        how="left"
    )


    expected_longitudinal = longitudinal_versions.merge(
        form_elements_versioned,
        on=["form_id", "form_version"],
        how="left"
    )

    expected_longitudinal.to_csv(OUTPUT_PATH, sep=";", index=False)
    expected_basic.to_csv(OUTPUT_PATH, sep=";", index=False)
    expected_basic["form_type"] = "basic"
    expected_longitudinal["form_type"] = "longitudinal"

    expected_elements = pd.concat(
        [expected_basic, expected_longitudinal],
        ignore_index=True
    )
    unique_form_versions = (
    expected_elements[
        ["form_id", "form_version"]
    ]
    .drop_duplicates()
    .sort_values(["form_id", "form_version"])
)
    unique_form_versions.to_csv(
    "metadata/processed/form_versions_present.csv", sep=";",
    index=False
)


    return expected_elements

def create_expected_elements_summary(
    form_items,
    form_elements_extended,
    form_elements_resolved_only,
    expected_basic,
    expected_longitudinal,
):
    """
    Create summary metrics for version-aware expected-elements preprocessing.
    """

    rows = []

    rows.append({
        "metric": "form_versions_found",
        "value": form_items[["form_id", "form_version"]].drop_duplicates().shape[0]
    })

    rows.append({
        "metric": "form_items_extracted_from_json",
        "value": len(form_items)
    })

    rows.append({
        "metric": "direct_dataelement_items",
        "value": form_items["type"].astype(str).str.lower().eq("dataelement").sum()
    })

    rows.append({
        "metric": "record_items",
        "value": form_items["type"].astype(str).str.lower().eq("record").sum()
    })

    rows.append({
        "metric": "resolved_items",
        "value": form_elements_extended["source_id"].notna().sum()
    })

    rows.append({
        "metric": "unresolved_items",
        "value": form_elements_extended["source_id"].isna().sum()
    })

    rows.append({
        "metric": "resolved_items_used_for_expected_elements",
        "value": len(form_elements_resolved_only)
    })

    rows.append({
        "metric": "expected_basic_elements",
        "value": len(expected_basic)
    })

    rows.append({
        "metric": "expected_longitudinal_elements",
        "value": len(expected_longitudinal)
    })

    rows.append({
        "metric": "total_expected_elements",
        "value": len(expected_basic) + len(expected_longitudinal)
    })

    return pd.DataFrame(rows)

def main():

    basic_versions = pd.read_csv(BASIC_VERSIONS_PATH, dtype="object")
    longitudinal_versions = pd.read_csv(LONGITUDINAL_VERSIONS_PATH,  dtype="object")
    form_elements_versioned = pd.read_csv(FORM_ELEMENTS_PATH, dtype="object")

    form_items = pd.read_csv(FORM_ITEMS_PATH, sep=";", dtype="object")
    form_elements_extended = pd.read_csv(FORM_ELEMENTS_EXTENDED_PATH, sep=";", dtype="object")

    expected_elements = create_expected_elements(
        basic_versions,
        longitudinal_versions,
        form_elements_versioned
    )

    expected_elements.to_csv(OUTPUT_PATH, sep=";", index=False)

    expected_basic = expected_elements[
        expected_elements["form_type"].eq("basic")
    ].copy()

    expected_longitudinal = expected_elements[
        expected_elements["form_type"].eq("longitudinal")
    ].copy()

    summary = create_expected_elements_summary(
        form_items=form_items,
        form_elements_extended=form_elements_extended,
        form_elements_resolved_only=form_elements_versioned,
        expected_basic=expected_basic,
        expected_longitudinal=expected_longitudinal,
    )

    summary.to_csv(SUMMARY_OUTPUT_PATH, sep=";", index=False)

    print(f"Saved {len(expected_elements)} expected elements.")
    print(f"Saved versioning summary to {SUMMARY_OUTPUT_PATH}")


if __name__ == "__main__":
    main()