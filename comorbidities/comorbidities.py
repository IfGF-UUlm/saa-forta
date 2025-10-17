from pathlib import Path
from json import load


# Standardized set of values representing missing or null data across inconsistent database entries
NULL = {None, 'NaN', '', ' '}


def load_comorbidity_mapping():
    """
    Load the comorbidity mapping from a JSON file.

    This function loads 'COMORBIDITY_MAPPING.json' located in the same directory
    as this script. The JSON should define a mapping of comorbidity labels to
    conditions that must be satisfied in patient data.

    Returns:
        dict: Parsed contents of the comorbidity mapping JSON file.
    """
    json_path = Path(__file__).parent / 'COMORBIDITY_MAPPING.json'
    with json_path.open('r') as f:
        return load(f)


def safe_get(sample, key, sentinel=None, cast=int):
    """
    Helper function to safely get and cast a value from a dict.

    Returns the sentinel if the key is missing, value is null-like, or cast fails.
    Also handles 'True'/'False' strings safely.
    """
    val = sample.get(key, sentinel)
    
    if val in NULL:
        return sentinel

    val_str = str(val).strip().lower()
    if val_str == "true":
        return True
    if val_str == "false":
        return False

    try:
        return cast(val)
    except (ValueError, TypeError):
        return sentinel


def get_comorbidities(sample_data):
    """
    Determines a tuple of comorbidities based on patient data and a predefined mapping.

    A comorbidity is considered present if all conditions associated with it
    are satisfied based on the patient's data. Conditions are specified in the
    COMORBIDITY_MAPPING.json file. Suspected diagnoses (prefixed with 'V. a. ')
    are skipped if their confirmed version is already identified.

    Args:
        sample_data (dict): Dictionary representing patient-specific data.

    Returns:
        tuple: A tuple containing comorbidity labels that match the patient data.
    """
    comorbidity_mapping = load_comorbidity_mapping()
    comorbidities = ()

    for diagnosis, logic in comorbidity_mapping.items():

        # Skip suspected diagnosis if confirmed version is already present
        if diagnosis.startswith("V. a. ") and diagnosis[6:] in comorbidities:
            continue

        for condition in logic:

            # All criteria within a condition must be met
            if all(safe_get(sample_data, key) in value for key, value in condition.items()):
                comorbidities += (diagnosis,)
                break

    return comorbidities


def multimorbidity_to_dict(comorbidities, max_number=20):
    """
    Converts a list of comorbidities into a fixed-length dictionary.

    The output dictionary contains keys labeled 'multimorbidity_1' through
    'multimorbidity_{max_number}', filled sequentially with the provided comorbidities.
    Remaining slots are filled with None if the list is shorter than `max_number`.

    Args:
        comorbidities (list or tuple): List or tuple of comorbidity strings.
        max_number (int, optional): Total number of keys to include in the output. Defaults to 20.

    Returns:
        dict: Dictionary with fixed-length comorbidity entries.
    """
    comorbidity_dict = {}

    for i in range(max_number):
        # Fill with actual comorbidity if available, otherwise use None
        if i < len(comorbidities):
            comorbidity_dict[f'multimorbidity_{i+1}'] = comorbidities[i]
        else:
            comorbidity_dict[f'multimorbidity_{i+1}'] = None

    return comorbidity_dict


def get_comorbidity_dict(sample_data):
    """
    Generate a fixed-length comorbidity dictionary from patient data.

    This function identifies comorbidities using predefined logic from a mapping file,
    then structures the result into a dictionary with fixed keys such as
    'multimorbidity_1', 'multimorbidity_2', etc.

    Args:
        sample_data (dict): Dictionary containing patient data.

    Returns:
        dict: Dictionary containing comorbidity entries in a fixed-length format.
    """
    comorbidities = get_comorbidities(sample_data)
    comorbidity_dict = multimorbidity_to_dict(comorbidities)

    return comorbidity_dict
