import json
import os
from collections import defaultdict
from io import StringIO
from io import BufferedWriter
from enum import Enum
from typing import Dict, Union

from pheval_elder.prepare.core.utils.obsolete_hp_mapping import update_hpo_id


class OMIMHPOExtractor:
    @staticmethod
    def extract_omim_hpo_mappings_old(data) -> Dict:
        """
        Extracts OMIM to HPO mappings from the provided data.

        :param data: String containing the data with OMIM and HPO information.
        :return: Dictionary with OMIM IDs as keys and lists of HPO IDs as values.
        """
        omim_hpo_dict = {}
        lines = data.split("\n")
        header_skipped = False

        for line in lines:
            if not line or line.startswith("#"):
                continue

            if not header_skipped:
                header_skipped = True
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                continue

            omim_id, disease_name, qualifier, hpo_id, frequency = parts[0], parts[1], parts[2], parts[3], parts[7]
            hpo_id = update_hpo_id(hpo_id)

            if frequency:
                frequency_percentage = frequency.strip("%")
            if qualifier != "NOT":
                if omim_id in omim_hpo_dict:
                    omim_hpo_dict[omim_id].add(hpo_id)
                    if frequency in omim_hpo_dict:
                        omim_hpo_dict[omim_id].add(frequency)
                else:
                    omim_hpo_dict[omim_id] = {hpo_id}
                    omim_hpo_dict[omim_id] = {frequency}

        for omim in omim_hpo_dict:
            omim_hpo_dict[omim] = list(omim_hpo_dict[omim])
        print(len(omim_hpo_dict))
        return omim_hpo_dict

    @staticmethod
    def extract_omim_hpo_mappings_default(data):
        """
        Extracts OMIM to HPO mappings from the provided data.

        :param data: String containing the data with OMIM and HPO information.
        :return: Dictionary with OMIM IDs as keys and lists of HPO IDs as values.
        """
        omim_hpo_dict = defaultdict(lambda: {"disease_name": None, "phenotypes": []})
        lines = data.split('\n')
        header_skipped = False

        for line in lines:
            if line.startswith("#"):
                continue

            if "database_id" in line and "disease_name" in line and "qualifier" in line and "hpo_id" in line:
                header_skipped = True
                continue
            if not header_skipped:
                continue

            parts = line.split('\t')
            if len(parts) < 8:
                continue

            omim_id, disease_name, hpo_id = parts[0].strip(), parts[1].strip(), parts[3].strip()

            updated_id = update_hpo_id(hpo_id)
            omim_hpo_dict[omim_id]['phenotypes'].append(updated_id)
            omim_hpo_dict[omim_id]['disease_name'] = disease_name

        final_omim_hpo_dict = {k: {"disease_name": v["disease_name"], "phenotypes": sorted(v["phenotypes"])} for k,v in omim_hpo_dict.items()}

        """
        {
            "OMIM:101600": {
                "disease_name": "Marfan Syndrome",
                "phenotypes": ["HP:0001250", "HP:0001263", "HP:0001274"]
        },
            "OMIM:203800": {
                "disease_name": "Cystic Fibrosis",
                "phenotypes": ["HP:0001733", "HP:0002023", "HP:0002715"]
            }
        }

        """

        return final_omim_hpo_dict

    @staticmethod
    def extract_omim_hpo_mappings_with_frequencies_1(data) -> Dict[str, Dict[str, Union[str, Dict[str, float]]]]:
        """
                Extracts OMIM to HPO mappings from the provided data.

                :param data: String containing the data with OMIM and HPO information.
                :return: Dictionary with OMIM IDs as keys and lists of HPO IDs as values.
                """
        omim_hpo_dict = defaultdict(lambda: {"disease_name": None, "phenotypes_and_frequencies": {}})
        lines = data.split("\n")
        header_found = False
        # Frequency mapping for special HPO terms referring to freq in DAG
        # TODO: those are ranges, i hardcoded for specific values inside those ranges, adapt ...
        special_frequencies = {
            "HP:0040281": 80.0,  # Very frequent
            "HP:0040283": 20.0,  # Occasional
            "HP:0040280": 100.0,  # Obligate
            "HP:0040285": 0.0,  # Excluded
            "HP:0040282": 50.0,  # Frequent
            "HP:0040284": 1.0  # Very rare
        }

        for line in lines:
            if line.startswith("#"):
                continue
            if "database_id" in line and "disease_name" in line and "qualifier" in line and "hpo_id" in line:
                header_found = True
                continue
            if not header_found:
                continue

            parts = [part.strip() for part in line.split("\t")]

            if len(parts) < 8:
                continue

            omim_id, disease_name, qualifier, hpo_id, frequency = parts[0], parts[1], parts[2], parts[3], parts[7]
            hpo_id = update_hpo_id(hpo_id)
            if not omim_id or not hpo_id:
                continue

            # Determine frequency as proportion, default to 0.5 if not in special frequencies
            if frequency in special_frequencies:
                frequency_proportion = special_frequencies[frequency] / 100

            if '/' in frequency:
                numerator, denominator = map(float, frequency.split('/'))
                frequency_proportion = numerator / denominator
            else:
                frequency_proportion = 0.5

            if qualifier != "NOT":
                omim_hpo_dict[omim_id]['phenotypes_and_frequencies'][hpo_id] = frequency_proportion
                omim_hpo_dict[omim_id]['disease_name'] = disease_name

                """ 
                "WAS"
                {
                    "OMIM:101600": {
                        "HP:00001": 0.5,
                        "Hp:00002": 0.3
                    }
                }

                { 
                "IS"
                    "OMIM:101600": {
                        "phenotypes_and_frequencies":{
                            "HP:00001": 0.5,
                            "Hp:00002": 0.3
                    },
                    "disease_name" : "Marfan Syndrome", }
                }
                """

        return omim_hpo_dict


    @staticmethod
    def read_data_from_file(file_path):
        """
        Reads data from a file at the given file path.

        :param file_path: Path to the file to read.
        :return: String containing the file's content.
        """
        with open(file_path, 'r') as file:
            data = file.read()
        return data

    # for testing
    @staticmethod
    def save_results_as_pretty_json_string(data: Dict, outfile: str):
        """
            Prints the given Dictionary in a nice format
        """
        output_dir = "/Users/carlo/Downloads/pheval.exomiser/output"
        result_path = os.path.join(output_dir, outfile)
        dump = json.dumps(data, sort_keys=True, indent=4)
        with (open(result_path, "w") as file):
            file.write(dump)

