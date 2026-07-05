

###
# This script runs some preprocessing steps on the Raw OSSE Export data
## Removes unnecessary columns
## Renames columns
## Drops outdated Data Elements
## Turns data into long format
###


import pandas as pd
import csv
from pathlib import Path

# Paths will be added to config.py later
DATA_PATH = "data/raw/ACLF_2026-02-12_MDAT.csv"
OUTPUT_DIR = Path("data\processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "Export_long.csv"

#Load data (includes metadata rows)

def load_raw_export(path):
    df_raw = pd.read_csv(path, dtype="object", sep=";", header=None)
    return df_raw

#Drop outdated elements, check w Jessica if this is safe
def drop_outdated_columns(df_raw):
    outdated_row = df_raw.iloc[4].fillna("").astype(str)

    outdated_mask = outdated_row.str.contains("outdated", case=False, na=False)

    print("Outdated columns:")
    print(df_raw.loc[7, outdated_mask].tolist())
    return df_raw.loc[:, ~outdated_mask].copy()

def extract_data_table(df_raw):
    header_row = 7
    data_start_row = 8

    df = df_raw.iloc[data_start_row:].copy()
    df.columns = df_raw.iloc[header_row]
    df.reset_index(drop=True, inplace=True)

    return df

#Remove unnecessary columns
def drop_columns(df):
    df = df.drop(columns=['patient repeat number', 'Unique ID (Form_Record_DataElement):'])
    return df

# Drop Test Patients (patients in Test Locations)
def drop_test_data(df):
  
    mask_test = (
        df["Location"]
        .astype(str)
        .str.lower()
        .str.contains("test location", na=False)
    )

    df_clean = df[~mask_test].copy()

    print(f"Dropped {mask_test.sum()} test rows")

    return df_clean

#Rename columns
def rename_columns(df):
    df = df.rename(columns={'Episode number': 'episode',
                                             'episode date': 'episode_date',
})
    return df

#Wide to Long format conversion

def wide_to_long(df):
## add index column for repeatables (including checkboxes)
    df_wide = df.drop(columns=['Location', 'Episode_Description']).copy()
    df_wide['Episode'] = df_wide['Episode'].fillna(0)
    df_wide['IX'] = df_wide.groupby(['PID', 'Episode','Episode_Date']).cumcount().add(1).fillna(0).astype(int)

## convert dataframe into long format using PID / Episode / Episode date/ IX as id variables and column names (parameters) as variable names
    data_long = pd.melt(df_wide, 
                                id_vars=['PID', 'Episode', 'Episode_Date', 'IX'],
                                    var_name='source_id',
    value_name='source_value')
        
    return data_long


def preprocess_export_data(df):
    df= drop_test_data(df)
    df = drop_columns(df)
    df = rename_columns(df) 
    return df

def main():
    df_raw = load_raw_export(DATA_PATH)
    df_raw = drop_outdated_columns(df_raw)
    df = extract_data_table(df_raw)
    df_clean = preprocess_export_data(df)
    df_long = wide_to_long(df_clean)
    df_long.to_csv(OUTPUT_PATH, index=False, sep=';', quoting=csv.QUOTE_ALL, encoding='UTF-8')
   

    
if __name__ == "__main__":
    main()