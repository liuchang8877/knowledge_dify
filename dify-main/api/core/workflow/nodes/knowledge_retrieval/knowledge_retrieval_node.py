import logging
from collections.abc import Mapping, Sequence
from typing import Any, cast, Optional, Tuple, List
# 设置日志级别为 DEBUG
logging.basicConfig(level=logging.DEBUG)

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from core.app.app_config.entities import DatasetRetrieveConfigEntity
from core.app.entities.app_invoke_entities import ModelConfigWithCredentialsEntity
from core.entities.agent_entities import PlanningStrategy
from core.entities.model_entities import ModelStatus
from core.model_manager import ModelInstance, ModelManager
from core.model_runtime.entities.model_entities import ModelFeature, ModelType
from core.model_runtime.model_providers.__base.large_language_model import LargeLanguageModel
from core.rag.datasource.retrieval_service import RetrievalService
from core.rag.retrieval.dataset_retrieval import DatasetRetrieval
from core.rag.retrieval.retrieval_methods import RetrievalMethod
from core.variables import StringSegment
from core.workflow.entities.node_entities import NodeRunResult
from core.workflow.nodes.base import BaseNode
from core.workflow.nodes.enums import NodeType
from extensions.ext_database import db
from models.dataset import Dataset, Document
from models.workflow import WorkflowNodeExecutionStatus

from .entities import KnowledgeRetrievalNodeData
from .exc import (
    KnowledgeRetrievalNodeError,
    ModelCredentialsNotInitializedError,
    ModelNotExistError,
    ModelNotSupportedError,
    ModelQuotaExceededError,
)

logger = logging.getLogger(__name__)

default_retrieval_model = {
    "search_method": RetrievalMethod.SEMANTIC_SEARCH.value,
    "reranking_enable": False,
    "reranking_model": {"reranking_provider_name": "", "reranking_model_name": ""},
    "top_k": 2,
    "score_threshold_enabled": False,
}


