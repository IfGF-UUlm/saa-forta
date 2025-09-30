import json
import pandas as pd
from comorbidities.comorbidities import get_comorbidity_dict
from forta.forta import get_forta_list


if __name__ == "__main__":

    # Load single sample
    with open("single_sample.json") as f:
        sample = json.load(f)

    # Get comorbidities and forta list
    multimorbidity_dict = get_comorbidity_dict(sample)
    forta_list = get_forta_list(sample)

    # Export to JSON
    with open('multimorbidity.json', 'w') as f:
        json.dump(multimorbidity_dict, f, indent=4)

    forta_list.to_json('forta_list.json', indent=4)

