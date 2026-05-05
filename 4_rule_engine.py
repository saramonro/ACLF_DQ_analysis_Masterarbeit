import pandas as pd
import re
from pathlib import Path

EXPORT_LONG_PATH = "data/processed/export_long_clean.csv"
DATA_DICTIONARY_PATH ="metadata/processed/data_dictionary.csv"
PERMISSIBLE_VALUES_PATH = "metadata/processed/permissible_values.csv"

OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "rule_results.csv"




def load_csv(path):
    return pd.read_csv(path, dtype="object", sep=";")

# normalize text for boolean types, lowercase and strip
def normalize_bool_text(series):
    return series.astype(str).str.strip().str.lower()

# merge export_long with data dictionary on source_id, keeping only useful columns of data_dictionary

def merge_export_with_dictionary(df_export, df_dict):
        dict_cols = [
    "source_id",
    "dataelement_designation",
    "dataelement_urn",
    "record_designation",
    "record_urn",
    "data_type",
    "data_format",
    "record_mandatory",
    "dataelement_mandatory",
    "slots"
]
        df_dict_rules = df_dict [dict_cols].copy()
        df_merged = df_export.merge(df_dict_rules, how="left", on="source_id")
        return df_merged

def make_violation(df, rule_id, rule_type, expected, observed_col="source_value"):
     out = df.copy()
     out["rule_id"] = rule_id
     out["rule_type"]=rule_type
     out["expected"] = expected
     out["observed"] = out[observed_col]
     return out

# Check if mapping worked by checking if all source_ids in the export map to information on the metadata
def check_unmapped_variables(df):
     failed = df[df["dataelement_urn"].isna()].copy()
     unique_failed = failed["source_id"].drop_duplicates()

     print("Number of unique unmapped source_ids:", len(unique_failed))
     print(unique_failed.tolist())
     return make_violation(failed, rule_id="UNMAPPED", rule_type= "mapping", expected="source_id exists in data dictionary")


# Check that integer data_types are whole numbers

def check_integer_conformance(df):
     is_integer = df["data_type"].str.upper().str.strip().eq("INTEGER")
     has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
     mask = is_integer & has_value
     values = df.loc[mask, "source_value"].astype(str).str.strip()

     is_integer = values.str.fullmatch(r"[+-]?\d+")
     failed=df.loc[mask].loc[~is_integer.fillna(False)].copy()

     return make_violation(failed, 
                           rule_id="Integer_conformance", 
                           rule_type = "datatype_conformance",
                           expected="whole number")

# Check float types

def check_float_conformance(df):
     is_float = df["data_type"].str.upper().str.strip().eq("FLOAT")
     has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
     mask = is_float & has_value
     values = df.loc[mask, "source_value"].astype(str).str.strip()
    #converts dots into commas so both are accepted by pandas.to_numeric() which only accepts dots
     normalized = values.str.replace(",",".", regex=False)
     numeric = pd.to_numeric(normalized, errors="coerce") # tries to convert to numbers, invalid numbers becone NaN via coerce
     failed=df.loc[mask].loc[numeric.isna()].copy()
     return make_violation(
     failed,
     rule_id="FLOAT_CONFORMANCE",
     rule_type="datatype_conformance",
     expected="numeric value using dot or comma as decimal separator"
)


def check_boolean_conformance(df):
     is_boolean = df["data_type"].str.upper().str.strip().eq("BOOLEAN")
     has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
     mask = is_boolean & has_value
     values = df.loc[mask, "source_value"].astype(str).str.strip()

     valid = values.str.upper().str.strip().isin(["TRUE", "FALSE"])
     failed = df.loc[mask].loc[~valid].copy()

     return make_violation(
          failed,
          rule_id="Boolean_conformance",
          rule_type="datatype_conformance",
          expected="True or False")

# Check if date formats fit expected date type 
## we cant rely solely on datetime validation, because issues like 202 as year arent flagged (its considered a valid year)
## Map date types to strftime format strings

def get_date_parser_format(data_format):

    KNOWN_DATE_FORMATS = {
    "DD.MM.YYYY": "%d.%m.%Y",
    "MM.YYYY":    "%m.%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "MM-YYYY":    "%m-%Y",
}
    return KNOWN_DATE_FORMATS.get(str(data_format).strip())

