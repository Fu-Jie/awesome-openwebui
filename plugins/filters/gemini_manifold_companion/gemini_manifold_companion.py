"""
title: Gemini Manifold Companion
id: gemini_manifold_companion
description: A companion filter for "Gemini Manifold google_genai" pipe providing enhanced functionality.
author: suurt8ll
author_url: https://github.com/suurt8ll
funding_url: https://github.com/suurt8ll/open_webui_functions
license: MIT
version: 1.7.0
"""

VERSION = "1.7.0"

# This filter can detect that a feature like web search or code execution is enabled in the front-end,
# set the feature back to False so Open WebUI does not run it's own logic and then
# pass custom values to "Gemini Manifold google_genai" that signal which feature was enabled and intercepted.

import copy
import json
from google.genai import types

import sys
import time
import asyncio
import aiohttp
from fastapi import Request
from fastapi.datastructures import State
from loguru import logger
from pydantic import BaseModel, Field
import pydantic_core
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TYPE_CHECKING, cast

from open_webui.models.functions import Functions

if TYPE_CHECKING:
    from loguru import Record
    from loguru._handler import Handler  # type: ignore
    from open_webui.utils.manifold_types import *  # My personal types in a separate file for more robustness.

# According to https://ai.google.dev/gemini-api/docs/models
ALLOWED_GROUNDING_MODELS = {
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite-preview-09-2025",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.0-pro-exp",
    "gemini-2.0-pro-exp-02-05",
    "gemini-exp-1206",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-001",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
}
ALLOWED_CODE_EXECUTION_MODELS = {
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite-preview-09-2025",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.0-pro-exp",
    "gemini-2.0-pro-exp-02-05",
    "gemini-exp-1206",
    "gemini-2.0-flash-thinking-exp-01-21",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-001",
}

# Default timeout for URL resolution
# TODO: Move to Pipe.Valves.
DEFAULT_URL_TIMEOUT = aiohttp.ClientTimeout(total=10)  # 10 seconds total timeout

# Setting auditable=False avoids duplicate output for log levels that would be printed out by the main log.
log = logger.bind(auditable=False)


