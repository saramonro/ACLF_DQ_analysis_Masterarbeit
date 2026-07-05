# Data Dictionary creation with registry IDs

# This script generates unique IDs from information extracted from MDR API, and compares it to the data_element_list to generate a final Data Dictionary with only registry-present Data Elements.


# Configuration 
NAMESPACE = "osse-11"          # adapt this to current registry 
REGISTRY_NAME = "ACLF"
URL_PREFIX = "test.aclf"
STRUCTURE_URL = f"https://{URL_PREFIX}.register.imi-frankfurt.de/schemata/data_element_list.csv"
MDR_DE_PATH = "metadata/processed/ACLF_API_MDR_dataelements.csv"
OUTPUT_DIR = "metadata/processed"

import pandas as pd
import numpy as np
import os

# function to load data_element_list; only first 15 columns are loaded to avoid parsing issues with permissible values column. adjust if necessary.
def load_structure_metadata(path):
    cols_to_keep = [
    "Form",
    "Form ID:Version",
    "Form Type",
    "Record URN",
    "Record Designation",
    "Record Mandatory",
    "Record Repeatable",
    "Data Element - URN",
    "Data Element - Designation",
    "Data Element - Definition",
    "Data Element Mandatory",
    "Data Element Repeatable",
    "Data Type",
    "Data Format",
    "Unit of Measure"
]

    df = pd.read_csv(path, dtype="object", sep=",", encoding="utf-8-sig",usecols=cols_to_keep)
    return df


def rename_columns(df):
    df = df.rename(columns={'Form ID:Version': 'form_id',
                                             'Form Type': 'form_type',
                                             'Record URN': 'record_urn',
                                             'Record Designation' : 'record_designation',
                                             'Record Mandatory' :'record_mandatory',
                                              'Record Repeatable':'record_repeatable',
                                               'Data Element - URN':'dataelement_urn' ,
                                               'Data Element - Designation':'dataelement_designation',
                                               'Data Element - Definition': 'dataelement_definition',
                                               'Data Element Mandatory':'dataelement_mandatory',
                                               'Data Element Repeatable' : 'dataelement_repeatable',
                                               'Data Type':'data_type',
                                               'Data Format': 'data_format',
                                               'Unit of Measure':'unit'
                                               })
    return df


def generate_source_ids(df):

    df.dropna(how='all', inplace=True)
    df['record_urn'] = df['record_urn'].fillna('0:0:0:0:0') # placeholder for data elements without record
    df['source_id'] = "X_" + df['form_id'].str.split(":").str[0] + '_' + df['record_urn'].str.split(":").str[3] + '_' + df['dataelement_urn'].str.split(":").str[3]
    df.drop_duplicates(subset='source_id', inplace=True)
    df['record_urn'] = df['record_urn'].replace('0:0:0:0:0', pd.NA) # removes placeholder
    return df

def load_mdr_dataelements(path):
    df = pd.read_csv(path, dtype="object", sep=";")
    return df

def remove_urn_version(urn):
    parts = str(urn).split(":")
    return ":".join(parts[:-1])


def add_base_urns(df):
    df = df.copy()
    df["dataelement_base_urn"] = df["dataelement_urn"].apply(remove_urn_version)
    return df

def merge_structure_with_mdr(df_structure, df_mdr):
    df_structure = add_base_urns(df_structure)
    df_mdr = add_base_urns(df_mdr)

    # Keep only MDR versions of elements that still exist in the current structure
    current_base_urns = df_structure["dataelement_base_urn"].dropna().unique()

    df_mdr_current = df_mdr[
        df_mdr["dataelement_base_urn"].isin(current_base_urns)
    ].copy()

    df_mdr_slots = df_mdr_current[
        ["dataelement_base_urn", "dataelement_urn", "slots"]
    ].copy()

    df_mdr_slots = df_mdr_slots.rename(
        columns={"dataelement_urn": "dataelement_urn_mdr"}
    )

    df_merged = df_structure.merge(
        df_mdr_slots,
        how="left",
        on="dataelement_base_urn"
    )

    return df_merged



def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True) 
    structure_metadata=load_structure_metadata(STRUCTURE_URL)
    clean_structure_metadata = rename_columns(structure_metadata)
    structure_metadata_with_ids = generate_source_ids(clean_structure_metadata)
    mdr_data=load_mdr_dataelements(MDR_DE_PATH)
    data_dictionary=merge_structure_with_mdr(structure_metadata_with_ids,mdr_data)
    output_path = f"{OUTPUT_DIR}/data_dictionary_with_versions.csv"
    data_dictionary.to_csv(output_path, index=False, sep=";")

if __name__ == "__main__":
    main()