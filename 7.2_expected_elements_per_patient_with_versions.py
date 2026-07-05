import pandas as pd
from pathlib import Path


BASIC_VERSIONS_PATH = Path("metadata/raw/aclf_caseforms.csv")
LONGITUDINAL_VERSIONS_PATH = Path("metadata/raw/aclf_episodeforms.csv")
FORM_ELEMENTS_PATH = Path("metadata/processed/form_elements_versioned_resolved_only.csv")

OUTPUT_PATH = Path("metadata/processed/expected_elements.csv")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


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

    expected_longitudinal.to_csv(
        OUTPUT_PATH,
        index=False
    )
    expected_basic.to_csv(
        OUTPUT_PATH,
        index=False
    )

    expected_basic["form_type"] = "basic"
    expected_longitudinal["form_type"] = "longitudinal"

    expected_elements = pd.concat(
        [expected_basic, expected_longitudinal],
        ignore_index=True
    )

    return expected_elements


def main():

    basic_versions = pd.read_csv(
        BASIC_VERSIONS_PATH,
        dtype="object"
    )

    longitudinal_versions = pd.read_csv(
        LONGITUDINAL_VERSIONS_PATH,
        dtype="object"
    )

    form_elements_versioned = pd.read_csv(
        FORM_ELEMENTS_PATH,
        dtype="object"
    )

    expected_elements = create_expected_elements(
        basic_versions,
        longitudinal_versions,
        form_elements_versioned
    )

    expected_elements.to_csv(
        OUTPUT_PATH,
        index=False
    )



    print(f"Saved {len(expected_elements)} expected elements.")


if __name__ == "__main__":
    main()