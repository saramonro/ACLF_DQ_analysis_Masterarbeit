import pandas as pd
from pathlib import Path

# Config
# Input paths
DATA_DICTIONARY_PATH ="metadata/processed/data_dictionary.csv"
EXPORT_LONG_PATH = "data/processed/export_long_clean.csv"
DATE_RULES_PATH = "metadata/contextual/date_rules.csv"

# Output Paths
OUTPUT_DIR = Path("results/dates")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATE_RESULTS_OUTPUT_PATH = OUTPUT_DIR / "date_rule_results.csv"
DATE_SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "date_rule_summary.csv"
# Registry specific configs - check about DOB as MDAT 
DATE_OF_VISIT_SOURCE_ID = "X_228_47_197"
DATE_OF_BIRTH_SOURCE_ID = "X_225_0_55"
DATE_OF_DEATH_SOURCE_ID = "X_236_0_339"


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

# Assume date rules already created


def merge_rules_export(export_long, date_rules):
    date_rules_checks = export_long.merge(date_rules, on="source_id", how="inner")
    return date_rules_checks

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
def parse_dates(df):
    df = df.copy()
    df["source_value_parsed"] = pd.NaT
    df["data_format"] = df["data_format"].astype(str).str.strip()

    for data_format, group in df.groupby("data_format", dropna=False):
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


def parse_source_dates(df):
    """
    Parses source_value into source_value_parsed according to each row's data_format.
    Rows with unknown data_format remain NaT.
    """
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
    """
    Creates the working table used by all date checks.
    """
    df = merge_rules_export(df_export, date_rules)
    df = parse_source_dates(df)
    
    return df



### Rule Checks
## DOB

def not_before_dob(df):

    # add DOB to patient rows
    dates_of_birth = df.loc[
        df["source_id"] == DATE_OF_BIRTH_SOURCE_ID, ["PID", "source_value_parsed"]
            ].dropna(subset=["source_value_parsed"]).drop_duplicates(subset=["PID"]).rename(columns={"source_value_parsed":"dob_parsed"})

    df=df.merge(dates_of_birth, on=["PID"], how="left")


    # Rows that can actually be assessed by this rule
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

    # Of the assessed rows, identify failures
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


def apply_date_rules(df):
    check_results = [
        not_before_dob(df),
        not_after_death(df),
        not_in_future(df),
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
    

## Main Pipeline

def main():
    df_export = load_csv(EXPORT_LONG_PATH)
    date_rules = load_csv(DATE_RULES_PATH)


    date_rule_checks = prepare_date_rule_checks(df_export, date_rules)

    results, summary = apply_date_rules(date_rule_checks)
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




                                            


    
