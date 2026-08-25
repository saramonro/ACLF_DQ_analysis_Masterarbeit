import pandas as pd
import numpy as np
import ast
import operator as op
from pathlib import Path



BASE_DIR = Path(__file__).resolve().parents[1] # project root; script lives in the checks/ subfolder

EXPORT_PATH = BASE_DIR / "data" / "processed" / "export_long_clean.csv"

CALC_INSTANCES_PATH = BASE_DIR / "metadata" / "behavioral" / "calculations" / "calculation_instances.csv"
CALC_MAPPINGS_PATH = BASE_DIR / "metadata" / "behavioral" / "calculations" / "calculation_variable_mappings.csv"
CALC_FORMULAS_PATH = BASE_DIR / "metadata" / "behavioral" / "calculations" / "calculation_formulas.csv"

RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

VIOLATIONS_PATH = RESULTS_DIR / "calculation_check_violations.csv"
ALL_RESULTS_PATH = RESULTS_DIR / "calculation_check_all_results.csv"
SUMMARY_PATH = (
    RESULTS_DIR
    / "calculation_check_summary.csv"
)



ALLOWED_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}

ALLOWED_FUNCTIONS = {
    "ln": np.log,
    "log": np.log,
    "sqrt": np.sqrt,
    "exp": np.exp,
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
}


def safe_eval_formula(expression, variables):
    #Evaluate a mathematical formula using only allowed operators, functions, and variables

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"Unknown variable in formula: {node.id}")
            return variables[node.id]

        if isinstance(node, ast.BinOp):
            operator_type = type(node.op)
            if operator_type not in ALLOWED_OPERATORS:
                raise ValueError(f"Operator not allowed: {operator_type}")
            return ALLOWED_OPERATORS[operator_type](_eval(node.left), _eval(node.right))

        if isinstance(node, ast.UnaryOp):
            operator_type = type(node.op)
            if operator_type not in ALLOWED_OPERATORS:
                raise ValueError(f"Unary operator not allowed: {operator_type}")
            return ALLOWED_OPERATORS[operator_type](_eval(node.operand))

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed")

            function_name = node.func.id

            if function_name not in ALLOWED_FUNCTIONS:
                raise ValueError(f"Function not allowed: {function_name}")

            args = [_eval(arg) for arg in node.args]
            return ALLOWED_FUNCTIONS[function_name](*args)

        raise ValueError(f"Unsupported expression element: {type(node)}")

    parsed_expression = ast.parse(expression, mode="eval")
    return _eval(parsed_expression)


#Load data


def load_data():
    export = pd.read_csv(EXPORT_PATH, sep=";", dtype=object)

    calculation_instances = pd.read_csv(CALC_INSTANCES_PATH, sep=";", dtype=object)
    calculation_mappings = pd.read_csv(CALC_MAPPINGS_PATH, sep=";", dtype=object)
    calculation_formulas = pd.read_csv(CALC_FORMULAS_PATH, sep=";", dtype=object)

    return export, calculation_instances, calculation_mappings, calculation_formulas


#Preprocess export

def preprocess_export(export):
    
   # Standardizes relevant column names and values
    
    if "Episode_Date" in export.columns and "episode_date" not in export.columns:
        export = export.rename(columns={"Episode_Date": "episode_date"})



    export["source_value_numeric"] = pd.to_numeric(
        export["source_value"].str.replace(",", ".", regex=False),
        errors="coerce"
    )

    return export

#get value for PID x episode_datexsource_idx IX
# IX added because of "repeatable" issue

def get_single_value(export_subset, source_id, ix):
    values = export_subset.loc[
        (export_subset["source_id"] == source_id)
        & (export_subset["IX"] == ix),
        "source_value_numeric"
    ].dropna().unique()

    if len(values) == 0:
        return np.nan

    if len(values) > 1:
        return "MULTIPLE_VALUES"

    return values[0]

# Calculation checks

def run_computational_conformance_checks(
    export,
    calculation_instances,
    calculation_mappings,
    calculation_formulas
):
    results = []
    summary_rows = []


    formula_lookup = calculation_formulas.set_index("calculation_type").to_dict("index")

    for _, instance in calculation_instances.iterrows():

        calculation_id = instance["calculation_id"]
        calculation_type = instance["calculation_type"]
        score_label = instance.get("score_label", calculation_id)
        score_source_id = instance["score_source_id"]
        instance_results = []
        if calculation_type not in formula_lookup:
            print(
                 f"Skipping {calculation_id}: "
                  "no formula found."
                    )

            summary_rows.append(
              make_summary(
                rule_type="computational_conformance",
                 rule_id=calculation_id,
                 assessed_elements=0,
                 violations=pd.DataFrame(),
        )
    )

            continue

        formula_info = formula_lookup[calculation_type]
        formula_expression = formula_info["formula_expression"]
        tolerance = float(formula_info.get("tolerance", 0.01))
        rounding = formula_info.get("rounding", "none")

        required_variables = calculation_mappings[
            calculation_mappings["calculation_id"] == calculation_id
        ]