class Filter:

    class Valves(BaseModel):
        FORCE_NON_STREAM_FOR_IMAGE_MODELS: bool = Field(
            default=True,
            description="""Automatically disable streaming for image generation models
            (e.g., gemini-2.5-flash-image-preview) to prevent 'Chunk too big' errors.
            Set to False to attempt streaming with these models.""",
        )
        SET_TEMP_TO_ZERO: bool = Field(
            default=False,
            description="""Decide if you want to set the temperature to 0 for grounded answers,
            Google reccomends it in their docs.""",
        )
        GROUNDING_DYNAMIC_RETRIEVAL_THRESHOLD: float | None = Field(
            default=None,
            description="""See https://ai.google.dev/gemini-api/docs/grounding?lang=python#dynamic-threshold for more information.
            Only supported for 1.0 and 1.5 models""",
        )
        USE_PERMISSIVE_SAFETY: bool = Field(
            default=False,
            description="""Whether to request relaxed safety filtering.
            Default value is False.""",
        )
        BYPASS_BACKEND_RAG: bool = Field(
            default=True,
            description="""Decide if you want ot bypass Open WebUI's RAG and send your documents directly to Google API.
            Default value is True.""",
        )
        LOG_LEVEL: Literal[
            "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
        ] = Field(
            default="INFO",
            description="Select logging level. Use `docker logs -f open-webui` to view logs.",
        )

    # TODO: Support user settting through UserValves.

    def __init__(self):
        # This hack makes the valves values available to the `__init__` method.
        # TODO: Get the id from the frontmatter instead of hardcoding it.
        valves = Functions.get_function_valves_by_id("gemini_manifold_companion")
        self.valves = self.Valves(**(valves if valves else {}))
        self.log_level = self.valves.LOG_LEVEL
        self._add_log_handler()
        log.success("Function has been initialized.")
        log.trace("Full self object:", payload=self.__dict__)

    def inlet(self, body: "Body", __metadata__: dict[str, Any]) -> "Body":
        """Modifies the incoming request payload before it's sent to the LLM. Operates on the `form_data` dictionary."""

        # Detect log level change inside self.valves
        if self.log_level != self.valves.LOG_LEVEL:
            log.info(
                f"Detected log level change: {self.log_level=} and {self.valves.LOG_LEVEL=}. "
                "Running the logging setup again."
            )
            self._add_log_handler()

        log.debug(
            f"inlet method has been called. Gemini Manifold Companion version is {VERSION}"
        )

        canonical_model_name, is_manifold = self._get_model_name(body)
        # Exit early if we are filtering an unsupported model.
        if not is_manifold:
            log.debug(
                "Returning the original body object because conditions for proceeding are not fulfilled."
            )
            return body

        # Check if it's a relevant model (supports either feature)
        is_grounding_model = canonical_model_name in ALLOWED_GROUNDING_MODELS
        is_code_exec_model = canonical_model_name in ALLOWED_CODE_EXECUTION_MODELS
        log.debug(f"{is_grounding_model=}, {is_code_exec_model=}")

        features = body.get("features", {})
        log.debug(f"body.features:", payload=features)

        # Ensure features field exists
        metadata = body.get("metadata")
        metadata_features = metadata.get("features")
        if metadata_features is None:
            metadata_features = cast(Features, {})
            metadata["features"] = metadata_features

        # Add the companion version to the payload for the pipe to consume.
        metadata_features["gemini_manifold_companion_version"] = VERSION

        if is_grounding_model:
            web_search_enabled = (
                features.get("web_search", False)
                if isinstance(features, dict)
                else False
            )
            if web_search_enabled:
                log.info(
                    "Search feature is enabled, disabling it and adding custom feature called grounding_w_google_search."
                )
                # Disable web_search
                features["web_search"] = False
                # Use "Google Search Retrieval" for 1.0 and 1.5 models and "Google Search as a Tool for >=2.0 models".
                if "1.0" in canonical_model_name or "1.5" in canonical_model_name:
                    metadata_features["google_search_retrieval"] = True
                    metadata_features["google_search_retrieval_threshold"] = (
                        self.valves.GROUNDING_DYNAMIC_RETRIEVAL_THRESHOLD
                    )
                else:
                    metadata_features["google_search_tool"] = True
                # Google suggest setting temperature to 0 if using grounding:
                # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/ground-with-google-search#:~:text=For%20ideal%20results%2C%20use%20a%20temperature%20of%200.0.
                if self.valves.SET_TEMP_TO_ZERO:
                    log.info("Setting temperature to 0.")
                    body["temperature"] = 0  # type: ignore
        if is_code_exec_model:
            code_execution_enabled = (
                features.get("code_interpreter", False)
                if isinstance(features, dict)
                else False
            )
            if code_execution_enabled:
                log.info(
                    "Code interpreter feature is enabled, disabling it and adding custom feature called google_code_execution."
                )
                # Disable code_interpreter
                features["code_interpreter"] = False
                metadata_features["google_code_execution"] = True
        if self.valves.USE_PERMISSIVE_SAFETY:
            log.info("Adding permissive safety settings to body.metadata")
            metadata["safety_settings"] = self._get_permissive_safety_settings(
                canonical_model_name
            )
        if self.valves.BYPASS_BACKEND_RAG:
            if __metadata__["chat_id"] == "local":
                # TODO toast notification
                log.warning(
                    "Bypassing Open WebUI's RAG is not possible for temporary chats. "
                    "The Manifold pipe requires a database entry to access uploaded files, "
                    "which temporary chats do not have. Falling back to Open WebUI's RAG."
                )
                metadata_features["upload_documents"] = False
            else:
                log.info(
                    "BYPASS_BACKEND_RAG is enabled, bypassing Open WebUI RAG to let the Manifold pipe handle documents."
                )
                if files := body.get("files"):
                    log.info(
                        f"Removing {len(files)} files from the Open WebUI RAG pipeline."
                    )
                    body["files"] = []
                metadata_features["upload_documents"] = True
        else:
            log.info(
                "BYPASS_BACKEND_RAG is disabled. Open WebUI's RAG will be used if applicable."
            )
            metadata_features["upload_documents"] = False

        # The manifold pipe requires the backend to be in streaming mode to correctly
        # process the AsyncGenerator it returns. We save the user's original
        # streaming intent and then force the backend into streaming mode.

        user_stream_intent = body.get("stream", True)
        image_generation_models = {
            "gemini-2.0-flash-preview-image-generation",
            "gemini-2.5-flash-image-preview",
            "gemini-2.5-flash-image",
        }

        # Check if the current model is an image generation model and if the
        # user has enabled the non-streaming override for them.
        if (
            self.valves.FORCE_NON_STREAM_FOR_IMAGE_MODELS
            and canonical_model_name in image_generation_models
        ):
            log.info(
                f"Image generation model '{canonical_model_name}' detected. "
                "Forcing non-streaming mode to prevent potential 'Chunk too big' errors."
            )
            # Override the user's intent to ensure stability.
            user_stream_intent = False

        log.info(
            f"Storing user's stream intent ({user_stream_intent}) into __metadata__. "
            "Backend will be forced down the streaming path."
        )
        metadata_features["stream"] = user_stream_intent
        body["stream"] = True

        # TODO: Filter out the citation markers here.

        log.debug("inlet method has finished.")
        return body

    def stream(self, event: dict) -> dict:
        """Modifies the streaming response from the LLM in real-time. Operates on individual chunks of data."""
        return event

    async def outlet(
        self,
        body: "Body",
        __request__: Request,
        __metadata__: dict[str, Any],
        __event_emitter__: Callable[["Event"], Awaitable[None]],
    ) -> "Body":
        """Modifies the complete response payload after it's received from the LLM. Operates on the final `body` dictionary."""

        log.debug("outlet method has been called.")

        chat_id: str = __metadata__.get("chat_id", "")
        message_id: str = __metadata__.get("message_id", "")
        grounding_key = f"grounding_{chat_id}_{message_id}"
        time_key = f"pipe_start_time_{chat_id}_{message_id}"

        app_state: State = __request__.app.state
        log.debug(f"Checking for attributes for message {message_id} in request state.")
        stored_metadata: types.GroundingMetadata | None = getattr(
            app_state, grounding_key, None
        )
        pipe_start_time: float | None = getattr(app_state, time_key, None)

        if stored_metadata:
            log.info("Found grounding metadata, processing citations.")
            log.trace("Stored grounding metadata:", payload=stored_metadata)

            current_content = body["messages"][-1]["content"]
            if isinstance(current_content, list):
                text_to_use = ""
                for item in current_content:
                    if item.get("type") == "text":
                        item = cast("TextContent", item)
                        text_to_use = item["text"]
                        break
            else:
                text_to_use = current_content

            # Insert citation markers into the response text
            cited_text = self._get_text_w_citation_markers(
                stored_metadata,
                text_to_use,
            )

            if cited_text:
                content = body["messages"][-1]["content"]
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            item = cast("TextContent", item)
                            item["text"] = cited_text
                            break
                else:
                    body["messages"][-1]["content"] = cited_text

            # Emit sources to the front-end.
            gs_supports = stored_metadata.grounding_supports
            gs_chunks = stored_metadata.grounding_chunks
            if gs_supports and gs_chunks:
                await self._resolve_and_emit_sources(
                    grounding_chunks=gs_chunks,
                    supports=gs_supports,
                    event_emitter=__event_emitter__,
                    pipe_start_time=pipe_start_time,
                )
            else:
                log.info(
                    "Grounding metadata missing supports or chunks (checked in outlet); "
                    "skipping source resolution and emission."
                )

            # Emit status event with search queries
            await self._emit_status_event_w_queries(stored_metadata, __event_emitter__)

            # Clean up state
            delattr(app_state, grounding_key)
            if hasattr(app_state, time_key):
                delattr(app_state, time_key)
        else:
            log.info("No grounding metadata found in request state.")

        log.debug("outlet method has finished.")
        return body

    # region 1. Helper methods inside the Filter class

    # region 1.1 Add citations

    def _get_text_w_citation_markers(
        self,
        grounding_metadata: types.GroundingMetadata,
        raw_str: str,
    ) -> str | None:
        """
        Returns the model response with citation markers.
        Thoughts, if present as THOUGHT_START_TAG...THOUGHT_END_TAG at the beginning of raw_str,
        are preserved but excluded from the citation indexing process.
        Everything up to the *last* THOUGHT_END_TAG tag is considered part of the thought.
        """

        supports = grounding_metadata.grounding_supports
        grounding_chunks = grounding_metadata.grounding_chunks
        if not supports or not grounding_chunks:
            log.info(
                "Grounding metadata missing supports or chunks, can't insert citation markers. "
                "Response was probably just not grounded."
            )
            return None

        log.trace("raw_str:", payload=raw_str, _log_truncation_enabled=False)

        thought_prefix = ""
        content_for_citation_processing = raw_str

        THOUGHT_START_TAG = "<details"
        THOUGHT_END_TAG = "</details>\n"

        if raw_str.startswith(THOUGHT_START_TAG):
            last_end_thought_tag_idx = raw_str.rfind(THOUGHT_END_TAG)
            if (
                last_end_thought_tag_idx != -1
                and last_end_thought_tag_idx >= len(THOUGHT_START_TAG) - 1
            ):
                thought_block_end_offset = last_end_thought_tag_idx + len(
                    THOUGHT_END_TAG
                )
                thought_prefix = raw_str[:thought_block_end_offset]
                content_for_citation_processing = raw_str[thought_block_end_offset:]
                log.info(
                    "Model thoughts detected at the beginning of the response. "
                    "Citations will be processed on the content following the last thought block."
                )
            else:
                log.warning(
                    "Detected THOUGHT_START_TAG at the start of raw_str without a subsequent closing THOUGHT_END_TAG "
                    "or a malformed thought block. The entire raw_str will be processed for citations. "
                    "This might lead to incorrect marker placement if thoughts were intended and indices "
                    "are relative to content after thoughts."
                )

        processed_content_part_with_markers = content_for_citation_processing

        if content_for_citation_processing:
            try:
                modified_content_bytes = bytearray(
                    content_for_citation_processing.encode("utf-8")
                )
                for support in reversed(supports):
                    segment = support.segment
                    indices = support.grounding_chunk_indices
                    if not (
                        indices is not None
                        and segment
                        and segment.end_index is not None
                    ):
                        log.debug(f"Skipping support due to missing data: {support}")
                        continue
                    end_pos = segment.end_index
                    if not (0 <= end_pos <= len(modified_content_bytes)):
                        log.warning(
                            f"Support segment end_index ({end_pos}) is out of bounds for the processable content "
                            f"(length {len(modified_content_bytes)} bytes after potential thought stripping). "
                            f"Content (first 50 chars): '{content_for_citation_processing[:50]}...'. Skipping this support. Support: {support}"
                        )
                        continue
                    citation_markers = "".join(f"[{index + 1}]" for index in indices)
                    encoded_citation_markers = citation_markers.encode("utf-8")
                    modified_content_bytes[end_pos:end_pos] = encoded_citation_markers
                processed_content_part_with_markers = modified_content_bytes.decode(
                    "utf-8"
                )
            except Exception as e:
                log.error(
                    f"Error injecting citation markers into content: {e}. "
                    f"Using content part (after potential thought stripping) without new markers."
                )
        else:
            if raw_str and not content_for_citation_processing:
                log.info(
                    "Content for citation processing is empty (e.g., raw_str contained only thoughts). "
                    "No citation markers will be injected."
                )
            elif not raw_str:
                log.warning("Raw string is empty, cannot inject citation markers.")

        final_result_str = thought_prefix + processed_content_part_with_markers
        return final_result_str

    async def _resolve_url(
        self,
        session: aiohttp.ClientSession,
        url: str,
        timeout: aiohttp.ClientTimeout = DEFAULT_URL_TIMEOUT,
        max_retries: int = 3,
        base_delay: float = 0.5,
    ) -> tuple[str, bool]:
        """
        Resolves a given URL using the provided aiohttp session, with multiple retries on failure.
        Returns the final URL and a boolean indicating success.
        """
        if not url:
            return "", False
        for attempt in range(max_retries + 1):
            try:
                async with session.get(
                    url,
                    allow_redirects=True,
                    timeout=timeout,
                ) as response:
                    final_url = str(response.url)
                    log.debug(
                        f"Resolved URL '{url}' to '{final_url}' after {attempt} retries"
                    )
                    return final_url, True
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt == max_retries:
                    log.error(
                        f"Failed to resolve URL '{url}' after {max_retries + 1} attempts: {e}"
                    )
                    return url, False
                else:
                    delay = min(base_delay * (2**attempt), 10.0)
                    log.warning(
                        f"Retry {attempt + 1}/{max_retries + 1} for URL '{url}': {e}. Waiting {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
            except Exception as e:
                log.error(f"Unexpected error resolving URL '{url}': {e}")
                return url, False
        return url, False

    async def _resolve_and_emit_sources(
        self,
        grounding_chunks: list[types.GroundingChunk],
        supports: list[types.GroundingSupport],
        event_emitter: Callable[["Event"], Awaitable[None]],
        pipe_start_time: float | None,
    ):
        """
        Resolves URLs in the background and emits a chat completion event
        containing only the source information, along with status updates.
        """
        initial_metadatas: list[tuple[int, str]] = []
        for i, g_c in enumerate(grounding_chunks):
            uri = None
            if (web_info := g_c.web) and web_info.uri:
                uri = web_info.uri
            elif (maps_info := g_c.maps) and maps_info.uri:
                uri = maps_info.uri

            if uri:
                initial_metadatas.append((i, uri))

        if not initial_metadatas:
            log.info("No source URIs found, skipping source emission.")
            return

        urls_to_resolve = [
            uri
            for _, uri in initial_metadatas
            if uri.startswith(
                "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
            )
        ]
        resolved_uris_map = {}

        if urls_to_resolve:
            num_urls = len(urls_to_resolve)
            self._emit_status_update(
                event_emitter,
                f"Resolving {num_urls} source URLs...",
                pipe_start_time,
            )

            try:
                log.info(f"Resolving {num_urls} source URLs...")
                async with aiohttp.ClientSession() as session:
                    tasks = [self._resolve_url(session, url) for url in urls_to_resolve]
                    results = await asyncio.gather(*tasks)
                log.info("URL resolution completed.")

                resolved_uris = [res[0] for res in results]
                resolved_uris_map = dict(zip(urls_to_resolve, resolved_uris))

                success_count = sum(1 for _, success in results if success)
                final_status_msg = (
                    "URL resolution complete"
                    if success_count == num_urls
                    else f"Resolved {success_count}/{num_urls} URLs"
                )
                self._emit_status_update(
                    event_emitter, final_status_msg, pipe_start_time, done=True
                )

            except Exception as e:
                log.error(f"Error during URL resolution: {e}")
                resolved_uris_map = {url: url for url in urls_to_resolve}
                self._emit_status_update(
                    event_emitter, "URL resolution failed", pipe_start_time, done=True
                )

        source_metadatas_template: list["SourceMetadata"] = [
            {"source": None, "original_url": None, "supports": []}
            for _ in grounding_chunks
        ]
        populated_metadatas = [m.copy() for m in source_metadatas_template]

        for chunk_index, original_uri in initial_metadatas:
            final_uri = resolved_uris_map.get(original_uri, original_uri)
            if 0 <= chunk_index < len(populated_metadatas):
                populated_metadatas[chunk_index]["original_url"] = original_uri
                populated_metadatas[chunk_index]["source"] = final_uri
            else:
                log.warning(
                    f"Chunk index {chunk_index} out of bounds when populating resolved URLs."
                )

        # Create a mapping from each chunk index to the text segments it supports.
        chunk_index_to_segments: dict[int, list[types.Segment]] = {}
        for support in supports:
            segment = support.segment
            indices = support.grounding_chunk_indices
            if not (segment and segment.text and indices is not None):
                continue

            for index in indices:
                if index not in chunk_index_to_segments:
                    chunk_index_to_segments[index] = []
                chunk_index_to_segments[index].append(segment)
                populated_metadatas[index]["supports"].append(support.model_dump())  # type: ignore

        valid_source_metadatas: list["SourceMetadata"] = []
        doc_list: list[str] = []

        for i, meta in enumerate(populated_metadatas):
            if meta.get("original_url") is not None:
                valid_source_metadatas.append(meta)

                content_parts: list[str] = []
                chunk = grounding_chunks[i]

                if maps_info := chunk.maps:
                    title = maps_info.title or "N/A"
                    place_id = maps_info.place_id or "N/A"
                    content_parts.append(f"Title: {title}\nPlace ID: {place_id}")

                supported_segments = chunk_index_to_segments.get(i)
                if supported_segments:
                    if content_parts:
                        content_parts.append("")  # Add a blank line for separation

                    # Use a set to show each unique snippet only once per source.
                    unique_snippets = {
                        (seg.text, seg.start_index, seg.end_index)
                        for seg in supported_segments
                        if seg.text is not None
                    }

                    # Sort snippets by their appearance in the text.
                    sorted_snippets = sorted(unique_snippets, key=lambda s: s[1] or 0)

                    snippet_strs = [
                        f'- "{text}" (Indices: {start}-{end})'
                        for text, start, end in sorted_snippets
                    ]
                    content_parts.append("Supported text snippets:")
                    content_parts.extend(snippet_strs)

                doc_list.append("\n".join(content_parts))

        sources_list: list["Source"] = []
        if valid_source_metadatas:
            sources_list.append(
                {
                    "source": {"name": "web_search"},
                    "document": doc_list,
                    "metadata": valid_source_metadatas,
                }
            )

        event: "ChatCompletionEvent" = {
            "type": "chat:completion",
            "data": {"sources": sources_list},
        }
        await event_emitter(event)
        log.info("Emitted sources event.")
        log.trace("ChatCompletionEvent:", payload=event)

    async def _emit_status_event_w_queries(
        self,
        grounding_metadata: types.GroundingMetadata,
        event_emitter: Callable[["Event"], Awaitable[None]],
    ) -> None:
        """
        Creates a StatusEvent with search URLs based on the web_search_queries
        in the GroundingMetadata. This covers both Google Search and Google Maps grounding.
        """
        if not grounding_metadata.web_search_queries:
            log.debug("Grounding metadata does not contain any search queries.")
            return

        search_queries = grounding_metadata.web_search_queries
        if not search_queries:
            log.debug("web_search_queries list is empty.")
            return

        # The queries are used for grounding, so we link them to a general Google search page.
        google_search_urls = [
            f"https://www.google.com/search?q={query}" for query in search_queries
        ]

        status_event_data: StatusEventData = {
            "action": "web_search",
            "description": "This response was grounded with a Google tool",
            "urls": google_search_urls,
        }
        status_event: StatusEvent = {
            "type": "status",
            "data": status_event_data,
        }
        await event_emitter(status_event)
        log.info("Emitted grounding queries.")
        log.trace("StatusEvent:", payload=status_event)

    # endregion 1.1 Add citations

    # region 1.2 Remove citation markers
    # TODO: Remove citation markers from model input.
    # endregion 1.2 Remove citation markers

    # region 1.3 Get permissive safety settings

    def _get_permissive_safety_settings(
        self, model_name: str
    ) -> list[types.SafetySetting]:
        """Get safety settings based on model name and permissive setting."""

        # Settings supported by most models
        category_threshold_map = {
            types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.OFF,
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.OFF,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.OFF,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.OFF,
            types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY: types.HarmBlockThreshold.BLOCK_NONE,
        }

        # Older models use BLOCK_NONE
        if model_name in [
            "gemini-1.5-pro-001",
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-8b-exp-0827",
            "gemini-1.5-flash-8b-exp-0924",
            "gemini-pro",
            "gemini-1.0-pro",
            "gemini-1.0-pro-001",
        ]:
            for category in category_threshold_map:
                category_threshold_map[category] = types.HarmBlockThreshold.BLOCK_NONE

        # Gemini 2.0 Flash supports CIVIC_INTEGRITY OFF
        if model_name in [
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-exp",
        ]:
            category_threshold_map[types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY] = (
                types.HarmBlockThreshold.OFF
            )

        log.debug(
            f"Safety settings: {str({k.value: v.value for k, v in category_threshold_map.items()})}"
        )

        safety_settings = [
            types.SafetySetting(category=category, threshold=threshold)
            for category, threshold in category_threshold_map.items()
        ]
        return safety_settings

    # endregion 1.3 Get permissive safety settings

    # region 1.4 Utility helpers

    def _emit_status_update(
        self,
        event_emitter: Callable[["Event"], Awaitable[None]],
        description: str,
        pipe_start_time: float | None,
        *,
        done: bool = False,
    ):
        """Constructs and emits a status event in a non-blocking task."""

        async def emit_task():
            time_str = (
                f" (+{(time.monotonic() - pipe_start_time):.2f}s)"
                if pipe_start_time is not None
                else ""
            )
            full_description = f"{description}{time_str}"

            status_event: "StatusEvent" = {
                "type": "status",
                "data": {"description": full_description, "done": done},
            }

            try:
                await event_emitter(status_event)
                log.debug(f"Emitted status:", payload=status_event)
            except Exception:
                log.exception("Error emitting status.")

        # Fire-and-forget the emission task.
        asyncio.create_task(emit_task())

    def _get_first_candidate(
        self, candidates: list[types.Candidate] | None
    ) -> types.Candidate | None:
        """Selects the first candidate, logging a warning if multiple exist."""
        if not candidates:
            log.warning("Received chunk with no candidates, skipping processing.")
            return None
        if len(candidates) > 1:
            log.warning("Multiple candidates found, defaulting to first candidate.")
        return candidates[0]

    def _get_model_name(self, body: "Body") -> tuple[str, bool]:
        """
        Extracts the effective and canonical model name from the request body.

        Handles standard model names and custom workspace models by prioritizing
        the base_model_id found in metadata.

        Args:
            body: The request body dictionary.

        Returns:
            A tuple containing:
            - The canonical model name (prefix removed).
            - A boolean indicating if the effective model name contained the
              'gemini_manifold_google_genai.' prefix.
        """
        # 1. Get the initially requested model name from the top level
        effective_model_name: str = body.get("model", "")
        initial_model_name = effective_model_name
        base_model_name = None

        # 2. Check for a base model ID in the metadata for custom models
        # If metadata exists, attempt to extract the base_model_id
        if metadata := body.get("metadata"):
            # Safely navigate the nested structure: metadata -> model -> info -> base_model_id
            base_model_name = (
                metadata.get("model", {}).get("info", {}).get("base_model_id", None)
            )
            # If a base model ID is found, it overrides the initially requested name
            if base_model_name:
                effective_model_name = base_model_name

        # 3. Determine if the effective model name contains the manifold prefix.
        # This flag indicates if the model (after considering base_model_id)
        # appears to be one defined or routed via the manifold pipe function.
        is_manifold_model = "gemini_manifold_google_genai." in effective_model_name

        # 4. Create the canonical model name by removing the manifold prefix
        # from the effective model name.
        canonical_model_name = effective_model_name.replace(
            "gemini_manifold_google_genai.", ""
        )

        # 5. Log the relevant names for debugging purposes
        log.debug(
            f"Model Name Extraction: initial='{initial_model_name}', "
            f"base='{base_model_name}', effective='{effective_model_name}', "
            f"canonical='{canonical_model_name}', is_manifold={is_manifold_model}"
        )

        # 6. Return the canonical name and the manifold flag
        return canonical_model_name, is_manifold_model

    def _is_flat_dict(self, data: Any) -> bool:
        """
        Checks if a dictionary contains only non-dict/non-list values (is one level deep).
        """
        if not isinstance(data, dict):
            return False
        return not any(isinstance(value, (dict, list)) for value in data.values())

    def _truncate_long_strings(
        self, data: Any, max_len: int, truncation_marker: str, truncation_enabled: bool
    ) -> Any:
        """
        Recursively traverses a data structure (dicts, lists) and truncates
        long string values. Creates copies to avoid modifying original data.

        Args:
            data: The data structure (dict, list, str, int, float, bool, None) to process.
            max_len: The maximum allowed length for string values.
            truncation_marker: The string to append to truncated values.
            truncation_enabled: Whether truncation is enabled.

        Returns:
            A potentially new data structure with long strings truncated.
        """
        if not truncation_enabled or max_len <= len(truncation_marker):
            # If truncation is disabled or max_len is too small, return original
            # Make a copy only if it's a mutable type we might otherwise modify
            if isinstance(data, (dict, list)):
                return copy.deepcopy(data)  # Ensure deep copy for nested structures
            return data  # Primitives are immutable

        if isinstance(data, str):
            if len(data) > max_len:
                return data[: max_len - len(truncation_marker)] + truncation_marker
            return data  # Return original string if not truncated
        elif isinstance(data, dict):
            # Process dictionary items, creating a new dict
            return {
                k: self._truncate_long_strings(
                    v, max_len, truncation_marker, truncation_enabled
                )
                for k, v in data.items()
            }
        elif isinstance(data, list):
            # Process list items, creating a new list
            return [
                self._truncate_long_strings(
                    item, max_len, truncation_marker, truncation_enabled
                )
                for item in data
            ]
        else:
            # Return non-string, non-container types as is (they are immutable)
            return data

    def plugin_stdout_format(self, record: "Record") -> str:
        """
        Custom format function for the plugin's logs.
        Serializes and truncates data passed under the 'payload' key in extra.
        """

        # Configuration Keys
        LOG_OPTIONS_PREFIX = "_log_"
        TRUNCATION_ENABLED_KEY = f"{LOG_OPTIONS_PREFIX}truncation_enabled"
        MAX_LENGTH_KEY = f"{LOG_OPTIONS_PREFIX}max_length"
        TRUNCATION_MARKER_KEY = f"{LOG_OPTIONS_PREFIX}truncation_marker"
        DATA_KEY = "payload"

        original_extra = record["extra"]
        # Extract the data intended for serialization using the chosen key
        data_to_process = original_extra.get(DATA_KEY)

        serialized_data_json = ""
        if data_to_process is not None:
            try:
                serializable_data = pydantic_core.to_jsonable_python(
                    data_to_process, serialize_unknown=True
                )

                # Determine truncation settings
                truncation_enabled = original_extra.get(TRUNCATION_ENABLED_KEY, True)
                max_length = original_extra.get(MAX_LENGTH_KEY, 256)
                truncation_marker = original_extra.get(TRUNCATION_MARKER_KEY, "[...]")

                # If max_length was explicitly provided, force truncation enabled
                if MAX_LENGTH_KEY in original_extra:
                    truncation_enabled = True

                # Truncate long strings
                truncated_data = self._truncate_long_strings(
                    serializable_data,
                    max_length,
                    truncation_marker,
                    truncation_enabled,
                )

                # Serialize the (potentially truncated) data
                if self._is_flat_dict(truncated_data) and not isinstance(
                    truncated_data, list
                ):
                    json_string = json.dumps(
                        truncated_data, separators=(",", ":"), default=str
                    )
                    # Add a simple prefix if it's compact
                    serialized_data_json = " - " + json_string
                else:
                    json_string = json.dumps(truncated_data, indent=2, default=str)
                    # Prepend with newline for readability
                    serialized_data_json = "\n" + json_string

            except (TypeError, ValueError) as e:  # Catch specific serialization errors
                serialized_data_json = f" - {{Serialization Error: {e}}}"
            except (
                Exception
            ) as e:  # Catch any other unexpected errors during processing
                serialized_data_json = f" - {{Processing Error: {e}}}"

        # Add the final JSON string (or error message) back into the record
        record["extra"]["_plugin_serialized_data"] = serialized_data_json

        # Base template
        base_template = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

        # Append the serialized data
        base_template += "{extra[_plugin_serialized_data]}"
        # Append the exception part
        base_template += "\n{exception}"
        # Return the format string template
        return base_template.rstrip()

    def _add_log_handler(self):
        """
        Adds or updates the loguru handler specifically for this plugin.
        Includes logic for serializing and truncating extra data.
        """

        def plugin_filter(record: "Record"):
            """Filter function to only allow logs from this plugin (based on module name)."""
            return record["name"] == __name__

        # Get the desired level name and number
        desired_level_name = self.valves.LOG_LEVEL
        try:
            # Use the public API to get level details
            desired_level_info = log.level(desired_level_name)
            desired_level_no = desired_level_info.no
        except ValueError:
            log.error(
                f"Invalid LOG_LEVEL '{desired_level_name}' configured for plugin {__name__}. Cannot add/update handler."
            )
            return  # Stop processing if the level is invalid

        # Access the internal state of the log
        handlers: dict[int, "Handler"] = log._core.handlers  # type: ignore
        handler_id_to_remove = None
        found_correct_handler = False

        for handler_id, handler in handlers.items():
            existing_filter = handler._filter  # Access internal attribute

            # Check if the filter matches our plugin_filter
            # Comparing function objects directly can be fragile if they are recreated.
            # Comparing by name and module is more robust for functions defined at module level.
            is_our_filter = (
                existing_filter is not None  # Make sure a filter is set
                and hasattr(existing_filter, "__name__")
                and existing_filter.__name__ == plugin_filter.__name__
                and hasattr(existing_filter, "__module__")
                and existing_filter.__module__ == plugin_filter.__module__
            )

            if is_our_filter:
                existing_level_no = handler.levelno
                log.trace(
                    f"Found existing handler {handler_id} for {__name__} with level number {existing_level_no}."
                )

                # Check if the level matches the desired level
                if existing_level_no == desired_level_no:
                    log.debug(
                        f"Handler {handler_id} for {__name__} already exists with the correct level '{desired_level_name}'."
                    )
                    found_correct_handler = True
                    break  # Found the correct handler, no action needed
                else:
                    # Found our handler, but the level is wrong. Mark for removal.
                    log.info(
                        f"Handler {handler_id} for {__name__} found, but log level differs "
                        f"(existing: {existing_level_no}, desired: {desired_level_no}). "
                        f"Removing it to update."
                    )
                    handler_id_to_remove = handler_id
                    break  # Found the handler to replace, stop searching

        # Remove the old handler if marked for removal
        if handler_id_to_remove is not None:
            try:
                log.remove(handler_id_to_remove)
                log.debug(f"Removed handler {handler_id_to_remove} for {__name__}.")
            except ValueError:
                # This might happen if the handler was somehow removed between the check and now
                log.warning(
                    f"Could not remove handler {handler_id_to_remove} for {__name__}. It might have already been removed."
                )
                # If removal failed but we intended to remove, we should still proceed to add
                # unless found_correct_handler is somehow True (which it shouldn't be if handler_id_to_remove was set).

        # Add a new handler if no correct one was found OR if we just removed an incorrect one
        if not found_correct_handler:
            self.log_level = desired_level_name
            log.add(
                sys.stdout,
                level=desired_level_name,
                format=self.plugin_stdout_format,
                filter=plugin_filter,
            )
            log.debug(
                f"Added new handler to loguru for {__name__} with level {desired_level_name}."
            )

    # endregion 1.4 Utility helpers

    # endregion 1. Helper methods inside the Filter class
