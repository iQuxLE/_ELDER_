from dataclasses import dataclass
from typing import Any, List, Optional
from chromadb.types import Collection
from deprecation import deprecated

from pheval_elder.prepare.core.store.chromadb_manager import ChromaDBManager
from pheval_elder.prepare.core.data_processing.data_processor import DataProcessor
from pheval_elder.prepare.core.collections.disease_avg_embedding_service import DiseaseAvgEmbeddingService
from pheval_elder.prepare.core.collections.disease_weighted_avg_embedding_service import DiseaseWeightedAvgEmbeddingService


@dataclass
class QueryService:

    data_processor: DataProcessor
    db_manager: ChromaDBManager
    average_llm_embedding_service: Optional[DiseaseAvgEmbeddingService] = None
    weighted_average_llm_embedding_service: Optional[DiseaseWeightedAvgEmbeddingService] = None
    similarity_strategy=None,[]

    def __post_init__(self):
        self.db_manager = self.db_manager
        self.data_processor = self.data_processor
        self.similarity_strategy = self.similarity_strategy
        self.hp_embeddings = self.data_processor.hp_embeddings
        self.disease_to_hps_from_omim = self.data_processor.disease_to_hps_with_frequencies
        if self.average_llm_embedding_service:
            self.disease_service = self.average_llm_embedding_service
        if self.weighted_average_llm_embedding_service:
            self.disease_weighted_service = self.weighted_average_llm_embedding_service


    '''
    The following is for the weighted average approach using LLM embeddings:
    '''

    def query_for_weighted_average_llm_embeddings_collection_top10_only(
            self,
            hps: List[str],
            n_results: int = 10
    ) -> list[Any]:
        """
        Queries the 'DiseaseWeightedAvgEmbeddings' collection for diseases closest to the weighted average embeddings of given HPO terms.

        :param hps: List of HPO term IDs.
        :param n_results: Optional number of results to return. Returns all if None.
        :return: List of diseases sorted by closeness to the average HPO embeddings.
        """

        avg_embedding = self.data_processor.calculate_average_embedding(hps,self.hp_embeddings)

        if avg_embedding is None:
            raise ValueError("No valid embeddings found for provided HPO terms.")

        query_params = {
            "query_embeddings": [avg_embedding.tolist()],
            "include": ["embeddings", "distances"],
            "n_results": n_results
        }

        query_results = self.disease_weighted_service.disease_weighted_avg_embeddings_collection.query(
            **query_params)
        disease_ids = query_results['ids'][0] if 'ids' in query_results and query_results['ids'] else []
        distances = query_results['distances'][0] if 'distances' in query_results and query_results[
            'distances'] else []
        sorted_results = sorted(zip(disease_ids, distances), key=lambda x: x[1])  # remember to add label
        return sorted_results

    def query_for_weighted_average_llm_embeddings_collection_top10_with_new_approach(
        self,
        hps: List[str],
        n_results: int = 10
    ) -> list[Any]:
        """
        Queries the 'DiseaseWeightedAvgEmbeddings' collection for diseases closest to the weighted average embeddings of given HPO terms.

        :param hps: List of HPO term IDs.
        :param n_results: Optional number of results to return. Returns all if None.
        :return: List of diseases sorted by closeness to the average HPO embeddings.
        """

        # TODO: can be made better

        '''
        write a function that takes this input list, goes through every disease and takes the weights for the hp_terms
        so we check the inputted HP terms of every single possible disease with its relevant weights
        
        
        input_list: [HP1, HP2, HP3, HP4, HP5]
        (if disease would share same phenotypes):
        DiseaseA: {HP1 : 0.5, HP2: 0.5, HP3: 0.5, HP4 : 0.5, HP5: 1}
        DieasesB: {HP1 : 0, HP2: 1, HP3: 1, HP4 : 0.5, HP5: 0 }
        DiseaseC: {HP1 : 1, HP2: 1, HP3: 1, HP4 : 1, HP5: 1}
        DiseaseD: {HP1 : 0, HP2: 0, HP3: 0, HP4 : 0, HP5: 1}
        
        should be getting DiseaseC by logic when taking their weights into account.
        samle for all others, see:
        With WeightsA: [0.5, 0.5, 0.5, 0.5, 1] would find A but rest not
        
        so maybe just check and write a function and how well it performs.
        
        Example might not say everything.
        
        But generally, when I maybe only take into account full 100% HPs, maybe it helps detection?
        What would be the downside of this approach? -> Instagram Stories notebook
        
        
        If diseases would not share same phenotypes
        DiseaseA: {HP4 : 0.5, HP10: 0.5, HP11: 0.5, HP12 : 0.5, HP22: 1}
        DieasesB: {HP5 : 0, HP1: 1, HP20: 1, HP21 : 0.5, HP30: 0 }
        DiseaseC: {HP6 : 1, HP8: 1, HP34: 1, HP42 : 1, HP40: 1}
        DiseaseD: {HP7 : 0, HP24: 0, HP300: 0, HP41 : 0, HP50: 1}
        '''
        hp_index = 0
        for disease, frequency_dict in self.data_processor.disease_to_hps_with_frequencies.items():
            hp_id = hps[hp_index]
            hp_index += 1
            # for hp

            avg_embedding = self.data_processor.calculate_weighted_average_for_hp_inputlist(disease, hps, self.hp_embeddings)
            if avg_embedding is None:
                raise ValueError("No valid embeddings found for provided HPO terms.")

            query_params = {
                "query_embeddings": [avg_embedding.tolist()],
                "include": ["embeddings", "distances"],
                "n_results": n_results
            }

            query_results = self.disease_weighted_service.disease_weighted_avg_embeddings_collection.query(**query_params)
            disease_ids = query_results['ids'][0] if 'ids' in query_results and query_results['ids'] else []
            distances = query_results['distances'][0] if 'distances' in query_results and query_results['distances'] else []
            sorted_results = sorted(zip(disease_ids, distances), key=lambda x: x[1])  # remember to add label
            return sorted_results
            pass

    '''
    The following is for the normal average approach using LLM embeddings:
    '''

    def query_for_average_llm_embeddings_collection_top10_only(
        self,
        hpo_ids: List[str],
        n_results: int = 10
    ) -> list[Any]:
        """
        Queries the 'DiseaseAvgEmbeddings' collection for diseases closest to the average embeddings of given HPO terms.

        :param hpo_ids: List of HPO term IDs.
        :param n_results: Optional number of results to return. Returns all if None.
        :return: List of diseases sorted by closeness to the average HPO embeddings.
        """
        avg_embedding = self.data_processor.calculate_average_embedding(hpo_ids, self.hp_embeddings)
        if avg_embedding is None:
            raise ValueError("No valid embeddings found for provided HPO terms.")

        query_params = {
            "query_embeddings": [avg_embedding.tolist()],
            "include": ["metadatas","embeddings", "distances"],
            "n_results": n_results
        }

        query_results = self.disease_service.disease_new_avg_embeddings_collection.query(**query_params)
        # print("query", query_results)
        sorted_results = self.process_query_results(query_results=query_results)
        return sorted_results

    '''
    The following is for the normal average apporach using LLM embeddings but giving output of the whole results,
    so every single rank
    '''

    def query_for_average_llm_embeddings_collection(
        self,
        hpo_ids: List[str],
        n_results: int = None
    ) -> list[Any]:
        """
        Queries the 'DiseaseAvgEmbeddings' collection for diseases closest to the average embeddings of given HPO terms.

        :param hpo_ids: List of HPO term IDs.
        :param n_results: Optional number of results to return. Returns all if None.
        :return: List of diseases sorted by closeness to the average HPO embeddings.
        """
        print("n_results at default  = :" + f"{n_results}")
        avg_embedding = self.data_processor.calculate_average_embedding(hpo_ids, self.hp_embeddings)
        if avg_embedding is None:
            raise ValueError("No valid embeddings found for provided HPO terms.")

        query_params = {
            "query_embeddings": [avg_embedding.tolist()],
            "include": ["embeddings", "distances"]
        }

        if n_results is None:
            estimated_total = self.disease_service.disease_new_avg_embeddings_collection.get(include=['metadatas'])
            estimated_length = len(estimated_total["metadatas"])  # 12468 - 1
            print(f"Estimated length (n_results) == {estimated_length}")
            max_n_results = self.binary_search_max_results_nocol(query_params, 11700, estimated_length)
            query_params["n_results"] = max_n_results
            print(f"Using max safe n_results: {max_n_results}")
        else:
            query_params["n_results"] = n_results

        query_results = self.disease_service.disease_new_avg_embeddings_collection.query(**query_params)
        disease_ids = query_results['ids'][0] if 'ids' in query_results and query_results['ids'] else []
        distances = query_results['distances'][0] if 'distances' in query_results and query_results['distances'] else []
        # labels = query_results['labels'][0] if 'labels' in query_results and query_results[
        #     'labels'] else []  # Fetching labels
        sorted_results = sorted(zip(disease_ids, distances), key=lambda x: x[1])  # remember to add label
        return sorted_results

    '''
    The following are util functions (but they are not necessary, having the top10 results printed is everything it needs,
    it would just be to check if it maybe does not find a specific diseasea:
    '''

    @staticmethod
    def process_query_results(query_results) -> list[Any]:
        disease_ids = query_results['ids'][0] if 'ids' in query_results and query_results['ids'] else []
        distances = query_results['distances'][0] if 'distances' in query_results and query_results['distances'] else []
        disease_names = (
            [metadata['disease_name'] for metadata in query_results['metadatas'][0]]
            if 'metadatas' in query_results and query_results['metadatas']
            else []
        )
        sorted_results = sorted(zip(disease_ids, disease_names, distances), key=lambda x: x[2])
        return sorted_results

    def binary_search_max_results_nocol(
        self,
        query_params,
        lower_bound,
        upper_bound
    ):
        max_safe_value = lower_bound

        while lower_bound < upper_bound - 1:
            mid_point = (lower_bound + upper_bound) // 2
            query_params['n_results'] = mid_point

            try:
                # query_results = self.disease_service.disease_avg_embeddings_collection.query(**query_params)
                # TODO: for clustered was self.disease_organ ... disease_organ_collection
                query_results = self.disease_weighted_service.disease_weighted_avg_embeddings_collection.query(
                    **query_params)

                max_safe_value = mid_point
                lower_bound = mid_point
            except RuntimeError as e:
                upper_bound = mid_point

        # Verification step: test values around max_safe_value to ensure it's the highest safe value.
        for test_value in range(max_safe_value - 1, max_safe_value + 2):
            if test_value <= 0:
                continue  # Skip non-positive values
            query_params['n_results'] = test_value
            try:
                # self.disease_service.disease_avg_embeddings_collection.query(**query_params)
                # TODO: same as 20 lines above
                self.disease_weighted_service.disease_weighted_avg_embeddings_collection.query(**query_params)
                max_safe_value = test_value  # Update max_safe_value if this higher value is also safe
            except RuntimeError as e:
                break

        return max_safe_value

    @deprecated  # look coment in deprecated -> binary_search_max_results
    def max_results(
        self,
        query_params,
        n_results,
        col: Collection,
        estimated_total_query_results
    ):
        if n_results is None:
            estimated_length = len(estimated_total_query_results["embeddings"])
            print(f"Estimated length (n_results) == {estimated_length}")
            max_n_results = self.binary_search_max_results(query_params, 11700, estimated_length, col=col)
            query_params["n_results"] = max_n_results
            print(f"Using max safe n_results: {max_n_results}")
        else:
            query_params["n_results"] = n_results

    @deprecated  # the other one is with nocol as parameter, which seems better but forgot why
    def binary_search_max_results(
        self,
        query_params,
        lower_bound,
        upper_bound,
        col: Collection
    ):
        max_safe_value = lower_bound

        while lower_bound < upper_bound - 1:
            mid_point = (lower_bound + upper_bound) // 2
            query_params['n_results'] = mid_point

            try:
                # query_results = self.disease_service.disease_avg_embeddings_collection.query(**query_params)
                query_results = col.query(**query_params)
                max_safe_value = mid_point
                lower_bound = mid_point
            except RuntimeError as e:
                upper_bound = mid_point

        # Verification step: test values around max_safe_value to ensure it's the highest safe value.
        for test_value in range(max_safe_value - 1, max_safe_value + 2):
            if test_value <= 0:
                continue  # Skip non-positive values
            query_params['n_results'] = test_value
            try:
                col.query(**query_params)
                # self.disease_service.disease_avg_embeddings_collection.query(**query_params)
                # self.disease_organ_service.clustered_embeddings_collection.query(**query_params)
                max_safe_value = test_value  # Update max_safe_value if this higher value is also safe
            except RuntimeError as e:
                break

        return max_safe_value
