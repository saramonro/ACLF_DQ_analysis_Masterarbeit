This file describes the structure of the created data_dictionary, what each column means, its source and its possible values

each row = 1 variable
variable = one unique instance of a data element + record(if any) + form

# Form
Name of the form the variable is in (raw text)
# form_id
form ID (X) + form version (Y) format X:Y
# form_type
either "Basic" or "Longitudinal"
# record_URN
either empty if variable doesn´t belong to a record, or the record´s full URN (urn:namespace:record:ID:version)
# record_designation
either empty if variable doesn´t belong to a record, or the record´s text designation
# record_mandatory
either empty if variable doesn´t belong to a record, or "true" or "false" on whether the record is mandatory
# record_repeatable
either empty if variable doesn´t belong to a record, or "true" or "false" on whether the record is repeatable
# dataelement_urn
datalement URN (urn:namespace:dataelement:ID:version)
# dataelement_designation
raw text designation of dataelement (as shown in EDC)
# dataelement_definition
raw text definition of dataelement (tooltip)
# dataelement_mandatory
true if dataelement is mandatory, false if not, and empty if the variable belongs to a record (in which case variable´s mandatory status is defined by record_mandatory)
# data_type
data type of the variable - can be STRING, enumerated, DATE, FLOAT, BOOLEAN or INTEGER
# data_format
defines the data format, depending on data type, or the range in case of numerical values. for each data type are possible formats:
## enumerated
enumerated
## DATE
DD.MM.YYYY, MM.YYYY, MM-DD-YYYY, MM-YYYY
## FLOAT
when x = value and y and z any number where z>y, format can be:
x - no range defined
y<x<z
y<x
x<z
y<=x<=z
y<=x
x<=z
## INTEGER
same as float
## STRING
max. number of characters, or empty

# unit
for numericals (float and integer), defines the unit presented on EDC

# source_id
unique variable id, in format X_000_0_00, or x_formid_recordURN_dataelementURN (recordURD = 0 if variable isnt in a record)

# slots
for enumerated types (empty for other types)
## SELECT_MANY_CHECKBOX 
for a multiple choice selection, 
## SELECT_ONE_RADIO
 for radio buttons, 
## empty
dropdown( single choice selection)
