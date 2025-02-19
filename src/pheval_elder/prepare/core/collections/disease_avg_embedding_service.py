import logging
import time
from typing import Optional

import numpy as np
from dataclasses import dataclass
from chromadb.types import Collection

from tqdm import tqdm

from pheval_elder.prepare.core.collections.base_service import BaseService
from pheval_elder.prepare.core.data_processing.data_processor import DataProcessor
from pheval_elder.prepare.core.utils.utils import populate_venomx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DiseaseAvgEmbeddingService(BaseService):
    data_processor: Optional[DataProcessor]

    def process_data(self) -> Collection:
        if not self.disease_to_hps:
            raise ValueError("disease to hps data is not initialized")
        if not self.disease_new_avg_embeddings_collection:
            raise ValueError("disease_new_avg_embeddings collection is not initialized")
        if self.disease_new_avg_embeddings_collection:
            logger.info(f"Return Exisiting DiseaseAvgEmbeddingsCollection {self.disease_new_avg_embeddings_collection}")
            return self.disease_new_avg_embeddings_collection

        batch_size = 500
        num_diseases = len(self.disease_to_hps)
        batch_embeddings = np.zeros((batch_size, 1536)) #3072 for large model
        # Use dtype=object for flexibility with string lengths and special characters, avoiding truncation issues.
        batch_diseases = np.empty(batch_size, dtype=object)
        current_index = 0
        embedding_calc_time = 0
        upsert_time = 0

        for disease, hps in tqdm(self.disease_to_hps.items(), total=num_diseases):
            # Check if hps is empty; if so, log and skip.
            if not hps:
                logger.warning(f"No HP data for disease: {disease}. Skipping.")
                continue

            start = time.time()
            average_embedding = self.data_processor.calculate_average_embedding(hps, self.hp_embeddings)
            embedding_calc_time += time.time() - start

            batch_diseases[current_index] = disease
            batch_embeddings[current_index] = average_embedding
            current_index += 1

            if current_index % batch_size == 0:
                self.upsert_batch(batch_diseases, batch_embeddings)
                current_index = 0

        if current_index > 0:
            start = time.time()
            self.upsert_batch(batch_diseases[:current_index], batch_embeddings[:current_index])
            upsert_time += time.time() - start

        print(f"Total time for embedding calculations (avg): {embedding_calc_time}s")
        print(f"Total time for upsert operations (avg): {upsert_time}s")

        return self.disease_new_avg_embeddings_collection

    def upsert_batch(self, disease_ids, embeddings):
        valid_indices = [i for i, disease in enumerate(disease_ids) if disease is not None]
        filtered_ids = [disease_ids[i] for i in valid_indices]
        metadatas = [{"type": "disease"}] * len(disease_ids)
        # col_metadata = self.disease_new_avg_embeddings_collection.metadata
        self.disease_new_avg_embeddings_collection.upsert(ids=filtered_ids, embeddings=embeddings, metadatas=metadatas)

    # def metadata(self):
    #     metadata = populate_venomx()

