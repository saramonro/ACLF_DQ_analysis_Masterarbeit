from pathlib import Path
import pandas as pd
import numpy as np


# Configuration

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = PROJECT_ROOT / "data" / "processed" / "export_long_clean.csv"
RULES_PATH = PROJECT_ROOT / "metadata" / "contextual" / "longitudinal_plausibility.csv"

VIOLATIONS_OUT = PROJECT_ROOT / "results" / "longitudinal_plausibility_violations.csv"
SUMMARY_OUT = PROJECT_ROOT / "results" / "longitudinal_plausibility_summary.csv"

EXPORT_SEP = ";"
RULES_SEP = ";"


# Loading

def load_rules(path: Path):
    rules = pd.read_csv(path, sep=RULES_SEP, dtype="object")

    required_cols = {
        "rule_id",
        "source_id",
        "variable_label",
        "value_type",
        "allowed_variation_percent",
    }
    missing = required_cols - set(rules.columns)
    if missing:
        raise ValueError(f"Rules file is missing columns: {missing}")
    rules["allowed_variation_percent"] = pd.to_numeric(
        rules["allowed_variation_percent"],
        errors="coerce"
    )

    if rules["allowed_variation_percent"].isna().any():
        bad_rules = rules.loc[rules["allowed_variation_percent"].isna(), "rule_id"].tolist()
        raise ValueError(f"Invalid allowed_variation_percent for rules: {bad_rules}")

    return rules


def load_relevant_export(path: Path, source_ids: set[str]):
    usecols = ["PID", "Episode_Date", "source_id", "source_value"]

    export = pd.read_csv(
        path,
        sep=EXPORT_SEP,
        dtype="object",
        usecols=usecols,
    )

    export = export[export["source_id"].isin(source_ids)].copy()

    export = export.rename(columns={"Episode_Date": "episode_date"})

    export = export.dropna(
        subset=["PID", "episode_date", "source_id", "source_value"]
    )

    export["source_value"] = export["source_value"].astype(str).str.strip()
    export = export[export["source_value"] != ""]

    export["episode_date"] = pd.to_datetime(
        export["episode_date"],
        errors="coerce",
        dayfirst=True
    )

    export = export.dropna(subset=["episode_date"])

    return export


# Variation logic

def calculate_variation(group: pd.DataFrame, value_type: str):
    value_type = str(value_type).lower()
    if value_type == "date_increasing":
         ordered_group = group.sort_values("episode_date").copy()

         ordered_group["parsed_value"] = pd.to_datetime(
             ordered_group["source_value"],
                errors="coerce",
                dayfirst=True,
        )

         valid_group = ordered_group.dropna(
             subset=["parsed_value"]
           ).copy()

         if valid_group["episode_date"].nunique() < 2:
                return {
                    "observed_variation": np.nan,
                   "min_value": np.nan,
                   "max_value": np.nan,
                   "values_observed": "",
                   "n_valid_episode_dates": valid_group["episode_date"].nunique(),
                  "n_rows_checked": len(valid_group),
               }

         valid_group["previous_value"] = (
          valid_group["parsed_value"].shift(1)
            )

         invalid_transitions = (
             valid_group["parsed_value"]
            < valid_group["previous_value"]
       )

         number_of_decreases = int(invalid_transitions.sum())

         return {
            "observed_variation": number_of_decreases,
            "min_value": valid_group["parsed_value"].min(),
            "max_value": valid_group["parsed_value"].max(),
            "values_observed": " | ".join(
               valid_group["parsed_value"]
                .dt.strftime("%Y-%m-%d")
                .tolist()
            ),
           "n_valid_episode_dates": valid_group["episode_date"].nunique(),
            "n_rows_checked": len(valid_group),
       }


    if value_type in ["float", "integer", "numeric"]:
        numeric_values = pd.to_numeric(group["source_value"], errors="coerce")

        valid_group = group[numeric_values.notna()].copy()
        valid_values = numeric_values[numeric_values.notna()]

        if valid_group["episode_date"].nunique() < 2: # applies the check only on instances where the same patient has more a value in more than one episode_date
            return {
                "observed_variation": np.nan,
                "min_value": np.nan,
                "max_value": np.nan,
                "values_observed": "",
                "n_valid_episode_dates": valid_group["episode_date"].nunique(),
                "n_rows_checked": len(valid_group),
            }

        min_value = valid_values.min()
        max_value = valid_values.max()

        if min_value == 0 and max_value == 0:
            observed_variation = 0.0
        elif min_value == 0:
            observed_variation = np.inf
        else:
            observed_variation = ((max_value - min_value) / abs(min_value)) * 100

        return {
            "observed_variation": observed_variation,
            "min_value": min_value,
            "max_value": max_value,
            "values_observed": " | ".join(
                sorted(valid_group["source_value"].astype(str).unique())
            ),
            "n_valid_episode_dates": valid_group["episode_date"].nunique(),
            "n_rows_checked": len(valid_group),
        }

    if value_type in ["enumerated", "multiple-choice", "radio", "dropdown", "date"]: # User friendly terms not restricted to metadata terms to facilitate user input
        # dates are treated as strings and compared
        clean_values = group["source_value"].astype(str).str.strip()
        unique_values = sorted(clean_values.unique())

        observed_variation = len(unique_values) - 1
