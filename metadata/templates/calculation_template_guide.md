# Guide for defining calculation checks

The calculation metadata consist of three CSV files:

* `calculation_formulas.csv` defines how a calculation is performed
* `calculation_instances.csv` defines where a calculated result occurs in the registry
* `calculation_variable_mappings.csv` defines which registry variables provide the inputs for each calculation

All CSV files use a semicolon (`;`) as the separator.

The identifiers used across the three files must match exactly. Differences in spelling, capitalization, spaces, or underscores may prevent a calculation from being evaluated.


## 1. `calculation_formulas.csv`

This table defines the mathematical formula for each type of calculation.

### `calculation_type`

A unique name for the type of calculation.

Examples:

`BMI`
`MAP`
`MELD`
`MELD_Na`

The same value must be entered in the `calculation_type` column of `calculation_instances.csv`.

Use a short, consistent identifier. Avoid spaces where possible; underscores can be used instead.




### `formula_expression`

The mathematical expression used to recalculate the expected value.

Variable names used here must correspond **exactly** to the `variable_alias` values entered for that calculation in `calculation_variable_mappings.csv`.

For example:

`weight / ((height / 100) ** 2)`

requires mappings with the aliases:

`weight`
`height`



### Supported mathematical operators

The following operators can be used:

* `+` addition
* `-` subtraction
* `*` multiplication
* `/` division
* `**` exponentiation
* unary `-` for negative values

Parentheses may be used normally to define the order of operations.

### Supported functions

The following functions are supported:

* `ln(x)` - natural logarithm
* `log(x)` - natural logarithm
* `sqrt(x)` - square root
* `exp(x)` - exponential function
* `min(x, y, ...)`
* `max(x, y, ...)`
* `round(x)`
* `abs(x)` - absolute value

For example:

`9.57 * ln(max(creatinine,1)) + 3.78 * ln(max(bilirubin,1))`

Do not use functions or Python expressions that are not included in this list.

Variable aliases should contain simple names such as `creatinine`, `sodium`, or `prothrombin_time`. Avoid spaces, hyphens, brackets, or special characters in aliases.



### `tolerance`

Defines how much the stored value may differ from the recalculated value before the result is considered a violation.

Enter a numeric value using a decimal point.

Examples:

`0`
`0.1`
`0.01`

A tolerance of `0` requires an exact match.

A tolerance of `0.1` allows an absolute difference of up to 0.1.

Do not use a comma as the decimal separator.

Because of slight discrepancies in how javascript and python handle roundings, it is advisable to use a tolerance value higher than 0.

### `rounding`

Defines whether the calculated result is rounded before comparison with the stored value.

Supported values are:

* `integer` - round to the nearest whole number
* `nearest_integer` - equivalent whole-number rounding
* `one_decimal` - round to one decimal place
* `two_decimals` - round to two decimal places
* `none` - no additional rounding

The spelling must match exactly.

Choose the rounding rule according to how the corresponding value is calculated and stored in the registry.



## 2. `calculation_instances.csv`

This table identifies each concrete occurrence of a calculated variable in the registry.

The same calculation type can occur in more than one form. For example, Mean Arterial Pressure may be calculated using the same formula in two different forms. Each occurrence therefore receives its own `calculation_id`.

### `calculation_id`

A unique identifier for the individual calculation instance.

Examples:

`BMI_basic`
`MAP_aclf_examination`
`MAP_physical_examination`

This identifier connects the instance to its input variables in `calculation_variable_mappings.csv`.

Every `calculation_id` used here must therefore also be used for the corresponding rows in the mapping table.

Use a unique, descriptive identifier without spaces.



### `calculation_type`

Specifies which formula is used for this instance.

The value must exactly match a `calculation_type` in `calculation_formulas.csv`.

For example:

If the formulas table contains `MAP` then an instance may contain MAP_aclf_examination ; MAP ; ...`

and another `MAP_physical_examination ; MAP ; ...`

Both instances will use the same MAP formula but may use different source variables.



### `score_label`

A human-readable label for the calculated result.

Examples:

`BMI`
`MELD Score`
`Mean Arterial Pressure`

This field is intended to make the metadata and output easier to interpret.

Use the terminology used in the registry where possible.



### `score_source_id`

The `source_id` of the registry variable containing the **stored calculated result**.

Example: `X_230_0_236`

Copy this value exactly from the relevant registry/export metadata.

Do not construct or modify source IDs manually. The value must match the `source_id` appearing in the processed data export.


### `score_urn`

The MDR URN of the data element containing the calculated result.

Example:

`urn:osse-11:dataelement:236`

Copy the complete URN from the MDR metadata.

Do not remove the namespace or enter only the numeric data-element ID.

The current calculation check primarily identifies data in the export through `score_source_id`; the URN nevertheless documents which MDR data element the instance refers to.



## 3. `calculation_variable_mappings.csv`

This table defines the input variables required for each calculation instance.

Create one row for every input variable required by a calculation.

For example, BMI requires two variables:

 weight
 height

The mapping table therefore contains two rows with the same `calculation_id`.


### `calculation_id`

Identifies the calculation instance to which the input belongs.

This value must exactly match a `calculation_id` from `calculation_instances.csv`.

For example:

`BMI_basic`

If BMI requires both weight and height, both mapping rows use `BMI_basic`



### `variable_alias`

The short variable name used inside the mathematical formula.

For example:

`weight`
`height`
`sbp`
`dbp`
`creatinine`

This is particularly important: **the alias must exactly match the variable name used in `formula_expression`.**

For example, if the formula is:

`weight / ((height / 100) ** 2)`

the mapping table must contain the aliases:

`weight`nand `height`

Do not enter `Weight`, `body_weight`, or another variation unless that exact name is also used in the formula.

Aliases should:

- use simple descriptive names;
- preferably use lowercase letters;
-use underscores instead of spaces;
- not contain hyphens or special characters.


### `variable_label`

A human-readable name for the input variable.

Examples:

`Weight`
`Height`
`Systolic Blood Pressure`
`Creatinine`

This does not need to match the formula alias. It is intended for documentation and readability.

Use the terminology used in the registry where possible.



### `variable_source_id`

The `source_id` of the registry variable providing the input value.

Example:

`X_230_0_349`

Copy the source ID exactly from the registry/export metadata.

The source ID is important because it identifies the concrete occurrence of a data element in a form. The same MDR data element may occur in more than one form and therefore have different source IDs.

Do not construct source IDs manually.



### `variable_urn`

The MDR URN of the input data element.

Example:

`urn:osse-11:dataelement:349`

Copy the complete URN from the MDR metadata.

The URN documents which MDR data element the input represents, while `variable_source_id` identifies the concrete occurrence used for the calculation.




The calculation can only be assessed when the stored result and all required input variables are available for the same patient, episode/date and, where applicable, repeat index (`IX`). Cases with missing or ambiguous input values are not included in the calculation assessment.