# Addition to make it less memory consuming, targetting only relevant ids
        relevant_source_ids = (
         required_variables["variable_source_id"].tolist()
           + [score_source_id]
)

        calculation_export = export[
         export["source_id"].isin(relevant_source_ids)
]

        if required_variables.empty:
            print(f"Skipping {calculation_id}: no variable mappings found.")
            summary_rows.append(
            make_summary(
            rule_type="computational_conformance",
            rule_id=calculation_id,
            assessed_elements=0,
            violations=pd.DataFrame(),
        )
    )
            continue

        # Only evaluate PID x episode_date x IX combinations
        # where the target calculated value is actually present
        target_rows = calculation_export[
    (calculation_export["source_id"] == score_source_id)
    & (calculation_export["source_value_numeric"].notna())
][["PID", "episode_date", "IX", "source_value_numeric"]]

        for _, target_context in target_rows.iterrows():

            pid = target_context["PID"]
            episode_date = target_context["episode_date"]
            ix = target_context["IX"]
            stored_value = target_context["source_value_numeric"]

            if pd.isna(episode_date):
                 export_subset = calculation_export[
                  (calculation_export["PID"] == pid)
                 & calculation_export["episode_date"].isna()
                  ]
            else:
                   export_subset = calculation_export[
                 (calculation_export["PID"] == pid)
                  & (calculation_export["episode_date"] == episode_date)
    ]


            variable_values = {}
            missing_variables = []
            multiple_value_variables = []

            for _, variable in required_variables.iterrows():

                alias = variable["variable_alias"]
                variable_source_id = variable["variable_source_id"]

                value = get_single_value(
    export_subset,
    variable_source_id,
    ix
)

                if isinstance(value, str) and value == "MULTIPLE_VALUES":
                    multiple_value_variables.append(alias)

                elif pd.isna(value):
                    missing_variables.append(alias)

                else:
                    variable_values[alias] = float(value)

            # Do not include incomplete cases in the results table
            if missing_variables or multiple_value_variables:
                continue

            try:
                expected_value = safe_eval_formula(
                    formula_expression,
                    variable_values
                )

                if rounding in ["integer", "nearest_integer"]:
                    expected_value = round(expected_value)

                elif rounding == "one_decimal":
                    expected_value = round(expected_value, 1)

                elif rounding == "two_decimals":
                    expected_value = round(expected_value, 2)

                difference = abs(float(stored_value) - float(expected_value))
                violation = difference > tolerance

                result_row = {
                     "PID": pid,
                     "episode_date": episode_date,
                     "calculation_id": calculation_id,
                     "calculation_type": calculation_type,
                     "score_label": score_label,
                     "score_source_id": score_source_id,
                     "IX": ix,
                     "stored_value": stored_value,
                     "expected_value": expected_value,
                     "difference": difference,
                     "tolerance": tolerance,
                     "formula_expression": formula_expression,
                     "input_values": variable_values,
                     "status": (
                       "violation"
                       if violation
                       else "pass"
                       ),
                     "violation": violation,
}
                results.append(result_row)
                instance_results.append(result_row)



            except Exception as error:
                # Formula errors are implementation issues, not data-quality results.
                # They are printed but not included in the results table.
                print(
                    f"Formula error for {calculation_id}, "
                    f"PID={pid}, episode_date={episode_date}: {error}"
                )
                
        instance_results_df = pd.DataFrame(
            instance_results
        )

        if instance_results_df.empty:
            instance_violations = pd.DataFrame()
        else:
            instance_violations = instance_results_df[
                instance_results_df["violation"] == True
            ].copy()

        summary_rows.append(
            make_summary(
                rule_type="calculation_check",
                rule_id=calculation_id,
                assessed_elements=len(instance_results),
                violations=instance_violations,
            )
        )

    
    results_df = pd.DataFrame(results)

    if results_df.empty:
        violations_df = pd.DataFrame()
    else:
        violations_df = results_df[
            results_df["violation"] == True
        ].copy()

    summary_df = pd.DataFrame(
        summary_rows,
        columns=[
            "rule_type",
            "rule_id",
            "assessed_elements",
            "total_violations",
        ],
    )

    return results_df, violations_df, summary_df




# Summary
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

# Main

def main():
    export, calculation_instances, calculation_mappings, calculation_formulas = load_data()

    export = preprocess_export(export)

    all_results, violations, summary = (
    run_computational_conformance_checks(        export=export,
        calculation_instances=calculation_instances,
        calculation_mappings=calculation_mappings,
        calculation_formulas=calculation_formulas
    ))

    all_results.to_csv(ALL_RESULTS_PATH, sep=";", index=False)
    violations.to_csv(VIOLATIONS_PATH, sep=";", index=False)
    summary.to_csv(SUMMARY_PATH, sep=";", index=False)

    print("Computational conformance check finished.")
    print(f"All results saved to: {ALL_RESULTS_PATH}")
    print(f"Violations saved to: {VIOLATIONS_PATH}")
    print(f"Number of evaluated rows: {len(all_results)}")
    print(f"Number of violations: {len(violations)}")


if __name__ == "__main__":
    main()