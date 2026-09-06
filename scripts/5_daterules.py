import sys
import pandas as pd
from pathlib import Path


'''
Temporal Plausibility

This module assesses if values in date variables conform to the constraints defined in the contextual metadata object "date_rules.csv"

Required inputs:
Export long
date_rules.csv filled out (template can be found under metadata/templates)

The script works by:
- identifying date variables in the date rules
- parsing their values according to their individual date formats
- preparing comparison dates (DOB, today, episode, other variables)
- comparing values according to rules
- collecting violations + summaries as outputs


'''



# Config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Input paths
#DATA_DICTIONARY_PATH = PROJECT_ROOT / "metadata" / "processed" / "data_dictionary.csv"
EXPORT_LONG_PATH = PROJECT_ROOT / "data" / "processed" / "export_long_clean.csv"
DATE_RULES_PATH = PROJECT_ROOT / "metadata" / "contextual" / "date_rules.csv"

# Output Paths
OUTPUT_DIR = PROJECT_ROOT / "results" / "dates"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATE_RESULTS_OUTPUT_PATH = OUTPUT_DIR / "date_rule_results.csv"
DATE_SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "date_rule_summary.csv"
# Registry specific configs - check about DOB as MDAT 
from config import DATE_OF_BIRTH_SOURCE_ID

# Helper functions
def load_csv(path):
    return pd.read_csv(path, dtype="object", sep=";")


def has_non_empty_value(series):
    return series.notna() & series.astype(str).str.strip().ne("")


def make_violation(df, rule_id, rule_type, expected, observed_col="source_value"):
    out = df.copy()
    out["rule_id"] = rule_id
    out["rule_type"] = rule_type
    out["expected"] = expected
    out["observed"] = out[observed_col]
    return out

def make_summary(
    rule_type,
    rule_id,
    assessed_elements,
    violations,
):
    return {
        "rule_type": rule_type,
        "rule_id": rule_id,
        "assessed_elements": int(assessed_elements),
        "total_violations": int(len(violations)),
    }


#  inner merge to keep only values from variables in date_rules and append the rule metadata.
def merge_rules_export(export_long, date_rules):
    date_rules_checks = export_long.merge(date_rules, on="source_id", how="inner")
    return date_rules_checks



# turn date formats into parseable pandas formats. adds prefix day to date formats without days.
def get_date_parse_config(data_format):
    configs = {
        "DD.MM.YYYY": {
            "parser_format": "%d.%m.%Y",
            "prefix": None,
        },
        "YYYY-MM-DD": {
            "parser_format": "%Y-%m-%d",
            "prefix": None,
        },
        "MM.YYYY": {
            "parser_format": "%d.%m.%Y",
            "prefix": "01.",
        },
        "MM-YYYY": {
            "parser_format": "%d-%m-%Y",
            "prefix": "01-",
        },
        "MM-DD-YYYY": {
            "parser_format": "%m-%d-%Y",
            "prefix": None,
        },
    }

    return configs.get(str(data_format).strip())


# parses dates and converts to pandas datetime format

def parse_source_dates(df):
    
    # parses source_value into source_value_parsed according to each row's data_format
    ## rows with unknown data_format remain NaT
    
    df = df.copy()
    df["source_value_parsed"] = pd.NaT
    df["data_format"] = df["data_format"].astype(str).str.strip()
    
    rows_with_value = df[has_non_empty_value(df["source_value"])].copy()

    for data_format, group in rows_with_value.groupby("data_format", dropna=False):
        config = get_date_parse_config(data_format)

        if config is None:
            continue

        values = group["source_value"].astype(str).str.strip()

        if config["prefix"] is not None:
            values = config["prefix"] + values

        parsed = pd.to_datetime(
            values,
            format=config["parser_format"],
            errors="coerce"
        )

        df.loc[group.index, "source_value_parsed"] = parsed

    return df


def prepare_date_rule_checks(df_export, date_rules):
    
    # Creates the working dataframe used by all date checks.
    
    df = merge_rules_export(df_export, date_rules)
    df = parse_source_dates(df)
    
    # Parses Episode_Date to numeric in export_long_clean.csv , format is DD/MM/YYYY
    df["episode_date_parsed"] = pd.to_datetime(
        df["Episode_Date"].astype(str).str.strip(),
        format="%d/%m/%Y",
        errors="coerce",
    )

    return df



