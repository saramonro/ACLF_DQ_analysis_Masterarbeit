

# ACLF_DQ_analysis_Masterarbeit

## export_data_preprocess

Input: raw OSSE export (wide format)
Output: long format export data

 - loads raw export
 - removes outdated variables
 - skips metadata/header rows
 - drops unnecessary columns
 - renames columns
 - creates IX repeat index
 - converts wide to long (melt method)
 - output: export_long.csv

## mdr_metadata_fetch
Input: MDR API namespace
Output: MDR Metadata 

 - builds search URL with namespace
 - builds data element URL with namespace
 - calls MDR API
 - extracts all data elements in the namespace
 - extracts datatype, format, status, definition, slots
 - extracts permissible values
 
 - outputs: metadata/processed/..._API_MDR_dataelements.csv
metadata/processed/..._API_MDR_permittedValues.csv

## create_data_dictionary
Input: MDR_dataelements, data_element_list.csv (formEditor metadata)
Otput: data dictionary

- loads only stable columns from data_element_list - first 15 columns; skips permissible values to avoid parsing issues.
- renames columns
- generates source IDS (form ID, record URN, dataelement URN)
- merges with MDR metadata - columns included from MDR data = slots and URN

Output: final data_dictionary with all metadata from MDR + form editor + unique source_ids for variables
