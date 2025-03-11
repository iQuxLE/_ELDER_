import logging
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from dataclasses import dataclass
from functools import cached_property, cache
from typing import Dict, Iterator, Any
from pathlib import Path
import numpy as np
from chromadb.types import Collection

from pheval_elder.prepare.core.data_processing.OMIMHPOExtractor import OMIMHPOExtractor
from pheval_elder.prepare.core.store.chromadb_manager import ChromaDBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DataProcessor:

    db_manager: ChromaDBManager

    def __post_init__(self):
        self._hp_embeddings = None
        self._disease_to_hps = None
        self._disease_to_hps_with_frequencies = None

    @cached_property
    def hp_embeddings(self) -> Dict[str, Dict[str, Any]]:
        if self._hp_embeddings is None:
            self._hp_embeddings = self.create_hpo_id_to_embedding(self.db_manager.ont_hp)
        if len(self._hp_embeddings) > 0:
            return self._hp_embeddings
        else:
            logger.warning(f"No HPO embeddings found for {self.db_manager.ont_hp}")
            return {}

    @cached_property
    def disease_to_hps_with_frequencies(self) -> Dict:
        if self._disease_to_hps_with_frequencies is None:
            file = Path(__file__).resolve().parents[5]
            file_path = file / "phenotype.hpoa"
            data = OMIMHPOExtractor.read_data_from_file(file_path)
            self._disease_to_hps_with_frequencies = OMIMHPOExtractor.extract_omim_hpo_mappings_with_frequencies_1(data)
        return self._disease_to_hps_with_frequencies

    @cached_property
    def disease_to_hps(self) -> Dict:
        if self._disease_to_hps is None:
            file = Path(__file__).resolve().parents[5]
            file_path = file / "phenotype.hpoa"
            data = OMIMHPOExtractor.read_data_from_file(file_path)
            self._disease_to_hps = OMIMHPOExtractor.extract_omim_hpo_mappings_default(data)
        return self._disease_to_hps

    @staticmethod
    def create_hpo_id_to_embedding(collection: Collection) -> Dict[str, Dict[str, Any]]:
        """
        Create a dictionary mapping HPO IDs to embeddings.
        """
        hpo_id_to_data = defaultdict(dict)
        results = collection.get(include=["metadatas", "embeddings"])
        for metadata, embedding in zip(results.get("metadatas", []), results.get("embeddings", []), strict=False):
            hpo_id = None
            if isinstance(metadata, dict) and "_json" in metadata:
                try:
                    metadata_json = json.loads(metadata["_json"])
                    hpo_id = metadata_json.get("original_id")
                    label = metadata_json.get("label")
                    if hpo_id is None and isinstance(metadata_json.get("metadata"), dict):
                        hpo_id = metadata_json["metadata"].get("original_id")
                        label = metadata_json["metadata"].get("label")
                except (json.decoder.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse _json metadata: {e}")
            if hpo_id:
                if label is None:
                    logger.warning(f"Warning: Label missing for {hpo_id}, setting default")
                    label = "Unknown"
                hpo_id_to_data[hpo_id] = {
                    "label": label,
                    "embeddings": np.array(embedding)
                }
            else:
                logger.warning(f"Warning: Missing 'original_id' in metadata: {metadata}")
        return hpo_id_to_data

    @staticmethod
    def create_disease_to_hps_dict(collection: Collection) -> Dict:
        """
        Creates a dictionary mapping diseases (OMIM IDs) to their associated HPO IDs.
        """
        disease_to_hps_dict = {}
        results = collection.get(include=["metadatas"])
        for item in results.get("metadatas"):
            metadata_json = json.loads(item["_json"])
            disease = metadata_json.get("disease")
            phenotype = metadata_json.get("phenotype")
            if disease and phenotype:
                if disease not in disease_to_hps_dict:
                    disease_to_hps_dict[disease] = [phenotype]
                else:
                    disease_to_hps_dict[disease].append(phenotype)
        return disease_to_hps_dict

    @staticmethod
    def calculate_average_embedding(hps: list, embeddings_dict: Dict) -> np.ndarray:
        embeddings = [embeddings_dict[hp_id]["embeddings"] for hp_id in hps if hp_id in embeddings_dict]
        return np.mean(embeddings, axis=0) if embeddings else []

    @staticmethod
    def convert_embeddings_to_numpy(embeddings_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, np.ndarray]]:
        return {k: {'embeddings': np.array(v['embeddings'])} for k, v in embeddings_dict.items()}

    @staticmethod
    def calculate_average_embedding_weighted(hps_with_frequencies: dict, embeddings_dict: dict) -> np.ndarray:
        embeddings_dict = DataProcessor.convert_embeddings_to_numpy(embeddings_dict)
        weighted_embeddings = []
        total_weight = 0
        for hp_id, proportion in hps_with_frequencies.items():
            embedding = embeddings_dict.get(hp_id, {}).get('embeddings')
            if embedding is not None:
                weighted_embeddings.append(proportion * embedding)
                total_weight += proportion
        if total_weight > 0:
            return np.sum(weighted_embeddings, axis=0) / total_weight
        return np.array([])

    def calculate_weighted_llm_embeddings(self, disease: str) -> np.ndarray:
        weighted_embeddings = np.zeros_like(next(iter(self.hp_embeddings.values()))['embeddings'])
        total_weight = 0
        hps_with_frequencies = self.disease_to_hps_with_frequencies[disease]['phenotypes_and_frequencies']
        for hp_id, proportion in hps_with_frequencies.items():
            embedding = self.hp_embeddings.get(hp_id, {}).get('embeddings')
            if embedding is not None:
                weighted_embeddings += proportion * embedding
                total_weight += proportion
        
        if total_weight > 0:
            return weighted_embeddings / total_weight
        return np.array([])