class KnowledgeRetrievalNode(BaseNode[KnowledgeRetrievalNodeData]):
    _node_data_cls = KnowledgeRetrievalNodeData
    _node_type = NodeType.KNOWLEDGE_RETRIEVAL

    def _run(self) -> NodeRunResult:
        """Execute the knowledge retrieval node."""
        logger.info(f"Starting KnowledgeRetrievalNode with variable pool: {self.graph_runtime_state.variable_pool}")

        # Extract and validate query
        query_variable = self.graph_runtime_state.variable_pool.get(self.node_data.query_variable_selector)
        if not isinstance(query_variable, StringSegment):
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                inputs={},
                error="Query variable must be a string"
            )
        query = query_variable.value
        if not query:
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                inputs={"query": query},
                error="Query is required"
            )

        # Extract knowledge_id with detailed logging
        variables = {"query": query}
        knowledge_id = self._extract_knowledge_id()
        if knowledge_id:
            if not isinstance(knowledge_id, str):
                return NodeRunResult(
                    status=WorkflowNodeExecutionStatus.FAILED,
                    inputs=variables,
                    error="knowledge_id must be a string"
                )
            variables["knowledge_id"] = knowledge_id
        else:
            logger.warning("No knowledge_id provided, falling back to node_data.dataset_ids: %s", self.node_data.dataset_ids)

        logger.info(f"Using knowledge_id: {knowledge_id}")

        # Retrieve knowledge
        try:
            results = self._fetch_dataset_retriever(node_data=self.node_data, query=query, knowledge_id=knowledge_id)
            logger.info(f"Retrieved {len(results)} results for query: {query}")
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.SUCCEEDED,
                inputs=variables,
                outputs={"result": results}
            )
        except KnowledgeRetrievalNodeError as e:
            logger.error(f"Knowledge retrieval failed: {str(e)}")
            return NodeRunResult(status=WorkflowNodeExecutionStatus.FAILED, inputs=variables, error=str(e))
        except SQLAlchemyError as se:
            logger.error(f"Database error during retrieval: {str(se)}")
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                inputs=variables,
                error="Database error occurred"
            )
        except Exception as e:
            logger.error(f"Unexpected error in knowledge retrieval: {str(e)}", exc_info=True)
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                inputs=variables,
                error="Unexpected error occurred"
            )

    def _extract_knowledge_id(self) -> Optional[str]:
        """Extract knowledge_id from user_inputs or start node with detailed logging."""
        # Log the entire variable pool for debugging
        logger.debug(f"Variable pool content: {self.graph_runtime_state.variable_pool}")

        # Try user_inputs first
        try:
            user_inputs = self.graph_runtime_state.variable_pool.user_inputs
            logger.debug(f"user_inputs content: {user_inputs}")
            knowledge_id = user_inputs.get("knowledge_id")
            if knowledge_id:
                logger.info(f"Extracted knowledge_id from user_inputs: {knowledge_id}")
                return knowledge_id
            else:
                logger.warning("knowledge_id not found in user_inputs: %s", user_inputs)
        except AttributeError:
            logger.warning("variable_pool missing user_inputs attribute, attempting fallback")

        # Fallback to start node
        start_node_id = self._get_start_node_id()
        if start_node_id:
            logger.debug(f"Using start_node_id: {start_node_id}")
            start_node_vars = self.graph_runtime_state.variable_pool.get([start_node_id])
            logger.debug(f"Start node variables: {start_node_vars}")
            knowledge_id_var = self.graph_runtime_state.variable_pool.get([start_node_id, "knowledge_id"])
            logger.debug(f"Start node knowledge_id variable: {knowledge_id_var}")
            if isinstance(knowledge_id_var, StringSegment):
                knowledge_id = knowledge_id_var.value
                logger.info(f"Extracted knowledge_id from start node {start_node_id}: {knowledge_id}")
                return knowledge_id
            else:
                logger.warning(f"No valid knowledge_id found in start node {start_node_id}: {knowledge_id_var}")
        else:
            logger.warning("No start node found in variable pool")

        return None

    def _get_start_node_id(self) -> Optional[str]:
        """Get the start node ID from the graph runtime state."""
        # Adjust this logic based on how Dify identifies the start node
        variable_dict = self.graph_runtime_state.variable_pool.variable_dictionary
        logger.debug(f"Variable dictionary: {variable_dict}")
        for node_id in variable_dict.keys():
            if node_id != "sys":
                logger.debug(f"Identified potential start node ID: {node_id}")
                return node_id
        logger.warning("No non-sys node found in variable_dictionary")
        return None

    def _fetch_dataset_retriever(
        self, node_data: KnowledgeRetrievalNodeData, query: str, knowledge_id: Optional[str] = None
    ) -> List[dict[str, Any]]:
        """Fetch and retrieve documents from datasets."""
        dataset_ids = [knowledge_id] if knowledge_id else node_data.dataset_ids
        logger.info(f"Using dataset_ids: {dataset_ids}")

        # Fetch available datasets
        available_datasets = self._query_available_datasets(dataset_ids)
        if not available_datasets:
            logger.warning(f"No available datasets found for IDs: {dataset_ids}")
            return []

        # Perform retrieval based on mode
        dataset_retrieval = DatasetRetrieval()
        all_documents = []
        if node_data.retrieval_mode == DatasetRetrieveConfigEntity.RetrieveStrategy.SINGLE.value:
            model_instance, model_config = self._fetch_model_config(node_data)
            all_documents = self._single_retrieval(
                dataset_retrieval, available_datasets, query, model_instance, model_config
            )
        elif node_data.retrieval_mode == DatasetRetrieveConfigEntity.RetrieveStrategy.MULTIPLE.value:
            all_documents = self._multiple_retrieval(dataset_retrieval, available_datasets, query, node_data)

        # Format retrieval results
        return self._format_retrieval_results(all_documents)

    def _query_available_datasets(self, dataset_ids: List[str]) -> List[Dataset]:
        """Query available datasets with at least one valid document."""
        subquery = (
            db.session.query(Document.dataset_id, func.count(Document.id).label("available_document_count"))
            .filter(
                Document.indexing_status == "completed",
                Document.enabled == True,
                Document.archived == False,
                Document.dataset_id.in_(dataset_ids),
            )
            .group_by(Document.dataset_id)
            .having(func.count(Document.id) > 0)
            .subquery()
        )

        results = (
            db.session.query(Dataset)
            .outerjoin(subquery, Dataset.id == subquery.c.dataset_id)
            .filter(Dataset.tenant_id == self.tenant_id, Dataset.id.in_(dataset_ids))
            .filter((subquery.c.available_document_count > 0) | (Dataset.provider == "external"))
            .all()
        )
        return [dataset for dataset in results if dataset]

    def _single_retrieval(
        self,
        dataset_retrieval: DatasetRetrieval,
        available_datasets: List[Dataset],
        query: str,
        model_instance: ModelInstance,
        model_config: ModelConfigWithCredentialsEntity,
    ) -> List[Any]:
        """Perform single retrieval strategy."""
        model_type_instance = cast(LargeLanguageModel, model_instance.model_type_instance)
        model_schema = model_type_instance.get_model_schema(model_config.model, model_config.credentials)

        if not model_schema:
            raise KnowledgeRetrievalNodeError(f"Model schema not found for {model_config.model}")

        planning_strategy = PlanningStrategy.REACT_ROUTER
        if model_schema.features and (
            ModelFeature.TOOL_CALL in model_schema.features or ModelFeature.MULTI_TOOL_CALL in model_schema.features
        ):
            planning_strategy = PlanningStrategy.ROUTER

        return dataset_retrieval.single_retrieve(
            available_datasets=available_datasets,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            app_id=self.app_id,
            user_from=self.user_from.value,
            query=query,
            model_config=model_config,
            model_instance=model_instance,
            planning_strategy=planning_strategy,
        )

    def _multiple_retrieval(
        self,
        dataset_retrieval: DatasetRetrieval,
        available_datasets: List[Dataset],
        query: str,
        node_data: KnowledgeRetrievalNodeData,
    ) -> List[Any]:
        """Perform multiple retrieval strategy."""
        if node_data.multiple_retrieval_config is None:
            raise KnowledgeRetrievalNodeError("multiple_retrieval_config is required")

        config = node_data.multiple_retrieval_config
        reranking_model = (
            {
                "reranking_provider_name": config.reranking_model.provider,
                "reranking_model_name": config.reranking_model.model,
            }
            if config.reranking_mode == "reranking_model" and config.reranking_model
            else None
        )
        weights = (
            {
                "vector_setting": {
                    "vector_weight": config.weights.vector_setting.vector_weight,
                    "embedding_provider_name": config.weights.vector_setting.embedding_provider_name,
                    "embedding_model_name": config.weights.vector_setting.embedding_model_name,
                },
                "keyword_setting": {"keyword_weight": config.weights.keyword_setting.keyword_weight},
            }
            if config.reranking_mode == "weighted_score" and config.weights
            else None
        )

        return dataset_retrieval.multiple_retrieve(
            app_id=self.app_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_from=self.user_from.value,
            available_datasets=available_datasets,
            query=query,
            top_k=config.top_k,
            score_threshold=config.score_threshold if config.score_threshold is not None else 0.0,
            reranking_mode=config.reranking_mode,
            reranking_model=reranking_model,
            weights=weights,
            reranking_enable=config.reranking_enable,
        )

    def _format_retrieval_results(self, all_documents: List[Any]) -> List[dict[str, Any]]:
        """Format retrieved documents into a standardized structure."""
        dify_docs = [doc for doc in all_documents if doc.provider == "dify"]
        external_docs = [doc for doc in all_documents if doc.provider == "external"]
        retrieval_resource_list = []

        # Process external documents
        for item in external_docs:
            retrieval_resource_list.append({
                "metadata": {
                    "_source": "knowledge",
                    "dataset_id": item.metadata.get("dataset_id"),
                    "dataset_name": item.metadata.get("dataset_name"),
                    "document_name": item.metadata.get("title"),
                    "data_source_type": "external",
                    "retriever_from": "workflow",
                    "score": item.metadata.get("score"),
                },
                "title": item.metadata.get("title"),
                "content": item.page_content,
            })

        # Process dify documents
        if dify_docs:
            records = RetrievalService.format_retrieval_documents(dify_docs)
            for record in records:
                segment = record.segment
                dataset = Dataset.query.filter_by(id=segment.dataset_id).first()
                document = Document.query.filter(
                    Document.id == segment.document_id,
                    Document.enabled == True,
                    Document.archived == False,
                ).first()
                if dataset and document:
                    source = {
                        "metadata": {
                            "_source": "knowledge",
                            "dataset_id": dataset.id,
                            "dataset_name": dataset.name,
                            "document_id": document.id,
                            "document_name": document.name,
                            "document_data_source_type": document.data_source_type,
                            "segment_id": segment.id,
                            "retriever_from": "workflow",
                            "score": record.score or 0.0,
                            "segment_hit_count": segment.hit_count,
                            "segment_word_count": segment.word_count,
                            "segment_position": segment.position,
                            "segment_index_node_hash": segment.index_node_hash,
                        },
                        "title": document.name,
                        "content": (
                            f"question:{segment.get_sign_content()} \nanswer:{segment.answer}"
                            if segment.answer
                            else segment.get_sign_content()
                        ),
                    }
                    retrieval_resource_list.append(source)

        # Sort and assign positions
        if retrieval_resource_list:
            retrieval_resource_list.sort(
                key=lambda x: x["metadata"]["score"] if x["metadata"].get("score") is not None else 0.0,
                reverse=True,
            )
            for position, item in enumerate(retrieval_resource_list, start=1):
                item["metadata"]["position"] = position

        return retrieval_resource_list

    @classmethod
    def _extract_variable_selector_to_variable_mapping(
        cls,
        *,
        graph_config: Mapping[str, Any],
        node_id: str,
        node_data: KnowledgeRetrievalNodeData,
    ) -> Mapping[str, Sequence[str]]:
        """Extract variable selector to variable mapping."""
        variable_mapping = {
            f"{node_id}.query": node_data.query_variable_selector,
        }
        # Explicitly map knowledge_id from Start node
        start_node_id = next((n_id for n_id in graph_config.keys() if n_id != "sys"), None)
        if start_node_id:
            variable_mapping[f"{node_id}.knowledge_id"] = [start_node_id, "knowledge_id"]
            logger.debug(f"Mapped knowledge_id to Start node {start_node_id}: {variable_mapping}")
        else:
            variable_mapping[f"{node_id}.knowledge_id"] = ["start", "knowledge_id"]  # Default fallback
            logger.warning("No start node found in graph_config, using default 'start' ID")
        return variable_mapping

    def _fetch_model_config(
        self, node_data: KnowledgeRetrievalNodeData
    ) -> Tuple[ModelInstance, ModelConfigWithCredentialsEntity]:
        """Fetch model configuration for single retrieval."""
        if node_data.single_retrieval_config is None:
            raise ValueError("single_retrieval_config is required")

        model_config = node_data.single_retrieval_config.model
        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(
            tenant_id=self.tenant_id,
            model_type=ModelType.LLM,
            provider=model_config.provider,
            model=model_config.name,
        )

        provider_model_bundle = model_instance.provider_model_bundle
        model_type_instance = cast(LargeLanguageModel, model_instance.model_type_instance)
        model_credentials = model_instance.credentials

        provider_model = provider_model_bundle.configuration.get_provider_model(
            model=model_config.name, model_type=ModelType.LLM
        )
        if not provider_model:
            raise ModelNotExistError(f"Model {model_config.name} not exist.")

        if provider_model.status == ModelStatus.NO_CONFIGURE:
            raise ModelCredentialsNotInitializedError(f"Model {model_config.name} credentials not initialized.")
        elif provider_model.status == ModelStatus.NO_PERMISSION:
            raise ModelNotSupportedError(f"Dify Hosted OpenAI {model_config.name} currently not supported.")
        elif provider_model.status == ModelStatus.QUOTA_EXCEEDED:
            raise ModelQuotaExceededError(f"Model provider {model_config.provider} quota exceeded.")

        completion_params = model_config.completion_params
        stop = completion_params.pop("stop", [])

        if not model_config.mode:
            raise ModelNotExistError("LLM mode is required.")

        model_schema = model_type_instance.get_model_schema(model_config.name, model_credentials)
        if not model_schema:
            raise ModelNotExistError(f"Model {model_config.name} not exist.")

        return model_instance, ModelConfigWithCredentialsEntity(
            provider=model_config.provider,
            model=model_config.name,
            model_schema=model_schema,
            mode=model_config.mode,
            provider_model_bundle=provider_model_bundle,
            credentials=model_credentials,
            parameters=completion_params,
            stop=stop,
        )