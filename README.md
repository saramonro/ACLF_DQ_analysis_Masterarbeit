# Metadata-Driven Data Quality Assessment Pipeline

## Overview

This repository contains the prototypical metadata-driven data quality (DQ)
assessment pipeline developed for the Master's thesis.

The pipeline assesses registry data using information derived from registry
metadata and configurable contextual rules. The implemented checks cover
completeness, conformance and plausibility and are based on the categories of
the harmonized data quality assessment framework by Kahn et al.

The prototype was developed primarily for an OSSE registry and was additionally
applied to a second OSSE registry to assess transferability.

## Pipeline structure

The project is organized into four main components:

- `scripts/` – executable preprocessing and DQ assessment scripts
- `data/` – raw and processed registry data
- `metadata/` – structural, versioning, behavioral and contextual metadata
- `results/` – generated assessment outputs 
- `report/` – reporting module, template, and HTML report as output


The main pipeline is executed through `run_all.py`.

## Directory structure

```text
Pipeline/
├── scripts/
├── data/
│   ├── raw/
│   └── processed/
├── metadata/
│   ├── raw/
│   │   ├── structural/
│   │   └── versioning/
│   ├── processed/
│   ├── behavioral/
│   │   ├── calculations/
│   │   └── imports/
│   └── contextual/
├── reports/
│   ├── assets/
│   └── templates/
├── config.py
├── config.yaml
└── run_all.py

```

## Metadata Sources

The pipeline uses several types of metadata. Modules depend on the presence of specific metadata objects. 

### Structural Metadata
Describe the structure of the registry, data elements and forms definitions etc. The preprocessing steps (scripts 1 and 2) fetch metadata from the MDR and the registry`s EDC via direct public URL and REST API. The Scripts output the processed structural metadata objects usable by the check modules.

### Versioning Metadata
Versioning Metadata are required for Completeness. They should be saved under metadata/raw/versioning and are preprocessed by scripts 7.1 and 7.2.
Raw versioning metadata expected:
 - caseforms.csv - patient-form-version mappings for basic forms
 - episodeforms.csv - patient-form-version mappings for longitudinal forms
 - form_details.json - version history of Form Editor metadata

 Once processed, outputs are saved under metadata/processed/versioning

 ### Behavioural Metadata
 Represent programmed EDC logic. Implemented examples of checks using behavioural metadata include:
  - import conformance - requires "import_rules.csv" to be saved under metadata/behavioural/imports
  - calculation conformance - requires 3 metadata objects to be saved under metadata/behavioural/calculations

    Generation of these objects is currently not implemented in the pipeline and was performed manually for the prototype implementation. Templates for these metadata can however be found uder metadata/templates

### Contextual Metadata

Contextual rules contain registry-specific DQ knowledge that is not directly available from the structural metadata

 - temporal plausibility - requires date_rules.csv
 - longitudinal plausibility - requires longitudinal_plausibility.csv
  - completeness - requires core_elements.csv for core layer

   Generation of these objects is currently not implemented in the pipeline and was performed manually for the prototype implementation. Templates for these metadata can however be found uder metadata/templates



## Registry data

Raw registry export can be stored under data/raw/.

Preprocessing transforms the exported data into the standardized structure
required by the assessment modules. Processed files are written to
data/processed/.

### Configuration

Pipeline execution is controlled using config.yaml.

Individual scripts can be enabled or disabled in the scripts section of the
YAML configuration file by adding "true" or "false" in front of each script name.

Preprocessing scripts can be skipped if the outputs have already been generated previously.

An alternative configuration file can also be supplied when executing the
pipeline.

## Running the pipeline

Run all checks enabled in config.yaml:

python run_all.py

Run selected modules only:

python run_all.py --only 4_value-conformance 5_daterules


Each module is executed as a separate Python subprocess. Pipeline execution
stops if one of the enabled modules terminates with an error.

## Software requirements

The pipeline was implemented in Python.

Major Python packages used include:

pandas
Matplotlib
Jinja2

## Limitations

The software is a research prototype rather than a production-ready DQ system.

Its execution depends on the expected structure of the registry exports and
metadata files. Registry-specific metadata and contextual rules therefore
require preparation before applying the pipeline to another registry.