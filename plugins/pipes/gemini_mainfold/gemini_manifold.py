"""
title: Gemini Manifold google_genai
id: gemini_manifold_google_genai
description: Manifold function for Gemini Developer API and Vertex AI. Uses the newer google-genai SDK. Aims to support as many features from it as possible.
author: suurt8ll
author_url: https://github.com/suurt8ll
funding_url: https://github.com/suurt8ll/open_webui_functions
license: MIT
version: 1.26.0
requirements: google-genai==1.49.0
"""

VERSION = "1.26.0"
# This is the recommended version for the companion filter.
# Older versions might still work, but backward compatibility is not guaranteed
# during the development of this personal use plugin.
RECOMMENDED_COMPANION_VERSION = "1.7.0"


# Keys `title`, `id` and `description` in the frontmatter above are used for my own development purposes.
# They don't have any effect on the plugin's functionality.


# This is a helper function that provides a manifold for Google's Gemini Studio API and Vertex AI.
# Be sure to check out my GitHub repository for more information! Contributions, questions and suggestions are very welcome.

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from google.cloud import storage
from google.api_core import exceptions

import time
import copy
import json
from urllib.parse import urlparse, parse_qs
import xxhash
import asyncio
import aiofiles
from aiocache import cached
from aiocache.base import BaseCache
from aiocache.serializers import NullSerializer
from aiocache.backends.memory import SimpleMemoryCache
from functools import cache
from datetime import datetime, timezone
from fastapi.datastructures import State
import io
import mimetypes
import uuid
import base64
import re
import fnmatch
import sys
from loguru import logger
from fastapi import Request
import pydantic_core
from pydantic import BaseModel, Field, field_validator
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import (
    Any,
    Final,
    AsyncGenerator,
    Literal,
    TYPE_CHECKING,
    cast,
)

from open_webui.models.chats import Chats
from open_webui.models.files import FileForm, Files
from open_webui.storage.provider import Storage
from open_webui.models.functions import Functions
from open_webui.utils.misc import pop_system_message

# This block is skipped at runtime.
if TYPE_CHECKING:
    from loguru import Record
    from loguru._handler import Handler  # type: ignore
    # Imports custom type definitions (TypedDicts) for static analysis purposes (mypy/pylance).
    from utils.manifold_types import *

# Setting auditable=False avoids duplicate output for log levels that would be printed out by the main log.
log = logger.bind(auditable=False)

# FIXME: remove
COMPATIBLE_MODELS_FOR_URL_CONTEXT: Final = [
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite-preview-09-2025",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-live-001",
]

# A mapping of finish reason names (str) to human-readable descriptions.
# This allows handling of reasons that may not be defined in the current SDK version.
FINISH_REASON_DESCRIPTIONS: Final = {
    "FINISH_REASON_UNSPECIFIED": "The reason for finishing is not specified.",
    "STOP": "Natural stopping point or stop sequence reached.",
    "MAX_TOKENS": "The maximum number of tokens was reached.",
    "SAFETY": "The response was blocked due to safety concerns.",
    "RECITATION": "The response was blocked due to potential recitation of copyrighted material.",
    "LANGUAGE": "The response was stopped because of an unsupported language.",
    "OTHER": "The response was stopped for an unspecified reason.",
    "BLOCKLIST": "The response was blocked due to a word on a blocklist.",
    "PROHIBITED_CONTENT": "The response was blocked for containing prohibited content.",
    "SPII": "The response was blocked for containing sensitive personally identifiable information.",
    "MALFORMED_FUNCTION_CALL": "The model generated an invalid function call.",
    "IMAGE_SAFETY": "Generated image was blocked due to safety concerns.",
    "UNEXPECTED_TOOL_CALL": "The model generated an invalid tool call.",
    "IMAGE_PROHIBITED_CONTENT": "Generated image was blocked for containing prohibited content.",
    "NO_IMAGE": "The model was expected to generate an image, but it did not.",
    "IMAGE_OTHER": (
        "Image generation stopped for other reasons, possibly related to safety or quality. "
        "Try a different image or prompt."
    ),
}

# Finish reasons that are considered normal and do not require user notification.
NORMAL_REASONS: Final = {types.FinishReason.STOP, types.FinishReason.MAX_TOKENS}

# These tags will be "disabled" in the response, meaning that they will not be parsed by the backend.
SPECIAL_TAGS_TO_DISABLE = [
    "details",
    "think",
    "thinking",
    "reason",
    "reasoning",
    "thought",
    "Thought",
    "|begin_of_thought|",
    "code_interpreter",
    "|begin_of_solution|",
]
ZWS = "\u200b"


class GenaiApiError(Exception):
    """Custom exception for errors during Genai API interactions."""

    pass


class FilesAPIError(Exception):
    """Custom exception for errors during Files API operations."""

    pass