#Converts everything to strings and removes leading/trailing spaces.
#Gets the distinct values observed for that patient.
#Raises violation if patient has more than one distinct values
        return {
            "observed_variation": observed_variation,
            "min_value": np.nan,
            "max_value": np.nan,
            "values_observed": " | ".join(
    pd.unique(
        group.sort_values("episode_date")["source_value"].astype(str)
    )
), # guarantees observed values are showed chronologically and not alphabetically
            "n_valid_episode_dates": group["episode_date"].nunique(),
            "n_rows_checked": len(group),
        }

    raise ValueError(f"Unsupported value_type: {value_type}")


def check_group(group: pd.DataFrame, rule: pd.Series):
    stats = calculate_variation(group, rule["value_type"])

    if stats["n_valid_episode_dates"] < 2:
        return None

    if stats["observed_variation"] <= float(rule["allowed_variation_percent"]):
        return None

    return {
        "rule_id": rule["rule_id"],
        "PID": group["PID"].iloc[0],
        "source_id": rule["source_id"],
        "variable_label": rule["variable_label"],
        "value_type": rule["value_type"],
        "allowed_variation_percent": rule["allowed_variation_percent"],
        "observed_variation": stats["observed_variation"],
        "min_value": stats["min_value"],
        "max_value": stats["max_value"],
        "values_observed": stats["values_observed"],
        "first_episode_date": group["episode_date"].min().date(),
        "last_episode_date": group["episode_date"].max().date(),
        "n_episode_dates": group["episode_date"].nunique(),
        "n_rows_checked": stats["n_rows_checked"],
    }


# Running checks

def run_longitudinal_checks(export: pd.DataFrame, rules: pd.DataFrame):
    violations = []

    rules_by_source = rules.set_index("source_id", drop=False)

    for (_, source_id), group in export.groupby(["PID", "source_id"], sort=False):
        rule = rules_by_source.loc[source_id]
        result = check_group(group, rule)

        if result is not None:
            violations.append(result)

    return pd.DataFrame(violations)


# Summary

def build_summary(
    export,
    violations,
    rules,
):
    summary_rows = []

    for _, rule in rules.iterrows():
        rule_id = rule["rule_id"]
        source_id = rule["source_id"]
        value_type = rule["value_type"]

        # Export rows relevant to the current rule
        rule_export = export[
            export["source_id"] == source_id
        ].copy()

        assessed_elements = 0

        # Each PID × source_id group is one potential
        # longitudinal assessment
        for _, group in rule_export.groupby(
            "PID",
            sort=False,
            dropna=False,
        ):
            # calculate_variation is used because it filters numerical values which cannot be converted to numbers (so false format)
            ## so these dont count as assessments
            stats = calculate_variation(
                group,
                value_type,
            )

            # The longitudinal rule is assessed only when
            ## at least two valid episode dates are available
            if stats["n_valid_episode_dates"] >= 2:
                assessed_elements += 1

        if (
            violations.empty
            or "rule_id" not in violations.columns
        ):
            total_violations = 0
        else:
            total_violations = int(
                violations["rule_id"]
                .eq(rule_id)
                .sum()
            )

        summary_rows.append({
            "rule_type": "longitudinal_plausibility",
            "rule_id": rule_id,
            "assessed_elements": assessed_elements,
            "total_violations": total_violations,
        })

    return pd.DataFrame(
        summary_rows,
        columns=[
            "rule_type",
            "rule_id",
            "assessed_elements",
            "total_violations",
        ],
    )


# Main

def main() -> None:
    VIOLATIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)

    rules = load_rules(RULES_PATH)
    source_ids = set(rules["source_id"].dropna().astype(str))

    export = load_relevant_export(EXPORT_PATH, source_ids)

    violations = run_longitudinal_checks(export, rules)
    summary = build_summary(export, violations, rules)

    violations.to_csv(VIOLATIONS_OUT, sep=";", index=False)
    summary.to_csv(SUMMARY_OUT, sep=";", index=False)
    

    print("Longitudinal plausibility check complete.")

    print(
    "Rules summarized:",
    len(summary),
)

    print(
    "Assessed patient-variable groups:",
    summary["assessed_elements"].sum(),
)

    print(
    "Total violations:",
    summary["total_violations"].sum(),
)


if __name__ == "__main__":
    main()