import csv
import pandas as pd
import re


# Load metadata
## We´re using the data_element_list from the OSSE EDC. This can be loaded manually or via direct URL. 
## To ensure stability during pipeline development we will rely on a locally saved version for now

METADATA_PATH = "metadata/raw/data_element_list.csv"
METADATA_URL = "https://test.aclf.register.imi-frankfurt.de/schemata/data_element_list.csv"

def load_metadata(path=None, url=None):
    if path and url:
        raise ValueError("Provide either 'path' or 'url', not both.")
    if not path and not url:
        raise ValueError("Either 'path' or 'url' must be provided.")

    if url:
        # for now,  support the local file version first
        raise NotImplementedError("Custom CSV repair is currently implemented for local files only.")

    rows = []
# fixes issue with permissible values column having values across multiple columns (breaks expected fields)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)

        expected_cols = len(header)

        for i, row in enumerate(reader, start=2):
            if len(row) < expected_cols:
                row = row + [""] * (expected_cols - len(row))
            elif len(row) > expected_cols:
                row = row[:expected_cols - 1] + [",".join(row[expected_cols - 1:])]

            rows.append(row)

    df = pd.DataFrame(rows, columns=header)
    df.columns = df.columns.str.strip()

    return df
    
    


def rename_columns(df):
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        'Form': 'form',
        'Form ID:Version': 'form_id_version',
        'Form Type': 'form_type',
        'Record URN': 'record_urn',
        'Record Designation': 'record_designation',
        'Record Mandatory': 'record_mandatory',
        'Record Repeatable': 'record_repeatable',
        'Data Element - URN': 'dataelement_urn',
        'Data Element - Designation': 'dataelement_designation',
        'Data Element - Definition': 'dataelement_definition',
        'Data Element Mandatory': 'dataelement_mandatory',
        'Data Element Repeatable': 'dataelement_repeatable',
        'Data Type': 'data_type',
        'Data Format': 'data_format',
        'Unit of Measure': 'unit',
        'Permissible Values ...': 'permissible_values'
    })
    return df

def extract_ids(df):
    df['form_id'] = df['form_id_version'].str.extract(r'^(\d+)(?=:)')
    df['record_id'] = df['record_urn'].str.extract(r'(?<=:)(\d+)(?=:)')
    df['dataelement_id'] = df['dataelement_urn'].str.extract(r'(?<=:)(\d+)(?=:)')

    df['variable_id'] = (
        "X_" + df['form_id'] + "_" + df['record_id'] + "_" + df['dataelement_id']
    )

    return df

def drop_columns(df):
    df = df.drop(columns=['form', 'form_id_version','record_urn','dataelement_definition' ])
    return df


def preprocess_metadata(df):
    df = rename_columns(df)
    df = extract_ids(df)
    df = drop_columns(df)
    return df

def main():

    df_meta = load_metadata(path=METADATA_PATH)
    df_meta_clean=preprocess_metadata(df_meta)

    print(df_meta_clean.head())
    print(df_meta_clean.columns)

    df_meta_clean.to_csv("metadata/processed/metadata_clean.csv", index=False, sep=";")

if __name__ == "__main__":
    main()