def check_date_format_validity(df):
     # identify DATE data_types and exlude missing values
     is_date = df["data_type"].str.upper().str.strip().eq("DATE")
     has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
     mask = is_date & has_value
     date_rows = df.loc[mask].copy()
     
     failed_parts=[]
     # group by data_format so each variable is validated with its own parser
     for date_format, group in date_rows.groupby("data_format", dropna=False): 
          # look up the mapped strftime string for each data_format
          parser_format = get_date_parser_format(date_format)

          # attempt to parse source_value using expected format; errors="coerce" turns unparseable values into NaN silently
          parsed = pd.to_datetime(
               group["source_value"].astype(str).str.strip(),
               format= parser_format,
               errors= "coerce"
          )
          # rows where parser failed are violations
          failed=group.loc[parsed.isna()].copy()
          if not failed.empty:  # skip appending empty violations
            failed_parts.append(
                 make_violation(failed,
                                rule_id="Date_format_validity",
                                rule_type="Date_format_validity",
                                expected=f"valid date format = {date_format}")
            )
    # combine all violations into one df
     if failed_parts: 
            return pd.concat(failed_parts, ignore_index=True)
          
     return pd.DataFrame()
          


# Check if values are included in permissible_values

def check_permissible_values(df, df_pv):
    # identify enumerated types and exclude missing values
    is_enumerated = df["data_type"].str.strip().str.lower().eq("enumerated")
    has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
    mask = is_enumerated & has_value

    enum_rows = df[mask].copy()

    # load unique combinations of dataelement_urn and pv_value and clean values
    allowed = df_pv[["dataelement_urn", "pv_value"]].drop_duplicates().copy()
    allowed["pv_value"] = allowed["pv_value"].astype(str).str.strip()
    # clean values in export
    enum_rows["source_value_clean"]= enum_rows ["source_value"].astype(str).str.strip()



    # left merge: each source_value is matched against the allowed values
    # for its specific dataelement_urn
    # rows with no match will have NaN in the pv_value column after the merge
    checked=enum_rows.merge(
         allowed,
         how="left",
         left_on=["dataelement_urn","source_value_clean"],
         right_on=["dataelement_urn", "pv_value"]
    )

    # rows where pv_value is Nan had no match to permissible values and is a value violation
    failed=checked[checked["pv_value"].isna()].copy()
    
    return make_violation(
        failed,
        rule_id="PERMISSIBLE_VALUE_CONFORMANCE",
        rule_type="permissible_values",
        expected="value exists in permissible values for this dataelement_urn",
        observed_col="source_value"
    )


def check_single_vs_multiple_choice(df):
    # identify enumerated types and exclude missing values
    is_enumerated = df["data_type"].str.strip().str.lower().eq("enumerated")
    has_value = (
        df["source_value"].notna()
        & df["source_value"].astype(str).str.strip().ne(""))
    mask = is_enumerated & has_value

    enum_rows = df[mask].copy()   

    # single-choice enumerated types are those with SELECT_ONE_RADIO as slot or  empty slots (become dropdowns)

    enum_rows["slots_clean"] = enum_rows["slots"].fillna("").astype(str).str.strip()
    single_choice = enum_rows[
         enum_rows["slots_clean"].isin(["", "SELECT_ONE_RADIO"])].copy()
    
    # Variable instances are a combination of following columns
    group_cols =[
         "PID",
         "Episode",
         "Episode_Date",
         "IX",
         "source_id"
    ]
    # Make sure columns exist
    existing_group_cols = [ c for c in group_cols if c in single_choice.columns]
    
    # Counts of unique values per combination
    counts = (
        single_choice
        .dropna(subset=["source_value"])
        .groupby(existing_group_cols)
        .size()
        .reset_index(name="n_values")
    )

    # Keep only groups where a single-choice variable has more than one value

    bad_groups = counts[counts["n_values"] > 1]

    failed = single_choice.merge(bad_groups[existing_group_cols + ["n_values"]], how="inner", on=existing_group_cols)

    # Rename column
    failed["observed_count"] = failed["n_values"]
    return make_violation(
    failed,
    rule_id="SINGLE_CHOICE_MULTIPLE_VALUES",
    rule_type="single_vs_multiple_choice",
    expected="only one selected value for single-choice enumerated variable",
    observed_col="observed_count"
)


def apply_rules(df, df_pv):
    rule_results = [
        check_integer_conformance(df),
        check_float_conformance(df),
        check_boolean_conformance(df),
        check_date_format_validity(df),
        check_permissible_values(df, df_pv),
        check_single_vs_multiple_choice(df)
    ]

    rule_results = [r for r in rule_results if not r.empty]

    if not rule_results:
        return pd.DataFrame()

    return pd.concat(rule_results, ignore_index=True)

def main():

    df_export = load_csv(EXPORT_LONG_PATH)
    df_dict = load_csv(DATA_DICTIONARY_PATH)
    df_pv = load_csv(PERMISSIBLE_VALUES_PATH)

    df_merged = merge_export_with_dictionary(df_export, df_dict)

    results = apply_rules(df_merged, df_pv)

    print(f"Total rule violations: {len(results)}")

    if not results.empty:
        print(results[["PID", "source_id", "source_value", "rule_id", "expected", "observed"]].head())

    results.to_csv(OUTPUT_PATH, index=False, sep=";")


if __name__ == "__main__":
    main()