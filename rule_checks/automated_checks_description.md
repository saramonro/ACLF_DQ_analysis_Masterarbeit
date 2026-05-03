# Mapping/metadata coverage
Checks that every source_id in the export exists in the data_dictionary and vice-versa
 - merge export_long and data_dictionary on source_id, check for rows with missing data

 # Datatype conformance
 uses data_type
 DATE - must be accepted date type
 INTEGER - must be whole number
 FLOAT - must be numeric (check if commas or dots)
 BOOLEAN - must match "TRUE" or "FALSE"

 

 # Date format validity
 uses data_type==DATE and data_format
 map each allowed format to a parser pattern
 parse with strict format
 failed parse = invalid date format

 # permissible values conformance
 if data_type == enumerated
 uses separate permissible values table

 checks if: value(s) exist in permissibel_values for that dataelement_URN

 # single-choice vs multiple-choice conformance
 Uses "slots" and "data_type"

 if data_type == enumerated and slots == SELECT_ONE_RADIO OR empty, only one value allowed
 if data_type == enumerated and slots == SELECT_MANY_CHECKBOX, multiple values allowed

# mandatory completeness
if record_mandatory == true OR dataelement_mandatory == true, value must be non_null