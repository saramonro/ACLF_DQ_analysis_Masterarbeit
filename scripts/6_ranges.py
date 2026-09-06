# Range Conformance 


import pandas as pd
import operator
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_LONG_PATH = PROJECT_ROOT / "data" / "processed" / "export_long_clean.csv"
DATA_DICTIONARY_PATH = PROJECT_ROOT / "metadata" / "processed" / "data_dictionary.csv"

OUTPUT_DIR = PROJECT_ROOT / "results" / "range"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "range_rule_results.csv"
SUMMARY_OUTPUT_PATH = (
    OUTPUT_DIR / "range_rule_summary.csv"
)


'''
Additional Value Conformance check - Range Conformance
checks whether values of numeric variables with MDR-defined hard-coded ranges are within the defined ranges

Assesses variables with date type integer or float in DD
Parses their defined ranges
Matches value against range
If value is not within range , its a violation 


'''


VALID_NUMERIC_TYPES = ["INTEGER", "FLOAT"]

OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def load_csv(path):
    return pd.read_csv(path, dtype="object", sep=";")


def make_violation(df, rule_id, rule_type, expected, observed_col="source_value"):
    out = df.copy()


    out["rule_id"] = rule_id
    out["rule_type"] = rule_type
    out["expected"] = expected
    out["observed"] = out[observed_col]

    return out


# assessed elements are numeric + with range + export value converted numerically + range expression parseable.
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
def get_numeric_types(df):
    
    # takes Data Dictionary, returns only INTEGER and FLOAT rows
    

    df = df.copy()

    df["data_type"] = (
        df["data_type"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    cols = [
        "source_id",
        "data_type",
        "data_format",
        "dataelement_designation",
        "dataelement_urn",
        "record_designation",
        "record_urn"
    ]

    df = df[df["data_type"].isin(VALID_NUMERIC_TYPES)][cols]

    return df


def parse_numeric_range(data_format):
    
    # Parses numeric range expressions from metadata.
    """
    Supported examples...
    - 0<X<100
    - 0<=X<=100
    - 0<X<=100
    - 0<=X<100
    - X<100
    - X<=100
    - X>0
    - X>=0
    ...although MDR does not seem to support > or < 
    """

    if pd.isna(data_format):
        return []

    range_string = str(data_format).replace(" ", "").upper()

# Case 0: if data_format is X there is no set hard coded range

    if range_string == "X":
        return []

    conditions = []

    # Case 1: two sided range
    # 0<X<100
    # 0<=X<=100
    # etc.

    match = re.fullmatch(
        r"(-?\d+(?:\.\d+)?)(<=|<)X(<=|<)(-?\d+(?:\.\d+)?)", # Regex separates sections into groups via ()s
        range_string
    )

    if match:
        lower_value, lower_operator, upper_operator, upper_value = match.groups() # Match sections to labels

        lower_value = float(lower_value)
        upper_value = float(upper_value)

        # Convert from:
        # 0 < X
        # to:
        # X > 0

        if lower_operator == "<":
            conditions.append((">", lower_value))

        elif lower_operator == "<=":
            conditions.append((">=", lower_value))

        conditions.append((upper_operator, upper_value))

        return conditions

    # Case 2: upper range
    # X<100
    # X<=100


    match = re.fullmatch(
       r"X(<=|<)(-?\d+(?:\.\d+)?)",
     range_string
    )

    if match:
        operator_symbol, value = match.groups()

        conditions.append((operator_symbol, float(value)))

        return conditions
    
    # Case 3: lower range
    # 0<X
    # 0<=X
    match = re.fullmatch(
    r"(-?\d+(?:\.\d+)?)(<=|<)X",
    range_string
    )

    if match:
        value, operator_symbol = match.groups()
        value = float(value)

        # Convert from:
        # 0 <= X
        # to:
        # X >= 0

        if operator_symbol == "<":
            conditions.append((">", value))

        elif operator_symbol == "<=":
            conditions.append((">=", value))

        return conditions

    return []

#check whether numeric source_values fall inside metadata-defined ranges
def check_numeric_range(df_export, df_dict):
    
    
    # get numeric rules from metadata

    numeric_rules = get_numeric_types(df_dict)[
        ["source_id", "data_type", "data_format"]
    ].copy()

    #merge export with numeric metadata, keep only numeric_types

    merged = df_export.merge(
        numeric_rules,
        on="source_id",
        how="inner"
    )

    #exclude rows without range (numeric types without range have data_format = X)

    has_range = (
        merged["data_format"]
        .astype(str)
        .str.strip()
        .str.upper()
        .ne("X")
    )

    range_rows = merged[has_range].copy()

    #convert values to numeric

    normalized = (
        range_rows["source_value"]
        .astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
    )

    range_rows["numeric_value"] = pd.to_numeric(
        normalized,
        errors="coerce"
    )

    # invalid numeric values cannot be range-checked

    valid_numeric = range_rows[
        range_rows["numeric_value"].notna()
    ].copy()

    failed_parts = []
    assessed_elements = 0

    #evaluate each row against parsed conditions

    for _, row in valid_numeric.iterrows():

        conditions = parse_numeric_range(row["data_format"])
        # No recognized range means that this row
        # could not actually be assessed
        if not conditions:
            continue
        assessed_elements += 1 #malformed range expressions dont count as assessed


        value = row["numeric_value"] # example 50

        violated = False

        for operator_symbol, boundary in conditions: # example (">", 0)

            operation = OPS[operator_symbol] # turns > into operator.gt

            if not operation(value, boundary): # operator.gt(50, 0) i.e. 50>0 -> true
                violated = True
                break

        if violated:
            failed_parts.append(row)

    # combine violations

    if failed_parts:

        failed_df = pd.DataFrame(failed_parts)

        violations = make_violation(
            failed_df,
            rule_id="NUMERIC_RANGE_CONFORMANCE",
            rule_type="numeric_range",
            expected=(
                "value falls within metadata-defined "
                "numeric range"
            ),
        )
    else:
        violations = pd.DataFrame()

    summary = make_summary(
        rule_type="numeric_range",
        rule_id="range_conformance",
        assessed_elements=assessed_elements,
        violations=violations,
    )

    return violations, summary

def apply_rules(df_export, df_dict):
    violations, summary = check_numeric_range(
        df_export,
        df_dict,
    )

    summary_df = pd.DataFrame(
        [summary],
        columns=[
            "rule_type",
            "rule_id",
            "assessed_elements",
            "total_violations",
        ],
    )

    return violations, summary_df


def main():

    df_export = load_csv(EXPORT_LONG_PATH)
    df_dict = load_csv(DATA_DICTIONARY_PATH)

    results, summary = apply_rules(
    df_export,
    df_dict,
)
    print(f"Total range violations: {len(results)}")

    if not results.empty:
        print(
            results[[
                "PID",
                "source_id",
                "source_value",
                "rule_id",
                "expected",
                "observed"
            ]].head()
        )

    results.to_csv(OUTPUT_PATH, index=False, sep=";")
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False,sep=";")

if __name__ == "__main__":
    main()