class EventEmitter:
    """A helper class to abstract web-socket event emissions to the front-end."""

    def __init__(
        self,
        event_emitter: Callable[["Event"], Awaitable[None]] | None,
        *,
        hide_successful_status: bool = False,
    ):
        self.event_emitter = event_emitter
        self.hide_successful_status = hide_successful_status

    def emit_toast(
        self,
        msg: str,
        toastType: Literal["info", "success", "warning", "error"] = "info",
    ) -> None:
        """Emits a toast notification to the front-end. This is a fire-and-forget operation."""
        if not self.event_emitter:
            return

        event: "NotificationEvent" = {
            "type": "notification",
            "data": {"type": toastType, "content": msg},
        }

        log.debug(f"Emitting toast: '{msg}'")
        log.trace("Toast payload:", payload=event)

        async def send_toast():
            try:
                # Re-check in case the event loop runs this later and state has changed.
                if self.event_emitter:
                    await self.event_emitter(event)
            except Exception:
                log.exception("Error emitting toast notification.")

        asyncio.create_task(send_toast())

    async def emit_status(
        self,
        message: str,
        done: bool = False,
        hidden: bool = False,
        *,
        is_successful_finish: bool = False,
    ) -> None:
        """Emit status updates asynchronously."""
        if not self.event_emitter:
            return

        # If this is a successful finish status and the user wants to hide it,
        # we override the hidden flag.
        if is_successful_finish and self.hide_successful_status:
            hidden = True

        status_event: "StatusEvent" = {
            "type": "status",
            "data": {"description": message, "done": done, "hidden": hidden},
        }

        log.debug(f"Emitting status: '{message}'")
        log.trace("Status payload:", payload=status_event)

        try:
            await self.event_emitter(status_event)
        except Exception:
            log.exception("Error emitting status.")

    async def emit_completion(
        self,
        content: str | None = None,
        done: bool = False,
        error: str | None = None,
        sources: list["Source"] | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Constructs and emits completion event."""
        if not self.event_emitter:
            return

        emission: "ChatCompletionEvent" = {
            "type": "chat:completion",
            "data": {"done": done},
        }
        parts = []
        if content is not None:
            emission["data"]["content"] = content
            parts.append("content")
        if error is not None:
            emission["data"]["error"] = {"detail": error}
            parts.append("error")
        if sources is not None:
            emission["data"]["sources"] = sources
            parts.append("sources")
        if usage is not None:
            emission["data"]["usage"] = usage
            parts.append("usage")

        desc = f" with {', '.join(parts)}" if parts else ""
        log.debug(f"Emitting completion: done={done}{desc}")
        log.trace("Completion payload:", payload=emission)

        try:
            await self.event_emitter(emission)
        except Exception:
            log.exception("Error emitting completion.")

    async def emit_usage(self, usage_data: dict[str, Any]) -> None:
        """A wrapper around emit_completion to specifically emit usage data."""
        await self.emit_completion(usage=usage_data)

    async def emit_error(
        self,
        error_msg: str,
        warning: bool = False,
        exception: bool = True,
    ) -> None:
        """Emits an event to the front-end that causes it to display a nice red error message."""
        if warning:
            log.opt(depth=1, exception=False).warning(error_msg)
        else:
            log.opt(depth=1, exception=exception).error(error_msg)
        await self.emit_completion(error=f"\n{error_msg}", done=True)


class UploadStatusManager:
    """
    Manages and centralizes status updates for concurrent file uploads.

    This manager is self-configuring. It discovers the number of files that
    require an actual upload at runtime, only showing a status message to the
    user when network activity is necessary.

    The communication protocol uses tuples sent via an asyncio.Queue:
    - ('REGISTER_UPLOAD',): Sent by a worker when it determines an upload is needed.
    - ('COMPLETE_UPLOAD',): Sent by a worker when its upload is finished.
    - ('FINALIZE',): Sent by the orchestrator when all workers are done.
    """

    def __init__(
        self,
        event_emitter: EventEmitter,
        start_time: float,
    ):
        self.event_emitter = event_emitter
        self.start_time = start_time
        self.queue = asyncio.Queue()
        self.total_uploads_expected = 0
        self.uploads_completed = 0
        self.finalize_received = False
        self.is_active = False

    async def run(self) -> None:
        """
        Runs the manager loop, listening for updates and emitting status to the UI.
        This should be started as a background task using asyncio.create_task().
        """
        while not (
            self.finalize_received
            and self.total_uploads_expected == self.uploads_completed
        ):
            msg = await self.queue.get()
            msg_type = msg[0]

            if msg_type == "REGISTER_UPLOAD":
                self.is_active = True
                self.total_uploads_expected += 1
                await self._emit_progress_update()
            elif msg_type == "COMPLETE_UPLOAD":
                self.uploads_completed += 1
                await self._emit_progress_update()
            elif msg_type == "FINALIZE":
                self.finalize_received = True

            self.queue.task_done()

        log.debug("UploadStatusManager finished its run.")

    async def _emit_progress_update(self) -> None:
        """Emits the current progress to the front-end if uploads are active."""
        if not self.is_active:
            return

        elapsed_time = time.monotonic() - self.start_time
        time_str = f"(+{elapsed_time:.2f}s)"

        is_done = (
            self.total_uploads_expected > 0
            and self.uploads_completed == self.total_uploads_expected
        )

        if is_done:
            message = f"- Upload complete. {self.uploads_completed} file(s) processed. {time_str}"
        else:
            # Show "Uploading 1 of N..."
            message = f"- Uploading file {self.uploads_completed + 1} of {self.total_uploads_expected}... {time_str}"

        await self.event_emitter.emit_status(message, done=is_done)


class FilesAPIManager:
    """
    Manages uploading, caching, and retrieving files using the Google Gemini Files API.

    This class provides a stateless and efficient way to handle files by using a fast,
    non-cryptographic hash (xxHash) of the file's content as the primary identifier.
    This enables content-addressable storage, preventing duplicate uploads of the
    same file. It uses a multi-tiered approach:

    1. Hot Path (In-Memory Caches): For instantly retrieving file objects and hashes
       for recently used files.
    2. Warm Path (Stateless GET): For quickly recovering file state after a server
       restart by using a deterministic name (derived from the content hash) and a
       single `get` API call.
    3. Cold Path (Upload): As a last resort, for uploading new files or re-uploading
       expired ones.
    """

    def __init__(
        self,
        client: genai.Client,
        file_cache: SimpleMemoryCache,
        id_hash_cache: SimpleMemoryCache,
        event_emitter: EventEmitter,
    ):
        """
        Initializes the FilesAPIManager.

        Args:
            client: An initialized `google.genai.Client` instance.
            file_cache: An aiocache instance for mapping `content_hash -> types.File`.
                        Must be configured with `aiocache.serializers.NullSerializer`.
            id_hash_cache: An aiocache instance for mapping `owui_file_id -> content_hash`.
                           This is an optimization to avoid re-hashing known files.
            event_emitter: An abstract class for emitting events to the front-end.
        """
        self.client = client
        self.file_cache = file_cache
        self.id_hash_cache = id_hash_cache
        self.event_emitter = event_emitter
        # A dictionary to manage locks for concurrent uploads.
        # The key is the content_hash, the value is an asyncio.Lock.
        self.upload_locks: dict[str, asyncio.Lock] = {}

    async def get_or_upload_file(
        self,
        file_bytes: bytes,
        mime_type: str,
        *,
        owui_file_id: str | None = None,
        status_queue: asyncio.Queue | None = None,
    ) -> types.File:
        """
        The main public method to get a file, using caching, recovery, or uploading.

        This method uses a fast content hash (xxHash) as the primary key for all
        caching and remote API interactions to ensure deduplication and performance.
        It is safe from race conditions during concurrent uploads.

        Args:
            file_bytes: The raw byte content of the file. Required.
            mime_type: The MIME type of the file (e.g., 'image/png'). Required.
            owui_file_id: The unique ID of the file from Open WebUI, if available.
                          Used for logging and as a key for the hash cache optimization.
            status_queue: An optional asyncio.Queue to report upload lifecycle events.

        Returns:
            An `ACTIVE` `google.genai.types.File` object.

        Raises:
            FilesAPIError: If the file fails to upload or process.
        """
        # Step 1: Get the fast content hash, using the ID cache as an optimization if possible.
        content_hash = await self._get_content_hash(file_bytes, owui_file_id)

        # Step 2: The Hot Path (Check Local File Cache)
        # A cache hit means the file is valid and we can return immediately.
        cached_file: types.File | None = await self.file_cache.get(content_hash)
        if cached_file:
            log_id = f"OWUI ID: {owui_file_id}" if owui_file_id else "anonymous file"
            log.debug(
                f"Cache HIT for file hash {content_hash} ({log_id}). Returning immediately."
            )
            return cached_file

        # On cache miss, acquire a lock specific to this file's content to prevent race conditions.
        # dict.setdefault is atomic, ensuring only one lock is created per hash.
        lock = self.upload_locks.setdefault(content_hash, asyncio.Lock())
        if lock.locked():
            log.debug(
                f"Lock for hash {content_hash} is held by another task. "
                f"This call will now wait for the lock to be released."
            )

        async with lock:
            # Step 2.5: Double-Checked Locking
            # After acquiring the lock, check the cache again. Another task might have
            # completed the upload while we were waiting for the lock.
            cached_file = await self.file_cache.get(content_hash)
            if cached_file:
                log.debug(
                    f"Cache HIT for file hash {content_hash} after acquiring lock. Returning."
                )
                return cached_file

            # Step 3: The Warm/Cold Path (On Cache Miss)
            deterministic_name = f"files/owui-v1-{content_hash}"
            log.debug(
                f"Cache MISS for hash {content_hash}. Attempting stateless recovery with GET: {deterministic_name}"
            )

            try:
                # Attempt to get the file (Warm Path)
                file = await self.client.aio.files.get(name=deterministic_name)
                if not file.name:
                    raise FilesAPIError(
                        f"Stateless recovery for {deterministic_name} returned a file without a name."
                    )

                log.debug(
                    f"Stateless recovery successful for {deterministic_name}. File exists on server."
                )
                active_file = await self._poll_for_active_state(file.name, owui_file_id)

                ttl_seconds = self._calculate_ttl(active_file.expiration_time)
                await self.file_cache.set(content_hash, active_file, ttl=ttl_seconds)

                return active_file
            except genai_errors.ClientError as e:
                if e.code == 403:  # "Not found" signal from the API.
                    log.info(
                        f"File {deterministic_name} not found on server (received 403). Proceeding to upload."
                    )
                    # Proceed to upload (Cold Path)
                    return await self._upload_and_process_file(
                        content_hash,
                        file_bytes,
                        mime_type,
                        deterministic_name,
                        owui_file_id,
                        status_queue,
                    )
                else:
                    log.exception(
                        f"A non-403 client error occurred during stateless recovery for {deterministic_name}."
                    )
                    self.event_emitter.emit_toast(
                        f"API error for file: {e.code}. Please check permissions.",
                        "error",
                    )
                    raise FilesAPIError(
                        f"Failed to check file status for {deterministic_name}: {e}"
                    ) from e
            except Exception as e:
                log.exception(
                    f"An unexpected error occurred during stateless recovery for {deterministic_name}."
                )
                self.event_emitter.emit_toast(
                    "Unexpected error retrieving a file. Please try again.",
                    "error",
                )
                raise FilesAPIError(
                    f"Failed to check file status for {deterministic_name}: {e}"
                ) from e
            finally:
                # Clean up the lock from the dictionary once processing is complete
                # for this hash, preventing memory growth over time.
                # This is safe because any future request for this hash will hit the cache.
                if content_hash in self.upload_locks:
                    del self.upload_locks[content_hash]

    async def _get_content_hash(
        self, file_bytes: bytes, owui_file_id: str | None
    ) -> str:
        """
        Retrieves the file's content hash, using a cache for known IDs or computing it.

        This acts as a memoization layer for the hashing process, avoiding
        re-computation for files with a known Open WebUI ID. For anonymous files
        (owui_file_id=None), it will always compute the hash.
        """
        if owui_file_id:
            # First, check the ID-to-Hash cache for known files.
            cached_hash: str | None = await self.id_hash_cache.get(owui_file_id)
            if cached_hash:
                log.trace(f"Hash cache HIT for OWUI ID {owui_file_id}.")
                return cached_hash

        # If not in cache or if file is anonymous, compute the fast hash.
        log.trace(
            f"Hash cache MISS for OWUI ID {owui_file_id if owui_file_id else 'N/A'}. Computing hash."
        )
        content_hash = xxhash.xxh64(file_bytes).hexdigest()

        # If there was an ID, store the newly computed hash for next time.
        if owui_file_id:
            await self.id_hash_cache.set(owui_file_id, content_hash)

        return content_hash

    def _calculate_ttl(self, expiration_time: datetime | None) -> float | None:
        """Calculates the TTL in seconds from an expiration datetime."""
        if not expiration_time:
            return None

        now_utc = datetime.now(timezone.utc)
        if expiration_time <= now_utc:
            return 0

        return (expiration_time - now_utc).total_seconds()

    async def _upload_and_process_file(
        self,
        content_hash: str,
        file_bytes: bytes,
        mime_type: str,
        deterministic_name: str,
        owui_file_id: str | None,
        status_queue: asyncio.Queue | None = None,
    ) -> types.File:
        """Handles the full upload and post-upload processing workflow."""

        # Register with the manager that an actual upload is starting.
        if status_queue:
            await status_queue.put(("REGISTER_UPLOAD",))

        log.info(f"Starting upload for {deterministic_name}...")

        try:
            file_io = io.BytesIO(file_bytes)
            upload_config = types.UploadFileConfig(
                name=deterministic_name, mime_type=mime_type
            )
            uploaded_file = await self.client.aio.files.upload(
                file=file_io, config=upload_config
            )
            if not uploaded_file.name:
                raise FilesAPIError(
                    f"File upload for {deterministic_name} did not return a file name."
                )

            log.debug(f"{uploaded_file.name} uploaded.")
            log.trace("Uploaded file details:", payload=uploaded_file)

            # Check if the file is already active. If so, we can skip polling.
            if uploaded_file.state == types.FileState.ACTIVE:
                log.debug(
                    f"File {uploaded_file.name} is already ACTIVE. Skipping poll."
                )
                active_file = uploaded_file
            else:
                # If not active, proceed with the original polling logic.
                log.debug(
                    f"{uploaded_file.name} uploaded with state {uploaded_file.state}. Polling for ACTIVE state."
                )
                active_file = await self._poll_for_active_state(
                    uploaded_file.name, owui_file_id
                )
                log.debug(f"File {active_file.name} is now ACTIVE.")

            # Calculate TTL and set in the main file cache using the content hash as the key.
            ttl_seconds = self._calculate_ttl(active_file.expiration_time)
            await self.file_cache.set(content_hash, active_file, ttl=ttl_seconds)
            log.debug(
                f"Cached new file object for hash {content_hash} with TTL: {ttl_seconds}s."
            )

            return active_file
        except Exception as e:
            log.exception(f"File upload or processing failed for {deterministic_name}.")
            self.event_emitter.emit_toast(
                "Upload failed for a file. Please check connection and try again.",
                "error",
            )
            raise FilesAPIError(f"Upload failed for {deterministic_name}: {e}") from e
        finally:
            # Report completion (success or failure) to the status manager.
            # This ensures the progress counter always advances.
            if status_queue:
                await status_queue.put(("COMPLETE_UPLOAD",))

    async def _poll_for_active_state(
        self,
        file_name: str,
        owui_file_id: str | None,
        timeout: int = 60,
        poll_interval: int = 1,
    ) -> types.File:
        """Polls the file's status until it is ACTIVE or fails."""
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            try:
                file = await self.client.aio.files.get(name=file_name)
            except Exception as e:
                raise FilesAPIError(
                    f"Polling failed: Could not get status for {file_name}. Reason: {e}"
                ) from e

            if file.state == types.FileState.ACTIVE:
                return file
            if file.state == types.FileState.FAILED:
                log_id = f"'{owui_file_id}'" if owui_file_id else "an uploaded file"
                error_message = f"File processing failed on server for {file_name}."
                toast_message = f"Google could not process {log_id}."
                if file.error:
                    reason = f"Reason: {file.error.message} (Code: {file.error.code})"
                    error_message += f" {reason}"
                    toast_message += f" Reason: {file.error.message}"

                self.event_emitter.emit_toast(toast_message, "error")
                raise FilesAPIError(error_message)

            state_name = file.state.name if file.state else "UNKNOWN"
            log.trace(
                f"File {file_name} is still {state_name}. Waiting {poll_interval}s..."
            )
            await asyncio.sleep(poll_interval)

        raise FilesAPIError(
            f"File {file_name} did not become ACTIVE within {timeout} seconds."
        )


class GeminiContentBuilder:
    """Builds a list of `google.genai.types.Content` objects from the OWUI's body payload."""

    def __init__(
        self,
        messages_body: list["Message"],
        metadata_body: "Metadata",
        user_data: "UserData",
        event_emitter: EventEmitter,
        valves: "Pipe.Valves",
        files_api_manager: "FilesAPIManager",
    ):
        self.messages_body = messages_body
        self.upload_documents = (metadata_body.get("features", {}) or {}).get(
            "upload_documents", False
        )
        self.event_emitter = event_emitter
        self.valves = valves
        self.files_api_manager = files_api_manager
        self.is_temp_chat = metadata_body.get("chat_id") == "local"
        self.vertexai = self.files_api_manager.client.vertexai

        self.system_prompt, self.messages_body = self._extract_system_prompt(
            self.messages_body
        )
        self.messages_db = self._fetch_and_validate_chat_history(
            metadata_body, user_data
        )

    async def build_contents(self, start_time: float) -> list[types.Content]:
        """
        The main public method to generate the contents list by processing all
        message turns concurrently and using a self-configuring status manager.
        """
        if not self.messages_db:
            warn_msg = (
                "There was a problem retrieving the messages from the backend database. "
                "Check the console for more details. "
                "Citation filtering and file uploads will not be available."
            )
            self.event_emitter.emit_toast(warn_msg, "warning")

        # 1. Set up and launch the status manager. It will activate itself if needed.
        status_manager = UploadStatusManager(self.event_emitter, start_time=start_time)
        manager_task = asyncio.create_task(status_manager.run())

        # 2. Create and run concurrent processing tasks for each message turn.
        tasks = [
            self._process_message_turn(i, message, status_manager.queue)
            for i, message in enumerate(self.messages_body)
        ]
        log.debug(f"Starting concurrent processing of {len(tasks)} message turns.")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Signal to the manager that no more uploads will be registered.
        await status_manager.queue.put(("FINALIZE",))

        # 4. Wait for the manager to finish processing all reported uploads.
        await manager_task

        # 5. Filter and assemble the final contents list.
        contents: list[types.Content] = []
        for i, res in enumerate(results):
            if isinstance(res, types.Content):
                contents.append(res)
            elif isinstance(res, Exception):
                log.error(
                    f"An error occurred while processing message {i} concurrently.",
                    payload=res,
                )
        return contents

    @staticmethod
    def _extract_system_prompt(
        messages: list["Message"],
    ) -> tuple[str | None, list["Message"]]:
        """Extracts the system prompt and returns it along with the modified message list."""
        system_message, remaining_messages = pop_system_message(messages)  # type: ignore
        system_prompt: str | None = (system_message or {}).get("content")
        return system_prompt, remaining_messages  # type: ignore

    def _fetch_and_validate_chat_history(
        self, metadata_body: "Metadata", user_data: "UserData"
    ) -> list["ChatMessageTD"] | None:
        """
        Fetches message history from the database and validates its length against the request body.
        Returns the database messages or None if not found or if validation fails.
        """
        # 1. Fetch from database
        chat_id = metadata_body.get("chat_id", "")
        if chat := Chats.get_chat_by_id_and_user_id(
            id=chat_id, user_id=user_data["id"]
        ):
            chat_content: "ChatObjectDataTD" = chat.chat  # type: ignore
            # Last message is the upcoming assistant response, at this point in the logic it's empty.
            messages_db = chat_content.get("messages", [])[:-1]
        else:
            log.warning(
                f"Chat {chat_id} not found. Cannot process files or filter citations."
            )
            return None

        # 2. Validate length against the current message body
        if len(messages_db) != len(self.messages_body):
            warn_msg = (
                f"Messages in the body ({len(self.messages_body)}) and "
                f"messages in the database ({len(messages_db)}) do not match. "
                "This is likely due to a bug in Open WebUI. "
                "Cannot process files or filter citations."
            )

            # TODO: Emit a toast to the user in the front-end.
            log.warning(warn_msg)
            # Invalidate the db messages if they don't match
            return None

        return messages_db

    async def _process_message_turn(
        self, i: int, message: "Message", status_queue: asyncio.Queue
    ) -> types.Content | None:
        """
        Processes a single message turn, handling user and assistant roles,
        and returns a complete `types.Content` object. Designed to be run concurrently.
        """
        role = message.get("role")
        parts: list[types.Part] = []

        if role == "user":
            message = cast("UserMessage", message)
            files = []
            if self.messages_db:
                message_db = self.messages_db[i]
                if self.upload_documents:
                    files = message_db.get("files", [])
            parts = await self._process_user_message(message, files, status_queue)
            # Case 1: User content is completely empty (no text, no files).
            if not parts:
                log.info(
                    f"User message at index {i} is completely empty. "
                    "Injecting a prompt to ask for clarification."
                )
                # Inform the user via a toast notification.
                toast_msg = f"Your message #{i + 1} was empty. The assistant will ask for clarification."
                self.event_emitter.emit_toast(toast_msg, "info")

                clarification_prompt = (
                    "The user sent an empty message. Please ask the user for "
                    "clarification on what they would like to ask or discuss."
                )
                # This will become the only part for this user message.
                parts = await self._genai_parts_from_text(
                    clarification_prompt, status_queue
                )
            else:
                # Case 2: User has sent content, check if it includes text.
                has_text_component = any(p.text for p in parts if p.text)
                if not has_text_component:
                    # The user sent content (e.g., files) but no accompanying text.
                    if self.vertexai:
                        # Vertex AI requires a text part in multi-modal messages.
                        log.info(
                            f"User message at index {i} lacks a text component for Vertex AI. "
                            "Adding default text prompt."
                        )
                        # Inform the user via a toast notification.
                        toast_msg = (
                            f"For your message #{i + 1}, a default prompt was added as text is required "
                            "for requests with attachments when using Vertex AI."
                        )
                        self.event_emitter.emit_toast(toast_msg, "info")

                        default_prompt_text = (
                            "The user did not send any text message with the additional context. "
                            "Answer by summarizing the newly added context."
                        )
                        default_text_parts = await self._genai_parts_from_text(
                            default_prompt_text, status_queue
                        )
                        parts.extend(default_text_parts)
                    else:
                        # Google Developer API allows no-text user content.
                        log.info(
                            f"User message at index {i} lacks a text component for Google Developer API. "
                            "Proceeding with non-text parts only."
                        )
        elif role == "assistant":
            message = cast("AssistantMessage", message)
            # Google API's assistant role is "model"
            role = "model"
            sources = None
            if self.messages_db:
                message_db = self.messages_db[i]
                sources = message_db.get("sources")
            parts = await self._process_assistant_message(
                message, sources, status_queue
            )
        else:
            warn_msg = f"Message {i} has an invalid role: {role}. Skipping to the next message."
            log.warning(warn_msg)
            self.event_emitter.emit_toast(warn_msg, "warning")
            return None

        # Only create a Content object if there are parts to include.
        if parts:
            return types.Content(parts=parts, role=role)
        return None

    async def _process_user_message(
        self,
        message: "UserMessage",
        files: list["FileAttachmentTD"],
        status_queue: asyncio.Queue,
    ) -> list[types.Part]:
        user_parts: list[types.Part] = []
        db_files_processed = False

        # PATH 1: Database is available (Normal Chat).
        if self.messages_db and files:
            db_files_processed = True
            log.info(f"Processing {len(files)} files from the database concurrently.")

            upload_tasks = []
            for file in files:
                log.debug("Preparing DB file for concurrent upload:", payload=file)
                uri = ""
                if file.get("type") == "image":
                    uri = file.get("url", "")
                elif file.get("type") == "file":
                    # Reconstruct the local API URI to be handled by our unified function
                    uri = f"/api/v1/files/{file.get('id', '')}/content"

                if uri:
                    # Create a coroutine for each file upload and add it to a list.
                    upload_tasks.append(self._genai_part_from_uri(uri, status_queue))
                else:
                    log.warning("Could not determine URI for file in DB.", payload=file)

            if upload_tasks:
                # Run all upload tasks concurrently. asyncio.gather maintains the order of results.
                results = await asyncio.gather(*upload_tasks)
                # Filter out None results (from failed uploads) and add the successful parts to the list.
                user_parts.extend(part for part in results if part)

        # Now, process the content from the message payload.
        user_content = message.get("content")
        if isinstance(user_content, str):
            user_content_list: list["Content"] = [
                {"type": "text", "text": user_content}
            ]
        elif isinstance(user_content, list):
            user_content_list = user_content
        else:
            warn_msg = "User message content is not a string or list, skipping."
            log.warning(warn_msg)
            self.event_emitter.emit_toast(warn_msg, "warning")
            return user_parts

        for c in user_content_list:
            c_type = c.get("type")
            if c_type == "text":
                c = cast("TextContent", c)
                if c_text := c.get("text"):
                    user_parts.extend(
                        await self._genai_parts_from_text(c_text, status_queue)
                    )

            # PATH 2: Temporary Chat Image Handling.
            elif c_type == "image_url" and not db_files_processed:
                log.info("Processing image from payload (temporary chat mode).")
                c = cast("ImageContent", c)
                if uri := c.get("image_url", {}).get("url"):
                    if part := await self._genai_part_from_uri(uri, status_queue):
                        user_parts.append(part)

        return user_parts

    async def _process_assistant_message(
        self,
        message: "AssistantMessage",
        sources: list["Source"] | None,
        status_queue: asyncio.Queue,
    ) -> list[types.Part]:
        assistant_text = message.get("content")
        if sources:
            assistant_text = self._remove_citation_markers(assistant_text, sources)
        return await self._genai_parts_from_text(assistant_text, status_queue)

    async def _genai_part_from_uri(
        self, uri: str, status_queue: asyncio.Queue
    ) -> types.Part | None:
        """
        Processes any resource URI and returns a genai.types.Part.
        This is the central dispatcher for all media processing, handling data URIs,
        local API file paths, and YouTube URLs. It decides whether to use the
        Files API or send raw bytes based on configuration and context.
        """
        if not uri:
            log.warning("Received an empty URI, skipping.")
            return None

        try:
            file_bytes: bytes | None = None
            mime_type: str | None = None
            owui_file_id: str | None = None

            # Step 1: Extract bytes and mime_type from the URI if applicable
            if uri.startswith("data:image"):
                match = re.match(r"data:(image/\w+);base64,(.+)", uri)
                if not match:
                    raise ValueError("Invalid data URI for image.")
                mime_type, base64_data = match.group(1), match.group(2)
                file_bytes = base64.b64decode(base64_data)
            elif uri.startswith("/api/v1/files/"):
                log.info(f"Processing local API file URI: {uri}")
                file_id = uri.split("/")[4]
                owui_file_id = file_id
                file_bytes, mime_type = await self._get_file_data(file_id)
            elif "youtube.com/" in uri or "youtu.be/" in uri:
                log.info(f"Found YouTube URL: {uri}")
                return self._genai_part_from_youtube_uri(uri)
            # TODO: Google Cloud Storage bucket support.
            # elif uri.startswith("gs://"): ...
            else:
                warn_msg = f"Unsupported URI: '{uri[:64]}...' Links must be to YouTube or a supported file type."
                log.warning(warn_msg)
                self.event_emitter.emit_toast(warn_msg, "warning")
                return None

            # Step 2: If we have bytes, decide how to create the Part
            if file_bytes and mime_type:
                # TODO: The Files API is strict about MIME types (e.g., text/plain,
                # application/pdf). In the future, inspect the content of files
                # with unsupported text-like MIME types (e.g., 'application/json',
                # 'text/markdown'). If the content is detected as plaintext,
                # override the `mime_type` variable to 'text/plain' to allow the upload.

                # Determine whether to use the Files API based on the specified conditions.
                use_files_api = True
                reason = ""

                if not self.valves.USE_FILES_API:
                    reason = "disabled by user setting (USE_FILES_API=False)"
                    use_files_api = False
                elif self.vertexai:
                    reason = "the active client is configured for Vertex AI, which does not support the Files API"
                    use_files_api = False
                elif self.is_temp_chat:
                    reason = "temporary chat mode is active"
                    use_files_api = False

                if use_files_api:
                    log.info(f"Using Files API for resource from URI: {uri[:64]}...")
                    gemini_file = await self.files_api_manager.get_or_upload_file(
                        file_bytes=file_bytes,
                        mime_type=mime_type,
                        owui_file_id=owui_file_id,
                        status_queue=status_queue,
                    )
                    return types.Part(
                        file_data=types.FileData(
                            file_uri=gemini_file.uri,
                            mime_type=gemini_file.mime_type,
                        )
                    )
                else:
                    log.info(
                        f"Sending raw bytes because {reason}. Resource from URI: {uri[:64]}..."
                    )
                    return types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

            return None  # Return None if bytes/mime_type could not be determined

        except FilesAPIError as e:
            error_msg = f"Files API failed for URI '{uri[:64]}...': {e}"
            log.error(error_msg)
            self.event_emitter.emit_toast(error_msg, "error")
            return None
        except Exception:
            log.exception(f"Error processing URI: {uri[:64]}[...]")
            return None

    def _genai_part_from_youtube_uri(self, uri: str) -> types.Part | None:
        """Creates a Gemini Part from a YouTube URL, with optional video metadata.

        Handles standard (`watch?v=`), short (`youtu.be/`), mobile (`shorts/`),
        and live (`live/`) URLs. Metadata is parsed for the Gemini Developer API
        but ignored for Vertex AI, which receives a simple URI Part.

        - **Start/End Time**: `?t=<value>` and `#end=<value>`. The value can be a
          flexible duration (e.g., "1m30s", "90") and will be converted to seconds.
        - **Frame Rate**: Can be specified in two ways (if both are present,
          `interval` takes precedence):
          - **Interval**: `#interval=<value>` (e.g., `#interval=10s`, `#interval=0.5s`).
            The value is a flexible duration converted to seconds, then to FPS (1/interval).
          - **FPS**: `#fps=<value>` (e.g., `#fps=2.5`).
          The final FPS value must be in the range (0, 24].

        Args:
            uri: The raw YouTube URL from the user.
            is_vertex_client: If True, creates a simple Part for Vertex AI.

        Returns:
            A `types.Part` object, or `None` if the URI is not a valid YouTube link.
        """
        # Convert YouTube Music URLs to standard YouTube URLs for consistent parsing.
        if "music.youtube.com" in uri:
            uri = uri.replace("music.youtube.com", "www.youtube.com")
            log.info(f"Converted YouTube Music URL to standard URL: {uri}")

        # Regex to capture the 11-character video ID from various YouTube URL formats.
        video_id_pattern = re.compile(
            r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu.be/)([a-zA-Z0-9_-]{11})"
        )

        match = video_id_pattern.search(uri)
        if not match:
            log.warning(f"Could not extract a valid YouTube video ID from URI: {uri}")
            return None

        video_id = match.group(1)
        canonical_uri = f"https://www.youtube.com/watch?v={video_id}"

        # --- Branching logic for Vertex AI vs. Gemini Developer API ---
        if self.vertexai:
            return types.Part.from_uri(file_uri=canonical_uri, mime_type="video/mp4")
        else:
            parsed_uri = urlparse(uri)
            query_params = parse_qs(parsed_uri.query)
            fragment_params = parse_qs(parsed_uri.fragment)

            start_offset: str | None = None
            end_offset: str | None = None
            fps: float | None = None

            # Start time from query `t`. Convert flexible format to "Ns".
            if "t" in query_params:
                raw_start = query_params["t"][0]
                if (
                    total_seconds := self._parse_duration_to_seconds(raw_start)
                ) is not None:
                    start_offset = f"{total_seconds}s"

            # End time from fragment `end`. Convert flexible format to "Ns".
            if "end" in fragment_params:
                raw_end = fragment_params["end"][0]
                if (
                    total_seconds := self._parse_duration_to_seconds(raw_end)
                ) is not None:
                    end_offset = f"{total_seconds}s"

            # Frame rate from fragment `interval` or `fps`. `interval` takes precedence.
            if "interval" in fragment_params:
                raw_interval = fragment_params["interval"][0]
                if (
                    interval_seconds := self._parse_duration_to_seconds(raw_interval)
                ) is not None and interval_seconds > 0:
                    calculated_fps = 1.0 / interval_seconds
                    if 0.0 < calculated_fps <= 24.0:
                        fps = calculated_fps
                    else:
                        log.warning(
                            f"Interval '{raw_interval}' results in FPS '{calculated_fps}' which is outside the valid range (0.0, 24.0]. Ignoring."
                        )

            # Fall back to `fps` param if not set by `interval`.
            if fps is None and "fps" in fragment_params:
                try:
                    fps_val = float(fragment_params["fps"][0])
                    if 0.0 < fps_val <= 24.0:
                        fps = fps_val
                    else:
                        log.warning(
                            f"FPS value '{fps_val}' is outside the valid range (0.0, 24.0]. Ignoring."
                        )
                except (ValueError, IndexError):
                    log.warning(
                        f"Invalid FPS value in fragment: {fragment_params.get('fps')}. Ignoring."
                    )

            video_metadata: types.VideoMetadata | None = None
            if start_offset or end_offset or fps is not None:
                video_metadata = types.VideoMetadata(
                    start_offset=start_offset,
                    end_offset=end_offset,
                    fps=fps,
                )

            return types.Part(
                file_data=types.FileData(file_uri=canonical_uri),
                video_metadata=video_metadata,
            )

    def _parse_duration_to_seconds(self, duration_str: str) -> float | None:
        """Converts a human-readable duration string to total seconds.

        Supports formats like "1h30m15s", "90m", "3600s", or just "90".
        Also supports float values like "0.5s" or "90.5".
        Returns total seconds as a float, or None if the string is invalid.
        """
        # First, try to convert the whole string as a plain number (e.g., "90", "90.5").
        try:
            return float(duration_str)
        except ValueError:
            # If it fails, it might be a composite duration like "1m30s", so we parse it below.
            pass

        total_seconds = 0.0
        # Regex to find number-unit pairs (e.g., 1h, 30.5m, 15s). Supports floats.
        parts = re.findall(r"(\d+(?:\.\d+)?)\s*(h|m|s)?", duration_str, re.IGNORECASE)

        if not parts:
            # log.warning(f"Could not parse duration string: {duration_str}")
            return None

        for value, unit in parts:
            val = float(value)
            unit = (unit or "s").lower()  # Default to seconds if no unit
            if unit == "h":
                total_seconds += val * 3600
            elif unit == "m":
                total_seconds += val * 60
            elif unit == "s":
                total_seconds += val

        return total_seconds

    @staticmethod
    def _enable_special_tags(text: str) -> str:
        """
        Reverses the action of _disable_special_tags by removing the ZWS
        from special tags. This is used to clean up history messages before
        sending them to the model, so it can understand the context correctly.
        """
        if not text:
            return ""

        # The regex finds '<ZWS' followed by an optional '/' and then one of the special tags.
        # The inner parentheses group the tags, so the optional '/' applies to all of them.
        REVERSE_TAG_REGEX = re.compile(
            r"<"
            + ZWS
            + r"(/?"
            + "("
            + "|".join(re.escape(tag) for tag in SPECIAL_TAGS_TO_DISABLE)
            + ")"
            + r")"
        )
        # The substitution restores the original tag, e.g., '<ZWS/think' becomes '</think'.
        restored_text, count = REVERSE_TAG_REGEX.subn(r"<\1", text)
        if count > 0:
            log.debug(f"Re-enabled {count} special tag(s) for model context.")

        return restored_text

    async def _genai_parts_from_text(
        self, text: str, status_queue: asyncio.Queue
    ) -> list[types.Part]:
        if not text:
            return []

        text = self._enable_special_tags(text)
        parts: list[types.Part] = []
        last_pos = 0

        # Conditionally build a regex to find media links.
        # If YouTube parsing is disabled, the regex will only find markdown image links,
        # leaving YouTube URLs to be treated as plain text.
        markdown_part = r"!\[.*?\]\(([^)]+)\)"  # Group 1: Markdown URI
        youtube_part = r"(https?://(?:(?:www|music)\.)?youtube\.com/(?:watch\?v=|shorts/|live/)[^\s)]+|https?://youtu\.be/[^\s)]+)"  # Group 2: YouTube URL
        if self.valves.PARSE_YOUTUBE_URLS:
            pattern = re.compile(f"{markdown_part}|{youtube_part}")
            process_youtube = True
        else:
            pattern = re.compile(markdown_part)
            process_youtube = False
            log.info(
                "YouTube URL parsing is disabled. URLs will be treated as plain text."
            )

        for match in pattern.finditer(text):
            # Add the text segment that precedes the media link
            if text_segment := text[last_pos : match.start()].strip():
                parts.append(types.Part.from_text(text=text_segment))

            # The URI is in group 1 for markdown, or group 2 for YouTube.
            if process_youtube:
                uri = match.group(1) or match.group(2)
            else:
                uri = match.group(1)

            if not uri:
                log.warning(
                    f"Found unsupported URI format in text: {match.group(0)}. Skipping."
                )
                continue

            # Delegate all URI processing to the unified helper
            if media_part := await self._genai_part_from_uri(uri, status_queue):
                parts.append(media_part)

            last_pos = match.end()

        # Add any remaining text after the last media link
        if remaining_text := text[last_pos:].strip():
            parts.append(types.Part.from_text(text=remaining_text))

        # If no media links were found, the whole text is a single part
        if not parts and text.strip():
            parts.append(types.Part.from_text(text=text.strip()))

        return parts

    @staticmethod
    async def _get_file_data(file_id: str) -> tuple[bytes | None, str | None]:
        """
        Asynchronously retrieves file metadata from the database and its content from disk.
        """
        # TODO: Emit toasts on unexpected conditions.
        if not file_id:
            log.warning("file_id is empty. Cannot continue.")
            return None, None

        # Run the synchronous, blocking database call in a separate thread
        # to avoid blocking the main asyncio event loop.
        try:
            file_model = await asyncio.to_thread(Files.get_file_by_id, file_id)
        except Exception as e:
            log.exception(
                f"An unexpected error occurred during database call for file_id {file_id}: {e}"
            )
            return None, None

        if file_model is None:
            # The get_file_by_id method already handles and logs the specific exception,
            # so we just need to handle the None return value.
            log.warning(f"File {file_id} not found in the backend's database.")
            return None, None

        if not (file_path := file_model.path):
            log.warning(
                f"File {file_id} was found in the database but it lacks `path` field. Cannot Continue."
            )
            return None, None
        if file_model.meta is None:
            log.warning(
                f"File {file_path} was found in the database but it lacks `meta` field. Cannot continue."
            )
            return None, None
        if not (content_type := file_model.meta.get("content_type")):
            log.warning(
                f"File {file_path} was found in the database but it lacks `meta.content_type` field. Cannot continue."
            )
            return None, None

        if file_path.startswith("gs://"):
            try:
                # Initialize the GCS client
                storage_client = storage.Client()

                # Parse the GCS path
                # The path should be in the format "gs://bucket-name/object-name"
                if len(file_path.split("/", 3)) < 4:
                    raise ValueError(
                        f"Invalid GCS path: '{file_path}'. "
                        "Path must be in the format 'gs://bucket-name/object-name'."
                    )

                bucket_name, blob_name = file_path.removeprefix("gs://").split("/", 1)

                # Get the bucket and blob (file object)
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)

                # Download the file's content as bytes
                print(f"Reading from GCS: {file_path}")
                return blob.download_as_bytes(), content_type
            except exceptions.NotFound:
                print(f"Error: GCS object not found at {file_path}")
                raise
            except Exception as e:
                print(f"An error occurred while reading from GCS: {e}")
                raise
        try:
            async with aiofiles.open(file_path, "rb") as file:
                file_data = await file.read()
            return file_data, content_type
        except FileNotFoundError:
            log.exception(f"File {file_path} not found on disk.")
            return None, content_type
        except Exception:
            log.exception(f"Error processing file {file_path}")
            return None, content_type

    @staticmethod
    def _remove_citation_markers(text: str, sources: list["Source"]) -> str:
        original_text = text
        processed: set[str] = set()
        for source in sources:
            supports = [
                metadata["supports"]
                for metadata in source.get("metadata", [])
                if "supports" in metadata
            ]
            supports = [item for sublist in supports for item in sublist]
            for support in supports:
                support = types.GroundingSupport(**support)
                indices = support.grounding_chunk_indices
                segment = support.segment
                if not (indices and segment):
                    continue
                segment_text = segment.text
                if not segment_text:
                    continue
                # Using a shortened version because user could edit the assistant message in the front-end.
                # If citation segment get's edited, then the markers would not be removed. Shortening reduces the
                # chances of this happening.
                segment_end = segment_text[-32:]
                if segment_end in processed:
                    continue
                processed.add(segment_end)
                citation_markers = "".join(f"[{index + 1}]" for index in indices)
                # Find the position of the citation markers in the text
                pos = text.find(segment_text + citation_markers)
                if pos != -1:
                    # Remove the citation markers
                    text = (
                        text[: pos + len(segment_text)]
                        + text[pos + len(segment_text) + len(citation_markers) :]
                    )
        trim = len(original_text) - len(text)
        log.debug(
            f"Citation removal finished. Returning text str that is {trim} character shorter than the original input."
        )
        return text


