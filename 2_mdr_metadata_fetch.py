import pandas as pd
import requests
from datetime import date
import csv
import json


####################
# Configuration 
####################
NAMESPACE = "osse-11"          # adapt this to current registry 
REGISTRY_NAME = "ACLF"
MDR_BASE = "https://mdr.prod.osse-register.de/rest/api/mdr/"
OUTPUT_DIR = "metadata/processed"
HEADERS = {
    "Accept-Language": "en-US, en;q=0.7,de;q=0.3"
}
####################

def build_search_url(namespace):
    return f"{MDR_BASE}namespaces/{namespace}/search?query="

# function to build URL for fetching each specific data element
def build_dataelement_url(namespace, element_id, element_version):
    return f"{MDR_BASE}dataelements/urn:{namespace}:dataelement:{element_id}:{element_version}"

# function for sending request to MDR API returning JSON
def get_json(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()

# function to separate IDs and versions for building API URLs
def parse_urn_parts(urn): 
    parts = urn.split(":")
    return {
        "urn": urn,
        "id": parts[-2],
        "version": parts[-1]
    }

# calls search API, keeps dataelements, returns URNs
def get_elements(namespace):
    search_url = build_search_url(namespace)
    payload = get_json(search_url)

    dataelement_urns = []
    for result in payload.get("results", []):
        if result.get("type") == "DATAELEMENT":
            urn = result.get("identification", {}).get("urn")
            if urn:
                dataelement_urns.append(urn)

    return dataelement_urns

# Return slots information (radio  vs multicheckbox)
def check_slots(element_json):
    slots = element_json.get("slots", [])
    if slots:
        return slots[0].get("slot_value")
    return None

def extract_designation_info(element_json):
    designations = element_json.get("designations", [])
    if designations:
        first = designations[0]
        return {
            "language": first.get("language"),
            "designation": first.get("designation"),
            "definition": first.get("definition")
        }
    return {
        "language": None,
        "designation": None,
        "definition": None
    }


# function to build one row for data dictionary per element, with:
## ID, version, URN, stattus, designation, definiiton, datatype, format, slots
##{example
 #"dataelement_id": "45",
 #"datatype": "enumerated",
 #"format": "enumerated", etc
 

 # 
def extract_dataelement_row(element_json, element_id, element_version):
    designation_info = extract_designation_info(element_json)
    validation = element_json.get("validation", {})
    identification = element_json.get("identification", {})

    return {
        "dataelement_id": element_id,
        "dataelement_version": element_version,
        "dataelement_urn": identification.get("urn"),
        "status": identification.get("status"),
        "language": designation_info["language"],
        "dataelement_designation": designation_info["designation"],
        "dataelement_definition": designation_info["definition"],
        "datatype": validation.get("datatype"),
        "format": validation.get("format"),
        "slots": check_slots(element_json)
    }


# extract permissible values for datatype = enumerated
def extract_permissible_value_rows(element_json, element_id, element_version):
    rows = []
    validation = element_json.get("validation", {})
    datatype = validation.get("datatype")
    permissible_values = validation.get("permissible_values", [])

    if datatype != "enumerated":
        return rows

    selection_type = check_slots(element_json)
    dataelement_urn = element_json.get("identification", {}).get("urn")

    for item in permissible_values:
        meanings = item.get("meanings", [])
        first_meaning = meanings[0] if meanings else {}

        rows.append({
            "dataelement_id": element_id,
            "dataelement_version": element_version,
            "dataelement_urn": dataelement_urn,
            "pv_value": str(item.get("value")),
            "pv_language": first_meaning.get("language"),
            "pv_designation": first_meaning.get("designation"),
            "pv_definition": first_meaning.get("definition"),
            "pv_selection": selection_type
        })

    return rows

def fetch_namespace_metadata(namespace):
    dataelement_rows = []
    permissible_value_rows = []

    element_urns = get_elements(namespace)
    print(f"Found {len(element_urns)} data elements in namespace {namespace}")

    for urn in element_urns:
        urn_info = parse_urn_parts(urn)
        element_id = urn_info["id"]
        element_version = urn_info["version"]

        url = build_dataelement_url(namespace, element_id, element_version)
        element_json = get_json(url)

        dataelement_rows.append(
            extract_dataelement_row(element_json, element_id, element_version)
        )

        permissible_value_rows.extend(
            extract_permissible_value_rows(element_json, element_id, element_version)
        )

        print(f"Fetched data element {element_id}:{element_version}")

    df_dataelements = pd.DataFrame(dataelement_rows)
    df_permissible_values = pd.DataFrame(permissible_value_rows)

    return df_dataelements, df_permissible_values

def main():
    today = date.today().isoformat()

    df_dataelements, df_permissible_values = fetch_namespace_metadata(NAMESPACE)

    dataelements_path = f"{OUTPUT_DIR}/{today}_{REGISTRY_NAME}_API_MDR_dataelements.csv"
    permissible_values_path = f"{OUTPUT_DIR}/{today}_{REGISTRY_NAME}_API_MDR_permittedValues.csv"

    df_dataelements.to_csv(dataelements_path, index=False, sep=";", encoding="utf-8")
    df_permissible_values.to_csv(permissible_values_path, index=False, sep=";", encoding="utf-8")

    print(f"Saved data elements to: {dataelements_path}")
    print(f"Saved permissible values to: {permissible_values_path}")

if __name__ == "__main__":
    main()