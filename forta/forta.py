from pathlib import Path
from json import load
import pandas as pd
from comorbidities.comorbidities import get_comorbidities


# Standardized set of values representing missing or null data across inconsistent database entries
NULL = {None, 'NaN', '', ' '}


def load_forta_database():
    """
    Loads the FORTA medication classification database CSV file.

    The CSV file is expected to be located in the same directory as this script,
    with the filename 'FORTA_database.csv'. The function reads the file into a pandas
    DataFrame and renames the 'FORTA-Klassifikation' column to 'FORTA' for consistency.

    Returns:
        pd.DataFrame: DataFrame containing FORTA medication data with columns such as
                      'Wirkstoff' (active substance), 'Indikation' (indication), and 'FORTA'.
    """
    database_path = Path(__file__).parent / 'FORTA_database.csv'
    forta_database = pd.read_csv(
        './forta/FORTA_database.csv'
    ).rename(columns={'FORTA-Klassifikation': 'FORTA'})
    
    return forta_database


def load_forta_mapping():
    """
    Loads the FORTA_MAPPING.json file, which maps comorbidities to FORTA indications.

    The JSON file is expected to be located in the same directory as this script.

    Returns:
        dict: Dictionary mapping comorbidities (strings) to FORTA indications. Values
              can be either a list of strings or conditional dictionaries.
    """
    json_path = Path(__file__).parent / 'FORTA_MAPPING.json'
    with open(json_path, 'r') as f:
        return load(f)


def get_medication(sample):
    """
    Extracts non-empty medication entries from a sample dictionary 
    with keys in the format 'medication_preop_<n>'.

    Parameters:
        sample (dict): A dictionary representing a row of data with 
                       medication keys such as 'medication_preop_1', ..., 'medication_preop_20'.

    Returns:
        list: A list of non-null, non-empty medication values.
    """
    medication = []

    for i in range(1, 21):
        if sample[f'medication_preop_{i}'] and sample[f'medication_preop_{i}'] not in NULL:
            medication.append(sample[f'medication_preop_{i}'])

    return medication


def forta_condition_check(condition_key, sample, comorbidities):
    """
    Evaluates a specific condition used to determine if a conditional FORTA indication applies.

    The condition keys correspond to predefined patient attributes or comorbidity checks.

    Args:
        condition_key (str): Identifier for the condition to evaluate (e.g., 'is_old', 'has_depression').
        sample (dict): Patient-specific data including demographics and lab values.
        comorbidities (iterable): List of comorbidity names detected for the patient.

    Returns:
        bool: True if the condition is met for the given sample and comorbidities, False otherwise.
              Defaults to True if the condition_key is unknown.
    """
    condition_map = {
        'has_depression': lambda s, c: 'Depression' in c,
        'has_insomnia': lambda s, c: 'Schlafstörung' in c,
        'is_woman': lambda s, c: s.get('sex', 1) == 0,
        'has_renal_failure': lambda s, c: s.get('lab_preop_egfr', 120) < 30,
        'has_no_renal_failure': lambda s, c: s.get('lab_preop_egfr', 120) >= 30,
        'is_old': lambda s, c: s.get('adm_age', 70) >= 85,
        'is_not_old': lambda s, c: s.get('adm_age', 70) < 85,
        'no_hypertension': lambda s, c: 'Arterielle Hypertonie' not in c,
        'has_pneumonia': lambda s, c: 'Pneumonie' in c,
    }

    # Return the result of the corresponding condition function, or True by default
    return condition_map.get(condition_key, lambda s, c: True)(sample, comorbidities)