### Rule Checks
## DOB: expected is target date >= DOB
### This has to be reassessed for registries where DOB is not MDAT. Currently the DOB is indirectly taken from the export into the dataframe.
def not_before_dob(df):

    # add DOB to patient rows
    dates_of_birth = df.loc[
        df["source_id"] == DATE_OF_BIRTH_SOURCE_ID, ["PID", "source_value_parsed"]
            ].dropna(subset=["source_value_parsed"]).drop_duplicates(subset=["PID"]).rename(columns={"source_value_parsed":"dob_parsed"})

    df=df.merge(dates_of_birth, on=["PID"], how="left")


    # Observations that can actually be assessed by this rule -Y count as denominator
    # If a patient lacks DOB, then values cannot be assessed
    ## Missing reference dates is not counted as a violation 
    assessment_mask = (
        df["notBeforeDOB"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
        & df["source_value_parsed"].notna()
        & df["dob_parsed"].notna()
    )

    assessed_elements = int(assessment_mask.sum())

    # Of the assessed instances, identify failures
    violation_mask = (
        assessment_mask
        & (df["source_value_parsed"] < df["dob_parsed"])
    )

    failed = df.loc[violation_mask].copy()

    violations = make_violation(
        failed,
        rule_id="not_before_dob",
        rule_type="temporal_plausibility",
        expected="date is not before DOB",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_before_dob",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary

''' outdated
def not_after_death(df):

    # add date of death to patient rows
    dates_of_death=df.loc[df["source_id"]==DATE_OF_DEATH_SOURCE_ID,
                          ["PID", "source_value_parsed"]
                          ].dropna(subset=["source_value_parsed"]).drop_duplicates(subset=["PID"]).rename(columns={"source_value_parsed":"date_of_death_parsed"})
    
    df = df.merge(dates_of_death, on=["PID"], how= "left")

    assessment_mask = (
        df["notAfterDeath"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
        & df["source_value_parsed"].notna()
        & df["date_of_death_parsed"].notna()
    )

    assessed_elements = int(assessment_mask.sum())

    violation_mask = (
        assessment_mask
        & (
            df["source_value_parsed"]
            > df["date_of_death_parsed"]
        )
    )

    failed = df.loc[violation_mask].copy()

    violations = make_violation(
        failed,
        rule_id="not_after_death",
        rule_type="temporal_plausibility",
        expected="date is not after death",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_after_death",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary
'''

# Not in Future
## Expected is target <= today
### Should be reassessed to compare against export date or data collection date.
def not_in_future(df):
    today = pd.Timestamp.today().normalize() # Todays date without time, current timezone

    assessment_mask = (
        df["notFuture"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
        & df["source_value_parsed"].notna()
    )

    assessed_elements = int(assessment_mask.sum())

    violation_mask = (
        assessment_mask
        & (df["source_value_parsed"] > today)
    )

    failed = df.loc[violation_mask].copy()

    violations = make_violation(
        failed,
        rule_id="not_in_future",
        rule_type="temporal_plausibility",
        expected="date is not in the future",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_in_future",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary

# Not After Episode
## Expected is target value >= episode date
### was not applicable to ACLF case but could be useful in future registries
def not_after_episode(df):

    assessment_mask = (
        df["notAfterEpisode"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
        & df["source_value_parsed"].notna()
        & df["episode_date_parsed"].notna()
    )

    assessed_elements = int(assessment_mask.sum())

    violation_mask = (
        assessment_mask
        & (
            df["source_value_parsed"]
            > df["episode_date_parsed"]
        )
    )

    failed = df.loc[violation_mask].copy()

    violations = make_violation(
        failed,
        rule_id="not_after_episode",
        rule_type="temporal_plausibility",
        expected="date is not after the episode date",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_after_episode",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary

#####
# Comparison between Variables - handles both notAfter and notBefore


### Gets Metadata fr reference variables from date_rules.csv itself. Assumes therefore that all reference variables are present in date_rules. Needs reassessment for introducing reference dates like DOB which are not MDAT.
def get_variable_comparison_keys(
    target_form_type,
    reference_form_type
):
    
    # Determines how a target date variable should be matched to another date variable used as its comparison reference.

    ##If the reference variable is Basic, compare by PID.
    ##If both target and reference are Longitudinal, compare by patient x Episode
      
    ##a Basic target compared against a Longitudinal reference is not supported
    

    target_form_type = str(target_form_type).strip().lower()
    reference_form_type = str(reference_form_type).strip().lower()

    # Basic basic:
    
    if reference_form_type == "basic":
        return ["PID"]

    # Both variables longitudinal:
    
    if (
        target_form_type == "longitudinal"
        and reference_form_type == "longitudinal"
    ):
        return ["PID", "Episode"]

    return None


def prepare_variable_reference(
    df_export,
    date_rules,
    reference_source_id,
    target_form_type
):
    """"
    Retrieves a reference date variable from the full export,
    determines its form type and date format from date_rules,
    parses its values, and prepares it for merging with the
    target variable.

    Returns:
        reference_values:
            DataFrame containing the appropriate matching columns
            and the parsed comparison date.

        merge_cols:
            Columns on which target and reference should be matched.
            Either ["PID"] or ["PID", "Episode"].

    If the reference variable cannot be found or the comparison
    type is unsupported, it returns (None, None).
    """

    # Find metadata for the reference variable
    reference_metadata = date_rules.loc[
        date_rules["source_id"].astype(str)
        == str(reference_source_id)
    ]

    if reference_metadata.empty:
        return None, None

    # Retrieve form type and date format of reference variable
    reference_form_type = (
        reference_metadata["form_type"]
        .iloc[0]
    )

    reference_data_format = (
        reference_metadata["data_format"]
        .iloc[0]
    )

    # Determine whether matching is patient-level or episode-level
    merge_cols = get_variable_comparison_keys(
        target_form_type,
        reference_form_type
    )

    if merge_cols is None:
        return None, None

    # Retrieve all values of the reference variable
    # directly from the FULL export
    reference_values = df_export.loc[
        df_export["source_id"].astype(str)
        == str(reference_source_id)
    ].copy()

    if reference_values.empty:
        return None, None

    # Add the date format from date_rules so that the existing
    # parsing function can be reused
    reference_values["data_format"] = reference_data_format

    reference_values = parse_source_dates(
        reference_values
    )

    # Keep only information needed for the comparison
    reference_values = (
        reference_values[
            merge_cols + ["source_value_parsed"]
        ]
        .dropna(subset=["source_value_parsed"])
        .drop_duplicates(subset=merge_cols)
        .rename(
            columns={
                "source_value_parsed":
                    "comparison_date_parsed"
            }
        )
    )

    return reference_values, merge_cols

# variable comparison 
def not_before_variable(
    df,
    df_export,
    date_rules
):
    """
    Checks date variables marked with:

        notBeforeVariable = true

    against the date variable identified in:

        notBeforeVariable_source_id

    A violation occurs when:

        target date < comparison date
 
        Matching is as defined by get_variable_comparison_keys
    """

    all_failed = []
    assessed_elements = 0

    # Get metadata rows for which rule is true
    rule_rows = date_rules.loc[
        date_rules["notBeforeVariable"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    ].copy()

    for _, rule in rule_rows.iterrows():

        target_source_id = rule["source_id"]
        target_form_type = rule["form_type"]
        reference_source_id = rule[
            "notBeforeVariable_source_id"
        ]
        
      

        # Skip rules without a reference source ID
        if pd.isna(reference_source_id):
            continue

        reference_source_id = str(
            reference_source_id
        ).strip()

        if reference_source_id == "":
            continue

        # Retrieve rows belonging to this target variable
        # from the already prepared date-rule table
        target_rows = df.loc[
            df["source_id"].astype(str)
            == str(target_source_id)
        ].copy()

        if target_rows.empty:
            continue

        # Retrieve and prepare the comparison variable
        reference_values, merge_cols = (
            prepare_variable_reference(
                df_export=df_export,
                date_rules=date_rules,
                reference_source_id=reference_source_id,
                target_form_type=target_form_type
            )
        )

        if reference_values is None:
            continue

        # Add reference date to corresponding target rows; multiple values are supported
        target_rows = target_rows.merge(
            reference_values,
            on=merge_cols,
            how="left"
        )

        # Rows that can actually be assessed
        assessment_mask = (
            target_rows["source_value_parsed"].notna()
            & target_rows[
                "comparison_date_parsed"
            ].notna()
        )

        assessed_elements += int(
            assessment_mask.sum()
        )

        # Target date must NOT be before reference date
        violation_mask = (
            assessment_mask
            & (
                target_rows["source_value_parsed"]
                < target_rows[
                    "comparison_date_parsed"
                ]
            )
        )

        failed = target_rows.loc[
            violation_mask
        ].copy()

        # Keep the reference source ID in the violation output
        failed["comparison_source_id"] = (
            reference_source_id
        )

        if not failed.empty:
            all_failed.append(failed)

    # Combine violations from all target/reference relationships
    failed = (
    pd.concat(
        all_failed,
        ignore_index=True
    )
    if all_failed
    else df.iloc[0:0].copy()
)

    violations = make_violation(
        failed,
        rule_id="not_before_variable",
        rule_type="temporal_plausibility",
        expected="date is not before comparison variable",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_before_variable",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary


def not_after_variable(
    df,
    df_export,
    date_rules
):
    """
    Checks date variables marked with notAfterVariable = true

    against the date variable identified in notAfterVariable_source_id

    A violation occurs when target date > comparison date

    Matching is as defined by get_variable_comparison_keys
    """

    all_failed = []
    assessed_elements = 0

    # Get metadata rows for which this rule is activated
    rule_rows = date_rules.loc[
        date_rules["notAfterVariable"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    ].copy()

    for _, rule in rule_rows.iterrows():

        target_source_id = rule["source_id"]
        target_form_type = rule["form_type"]
        reference_source_id = rule[
            "notAfterVariable_source_id"
        ]
        

        # Skip rules without a reference source ID
        if pd.isna(reference_source_id):
            continue

        reference_source_id = str(
            reference_source_id
        ).strip()

        if reference_source_id == "":
            continue

        # Retrieve rows belonging to this target variable
        target_rows = df.loc[
            df["source_id"].astype(str)
            == str(target_source_id)
        ].copy()

        if target_rows.empty:
            continue

        # Retrieve and prepare the comparison variable
        reference_values, merge_cols = (
            prepare_variable_reference(
                df_export=df_export,
                date_rules=date_rules,
                reference_source_id=reference_source_id,
                target_form_type=target_form_type
            )
        )

        if reference_values is None:
            continue

        # Add reference date to corresponding target rows
        target_rows = target_rows.merge(
            reference_values,
            on=merge_cols,
            how="left"
        )

        #rows that can actually be assessed
        assessment_mask = (
            target_rows["source_value_parsed"].notna()
            & target_rows[
                "comparison_date_parsed"
            ].notna()
        )

        assessed_elements += int(
            assessment_mask.sum()
        )

        # Target date must NOT be after reference date
        violation_mask = (
            assessment_mask
            & (
                target_rows["source_value_parsed"]
                > target_rows[
                    "comparison_date_parsed"
                ]
            )
        )

        failed = target_rows.loc[
            violation_mask
        ].copy()

        # keep the reference source ID in the violation output
        failed["comparison_source_id"] = (
            reference_source_id
        )

        if not failed.empty:
            all_failed.append(failed)

    # Combine violations from all target/reference relationships
    failed = (
    pd.concat(
        all_failed,
        ignore_index=True
    )
    if all_failed
    else df.iloc[0:0].copy()
)

    violations = make_violation(
        failed,
        rule_id="not_after_variable",
        rule_type="temporal_plausibility",
        expected="date is not after comparison variable",
        observed_col="source_value_parsed",
    )

    summary = make_summary(
        rule_type="temporal_plausibility",
        rule_id="not_after_variable",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary


# Apply all temporal plausibility rules
 

def apply_date_rules(df, df_export, date_rules):
    check_results = [
        not_before_dob(df),
        #not_after_death(df),
        not_in_future(df),
        not_after_episode(df),
        not_before_variable(df, df_export, date_rules),
        not_after_variable(df, df_export, date_rules),
    ]

    violation_tables = [
        violations
        for violations, _ in check_results
        if not violations.empty
    ]

    summary_rows = [
        summary
        for _, summary in check_results
    ]

    results_df = (
        pd.concat(
            violation_tables,
            ignore_index=True,
        )
        if violation_tables
        else pd.DataFrame()
    )

    summary_df = pd.DataFrame(
        summary_rows,
        columns=[
            "rule_type",
            "rule_id",
            "assessed_elements",
            "total_violations",
        ],
    )

    return results_df, summary_df
    

## Main 

def main():
    df_export = load_csv(EXPORT_LONG_PATH)
    date_rules = load_csv(DATE_RULES_PATH)


    date_rule_checks = prepare_date_rule_checks(df_export, date_rules)

    results, summary = apply_date_rules(
    date_rule_checks,
    df_export,
    date_rules
)
    print(f"Date variables in rule table: {date_rules['source_id'].nunique()}")
    print(f"Total date rule violations: {len(results)}")

    if not results.empty:
        preview_cols = [
            "PID",
            "Episode",
            "source_id",
            "dataelement_designation",
            "source_value",
            "source_value_parsed",
            "rule_id",
            "expected",
            "observed",
        ]
        existing_preview_cols = [c for c in preview_cols if c in results.columns]
        print(results[existing_preview_cols].head())

    results.to_csv(
    DATE_RESULTS_OUTPUT_PATH,
    sep=";",
    index=False,
)

    summary.to_csv(
    DATE_SUMMARY_OUTPUT_PATH,
    sep=";",
    index=False,
)

if __name__ == "__main__":
    main()




                                            


    
