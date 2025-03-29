from typing import List, Dict
import asyncio
from itertools import cycle
from logging import Logger
from openai import AsyncAzureOpenAI
from openai import RateLimitError as OpenAIRateLimitError
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import IndexingResult
from azure.core.credentials import AzureKeyCredential
from sqlalchemy.orm import Session

from doc2rag.db_utils.models import File, Chunk, SplitFile
from doc2rag.db_utils.database import BaseSQLAgent
from doc2rag.logger_utils import LoggingAgent
from doc2rag.config_utils import (
    AzureAISearchConfig,
    EmbeddingConfig,
    TiktokenConfig,
)

TiktokenConfig().set_tiktoken_cache_dir_in_env("cl100k_base")
RATE_LIMIT_RETRY_DELAY = 10  # Initial delay in seconds
BACKOFF_FACTOR = 2  # Exponential backoff multiplier
MAX_RETRIES = 3  # Maximum retry attempts
DOCUMENT_TYPE = "Chunk"


class ChunkGroupUploadTask:
    def __init__(
        self,
        logger: Logger,
        embed_config: EmbeddingConfig,
        ais_config: AzureAISearchConfig,
        db: Session,
        chunks: List[Chunk],
        file_id: int,
        file_name: str,
    ):
        self.logger = logger
        self.embed_config = embed_config
        self.ais_config = ais_config
        self.db = db
        self.chunks = chunks
        self.file_id = file_id
        self.file_name = file_name

    async def _prepare_payload(self) -> dict:
        """
        Prepare the payload for uploading chunks to Azure AI Search with rate limit handling.
        """
        retries = 0

        while retries < MAX_RETRIES:
            try:
                async with AsyncAzureOpenAI(
                    azure_endpoint=self.embed_config.endpoint,
                    azure_deployment=self.embed_config.deployment,
                    api_version=self.embed_config.api_version,
                    api_key=self.embed_config.api_key,
                ) as aoai:
                    response = await aoai.embeddings.create(
                        [chunk.content for chunk in self.chunks]
                    )
                    embeddings = [item.embedding for item in response.data]

                    # Ensure lengths match before proceeding
                    if len(self.chunks) != len(embeddings):
                        self.logger.error(
                            f"Mismatch: {len(self.chunks)} chunks but {len(embeddings)} embeddings"
                        )
                        raise ValueError(
                            "Mismatch between number of chunks and embeddings."
                        )

                return {
                    "value": [
                        {
                            "@search.action": "upload",
                            "id": chunk.ai_search_id,
                            "document_type": DOCUMENT_TYPE,
                            "file_id": self.file_id,
                            "file_name": self.file_name,
                            "content": chunk.content,
                            "content_vector": embedding,
                        }
                        for chunk, embedding in zip(self.chunks, embeddings)
                    ]
                }
            except OpenAIRateLimitError:  # Catch rate limit errors directly
                wait_time = RATE_LIMIT_RETRY_DELAY * (BACKOFF_FACTOR**retries)
                self.logger.warning(
                    f"Embedding Rate limit hit. Retrying in {wait_time:.2f} seconds... (Attempt {retries + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait_time)
                retries += 1
            except Exception as e:
                self.logger.error(f"Error preparing payload: {e}", exc_info=True)
                raise  # Re-raise other exceptions immediately

        raise Exception("Max retries reached for embedding API due to rate limits.")

    async def _upload_documents(self, payload: Dict) -> List[IndexingResult]:
        """
        Upload documents to Azure AI Search with retry handling for RequestEntityTooLargeError.
        """
        retries = 0

        while retries < MAX_RETRIES:
            try:
                async with SearchClient(
                    endpoint=self.ais_config.endpoint,
                    index_name=self.ais_config.index_name,
                    credential=AzureKeyCredential(self.ais_config.api_key),
                ) as search_client:
                    return await search_client.upload_documents(
                        documents=payload["value"]
                    )

            except Exception as e:
                wait_time = RATE_LIMIT_RETRY_DELAY * (BACKOFF_FACTOR**retries)
                self.logger.warning(
                    f"Upload to Azure AI Search failed: {e}. Retrying in {wait_time:.2f} seconds... (Attempt {retries + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait_time)
                retries += 1

        raise Exception("Max retries reached for document upload to Azure AI Search.")

    def _mark_chunks_as_uploaded(self, indexing_results: List[IndexingResult]):
        """
        Mark chunks as uploaded in the database.
        """
        try:
            updated = False
            for chunk, indexing_result in zip(self.chunks, indexing_results):
                if indexing_result.succeeded:
                    chunk.status = "uploaded"
                    self.db.add(chunk)
                    updated = True

            if updated:
                self.db.commit()
        except Exception as e:
            self.logger.error(f"Error marking chunks as uploaded: {e}", exc_info=True)
            raise

    async def run(self):
        """
        Orchestrate the process of embedding, uploading, and updating database records.
        """
        payload = await self._prepare_payload()
        indexing_results = await self._upload_documents(payload)
        self._mark_chunks_as_uploaded(indexing_results)


class FileUploadTask:
    def __init__(
        self,
        index_name: str,
        file_id: int,
        file_name: str,
        chunks: List[Chunk],
        batch_size: int,
        embed_config_pool: List[EmbeddingConfig],
        ais_config: AzureAISearchConfig,
        db: Session,
        logger: Logger,
    ):
        self.index_name = index_name
        self.file_id = file_id
        self.file_name = file_name
        self.chunks = chunks
        self.batch_size = batch_size
        self.embed_config_pool = embed_config_pool
        self.ais_config = ais_config
        self.db = db
        self.chunk_groups = self._split_chunks()
        self.logger = logger

    def _split_chunks(self) -> List[ChunkGroupUploadTask]:
        """
        Splits chunks into multiple ChunkGroupUploadTask instances ensuring each group
        has no more than batch_size chunks and cycles through embed_config_pool.
        """
        chunk_groups = []
        embed_config_iterator = cycle(self.embed_config_pool)  # Round-robin iterator

        for i in range(0, len(self.chunks), self.batch_size):
            group_chunks = self.chunks[
                i : i + self.batch_size
            ]  # Slice batch_size chunks
            embed_config = next(embed_config_iterator)  # Get the next embed config

            chunk_groups.append(
                ChunkGroupUploadTask(
                    logger=self.logger,
                    embed_config=embed_config,
                    ais_config=self.ais_config,
                    db=self.db,
                    chunks=group_chunks,
                    file_id=self.file_id,
                    file_name=self.file_name,
                )
            )

        return chunk_groups

    def _mark_file_as_uploaded(self):
        """
        Mark the file as uploaded in the database.
        """
        file = self.db.query(File).filter(File.id == self.file_id).first()
        if not file:
            self.logger.error(f"File with ID {self.file_id} not found.")
            return

        # Fetch all chunk statuses for this file's chunks
        chunk_statuses = (
            self.db.query(Chunk.status)
            .join(SplitFile, Chunk.split_file_id == SplitFile.id)
            .filter(SplitFile.file_id == self.file_id)
            .all()
        )

        # Extract statuses and check if all chunks are uploaded
        if chunk_statuses and all(status[0] == "uploaded" for status in chunk_statuses):
            file.status = "uploaded"
            self.db.commit()
            self.logger.info(f"File {file.name} marked as uploaded.")
        else:
            self.logger.warning(
                f"File {file.name} has chunks not marked as uploaded. Please check the database."
            )

    async def _upload_chunk_groups(self):
        """
        Upload multiple ChunkGroupUploadTask instances concurrently with rate-limit handling.
        """
        semaphore = asyncio.Semaphore(5)  # Limit concurrent uploads

        async def upload_task(chunk_group: ChunkGroupUploadTask):
            nonlocal semaphore
            try:
                async with semaphore:
                    await chunk_group.run()
            except Exception as e:
                self.logger.error(f"A chunk group upload failed: {e} for File(id={self.file_id}, name={self.file_name})", exc_info=True)

        tasks = [upload_task(cg) for cg in self.chunk_groups]
        await asyncio.gather(*tasks)

        self._mark_file_as_uploaded()

    async def run(self):
        """
        Run all ChunkGroupUploadTask instances concurrently.
        """
        self.logger.info(
            f"Uploading {len(self.chunks)} chunks for file {self.file_name}..."
        )
        await self._upload_chunk_groups()
        self.logger.info(f"Upload complete for file {self.file_name}.")


class UploadToAISearchMainAgent:
    def __init__(
        self,
        sql_agent: BaseSQLAgent,
        embed_config_pool: List[EmbeddingConfig],
        ais_config: AzureAISearchConfig,
        logger: Logger,
    ):
        self.sql_agent = sql_agent
        self.embed_config_pool = embed_config_pool
        self.ais_config = ais_config
        self.logger = logger

    def _fetch_chunks_to_upload(
        self, session: Session
    ) -> tuple[list[Chunk], list[int], list[str], list[str]]:
        """
        Retrieve only the fields necessary for upload.
        """
        results = (
            session.query(
                Chunk,
                File.id.label("file_id"),
                File.name.label("file_name"),
                File.index_name.label("index_name"),
            )
            .join(SplitFile, Chunk.split_file_id == SplitFile.id)
            .join(File, SplitFile.file_id == File.id)
            .filter(Chunk.status == "wait-for-upload")
            .order_by(SplitFile.id)
            .all()
        )
        chunks, file_ids, file_names, index_names = (
            zip(*results) if results else ([], [], [], [])
        )
        return chunks, file_ids, file_names, index_names

    def _get_file_map(
        self,
        chunks: list[Chunk],
        file_ids: list[int],
        file_names: list[str],
        index_names: list[str],
    ) -> dict:
        """
        Organize chunks into a dictionary keyed by file_id.
        """
        file_map = {}
        for chunk, file_id, file_name, index_name in zip(
            chunks, file_ids, file_names, index_names
        ):
            if file_id not in file_map:
                file_map[file_id] = {
                    "index_name": index_name,
                    "file_name": file_name,
                    "chunks": [],
                }
            file_map[file_id]["chunks"].append(chunk)
        return file_map

    def _get_file_upload_tasks(
        self, session: Session, file_map: dict
    ) -> list[FileUploadTask]:
        """
        Create FileUploadTask instances from the file map.
        """
        return [
            FileUploadTask(
                index_name=file_data["index_name"],
                file_id=file_id,
                file_name=file_data["file_name"],
                chunks=file_data["chunks"],
                batch_size=10,
                embed_config_pool=self.embed_config_pool,
                ais_config=self.ais_config,
                db=session,
                logger=self.logger,
            )
            for file_id, file_data in file_map.items()
        ]

    async def run(self):
        """
        Main method to fetch chunks and execute file uploads.
        """
        with self.sql_agent.SessionLocal() as session:
            chunks, file_ids, file_names, index_names = self._fetch_chunks_to_upload(
                session
            )
            file_map = self._get_file_map(chunks, file_ids, file_names, index_names)
            file_upload_tasks = self._get_file_upload_tasks(session, file_map)

        tasks = [
            asyncio.create_task(file_task.run()) for file_task in file_upload_tasks
        ]
        await asyncio.gather(*tasks)


async def main(
    sql_agent: BaseSQLAgent,
    embed_config_pool: List[EmbeddingConfig],
    ais_config: AzureAISearchConfig,
):
    logger = LoggingAgent("AzureAISearch").logger
    agent = UploadToAISearchMainAgent(sql_agent, embed_config_pool, ais_config, logger)
    await agent.run()


if __name__ == "__main__":
    sql_agent = BaseSQLAgent()
    embed_config_pool = EmbeddingConfig().get_embed_configs()
    asyncio.run(main())