def get_forta_indications(sample, comorbidities):
    """
    Determines the set of applicable FORTA indications for a patient based on their comorbidities
    and other patient-specific data.

    It processes each comorbidity and applies any conditional rules defined in the FORTA mapping
    to produce a comprehensive set of FORTA indications relevant to the patient.

    Args:
        sample (dict): Patient data including demographics, lab values, medications, etc.
        comorbidities (iterable): List of comorbidity names for the patient.

    Returns:
        set: A set of FORTA indication strings applicable to the patient.
    """
    forta_mapping = load_forta_mapping()
    forta_indications = set()

    for diagnosis in comorbidities:
        # Normalize diagnosis name by removing "V. a. " prefix if present
        diagnosis = diagnosis[6:] if diagnosis.startswith(
            'V. a. ') else diagnosis

        # Skip if diagnosis is not defined in FORTA mapping
        if diagnosis not in forta_mapping:
            continue

        for entry in forta_mapping[diagnosis]:
            if isinstance(entry, str):
                # Unconditional indication
                forta_indications.add(entry)
            elif isinstance(entry, dict):
                # Conditional indications
                for condition_key, indication in entry.items():
                    if forta_condition_check(condition_key, sample, comorbidities):
                        forta_indications.add(indication)

    return forta_indications


def make_forta_df(medication, forta_indications):
    """
    Filters the FORTA database for medications prescribed to the patient and relevant indications,
    returning matched entries along with their FORTA ratings.

    Args:
        medication (iterable): List of active substances prescribed to the patient.
        forta_indications (iterable): List or set of FORTA indications relevant to the patient.

    Returns:
        pd.DataFrame: DataFrame containing matching medications, indications, and their FORTA classification.
                      Sorted by 'Wirkstoff' and descending 'FORTA' rating.
    """
    forta_database = load_forta_database()

    # Filter database to substances and indications relevant to the patient
    forta_exact = forta_database[
        forta_database['Wirkstoff'].isin(medication) &
        forta_database['Indikation'].isin(forta_indications)
    ][['Wirkstoff', 'Indikation', 'FORTA']]

    # Sort by substance name for readability
    forta_exact = forta_exact.sort_values(
        by=['Wirkstoff', 'FORTA'], ascending=[True, False])

    return forta_exact


def add_remaining_med(forta_exact, medication):
    """
    Appends a summary row to the FORTA DataFrame listing medications that were prescribed
    but not matched to any FORTA indication for manual review.

    Args:
        forta_exact (pd.DataFrame): DataFrame of medications with matched FORTA indications.
        medication (iterable): Full list of medications prescribed to the patient.

    Returns:
        pd.DataFrame: The original DataFrame with an additional row summarizing unmatched medications,
                      with placeholder indication and FORTA class.
    """

    # Identify medications that are not in the matched DataFrame
    missing_medication = list(set(medication) - set(forta_exact['Wirkstoff']))
    missing_medication_string = ', '.join(sorted(missing_medication))

    # Add a summary row for unmatched medications
    new_row = pd.DataFrame([{
        'Wirkstoff': missing_medication_string,
        'Indikation': 'Indikation ggf. prüfen',
        'FORTA': '-'
    }])

    # Append the new row to the existing DataFrame
    forta_complete = pd.concat([forta_exact, new_row], ignore_index=True)

    return forta_complete


def get_forta_list(sample):
    """
    Generates a comprehensive FORTA classification DataFrame for a patient based on
    their comorbidities, prescribed medications, and other patient-specific data.

    The function:
        - Extracts comorbidities from patient data.
        - Maps comorbidities to FORTA indications (including conditional ones).
        - Matches prescribed medications with relevant indications in the FORTA database.
        - Adds a summary entry for any medications without matched FORTA indications.

    Args:
        sample (dict): Patient data including 'medication' (list of active substances),
                       demographics, lab values, etc.

    Returns:
        pd.DataFrame: DataFrame listing medications, their matched indications, and FORTA ratings.
                      Medications without matched indications are included in a separate summary row.
    """

    # Extract comorbidities from sample data
    comorbidities = get_comorbidities(sample)

    # Map comorbidities + sample context to FORTA indications
    forta_indications = get_forta_indications(sample, comorbidities)

    # Find exact FORTA matches for given medications and indications
    medication = get_medication(sample)
    forta_exact = make_forta_df(medication, forta_indications)

    # Add summary row for unmatched medications
    forta_complete = add_remaining_med(forta_exact, sample['medication'])

    return forta_complete