class Pipe:

    @staticmethod
    def _validate_coordinates_format(v: str | None) -> str | None:
        """Reusable validator for 'latitude,longitude' format."""
        if v is not None and v != "":
            try:
                parts = v.split(",")
                if len(parts) != 2:
                    raise ValueError(
                        "Must contain exactly two parts separated by a comma."
                    )

                lat_str, lon_str = parts
                lat = float(lat_str.strip())
                lon = float(lon_str.strip())

                if not (-90 <= lat <= 90):
                    raise ValueError("Latitude must be between -90 and 90.")
                if not (-180 <= lon <= 180):
                    raise ValueError("Longitude must be between -180 and 180.")
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid format for MAPS_GROUNDING_COORDINATES: '{v}'. "
                    f"Expected 'latitude,longitude' (e.g., '40.7128,-74.0060'). Original error: {e}"
                )
        return v

    class Valves(BaseModel):
        GEMINI_API_KEY: str | None = Field(default=None)
        IMAGE_GEN_GEMINI_API_KEY: str | None = Field(
            default=None,
            description="""Optional separate API key for image generation models.
            If not provided, the main GEMINI_API_KEY will be used.
            An image generation model is identified by the Image Model Pattern regex below.""",
        )
        USER_MUST_PROVIDE_AUTH_CONFIG: bool = Field(
            default=False,
            description="""Whether to require users (including admins) to provide their own authentication configuration.
            User can provide these through UserValves. Setting this to True will disallow users from using Vertex AI.
            Default value is False.""",
        )
        AUTH_WHITELIST: str | None = Field(
            default=None,
            description="""Comma separated list of user emails that are allowed to bypassUSER_MUST_PROVIDE_AUTH_CONFIG and use the default authentication configuration.
            Default value is None (no users are whitelisted).""",
        )
        GEMINI_API_BASE_URL: str | None = Field(
            default=None,
            description="""The base URL for calling the Gemini API.
            Default value is None.""",
        )
        USE_VERTEX_AI: bool = Field(
            default=False,
            description="""Whether to use Google Cloud Vertex AI instead of the standard Gemini API.
            If VERTEX_PROJECT is not set then the plugin will use the Gemini Developer API.
            Default value is False.
            Users can opt out of this by setting USE_VERTEX_AI to False in their UserValves.""",
        )
        VERTEX_PROJECT: str | None = Field(
            default=None,
            description="""The Google Cloud project ID to use with Vertex AI.
            Default value is None.""",
        )
        VERTEX_LOCATION: str = Field(
            default="global",
            description="""The Google Cloud region to use with Vertex AI.
            Default value is 'global'.""",
        )
        MODEL_WHITELIST: str = Field(
            default="*",
            description="""Comma-separated list of allowed model names.
            Supports `fnmatch` patterns: *, ?, [seq], [!seq].
            Default value is * (all models allowed).""",
        )
        MODEL_BLACKLIST: str | None = Field(
            default=None,
            description="""Comma-separated list of blacklisted model names.
            Supports `fnmatch` patterns: *, ?, [seq], [!seq].
            Default value is None (no blacklist).""",
        )
        CACHE_MODELS: bool = Field(
            default=True,
            description="""Whether to request models only on first load and when white- or blacklist changes.
            Default value is True.""",
        )
        THINKING_BUDGET: int = Field(
            default=8192,
            ge=-1,
            # The widest possible range is 0 (for Lite/Flash) to 32768 (for Pro).
            # -1 is used for dynamic thinking budget.
            # Model-specific constraints are detailed in the description.
            le=32768,
            description="""Specifies the token budget for the model's internal thinking process,
            used for complex tasks like tool use. Applicable to Gemini 2.5 models.
            Default value is 8192. If you want the model to control the thinking budget when using the API, set the thinking budget to -1.

            The valid token range depends on the specific model tier:
            - **Pro models**: Must be a value between 128 and 32,768.
            - **Flash and Lite models**: A value between 0 and 24,576. For these
              models, a value of 0 disables the thinking feature.

            See <https://cloud.google.com/vertex-ai/generative-ai/docs/thinking> for more details.""",
        )
        SHOW_THINKING_SUMMARY: bool = Field(
            default=True,
            description="""Whether to show the thinking summary in the response.
            This is only applicable for Gemini 2.5 models.
            Default value is True.""",
        )
        THINKING_MODEL_PATTERN: str = Field(
            default=r"^(?=.*(?:gemini-2\.5|gemini-flash-latest|gemini-flash-lite-latest))(?!(.*live))(?!(.*image))",
            description="""Regex pattern to identify thinking models.
            Default value is r"^(?=.*(?:gemini-2\.5|gemini-flash-latest|gemini-flash-lite-latest))(?!(.*live))(?!(.*image))".""",
        )
        IMAGE_MODEL_PATTERN: str = Field(
            default=r"image",
            description="""Regex pattern to identify image generation models.
            Default value is r"image".""",
        )
        # FIXME: remove
        ENABLE_URL_CONTEXT_TOOL: bool = Field(
            default=False,
            description="""Enable the URL context tool to allow the model to fetch and use content from provided URLs.
            This tool is only compatible with specific models. Default value is False.""",
        )
        USE_FILES_API: bool = Field(
            default=True,
            description="""Whether to use the Google Files API for uploading files.
            This provides caching and performance benefits, but can be disabled for privacy, cost, or compatibility reasons.
            If disabled, files are sent as raw bytes in the request.
            Default value is True.""",
        )
        PARSE_YOUTUBE_URLS: bool = Field(
            default=True,
            description="""Whether to parse YouTube URLs from user messages and provide them as context to the model.
            If disabled, YouTube links are treated as plain text.
            This is only applicable for models that support video.
            Default value is True.""",
        )
        USE_ENTERPRISE_SEARCH: bool = Field(
            default=False,
            description="""Enable the Enterprise Search tool to allow the model to fetch and use content from provided URLs. """,
        )
        MAPS_GROUNDING_COORDINATES: str | None = Field(
            default=None,
            description="""Optional latitude and longitude coordinates for location-aware results with Google Maps grounding.
            Expected format: 'latitude,longitude' (e.g., '40.7128,-74.0060').
            Default value is None.""",
        )
        HIDE_SUCCESSFUL_STATUS_MESSAGE: bool = Field(
            default=False,
            description="""Whether to hide the final 'Response finished' status message on success.
            Error messages will always be shown.
            Default value is False.""",
        )
        LOG_LEVEL: Literal[
            "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
        ] = Field(
            default="INFO",
            description="""Select logging level. Use `docker logs -f open-webui` to view logs.
            Default value is INFO.""",
        )

        @field_validator("MAPS_GROUNDING_COORDINATES", mode="after")
        @classmethod
        def validate_coordinates_format(cls, v: str | None):
            return Pipe._validate_coordinates_format(v)

    class UserValves(BaseModel):
        """Defines user-specific settings that can override the default `Valves`.

        The `UserValves` class provides a mechanism for individual users to customize
        their Gemini API settings for each request. This system is designed as a
        practical workaround for backend/frontend limitations, enabling per-user
        configurations.

        Think of the main `Valves` as the global, admin-configured template for the
        plugin. `UserValves` acts as a user-provided "overlay" or "patch" that
        is applied on top of that template at runtime.

        How it works:
        1.  **Default Behavior:** At the start of a request, the system merges the
            user's `UserValves` with the admin's `Valves`. If a field in
            `UserValves` has a value (i.e., is not `None` or an empty string `""`),
            it overrides the corresponding value from the main `Valves`. If a
            field is `None` or `""`, the admin's default is used.

        2.  **Special Authentication Logic:** A critical exception exists to enforce
            security and usage policies. If the admin sets `USER_MUST_PROVIDE_AUTH_CONFIG`
            to `True` in the main `Valves`, the merging logic changes for any user
            not on the `AUTH_WHITELIST`:
            - The user's `GEMINI_API_KEY` is taken directly from their `UserValves`,
              bypassing the admin's key entirely.
            - The ability to use the admin-configured Vertex AI is disabled
              (`USE_VERTEX_AI` is forced to `False`).
            This ensures that when required, users must use their own credentials
            and cannot fall back on the shared, system-level authentication.

        This two-tiered configuration allows administrators to set sensible defaults
        and enforce policies, while still giving users the flexibility to tailor
        certain parameters, like their API key or model settings, for their own use.
        """

        GEMINI_API_KEY: str | None = Field(
            default=None,
            description="""Gemini Developer API key.
            Default value is None (uses the default from Valves, same goes for other options below).""",
        )
        IMAGE_GEN_GEMINI_API_KEY: str | None = Field(
            default=None,
            description="""Optional separate API key for image generation models.
            If not provided, the main GEMINI_API_KEY will be used.""",
        )
        GEMINI_API_BASE_URL: str | None = Field(
            default=None,
            description="""The base URL for calling the Gemini API
            Default value is None.""",
        )
        USE_VERTEX_AI: bool | None | Literal[""] = Field(
            default=None,
            description="""Whether to use Google Cloud Vertex AI instead of the standard Gemini API.
            Default value is None.""",
        )
        VERTEX_PROJECT: str | None = Field(
            default=None,
            description="""The Google Cloud project ID to use with Vertex AI.
            Default value is None.""",
        )
        VERTEX_LOCATION: str | None = Field(
            default=None,
            description="""The Google Cloud region to use with Vertex AI.
            Default value is None.""",
        )
        THINKING_BUDGET: int | None | Literal[""] = Field(
            default=None,
            description="""Specifies the token budget for the model's internal thinking process,
            used for complex tasks like tool use. Applicable to Gemini 2.5 models.
            Default value is None. If you want the model to control the thinking budget when using the API, set the thinking budget to -1.

            The valid token range depends on the specific model tier:
            - **Pro models**: Must be a value between 128 and 32,768.
            - **Flash and Lite models**: A value between 0 and 24,576. For these
              models, a value of 0 disables the thinking feature.

            See <https://cloud.google.com/vertex-ai/generative-ai/docs/thinking> for more details.""",
        )
        SHOW_THINKING_SUMMARY: bool | None | Literal[""] = Field(
            default=None,
            description="""Whether to show the thinking summary in the response.
            This is only applicable for Gemini 2.5 models.
            Default value is None.""",
        )
        THINKING_MODEL_PATTERN: str | None = Field(
            default=None,
            description="""Regex pattern to identify thinking models.
            Default value is None.""",
        )
        ENABLE_URL_CONTEXT_TOOL: bool | None | Literal[""] = Field(
            default=None,
            description="""Enable the URL context tool to allow the model to fetch and use content from provided URLs.
            This tool is only compatible with specific models. Default value is None.""",
        )
        USE_FILES_API: bool | None | Literal[""] = Field(
            default=None,
            description="""Override the default setting for using the Google Files API.
            Set to True to force use, False to disable.
            Default is None (use the admin's setting).""",
        )
        PARSE_YOUTUBE_URLS: bool | None | Literal[""] = Field(
            default=None,
            description="""Override the default setting for parsing YouTube URLs.
            Set to True to enable, False to disable.
            Default is None (use the admin's setting).""",
        )
        MAPS_GROUNDING_COORDINATES: str | None | Literal[""] = Field(
            default=None,
            description="""Optional latitude and longitude coordinates for location-aware results with Google Maps grounding.
            Overrides the admin setting. Expected format: 'latitude,longitude' (e.g., '40.7128,-74.0060').
            Default value is None.""",
        )
        HIDE_SUCCESSFUL_STATUS_MESSAGE: bool | None | Literal[""] = Field(
            default=None,
            description="""Override the default setting for hiding the successful status message.
            Set to True to hide, False to show.
            Default is None (use the admin's setting).""",
        )

        @field_validator("THINKING_BUDGET", mode="after")
        @classmethod
        def validate_thinking_budget_range(cls, v):
            if v is not None and v != "":
                if not (-1 <= v <= 32768):
                    raise ValueError(
                        "THINKING_BUDGET must be between -1 and 32768, inclusive."
                    )
            return v

        @field_validator("MAPS_GROUNDING_COORDINATES", mode="after")
        @classmethod
        def validate_coordinates_format(cls, v: str | None):
            return Pipe._validate_coordinates_format(v)

    def __init__(self):
        self.valves = self.Valves()
        self.file_content_cache = SimpleMemoryCache(serializer=NullSerializer())
        self.file_id_to_hash_cache = SimpleMemoryCache(serializer=NullSerializer())
        log.success("Function has been initialized.")

    async def pipes(self) -> list["ModelData"]:
        """Register all available Google models."""
        self._add_log_handler(self.valves.LOG_LEVEL)
        log.debug("pipes method has been called.")

        # Clear cache if caching is disabled
        if not self.valves.CACHE_MODELS:
            log.debug("CACHE_MODELS is False, clearing model cache.")
            cache_instance = getattr(self._get_genai_models, "cache")
            await cast(BaseCache, cache_instance).clear()

        log.info("Fetching and filtering models from Google API.")
        # Get and filter models (potentially cached based on API key, base URL, white- and blacklist)
        try:
            client_args = self._prepare_client_args(self.valves)
            client_args += [self.valves.MODEL_WHITELIST, self.valves.MODEL_BLACKLIST]
            filtered_models = await self._get_genai_models(*client_args)
        except GenaiApiError:
            error_msg = "Error getting the models from Google API, check the logs."
            return [self._return_error_model(error_msg, exception=True)]

        log.info(f"Returning {len(filtered_models)} models to Open WebUI.")
        log.debug("Model list:", payload=filtered_models, _log_truncation_enabled=False)
        log.debug("pipes method has finished.")

        return filtered_models

    async def pipe(
        self,
        body: "Body",
        __user__: "UserData",
        __request__: Request,
        __event_emitter__: Callable[["Event"], Awaitable[None]] | None,
        __metadata__: "Metadata",
    ) -> AsyncGenerator[dict, None] | str:

        start_time = time.monotonic()
        self._add_log_handler(self.valves.LOG_LEVEL)

        log.debug(
            f"pipe method has been called. Gemini Manifold google_genai version is {VERSION}"
        )
        log.trace("__metadata__:", payload=__metadata__)
        features = __metadata__.get("features", {}) or {}

        # Check the version of the companion filter
        self._check_companion_filter_version(features)

        # Apply settings from the user
        valves: Pipe.Valves = self._get_merged_valves(
            self.valves, __user__.get("valves"), __user__.get("email")
        )

        model_name = re.sub(r"^.*?[./]", "", body.get("model", ""))
        is_image_model = self._is_image_model(model_name, valves.IMAGE_MODEL_PATTERN)

        if is_image_model and valves.IMAGE_GEN_GEMINI_API_KEY:
            log.info("Using separate API key for image generation model.")
            valves.GEMINI_API_KEY = valves.IMAGE_GEN_GEMINI_API_KEY

            # When using a separate key, assume it's for Gemini API, not Vertex AI
            # TODO: check if it would work for Vertex AI as well
            valves.USE_VERTEX_AI = False
            valves.VERTEX_PROJECT = None

        log.debug(
            f"USE_VERTEX_AI: {valves.USE_VERTEX_AI}, VERTEX_PROJECT set: {bool(valves.VERTEX_PROJECT)}, API_KEY set: {bool(valves.GEMINI_API_KEY)}"
        )

        log.debug(
            f"Getting genai client (potentially cached) for user {__user__['email']}."
        )
        client = self._get_user_client(valves, __user__["email"])
        __metadata__["is_vertex_ai"] = client.vertexai

        if __metadata__.get("task"):
            log.info(f'{__metadata__["task"]=}, disabling event emissions.') # type: ignore
            # Task model is not user facing, so we should not emit any events.
            __event_emitter__ = None

        event_emitter = EventEmitter(
            __event_emitter__,
            hide_successful_status=valves.HIDE_SUCCESSFUL_STATUS_MESSAGE,
        )

        files_api_manager = FilesAPIManager(
            client=client,
            file_cache=self.file_content_cache,
            id_hash_cache=self.file_id_to_hash_cache,
            event_emitter=event_emitter,
        )

        # Check if user is chatting with an error model for some reason.
        if "error" in __metadata__["model"]["id"]:
            error_msg = f"There has been an error during model retrival phase: {str(__metadata__['model'])}"
            raise ValueError(error_msg)

        # NOTE: will be "local" if Temporary Chat is enabled.
        chat_id = __metadata__.get("chat_id", "not_provided")
        message_id = __metadata__.get("message_id", "not_provided")

        log.info(
            "Converting Open WebUI's `body` dict into list of `Content` objects that `google-genai` understands."
        )

        builder = GeminiContentBuilder(
            messages_body=body.get("messages"),
            metadata_body=__metadata__,
            user_data=__user__,
            event_emitter=event_emitter,
            valves=valves,
            files_api_manager=files_api_manager,
        )
        # This is our first timed event, marking the start of payload preparation.
        asyncio.create_task(event_emitter.emit_status("Preparing request..."))
        contents = await builder.build_contents(start_time=start_time)

        gen_content_conf = self._build_gen_content_config(body, __metadata__, valves)
        gen_content_conf.system_instruction = builder.system_prompt

        # Some models (e.g., image generation, Gemma) do not support the system prompt message.
        system_prompt_unsupported = is_image_model or "gemma" in model_name
        if system_prompt_unsupported:
            # TODO: append to user message instead.
            if gen_content_conf.system_instruction:
                gen_content_conf.system_instruction = None
                log.warning(
                    f"Model '{model_name}' does not support the system prompt message! Removing the system prompt."
                )

        gen_content_args = {
            "model": model_name,
            "contents": contents,
            "config": gen_content_conf,
        }
        log.debug("Passing these args to the Google API:", payload=gen_content_args)

        # Both streaming and non-streaming responses are now handled by the same
        # unified processor, which returns an AsyncGenerator. For non-streaming,
        # we adapt the single response object into a one-item async generator.

        elapsed_time = time.monotonic() - start_time
        time_str = f"(+{elapsed_time:.2f}s)"

        # Determine the request type to provide a more informative status message.
        is_streaming = features.get("stream", True)
        request_type_str = "streaming" if is_streaming else "non-streaming"

        # Emit a status update with timing before making the actual API call.
        asyncio.create_task(event_emitter.emit_status(f"Sending {request_type_str} request to Google API... {time_str}"))

        if is_streaming:
            # Streaming response
            response_stream: AsyncIterator[types.GenerateContentResponse] = (
                await client.aio.models.generate_content_stream(**gen_content_args)  # type: ignore
            )

            log.info(
                "Streaming enabled. Returning AsyncGenerator from unified processor."
            )
            log.debug("pipe method has finished.")
            return self._unified_response_processor(
                response_stream,
                __request__,
                model_name,
                event_emitter,
                __user__["id"],
                chat_id,
                message_id,
                start_time=start_time,
            )
        else:
            # Non-streaming response.
            res = await client.aio.models.generate_content(**gen_content_args)

            # Adapter: Create a simple, one-shot async generator that yields the
            # single response object, making it behave like a stream.
            async def single_item_stream(
                response: types.GenerateContentResponse,
            ) -> AsyncGenerator[types.GenerateContentResponse, None]:
                yield response

            log.info(
                "Streaming disabled. Adapting full response and returning "
                "AsyncGenerator from unified processor."
            )
            log.debug("pipe method has finished.")
            return self._unified_response_processor(
                single_item_stream(res),
                __request__,
                model_name,
                event_emitter,
                __user__["id"],
                chat_id,
                message_id,
                start_time=start_time,
            )

    # region 2. Helper methods inside the Pipe class

    # region 2.1 Client initialization
    @staticmethod
    @cache
    def _get_or_create_genai_client(
        api_key: str | None = None,
        base_url: str | None = None,
        use_vertex_ai: bool | None = None,
        vertex_project: str | None = None,
        vertex_location: str | None = None,
    ) -> genai.Client:
        """
        Creates a genai.Client instance or retrieves it from cache.
        Raises GenaiApiError on failure.
        """

        if not vertex_project and not api_key:
            # FIXME: More detailed reason in the exception (tell user to set the API key).
            msg = "Neither VERTEX_PROJECT nor GEMINI_API_KEY is set."
            raise GenaiApiError(msg)

        if use_vertex_ai and vertex_project:
            kwargs = {
                "vertexai": True,
                "project": vertex_project,
                "location": vertex_location,
            }
            api = "Vertex AI"
        else:  # Covers (use_vertex_ai and not vertex_project) OR (not use_vertex_ai)
            if use_vertex_ai and not vertex_project:
                log.warning(
                    "Vertex AI is enabled but no project is set. "
                    "Using Gemini Developer API."
                )
            # This also implicitly covers the case where api_key might be None,
            # which is handled by the initial check or the SDK.
            kwargs = {
                "api_key": api_key,
                "http_options": types.HttpOptions(base_url=base_url),
            }
            api = "Gemini Developer API"

        try:
            client = genai.Client(**kwargs)
            log.success(f"{api} Genai client successfully initialized.")
            return client
        except Exception as e:
            raise GenaiApiError(f"{api} Genai client initialization failed: {e}") from e

    def _get_user_client(self, valves: "Pipe.Valves", user_email: str) -> genai.Client:
        user_whitelist = (
            valves.AUTH_WHITELIST.split(",") if valves.AUTH_WHITELIST else []
        )
        log.debug(
            f"User whitelist: {user_whitelist}, user email: {user_email}, "
            f"USER_MUST_PROVIDE_AUTH_CONFIG: {valves.USER_MUST_PROVIDE_AUTH_CONFIG}"
        )
        if valves.USER_MUST_PROVIDE_AUTH_CONFIG and user_email not in user_whitelist:
            if not valves.GEMINI_API_KEY:
                error_msg = (
                    "User must provide their own authentication configuration. "
                    "Please set GEMINI_API_KEY in your UserValves."
                )
                raise ValueError(error_msg)
        try:
            client_args = self._prepare_client_args(valves)
            client = self._get_or_create_genai_client(*client_args)
        except GenaiApiError as e:
            error_msg = f"Failed to initialize genai client for user {user_email}: {e}"
            # FIXME: include correct traceback.
            raise ValueError(error_msg) from e
        return client

    @staticmethod
    def _prepare_client_args(
        source_valves: "Pipe.Valves | Pipe.UserValves",
    ) -> list[str | bool | None]:
        """Prepares arguments for _get_or_create_genai_client from source_valves."""
        ATTRS = [
            "GEMINI_API_KEY",
            "GEMINI_API_BASE_URL",
            "USE_VERTEX_AI",
            "VERTEX_PROJECT",
            "VERTEX_LOCATION",
        ]
        return [getattr(source_valves, attr) for attr in ATTRS]

    # endregion 2.1 Client initialization

    # region 2.2 Model retrival from Google API
    @cached()  # aiocache.cached for async method
    async def _get_genai_models(
        self,
        api_key: str | None,
        base_url: str | None,
        use_vertex_ai: bool | None,  # User's preference from config
        vertex_project: str | None,
        vertex_location: str | None,
        whitelist_str: str,
        blacklist_str: str | None,
    ) -> list["ModelData"]:
        """
        Gets valid Google models from API(s) and filters them.
        If use_vertex_ai, vertex_project, and api_key are all provided,
        models are fetched from both Vertex AI and Gemini Developer API and merged.
        """
        all_raw_models: list[types.Model] = []

        # Condition for fetching from both sources
        fetch_both = bool(use_vertex_ai and vertex_project and api_key)

        if fetch_both:
            log.info(
                "Attempting to fetch models from both Gemini Developer API and Vertex AI."
            )
            gemini_models_list: list[types.Model] = []
            vertex_models_list: list[types.Model] = []

            # TODO: perf, consider parallelizing these two fetches
            # 1. Fetch from Gemini Developer API
            try:
                gemini_client = self._get_or_create_genai_client(
                    api_key=api_key,
                    base_url=base_url,
                    use_vertex_ai=False,  # Explicitly target Gemini API
                    vertex_project=None,
                    vertex_location=None,
                )
                gemini_models_list = await self._fetch_models_from_client_internal(
                    gemini_client, "Gemini Developer API"
                )
            except GenaiApiError as e:
                log.warning(
                    f"Failed to initialize or retrieve models from Gemini Developer API: {e}"
                )
            except Exception as e:
                log.warning(
                    f"An unexpected error occurred with Gemini Developer API models: {e}",
                    exc_info=True,
                )

            # 2. Fetch from Vertex AI
            try:
                vertex_client = self._get_or_create_genai_client(
                    use_vertex_ai=True,  # Explicitly target Vertex AI
                    vertex_project=vertex_project,
                    vertex_location=vertex_location,
                    api_key=None,  # API key is not used for Vertex AI with project auth
                    base_url=base_url,  # Pass base_url for potential Vertex custom endpoints
                )
                vertex_models_list = await self._fetch_models_from_client_internal(
                    vertex_client, "Vertex AI"
                )
            except GenaiApiError as e:
                log.warning(
                    f"Failed to initialize or retrieve models from Vertex AI: {e}"
                )
            except Exception as e:
                log.warning(
                    f"An unexpected error occurred with Vertex AI models: {e}",
                    exc_info=True,
                )

            # 3. Combine and de-duplicate
            # Prioritize models from Gemini Developer API in case of ID collision
            combined_models_dict: dict[str, types.Model] = {}

            for model in gemini_models_list:
                if model.name:
                    model_id = Pipe.strip_prefix(model.name)
                    if model_id and model_id not in combined_models_dict:
                        combined_models_dict[model_id] = model
                else:
                    log.trace(
                        f"Gemini model without a name encountered: {model.display_name or 'N/A'}"
                    )

            for model in vertex_models_list:
                if model.name:
                    model_id = Pipe.strip_prefix(model.name)
                    if model_id:
                        if model_id not in combined_models_dict:
                            combined_models_dict[model_id] = model
                        else:
                            log.info(
                                f"Duplicate model ID '{model_id}' from Vertex AI already sourced from Gemini API. Keeping Gemini API version."
                            )
                else:
                    log.trace(
                        f"Vertex AI model without a name encountered: {model.display_name or 'N/A'}"
                    )

            all_raw_models = list(combined_models_dict.values())

            log.info(
                f"Fetched {len(gemini_models_list)} models from Gemini API, "
                f"{len(vertex_models_list)} from Vertex AI. "
                f"Combined to {len(all_raw_models)} unique models."
            )

            if not all_raw_models and (gemini_models_list or vertex_models_list):
                log.warning(
                    "Models were fetched but resulted in an empty list after de-duplication, possibly due to missing names or empty/duplicate IDs."
                )

            if not all_raw_models and not gemini_models_list and not vertex_models_list:
                raise GenaiApiError(
                    "Failed to retrieve models: Both Gemini Developer API and Vertex AI attempts yielded no models."
                )

        else:  # Single source logic
            # Determine if we are effectively using Vertex AI or Gemini API
            # This depends on user's config (use_vertex_ai) and availability of project/key
            client_target_is_vertex = bool(use_vertex_ai and vertex_project)
            client_source_name = (
                "Vertex AI" if client_target_is_vertex else "Gemini Developer API"
            )
            log.info(
                f"Attempting to fetch models from a single source: {client_source_name}."
            )

            try:
                client = self._get_or_create_genai_client(
                    api_key=api_key,
                    base_url=base_url,
                    use_vertex_ai=client_target_is_vertex,  # Pass the determined target
                    vertex_project=vertex_project if client_target_is_vertex else None,
                    vertex_location=(
                        vertex_location if client_target_is_vertex else None
                    ),
                )
                all_raw_models = await self._fetch_models_from_client_internal(
                    client, client_source_name
                )

                if not all_raw_models:
                    raise GenaiApiError(
                        f"No models retrieved from {client_source_name}. This could be due to an API error, network issue, or no models being available."
                    )

            except GenaiApiError as e:
                raise GenaiApiError(
                    f"Failed to get models from {client_source_name}: {e}"
                ) from e
            except Exception as e:
                log.error(
                    f"An unexpected error occurred while configuring client or fetching models from {client_source_name}: {e}",
                    exc_info=True,
                )
                raise GenaiApiError(
                    f"An unexpected error occurred while retrieving models from {client_source_name}: {e}"
                ) from e

        # --- Common processing for all_raw_models ---

        if not all_raw_models:
            log.warning("No models available after attempting all configured sources.")
            return []

        log.info(f"Processing {len(all_raw_models)} unique raw models.")

        generative_models: list[types.Model] = []
        for model in all_raw_models:
            if model.name is None:
                log.trace(
                    f"Skipping model with no name during generative filter: {model.display_name or 'N/A'}"
                )
                continue
            actions = model.supported_actions
            if (
                actions is None or "generateContent" in actions
            ):  # Includes models if actions is None (e.g., Vertex)
                generative_models.append(model)
            else:
                log.trace(
                    f"Model '{model.name}' (ID: {Pipe.strip_prefix(model.name)}) skipped, not generative (actions: {actions})."
                )

        if not generative_models:
            log.warning(
                "No generative models found after filtering all retrieved models."
            )
            return []

        def match_patterns(
            name_to_check: str, list_of_patterns_str: str | None
        ) -> bool:
            if not list_of_patterns_str:
                return False
            patterns = [
                pat for pat in list_of_patterns_str.replace(" ", "").split(",") if pat
            ]  # Ensure pat is not empty
            return any(fnmatch.fnmatch(name_to_check, pat) for pat in patterns)

        filtered_models_data: list["ModelData"] = []
        for model in generative_models:
            # model.name is guaranteed non-None by generative_models filter logic
            stripped_name = Pipe.strip_prefix(model.name)  # type: ignore

            if not stripped_name:
                log.warning(
                    f"Model '{model.name}' (display: {model.display_name}) resulted in an empty ID after stripping. Skipping."
                )
                continue

            passes_whitelist = not whitelist_str or match_patterns(
                stripped_name, whitelist_str
            )
            passes_blacklist = not blacklist_str or not match_patterns(
                stripped_name, blacklist_str
            )

            if passes_whitelist and passes_blacklist:
                filtered_models_data.append(
                    {
                        "id": stripped_name,
                        "name": model.display_name or stripped_name,
                        "description": model.description,
                    }
                )
            else:
                log.trace(
                    f"Model ID '{stripped_name}' filtered out by whitelist/blacklist. Whitelist match: {passes_whitelist}, Blacklist pass: {passes_blacklist}"
                )

        log.info(
            f"Filtered {len(generative_models)} generative models down to {len(filtered_models_data)} models based on white/blacklists."
        )
        return filtered_models_data

    # TODO: Use cache for this method too?
    async def _fetch_models_from_client_internal(
        self, client: genai.Client, source_name: str
    ) -> list[types.Model]:
        """Helper to fetch models from a given client and handle common exceptions."""
        try:
            google_models_pager = await client.aio.models.list(
                config={"query_base": True}  # Fetch base models by default
            )
            models = [model async for model in google_models_pager]
            log.info(f"Retrieved {len(models)} models from {source_name}.")
            log.trace(
                f"All models returned by {source_name}:", payload=models
            )  # Can be verbose
            return models
        except Exception as e:
            log.error(f"Retrieving models from {source_name} failed: {e}")
            # Return empty list; caller decides if this is fatal for the whole operation.
            return []

    @staticmethod
    def _return_error_model(
        error_msg: str, warning: bool = False, exception: bool = True
    ) -> "ModelData":
        """Returns a placeholder model for communicating error inside the pipes method to the front-end."""
        if warning:
            log.opt(depth=1, exception=False).warning(error_msg)
        else:
            log.opt(depth=1, exception=exception).error(error_msg)
        return {
            "id": "error",
            "name": "[gemini_manifold] " + error_msg,
            "description": error_msg,
        }

    @staticmethod
    def strip_prefix(model_name: str) -> str:
        """
        Extract the model identifier using regex, handling various naming conventions.
        e.g., "gemini_manifold_google_genai.gemini-2.5-flash-preview-04-17" -> "gemini-2.5-flash-preview-04-17"
        e.g., "models/gemini-1.5-flash-001" -> "gemini-1.5-flash-001"
        e.g., "publishers/google/models/gemini-1.5-pro" -> "gemini-1.5-pro"
        """
        # Use regex to remove everything up to and including the last '/' or the first '.'
        stripped = re.sub(r"^(?:.*/|[^.]*\.)", "", model_name)
        return stripped

    @staticmethod
    def _is_image_model(model_name: str, pattern: str) -> bool:
        return bool(re.search(pattern, model_name, re.IGNORECASE))

    # endregion 2.2 Model retrival from Google API

    # region 2.3 GenerateContentConfig assembly

    def _build_gen_content_config(
        self,
        body: "Body",
        __metadata__: "Metadata",
        valves: "Valves",
    ) -> types.GenerateContentConfig:
        """Assembles the GenerateContentConfig for a Gemini API request."""
        model_name = re.sub(r"^.*?[./]", "", body.get("model", ""))
        features = __metadata__.get("features", {}) or {}
        is_vertex_ai = __metadata__.get("is_vertex_ai", False)

        log.debug(
            "Features extracted from metadata (UI toggles and config):",
            payload=features
        )

        safety_settings: list[types.SafetySetting] | None = __metadata__.get(
            "safety_settings"
        )

        thinking_conf = None
        # Use the user-configurable regex to determine if this is a thinking model.
        is_thinking_model = re.search(
            valves.THINKING_MODEL_PATTERN, model_name, re.IGNORECASE
        )
        log.debug(
            f"Model '{model_name}' is classified as a reasoning model: {bool(is_thinking_model)}. "
            f"Pattern: '{valves.THINKING_MODEL_PATTERN}'"
        )

        if is_thinking_model:
            # Start with the default thinking configuration from valves.
            log.info(f"Setting `thinking_budget` to {valves.THINKING_BUDGET} and `include_thoughts` to {valves.SHOW_THINKING_SUMMARY}.")
            thinking_conf = types.ThinkingConfig(
                thinking_budget=valves.THINKING_BUDGET,
                include_thoughts=valves.SHOW_THINKING_SUMMARY,
            )

            # Check if reasoning can be disabled. This happens if the toggle is available but turned OFF by the user.
            is_avail, is_on = self._get_toggleable_feature_status(
                "gemini_reasoning_toggle", __metadata__
            )
            if is_avail and not is_on:
                # This toggle is only applicable to flash/lite models, which support a budget of 0.
                is_reasoning_toggleable = "flash" in model_name or "lite" in model_name
                if is_reasoning_toggleable:
                    log.info(
                        f"Model '{model_name}' supports disabling reasoning, and it is toggled OFF in the UI. "
                        "Overwriting `thinking_budget` to 0 to disable reasoning."
                    )
                    thinking_conf.thinking_budget = 0

        # TODO: Take defaults from the general front-end config.
        # system_instruction is intentionally left unset here. It will be set by the caller.
        gen_content_conf = types.GenerateContentConfig(
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            top_k=body.get("top_k"),
            max_output_tokens=body.get("max_tokens"),
            stop_sequences=body.get("stop"),
            safety_settings=safety_settings,
            thinking_config=thinking_conf,
        )

        gen_content_conf.response_modalities = ["TEXT"]
        if self._is_image_model(model_name, valves.IMAGE_MODEL_PATTERN):
            gen_content_conf.response_modalities.append("IMAGE")

        gen_content_conf.tools = []

        if features.get("google_search_tool"):
            if valves.USE_ENTERPRISE_SEARCH and is_vertex_ai:
                log.info("Using grounding with Enterprise Web Search as a Tool.")
                gen_content_conf.tools.append(
                    types.Tool(enterprise_web_search=types.EnterpriseWebSearch())
                )
            else:
                log.info("Using grounding with Google Search as a Tool.")
                gen_content_conf.tools.append(
                    types.Tool(google_search=types.GoogleSearch())
                )
        elif features.get("google_search_retrieval"):
            log.info("Using grounding with Google Search Retrieval.")
            gs = types.GoogleSearchRetrieval(
                dynamic_retrieval_config=types.DynamicRetrievalConfig(
                    dynamic_threshold=features.get("google_search_retrieval_threshold")
                )
            )
            gen_content_conf.tools.append(types.Tool(google_search_retrieval=gs))

        # NB: It is not possible to use both Search and Code execution at the same time,
        # however, it can be changed later, so let's just handle it as a common error
        if features.get("google_code_execution"):
            log.info("Using code execution on Google side.")
            gen_content_conf.tools.append(
                types.Tool(code_execution=types.ToolCodeExecution())
            )

        # Determine if URL context tool should be enabled.
        is_avail, is_on = self._get_toggleable_feature_status(
            "gemini_url_context_toggle", __metadata__
        )
        enable_url_context = valves.ENABLE_URL_CONTEXT_TOOL  # Start with valve default.
        if is_avail:
            # If the toggle filter is configured, it overrides the valve setting.
            enable_url_context = is_on

        if enable_url_context:
            if model_name in COMPATIBLE_MODELS_FOR_URL_CONTEXT:
                if is_vertex_ai and (len(gen_content_conf.tools) > 0):
                    log.warning(
                        "URL context tool is enabled, but Vertex AI is used with other tools. Skipping."
                    )
                else:
                    log.info(
                        f"Model {model_name} is compatible with URL context tool. Enabling."
                    )
                    gen_content_conf.tools.append(
                        types.Tool(url_context=types.UrlContext())
                    )
            else:
                log.warning(
                    f"URL context tool is enabled, but model {model_name} is not in the compatible list. Skipping."
                )

        # Determine if Google Maps grounding should be enabled.
        is_avail, is_on = self._get_toggleable_feature_status(
            "gemini_maps_grounding_toggle", __metadata__
        )
        if is_avail and is_on:
            log.info("Enabling Google Maps grounding tool.")
            gen_content_conf.tools.append(
                types.Tool(google_maps=types.GoogleMaps())
            )

            if valves.MAPS_GROUNDING_COORDINATES:
                try:
                    lat_str, lon_str = valves.MAPS_GROUNDING_COORDINATES.split(",")
                    latitude = float(lat_str.strip())
                    longitude = float(lon_str.strip())

                    log.info(
                        "Using coordinates for Maps grounding: "
                        f"lat={latitude}, lon={longitude}"
                    )

                    lat_lng = types.LatLng(latitude=latitude, longitude=longitude)

                    # Ensure tool_config and retrieval_config exist before assigning lat_lng.
                    if not gen_content_conf.tool_config:
                        gen_content_conf.tool_config = types.ToolConfig()
                    if not gen_content_conf.tool_config.retrieval_config:
                        gen_content_conf.tool_config.retrieval_config = (
                            types.RetrievalConfig()
                        )

                    gen_content_conf.tool_config.retrieval_config.lat_lng = lat_lng

                except (ValueError, TypeError) as e:
                    # This should not happen due to the Pydantic validator, but it's good practice to be safe.
                    log.error(
                        "Failed to parse MAPS_GROUNDING_COORDINATES: "
                        f"'{valves.MAPS_GROUNDING_COORDINATES}'. Error: {e}"
                    )

        return gen_content_conf

    # endregion 2.3 GenerateContentConfig assembly

    # region 2.4 Model response processing
    async def _unified_response_processor(
        self,
        response_stream: AsyncIterator[types.GenerateContentResponse],
        __request__: Request,
        model: str,
        event_emitter: EventEmitter,
        user_id: str,
        chat_id: str,
        message_id: str,
        start_time: float,
    ) -> AsyncGenerator[dict, None]:
        """
        Processes an async iterator of GenerateContentResponse objects, yielding
        structured dictionary chunks for the Open WebUI frontend.

        This single method handles both streaming and non-streaming (via an adapter)
        responses, eliminating code duplication. It processes all parts within each
        response chunk, counts tag substitutions for a final toast notification,
        and handles post-processing in a finally block.
        """
        final_response_chunk: types.GenerateContentResponse | None = None
        error_occurred = False
        total_substitutions = 0
        first_chunk_received = False
        chunk_counter = 0

        try:
            async for chunk in response_stream:
                log.trace(f"Processing response chunk #{chunk_counter}:", payload=chunk)
                chunk_counter += 1
                final_response_chunk = chunk  # Keep the latest chunk for metadata

                if not first_chunk_received:
                    # This is the first (and possibly only) chunk.
                    elapsed_time = time.monotonic() - start_time
                    time_str = f"(+{elapsed_time:.2f}s)"
                    asyncio.create_task(
                        event_emitter.emit_status(
                            f"Response received {time_str}",
                            done=True,
                        )
                    )
                    first_chunk_received = True

                if not (parts := chunk.parts):
                    log.warning("Chunk has no parts, skipping.")
                    continue

                # This inner loop makes the method robust. It handles a single chunk
                # with many parts (non-streaming) or many chunks with one part (streaming).
                for part in parts:
                    payload, count = await self._process_part(
                        part,
                        __request__,
                        model,
                        user_id,
                        chat_id,
                        message_id,
                        is_stream=True,  # We always yield chunks, so this is effectively true
                    )

                    if payload:
                        if count > 0:
                            total_substitutions += count
                            log.debug(f"Disabled {count} special tag(s) in a part.")

                        structured_chunk = {"choices": [{"delta": payload}]}
                        yield structured_chunk

        except Exception as e:
            error_occurred = True
            error_msg = f"Response processing ended with error: {e}"
            log.exception(error_msg)
            await event_emitter.emit_error(error_msg)

        finally:
            # The async for loop has completed, meaning we have received all data
            # from the API. Now, we perform final internal processing.

            if total_substitutions > 0 and not error_occurred:
                plural_s = "s" if total_substitutions > 1 else ""
                toast_msg = (
                    f"For clarity, {total_substitutions} special tag{plural_s} "
                    "were disabled in the response by injecting a zero-width space (ZWS)."
                )
                event_emitter.emit_toast(toast_msg, "info")

            if not error_occurred:
                yield "data: [DONE]"
                log.info("Response processing finished successfully!")

            try:
                await self._do_post_processing(
                    final_response_chunk,
                    event_emitter,
                    __request__,
                    chat_id=chat_id,
                    message_id=message_id,
                    stream_error_happened=error_occurred,
                    start_time=start_time,
                )
            except Exception as e:
                error_msg = f"Post-processing failed with error:\n\n{e}"
                event_emitter.emit_toast(error_msg, "error")
                log.exception(error_msg)

            log.debug("Unified response processor has finished.")

    async def _process_part(
        self,
        part: types.Part,
        __request__: Request,
        model: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        is_stream: bool,
    ) -> tuple[dict | None, int]:
        """
        Processes a single `types.Part` object and returns a payload dictionary
        for the Open WebUI stream, along with a count of tag substitutions.
        """
        # Initialize variables to ensure they always have a defined state.
        payload: dict[str, str] | None = None
        count: int = 0
        key: str = "content"

        match part:
            case types.Part(text=str(text), thought=True):
                # It's a thought, so we'll use the "reasoning" key.
                key = "reasoning"
                sanitized_text, count = self._disable_special_tags(text)

                # For non-streaming responses, wrap the thought/reasoning block
                # in details block manually for nice front-end rendering.
                if not is_stream:
                    sanitized_text = f'\n<details type="reasoning" done="true">\n<summary>Thinking...</summary>\n{sanitized_text}\n</details>\n'

                payload = {key: sanitized_text}
            case types.Part(text=str(text)):
                # It's regular content, using the default "content" key.
                sanitized_text, count = self._disable_special_tags(text)
                payload = {key: sanitized_text}
            case types.Part(inline_data=data) if data:
                # Image parts don't need tag disabling.
                processed_text = await self._process_image_part(
                    data, model, user_id, chat_id, message_id, __request__
                )
                payload = {"content": processed_text}
            case types.Part(executable_code=code) if code:
                # Code blocks are already formatted and safe.
                if processed_text := self._process_executable_code_part(code):
                    payload = {"content": processed_text}
            case types.Part(code_execution_result=result) if result:
                # Code results are also safe.
                if processed_text := self._process_code_execution_result_part(result):
                    payload = {"content": processed_text}

        return payload, count

    @staticmethod
    def _disable_special_tags(text: str) -> tuple[str, int]:
        """
        Finds special tags in a text chunk and inserts a Zero-Width Space (ZWS)
        to prevent them from being parsed by the Open WebUI backend's legacy system.
        This is a safeguard against accidental tag generation by the model.
        """
        if not text:
            return "", 0

        # The regex finds '<' followed by an optional '/' and then one of the special tags.
        # The inner parentheses group the tags, so the optional '/' applies to all of them.
        TAG_REGEX = re.compile(
            r"<(/?"
            + "("
            + "|".join(re.escape(tag) for tag in SPECIAL_TAGS_TO_DISABLE)
            + ")"
            + r")"
        )
        # The substitution injects a ZWS, e.g., '</think>' becomes '<ZWS/think'.
        modified_text, num_substitutions = TAG_REGEX.subn(rf"<{ZWS}\1", text)
        return modified_text, num_substitutions

    async def _process_image_part(
        self,
        inline_data: types.Blob,
        model: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        request: Request,
    ) -> str:
        """
        Handles image data by saving it to the Open WebUI backend and returning a markdown link.
        """
        mime_type = inline_data.mime_type
        image_data = inline_data.data

        if mime_type and image_data:
            image_url = await self._upload_image(
                image_data=image_data,
                mime_type=mime_type,
                model=model,
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                __request__=request,
            )
        else:
            log.warning(
                "Image part has no mime_type or data, cannot upload image. "
                "Returning a placeholder message."
            )
            image_url = None

        return (
            f"![Generated Image]({image_url})"
            if image_url
            else "*An error occurred while trying to store this model generated image.*"
        )

    async def _upload_image(
        self,
        image_data: bytes,
        mime_type: str,
        model: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        __request__: Request,
    ) -> str | None:
        """
        Helper method that uploads a generated image to the configured Open WebUI storage provider.
        Returns the url to the uploaded image.
        """
        image_format = mimetypes.guess_extension(mime_type) or ".png"
        id = str(uuid.uuid4())
        name = f"generated-image{image_format}"

        # The final filename includes the unique ID to prevent collisions.
        imagename = f"{id}_{name}"
        image = io.BytesIO(image_data)

        # Create a clean, precise metadata object linking to the generation context.
        image_metadata = {
            "model": model,
            "chat_id": chat_id,
            "message_id": message_id,
        }

        log.info("Uploading the model-generated image to the Open WebUI backend.")

        try:
            contents, image_path = await asyncio.to_thread(
                Storage.upload_file, image, imagename, tags={}
            )
        except Exception:
            log.exception("Error occurred during upload to the storage provider.")
            return None

        log.debug("Adding the image file to the Open WebUI files database.")
        file_item = await asyncio.to_thread(
            Files.insert_new_file,
            user_id,
            FileForm(
                id=id,
                filename=name,
                path=image_path,
                meta={
                    "name": name,
                    "content_type": mime_type,
                    "size": len(contents),
                    "data": image_metadata,
                },
            ),
        )
        if not file_item:
            log.warning("Image upload to Open WebUI database likely failed.")
            return None

        image_url: str = __request__.app.url_path_for(
            "get_file_content_by_id", id=file_item.id
        )
        log.success("Image upload finished!")
        return image_url

    def _process_executable_code_part(
        self, executable_code_part: types.ExecutableCode | None
    ) -> str | None:
        """
        Processes an executable code part and returns the formatted string representation.
        """

        if not executable_code_part:
            return None

        lang_name = "python"  # Default language
        if executable_code_part_lang_enum := executable_code_part.language:
            if lang_name := executable_code_part_lang_enum.name:
                lang_name = executable_code_part_lang_enum.name.lower()
            else:
                log.warning(
                    f"Could not extract language name from {executable_code_part_lang_enum}. Default to python."
                )
        else:
            log.warning("Language Enum is None, defaulting to python.")

        if executable_code_part_code := executable_code_part.code:
            return f"```{lang_name}\n{executable_code_part_code.rstrip()}\n```\n\n"
        return ""

    def _process_code_execution_result_part(
        self, code_execution_result_part: types.CodeExecutionResult | None
    ) -> str | None:
        """
        Processes a code execution result part and returns the formatted string representation.
        """

        if not code_execution_result_part:
            return None

        if code_execution_result_part_output := code_execution_result_part.output:
            return f"**Output:**\n\n```\n{code_execution_result_part_output.rstrip()}\n```\n\n"
        else:
            return None

    # endregion 2.4 Model response processing

    # region 2.5 Post-processing
    async def _do_post_processing(
        self,
        model_response: types.GenerateContentResponse | None,
        event_emitter: EventEmitter,
        request: Request,
        chat_id: str,
        message_id: str,
        *,
        stream_error_happened: bool = False,
        start_time: float,
    ):
        """Handles emitting usage, grounding, and sources after the main response/stream is done."""
        log.info("Post-processing the model response.")

        elapsed_time = time.monotonic() - start_time
        time_str = f"(+{elapsed_time:.2f}s)"

        if stream_error_happened:
            log.warning("Response processing failed due to stream error.")
            await event_emitter.emit_status(
                f"Response failed [Stream Error] {time_str}", done=True
            )
            return

        if not model_response:
            log.warning("Response processing skipped: Model response was empty.")
            await event_emitter.emit_status(
                f"Response failed [Empty Response] {time_str}", done=True
            )
            return

        if not (candidate := self._get_first_candidate(model_response.candidates)):
            log.warning("Response processing skipped: No candidates found.")
            await event_emitter.emit_status(
                f"Response failed [No Candidates] {time_str}", done=True
            )
            return

        # --- Construct detailed finish reason message ---
        reason_name = getattr(candidate.finish_reason, "name", "UNSPECIFIED")
        reason_description = FINISH_REASON_DESCRIPTIONS.get(reason_name)
        finish_message = (
            candidate.finish_message.strip() if candidate.finish_message else None
        )

        details_parts = [part for part in (reason_description, finish_message) if part]
        details_str = f": {' '.join(details_parts)}" if details_parts else ""
        full_finish_details = f"[{reason_name}]{details_str}"

        # --- Determine final status and emit toast for errors ---
        is_normal_finish = candidate.finish_reason in NORMAL_REASONS

        if is_normal_finish:
            log.debug(f"Response finished normally. {full_finish_details}")
            status_prefix = "Response finished"
        else:
            log.error(f"Response finished with an error. {full_finish_details}")
            status_prefix = "Response failed"
            event_emitter.emit_toast(
                f"An error occurred. {full_finish_details}",
                "error",
            )

        # For the most common success case (STOP), we don't need to show the reason.
        final_reason_str = "" if reason_name == "STOP" else f" [{reason_name}]"
        await event_emitter.emit_status(
            f"{status_prefix}{final_reason_str} {time_str}",
            done=True,
            is_successful_finish=is_normal_finish,
        )

        # TODO: Emit a toast message if url context retrieval was not successful.

        # --- Emit usage and grounding data ---
        # Attempt to emit token usage data even if the finish reason was problematic,
        # as usage data might still be available.
        if usage_data := self._get_usage_data(model_response):
            # Inject the total processing time into the usage payload.
            usage_data["completion_time"] = round(elapsed_time, 2)
            await event_emitter.emit_usage(usage_data)

        self._add_grounding_data_to_state(
            model_response, request, chat_id, message_id, start_time
        )

    def _add_grounding_data_to_state(
        self,
        response: types.GenerateContentResponse,
        request: Request,
        chat_id: str,
        message_id: str,
        pipe_start_time: float,
    ):
        candidate = self._get_first_candidate(response.candidates)
        grounding_metadata_obj = candidate.grounding_metadata if candidate else None

        app_state: State = request.app.state
        grounding_key = f"grounding_{chat_id}_{message_id}"
        time_key = f"pipe_start_time_{chat_id}_{message_id}"

        if grounding_metadata_obj:
            log.debug(
                f"Found grounding metadata. Storing in request's app state using key {grounding_key}."
            )
            # Using shared `request.app.state` to pass data to Filter.outlet.
            # This is necessary because the Pipe and Filter operate on different requests.
            app_state._state[grounding_key] = grounding_metadata_obj
            app_state._state[time_key] = pipe_start_time
        else:
            log.debug(f"Response {message_id} does not have grounding metadata.")

    @staticmethod
    def _get_usage_data(
        response: types.GenerateContentResponse,
    ) -> dict[str, Any] | None:
        """
        Extracts and cleans usage data from a GenerateContentResponse object.
        Returns None if usage metadata is not present.
        """
        if not response.usage_metadata:
            log.warning(
                "Usage metadata is missing from the response. Cannot determine usage."
            )
            return None

        usage_data = response.usage_metadata.model_dump()

        # 1. Rename the three core required fields.
        usage_data["prompt_tokens"] = usage_data.pop("prompt_token_count")
        usage_data["completion_tokens"] = usage_data.pop("candidates_token_count")
        usage_data["total_tokens"] = usage_data.pop("total_token_count")

        CORE_KEYS = {"prompt_tokens", "completion_tokens", "total_tokens"}

        # 2. Remove auxiliary keys that have falsy values (None, empty list, etc.).
        # We must iterate over a copy of keys to safely delete items from the dict.
        for k in list(usage_data.keys()):
            if k in CORE_KEYS:
                continue

            # If the value is falsy (None, 0, empty list), remove the key.
            # This retains non-core data (like modality counts) if it exists.
            if not usage_data[k]:
                del usage_data[k]

        return usage_data

    # endregion 2.5 Post-processing

    # region 2.6 Logging
    # TODO: Move to a separate plugin that does not have any Open WebUI funcitonlity and is only imported by this plugin.

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

    @cache
    def _add_log_handler(self, log_level: str):
        """
        Adds or updates the loguru handler specifically for this plugin.
        Includes logic for serializing and truncating extra data.
        The handler is added only if the log_level has changed since the last call.
        """

        def plugin_filter(record: "Record"):
            """Filter function to only allow logs from this plugin (based on module name)."""
            return record["name"] == __name__

        # Get the desired level name and number
        desired_level_name = log_level
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
            log.add(
                sys.stdout,
                level=desired_level_name,
                format=self.plugin_stdout_format,
                filter=plugin_filter,
            )
            log.debug(
                f"Added new handler to loguru for {__name__} with level {desired_level_name}."
            )

    # endregion 2.6 Logging

    # region 2.7 Utility helpers

    @staticmethod
    def _get_toggleable_feature_status(
        filter_id: str,
        __metadata__: "Metadata",
    ) -> tuple[bool, bool]:
        """
        Checks the complete status of a toggleable filter (function).

        This function performs a series of checks to determine if a feature
        is available for use and if the user has activated it.

        1. Checks if the filter is installed.
        2. Checks if the filter's master toggle is active in the Functions dashboard.
        3. Checks if the filter is enabled for the current model (or is global).
        4. Checks if the user has toggled the feature ON for the current request.

        Args:
            filter_id: The ID of the filter to check.
            __metadata__: The metadata object for the current request.

        Returns:
            A tuple (is_available: bool, is_toggled_on: bool).
            - is_available: True if the filter is installed, active, and configured for the model.
            - is_toggled_on: True if the user has the toggle ON in the UI for this request.
        """
        # 1. Check if the filter is installed
        f = Functions.get_function_by_id(filter_id)
        if not f:
            log.warning(
                f"The '{filter_id}' filter is not installed. "
                "Install it to use the corresponding front-end toggle."
            )
            return (False, False)

        # 2. Check if the master toggle is active
        if not f.is_active:
            log.warning(
                f"The '{filter_id}' filter is installed but is currently disabled in the "
                "Functions dashboard (master toggle is off). Enable it to make it available."
            )
            return (False, False)

        # 3. Check if the filter is enabled for the model or is global
        model_info = __metadata__.get("model", {}).get("info", {})
        model_filter_ids = model_info.get("meta", {}).get("filterIds", [])
        is_enabled_for_model = filter_id in model_filter_ids or f.is_global

        log.debug(
            f"Checking model enablement for '{filter_id}': in_model_filters={filter_id in model_filter_ids}, "
            f"is_global={f.is_global} -> is_enabled={is_enabled_for_model}"
        )

        if not is_enabled_for_model:
            # This is a configuration issue, not a user-facing warning. Debug is appropriate.
            model_id = __metadata__.get("model", {}).get("id", "Unknown")
            log.debug(f"Filter '{filter_id}' is not enabled for model '{model_id}' and is not global.")
            return (False, False)

        # 4. Check if the user has toggled the feature ON for this request
        user_toggled_ids = __metadata__.get("filter_ids", [])
        is_toggled_on = filter_id in user_toggled_ids

        if is_toggled_on:
            log.info(
                f"Feature '{filter_id}' is available and enabled by the front-end toggle for this request."
            )
        else:
            log.debug(
                f"Feature '{filter_id}' is available but not enabled by the front-end toggle for this request."
            )

        return (True, is_toggled_on)

    @staticmethod
    def _get_merged_valves(
        default_valves: "Pipe.Valves",
        user_valves: "Pipe.UserValves | None",
        user_email: str,
    ) -> "Pipe.Valves":
        """
        Merges UserValves into a base Valves configuration.

        The general rule is that if a field in UserValves is not None, it overrides
        the corresponding field in the default_valves. Otherwise, the default_valves
        field value is used.

        Exceptions:
        - If default_valves.USER_MUST_PROVIDE_AUTH_CONFIG is True, then GEMINI_API_KEY and
          VERTEX_PROJECT in the merged result will be taken directly from
          user_valves (even if they are None), ignoring the values in default_valves.

        Args:
            default_valves: The base Valves object with default configurations.
            user_valves: An optional UserValves object with user-specific overrides.
                         If None, a copy of default_valves is returned.

        Returns:
            A new Valves object representing the merged configuration.
        """
        if user_valves is None:
            # If no user-specific valves are provided, return a copy of the default valves.
            return default_valves.model_copy(deep=True)

        # Start with the values from the base `Valves`
        merged_data = default_valves.model_dump()

        # Override with non-None values from `UserValves`
        # Iterate over fields defined in the UserValves model
        for field_name in Pipe.UserValves.model_fields:
            # getattr is safe as field_name comes from model_fields of user_valves' type
            user_value = getattr(user_valves, field_name)
            if user_value is not None and user_value != "":
                # Only update if the field is also part of the main Valves model
                # (keys of merged_data are fields of default_valves)
                if field_name in merged_data:
                    merged_data[field_name] = user_value

        user_whitelist = (
            default_valves.AUTH_WHITELIST.split(",")
            if default_valves.AUTH_WHITELIST
            else []
        )

        # Apply special logic based on default_valves.USER_MUST_PROVIDE_AUTH_CONFIG
        if (
            default_valves.USER_MUST_PROVIDE_AUTH_CONFIG
            and user_email not in user_whitelist
        ):
            # If USER_MUST_PROVIDE_AUTH_CONFIG is True and user is not in the whitelist,
            # then user must provide their own GEMINI_API_KEY
            # User is disallowed from using Vertex AI in this case.
            merged_data["GEMINI_API_KEY"] = user_valves.GEMINI_API_KEY
            merged_data["VERTEX_PROJECT"] = None
            merged_data["USE_VERTEX_AI"] = False

        # Create a new Valves instance with the merged data.
        # Pydantic will validate the data against the Valves model definition during instantiation.
        return Pipe.Valves(**merged_data)

    def _get_first_candidate(
        self, candidates: list[types.Candidate] | None
    ) -> types.Candidate | None:
        """Selects the first candidate, logging a warning if multiple exist."""
        if not candidates:
            # Logging warnings is handled downstream.
            return None
        if len(candidates) > 1:
            log.warning("Multiple candidates found, defaulting to first candidate.")
        return candidates[0]

    def _check_companion_filter_version(self, features: "Features | dict") -> None:
        """
        Checks for the presence and version compatibility of the Gemini Manifold Companion filter.
        Logs warnings if the filter is missing or outdated.
        """
        companion_version = features.get("gemini_manifold_companion_version")

        if companion_version is None:
            log.warning(
                "Gemini Manifold Companion filter not detected. "
                "While this pipe can function without it, you are missing out on key features like native Google Search, "
                "Code Execution, and direct document uploads. Please install the companion filter or ensure it is active "
                "for this model to unlock the full functionality."
            )
        else:
            # Comparing tuples of integers is a robust way to handle versions like '1.10.0' vs '1.2.0'.
            try:
                companion_v_tuple = tuple(map(int, companion_version.split(".")))
                recommended_v_tuple = tuple(
                    map(int, RECOMMENDED_COMPANION_VERSION.split("."))
                )

                if companion_v_tuple < recommended_v_tuple:
                    log.warning(
                        f"The installed Gemini Manifold Companion filter version ({companion_version}) is older than "
                        f"the recommended version ({RECOMMENDED_COMPANION_VERSION}). "
                        "Some features may not work as expected. Please update the filter."
                    )
                else:
                    log.debug(
                        f"Gemini Manifold Companion filter detected with version: {companion_version}"
                    )
            except (ValueError, TypeError):
                # This handles cases where the version string is malformed (e.g., '1.a.0').
                log.error(
                    f"Could not parse companion version string: '{companion_version}'. Version check skipped."
                )

    # endregion 2.7 Utility helpers

    # endregion 2. Helper methods inside the Pipe class
