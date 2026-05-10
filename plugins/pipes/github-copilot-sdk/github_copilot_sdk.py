"""
title: GitHub Copilot Official SDK Pipe
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
openwebui_id: ce96f7b4-12fc-4ac3-9a01-875713e69359
description: A powerful Agent SDK integration for OpenWebUI. It deeply bridges GitHub Copilot SDK with OpenWebUI's ecosystem, enabling the Agent to autonomously perform intent recognition, web search, and context compaction. It seamlessly reuses your existing Tools, MCP servers, OpenAPI servers, and Skills for a professional, full-featured experience.
version: 0.13.1
requirements: github-copilot-sdk==0.2.2
"""

import asyncio
import base64
import hashlib
import html as html_lib
import inspect
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
import threading
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple, Union

import aiohttp
from copilot import CopilotClient, define_tool
from copilot.generated.rpc import Mode, SessionModeSetParams
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, create_model

# PermissionHandler moved from copilot to copilot.session in v0.2.x
try:
    from copilot.session import PermissionHandler
except ImportError:
    PermissionHandler = None

# Import Tool Server Connections and Tool System from OpenWebUI Config
import mimetypes
import uuid

from open_webui.config import (
    PERSISTENT_CONFIG_REGISTRY,
    TOOL_SERVER_CONNECTIONS,
)
from open_webui.models.files import FileForm, Files
from open_webui.models.tools import Tools
from open_webui.models.users import Users
from open_webui.storage.provider import Storage
from open_webui.utils.tools import get_builtin_tools
from open_webui.utils.tools import get_tools as get_openwebui_tools

if os.path.exists("/app/backend/data"):
    CHAT_MAPPING_FILE = Path(
        "/app/backend/data/copilot_workspace/api_key_chat_id_mapping.json"
    )
else:
    CHAT_MAPPING_FILE = (
        Path(os.getcwd()) / "copilot_workspace" / "api_key_chat_id_mapping.json"
    )

# Get OpenWebUI version for capability detection
try:
    from open_webui.env import VERSION as open_webui_version
except ImportError:
    open_webui_version = "0.0.0"

# Setup logger
logger = logging.getLogger(__name__)


async def _resolve_awaitable_compat(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call_openwebui_compat(
    func: Any,
    *args: Any,
    prefer_thread_for_sync: bool = False,
    **kwargs: Any,
) -> Any:
    if prefer_thread_for_sync and not inspect.iscoroutinefunction(func):
        result = await asyncio.to_thread(func, *args, **kwargs)
    else:
        result = func(*args, **kwargs)
    return await _resolve_awaitable_compat(result)


def _resolve_awaitable_sync(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    result_box: Dict[str, Any] = {}
    error_box: Dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result_box["value"] = asyncio.run(value)
        except BaseException as exc:
            error_box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_box:
        raise error_box["error"]

    return result_box.get("value")


def _call_openwebui_sync_compat(func: Any, *args: Any, **kwargs: Any) -> Any:
    return _resolve_awaitable_sync(func(*args, **kwargs))


def _extract_search_result_items(result: Any) -> List[Any]:
    if result is None:
        return []

    if isinstance(result, list):
        return result

    if isinstance(result, tuple):
        return list(result)

    if isinstance(result, dict):
        items = result.get("items")
    else:
        items = getattr(result, "items", None)

    if callable(items):
        try:
            items = items()
        except TypeError:
            items = None

    if items is None:
        return []

    if isinstance(items, list):
        return items

    if isinstance(items, tuple):
        return list(items)

    try:
        return list(items)
    except TypeError:
        return []


RICHUI_BRIDGE_MARKER = 'data-openwebui-richui-bridge="1"'
RICHUI_BRIDGE_STYLE = """
<style id="openwebui-richui-bridge-style" data-openwebui-richui-bridge="1">
:root {
  color-scheme: light dark;
  /* Theme-aware CSS variables for AI-generated content */
  --richui-text: #1a202c;
  --richui-text-secondary: #4a5568;
  --richui-text-muted: #718096;
  --richui-bg: #ffffff;
  --richui-bg-secondary: #f7fafc;
  --richui-bg-tertiary: #edf2f7;
  --richui-border: #e2e8f0;
  --richui-border-subtle: #edf2f7;
  --richui-accent: #3182ce;
  --richui-accent-hover: #2b6cb0;
  --richui-success: #38a169;
  --richui-warning: #d69e2e;
  --richui-error: #e53e3e;
}
@media (prefers-color-scheme: dark) {
  :root {
    --richui-text: #f7fafc;
    --richui-text-secondary: #cbd5e0;
    --richui-text-muted: #a0aec0;
    --richui-bg: #1a202c;
    --richui-bg-secondary: #2d3748;
    --richui-bg-tertiary: #4a5568;
    --richui-border: #4a5568;
    --richui-border-subtle: #2d3748;
    --richui-accent: #63b3ed;
    --richui-accent-hover: #90cdf4;
    --richui-success: #68d391;
    --richui-warning: #f6e05e;
    --richui-error: #fc8181;
  }
}
html[data-openwebui-applied-theme="dark"],
html.dark {
  --richui-text: #f7fafc;
  --richui-text-secondary: #cbd5e0;
  --richui-text-muted: #a0aec0;
  --richui-bg: #1a202c;
  --richui-bg-secondary: #2d3748;
  --richui-bg-tertiary: #4a5568;
  --richui-border: #4a5568;
  --richui-border-subtle: #2d3748;
  --richui-accent: #63b3ed;
  --richui-accent-hover: #90cdf4;
  --richui-success: #68d391;
  --richui-warning: #f6e05e;
  --richui-error: #fc8181;
}
html[data-openwebui-applied-theme="light"],
html.light {
  --richui-text: #1a202c;
  --richui-text-secondary: #4a5568;
  --richui-text-muted: #718096;
  --richui-bg: #ffffff;
  --richui-bg-secondary: #f7fafc;
  --richui-bg-tertiary: #edf2f7;
  --richui-border: #e2e8f0;
  --richui-border-subtle: #edf2f7;
  --richui-accent: #3182ce;
  --richui-accent-hover: #2b6cb0;
  --richui-success: #38a169;
  --richui-warning: #d69e2e;
  --richui-error: #e53e3e;
}
html,
body {
  background: transparent !important;
  color: var(--richui-text) !important;
  overflow-x: hidden !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}
body[data-openwebui-richui-fragment="1"] {
  /* Prevent margin collapse issues that can jitter height */
  display: block;
}
</style>
"""
RICHUI_BRIDGE_SCRIPT = r"""
<script id="openwebui-richui-bridge-script" data-openwebui-richui-bridge="1">
(function() {
  if (window.__openWebUIRichUIBridgeInstalled) {
    return;
  }
  window.__openWebUIRichUIBridgeInstalled = true;

  var root = document.documentElement;
  var heightObserver = null;
  var domObserver = null;
  var parentThemeObserver = null;
  var heightTimer = null;
  var lastHeight = -1;
  var lastPromptText = '';
  var lastPromptAt = 0;
  var selectionState = {};
  var bridgeToastTimer = null;
  var declarativeActionSelector =
    '[data-openwebui-prompt],[data-prompt],[data-openwebui-link],[data-link],[data-openwebui-action],[data-openwebui-mode],[data-openwebui-copy],[data-copy],[data-openwebui-prompt-template],[data-openwebui-copy-template],[data-openwebui-select]';

  function getParentDocument() {
    try {
      if (window.parent && window.parent !== window) {
        void window.parent.document.documentElement;
        return window.parent.document;
      }
    } catch (e) {}
    return null;
  }

  function classHasThemeToken(className, token) {
    return String(className || '').indexOf(token) !== -1;
  }

  function applyTheme(theme) {
    if (theme !== 'dark' && theme !== 'light') {
      return;
    }
    var isDark = theme === 'dark';
    var shouldMirrorTheme = Boolean(getParentDocument());
    if (
      root.getAttribute('data-openwebui-applied-theme') === theme &&
      (!shouldMirrorTheme ||
        (root.getAttribute('data-theme') === theme &&
          root.classList.contains('dark') === isDark)) &&
      String(root.style.colorScheme || '') === theme
    ) {
      return;
    }
    root.setAttribute('data-openwebui-applied-theme', theme);
    if (shouldMirrorTheme) {
      root.setAttribute('data-theme', theme);
      root.classList.toggle('dark', isDark);
    }
    root.style.colorScheme = theme;
  }

  function parseColorLuma(colorStr) {
    if (!colorStr) {
      return null;
    }
    var normalized = String(colorStr).trim();
    var match = null;
    if (/^#[0-9a-f]{3}$/i.test(normalized)) {
      normalized =
        '#' +
        normalized.charAt(1) +
        normalized.charAt(1) +
        normalized.charAt(2) +
        normalized.charAt(2) +
        normalized.charAt(3) +
        normalized.charAt(3);
    }
    match = normalized.match(/^#?([0-9a-f]{6})$/i);
    if (match) {
      var hex = match[1];
      var r = parseInt(hex.slice(0, 2), 16);
      var g = parseInt(hex.slice(2, 4), 16);
      var b = parseInt(hex.slice(4, 6), 16);
      return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    }
    match = normalized.match(
      /rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i
    );
    if (match) {
      var rr = parseInt(match[1], 10);
      var gg = parseInt(match[2], 10);
      var bb = parseInt(match[3], 10);
      return (0.2126 * rr + 0.7152 * gg + 0.0722 * bb) / 255;
    }
    return null;
  }

  function getThemeFromMeta(doc) {
    try {
      var scopeDoc = doc || document;
      var metas = scopeDoc.querySelectorAll('meta[name="theme-color"]');
      if (!metas || !metas.length) {
        return null;
      }
      var color = metas[metas.length - 1].content || '';
      var luma = parseColorLuma(color);
      if (luma === null) {
        return null;
      }
      return luma < 0.5 ? 'dark' : 'light';
    } catch (e) {}
    return null;
  }

  function getThemeFromDocument(doc) {
    if (!doc) {
      return null;
    }
    try {
      var html = doc.documentElement;
      var body = doc.body;
      var htmlClass = html ? String(html.className || '') : '';
      var bodyClass = body ? String(body.className || '') : '';
      var htmlDataTheme = html ? html.getAttribute('data-theme') : '';

      if (
        htmlDataTheme === 'dark' ||
        classHasThemeToken(bodyClass, 'dark') ||
        classHasThemeToken(htmlClass, 'dark')
      ) {
        return 'dark';
      }
      if (
        htmlDataTheme === 'light' ||
        classHasThemeToken(bodyClass, 'light') ||
        classHasThemeToken(htmlClass, 'light')
      ) {
        return 'light';
      }
    } catch (e) {}
    return null;
  }

  function resolveTheme() {
    var parentDoc = getParentDocument();
    var parentMetaTheme = parentDoc ? getThemeFromMeta(parentDoc) : null;
    if (parentMetaTheme) {
      return parentMetaTheme;
    }

    var parentClassTheme = parentDoc ? getThemeFromDocument(parentDoc) : null;
    if (parentClassTheme) {
      return parentClassTheme;
    }

    if (!parentDoc) {
      var localMetaTheme = getThemeFromMeta(document);
      if (localMetaTheme) {
        return localMetaTheme;
      }

      var localClassTheme = getThemeFromDocument(document);
      if (localClassTheme) {
        return localClassTheme;
      }
    }

    try {
      if (
        window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches
      ) {
        return 'dark';
      }
    } catch (e) {}

    return 'light';
  }

  function syncTheme() {
    applyTheme(resolveTheme());
  }

function measureHeight() {
    var body = document.body;
    if (!body) {
      return 0;
    }

    // 1. Temporarily pause mutation observer to avoid self-triggered sizing Loops
    if (domObserver) {
      try { domObserver.disconnect(); } catch(e) {}
    }
    if (heightObserver && document.body) {
      try { heightObserver.unobserve(document.body); } catch(e) {}
    }

    var previousHeight = body.style.height;

    // 2. Clear explicit height to let the browser compute natural layout
    body.style.height = 'auto';

    // 3. Compute the scrollHeight accurately. Use Math.ceil to prevent fractional pixel jitter.
    var height = Math.ceil(document.documentElement.scrollHeight || body.scrollHeight);

    // If the height hasn't changed, don't update style to avoid triggering observers
    if (height === lastHeight) {
       if (previousHeight && previousHeight !== 'auto') {
          body.style.height = previousHeight;
       }
    } else {
       // Only set explicit height if we are not relying purely on flex/grid sizing.
       // For typical rich UI content, letting the parent iframe handle it is better.
       // We skip setting explicit body.style.height back to avoid "infinite growing" bugs.
    }

    // 4. Resume observer
    if (heightObserver && document.body) {
      try { heightObserver.observe(document.body); } catch(e) {}
    }
    if (domObserver) {
      try {
        domObserver.observe(document.documentElement, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
        });
      } catch(e) {}
    }

    return height;
  }

  function postToParent(message) {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(message, '*');
        return true;
      }
    } catch (e) {}
    return false;
  }

  function emitHeight(force) {
    var height = measureHeight();
    if (!force && height === lastHeight) {
      return height;
    }
    lastHeight = height;
    postToParent({ type: 'iframe:height', height: height });
    return height;
  }

  function scheduleHeight(delay, force) {
    if (heightTimer) {
      window.clearTimeout(heightTimer);
    }
    heightTimer = window.setTimeout(function() {
      emitHeight(Boolean(force));
    }, delay || 0);
  }

  function attachHeightObservers() {
    if (window.ResizeObserver && document.body && !heightObserver) {
      heightObserver = new ResizeObserver(function() {
        scheduleHeight(0, false);
      });
      heightObserver.observe(document.body);
    }
    if (window.MutationObserver && !domObserver) {
      domObserver = new MutationObserver(function() {
        scheduleHeight(0, false);
      });
      domObserver.observe(document.documentElement, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
      });
    }
  }

  function attachThemeObservers() {
    var themeDoc = getParentDocument() || document;
    if (!window.MutationObserver || !themeDoc || parentThemeObserver) {
      return;
    }
    try {
      parentThemeObserver = new MutationObserver(syncTheme);
      if (themeDoc.documentElement) {
        parentThemeObserver.observe(themeDoc.documentElement, {
          attributes: true,
          attributeFilter: ['class', 'data-theme'],
        });
      }
      if (themeDoc.body) {
        parentThemeObserver.observe(themeDoc.body, {
          attributes: true,
          attributeFilter: ['class', 'data-theme'],
        });
      }
      if (themeDoc.head) {
        parentThemeObserver.observe(themeDoc.head, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ['content', 'name'],
        });
      }
    } catch (e) {}
  }

  function sendPrompt(text) {
    var promptText = text == null ? '' : String(text);
    var normalizedPrompt = promptText.trim();
    var now = Date.now ? Date.now() : new Date().getTime();
    if (
      normalizedPrompt &&
      normalizedPrompt === lastPromptText &&
      now - lastPromptAt < 600
    ) {
      return false;
    }
    lastPromptText = normalizedPrompt;
    lastPromptAt = now;
    return postToParent({ type: 'input:prompt:submit', text: promptText });
  }

  function fillPrompt(text) {
    var promptText = text == null ? '' : String(text);
    return postToParent({ type: 'input:prompt', text: promptText });
  }

  function submitCurrentPrompt() {
    return postToParent({ type: 'action:submit', text: '' });
  }

  function getBridgeLanguage() {
    var lang =
      window.__OPENWEBUI_USER_LANG__ ||
      window.__openwebui_user_lang__ ||
      (document.documentElement && document.documentElement.getAttribute('lang')) ||
      navigator.language ||
      'en-US';
    return String(lang || 'en-US');
  }

  function getBridgeMessage(key) {
    var lang = getBridgeLanguage().toLowerCase();
    var messages = {
      copied: 'Copied to clipboard',
      copy_failed: 'Copy failed',
    };
    if (lang.indexOf('zh-hk') === 0 || lang.indexOf('zh-tw') === 0) {
      messages = {
        copied: '已複製到剪貼簿',
        copy_failed: '複製失敗',
      };
    } else if (lang.indexOf('zh') === 0) {
      messages = {
        copied: '已复制到剪贴板',
        copy_failed: '复制失败',
      };
    } else if (lang.indexOf('ja') === 0) {
      messages = {
        copied: 'クリップボードにコピーしました',
        copy_failed: 'コピーに失敗しました',
      };
    } else if (lang.indexOf('ko') === 0) {
      messages = {
        copied: '클립보드에 복사됨',
        copy_failed: '복사에 실패했습니다',
      };
    } else if (lang.indexOf('fr') === 0) {
      messages = {
        copied: 'Copie dans le presse-papiers',
        copy_failed: 'Echec de la copie',
      };
    } else if (lang.indexOf('de') === 0) {
      messages = {
        copied: 'In die Zwischenablage kopiert',
        copy_failed: 'Kopieren fehlgeschlagen',
      };
    } else if (lang.indexOf('es') === 0) {
      messages = {
        copied: 'Copiado al portapapeles',
        copy_failed: 'Error al copiar',
      };
    } else if (lang.indexOf('it') === 0) {
      messages = {
        copied: 'Copiato negli appunti',
        copy_failed: 'Copia non riuscita',
      };
    } else if (lang.indexOf('ru') === 0) {
      messages = {
        copied: 'Скопировано в буфер обмена',
        copy_failed: 'Не удалось скопировать',
      };
    } else if (lang.indexOf('vi') === 0) {
      messages = {
        copied: 'Da sao chep vao bo nho tam',
        copy_failed: 'Sao chep that bai',
      };
    } else if (lang.indexOf('id') === 0) {
      messages = {
        copied: 'Disalin ke clipboard',
        copy_failed: 'Gagal menyalin',
      };
    }
    return messages[key] || messages.copied;
  }

  function dispatchBridgeEvent(name, detail) {
    try {
      document.dispatchEvent(
        new CustomEvent(name, {
          detail: detail || {},
        })
      );
    } catch (e) {}
  }

  function ensureBridgeToast() {
    var toast = document.getElementById('openwebui-richui-toast');
    if (toast) {
      return toast;
    }
    toast = document.createElement('div');
    toast.id = 'openwebui-richui-toast';
    toast.setAttribute('data-openwebui-richui-bridge', '1');
    toast.style.position = 'fixed';
    toast.style.right = '16px';
    toast.style.bottom = '16px';
    toast.style.zIndex = '2147483647';
    toast.style.maxWidth = 'min(360px, calc(100vw - 24px))';
    toast.style.padding = '10px 14px';
    toast.style.borderRadius = '10px';
    toast.style.background = 'rgba(15,23,42,0.92)';
    toast.style.color = '#f8fafc';
    toast.style.font = '500 13px/1.4 Inter, system-ui, sans-serif';
    toast.style.boxShadow = '0 10px 30px rgba(15,23,42,0.28)';
    toast.style.opacity = '0';
    toast.style.pointerEvents = 'none';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'opacity .18s ease, transform .18s ease';
    document.body.appendChild(toast);
    return toast;
  }

  function showBridgeToast(message, tone) {
    if (!message || !document.body) {
      return;
    }
    var toast = ensureBridgeToast();
    toast.textContent = String(message);
    toast.style.background =
      tone === 'error' ? 'rgba(127,29,29,0.96)' : 'rgba(15,23,42,0.92)';
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    if (bridgeToastTimer) {
      window.clearTimeout(bridgeToastTimer);
    }
    bridgeToastTimer = window.setTimeout(function() {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
    }, 1800);
  }

  function fallbackCopyText(text) {
    if (!document.body) {
      return false;
    }
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'readonly');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    var copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (e) {}
    document.body.removeChild(textarea);
    return copied;
  }

  function copyText(text) {
    var copyValue = text == null ? '' : String(text);
    if (!copyValue) {
      return false;
    }

    function onCopied() {
      showBridgeToast(getBridgeMessage('copied'));
      dispatchBridgeEvent('openwebui:copy', {
        text: copyValue,
        success: true,
      });
      return true;
    }

    function onCopyFailed() {
      showBridgeToast(getBridgeMessage('copy_failed'), 'error');
      dispatchBridgeEvent('openwebui:copy', {
        text: copyValue,
        success: false,
      });
      return false;
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(copyValue).then(onCopied).catch(function() {
          if (fallbackCopyText(copyValue)) {
            onCopied();
            return;
          }
          onCopyFailed();
        });
        return true;
      }
    } catch (e) {}

    if (fallbackCopyText(copyValue)) {
      return onCopied();
    }
    return onCopyFailed();
  }

  function openLink(url) {
    try {
      if (window.parent && window.parent !== window && window.parent.window) {
        window.parent.window.open(url, '_blank');
        return true;
      }
    } catch (e) {}
    try {
      window.open(url, '_blank');
      return true;
    } catch (e) {}
    return false;
  }

  function reportHeightBridge() {
    return emitHeight(true);
  }

  function normalizeBridgeText(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  }

  function isInteractiveTag(element) {
    if (!element || !element.tagName) {
      return false;
    }
    var tag = String(element.tagName).toLowerCase();
    return (
      tag === 'a' ||
      tag === 'button' ||
      tag === 'input' ||
      tag === 'select' ||
      tag === 'textarea' ||
      tag === 'summary'
    );
  }

  function getPromptActionValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (
      element.getAttribute('data-openwebui-prompt') ||
      element.getAttribute('data-prompt') ||
      ''
    ).trim();
  }

  function getLinkActionValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (
      element.getAttribute('data-openwebui-link') ||
      element.getAttribute('data-link') ||
      ''
    ).trim();
  }

  function getCopyActionValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (
      element.getAttribute('data-openwebui-copy') ||
      element.getAttribute('data-copy') ||
      ''
    ).trim();
  }

  function getPromptTemplateValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (element.getAttribute('data-openwebui-prompt-template') || '').trim();
  }

  function getCopyTemplateValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (element.getAttribute('data-openwebui-copy-template') || '').trim();
  }

  function getSelectionKey(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (element.getAttribute('data-openwebui-select') || '').trim();
  }

  function getSelectionValue(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (
      element.getAttribute('data-openwebui-value') ||
      element.getAttribute('data-value') ||
      ''
    ).trim();
  }

  function getSelectionLabel(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return normalizeBridgeText(
      element.getAttribute('data-openwebui-selection-label') ||
      element.getAttribute('aria-label') ||
      element.textContent ||
      getSelectionValue(element)
    );
  }

  function getSelectionMode(element) {
    if (!element || !element.getAttribute) {
      return 'single';
    }
    var rawMode = (
      element.getAttribute('data-openwebui-selection-mode') || 'single'
    ).trim().toLowerCase();
    if (rawMode === 'toggle') {
      return 'toggle';
    }
    return 'single';
  }

  function cloneSelectionState() {
    var output = {};
    for (var key in selectionState) {
      if (!Object.prototype.hasOwnProperty.call(selectionState, key)) {
        continue;
      }
      output[key] = {
        value: selectionState[key].value,
        label: selectionState[key].label,
      };
    }
    return output;
  }

  function getSelectionSummary() {
    var parts = [];
    for (var key in selectionState) {
      if (!Object.prototype.hasOwnProperty.call(selectionState, key)) {
        continue;
      }
      var item = selectionState[key] || {};
      var display = item.label || item.value || '';
      if (!display) {
        continue;
      }
      parts.push(key + ': ' + display);
    }
    return parts.join('; ');
  }

  function resolveSelectionToken(token) {
    if (!token) {
      return '';
    }
    var normalized = String(token).trim();
    if (!normalized) {
      return '';
    }
    if (normalized === 'selection_summary') {
      return getSelectionSummary();
    }
    if (normalized === 'selection_json') {
      try {
        return JSON.stringify(cloneSelectionState());
      } catch (e) {
        return '';
      }
    }
    var parts = normalized.split('.');
    var baseKey = parts[0];
    var item = selectionState[baseKey];
    if (!item) {
      return '';
    }
    if (parts.length === 1) {
      return item.label || item.value || '';
    }
    if (parts[1] === 'value') {
      return item.value || '';
    }
    if (parts[1] === 'label') {
      return item.label || item.value || '';
    }
    return '';
  }

  function applySelectionTemplate(template) {
    if (!template) {
      return '';
    }
    return String(template).replace(
      /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g,
      function(match, token) {
        return resolveSelectionToken(token) || '';
      }
    );
  }

  function syncSelectionAttributes(selectionKey) {
    if (!selectionKey || !document.querySelectorAll) {
      return;
    }
    var selector =
      '[data-openwebui-select="' +
      String(selectionKey).replace(/"/g, '\\"') +
      '"]';
    var elements = document.querySelectorAll(selector);
    var current = selectionState[selectionKey];
    for (var i = 0; i < elements.length; i += 1) {
      var element = elements[i];
      var isSelected =
        Boolean(current) &&
        getSelectionValue(element) === String(current.value || '');
      if (isSelected) {
        element.setAttribute('data-openwebui-selected', '1');
        element.setAttribute('aria-pressed', 'true');
      } else {
        element.removeAttribute('data-openwebui-selected');
        element.setAttribute('aria-pressed', 'false');
      }
    }
  }

  function setSelection(selectionKey, value, options) {
    var key = normalizeBridgeText(selectionKey);
    if (!key) {
      return false;
    }
    var opts = options || {};
    var mode = String(opts.mode || 'single').toLowerCase();
    var normalizedValue = normalizeBridgeText(value);
    var normalizedLabel = normalizeBridgeText(
      opts.label == null ? normalizedValue : opts.label
    );
    if (!normalizedValue) {
      return false;
    }

    if (mode === 'toggle') {
      var current = selectionState[key];
      if (current && String(current.value || '') === normalizedValue) {
        delete selectionState[key];
      } else {
        selectionState[key] = {
          value: normalizedValue,
          label: normalizedLabel || normalizedValue,
        };
      }
    } else {
      selectionState[key] = {
        value: normalizedValue,
        label: normalizedLabel || normalizedValue,
      };
    }

    syncSelectionAttributes(key);
    dispatchBridgeEvent('openwebui:selection-change', {
      key: key,
      selection: selectionState[key] || null,
      state: cloneSelectionState(),
      summary: getSelectionSummary(),
    });
    return true;
  }

  function applySelectionFromElement(element) {
    var selectionKey = getSelectionKey(element);
    if (!selectionKey) {
      return false;
    }
    return setSelection(selectionKey, getSelectionValue(element), {
      label: getSelectionLabel(element),
      mode: getSelectionMode(element),
    });
  }

  function resolvePromptActionValue(element) {
    var directValue = getPromptActionValue(element);
    if (directValue) {
      return directValue;
    }
    return applySelectionTemplate(getPromptTemplateValue(element));
  }

  function resolveCopyActionValue(element) {
    var directValue = getCopyActionValue(element);
    if (directValue) {
      return directValue;
    }
    return applySelectionTemplate(getCopyTemplateValue(element));
  }

  function getDeclarativeActionRaw(element) {
    if (!element || !element.getAttribute) {
      return '';
    }
    return (
      element.getAttribute('data-openwebui-action') ||
      element.getAttribute('data-openwebui-mode') ||
      ''
    ).trim().toLowerCase();
  }

  function getDeclarativeActionType(element, promptValue, linkValue, copyValue) {
    var rawAction = getDeclarativeActionRaw(element);
    var hasPrompt = Boolean(promptValue);
    var hasLink = Boolean(linkValue);
    var hasCopy = Boolean(copyValue);

    if (!rawAction) {
      if (hasPrompt) {
        return 'send_prompt';
      }
      if (hasCopy) {
        return 'copy_text';
      }
      if (hasLink) {
        return 'open_link';
      }
      return '';
    }

    if (
      rawAction === 'prompt' ||
      rawAction === 'send' ||
      rawAction === 'send_prompt' ||
      rawAction === 'send-prompt' ||
      rawAction === 'continue'
    ) {
      return 'send_prompt';
    }

    if (
      rawAction === 'fill' ||
      rawAction === 'fill_prompt' ||
      rawAction === 'fill-prompt' ||
      rawAction === 'input' ||
      rawAction === 'input_prompt' ||
      rawAction === 'input-prompt' ||
      rawAction === 'input:prompt' ||
      rawAction === 'prefill'
    ) {
      return 'fill_prompt';
    }

    if (
      rawAction === 'submit' ||
      rawAction === 'submit_prompt' ||
      rawAction === 'submit-prompt' ||
      rawAction === 'submit_current' ||
      rawAction === 'submit-current' ||
      rawAction === 'action:submit'
    ) {
      return 'submit_prompt';
    }

    if (
      rawAction === 'copy' ||
      rawAction === 'copy_text' ||
      rawAction === 'copy-text' ||
      rawAction === 'clipboard'
    ) {
      return 'copy_text';
    }

    if (
      rawAction === 'link' ||
      rawAction === 'open' ||
      rawAction === 'open_link' ||
      rawAction === 'open-link' ||
      rawAction === 'url' ||
      rawAction === 'href'
    ) {
      return 'open_link';
    }

    return '';
  }

  function hasInlineClickHandler(element) {
    if (!element || !element.getAttribute) {
      return false;
    }
    return Boolean((element.getAttribute('onclick') || '').trim());
  }

  function forceDeclarativeBinding(element) {
    if (!element || !element.getAttribute) {
      return false;
    }
    var rawValue =
      element.getAttribute('data-openwebui-force-declarative') ||
      element.getAttribute('data-force-declarative') ||
      '';
    return /^(1|true|yes)$/i.test(String(rawValue).trim());
  }

  function shouldSkipDeclarativeBinding(element) {
    if (!element || !element.getAttribute) {
      return false;
    }
    if (forceDeclarativeBinding(element)) {
      return false;
    }
    return hasInlineClickHandler(element);
  }

  function decorateDeclarativeActionElement(element) {
    if (!element || !element.getAttribute || !element.setAttribute) {
      return;
    }
    var promptValue = resolvePromptActionValue(element);
    var linkValue = getLinkActionValue(element);
    var copyValue = resolveCopyActionValue(element);
    var actionType = getDeclarativeActionType(
      element,
      promptValue,
      linkValue,
      copyValue
    );
    var hasSelection = Boolean(getSelectionKey(element));
    if (!actionType && !hasSelection) {
      return;
    }
    if (!isInteractiveTag(element)) {
      if (!element.getAttribute('role')) {
        element.setAttribute('role', 'button');
      }
      if (!element.hasAttribute('tabindex')) {
        element.setAttribute('tabindex', '0');
      }
    }
    if (!element.style.cursor) {
      element.style.cursor = 'pointer';
    }
  }

  function decorateDeclarativeActionElements(rootNode) {
    var scope = rootNode && rootNode.querySelectorAll ? rootNode : document;
    if (!scope) {
      return;
    }
    if (rootNode && rootNode.matches && rootNode.matches(declarativeActionSelector)) {
      decorateDeclarativeActionElement(rootNode);
    }
    var elements = scope.querySelectorAll
      ? scope.querySelectorAll(declarativeActionSelector)
      : [];
    for (var i = 0; i < elements.length; i += 1) {
      decorateDeclarativeActionElement(elements[i]);
    }
  }

  function handleDeclarativeAction(element) {
    if (!element || shouldSkipDeclarativeBinding(element)) {
      return false;
    }
    var selectionChanged = applySelectionFromElement(element);
    var promptValue = resolvePromptActionValue(element);
    var linkValue = getLinkActionValue(element);
    var copyValue = resolveCopyActionValue(element);
    var actionType = getDeclarativeActionType(
      element,
      promptValue,
      linkValue,
      copyValue
    );

    if (actionType === 'send_prompt' && promptValue) {
      sendPrompt(promptValue);
      return true;
    }

    if (actionType === 'fill_prompt' && promptValue) {
      fillPrompt(promptValue);
      return true;
    }

    if (actionType === 'submit_prompt') {
      submitCurrentPrompt();
      return true;
    }

    if (actionType === 'copy_text' && copyValue) {
      copyText(copyValue);
      return true;
    }

    if (actionType === 'open_link' && linkValue) {
      openLink(linkValue);
      return true;
    }
    return selectionChanged;
  }

  function maybeHandleDeclarativeActionFromTarget(target) {
    if (!target || !target.closest) {
      return false;
    }
    var element = target.closest(declarativeActionSelector);
    return handleDeclarativeAction(element);
  }

  function isPrimaryClickEvent(event) {
    if (!event) {
      return true;
    }
    if (typeof event.button === 'number' && event.button !== 0) {
      return false;
    }
    return !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);
  }

  function stopHandledEvent(event) {
    if (!event) {
      return;
    }
    if (event.preventDefault) {
      event.preventDefault();
    }
    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }
    if (event.stopPropagation) {
      event.stopPropagation();
    }
  }

  function exposeReservedGlobal(name, fn) {
    try {
      Object.defineProperty(window, name, {
        configurable: false,
        enumerable: false,
        get: function() {
          return fn;
        },
        set: function() {
          try {
            console.warn(
              '[OpenWebUIBridge] Ignored overwrite attempt for reserved helper:',
              name
            );
          } catch (e) {}
        },
      });
    } catch (e) {
      window[name] = fn;
    }
  }

  exposeReservedGlobal('sendPrompt', sendPrompt);
  exposeReservedGlobal('submitPrompt', sendPrompt);
  exposeReservedGlobal('send_prompt', sendPrompt);
  exposeReservedGlobal('submit_prompt', sendPrompt);
  exposeReservedGlobal('sendMessage', sendPrompt);
  exposeReservedGlobal('send_message', sendPrompt);
  exposeReservedGlobal('fillPrompt', fillPrompt);
  exposeReservedGlobal('fill_prompt', fillPrompt);
  exposeReservedGlobal('inputPrompt', fillPrompt);
  exposeReservedGlobal('input_prompt', fillPrompt);
  exposeReservedGlobal('submitCurrentPrompt', submitCurrentPrompt);
  exposeReservedGlobal('submit_current_prompt', submitCurrentPrompt);
  exposeReservedGlobal('submitChatInput', submitCurrentPrompt);
  exposeReservedGlobal('submit_chat_input', submitCurrentPrompt);
  exposeReservedGlobal('copyText', copyText);
  exposeReservedGlobal('copy_text', copyText);
  exposeReservedGlobal('openLink', openLink);
  exposeReservedGlobal('open_link', openLink);
  exposeReservedGlobal('reportHeight', reportHeightBridge);
  exposeReservedGlobal('report_height', reportHeightBridge);
  window.OpenWebUIBridge = {
    prompt: sendPrompt,
    fill: fillPrompt,
    submit: submitCurrentPrompt,
    copy: copyText,
    sendPrompt: sendPrompt,
    fillPrompt: fillPrompt,
    inputPrompt: fillPrompt,
    submitCurrentPrompt: submitCurrentPrompt,
    submitChatInput: submitCurrentPrompt,
    submitPrompt: sendPrompt,
    send_prompt: sendPrompt,
    fill_prompt: fillPrompt,
    input_prompt: fillPrompt,
    submit_current_prompt: submitCurrentPrompt,
    submit_chat_input: submitCurrentPrompt,
    copyText: copyText,
    copy_text: copyText,
    submit_prompt: sendPrompt,
    sendMessage: sendPrompt,
    send_message: sendPrompt,
    openLink: openLink,
    open_link: openLink,
    reportHeight: reportHeightBridge,
    report_height: reportHeightBridge,
    setSelection: setSelection,
    getSelection: function(key) {
      return cloneSelectionState()[String(key || '').trim()] || null;
    },
    getSelections: cloneSelectionState,
    selectionSummary: getSelectionSummary,
    applyTemplate: applySelectionTemplate,
    syncTheme: syncTheme,
    bindInteractions: decorateDeclarativeActionElements,
    decorateInteractions: decorateDeclarativeActionElements,
  };
  window.openWebUI = window.OpenWebUIBridge;
  window.openwebui = window.OpenWebUIBridge;

  syncTheme();
  attachThemeObservers();
  attachHeightObservers();

  window.addEventListener('load', function() {
    attachHeightObservers();
    scheduleHeight(0, true);
  });
  window.addEventListener('resize', function() {
    scheduleHeight(0, false);
  });
  document.addEventListener(
    'toggle',
    function() {
      scheduleHeight(50, true);
    },
    true
  );
  document.addEventListener(
    'click',
    function(event) {
      if (!isPrimaryClickEvent(event)) {
        return;
      }
      if (maybeHandleDeclarativeActionFromTarget(event.target)) {
        stopHandledEvent(event);
      }
    },
    false
  );
  document.addEventListener(
    'keydown',
    function(event) {
      var key = event.key || event.code;
      if (key !== 'Enter' && key !== ' ') {
        return;
      }
      if (event.repeat) {
        return;
      }
      if (maybeHandleDeclarativeActionFromTarget(event.target)) {
        stopHandledEvent(event);
      }
    },
    false
  );
  document.addEventListener('DOMContentLoaded', function() {
    syncTheme();
    attachHeightObservers();
    decorateDeclarativeActionElements(document);
    scheduleHeight(0, true);
  });

  decorateDeclarativeActionElements(document);

  try {
    var themeMedia = window.matchMedia('(prefers-color-scheme: dark)');
    if (themeMedia && themeMedia.addEventListener) {
      themeMedia.addEventListener('change', syncTheme);
    } else if (themeMedia && themeMedia.addListener) {
      themeMedia.addListener(syncTheme);
    }
  } catch (e) {}

  scheduleHeight(0, true);
})();
</script>
"""


# Shared SQL Patterns
SQL_AND_STATE_PATTERNS = (
    "\n<sql_and_state_patterns>\n"
    "The `sql` tool provides access to Copilot session databases. Use that tool whenever structured, queryable data would help you work more effectively.\n"
    "These SQL databases (`session` and, when available, `session_store`) are tool-provided Copilot session stores, not the main OpenWebUI application database. Access them through the `sql` tool rather than by inventing your own application-database connection flow.\n"
    "**Session database (database: `session`, the default):** The per-session database persists across the session but is isolated from other sessions.\n"
    "In this environment, the session metadata directory is typically `COPILOTSDK_CONFIG_DIR/session-state/<chat_id>/`, and the SQLite file is usually stored there as `session.db`.\n"
    "**Default task-tracking tables:**\n"
    "- `todos`: id, title, description, status (pending/in_progress/done/blocked), created_at, updated_at\n"
    "- `todo_deps`: todo_id, depends_on (for dependency tracking)\n"
    "These are the preferred SQL tables for task tracking in this environment. In many sessions they are already present; if they are missing and you genuinely need SQL-backed task tracking, create them with the documented schema below instead of inventing a different task table.\n"
    "The UI may inject a `<todo_status>...</todo_status>` summary into user messages as a convenience reminder derived from the same session state. Treat that reminder as helpful context, but prefer the `sql` tool's live tables as the source of truth when available.\n"
    "Create any tables you need. The database is yours to use for any purpose:\n"
    "- Load and query data (CSVs, API responses, file listings)\n"
    "- Track progress on batch operations\n"
    "- Store intermediate results for multi-step analysis\n"
    "- Any workflow where SQL queries would help\n"
    "Examples: `CREATE TABLE csv_data (...)`, `CREATE TABLE api_results (...)`, `CREATE TABLE files_to_process (...)`.\n"
    "Use the `todos` and `todo_deps` tables to track work. Reserve custom tables such as `interactive_controls` for UI/control state rather than task tracking.\n"
    "Creating todos with good IDs and descriptions: Use descriptive kebab-case IDs (not `t1`, `t2`). Include enough detail that the todo can be executed without referring back to the plan.\n"
    "Example: `INSERT INTO todos (id, title, description) VALUES ('user-auth', 'Create user auth module', 'Implement JWT-based authentication in src/auth/ with login, logout, and token refresh endpoints. Use bcrypt for password hashing.');`\n"
    "Todo status workflow:\n"
    "- `pending`: Todo is waiting to be started\n"
    "- `in_progress`: You are actively working on this todo (set this before starting)\n"
    "- `done`: Todo is complete\n"
    "- `blocked`: Todo cannot proceed (document why in description)\n"
    "IMPORTANT: Always update todo status as you work. Before starting a todo: `UPDATE todos SET status = 'in_progress' WHERE id = 'X'`. After completing a todo: `UPDATE todos SET status = 'done' WHERE id = 'X'`. Check todo_status in each user message to see what is ready.\n"
    "Dependencies: `INSERT INTO todo_deps (todo_id, depends_on) VALUES ('api-routes', 'user-model');`\n"
    "When to use SQL vs `plan.md`:\n"
    "- Use `plan.md` for prose: problem statements, approach notes, high-level planning\n"
    "- Use SQL for operational data: todo lists, test cases, batch items, status tracking\n"
    "Common patterns:\n"
    "Todo tracking with dependencies:\n"
    "`CREATE TABLE todos ( id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT DEFAULT 'pending' );`\n"
    "`CREATE TABLE todo_deps (todo_id TEXT, depends_on TEXT, PRIMARY KEY (todo_id, depends_on));`\n"
    "Ready query: `SELECT t.* FROM todos t WHERE t.status = 'pending' AND NOT EXISTS ( SELECT 1 FROM todo_deps td JOIN todos dep ON td.depends_on = dep.id WHERE td.todo_id = t.id AND dep.status != 'done' );`\n"
    "TDD test case tracking:\n"
    "`CREATE TABLE test_cases ( id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT DEFAULT 'not_written' );`\n"
    "`SELECT * FROM test_cases WHERE status = 'not_written' LIMIT 1;`\n"
    "`UPDATE test_cases SET status = 'written' WHERE id = 'tc1';`\n"
    "Batch item processing (for example PR comments):\n"
    "`CREATE TABLE review_items ( id TEXT PRIMARY KEY, file_path TEXT, comment TEXT, status TEXT DEFAULT 'pending' );`\n"
    "`SELECT * FROM review_items WHERE status = 'pending' AND file_path = 'src/auth.ts';`\n"
    "`UPDATE review_items SET status = 'addressed' WHERE id IN ('r1', 'r2');`\n"
    "Session state (key-value):\n"
    "`CREATE TABLE session_state (key TEXT PRIMARY KEY, value TEXT);`\n"
    "`INSERT OR REPLACE INTO session_state (key, value) VALUES ('current_phase', 'testing');`\n"
    "`SELECT value FROM session_state WHERE key = 'current_phase';`\n\n"
    "**Session store (database: `session_store`, read-only):** The global session store contains history from all past sessions. Only read-only operations are allowed.\n"
    "Schema:\n"
    "- `sessions` — id, cwd, repository, branch, summary, created_at, updated_at\n"
    "- `turns` — session_id, turn_index, user_message, assistant_response, timestamp\n"
    "- `checkpoints` — session_id, checkpoint_number, title, overview, history, work_done, technical_details, important_files, next_steps\n"
    "- `session_files` — session_id, file_path, tool_name (edit/create), turn_index, first_seen_at\n"
    "- `session_refs` — session_id, ref_type (commit/pr/issue), ref_value, turn_index, created_at\n"
    "- `search_index` — FTS5 virtual table (content, session_id, source_type, source_id)\n"
    "Use `WHERE search_index MATCH 'query'` for full-text search. Source types include `turn`, `checkpoint_overview`, `checkpoint_history`, `checkpoint_work_done`, `checkpoint_technical`, `checkpoint_files`, `checkpoint_next_steps`, and `workspace_artifact`.\n"
    "Query expansion strategy (important): The session store uses keyword-based search (FTS5 + LIKE), not vector/semantic search. You must act as your own embedder by expanding conceptual queries into multiple keyword variants.\n"
    "- For 'what bugs did I fix?' search for: `bug`, `fix`, `error`, `crash`, `regression`, `debug`, `broken`, `issue`\n"
    "- For 'UI work' search for: `UI`, `rendering`, `component`, `layout`, `CSS`, `styling`, `display`, `visual`\n"
    "- For 'performance' search for: `performance`, `perf`, `slow`, `fast`, `optimize`, `latency`, `cache`, `memory`\n"
    "Use FTS5 OR syntax such as `MATCH 'bug OR fix OR error OR crash OR regression'`. Use LIKE for broader substring matching. Combine structured queries (branch names, file paths, refs) with text search for best recall. Start broad, then narrow down.\n"
    "Example queries:\n"
    "- `SELECT content, session_id, source_type FROM search_index WHERE search_index MATCH 'auth OR login OR token OR JWT OR session' ORDER BY rank LIMIT 10;`\n"
    "- `SELECT DISTINCT s.id, s.branch, substr(t.user_message, 1, 200) as ask FROM sessions s JOIN turns t ON t.session_id = s.id AND t.turn_index = 0 WHERE t.user_message LIKE '%bug%' OR t.user_message LIKE '%fix%' OR t.user_message LIKE '%error%' OR t.user_message LIKE '%crash%' ORDER BY s.created_at DESC LIMIT 20;`\n"
    "- `SELECT s.id, s.summary, sf.tool_name FROM session_files sf JOIN sessions s ON sf.session_id = s.id WHERE sf.file_path LIKE '%auth%';`\n"
    "- `SELECT s.* FROM sessions s JOIN session_refs sr ON s.id = sr.session_id WHERE sr.ref_type = 'pr' AND sr.ref_value = '42';`\n"
    "- `SELECT s.id, s.summary, t.user_message, t.assistant_response FROM turns t JOIN sessions s ON t.session_id = s.id WHERE t.timestamp >= date('now', '-7 days') ORDER BY t.timestamp DESC LIMIT 20;`\n"
    "- `SELECT sf.file_path, COUNT(DISTINCT sf.session_id) as session_count FROM session_files sf JOIN sessions s ON sf.session_id = s.id WHERE s.repository = 'owner/repo' AND sf.tool_name = 'edit' GROUP BY sf.file_path ORDER BY session_count DESC LIMIT 20;`\n"
    "- `SELECT checkpoint_number, title, overview FROM checkpoints WHERE session_id = 'abc-123' ORDER BY checkpoint_number;`\n"
    "</sql_and_state_patterns>\n"
)


TONE_AND_STYLE_PATTERNS = (
    "\n<tone_and_style_patterns>\n"
    "Tone and style:\n"
    "- Be concise and direct.\n"
    "- Make tool calls without unnecessary explanation.\n"
    "- Use the richer OpenWebUI AI Chat interface when the task benefits from Markdown structure, code blocks, diagrams, previews, or embedded UI. Prefer Rich UI for HTML presentation by default; only prefer artifacts when the user explicitly asks for artifacts.\n"
    "- When searching the file system for files or text, stay in the current working directory or child directories of the cwd unless absolutely necessary.\n"
    "- When searching code, the preference order for tools is: code intelligence tools (if available) > LSP-based tools (if available) > glob > grep with glob pattern > shell.\n"
    "- Remember that your output will be displayed in the OpenWebUI AI Chat page rather than a plain command line interface, so preserve the original efficiency rules while taking advantage of chat-native presentation features.\n"
    "</tone_and_style_patterns>\n"
)


TOOL_USAGE_EFFICIENCY_PATTERNS = (
    "\n<tool_usage_efficiency_patterns>\n"
    "Tool usage efficiency:\n"
    "CRITICAL: Minimize the number of LLM turns by using tools efficiently.\n"
    "- USE PARALLEL TOOL CALLING: when you need to perform multiple independent operations, make all tool calls in a single response instead of serializing them across multiple responses.\n"
    "- Chain related shell commands with `&&` instead of separate calls when practical.\n"
    "- Suppress verbose output (use `--quiet`, `--no-pager`, or pipe to `grep` / `head` when appropriate).\n"
    "</tool_usage_efficiency_patterns>\n"
)


NATIVE_BEHAVIOR_PATTERNS = (
    "\n<native_behavior_patterns>\n"
    "- Reflect on tool or command output before choosing the next step.\n"
    "- Clean up temporary files at the end of the task.\n"
    "- Prefer editing existing files with edit/view style tools instead of creating replacements when the target file already exists, to reduce data-loss risk.\n"
    "- Ask for guidance if uncertainty materially blocks safe progress.\n"
    "- Do not create markdown files inside the repository for planning, notes, or tracking unless the user explicitly asks for a specific file by name or path. Session artifacts such as `plan.md` are allowed only in the dedicated session metadata directory (for example `COPILOTSDK_CONFIG_DIR/session-state/<chat_id>/plan.md`), alongside runtime state files such as the per-session `session.db`.\n"
    "- Treat the environment as shared and non-sandboxed. Avoid disruptive operations, broad deletions, or assumptions that no one else is using the workspace.\n"
    "- If a request is blocked by safety or policy constraints, stop and explain briefly instead of working around the restriction.\n"
    "- When answering the user, include a brief description or summary of the requested work before deeper details when that helps orient the response.\n"
    "</native_behavior_patterns>\n"
)


SEARCH_AND_AGENT_PATTERNS = (
    "\n<search_and_agent_patterns>\n"
    "Built on ripgrep, not standard grep. Key notes: literal braces may need escaping (for example `interface\\{\\}` to find `interface{}`); default behavior usually matches within single lines only; use multiline only for cross-line patterns; default to files-with-matches mode for efficiency when appropriate.\n"
    "Fast file pattern matching works with any codebase size and supports standard glob patterns with wildcards such as `*`, `**`, `?`, and `{a,b}`. Use file pattern matching when you need to find files by name patterns. For searching file contents, use grep-style tools instead.\n"
    "When to use sub-agents: Prefer using relevant sub-agents instead of doing the work yourself. When relevant sub-agents are available, your role changes from a coder making changes to a manager of software engineers. Your job is to utilize these sub-agents to deliver the best results as efficiently as possible.\n"
    "When to use the explore agent instead of grep/glob: use it for questions needing understanding or synthesis, for multi-step searches requiring analysis, or when you want a summarized answer rather than raw results.\n"
    "When to use custom agents: If both a built-in agent and a custom agent could handle a task, prefer the custom agent because it has specialized knowledge for this environment.\n"
    "How to use sub-agents: Instruct the sub-agent to do the task itself. Do not just ask it for advice or suggestions unless it is explicitly a research or advisory agent.\n"
    "After a sub-agent completes: If the sub-agent replies that it succeeded, trust the accuracy of its response, but at least spot-check critical changes. If the sub-agent reports that it failed or behaved differently than expected, refine the prompt and call it again. If it fails repeatedly, you may attempt to do the task yourself.\n"
    "If code intelligence tools are available (semantic search, symbol lookup, call graphs, class hierarchies, summaries), prefer them over grep/rg/glob when searching for code symbols, relationships, or concepts.\n"
    "Use glob/grep for targeted single searches: simple searches where you know what to find, where you are looking for something specific rather than discovering something unknown, and where you need results in your context immediately.\n"
    "Best practices: Use glob patterns to narrow down which files to search (for example `/UserSearch.ts`, `**/*.ts`, or `src/**/*.test.js`). Prefer calling in the following order: Code Intelligence Tools (if available) > LSP (if available) > glob > grep with glob pattern. PARALLELIZE: make multiple independent search calls in one call.\n"
    "</search_and_agent_patterns>\n"
)

RICHUI_VISUALIZATION_PATTERNS = (
    "\n<richui_visualization_patterns>\n"
    "When generating Rich UI pages, think like a visualization builder, not a static document writer.\n"
    "- Rich UI pages should feel like exploration interfaces embedded in chat.\n"
    "- Keep explanatory prose primarily in your assistant response. Keep the HTML focused on structure, controls, diagrams, metrics, and interactive navigation.\n"
    '- Use the **recommended interaction contract** to avoid ambiguity: (1) `data-openwebui-prompt="..."` for immediate chat continuation, (2) `data-openwebui-prompt="..." data-openwebui-action="fill"` to prefill the chat input without sending, (3) `data-openwebui-action="submit"` to submit the current chat input, and (4) `data-openwebui-link="https://..."` for external links.\n'
    "- Treat `data-openwebui-copy`, `data-openwebui-select`, and template placeholders such as `data-openwebui-prompt-template` as **advanced optional patterns**. Use them only when the page truly needs copy buttons or pick-then-act selection flows.\n"
    "- Only use bridge JavaScript helpers when local state or dynamic code makes declarative attributes awkward. The recommended object methods are `window.OpenWebUIBridge.prompt(text)`, `fill(text)`, `submit()`, `openLink(url)`, and `reportHeight()`.\n"
    "- Write prompt text as a natural, specific follow-up request. Avoid vague labels like 'More' or 'Explain'. Prefer prompts such as 'Break down the reviewer agent responsibilities and handoff rules.'\n"
    "- Use local JavaScript only for instant client-side state changes such as tabs, filters, sliders, zoom, and expand/collapse. Use prompt/fill/submit actions when the user is asking the model to explain, compare, personalize, evaluate, or generate next steps.\n"
    '- Do not mix declarative prompt/link attributes with inline `onclick` on the same element unless you intentionally add `data-openwebui-force-declarative="1"`.\n'
    "- If a control looks clickable, it must either submit a prompt, prefill the input, open a real URL, or visibly change local state. Do not generate dead controls.\n"
    "- Prefer actionable labels such as 'Deep dive', 'Compare approaches', 'Draft reply', 'Turn into TODOs', or 'Generate rollout plan'.\n"
    "- External references should use `openLink(url)` or declarative link attributes rather than plain iframe navigation.\n"
    '- **Decision guide for controls**: If the user should get an answer immediately, use `data-openwebui-prompt`. If the user should review/edit text first, use `data-openwebui-action="fill"`. If the page is a final review step for already-prepared input, use `data-openwebui-action="submit"`. If the target is outside chat, use `data-openwebui-link`. Only use copy/select/template features for explicit advanced workflows.\n'
    "- **Avoid choice overload**: For most pages, 2-4 actions are enough. Prefer one primary action style per surface. Example: a dashboard should mostly use prompt actions; a drafting wizard should mostly use fill + submit; a documentation viewer should mostly use links.\n"
    "- **Multilingual UI rule**: Keep control labels short and concrete in the user's language. Prefer verb-first labels such as 'Explain', 'Draft in input', 'Send draft', 'Open docs', or their direct equivalents in the user's language.\n"
    "- **Minimal examples**:\n"
    '  1. Immediate answer: `<button data-openwebui-prompt="Explain this diagram step by step">Explain</button>`\n'
    '  2. Prefill only: `<button data-openwebui-prompt="Draft a migration checklist for this design" data-openwebui-action="fill">Draft in input</button>`\n'
    '  3. Submit current draft: `<button data-openwebui-action="submit">Send current draft</button>`\n'
    '  4. External docs: `<a data-openwebui-link="https://docs.example.com">Open docs</a>`\n'
    '  5. Advanced copy: `<button data-openwebui-copy="npm run build && npm test">Copy command</button>`\n'
    '  6. Advanced pick-then-act: `<button data-openwebui-select="role" data-openwebui-value="reviewer">Reviewer</button><button data-openwebui-prompt-template="Explain the responsibilities of {{role}}">Explain selected role</button>`\n'
    "</richui_visualization_patterns>\n"
)

# Base guidelines for all users
BASE_GUIDELINES = (
    "\n\n[Environment & Capabilities Context]\n"
    "You are a versatile AI Agent operating inside a live OpenWebUI instance, not a generic standalone terminal bot.\n"
    "You are an AI assistant operating within a high-capability Linux container environment (OpenWebUI).\n"
    f"{TONE_AND_STYLE_PATTERNS}"
    f"{TOOL_USAGE_EFFICIENCY_PATTERNS}"
    f"{RICHUI_VISUALIZATION_PATTERNS}"
    "\n"
    "**System Environment & User Privileges:**\n"
    "- **Host Product Context**: The user is interacting with you through the OpenWebUI chat interface. Treat OpenWebUI Tools, Built-in Tools, OpenAPI servers, MCP servers, session state, uploaded files, and installed skills as part of the same active application instance.\n"
    "- **Output Environment**: You are rendering in the **OpenWebUI Chat Page**, a modern, interactive web interface. Optimize your output format to leverage Markdown for the best UI experience.\n"
    "- **Root Access**: You are running as **root**. You have **READ access to the entire container file system** but you **MUST ONLY WRITE** to your designated persistent workspace directory (structured as `.../user_id/chat_id/`). All other system areas are strictly READ-ONLY.\n"
    "- **STRICT FILE CREATION RULE**: You are **PROHIBITED** from creating or editing files outside of your specific workspace path. Never place files in `/root`, `/tmp`, or `/app` (unless specifically instructed for analysis, but writing is banned). Every file operation (`create`, `edit`, `bash`) MUST use the absolute path provided in your `Session Context` below.\n"
    "- **Filesystem Layout (/app)**:\n"
    "  - `/app/backend`: Python backend source code. You can analyze core package logic here.\n"
    "  - `/app/build`: Compiled frontend assets (assets, static, pyodide, index.html).\n"
    "- **Rich Python Environment**: You can natively import and use any installed OpenWebUI dependencies. You have access to a wealth of libraries (e.g., for data processing, utility functions). However, you **MUST NOT** install new packages in the global environment to avoid polluting the system. If you need additional dependencies, you MUST create a virtual environment (`venv`) within your designated workspace directory and install packages there.\n"
    "- **Tool Availability**: You may have access to various tools (OpenWebUI Built-ins, Custom Tools, OpenAPI Servers, or MCP Servers) depending on the user's current configuration. If tools are visible in your session metadata, use them proactively to enhance your task execution.\n"
    "- **Skills vs Tools — CRITICAL DISTINCTION**:\n"
    "  - **Tools** (for example shell tools, file tools, custom functions, MCP tools, etc.) are **executable functions** you call directly. They take inputs, run code or API calls, and return results.\n"
    "  - **Skills** are **context-injected Markdown instructions** (from `SKILL.md` files in a skill directory). They are NOT callable functions and NOT shell commands. When the Copilot SDK detects intent, it reads the relevant `SKILL.md` and injects its content into your context automatically — you then follow those instructions using your standard tools.\n"
    "  - **Skill directory structure**: A skill lives in a subdirectory under the Skills Directory. **Only `SKILL.md` is required** — all other contents are optional resources that the skill may provide:\n"
    "    - `scripts/` — helper Python or shell scripts; invoke via `bash` / `python3` **only when SKILL.md instructs you to**.\n"
    "    - `references/` — supplementary Markdown documents (detailed workflows, examples); read them with the session's file-reading tool as directed.\n"
    "    - `templates/` — file templates to copy or fill in as part of the skill workflow.\n"
    "    - Any other supporting files (data, configs, assets) — treat them as resources described in `SKILL.md`.\n"
    "  - **Rule**: Always start by reading `SKILL.md`. It is the authoritative entry point. Other files in the directory only matter if `SKILL.md` references them.\n"
    "  - **Deterministic skill management**: For install/list/create/edit/delete/show operations, MUST use the `manage_skills` tool (do not rely on skill auto-trigger).\n"
    "  - **NEVER run a skill name as a shell command** (e.g., do NOT run `docx` or any skill name via `bash`). The skill name is not a binary. Scripts inside `scripts/` are helpers to be called explicitly as instructed.\n"
    "  - **How to identify a skill**: Skills appear in your context as injected instruction blocks (usually with a heading matching the skill name). Tools appear in your available-tools list.\n"
    "\n"
    "**Execution & Tooling Strategy:**\n"
    "1. **Maximize Native Capability**: Prefer the most structured/native tool available over raw shell usage. Use OpenWebUI tools, built-in tools, MCP servers, OpenAPI tools, and SDK-native capabilities proactively when they are relevant and actually available in the current session.\n"
    "2. **Efficient Tool Use**: When multiple independent reads/searches/tool calls can be done together, batch or parallelize them in the same turn. Chain related shell commands, suppress unnecessary verbosity, and avoid wasting turns on tiny incremental probes.\n"
    "3. **Search Preference**: Prefer semantic/code-aware, LSP-based, or otherwise structured search tools when available. Otherwise search the current workspace first, then expand scope only when necessary. Use shell-based searching as a fallback, not the default.\n"
    "4. **Report Intent Discipline**: If an intent-reporting tool such as `report_intent` is available, use it on the first tool-calling turn after a new request and again when intent changes materially, but always alongside at least one substantive tool call rather than in isolation. **CRITICAL**: Always phrase the intent string in the **SAME LANGUAGE** as the user's latest query (e.g., if the user asks in Chinese, report intent in Chinese; if in English, report in English).\n"
    "5. **Minimal, Surgical Changes**: Make the smallest set of changes needed to satisfy the user's request. Do not fix unrelated issues, do not refactor broadly without clear benefit, and do not modify working code unless it is required. Only run linters, builds, and tests that already exist; do not add new infrastructure unless directly required.\n"
    "6. **Validation First**: After making changes, validate with the existing tests, checks, or the smallest relevant verification path already present in the environment. Reflect on the command or tool output before continuing, and report clearly if validation could not be completed.\n"
    "7. **Task Tracking**: If TODO or task-management tools are available, use them for multi-step work and keep progress synchronized. Preserve the existing TODO-related behavior and present concise user-facing progress when the workflow expects it. Prefer the built-in SQLite `todos` and `todo_deps` tables when they already exist, use `plan.md` for prose planning/state visible to the UI, and only create new SQL tables when the task cannot be represented with the default storage.\n"
    "8. **Sub-Agent Leverage**: If specialized sub-agents are available and a task is better delegated (for example, broad codebase exploration or targeted implementation), prefer using them and then synthesize the result.\n"
    "9. **Environment Awareness**: Do not assume a tool exists; follow the actual tool list, current workspace boundaries, and the active restrictions of this OpenWebUI instance.\n"
    "\n"
    "**Formatting & Presentation Directives:**\n"
    "1. **Markdown Excellence**: Leverage full **Markdown** capabilities (headers, bold, italics, tables, lists) to structure your response professionally for the chat interface.\n"
    "2. **Advanced Visualization**: Use **Mermaid** for flowcharts/diagrams and **LaTeX** for math. **IMPORTANT**: Always wrap Mermaid code within a standard ` ```mermaid ` code block to ensure it is rendered correctly by the UI.\n"
    "3. **Interactive HTML Delivery**: **Premium Delivery Protocol**: For web applications, you MUST perform two actions:\n"
    "   - 1. **Persist**: Create the file in the workspace (e.g., `index.html`) for project structure.\n"
    "   - 2. **Publish & Embed**: Call `publish_file_from_workspace(filename='your_file.html')` only after the file-writing tool has completed successfully. Never batch the write step and the publish step into the same parallel tool round. This will automatically trigger the **Premium Experience** by directly embedding the interactive component using the action-style return.\n"
    "   - **CRITICAL ANTI-INLINE RULE**: Never output your *own* raw HTML source code directly in the chat. You MUST ALWAYS persist the HTML to a file and call `publish_file_from_workspace`.\n"
    "   - **Preferred default**: Use **Rich UI mode** (`embed_type='richui'`) for HTML presentation unless the user explicitly asks for **artifacts**.\n"
    "   - **CRITICAL**: When using this protocol in **Rich UI mode** (`embed_type='richui'`), **DO NOT** output the raw HTML code in a code block. Provide ONLY the **[Preview]** and **[Download]** links returned by the tool. The interactive embed will appear automatically after your message finishes.\n"
    "   - **Primary language rule**: The visible UI copy of generated HTML pages must use the **same language as the user's latest message** by default, unless the user explicitly requests another language or the task itself requires multilingual output. This includes titles, buttons, labels, helper text, empty states, and validation messages.\n"
    "   - **Built-in Rich UI bridge**: Rich UI embeds automatically expose a small recommended API on `window.OpenWebUIBridge`: `prompt(text)` = submit text immediately, `fill(text)` = prefill the chat input without sending, `submit()` = submit the current chat input, `openLink(url)` = open an external URL, and `reportHeight()` = force iframe resizing. Advanced optional helpers also exist for `copy(text)` and structured selection (`setSelection`, `applyTemplate`), but do not use them unless the page genuinely needs those flows. Legacy aliases such as `sendPrompt(...)` remain supported for compatibility, but prefer the object methods above in newly generated pages. Do not redefine these reserved helper names in your page code.\n"
    '   - **Declarative interaction contract**: Prefer zero-JS bindings on clickable UI elements. Recommended patterns: `data-openwebui-prompt="..."` for immediate continuation, `data-openwebui-prompt="..." data-openwebui-action="fill"` for prefill-only flows, `data-openwebui-action="submit"` to send the current chat input, and `data-openwebui-link="https://..."` for external links. Advanced optional patterns: `data-openwebui-copy="..."` for copy buttons, and `data-openwebui-select="key" data-openwebui-value="value"` plus `data-openwebui-prompt-template="...{{key}}..."` for pick-then-act flows. The Rich UI bridge auto-binds these attributes and adds keyboard accessibility.\n'
    '   - **Ownership rule**: Do not mix declarative prompt/link attributes with inline `onclick` on the same element unless you intentionally add `data-openwebui-force-declarative="1"`. By default, inline `onclick` owns the click behavior.\n'
    "   - **No dead controls**: If you generate buttons, cards, tabs, diagram nodes, or CTA blocks that imply a follow-up action, they MUST either continue the chat, prefill the input, submit the current input, open a real URL, or be visibly marked as static. Do not generate decorative controls that do nothing.\n"
    "   - **Artifacts mode** (`embed_type='artifacts'`): Use this when the user explicitly asks for artifacts. You MUST provide the **[Preview]** and **[Download]** links. DO NOT output HTML code block. The system will automatically append the HTML visualization to the chat string.\n"
    "   - **Process Visibility**: While raw code is often replaced by links/frames, you SHOULD provide a **very brief Markdown summary** of the component's structure or key features (e.g., 'Generated login form with validation') before publishing. This keeps the user informed of the 'processing' progress.\n"
    "   - **Game/App Controls**: If your HTML includes keyboard controls (e.g., arrow keys, spacebar for games), you MUST include `event.preventDefault()` in your `keydown` listeners to prevent the parent browser page from scrolling.\n"
    "4. **Media & Files**: ALWAYS embed generated images, GIFs, and videos directly using `![caption](url)`. Supported formats like PNG, JPG, GIF, MOV, and MP4 should be shown as visual assets. Never provide plain text links for visual media.\n"
    "5. **File Delivery Protocol (Dual-Channel Delivery)**:\n"
    "     - **Definition**: **Artifacts** = content/code-block driven visual output in chat (typically with `html_embed`). **Rich UI** = tool/action returned embedded UI rendered by emitter in a persistent sandboxed iframe.\n"
    "     - **Philosophy**: Prefer **Rich UI** as the default HTML presentation because it shows the effect more directly in OpenWebUI. Use **Artifacts** only when the user explicitly asks for artifacts. Downloadable files remain **COMPLEMENTARY** and should still be published when needed.\n"
    "     - **The Rule**: When the user needs to *possess* data (download/export), you MUST publish it. Creating a local file alone is useless because the user cannot access your container.\n"
    "     - **Implicit Requests**: If asked to 'export', 'get link', or 'save', automatically trigger this sequence.\n"
    "     - **Execution Sequence**: 1. **Write Local**: Create file. 2. **Wait for the write tool result**: Confirm the file exists. 3. **Publish**: Call `publish_file_from_workspace` in a later tool round. 4. **Response Structure**:\n"
    "     - **Strict Link Validity Rule (CRITICAL)**: You are FORBIDDEN to fabricate, guess, or handcraft any preview/download URL. Links MUST come directly from a successful `publish_file_from_workspace` tool result in the same turn.\n"
    "     - **Failure Handling**: If publish fails or no tool result is returned, DO NOT output any fake/placeholder link. Instead, explicitly report publish failure and ask to retry publish.\n"
    "     - **No Pre-Publish Linking**: Never output links before running publish. 'Create file' alone is NOT enough to produce a valid user-facing link.\n"
    "     - **Allowed Link Formats (Whitelist)**: You MUST only output links matching these exact patterns from tool output: `/api/v1/files/{file_id}/content` (download/content) and `/api/v1/files/{file_id}/content/html` (HTML preview). Absolute form is also valid only when it is exactly `{base_url}` + one of the two paths.\n"
    "     - **Invalid Link Examples (Forbidden)**: Any handcrafted variants such as `/files/...`, `/api/files/...`, `/api/v1/file/...`, missing `/content`, manually appended custom routes, or local-workspace style paths like `/c/...`, `./...`, `../...`, `file://...` are INVALID and MUST NOT be output.\n"
    "     - **Auto-Correction Rule**: If you generated a non-whitelisted link (including `/c/...`), you MUST discard it, run/confirm `publish_file_from_workspace`, and only output the returned whitelisted URL.\n"
    "        - **For PDF files**: You MUST output ONLY Markdown links from the tool output (preview + download). **CRITICAL: NEVER output iframe/html_embed for PDF.**\n"
    "        - **For HTML files**: Prefer **Rich UI mode** (`embed_type='richui'`) by default so the effect is shown directly in chat. Output ONLY [Preview]/[Download]; do NOT output HTML block because Rich UI will render automatically via emitter. The page's primary language must follow the user's latest message unless the user explicitly asks for another language. If the HTML may need more space, add a clickable 'Full Screen' button inside your HTML design. Prefer the declarative interaction contract for buttons/cards/nodes: immediate send = `data-openwebui-prompt`, prefill-only = `data-openwebui-prompt` + `data-openwebui-action=\\\"fill\\\"`, submit current input = `data-openwebui-action=\\\"submit\\\"`, and external links = `data-openwebui-link`. Use `window.OpenWebUIBridge.prompt/fill/submit/openLink` only when local JavaScript truly needs it. Use copy/select/template capabilities only for explicit advanced needs such as copy buttons or pick-then-act dashboards. Use **Artifacts mode** (`embed_type='artifacts'`) only when the user explicitly asks for artifacts; in that case, still output ONLY [Preview]/[Download], and do NOT output any iframe/html block because the protocol will automatically append the html code block via emitter.\n"
    '        - **Rich UI interaction examples**: `<button data-openwebui-prompt=\\"Explain the hotfix workflow step by step\\">Explain</button>`, `<button data-openwebui-prompt=\\"Draft a rollout checklist for this design\\" data-openwebui-action=\\"fill\\">Draft in input</button>`, `<button data-openwebui-action=\\"submit\\">Send current draft</button>`, `<a data-openwebui-link=\\"https://git-scm.com/docs/git-worktree\\">Official docs</a>`, and advanced optional patterns such as `<button data-openwebui-copy=\\"npm run build && npm test\\">Copy command</button>` or `<button data-openwebui-select=\\"role\\" data-openwebui-value=\\"reviewer\\">Reviewer</button><button data-openwebui-prompt-template=\\"Explain the responsibilities of {{role}}\\">Explain selected role</button>`. Prefer these declarative attributes when generating cards, tiles, SVG nodes, or dashboard controls because they survive templating better than custom JavaScript.\n'
    "     - **URL Format**: You MUST use the exact preview/download URLs returned by the tool output, copied verbatim. They may be relative API paths or absolute URLs depending on the environment; never modify, concatenate, or reconstruct them manually.\n"
    "     - **Bypass RAG**: This protocol automatically handles S3 storage and bypasses RAG, ensuring 100% accurate data delivery.\n"
    "6. **TODO Visibility**: When TODO state changes, prefer the environment's embedded TODO widget and lightweight status surfaces. Do not repeat the full TODO list in the main answer unless the user explicitly asks for a textual TODO list or the text itself is the requested deliverable. When using SQL instead of `update_todo`, follow the environment's default workflow: create descriptive todo rows in `todos`, mark them `in_progress` before execution, mark them `done` after completion, and record blocking relationships in `todo_deps`.\n"
    "7. **Python Execution Standard**: For ANY task requiring Python logic (not just data analysis), you **MUST NOT** embed multi-line code directly in a shell command (e.g., using `python -c` or `<< 'EOF'`).\n"
    '   - **Exception**: Trivial one-liners (e.g., `python -c "print(1+1)"`) are permitted.\n'
    "   - **Protocol**: For everything else, you MUST:\n"
    "     1. **Create** a `.py` file in the workspace (e.g., `script.py`).\n"
    "     2. **Run** it using `python3 script.py`.\n"
    "   - **Reason**: This ensures code is debuggable, readable, and persistent.\n"
    "8. **Session Mode — Follow the Active Mode**: Your working style is driven by the **configured session mode**, not by arbitrary self-determination. Adapt your approach to match the mode:\n"
    "   - **`autopilot`**: Work autonomously through multiple steps without stopping after each action. Given an initial instruction, keep working continuously until the task is determined complete, a problem blocks progress, or the maximum continuation limit is reached. This is the most efficient mode for well-defined, clear tasks where the end goal is unambiguous. When the task is done, use the `task_complete` tool to signal completion.\n"
    "   - **`interactive`**: The standard back-and-forth mode. After each action, wait for the user's next instruction before proceeding. Best for exploratory, vague, or high-risk tasks where you need ongoing guidance. The `task_complete` tool is also available here for marking done items.\n"
    "   - **`plan`**: Always plan first before acting. For ambiguous, architectural, multi-stage, or high-impact tasks, research the codebase, surface constraints, and present a structured `plan.md` stored in the session metadata directory (`COPILOTSDK_CONFIG_DIR/session-state/<chat_id>/plan.md`). Wait for user approval — or explicitly accept the plan to switch into autopilot mode — before executing. The `task_complete` tool is also available here for marking done items.\n"
    "   - **Mode overrides**: If the user explicitly requests a different style (e.g., 'just do it' in plan mode), their direct instruction overrides the configured mode.\n"
    "   - **TODO tracking**: Task-completion and TODO-related tools (for example `task_complete` and any available todo-management tools) can be used freely in any mode — they are not restricted to plan mode.\n"
    "9. **Large Output Management**: If a tool execution output is truncated or saved to a temporary file (e.g., `/tmp/...`), DO NOT worry. The system will automatically move it to your workspace and notify you of the new filename. You can then read it directly.\n"
    "10. **Workspace Visibility Hint**: When the user likely wants to inspect workspace files (e.g., asks to view files/directories/current workspace), first provide a brief workspace status summary including the current isolated workspace path and a concise directory snapshot (such as top entries) before deeper operations.\n"
    "\n"
    "**Native Tool Usage Guidelines (If Available):**\n"
    "- **Shell tools**: If the environment exposes a `bash`-style tool with sync/async/background controls, choose the appropriate mode for the task, prefer non-interactive execution when possible, disable pagers, and stop long-lived processes with explicit `kill <pid>` rather than broad process-kill patterns.\n"
    "- **File editing tools**: If the environment exposes a dedicated edit tool that supports batching, group related edits to the same file in one response when practical, especially for renames or non-overlapping blocks.\n"
    "- **File reading vs presentation**: If the environment exposes both a presentation-only file viewer and a file-reading tool, use the presentation tool only when the user explicitly asks to see a file or diff; otherwise use the file-reading tool for your own reasoning and keep snippets focused.\n"
    "- **rg/grep/find**: Remember that the grep tool requires escaping literal braces (e.g. `interface\\{\\}`). Prefer glob matching (`**/*.js`) for file discovery.\n"
    "- **Git Conventions**: If the user explicitly asks you to create commits, follow the repository's existing conventions and include only the trailers or metadata that the repository or the user actually requires.\n"
    "- **Safety & Hygiene**: Clean up temporary files at the end of a task. Prefer the session's existing file-reading/editing tools for files that already exist rather than replacing them with newly created copies. Never commit secrets, share sensitive data, or violate copyrights.\n"
    f"{SQL_AND_STATE_PATTERNS}"
    f"{NATIVE_BEHAVIOR_PATTERNS}"
    f"{SEARCH_AND_AGENT_PATTERNS}"
)

# Sensitive extensions only for Administrators
ADMIN_EXTENSIONS = (
    "\n**[ADMINISTRATOR PRIVILEGES - CONFIDENTIAL]**\n"
    "You have detected that the current user is an **ADMINISTRATOR**. You are granted additional 'God Mode' perspective:\n"
    "- **Full OS Interaction**: You can use shell tools to deep-dive into any container process or system configuration.\n"
    "- **Database Access**: There is no dedicated tool for the main **OpenWebUI application database**. If database access is necessary, you may obtain credentials from the environment (for example `DATABASE_URL`) and write code/scripts to connect explicitly.\n"
    "- **Copilot SDK & Metadata**: You can inspect your own session state and core configuration in the Copilot SDK config directory to debug session persistence.\n"
    "- **Environment Secrets**: You are permitted to read and analyze environment variables and system-wide secrets for diagnostic purposes.\n"
    "**SECURITY NOTE**: Do NOT leak these sensitive internal details to non-admin users if you are ever switched to a lower privilege context.\n"
)

# Strict restrictions for regular Users
USER_RESTRICTIONS = (
    "\n**[USER ACCESS RESTRICTIONS - STRICT]**\n"
    "You have detected that the current user is a **REGULAR USER**. You must adhere to the following security boundaries:\n"
    "- **NO Environment Access**: You are strictly **FORBIDDEN** from accessing environment variables (e.g., via `env`, `printenv`, or Python's `os.environ`).\n"
    "- **NO OpenWebUI App Database Access**: You must **NOT** attempt to connect to or query the main OpenWebUI application database (for example via `DATABASE_URL`, SQLAlchemy engines, custom connection code, or direct backend database credentials).\n"
    "- **Session SQL Scope Only**: You MAY use only the SQL databases explicitly exposed by the session tooling through the `sql` tool, such as the per-session `session` database and any read-only `session_store` made available by the environment. Treat them as separate from the main OpenWebUI app database, stay within the authorized task scope, and never use them to inspect unrelated users' private data.\n"
    "- **Own Session Metadata Access**: You MAY read Copilot session information for the current user/current chat as needed for the task. Allowed scope includes the current session metadata under the configured `COPILOTSDK_CONFIG_DIR` (default path pattern: `/app/backend/data/.copilot/session-state/<chat_id>/`). Access to other users' sessions or unrelated global metadata is strictly **PROHIBITED**.\n"
    "- **NO Writing Outside Workspace**: Any attempt to write files to `/root`, `/app`, `/etc`, or other system folders is a **SECURITY VIOLATION**. All generated code, HTML, or data artifacts MUST be saved strictly inside the `Your Isolated Workspace` path provided.\n"
    "- **Formal Delivery**: Write the file to the workspace and call `publish_file_from_workspace`. You are strictly **FORBIDDEN** from outputting raw HTML code blocks in the conversation.\n"
    "- **Tools and Shell Availability**: You MAY normally use the tools and terminal/shell tools provided by the system to complete the task, as long as you obey the security boundaries above. Write operations must stay inside your isolated workspace, and you must not explore other users' workspace directories or probe system secrets.\n"
    "- **System Tools Availability**: You MAY use all tools provided by the system for this session to complete tasks, as long as you obey the security boundaries above.\n"
    "**SECURITY NOTE**: Your priority is to protect the platform's integrity while providing helpful assistance within these boundaries.\n"
)

# Skill management is handled by the `manage_skills` tool.


class Pipe:
    class Valves(BaseModel):
        # === Required / Frequently Needed ===
        GH_TOKEN: str = Field(
            default="",
            description="GitHub Fine-grained Token (Requires 'Copilot Requests' permission)",
        )
        BYOK_TYPE: Literal["openai", "anthropic"] = Field(
            default="openai",
            description="BYOK Provider Type: openai, anthropic",
        )
        BYOK_BASE_URL: str = Field(
            default="",
            description="BYOK Base URL (e.g. https://api.openai.com/v1)",
        )
        BYOK_API_KEY: str = Field(
            default="",
            description="BYOK API Key (Global Setting)",
        )

        # === Session Mode (Applies to All Sessions) ===
        SESSION_MODE: Literal["autopilot", "interactive", "plan"] = Field(
            default="autopilot",
            description="SDK session agent mode: 'autopilot' (autonomous multi-step execution), 'interactive' (step-by-step with confirmation), 'plan' (plan-first). Applied to all sessions.",
        )

        # === Agent Team (Optional Feature) ===
        AGENT_TEAM_TAG: str = Field(
            default="",
            description="Filter agent team by tag name. Select a tag to see available models.",
            json_schema_extra={
                "input": {
                    "type": "select",
                    "options": "get_agent_team_tag_options",
                }
            },
        )
        AGENT_TEAM_LEADER: str = Field(
            default="",
            description="Select the leader model for agent team.",
            json_schema_extra={
                "input": {
                    "type": "select",
                    "options": "get_agent_team_leader_options",
                }
            },
        )
        AGENT_TEAM_MODEL_IDS: str = Field(
            default="",
            description="Select OpenWebUI custom models as agent team. First selected = active agent. Requires 2+ models. Invalid if AGENT_TEAM_TAG is set. Example: model-id-1,model-id-2,model-id-3",
        )

        # === Feature Toggles ===
        ENABLE_OPENWEBUI_TOOLS: bool = Field(
            default=True,
            description="Enable OpenWebUI Tools (includes defined Tools and Built-in Tools).",
        )
        ENABLE_OPENAPI_SERVER: bool = Field(
            default=True,
            description="Enable OpenAPI Tool Server connection.",
        )
        ENABLE_MCP_SERVER: bool = Field(
            default=True,
            description="Enable Direct MCP Client connection (Recommended).",
        )
        ENABLE_OPENWEBUI_SKILLS: bool = Field(
            default=True,
            description="Enable loading OpenWebUI model-attached skills into SDK skill directories.",
        )
        DISABLED_SKILLS: str = Field(
            default="",
            description="Comma-separated skill names to disable in Copilot SDK session (e.g. docs-writer,webapp-testing).",
        )

        # === AI Behavior ===
        REASONING_EFFORT: Literal["low", "medium", "high", "xhigh"] = Field(
            default="medium",
            description="Reasoning effort level (low, medium, high). Only affects standard Copilot models (not BYOK).",
        )
        SHOW_THINKING: bool = Field(
            default=True,
            description="Show model reasoning/thinking process",
        )

        # === Runtime Behavior ===
        INFINITE_SESSION: bool = Field(
            default=True,
            description="Enable Infinite Sessions (automatic context compaction)",
        )
        DEBUG: bool = Field(
            default=False,
            description="Enable technical debug logs (connection info, etc.)",
        )
        LOG_LEVEL: str = Field(
            default="error",
            description="Copilot CLI log level: none, error, warning, info, debug, all",
        )
        TIMEOUT: int = Field(
            default=86400,
            description="Timeout for each stream chunk (seconds)",
        )

        # === Filtering & Limits ===
        EXCLUDE_KEYWORDS: str = Field(
            default="",
            description="Exclude models containing these keywords (comma separated, e.g.: codex, haiku)",
        )
        MAX_MULTIPLIER: float = Field(
            default=3.0,
            description="Maximum allowed billing multiplier for standard Copilot models. 0 means only free models (0x). Set to a high value (e.g., 100) to allow all.",
        )
        COMPACTION_THRESHOLD: float = Field(
            default=0.8,
            description="Background compaction threshold (0.0-1.0)",
        )
        BUFFER_THRESHOLD: float = Field(
            default=0.95,
            description="Buffer exhaustion threshold (0.0-1.0)",
        )

        # === BYOK (Advanced) ===
        BYOK_BEARER_TOKEN: str = Field(
            default="",
            description="BYOK Bearer Token (Global, overrides API Key)",
        )
        BYOK_MODELS: str = Field(
            default="",
            description="BYOK Model List (comma separated). Leave empty to fetch from API.",
        )
        BYOK_WIRE_API: Literal["completions", "responses"] = Field(
            default="completions",
            description="BYOK Wire API: completions, responses",
        )

        # === Directory & Cache (Rarely Changed) ===
        COPILOTSDK_CONFIG_DIR: str = Field(
            default="/app/backend/data/.copilot",
            description="Persistent directory for Copilot SDK config and session state.",
        )
        OPENWEBUI_SKILLS_SHARED_DIR: str = Field(
            default="/app/backend/data/cache/copilot-openwebui-skills",
            description="Shared cache directory for OpenWebUI skills converted to SDK SKILL.md format.",
        )
        OPENWEBUI_UPLOAD_PATH: str = Field(
            default="/app/backend/data/uploads",
            description="Path to OpenWebUI uploads directory (for file processing).",
        )
        MODEL_CACHE_TTL: int = Field(
            default=3600,
            description="Model list cache TTL in seconds. Set to 0 to disable cache (always fetch). Default: 3600 (1 hour).",
        )
        CUSTOM_ENV_VARS: str = Field(
            default="",
            description='Custom environment variables (JSON format, e.g., {"VAR": "value"})',
        )

        @classmethod
        def get_agent_team_tag_options(cls, __user__=None) -> list[dict]:
            """Return available tags from custom models for filtering."""
            try:
                from open_webui.models.models import Models as OWModels

                user_id = "unknown"
                if isinstance(__user__, dict):
                    user_id = __user__.get("id", "unknown")
                elif isinstance(__user__, (list, tuple)) and __user__:
                    user_id = (
                        __user__[0].get("id", "unknown")
                        if isinstance(__user__[0], dict)
                        else "unknown"
                    )
                result = _call_openwebui_sync_compat(
                    OWModels.search_models,
                    user_id=user_id,
                    filter={},
                    limit=200,
                )
                tags = set()
                for m in _extract_search_result_items(result):
                    if hasattr(m, "meta") and m.meta:
                        meta_obj = m.meta
                        if hasattr(meta_obj, "model_dump"):
                            meta = meta_obj.model_dump()
                        elif isinstance(meta_obj, dict):
                            meta = meta_obj
                        else:
                            meta = {}
                        raw_tags = meta.get("tags", []) or []
                        for tag in raw_tags:
                            if isinstance(tag, dict):
                                name = tag.get("name", "")
                            else:
                                name = str(tag) if tag else ""
                            if name:
                                tags.add(name)
                return [{"value": t, "label": t} for t in sorted(tags) if t]
            except Exception:
                return []

        @classmethod
        def get_agent_team_leader_options(cls, __user__=None) -> list[dict]:
            """Return all custom models for leader selection, with tag-model format."""
            try:
                from open_webui.models.models import Models as OWModels

                user_id = "unknown"
                if isinstance(__user__, dict):
                    user_id = __user__.get("id", "unknown")
                elif isinstance(__user__, (list, tuple)) and __user__:
                    user_id = (
                        __user__[0].get("id", "unknown")
                        if isinstance(__user__[0], dict)
                        else "unknown"
                    )
                result = _call_openwebui_sync_compat(
                    OWModels.search_models,
                    user_id=user_id,
                    filter={},
                    limit=200,
                )
                models = []
                for m in _extract_search_result_items(result):
                    if (
                        hasattr(m, "base_model_id")
                        and m.base_model_id
                        and m.base_model_id.strip()
                    ):
                        model_name = getattr(m, "name", "") or m.id
                        tag_names = []
                        if hasattr(m, "meta") and m.meta:
                            meta_obj = m.meta
                            if hasattr(meta_obj, "model_dump"):
                                meta = meta_obj.model_dump()
                            elif isinstance(meta_obj, dict):
                                meta = meta_obj
                            else:
                                meta = {}
                            raw_tags = meta.get("tags", []) or []
                            for tag in raw_tags:
                                if isinstance(tag, dict):
                                    name = tag.get("name", "")
                                else:
                                    name = str(tag) if tag else ""
                                if name:
                                    tag_names.append(name)
                        # Format: tag1,tag2-modelname or just modelname
                        if tag_names:
                            label = f"{','.join(tag_names)}-{model_name}"
                        else:
                            # Skip models that have no tags
                            continue
                        models.append({"value": m.id, "label": label})
                models.sort(key=lambda x: x["label"])
                return models
            except Exception:
                return []

    class UserValves(BaseModel):
        # === Required ===
        GH_TOKEN: str = Field(
            default="",
            description="Personal GitHub Fine-grained Token (overrides global setting)",
        )

        # === BYOK (Essential) ===
        BYOK_TYPE: Literal["", "openai", "anthropic"] = Field(
            default="",
            description="BYOK Provider Type override.",
        )
        BYOK_BASE_URL: str = Field(
            default="",
            description="BYOK Base URL override.",
        )
        BYOK_API_KEY: str = Field(
            default="",
            description="BYOK API Key (User override)",
        )

        # === Session Mode (Applies to All Sessions) ===
        SESSION_MODE: Literal["autopilot", "interactive", "plan"] = Field(
            default="autopilot",
            description="SDK session agent mode (user override): 'autopilot', 'interactive', 'plan'.",
        )

        # === Agent Team (Optional Feature) ===
        AGENT_TEAM_TAG: str = Field(
            default="",
            description="Filter agent team by tag name (user override).",
            json_schema_extra={
                "input": {
                    "type": "select",
                    "options": "get_agent_team_tag_options",
                }
            },
        )
        AGENT_TEAM_LEADER: str = Field(
            default="",
            description="Select the leader model for agent team.",
            json_schema_extra={
                "input": {
                    "type": "select",
                    "options": "get_agent_team_leader_options",
                }
            },
        )
        AGENT_TEAM_MODEL_IDS: str = Field(
            default="",
            description="Select agent team by model IDs (user override). Invalid if AGENT_TEAM_TAG is set. Example: model-id-1,model-id-2,model-id-3",
        )

        # === Feature Toggles ===
        ENABLE_OPENWEBUI_TOOLS: bool = Field(
            default=True,
            description="Enable OpenWebUI Tools (includes defined Tools and Built-in Tools).",
        )
        ENABLE_OPENAPI_SERVER: bool = Field(
            default=True,
            description="Enable OpenAPI Tool Server loading (overrides global).",
        )
        ENABLE_MCP_SERVER: bool = Field(
            default=True,
            description="Enable dynamic MCP server loading (overrides global).",
        )
        ENABLE_OPENWEBUI_SKILLS: bool = Field(
            default=True,
            description="Enable loading OpenWebUI model-attached skills into SDK skill directories (user override).",
        )
        DISABLED_SKILLS: str = Field(
            default="",
            description="Comma-separated skill names to disable in Copilot SDK session (user override).",
        )

        # === AI Behavior ===
        REASONING_EFFORT: Literal["", "low", "medium", "high", "xhigh"] = Field(
            default="",
            description="Reasoning effort override. Only affects standard Copilot Models.",
        )
        SHOW_THINKING: bool = Field(
            default=True,
            description="Show model reasoning/thinking process",
        )

        # === Debug ===
        DEBUG: bool = Field(
            default=False,
            description="Enable technical debug logs (connection info, etc.)",
        )

        # === Filtering & Limits ===
        MAX_MULTIPLIER: Optional[float] = Field(
            default=None,
            description="Maximum allowed billing multiplier override for standard Copilot models.",
        )
        EXCLUDE_KEYWORDS: str = Field(
            default="",
            description="Exclude models containing these keywords (comma separated, user override).",
        )

        # === BYOK (Advanced) ===
        BYOK_BEARER_TOKEN: str = Field(
            default="",
            description="BYOK Bearer Token override.",
        )
        BYOK_MODELS: str = Field(
            default="",
            description="BYOK Model List override.",
        )
        BYOK_WIRE_API: Literal["", "completions", "responses"] = Field(
            default="",
            description="BYOK Wire API override.",
        )

        @classmethod
        def get_agent_team_tag_options(cls, __user__=None) -> list[dict]:
            """Return available tags from custom models for filtering."""
            try:
                from open_webui.models.models import Models as OWModels

                user_id = "unknown"
                if isinstance(__user__, dict):
                    user_id = __user__.get("id", "unknown")
                elif isinstance(__user__, (list, tuple)) and __user__:
                    user_id = (
                        __user__[0].get("id", "unknown")
                        if isinstance(__user__[0], dict)
                        else "unknown"
                    )
                result = _call_openwebui_sync_compat(
                    OWModels.search_models,
                    user_id=user_id,
                    filter={},
                    limit=200,
                )
                tags = set()
                for m in _extract_search_result_items(result):
                    if hasattr(m, "meta") and m.meta:
                        meta_obj = m.meta
                        if hasattr(meta_obj, "model_dump"):
                            meta = meta_obj.model_dump()
                        elif isinstance(meta_obj, dict):
                            meta = meta_obj
                        else:
                            meta = {}
                        raw_tags = meta.get("tags", []) or []
                        for tag in raw_tags:
                            if isinstance(tag, dict):
                                name = tag.get("name", "")
                            else:
                                name = str(tag) if tag else ""
                            if name:
                                tags.add(name)
                return [{"value": t, "label": t} for t in sorted(tags) if t]
            except Exception:
                return []

        @classmethod
        def get_agent_team_leader_options(cls, __user__=None) -> list[dict]:
            """Return all custom models for leader selection, with tag-model format."""
            try:
                from open_webui.models.models import Models as OWModels

                user_id = "unknown"
                if isinstance(__user__, dict):
                    user_id = __user__.get("id", "unknown")
                elif isinstance(__user__, (list, tuple)) and __user__:
                    user_id = (
                        __user__[0].get("id", "unknown")
                        if isinstance(__user__[0], dict)
                        else "unknown"
                    )
                result = _call_openwebui_sync_compat(
                    OWModels.search_models,
                    user_id=user_id,
                    filter={},
                    limit=200,
                )
                models = []
                for m in _extract_search_result_items(result):
                    if (
                        hasattr(m, "base_model_id")
                        and m.base_model_id
                        and m.base_model_id.strip()
                    ):
                        model_name = getattr(m, "name", "") or m.id
                        tag_names = []
                        if hasattr(m, "meta") and m.meta:
                            meta_obj = m.meta
                            if hasattr(meta_obj, "model_dump"):
                                meta = meta_obj.model_dump()
                            elif isinstance(meta_obj, dict):
                                meta = meta_obj
                            else:
                                meta = {}
                            raw_tags = meta.get("tags", []) or []
                            for tag in raw_tags:
                                if isinstance(tag, dict):
                                    name = tag.get("name", "")
                                else:
                                    name = str(tag) if tag else ""
                                if name:
                                    tag_names.append(name)
                        # Format: tag1,tag2-modelname or just modelname
                        if tag_names:
                            label = f"{','.join(tag_names)}-{model_name}"
                        else:
                            # Skip models that have no tags
                            continue
                        models.append({"value": m.id, "label": label})
                models.sort(key=lambda x: x["label"])
                return models
            except Exception:
                return []

    _shared_clients: Dict[str, Any] = {}  # Map: token_hash -> CopilotClient
    _shared_client_lock = asyncio.Lock()  # Lock for thread-safe client lifecycle
    _model_cache: List[dict] = []  # Model list cache (Memory only fallback)
    _standard_model_ids: set = set()  # Track standard model IDs
    _last_byok_config_hash: str = ""  # Track BYOK config (Status only)
    _last_model_cache_time: float = 0  # Timestamp
    _env_setup_done = False  # Track if env setup has been completed
    _last_update_check = 0  # Timestamp of last CLI update check
    _discovery_cache: Dict[str, Dict[str, Any]] = (
        {}
    )  # Map config_hash -> {"time": float, "models": list}

    def _is_version_at_least(self, target: str) -> bool:
        """Check if OpenWebUI version is at least the target version."""
        try:
            # Simple numeric comparison for speed and to avoid dependencies
            def parse_v(v_str):
                # Extract only numbers and dots
                clean = re.sub(r"[^0-9.]", "", v_str)
                return [int(x) for x in clean.split(".") if x]

            return parse_v(open_webui_version) >= parse_v(target)
        except Exception:
            return False

    def _insert_html_before_closing_tag(
        self, html_content: str, tag: str, insertion: str
    ) -> Tuple[str, bool]:
        """Insert content before the first closing tag, if present."""
        match = re.search(rf"</{tag}\s*>", html_content, re.IGNORECASE)
        if not match:
            return html_content, False
        return (
            html_content[: match.start()] + insertion + html_content[match.start() :],
            True,
        )

    def _insert_html_before_opening_tag(
        self, html_content: str, tag: str, insertion: str
    ) -> Tuple[str, bool]:
        """Insert content before the first opening tag, if present."""
        match = re.search(rf"<{tag}\b[^>]*>", html_content, re.IGNORECASE)
        if not match:
            return html_content, False
        return (
            html_content[: match.start()] + insertion + html_content[match.start() :],
            True,
        )

    def _insert_html_after_opening_tag(
        self, html_content: str, tag: str, insertion: str
    ) -> Tuple[str, bool]:
        """Insert content right after the first opening tag, if present."""
        match = re.search(rf"<{tag}\b[^>]*>", html_content, re.IGNORECASE)
        if not match:
            return html_content, False
        return (
            html_content[: match.end()] + insertion + html_content[match.end() :],
            True,
        )

    def _resolve_embed_lang(self, user_language: Optional[str]) -> str:
        """Return a reasonable HTML lang code for generated RichUI pages."""
        raw_lang = str(user_language or "").strip()
        if not raw_lang:
            return "en-US"

        raw_lang = raw_lang.split(",")[0].split(";")[0].strip().replace("_", "-")
        raw_lang = re.sub(r"[^A-Za-z0-9-]", "", raw_lang)
        if not raw_lang:
            return self._resolve_language(user_language or "")

        parts = [part for part in raw_lang.split("-") if part]
        if not parts:
            return self._resolve_language(user_language or "")

        normalized_parts = []
        for index, part in enumerate(parts):
            if index == 0:
                normalized_parts.append(part.lower())
            elif len(part) == 2 and part.isalpha():
                normalized_parts.append(part.upper())
            elif len(part) == 4 and part.isalpha():
                normalized_parts.append(part.title())
            else:
                normalized_parts.append(part)

        return "-".join(normalized_parts)

    def _ensure_html_lang_attr(self, html_content: str, lang: str) -> str:
        """Ensure the root <html> tag carries a lang attribute."""
        if not lang:
            return html_content

        match = re.search(r"<html\b([^>]*)>", html_content, re.IGNORECASE)
        if not match:
            return html_content

        attrs = match.group(1) or ""
        if re.search(r"\blang\s*=", attrs, re.IGNORECASE):
            return html_content

        replacement = f'<html lang="{lang}"{attrs}>'
        return html_content[: match.start()] + replacement + html_content[match.end() :]

    def _strip_html_to_text(self, html_content: str) -> str:
        """Best-effort visible-text extraction for heuristics like language inference."""
        text = re.sub(
            r"<(script|style)\b[^>]*>[\s\S]*?</\1>",
            " ",
            html_content,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_lib.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _infer_lang_from_html_content(self, html_content: str) -> Optional[str]:
        """Infer language from rendered HTML content when user metadata is too generic."""
        text = self._strip_html_to_text(html_content)
        if not text:
            return None

        japanese = len(re.findall(r"[\u3040-\u30ff]", text))
        korean = len(re.findall(r"[\uac00-\ud7af]", text))
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        cyrillic = len(re.findall(r"[\u0400-\u04ff]", text))

        if japanese >= 3:
            return "ja-JP"
        if korean >= 3:
            return "ko-KR"
        if chinese >= 6:
            return "zh-CN"
        if cyrillic >= 6:
            return "ru-RU"
        return None

    def _extract_html_title_or_heading(self, html_content: str) -> str:
        """Extract a concise human-readable page title for fallback RichUI actions."""
        patterns = [
            r"<title\b[^>]*>([\s\S]*?)</title>",
            r"<h1\b[^>]*>([\s\S]*?)</h1>",
            r"<h2\b[^>]*>([\s\S]*?)</h2>",
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if not match:
                continue
            candidate = self._strip_html_to_text(match.group(1))
            if candidate:
                return candidate[:120]
        return ""

    def _contains_richui_interactions(self, html_content: str) -> bool:
        """Return True if the page already includes explicit prompt/link interactions."""
        interaction_patterns = [
            r"\bOpenWebUIBridge\s*\.\s*prompt\b",
            r"\bOpenWebUIBridge\s*\.\s*fill\b",
            r"\bOpenWebUIBridge\s*\.\s*submit\b",
            r"\bOpenWebUIBridge\s*\.\s*copy\b",
            r"\bOpenWebUIBridge\s*\.\s*sendPrompt\b",
            r"\bOpenWebUIBridge\s*\.\s*fillPrompt\b",
            r"\bOpenWebUIBridge\s*\.\s*submitCurrentPrompt\b",
            r"\bOpenWebUIBridge\s*\.\s*copyText\b",
            r"\bOpenWebUIBridge\s*\.\s*setSelection\b",
            r"\bsendPrompt\s*\(",
            r"\bsend_prompt\s*\(",
            r"\bfillPrompt\s*\(",
            r"\bfill_prompt\s*\(",
            r"\binputPrompt\s*\(",
            r"\binput_prompt\s*\(",
            r"\bsubmitCurrentPrompt\s*\(",
            r"\bsubmit_current_prompt\s*\(",
            r"\bcopyText\s*\(",
            r"\bcopy_text\s*\(",
            r"\bsubmitPrompt\s*\(",
            r"\bsubmit_prompt\s*\(",
            r"\bopenLink\s*\(",
            r"\bopen_link\s*\(",
            r"data-openwebui-action\s*=",
            r"data-openwebui-mode\s*=",
            r"data-openwebui-copy\s*=",
            r"data-copy\s*=",
            r"data-openwebui-prompt-template\s*=",
            r"data-openwebui-copy-template\s*=",
            r"data-openwebui-select\s*=",
            r"data-openwebui-prompt\s*=",
            r"data-prompt\s*=",
            r"data-openwebui-link\s*=",
            r"data-link\s*=",
        ]
        return any(
            re.search(pattern, html_content, re.IGNORECASE)
            for pattern in interaction_patterns
        )

    def _richui_default_actions_disabled(self, html_content: str) -> bool:
        """Allow specific embeds such as widgets to opt out of fallback action buttons."""
        markers = [
            r'data-openwebui-no-default-actions\s*=\s*["\']1["\']',
            r'data-openwebui-static-widget\s*=\s*["\']1["\']',
        ]
        return any(
            re.search(pattern, html_content, re.IGNORECASE) for pattern in markers
        )

    def _build_richui_default_actions_block(
        self, html_content: str, user_lang: Optional[str], embed_lang: str
    ) -> str:
        """Create a small fallback action bar when a page has no chat interactions."""
        title = self._extract_html_title_or_heading(html_content) or (
            "this visualization"
            if not str(embed_lang).lower().startswith("zh")
            else "这个页面"
        )
        is_zh = str(embed_lang or user_lang or "").lower().startswith("zh")

        if is_zh:
            heading = "继续探索"
            button_specs = [
                (
                    "深入讲解",
                    f"请基于《{title}》继续深入解释这个页面里的关键结构、角色分工和工作流。",
                ),
                (
                    "落地方案",
                    f"请基于《{title}》给我一个可执行的实施方案，包括阶段拆分、技术选型和风险点。",
                ),
                (
                    "转成 TODO",
                    f"请基于《{title}》把这个设计转换成一个分阶段 TODO 清单，并标出依赖关系。",
                ),
            ]
        else:
            heading = "Continue exploring"
            button_specs = [
                (
                    "Deep dive",
                    f"Based on '{title}', explain the key structure, roles, and workflow shown in this page in more detail.",
                ),
                (
                    "Execution plan",
                    f"Based on '{title}', turn this design into an implementation plan with phases, technical choices, and key risks.",
                ),
                (
                    "Convert to TODOs",
                    f"Based on '{title}', convert this design into a phased TODO list with dependencies.",
                ),
            ]

        button_html = []
        for label, prompt in button_specs:
            button_html.append(
                '<button type="button" class="openwebui-richui-action-btn" '
                f'data-openwebui-prompt="{html_lib.escape(prompt, quote=True)}">'
                f"{html_lib.escape(label)}"
                "</button>"
            )

        return (
            "\n"
            '<section class="openwebui-richui-fallback-actions" data-openwebui-fallback-actions="1">'
            f'<div class="openwebui-richui-fallback-title">{html_lib.escape(heading)}</div>'
            '<div class="openwebui-richui-fallback-row">'
            + "".join(button_html)
            + "</div></section>\n"
            "<style>\n"
            ".openwebui-richui-fallback-actions{margin:20px auto 0;max-width:1200px;padding:14px 16px;border:1px solid var(--richui-border, rgba(148,163,184,.18));border-radius:14px;background:var(--richui-bg-secondary, rgba(15,23,42,.04));}\n"
            ".openwebui-richui-fallback-title{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--richui-text-secondary, #64748b);margin-bottom:10px;}\n"
            ".openwebui-richui-fallback-row{display:flex;flex-wrap:wrap;gap:10px;}\n"
            ".openwebui-richui-action-btn{appearance:none;border:1px solid var(--richui-border, rgba(148,163,184,.24));background:var(--richui-bg, rgba(255,255,255,.9));color:var(--richui-text, #0f172a);border-radius:999px;padding:8px 14px;font:500 13px/1.2 var(--font-sans, system-ui);cursor:pointer;transition:all .18s ease;}\n"
            ".openwebui-richui-action-btn:hover{transform:translateY(-1px);border-color:var(--richui-accent, rgba(59,130,246,.55));}\n"
            ".openwebui-richui-action-btn:focus-visible{outline:2px solid var(--richui-accent, rgba(59,130,246,.6));outline-offset:2px;}\n"
            "</style>\n"
        )

    def _prepare_richui_embed_html(
        self, html_content: Any, user_lang: Optional[str] = None
    ) -> Any:
        """Inject a shared bridge so rich UI embeds can talk to the parent app."""
        if isinstance(html_content, (bytes, bytearray)):
            html_content = html_content.decode("utf-8", errors="replace")
        if not isinstance(html_content, str):
            return html_content

        stripped = html_content.strip()
        if not stripped or RICHUI_BRIDGE_MARKER in html_content:
            return html_content

        embed_lang = self._resolve_embed_lang(user_lang)
        inferred_lang = self._infer_lang_from_html_content(html_content)
        if inferred_lang and (not user_lang or embed_lang.lower().startswith("en")):
            embed_lang = inferred_lang
        lang_json = json.dumps(embed_lang, ensure_ascii=False)
        lang_head_block = (
            "\n"
            '<meta name="openwebui-user-language" content="'
            f"{embed_lang}"
            '">\n'
            '<script id="openwebui-richui-language" data-openwebui-richui-bridge="1">'
            "(function(){"
            f"var userLang={lang_json};"
            "window.__OPENWEBUI_USER_LANG__=userLang;"
            "window.__openwebui_user_lang__=userLang;"
            "if(document.documentElement){"
            "document.documentElement.setAttribute('data-openwebui-user-lang',userLang);"
            "if(!document.documentElement.getAttribute('lang')){document.documentElement.setAttribute('lang',userLang);}"
            "}"
            "})();"
            "</script>\n"
        )
        style_block = "\n" + RICHUI_BRIDGE_STYLE.strip() + "\n"
        script_block = "\n" + RICHUI_BRIDGE_SCRIPT.strip() + "\n"
        looks_like_document = bool(
            re.search(
                r"<!doctype html|<html\b|<head\b|<body\b", html_content, re.IGNORECASE
            )
        )

        if not looks_like_document:
            return (
                "<!DOCTYPE html>\n"
                f'<html lang="{embed_lang}">\n'
                "<head>\n"
                '<meta charset="UTF-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                f"{lang_head_block.strip()}\n"
                f"{RICHUI_BRIDGE_STYLE.strip()}\n"
                "</head>\n"
                f'<body data-openwebui-richui-fragment="1" data-openwebui-user-lang="{embed_lang}">\n'
                f"{html_content}\n"
                f"{RICHUI_BRIDGE_SCRIPT.strip()}\n"
                "</body>\n"
                "</html>\n"
            )

        enhanced_html = self._ensure_html_lang_attr(html_content, embed_lang)
        enhanced_html, inserted = self._insert_html_before_closing_tag(
            enhanced_html, "head", lang_head_block
        )
        if not inserted:
            head_block = f"<head>{lang_head_block}</head>\n"
            enhanced_html, inserted = self._insert_html_before_opening_tag(
                enhanced_html, "body", head_block
            )
            if not inserted:
                enhanced_html, inserted = self._insert_html_after_opening_tag(
                    enhanced_html, "html", "\n" + head_block
                )
            if not inserted:
                enhanced_html = lang_head_block + enhanced_html

        enhanced_html, inserted = self._insert_html_before_closing_tag(
            enhanced_html, "head", style_block
        )
        if not inserted:
            head_block = f"<head>{style_block}</head>\n"
            enhanced_html, inserted = self._insert_html_before_opening_tag(
                enhanced_html, "body", head_block
            )
            if not inserted:
                enhanced_html, inserted = self._insert_html_after_opening_tag(
                    enhanced_html, "html", "\n" + head_block
                )
            if not inserted:
                enhanced_html = style_block + enhanced_html

        enhanced_html, inserted = self._insert_html_before_closing_tag(
            enhanced_html, "body", script_block
        )
        if not inserted:
            enhanced_html += script_block

        if not self._richui_default_actions_disabled(
            enhanced_html
        ) and not self._contains_richui_interactions(enhanced_html):
            action_block = self._build_richui_default_actions_block(
                enhanced_html, user_lang=user_lang, embed_lang=embed_lang
            )
            enhanced_html, inserted = self._insert_html_before_closing_tag(
                enhanced_html, "body", "\n" + action_block + "\n"
            )
            if not inserted:
                enhanced_html += "\n" + action_block + "\n"

        return enhanced_html

    TRANSLATIONS = {
        "en-US": {
            "status_conn_est": "Connection established, waiting for response...",
            "status_reasoning_inj": "Reasoning Effort injected: {effort}",
            "status_assistant_start": "Agent is starting to think...",
            "status_assistant_processing": "Agent is processing your request...",
            "status_still_working": "Still processing... ({seconds}s elapsed)",
            "status_skill_invoked": "Detected and using skill: {skill}",
            "status_tool_using": "Using tool: {name}...",
            "status_tool_progress": "Tool progress: {name} ({progress}%) {msg}",
            "status_tool_done": "Tool completed: {name}",
            "status_tool_failed": "Tool failed: {name}",
            "status_subagent_start": "Invoking sub-agent: {name}",
            "status_compaction_start": "Compacting session context...",
            "status_compaction_complete": "Context compaction complete.",
            "status_publishing_file": "Publishing artifact: {filename}",
            "status_task_completed": "Task completed.",
            "status_todo_hint": "📋 Current TODO status: {todo_text}",
            "plan_title": "Action Plan",
            "status_plan_changed": "Plan updated: {operation}",
            "status_context_changed": "Working in {path}",
            "status_intent": "Intent: {intent}",
            "status_session_error": "Processing failed: {error}",
            "status_no_skill_invoked": "No skill was invoked in this turn (DEBUG)",
            "debug_agent_working_in": "Agent working in: {path}",
            "debug_mcp_servers": "🔌 Connected MCP Servers: {servers}",
            "publish_success": "File published successfully.",
            "publish_hint_html": "[View {filename}]({view_url}) | [Download]({download_url})",
            "publish_hint_embed": "✨ Premium: Displayed directly via Action.",
            "publish_hint_default": "Link: [Download {filename}]({download_url})",
        },
        "zh-CN": {
            "status_conn_est": "已建立连接，等待响应...",
            "status_reasoning_inj": "已注入推理级别：{effort}",
            "status_assistant_start": "Agent 开始思考...",
            "status_assistant_processing": "Agent 正在处理您的请求...",
            "status_still_working": "仍在处理中...（已耗时 {seconds} 秒）",
            "status_skill_invoked": "已发现并使用技能：{skill}",
            "status_tool_using": "正在使用工具：{name}...",
            "status_tool_progress": "工具进度：{name} ({progress}%) {msg}",
            "status_tool_done": "工具已完成：{name}",
            "status_tool_failed": "工具执行失败：{name}",
            "status_subagent_start": "正在调用子代理：{name}",
            "status_compaction_start": "正在压缩会话上下文...",
            "status_compaction_complete": "上下文压缩完成。",
            "status_publishing_file": "正在发布成果物：{filename}",
            "status_task_completed": "任务已完成。",
            "status_todo_hint": "📋 当前 TODO 状态：{todo_text}",
            "plan_title": "行动计划",
            "status_plan_changed": "计划已更新: {operation}",
            "status_context_changed": "工作目录已切换：{path}",
            "status_intent": "当前意图：{intent}",
            "status_session_error": "处理失败：{error}",
            "status_no_skill_invoked": "本轮未触发任何技能（DEBUG）",
            "debug_agent_working_in": "Agent 工作目录: {path}",
            "debug_mcp_servers": "🔌 已连接 MCP 服务器: {servers}",
            "publish_success": "文件发布成功。",
            "publish_hint_html": "[查看网页]({view_url}) | [下载文件]({download_url})",
            "publish_hint_embed": "✨ 高级体验：组件已通过 Action 直接展示。",
            "publish_hint_default": "链接: [下载 {filename}]({download_url})",
        },
        "zh-HK": {
            "status_conn_est": "已建立連接，等待響應...",
            "status_reasoning_inj": "已注入推理級別：{effort}",
            "status_assistant_start": "Agent 開始思考...",
            "status_assistant_processing": "Agent 正在處理您的請求...",
            "status_still_working": "仍在處理中... (已耗時 {seconds} 秒)",
            "status_skill_invoked": "已發現並使用技能：{skill}",
            "status_tool_using": "正在使用工具：{name}...",
            "status_tool_progress": "工具進度：{name} ({progress}%) {msg}",
            "status_tool_done": "工具執行完成：{name}",
            "status_tool_failed": "工具執行失敗：{name}",
            "status_subagent_start": "正在調用子代理：{name}",
            "status_compaction_start": "正在壓縮會話上下文...",
            "status_compaction_complete": "上下文壓縮完成。",
            "status_publishing_file": "正在發布成果物：{filename}",
            "status_task_completed": "任務已完成。",
            "status_todo_hint": "📋 當前 TODO 狀態：{todo_text}",
            "plan_title": "行動計劃",
            "status_plan_changed": "計劃已更新: {operation}",
            "status_context_changed": "工作目錄已切換：{path}",
            "status_intent": "當前意圖：{intent}",
            "status_session_error": "處理失敗：{error}",
            "status_no_skill_invoked": "本輪未觸發任何技能（DEBUG）",
            "debug_agent_working_in": "Agent 工作目錄: {path}",
            "debug_mcp_servers": "🔌 已連接 MCP 伺服器: {servers}",
            "publish_success": "文件發布成功。",
            "publish_hint_html": "連結: [查看 {filename}]({view_url}) | [下載]({download_url})",
            "publish_hint_embed": "高級體驗：組件已通過 Action 直接展示。",
            "publish_hint_default": "連結: [下載 {filename}]({download_url})",
        },
        "zh-TW": {
            "status_conn_est": "已建立連接，等待響應...",
            "status_reasoning_inj": "已注入推理級別：{effort}",
            "status_assistant_start": "Agent 開始思考...",
            "status_assistant_processing": "Agent 正在處理您的請求...",
            "status_still_working": "仍在處理中... (已耗時 {seconds} 秒)",
            "status_skill_invoked": "已發現並使用技能：{skill}",
            "status_tool_using": "正在使用工具：{name}...",
            "status_tool_progress": "工具進度：{name} ({progress}%) {msg}",
            "status_tool_done": "工具執行完成：{name}",
            "status_tool_failed": "工具執行失敗：{name}",
            "status_subagent_start": "正在調用子代理：{name}",
            "status_compaction_start": "正在壓縮會話上下文...",
            "status_compaction_complete": "上下文壓縮完成。",
            "status_publishing_file": "正在發布成果物：{filename}",
            "status_task_completed": "任務已完成。",
            "status_todo_hint": "📋 當前 TODO 狀態：{todo_text}",
            "plan_title": "行動計劃",
            "status_plan_changed": "計劃已更新: {operation}",
            "status_context_changed": "工作目錄已切換：{path}",
            "status_intent": "當前意圖：{intent}",
            "status_session_error": "處理失敗：{error}",
            "status_no_skill_invoked": "本輪未觸發任何技能（DEBUG）",
            "debug_agent_working_in": "Agent 工作目錄: {path}",
            "debug_mcp_servers": "🔌 已連接 MCP 伺服器: {servers}",
            "publish_success": "文件發布成功。",
            "publish_hint_html": "連結: [查看 {filename}]({view_url}) | [下載]({download_url})",
            "publish_hint_embed": "高級體驗：組件已通過 Action 直接展示。",
            "publish_hint_default": "連結: [下載 {filename}]({download_url})",
        },
        "ja-JP": {
            "status_conn_est": "接続が確立されました。応答を待っています...",
            "status_reasoning_inj": "推論レベルが注入されました：{effort}",
            "status_assistant_start": "Agent が考え始めました...",
            "status_assistant_processing": "Agent がリクエストを処理しています...",
            "status_still_working": "処理を継続しています... ({seconds}秒経過)",
            "status_skill_invoked": "スキルが検出され、使用されています：{skill}",
            "status_tool_using": "ツールを使用中: {name}...",
            "status_tool_progress": "ツール進行状況: {name} ({progress}%) {msg}",
            "status_tool_done": "ツールの実行が完了しました: {name}",
            "status_tool_failed": "ツールの実行に失敗しました: {name}",
            "status_subagent_start": "サブエージェントを呼び出し中: {name}",
            "status_compaction_start": "セッションコンテキストを圧縮しています...",
            "status_compaction_complete": "コンテキストの圧縮が完了しました。",
            "status_publishing_file": "アーティファクトを公開中：{filename}",
            "status_task_completed": "タスクが完了しました。",
            "status_todo_hint": "📋 現在の TODO 状態: {todo_text}",
            "plan_title": "アクションプラン",
            "status_plan_changed": "プランが更新されました: {operation}",
            "status_context_changed": "作業ディレクトリが変更されました: {path}",
            "status_intent": "現在の意図: {intent}",
            "status_session_error": "処理に失敗しました: {error}",
            "status_no_skill_invoked": "このターンではスキルは呼び出されませんでした (DEBUG)",
            "debug_agent_working_in": "エージェントの作業ディレクトリ: {path}",
            "debug_mcp_servers": "🔌 接続された MCP サーバー: {servers}",
            "publish_success": "ファイルが正常に公開されました。",
            "publish_hint_html": "リンク: [表示 {filename}]({view_url}) | [ダウンロード]({download_url})",
            "publish_hint_embed": "プレミアム体験：コンポーネントはアクション経由で直接表示されました。",
            "publish_hint_default": "リンク: [ダウンロード {filename}]({download_url})",
        },
        "ko-KR": {
            "status_conn_est": "연결이 설정되었습니다. 응답을 기다리는 중...",
            "status_reasoning_inj": "추론 노력이 주입되었습니다: {effort}",
            "status_assistant_start": "Agent 가 생각을 시작했습니다...",
            "status_assistant_processing": "Agent 가 요청을 처리 중입니다...",
            "status_still_working": "처리 중입니다... ({seconds}초 경과)",
            "status_skill_invoked": "스킬이 감지되어 사용 중입니다: {skill}",
            "status_tool_using": "도구 사용 중: {name}...",
            "status_tool_progress": "도구 진행 상황: {name} ({progress}%) {msg}",
            "status_tool_done": "도구 실행 완료: {name}",
            "status_tool_failed": "도구 실행 실패: {name}",
            "status_subagent_start": "하위 에이전트 호출 중: {name}",
            "status_compaction_start": "세션 컨텍스트를 압축하는 중...",
            "status_compaction_complete": "컨텍스트 압축 완료.",
            "status_publishing_file": "아티팩트 게시 중: {filename}",
            "status_task_completed": "작업이 완료되었습니다.",
            "status_todo_hint": "📋 현재 TODO 상태: {todo_text}",
            "plan_title": "실행 계획",
            "status_plan_changed": "계획이 업데이트되었습니다: {operation}",
            "status_context_changed": "작업 디렉토리가 변경되었습니다: {path}",
            "status_intent": "현재 의도: {intent}",
            "status_session_error": "처리에 실패했습니다: {error}",
            "status_no_skill_invoked": "이 턴에는 스킬이 호출되지 않았습니다 (DEBUG)",
            "debug_agent_working_in": "에이전트 작업 디렉토리: {path}",
            "debug_mcp_servers": "🔌 연결된 MCP 서버: {servers}",
            "publish_success": "파일이 성공적으로 게시되었습니다.",
            "publish_hint_html": "링크: [{filename} 보기]({view_url}) | [다운로드]({download_url})",
            "publish_hint_embed": "프리미엄 경험: 구성 요소가 액션을 통해 직접 표시되었습니다.",
            "publish_hint_default": "링크: [{filename} 다운로드]({download_url})",
        },
        "fr-FR": {
            "status_conn_est": "Connexion établie, en attente de réponse...",
            "status_reasoning_inj": "Effort de raisonnement injecté : {effort}",
            "status_assistant_start": "L'Agent commence à réfléchir...",
            "status_assistant_processing": "L'Agent traite votre demande...",
            "status_still_working": "Toujours en cours... ({seconds}s écoulées)",
            "status_skill_invoked": "Compétence détectée et utilisée : {skill}",
            "status_tool_using": "Utilisation de l'outil : {name}...",
            "status_session_error": "Échec du traitement : {error}",
            "status_no_skill_invoked": "Aucune compétence invoquée pour ce tour (DEBUG)",
            "debug_agent_working_in": "Agent travaillant dans : {path}",
            "debug_mcp_servers": "🔌 Serveurs MCP connectés : {servers}",
            "publish_success": "Fichier publié avec succès.",
            "publish_hint_html": "Lien : [Voir {filename}]({view_url}) | [Télécharger]({download_url})",
            "publish_hint_embed": "Expérience Premium : Le composant est affiché directement via Action.",
            "publish_hint_default": "Lien : [Télécharger {filename}]({download_url})",
        },
        "de-DE": {
            "status_conn_est": "Verbindung hergestellt, warte auf Antwort...",
            "status_reasoning_inj": "Schlussfolgerungsaufwand injiziert: {effort}",
            "status_assistant_start": "Agent beginnt zu denken...",
            "status_assistant_processing": "Agent bearbeitet Ihre Anfrage...",
            "status_still_working": "Wird noch verarbeitet... ({seconds}s vergangen)",
            "status_skill_invoked": "Skill erkannt und verwendet: {skill}",
            "status_tool_using": "Nutze Tool: {name}...",
            "status_tool_progress": "Tool-Fortschritt: {name} ({progress}%) {msg}",
            "status_tool_done": "Tool abgeschlossen: {name}",
            "status_tool_failed": "Tool fehlgeschlagen: {name}",
            "status_subagent_start": "Unteragent wird aufgerufen: {name}",
            "status_compaction_start": "Sitzungskontext wird komprimiert...",
            "status_compaction_complete": "Kontextkomprimierung abgeschlossen.",
            "status_publishing_file": "Artifact wird veröffentlicht: {filename}",
            "status_task_completed": "Aufgabe abgeschlossen.",
            "status_todo_hint": "📋 Aktueller TODO-Status: {todo_text}",
            "plan_title": "Aktionsplan",
            "status_plan_changed": "Plan aktualisiert: {operation}",
            "status_context_changed": "Arbeite in {path}",
            "status_intent": "Absicht: {intent}",
            "status_session_error": "Verarbeitung fehlgeschlagen: {error}",
            "status_no_skill_invoked": "In dieser Runde wurde kein Skill aufgerufen (DEBUG)",
            "debug_agent_working_in": "Agent arbeitet in: {path}",
            "debug_mcp_servers": "🔌 Verbundene MCP-Server: {servers}",
            "publish_success": "Datei erfolgreich veröffentlicht.",
            "publish_hint_html": "Link: [{filename} ansehen]({view_url}) | [Herunterladen]({download_url})",
            "publish_hint_embed": "Premium-Erlebnis: Die Komponente wurde direkt per Action angezeigt.",
            "publish_hint_default": "Link: [{filename} herunterladen]({download_url})",
        },
        "it-IT": {
            "status_conn_est": "Connessione stabilita, in attesa di risposta...",
            "status_reasoning_inj": "Sforzo di ragionamento iniettato: {effort}",
            "status_assistant_start": "L'Agent sta iniziando a pensare...",
            "status_assistant_processing": "L'Agent sta elaborando la tua richiesta...",
            "status_still_working": "Ancora in elaborazione... ({seconds}s trascorsi)",
            "status_skill_invoked": "Skill rilevata e utilizzata: {skill}",
            "status_tool_using": "Utilizzando lo strumento: {name}...",
            "status_tool_progress": "Progresso strumento: {name} ({progress}%) {msg}",
            "status_tool_done": "Strumento completato: {name}",
            "status_tool_failed": "Strumento fallito: {name}",
            "status_subagent_start": "Invocazione sotto-agente: {name}",
            "status_compaction_start": "Compattazione del contesto della sessione...",
            "status_compaction_complete": "Compattazione del contesto completata.",
            "status_publishing_file": "Pubblicazione dell'artefatto: {filename}",
            "status_task_completed": "Task completato.",
            "status_todo_hint": "📋 Stato TODO attuale: {todo_text}",
            "plan_title": "Piano d'azione",
            "status_plan_changed": "Piano aggiornato: {operation}",
            "status_context_changed": "Lavoro in {path}",
            "status_intent": "Intento: {intent}",
            "status_session_error": "Elaborazione fallita: {error}",
            "status_no_skill_invoked": "Nessuna skill invocata in questo turno (DEBUG)",
            "debug_agent_working_in": "Agente al lavoro in: {path}",
            "debug_mcp_servers": "🔌 Server MCP connessi: {servers}",
            "publish_success": "File pubblicato correttamente.",
            "publish_hint_html": "Link: [Visualizza {filename}]({view_url}) | [Scarica]({download_url})",
            "publish_hint_embed": "Esperienza Premium: il componente è stato visualizzato direttamente tramite Action.",
            "publish_hint_default": "Link: [Scarica {filename}]({download_url})",
        },
        "es-ES": {
            "status_conn_est": "Conexión establecida, esperando respuesta...",
            "status_reasoning_inj": "Esfuerzo de razonamiento inyectado: {effort}",
            "status_assistant_start": "El Agent está empezando a pensar...",
            "status_assistant_processing": "El Agent está procesando su solicitud...",
            "status_still_working": "Aún procesando... ({seconds}s transcurridos)",
            "status_skill_invoked": "Habilidad detectada y utilizada: {skill}",
            "status_tool_using": "Usando herramienta: {name}...",
            "status_tool_progress": "Progreso de herramienta: {name} ({progress}%) {msg}",
            "status_tool_done": "Herramienta completada: {name}",
            "status_tool_failed": "Herramienta fallida: {name}",
            "status_subagent_start": "Invocando sub-agente: {name}",
            "status_compaction_start": "Compactando el contexto de la sesión...",
            "status_compaction_complete": "Compactación del contexto completada.",
            "status_publishing_file": "Publicando artefacto: {filename}",
            "status_task_completed": "Tarea completada.",
            "status_todo_hint": "📋 Estado actual de TODO: {todo_text}",
            "plan_title": "Plan de acción",
            "status_plan_changed": "Plan actualizado: {operation}",
            "status_context_changed": "Trabajando en {path}",
            "status_intent": "Intento: {intent}",
            "status_session_error": "Error de procesamiento: {error}",
            "status_no_skill_invoked": "No se invocó ninguna habilidad en este turno (DEBUG)",
            "debug_agent_working_in": "Agente trabajando en: {path}",
            "debug_mcp_servers": "🔌 Servidores MCP conectados: {servers}",
            "publish_success": "Archivo publicado con éxito.",
            "publish_hint_html": "Enlace: [Ver {filename}]({view_url}) | [Descargar]({download_url})",
            "publish_hint_embed": "Experiencia Premium: el componente se mostró directamente a través de Action.",
            "publish_hint_default": "Enlace: [Descargar {filename}]({download_url})",
        },
        "vi-VN": {
            "status_conn_est": "Đã thiết lập kết nối, đang chờ phản hồi...",
            "status_reasoning_inj": "Nỗ lực suy luận đã được đưa vào: {effort}",
            "status_assistant_start": "Agent bắt đầu suy nghĩ...",
            "status_assistant_processing": "Agent đang xử lý yêu cầu của bạn...",
            "status_still_working": "Vẫn đang xử lý... ({seconds} giây đã trôi qua)",
            "status_skill_invoked": "Kỹ năng đã được phát hiện và sử dụng: {skill}",
            "status_tool_using": "Đang sử dụng công cụ: {name}...",
            "status_tool_progress": "Tiến độ công cụ: {name} ({progress}%) {msg}",
            "status_tool_done": "Công cụ đã hoàn tất: {name}",
            "status_tool_failed": "Công cụ thất bại: {name}",
            "status_subagent_start": "Đang gọi đại lý phụ: {name}",
            "status_compaction_start": "Đang nén ngữ cảnh phiên...",
            "status_compaction_complete": "Nén ngữ cảnh hoàn tất.",
            "status_publishing_file": "Đang xuất bản thành phẩm: {filename}",
            "status_task_completed": "Nhiệm vụ hoàn tất.",
            "status_todo_hint": "📋 Trạng thái TODO hiện tại: {todo_text}",
            "plan_title": "Kế hoạch hành động",
            "status_plan_changed": "Kế hoạch đã cập nhật: {operation}",
            "status_context_changed": "Đang làm việc tại {path}",
            "status_intent": "Ý định: {intent}",
            "status_session_error": "Xử lý thất bại: {error}",
            "status_no_skill_invoked": "Không có kỹ năng nào được gọi trong lượt này (DEBUG)",
            "debug_agent_working_in": "Agent đang làm việc tại: {path}",
            "debug_mcp_servers": "🔌 Các máy chủ MCP đã kết nối: {servers}",
            "publish_success": "Tệp đã được xuất bản thành công.",
            "publish_hint_html": "Liên kết: [Xem {filename}]({view_url}) | [Tải xuống]({download_url})",
            "publish_hint_embed": "Trải nghiệm Cao cấp: Thành phần đã được hiển thị trực tiếp qua Action.",
            "publish_hint_default": "Liên kết: [Tải xuống {filename}]({download_url})",
        },
        "id-ID": {
            "status_conn_est": "Koneksi terjalin, menunggu respons...",
            "status_reasoning_inj": "Upaya penalaran dimasukkan: {effort}",
            "status_assistant_start": "Agen mulai berpikir...",
            "status_assistant_processing": "Agen sedang memproses permintaan Anda...",
            "status_still_working": "Masih memproses... ({seconds} detik berlalu)",
            "status_skill_invoked": "Keahlian terdeteksi và digunakan: {skill}",
            "status_tool_using": "Menggunakan alat: {name}...",
            "status_tool_progress": "Kemajuan alat: {name} ({progress}%) {msg}",
            "status_tool_done": "Alat selesai: {name}",
            "status_tool_failed": "Alat gagal: {name}",
            "status_subagent_start": "Memanggil sub-agen: {name}",
            "status_compaction_start": "Memadatkan konteks sesi...",
            "status_compaction_complete": "Pemadatan konteks selesai.",
            "status_publishing_file": "Menerbitkan artefak: {filename}",
            "status_task_completed": "Tugas selesai.",
            "status_todo_hint": "📋 Status TODO saat ini: {todo_text}",
            "plan_title": "Rencana Aksi",
            "status_plan_changed": "Rencana diperbarui: {operation}",
            "status_context_changed": "Bekerja di {path}",
            "status_intent": "Niat: {intent}",
            "status_session_error": "Pemrosesan gagal: {error}",
            "status_no_skill_invoked": "Tidak ada keahlian yang dipanggil dalam giliran ini (DEBUG)",
            "debug_agent_working_in": "Agen bekerja di: {path}",
            "debug_mcp_servers": "🔌 Server MCP Terhubung: {servers}",
            "publish_success": "File berhasil diterbitkan.",
            "publish_hint_html": "Tautan: [Lihat {filename}]({view_url}) | [Unduh]({download_url})",
            "publish_hint_embed": "Pengalaman Premium: Komponen ditampilkan secara langsung melalui Action.",
            "publish_hint_default": "Tautan: [Unduh {filename}]({download_url})",
        },
        "ru-RU": {
            "status_conn_est": "Соединение установлено, ожидание ответа...",
            "status_reasoning_inj": "Уровень рассуждения внедрен: {effort}",
            "status_assistant_start": "Agent начинает думать...",
            "status_assistant_processing": "Agent обрабатывает ваш запрос...",
            "status_still_working": "Все еще обрабатывается... (прошло {seconds} сек.)",
            "status_skill_invoked": "Обнаружен и используется навык: {skill}",
            "status_tool_using": "Используется инструмент: {name}...",
            "status_tool_progress": "Прогресс инструмента: {name} ({progress}%) {msg}",
            "status_tool_done": "Инструмент готов: {name}",
            "status_tool_failed": "Ошибка инструмента: {name}",
            "status_subagent_start": "Вызов подагента: {name}",
            "status_compaction_start": "Сжатие контекста сеанса...",
            "status_compaction_complete": "Сжатие контекста завершено.",
            "status_publishing_file": "Публикация файла: {filename}",
            "status_task_completed": "Задача выполнена.",
            "status_todo_hint": "📋 Текущее состояние TODO: {todo_text}",
            "plan_title": "План действий",
            "status_plan_changed": "План обновлен: {operation}",
            "status_context_changed": "Работа в {path}",
            "status_intent": "Намерение: {intent}",
            "status_session_error": "Ошибка обработки: {error}",
            "status_no_skill_invoked": "На этом шаге навыки не вызывались (DEBUG)",
            "debug_agent_working_in": "Рабочий каталог Агента: {path}",
            "debug_mcp_servers": "🔌 Подключенные серверы MCP: {servers}",
            "publish_success": "Файл успешно опубликован.",
            "publish_hint_html": "Ссылка: [Просмотр {filename}]({view_url}) | [Скачать]({download_url})",
            "publish_hint_embed": "Premium: компонент отображен напрямую через Action.",
            "publish_hint_default": "Ссылка: [Скачать {filename}]({download_url})",
        },
    }

    FALLBACK_MAP = {
        "zh": "zh-CN",
        "zh-TW": "zh-TW",
        "zh-HK": "zh-HK",
        "en": "en-US",
        "en-GB": "en-US",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "fr": "fr-FR",
        "de": "de-DE",
        "es": "es-ES",
        "it": "it-IT",
        "ru": "ru-RU",
        "vi": "vi-VN",
        "id": "id-ID",
    }

    def __init__(self):
        self.type = "pipe"
        self.id = "github_copilot_sdk"
        self.name = "copilotsdk"
        self.valves = self.Valves()
        self.temp_dir = tempfile.mkdtemp(prefix="copilot_images_")

    def _resolve_language(self, user_language: str) -> str:
        """Normalize user language code to a supported translation key."""
        if not user_language:
            return "en-US"
        if user_language in self.TRANSLATIONS:
            return user_language
        lang_base = user_language.split("-")[0]
        if user_language in self.FALLBACK_MAP:
            return self.FALLBACK_MAP[user_language]
        if lang_base in self.FALLBACK_MAP:
            return self.FALLBACK_MAP[lang_base]
        return "en-US"

    def _get_translation(self, lang: str, key: str, **kwargs) -> str:
        """Helper function to get translated string for a key."""
        lang_key = self._resolve_language(lang)
        trans_map = self.TRANSLATIONS.get(lang_key, self.TRANSLATIONS["en-US"])
        text = trans_map.get(key, self.TRANSLATIONS["en-US"].get(key, key))
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception as e:
                logger.warning(f"Translation formatting failed for {key}: {e}")
        return text

    def _localize_intent_text(self, lang: str, intent: str) -> str:
        """Best-effort localization for short English intent labels."""
        intent_text = str(intent or "").strip()
        if not intent_text:
            return ""
        if re.search(r"[\u4e00-\u9fff]", intent_text):
            return intent_text

        lang_key = self._resolve_language(lang)
        replacements = {
            "zh-CN": [
                (r"\btodo\s*list\b|\btodolist\b", "待办列表"),
                (r"\btodo\b", "待办"),
                (r"\bcodebase\b", "代码库"),
                (r"\brepository\b|\brepo\b", "仓库"),
                (r"\bworkspace\b", "工作区"),
                (r"\bfiles\b|\bfile\b", "文件"),
                (r"\bchanges\b|\bchange\b", "变更"),
                (r"\brequest\b", "请求"),
                (r"\buser\b", "用户"),
                (r"\breviewing\b|\breview\b", "审查"),
                (r"\banalyzing\b|\banalyse\b|\banalyze\b", "分析"),
                (r"\binspecting\b|\binspect\b|\bchecking\b|\bcheck\b", "检查"),
                (r"\bsearching\b|\bsearch\b", "搜索"),
                (r"\bupdating\b|\bupdate\b", "更新"),
                (r"\bimplementing\b|\bimplement\b", "实现"),
                (r"\bplanning\b|\bplan\b", "规划"),
                (r"\bvalidating\b|\bvalidate\b|\bverifying\b|\bverify\b", "验证"),
                (r"\btesting\b|\btest\b", "测试"),
                (r"\bfixing\b|\bfix\b", "修复"),
                (r"\bdebugging\b|\bdebug\b", "调试"),
                (r"\bediting\b|\bedit\b", "编辑"),
                (r"\breading\b|\bread\b", "读取"),
                (r"\bwriting\b|\bwrite\b", "写入"),
                (r"\bcreating\b|\bcreate\b", "创建"),
                (r"\bpreparing\b|\bprepare\b", "准备"),
                (r"\bsummarizing\b|\bsummarize\b", "总结"),
                (r"\bsyncing\b|\bsync\b", "同步"),
                (r"\band\b", "并"),
            ],
            "zh-HK": [
                (r"\btodo\s*list\b|\btodolist\b", "待辦清單"),
                (r"\btodo\b", "待辦"),
                (r"\bcodebase\b", "程式碼庫"),
                (r"\brepository\b|\brepo\b", "儲存庫"),
                (r"\bworkspace\b", "工作區"),
                (r"\bfiles\b|\bfile\b", "檔案"),
                (r"\bchanges\b|\bchange\b", "變更"),
                (r"\brequest\b", "請求"),
                (r"\buser\b", "使用者"),
                (r"\breviewing\b|\breview\b", "審查"),
                (r"\banalyzing\b|\banalyse\b|\banalyze\b", "分析"),
                (r"\binspecting\b|\binspect\b|\bchecking\b|\bcheck\b", "檢查"),
                (r"\bsearching\b|\bsearch\b", "搜尋"),
                (r"\bupdating\b|\bupdate\b", "更新"),
                (r"\bimplementing\b|\bimplement\b", "實作"),
                (r"\bplanning\b|\bplan\b", "規劃"),
                (r"\bvalidating\b|\bvalidate\b|\bverifying\b|\bverify\b", "驗證"),
                (r"\btesting\b|\btest\b", "測試"),
                (r"\bfixing\b|\bfix\b", "修復"),
                (r"\bdebugging\b|\bdebug\b", "除錯"),
                (r"\bediting\b|\bedit\b", "編輯"),
                (r"\breading\b|\bread\b", "讀取"),
                (r"\bwriting\b|\bwrite\b", "寫入"),
                (r"\bcreating\b|\bcreate\b", "建立"),
                (r"\bpreparing\b|\bprepare\b", "準備"),
                (r"\bsummarizing\b|\bsummarize\b", "總結"),
                (r"\bsyncing\b|\bsync\b", "同步"),
                (r"\band\b", "並"),
            ],
            "zh-TW": [
                (r"\btodo\s*list\b|\btodolist\b", "待辦清單"),
                (r"\btodo\b", "待辦"),
                (r"\bcodebase\b", "程式碼庫"),
                (r"\brepository\b|\brepo\b", "儲存庫"),
                (r"\bworkspace\b", "工作區"),
                (r"\bfiles\b|\bfile\b", "檔案"),
                (r"\bchanges\b|\bchange\b", "變更"),
                (r"\brequest\b", "請求"),
                (r"\buser\b", "使用者"),
                (r"\breviewing\b|\breview\b", "審查"),
                (r"\banalyzing\b|\banalyse\b|\banalyze\b", "分析"),
                (r"\binspecting\b|\binspect\b|\bchecking\b|\bcheck\b", "檢查"),
                (r"\bsearching\b|\bsearch\b", "搜尋"),
                (r"\bupdating\b|\bupdate\b", "更新"),
                (r"\bimplementing\b|\bimplement\b", "實作"),
                (r"\bplanning\b|\bplan\b", "規劃"),
                (r"\bvalidating\b|\bvalidate\b|\bverifying\b|\bverify\b", "驗證"),
                (r"\btesting\b|\btest\b", "測試"),
                (r"\bfixing\b|\bfix\b", "修復"),
                (r"\bdebugging\b|\bdebug\b", "除錯"),
                (r"\bediting\b|\bedit\b", "編輯"),
                (r"\breading\b|\bread\b", "讀取"),
                (r"\bwriting\b|\bwrite\b", "寫入"),
                (r"\bcreating\b|\bcreate\b", "建立"),
                (r"\bpreparing\b|\bprepare\b", "準備"),
                (r"\bsummarizing\b|\bsummarize\b", "總結"),
                (r"\bsyncing\b|\bsync\b", "同步"),
                (r"\band\b", "並"),
            ],
        }

        if lang_key not in replacements:
            return intent_text

        localized = intent_text
        for pattern, replacement in replacements[lang_key]:
            localized = re.sub(pattern, replacement, localized, flags=re.IGNORECASE)
        localized = re.sub(r"\s+", " ", localized).strip(" .,-")
        return localized or intent_text

    def _get_todo_widget_texts(self, lang: str) -> Dict[str, str]:
        """Return dedicated i18n strings for the embedded TODO widget."""
        lang_key = self._resolve_language(lang)
        texts = {
            "en-US": {
                "title": "TODO",
                "total": "Total",
                "pending": "Pending",
                "doing": "Doing",
                "done": "Done",
                "blocked": "Blocked",
                "ready_now": "Ready now: {ready_count}",
                "updated_at": "Updated: {time}",
                "empty": "All tasks are complete.",
                "status_pending": "pending",
                "status_in_progress": "in progress",
                "status_done": "done",
                "status_blocked": "blocked",
            },
            "zh-CN": {
                "title": "待办",
                "total": "总数",
                "pending": "待开始",
                "doing": "进行中",
                "done": "已完成",
                "blocked": "阻塞",
                "ready_now": "当前可执行：{ready_count}",
                "updated_at": "更新时间：{time}",
                "empty": "所有任务都已完成。",
                "status_pending": "待开始",
                "status_in_progress": "进行中",
                "status_done": "已完成",
                "status_blocked": "阻塞",
            },
            "zh-HK": {
                "title": "待辦",
                "total": "總數",
                "pending": "待開始",
                "doing": "進行中",
                "done": "已完成",
                "blocked": "阻塞",
                "ready_now": "當前可執行：{ready_count}",
                "updated_at": "更新時間：{time}",
                "empty": "所有任務都已完成。",
                "status_pending": "待開始",
                "status_in_progress": "進行中",
                "status_done": "已完成",
                "status_blocked": "阻塞",
            },
            "zh-TW": {
                "title": "待辦",
                "total": "總數",
                "pending": "待開始",
                "doing": "進行中",
                "done": "已完成",
                "blocked": "阻塞",
                "ready_now": "當前可執行：{ready_count}",
                "updated_at": "更新時間：{time}",
                "empty": "所有任務都已完成。",
                "status_pending": "待開始",
                "status_in_progress": "進行中",
                "status_done": "已完成",
                "status_blocked": "阻塞",
            },
            "ja-JP": {
                "title": "TODO",
                "total": "合計",
                "pending": "未着手",
                "doing": "進行中",
                "done": "完了",
                "blocked": "ブロック",
                "ready_now": "今すぐ着手可能: {ready_count}",
                "updated_at": "更新時刻: {time}",
                "empty": "すべてのタスクが完了しました。",
                "status_pending": "未着手",
                "status_in_progress": "進行中",
                "status_done": "完了",
                "status_blocked": "ブロック",
            },
            "ko-KR": {
                "title": "할 일",
                "total": "전체",
                "pending": "대기",
                "doing": "진행 중",
                "done": "완료",
                "blocked": "차단",
                "ready_now": "지금 가능한 작업: {ready_count}",
                "updated_at": "업데이트: {time}",
                "empty": "모든 작업이 완료되었습니다.",
                "status_pending": "대기",
                "status_in_progress": "진행 중",
                "status_done": "완료",
                "status_blocked": "차단",
            },
            "fr-FR": {
                "title": "TODO",
                "total": "Total",
                "pending": "En attente",
                "doing": "En cours",
                "done": "Terminées",
                "blocked": "Bloquées",
                "ready_now": "Prêtes maintenant : {ready_count}",
                "updated_at": "Mis a jour : {time}",
                "empty": "Toutes les taches sont terminees.",
                "status_pending": "en attente",
                "status_in_progress": "en cours",
                "status_done": "terminee",
                "status_blocked": "bloquee",
            },
            "de-DE": {
                "title": "TODO",
                "total": "Gesamt",
                "pending": "Offen",
                "doing": "In Arbeit",
                "done": "Erledigt",
                "blocked": "Blockiert",
                "ready_now": "Jetzt bereit: {ready_count}",
                "updated_at": "Aktualisiert: {time}",
                "empty": "Alle Aufgaben sind erledigt.",
                "status_pending": "offen",
                "status_in_progress": "in Arbeit",
                "status_done": "erledigt",
                "status_blocked": "blockiert",
            },
            "it-IT": {
                "title": "TODO",
                "total": "Totale",
                "pending": "In attesa",
                "doing": "In corso",
                "done": "Completati",
                "blocked": "Bloccati",
                "ready_now": "Pronti ora: {ready_count}",
                "updated_at": "Aggiornato: {time}",
                "empty": "Tutte le attivita sono completate.",
                "status_pending": "in attesa",
                "status_in_progress": "in corso",
                "status_done": "completato",
                "status_blocked": "bloccato",
            },
            "es-ES": {
                "title": "TODO",
                "total": "Total",
                "pending": "Pendientes",
                "doing": "En progreso",
                "done": "Hechas",
                "blocked": "Bloqueadas",
                "ready_now": "Listas ahora: {ready_count}",
                "updated_at": "Actualizado: {time}",
                "empty": "Todas las tareas estan completas.",
                "status_pending": "pendiente",
                "status_in_progress": "en progreso",
                "status_done": "hecha",
                "status_blocked": "bloqueada",
            },
            "vi-VN": {
                "title": "TODO",
                "total": "Tong",
                "pending": "Cho xu ly",
                "doing": "Dang lam",
                "done": "Hoan tat",
                "blocked": "Bi chan",
                "ready_now": "Co the lam ngay: {ready_count}",
                "updated_at": "Cap nhat: {time}",
                "empty": "Tat ca tac vu da hoan tat.",
                "status_pending": "cho xu ly",
                "status_in_progress": "dang lam",
                "status_done": "hoan tat",
                "status_blocked": "bi chan",
            },
            "id-ID": {
                "title": "TODO",
                "total": "Total",
                "pending": "Tertunda",
                "doing": "Dikerjakan",
                "done": "Selesai",
                "blocked": "Terblokir",
                "ready_now": "Siap sekarang: {ready_count}",
                "updated_at": "Diperbarui: {time}",
                "empty": "Semua tugas sudah selesai.",
                "status_pending": "tertunda",
                "status_in_progress": "dikerjakan",
                "status_done": "selesai",
                "status_blocked": "terblokir",
            },
            "ru-RU": {
                "title": "TODO",
                "total": "Всего",
                "pending": "Ожидают",
                "doing": "В работе",
                "done": "Готово",
                "blocked": "Заблокировано",
                "ready_now": "Готово к выполнению: {ready_count}",
                "updated_at": "Обновлено: {time}",
                "empty": "Все задачи завершены.",
                "status_pending": "ожидает",
                "status_in_progress": "в работе",
                "status_done": "готово",
                "status_blocked": "заблокировано",
            },
        }
        return texts.get(lang_key, texts["en-US"])

    async def _get_user_context(self, __user__, __event_call__=None, __request__=None):
        """Extract basic user context with safe fallbacks including JS localStorage."""
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        user_id = user_data.get("id", "unknown_user")
        user_name = user_data.get("name", "User")
        user_language = user_data.get("language", "en-US")

        if (
            __request__
            and hasattr(__request__, "headers")
            and "accept-language" in __request__.headers
        ):
            raw_lang = __request__.headers.get("accept-language", "")
            if raw_lang:
                user_language = raw_lang.split(",")[0].split(";")[0]

        if __event_call__:
            try:
                js_code = """
                    try {
                        return (
                            document.documentElement.lang ||
                            localStorage.getItem('locale') ||
                            localStorage.getItem('language') ||
                            navigator.language ||
                            'en-US'
                        );
                    } catch (e) {
                        return 'en-US';
                    }
                """
                frontend_lang = await asyncio.wait_for(
                    __event_call__({"type": "execute", "data": {"code": js_code}}),
                    timeout=2.0,
                )
                if frontend_lang and isinstance(frontend_lang, str):
                    user_language = frontend_lang
            except Exception:
                pass

        return {
            "user_id": user_id,
            "user_name": user_name,
            "user_language": user_language,
        }

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    # ==================== Fixed System Entry ====================
    # pipe() is the stable entry point used by OpenWebUI to handle requests.
    # Keep this section near the top for quick navigation and maintenance.
    # =============================================================
    async def pipe(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
        __request__=None,
        __messages__: Optional[list] = None,
        __files__: Optional[list] = None,
        __task__: Optional[str] = None,
        __task_body__: Optional[str] = None,
        __session_id__: Optional[str] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ) -> Union[str, AsyncGenerator]:
        return await self._pipe_impl(
            body,
            __metadata__=__metadata__,
            __user__=__user__,
            __event_emitter__=__event_emitter__,
            __event_call__=__event_call__,
            __request__=__request__,
            __messages__=__messages__,
            __files__=__files__,
            __task__=__task__,
            __task_body__=__task_body__,
            __session_id__=__session_id__,
            __chat_id__=__chat_id__,
            __message_id__=__message_id__,
        )

    # ==================== Functional Areas ====================
    # 1) Tool registration: define tools and register in _initialize_custom_tools
    # 2) Debug logging: _emit_debug_log / _emit_debug_log_sync
    # 3) Prompt/session: _extract_system_prompt / _build_session_config / _build_prompt
    # 4) Runtime flow: pipe() for request, stream_response() for streaming
    # ============================================================
    # ==================== Custom Tool Examples ====================
    # Tool registration: Add @define_tool decorated functions at module level,
    # then register them in _initialize_custom_tools() -> all_tools dict.
    async def _initialize_custom_tools(
        self,
        body: Optional[dict] = None,
        __user__=None,
        user_lang: str = "en-US",
        __event_emitter__=None,
        __event_call__=None,
        __request__=None,
        __metadata__=None,
        pending_embeds: Optional[List[dict]] = None,
        __messages__: Optional[list] = None,
        __files__: Optional[list] = None,
        __task__: Optional[str] = None,
        __task_body__: Optional[str] = None,
        __session_id__: Optional[str] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ):
        """Initialize custom tools based on configuration"""
        import time

        t_start = time.perf_counter()
        # 1. Determine effective settings (User override > Global)
        uv = self._get_user_valves(__user__)
        enable_tools = uv.ENABLE_OPENWEBUI_TOOLS
        enable_openapi = uv.ENABLE_OPENAPI_SERVER

        # 2. Publish tool is always injected, regardless of other settings
        chat_ctx = self._get_chat_context(body, __metadata__)
        chat_id = chat_ctx.get("chat_id")
        file_tool = self._get_publish_file_tool(
            __user__,
            chat_id,
            __request__,
            __event_emitter__=__event_emitter__,
            pending_embeds=pending_embeds,
        )
        final_tools = [file_tool] if file_tool else []

        # Skill management tool is always injected for deterministic operations
        manage_skills_tool = self._get_manage_skills_tool(__user__, chat_id)
        if manage_skills_tool:
            final_tools.append(manage_skills_tool)

        todo_widget_tool = self._get_render_todo_widget_tool(
            user_lang,
            chat_id,
            __event_emitter__=__event_emitter__,
        )
        if todo_widget_tool:
            final_tools.append(todo_widget_tool)

        t_base_tools_done = time.perf_counter()

        # 3. If all OpenWebUI tool types are disabled, skip loading and return early
        if not enable_tools and not enable_openapi:
            logger.info(
                f"[Perf] _initialize_custom_tools (fast return): {(time.perf_counter() - t_start) * 1000:.2f}ms"
            )
            return final_tools

        # 4. Extract chat-level tool selection (P4: user selection from Chat UI)
        chat_tool_ids = self._normalize_chat_tool_ids(
            __metadata__.get("tool_ids") if isinstance(__metadata__, dict) else None
        )

        # 5. Load OpenWebUI tools dynamically (always fresh, no cache)
        t_dyn_tools_start = time.perf_counter()
        openwebui_tools = await self._load_openwebui_tools(
            body=body,
            __user__=__user__,
            __request__=__request__,
            __event_emitter__=__event_emitter__,
            __event_call__=__event_call__,
            enable_tools=enable_tools,
            enable_openapi=enable_openapi,
            chat_tool_ids=chat_tool_ids,
            __metadata__=__metadata__,
            __messages__=__messages__,
            __files__=__files__,
            __task__=__task__,
            __task_body__=__task_body__,
            __session_id__=__session_id__,
            __chat_id__=__chat_id__,
            __message_id__=__message_id__,
        )
        t_dyn_tools_done = time.perf_counter()

        if openwebui_tools:
            tool_names = [t.name for t in openwebui_tools]
            await self._emit_debug_log(
                f"Loaded {len(openwebui_tools)} tools: {tool_names}",
                __event_call__,
            )
            if self.valves.DEBUG:
                for t in openwebui_tools:
                    await self._emit_debug_log(
                        f"📋 Tool Detail: {t.name} - {t.description[:100]}...",
                        __event_call__,
                    )

        final_tools.extend(openwebui_tools)

        t_total = time.perf_counter() - t_start
        logger.info(
            f"[Perf] _initialize_custom_tools total: {t_total * 1000:.2f}ms (Base tools: {(t_base_tools_done - t_start) * 1000:.2f}ms, Dyn Load: {(t_dyn_tools_done - t_dyn_tools_start) * 1000:.2f}ms)"
        )

        return final_tools

    def _get_render_todo_widget_tool(
        self,
        user_lang,
        chat_id,
        __event_emitter__=None,
    ):
        """Create a compact Rich UI widget tool for live TODO display."""
        if not chat_id or not __event_emitter__:
            return None

        class RenderTodoWidgetParams(BaseModel):
            force: bool = Field(
                default=False,
                description="Force a widget refresh even if the TODO snapshot hash did not change.",
            )

        async def render_todo_widget(params: Any) -> dict:
            force = False
            if hasattr(params, "model_dump"):
                payload = params.model_dump(exclude_unset=True)
                force = bool(payload.get("force", False))
            elif hasattr(params, "dict"):
                payload = params.dict(exclude_unset=True)
                force = bool(payload.get("force", False))
            elif isinstance(params, dict):
                force = bool(params.get("force", False))

            return await self._emit_todo_widget(
                chat_id=chat_id,
                lang=user_lang,
                emitter=__event_emitter__,
                force=force,
            )

        return define_tool(  # type: ignore[call-overload]
            name="render_todo_widget",
            description="Render the current session TODO list as a compact embedded widget. Only refreshes when the TODO snapshot changed unless force=true. Do not restate the widget contents in the final answer unless the user explicitly asks for a textual TODO list.",
            params_type=RenderTodoWidgetParams,
        )(render_todo_widget)

    def _get_publish_file_tool(
        self,
        __user__,
        chat_id,
        __request__=None,
        __event_emitter__=None,
        pending_embeds: Optional[List[dict]] = None,
    ):
        """
        Create a tool to publish files from the workspace to a downloadable URL.
        """
        # Resolve user_id
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        user_id = user_data.get("id") or user_data.get("user_id")
        user_lang = user_data.get("language") or "en-US"
        is_admin = user_data.get("role") == "admin"
        if not user_id:
            return None

        # Resolve workspace directory
        workspace_dir = Path(self._get_workspace_dir(user_id=user_id, chat_id=chat_id))

        # Resolve host from request for absolute URLs
        base_url = ""
        if __request__ and hasattr(__request__, "base_url"):
            base_url = str(__request__.base_url).rstrip("/")
        elif __request__ and hasattr(__request__, "url"):
            # Fallback for different request implementations
            try:
                from urllib.parse import urljoin, urlparse

                parsed = urlparse(str(__request__.url))
                base_url = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                pass

        # Define parameter schema explicitly for the SDK
        class PublishFileParams(BaseModel):
            filename: str = Field(
                ...,
                description=(
                    "The relative path of the file to publish (e.g., 'report.html', 'data/results.csv'). "
                    "The tool will return internal access URLs starting with `/api/v1/files/`. "
                    "You MUST use these specific relative paths as is in your response."
                ),
            )
            embed_type: Literal["artifacts", "richui"] = Field(
                default="richui",
                description=(
                    "Rendering style for HTML files. For PDF files, embedding is disabled and you MUST only provide preview/download Markdown links from tool output. "
                    "Default to 'richui' so the HTML effect is shown directly in OpenWebUI. DO NOT output html_embed in richui mode. If richui is used for long content, you MUST add a 'Full Screen' expansion button in the HTML logic. "
                    'For diagrams, dashboards, timelines, architectures, and explainers, make the page interactive by default, but keep the interaction menu simple: use `data-openwebui-prompt` for immediate continuation, add `data-openwebui-action="fill"` only when you want prefill-only behavior, use `data-openwebui-action="submit"` to send the current chat input, and `data-openwebui-link` for external URLs. Prefer declarative bindings over custom JavaScript. '
                    "Use 'artifacts' only when the user explicitly asks for artifacts. "
                    "Only 'artifacts' and 'richui' are supported."
                ),
            )

        async def publish_file_from_workspace(filename: Any) -> Union[dict, tuple]:
            """
            Publishes a file from the local chat workspace to a downloadable URL.
            If the file is HTML, it will also be directly embedded as an interactive component.
            """
            try:
                # 1. Robust Parameter Extraction
                embed_type = "richui"
                # Case A: filename is a Pydantic model (common when using params_type)
                if hasattr(filename, "model_dump"):  # Pydantic v2
                    data = filename.model_dump()
                    filename = data.get("filename")
                    embed_type = data.get("embed_type", "richui")
                elif hasattr(filename, "dict"):  # Pydantic v1
                    data = filename.dict()
                    filename = data.get("filename")
                    embed_type = data.get("embed_type", "richui")

                # Case B: filename is a dict
                if isinstance(filename, dict):
                    embed_type = filename.get("embed_type") or embed_type
                    filename = (
                        filename.get("filename")
                        or filename.get("file")
                        or filename.get("file_path")
                    )

                # Case C: filename is a JSON string or wrapped string
                if isinstance(filename, str):
                    filename = filename.strip()
                    if filename.startswith("{"):
                        try:
                            import json

                            data = json.loads(filename)
                            if isinstance(data, dict):
                                embed_type = data.get("embed_type") or embed_type
                                filename = (
                                    data.get("filename") or data.get("file") or filename
                                )
                        except:
                            pass

                if embed_type not in ("artifacts", "richui"):
                    embed_type = "richui"

                # 2. Final String Validation
                if (
                    not filename
                    or not isinstance(filename, str)
                    or filename.strip() in ("", "{}", "None", "null")
                ):
                    return {
                        "error": "Missing or invalid required argument: 'filename'.",
                        "hint": f"Received value: {type(filename).__name__}. Please provide the filename as a simple string like 'report.md'.",
                    }

                filename = filename.strip()

                # 2. Path Resolution (Lock to current chat workspace)
                target_path = workspace_dir / filename
                try:
                    target_path = target_path.resolve()
                    if not str(target_path).startswith(str(workspace_dir.resolve())):
                        return {
                            "error": f"Security violation: path traversal detected.",
                            "filename": filename,
                        }
                except Exception as e:
                    return {
                        "error": f"Invalid filename format: {e}",
                        "filename": filename,
                    }

                if not target_path.exists() or not target_path.is_file():
                    wait_deadline = time.monotonic() + 2.0
                    while time.monotonic() < wait_deadline:
                        await asyncio.sleep(0.1)
                        if target_path.exists() and target_path.is_file():
                            break

                if not target_path.exists() or not target_path.is_file():
                    return {
                        "error": f"File not found in workspace: {filename}",
                        "workspace": str(workspace_dir),
                        "hint": "Ensure the file was successfully written using shell commands or create_file tool before publishing. If the file is being generated in the current turn, wait for the write tool to finish before calling publish_file_from_workspace.",
                    }

                # 3. Handle Storage & File ID
                # We check if file already exists in OpenWebUI DB to avoid duplicates
                safe_filename = target_path.name
                try:
                    # deterministic ID based on user + workspace path + filename
                    file_key = f"{user_id}:{workspace_dir}:{safe_filename}"
                    file_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_key))
                except Exception as e:
                    file_id = str(uuid.uuid4())

                existing_file = await _call_openwebui_compat(
                    Files.get_file_by_id,
                    file_id,
                    prefer_thread_for_sync=True,
                )
                if not existing_file:

                    def _upload_via_storage():
                        # Open file and upload to storage provider (S3 or Local)
                        with open(target_path, "rb") as f:
                            _, stored_path = Storage.upload_file(
                                f,
                                f"{file_id}_{safe_filename}",
                                {
                                    "OpenWebUI-User-Id": user_id,
                                    "OpenWebUI-File-Id": file_id,
                                },
                            )
                        return stored_path

                    try:
                        db_path = await asyncio.to_thread(_upload_via_storage)
                    except Exception as e:
                        error_text = str(e)
                        logger.error(
                            f"Publish storage upload failed for '{target_path}': {error_text}"
                        )
                        lowered_error = error_text.lower()
                        if (
                            "nosuchbucket" in lowered_error
                            or "specified bucket does not exist" in lowered_error
                        ):
                            return {
                                "error": "OpenWebUI storage upload failed: the configured object-storage bucket does not exist.",
                                "filename": safe_filename,
                                "hint": "Your OpenWebUI file storage is pointing at an S3-compatible bucket that is missing or misnamed. Create the bucket or fix the bucket name/endpoint/credentials, then retry publish_file_from_workspace.",
                                "storage_stage": "upload_file",
                                "original_error": error_text,
                            }
                        return {
                            "error": f"OpenWebUI storage upload failed: {error_text}",
                            "filename": safe_filename,
                            "hint": "Check the OpenWebUI file-storage backend configuration. publish_file_from_workspace depends on Storage.upload_file() succeeding before preview/download links can be created.",
                            "storage_stage": "upload_file",
                        }

                    file_form = FileForm(
                        id=file_id,
                        filename=safe_filename,
                        path=db_path,
                        data={"status": "completed", "skip_rag": True},
                        meta={
                            "name": safe_filename,
                            "content_type": mimetypes.guess_type(safe_filename)[0]
                            or "text/plain",
                            "size": os.path.getsize(target_path),
                            "source": "copilot_workspace_publish",
                            "skip_rag": True,
                        },
                    )
                    await _call_openwebui_compat(
                        Files.insert_new_file,
                        user_id,
                        file_form,
                        prefer_thread_for_sync=True,
                    )

                # 5. Result Construction
                raw_id = str(file_id).split("/")[-1]
                rel_download_url = f"/api/v1/files/{raw_id}/content"
                download_url = (
                    f"{base_url}{rel_download_url}" if base_url else rel_download_url
                )

                is_html = safe_filename.lower().endswith((".html", ".htm"))
                is_pdf = safe_filename.lower().endswith(".pdf")
                is_img = safe_filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
                )
                is_video = safe_filename.lower().endswith((".mov", ".mp4", ".webm"))

                view_url = None
                has_preview = False

                # Capability Check: Rich UI requires OpenWebUI >= 0.8.0
                rich_ui_supported = self._is_version_at_least("0.8.0")

                if is_html:
                    view_url = f"{download_url}/html"
                    has_preview = True
                elif is_pdf:
                    view_url = download_url
                    # Add download flag to absolute URL carefully
                    sep = "&" if "?" in download_url else "?"
                    download_url = f"{download_url}{sep}download=1"
                    has_preview = True

                # Localized output
                msg = self._get_translation(user_lang, "publish_success")
                if is_html and rich_ui_supported:
                    # Specific sequence for HTML
                    hint = (
                        self._get_translation(user_lang, "publish_hint_embed")
                        + "\n\n"
                        + self._get_translation(
                            user_lang,
                            "publish_hint_html",
                            filename=safe_filename,
                            view_url=view_url,
                            download_url=download_url,
                        )
                    )
                    if embed_type == "richui":
                        hint += "\n\nCRITICAL: You are in 'richui' mode. DO NOT output an HTML code block or iframe in your message. Just output the links above."
                        hint += '\n\nINTERACTION RULE: If the HTML is a diagram, architecture page, explainer, dashboard, or workflow, it SHOULD behave like an exploration interface instead of a static poster. Prefer the declarative contract and keep it simple: use `data-openwebui-prompt` for immediate continuation, add `data-openwebui-action="fill"` only when prefill-only behavior is needed, use `data-openwebui-action="submit"` to send the current chat input, and `data-openwebui-link` for external links. Only use `data-openwebui-copy`, `data-openwebui-select`, or template placeholders for explicit advanced needs.'
                    elif embed_type == "artifacts":
                        hint += "\n\nIMPORTANT: You are in 'artifacts' mode. DO NOT output an HTML code block in your message. The system will automatically inject it after you finish."
                elif has_preview:
                    hint = self._get_translation(
                        user_lang,
                        "publish_hint_html",
                        filename=safe_filename,
                        view_url=view_url,
                        download_url=download_url,
                    )
                else:
                    hint = self._get_translation(
                        user_lang,
                        "publish_hint_default",
                        filename=safe_filename,
                        download_url=download_url,
                    )

                # Fallback for old versions
                if is_html and not rich_ui_supported:
                    hint += f"\n\n**NOTE**: Rich UI embedding is NOT supported in this OpenWebUI version ({open_webui_version}). You SHOULD output the HTML code block manually if the user needs to see the result immediately."

                result_dict = {
                    "file_id": raw_id,
                    "filename": safe_filename,
                    "download_url": download_url,
                    "url_type": "internal_relative_path",
                    "path_specification": "MUST_START_WITH_/api",
                    "message": msg,
                    "hint": hint,
                    "rich_ui_supported": rich_ui_supported,
                }
                if has_preview and view_url:
                    result_dict["view_url"] = view_url

                # Premium Experience for HTML only (Direct Embed via emitter)
                # Emission is delayed until session.idle to avoid UI flicker and ensure reliability.
                if is_html and rich_ui_supported:
                    try:
                        # For BOTH Rich UI and Artifacts Mode, OpenWebUI expects the raw HTML of the component itself
                        embed_content = await asyncio.to_thread(
                            lambda: target_path.read_text(
                                encoding="utf-8", errors="replace"
                            )
                        )

                        if pending_embeds is not None:
                            if embed_type == "richui":
                                embed_content = self._prepare_richui_embed_html(
                                    embed_content, user_lang=user_lang
                                )
                                pending_embeds.append(
                                    {
                                        "filename": safe_filename,
                                        "content": embed_content,
                                        "type": "richui",
                                    }
                                )
                                logger.info(
                                    f"[Copilot] Queued richui embed for '{safe_filename}', pending_embeds len={len(pending_embeds)}"
                                )
                                if __event_emitter__:
                                    await __event_emitter__(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": f"📦 Queued richui embed: {safe_filename} (queue={len(pending_embeds)})",
                                                "done": True,
                                            },
                                        }
                                    )
                            elif embed_type == "artifacts":
                                artifacts_content = f"\n```html\n{embed_content}\n```\n"
                                pending_embeds.append(
                                    {
                                        "filename": safe_filename,
                                        "content": artifacts_content,
                                        "type": "artifacts",
                                    }
                                )
                                logger.info(
                                    f"[Copilot] Queued artifacts embed for '{safe_filename}' (content={len(artifacts_content)}, queue={len(pending_embeds)})"
                                )
                                if __event_emitter__:
                                    await __event_emitter__(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": f"📦 Queued artifacts embed: {safe_filename} (content={len(artifacts_content)}, queue={len(pending_embeds)})",
                                                "done": True,
                                            },
                                        }
                                    )
                        else:
                            logger.warning(
                                f"[Copilot] pending_embeds is None! Cannot queue embed for '{safe_filename}'"
                            )
                            if __event_emitter__:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": f"⚠️ pending_embeds is None for {safe_filename}",
                                            "done": True,
                                        },
                                    }
                                )
                    except Exception as e:
                        logger.error(f"Failed to prepare HTML embed: {e}")

                return result_dict

            except Exception as e:
                logger.error(f"Publish error: {e}")
                return {"error": str(e), "filename": filename}

        return define_tool(  # type: ignore[call-overload]
            name="publish_file_from_workspace",
            description="Converts a file created in your local workspace into a downloadable URL. Use this tool AFTER writing a file to the current directory.",
            params_type=PublishFileParams,
        )(publish_file_from_workspace)

    def _get_manage_skills_tool(self, __user__, chat_id):
        """Create a deterministic standalone skill management tool.

        Supports:
        - install: install skill(s) from URL (GitHub tree URL / zip / tar.gz)
        - list: list installed skills under shared directory
        - create: create skill from current context content
        - edit/show/delete: local skill CRUD
        """
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        user_id = user_data.get("id") or user_data.get("user_id")
        if not user_id:
            return None

        workspace_dir = self._get_workspace_dir(user_id=user_id, chat_id=chat_id)
        shared_dir = self._get_shared_skills_dir(workspace_dir)

        class ManageSkillsParams(BaseModel):
            action: Literal["list", "install", "create", "edit", "delete", "show"] = (
                Field(
                    ...,
                    description="Operation to perform on skills.",
                )
            )
            skill_name: Optional[str] = Field(
                default=None,
                description="Skill name for create/edit/delete/show operations.",
            )
            url: Optional[Union[str, List[str]]] = Field(
                default=None,
                description=(
                    "Source URL(s) for install operation. "
                    "Accepts a single URL string or a list of URLs to install multiple skills at once."
                ),
            )
            description: Optional[str] = Field(
                default=None,
                description="Skill description for create/edit.",
            )
            content: Optional[str] = Field(
                default=None,
                description="Skill instruction body (SKILL.md body) for create/edit.",
            )
            files: Optional[Dict[str, str]] = Field(
                default=None,
                description=(
                    "Extra files to write into the skill folder alongside SKILL.md. "
                    "Keys are relative filenames (e.g. 'template.md', 'examples/usage.py'), "
                    "values are their text content. Useful for templates, example scripts, "
                    "or any resource files the Copilot agent can read from the skill directory."
                ),
            )
            force: Optional[bool] = Field(
                default=False,
                description="Force overwrite for install.",
            )
            dry_run: Optional[bool] = Field(
                default=False,
                description="Preview install without writing files.",
            )
            output_format: Optional[Literal["text", "json"]] = Field(
                default="text",
                description="Output format for list action.",
            )

        def _sanitize_skill_name(name: str) -> str:
            clean = self._skill_dir_name_from_skill_name(name)
            return re.sub(r"\s+", "-", clean)

        def _normalize_github_archive_url(url: str) -> tuple[str, str]:
            parsed = urllib.parse.urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]
            # GitHub tree URL: /owner/repo/tree/branch/subpath
            if parsed.netloc.endswith("github.com") and "tree" in path_parts:
                tree_idx = path_parts.index("tree")
                if tree_idx >= 2 and len(path_parts) > tree_idx + 1:
                    owner = path_parts[0]
                    repo = path_parts[1]
                    branch = path_parts[tree_idx + 1]
                    subpath = "/".join(path_parts[tree_idx + 2 :])
                    archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
                    return archive_url, subpath
            return url, ""

        def _extract_archive(archive_path: Path, dest_dir: Path) -> Path:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(dest_dir)
            elif archive_path.name.endswith(".tar.gz") or archive_path.suffix in {
                ".tgz",
                ".tar",
            }:
                with tarfile.open(archive_path, "r:*") as tf:
                    tf.extractall(dest_dir)
            else:
                raise ValueError(f"Unsupported archive format: {archive_path.name}")

            children = [p for p in dest_dir.iterdir() if p.is_dir()]
            if len(children) == 1:
                return children[0]
            return dest_dir

        def _discover_skill_dirs(root: Path, subpath: str = "") -> List[Path]:
            target = root / subpath if subpath else root
            target = target.resolve()
            if not target.exists() or not target.is_dir():
                raise ValueError(
                    f"Skill source path not found in archive: {subpath or str(root)}"
                )

            if (target / "SKILL.md").exists() or (target / "README.md").exists():
                return [target]

            found = []
            for child in target.iterdir():
                if child.is_dir() and (
                    (child / "SKILL.md").exists() or (child / "README.md").exists()
                ):
                    found.append(child)
            if not found:
                raise ValueError("No valid skill found (need SKILL.md or README.md)")
            return found

        def _copy_skill_dir(src_dir: Path, dest_root: Path, force: bool = False) -> str:
            skill_name = _sanitize_skill_name(src_dir.name)
            dest_dir = dest_root / skill_name
            if dest_dir.exists():
                if not force:
                    raise FileExistsError(f"Skill already exists: {skill_name}")
                shutil.rmtree(dest_dir)

            shutil.copytree(src_dir, dest_dir)
            readme = dest_dir / "README.md"
            skill_md = dest_dir / "SKILL.md"
            if not skill_md.exists() and readme.exists():
                readme.rename(skill_md)
            if not skill_md.exists():
                raise ValueError(f"Installed directory missing SKILL.md: {skill_name}")
            return skill_name

        def _list_skills_text(skills: List[dict]) -> str:
            if not skills:
                return "No skills found"
            lines = []
            for s in skills:
                lines.append(f"- {s['name']}: {s.get('description', '')}")
            return "\n".join(lines)

        async def manage_skills(params: Any) -> dict:
            try:
                if hasattr(params, "model_dump"):
                    payload = params.model_dump(exclude_unset=True)
                elif isinstance(params, dict):
                    payload = params
                else:
                    payload = {}

                action = str(payload.get("action", "")).strip().lower()
                skill_name = (payload.get("skill_name") or "").strip()
                _raw_url = payload.get("url") or ""
                if isinstance(_raw_url, list):
                    source_urls = [u.strip() for u in _raw_url if u and u.strip()]
                    source_url = source_urls[0] if source_urls else ""
                else:
                    source_url = str(_raw_url).strip()
                    source_urls = [source_url] if source_url else []
                skill_desc = (payload.get("description") or "").strip()
                skill_body = (payload.get("content") or "").strip()
                force = bool(payload.get("force", False))
                dry_run = bool(payload.get("dry_run", False))
                output_format = (
                    str(payload.get("output_format", "text")).strip().lower()
                )

                if action == "list":
                    entries = []
                    root = Path(shared_dir)
                    if root.exists():
                        for child in sorted(
                            root.iterdir(), key=lambda p: p.name.lower()
                        ):
                            if not child.is_dir():
                                continue
                            skill_md = child / "SKILL.md"
                            if not skill_md.exists():
                                continue
                            name, desc, _ = self._parse_skill_md_meta(
                                skill_md.read_text(encoding="utf-8"), child.name
                            )
                            entries.append(
                                {
                                    "name": name or child.name,
                                    "dir_name": child.name,
                                    "description": desc,
                                    "path": str(skill_md),
                                }
                            )
                    if output_format == "json":
                        return {"skills": entries, "count": len(entries)}
                    return {"count": len(entries), "text": _list_skills_text(entries)}

                if action == "install":
                    if not source_urls:
                        return {"error": "Missing required argument: url"}

                    all_installed: List[str] = []
                    errors: List[str] = []

                    for _url in source_urls:
                        archive_url, subpath = _normalize_github_archive_url(_url)
                        tmp_dir = Path(tempfile.mkdtemp(prefix="skill-install-"))
                        try:
                            suffix = ".zip"
                            if archive_url.endswith(".tar.gz"):
                                suffix = ".tar.gz"
                            elif archive_url.endswith(".tgz"):
                                suffix = ".tgz"
                            archive_path = tmp_dir / f"download{suffix}"

                            await asyncio.to_thread(
                                urllib.request.urlretrieve,
                                archive_url,
                                str(archive_path),
                            )
                            extracted_root = _extract_archive(
                                archive_path, tmp_dir / "extract"
                            )
                            candidates = _discover_skill_dirs(extracted_root, subpath)

                            for candidate in candidates:
                                if dry_run:
                                    all_installed.append(
                                        _sanitize_skill_name(candidate.name)
                                    )
                                else:
                                    all_installed.append(
                                        _copy_skill_dir(
                                            candidate, Path(shared_dir), force=force
                                        )
                                    )
                        except Exception as e:
                            errors.append(f"{_url}: {e}")
                        finally:
                            shutil.rmtree(tmp_dir, ignore_errors=True)

                    if not dry_run and all_installed:
                        # Immediately sync new skills to OW DB so frontend
                        # reflects them without needing a new request.
                        try:
                            await asyncio.to_thread(
                                self._sync_openwebui_skills, workspace_dir, user_id
                            )
                        except Exception:
                            pass

                    return {
                        "success": len(errors) == 0,
                        "action": "install",
                        "dry_run": dry_run,
                        "installed": all_installed,
                        "count": len(all_installed),
                        **({"errors": errors} if errors else {}),
                    }

                if action in {"create", "edit", "show", "delete"}:
                    if not skill_name:
                        return {
                            "error": "Missing required argument: skill_name for this action"
                        }
                    dir_name = self._skill_dir_name_from_skill_name(skill_name)
                    skill_dir = Path(shared_dir) / dir_name
                    skill_md = skill_dir / "SKILL.md"

                    if action == "show":
                        if not skill_dir.exists():
                            return {"error": f"Skill not found: {dir_name}"}
                        # Return SKILL.md content plus a listing of all other files
                        skill_md_content = (
                            skill_md.read_text(encoding="utf-8")
                            if skill_md.exists()
                            else ""
                        )
                        other_files = []
                        for f in sorted(skill_dir.rglob("*")):
                            if f.is_file() and f.name not in ("SKILL.md", ".owui_id"):
                                rel = str(f.relative_to(skill_dir))
                                other_files.append(rel)
                        return {
                            "skill_name": dir_name,
                            "path": str(skill_dir),
                            "skill_md": skill_md_content,
                            "other_files": other_files,
                        }

                    if action == "delete":
                        if not skill_dir.exists():
                            return {"error": f"Skill not found: {dir_name}"}
                        # Remove from OW DB before deleting local dir, otherwise
                        # next-request sync will recreate the directory from DB.
                        owui_id_file = skill_dir / ".owui_id"
                        if owui_id_file.exists():
                            owui_id = owui_id_file.read_text(encoding="utf-8").strip()
                            if owui_id:
                                try:
                                    from open_webui.models.skills import Skills

                                    Skills.delete_skill_by_id(owui_id)
                                except Exception:
                                    pass
                        shutil.rmtree(skill_dir)
                        return {
                            "success": True,
                            "action": "delete",
                            "skill_name": dir_name,
                            "path": str(skill_dir),
                        }

                    # create / edit
                    if action == "create" and skill_dir.exists() and not force:
                        return {
                            "error": f"Skill already exists: {dir_name}. Use force=true to overwrite."
                        }

                    if action == "edit" and not skill_md.exists():
                        return {
                            "error": f"Skill not found: {dir_name}. Create it first."
                        }

                    existing_content = ""
                    if skill_md.exists():
                        existing_content = skill_md.read_text(encoding="utf-8")

                    parsed_name, parsed_desc, parsed_body = self._parse_skill_md_meta(
                        existing_content, dir_name
                    )

                    final_name = skill_name or parsed_name or dir_name
                    final_desc = skill_desc or parsed_desc or final_name
                    final_body = (
                        skill_body or parsed_body or "Describe how to use this skill."
                    )

                    skill_dir.mkdir(parents=True, exist_ok=True)
                    final_content = self._build_skill_md_content(
                        final_name, final_desc, final_body
                    )
                    skill_md.write_text(final_content, encoding="utf-8")

                    # Write any extra files into the skill folder.
                    # These are accessible to the Copilot SDK agent but not synced to OW DB.
                    extra_files = payload.get("files") or {}
                    if not isinstance(extra_files, dict):
                        return {
                            "error": "Invalid 'files' parameter: must be a dictionary of {filename: content} pairs"
                        }

                    written_files = []
                    for rel_path, file_content in extra_files.items():
                        # Sanitize: prevent absolute paths or path traversal
                        rel = Path(rel_path)
                        if rel.is_absolute() or any(part == ".." for part in rel.parts):
                            continue
                        dest = skill_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(file_content, encoding="utf-8")
                        written_files.append(str(rel))

                    # Immediately sync to OW DB so frontend reflects the change.
                    try:
                        await asyncio.to_thread(
                            self._sync_openwebui_skills, workspace_dir, user_id
                        )
                    except Exception:
                        pass

                    return {
                        "success": True,
                        "action": action,
                        "skill_name": dir_name,
                        "skill_dir": str(skill_dir),
                        "skill_md": str(skill_md),
                        "extra_files_written": written_files,
                    }

                return {"error": f"Unsupported action: {action}"}
            except Exception as e:
                return {"error": str(e)}

        return define_tool(  # type: ignore[call-overload]
            name="manage_skills",
            description="Manage skills deterministically: install/list/create/edit/delete/show. Supports creating skill content from current context.",
            params_type=ManageSkillsParams,
        )(manage_skills)

    def _json_schema_to_python_type(self, schema: dict) -> Any:
        """Convert JSON Schema type to Python type for Pydantic models."""
        if not isinstance(schema, dict):
            return Any

        # Check for Enum (Literal)
        enum_values = schema.get("enum")
        if enum_values and isinstance(enum_values, list):
            from typing import Literal

            return Literal[tuple(enum_values)]

        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            schema_type = next((t for t in schema_type if t != "null"), schema_type[0])

        if schema_type == "string":
            return str
        if schema_type == "integer":
            return int
        if schema_type == "number":
            return float
        if schema_type == "boolean":
            return bool
        if schema_type == "object":
            return Dict[str, Any]
        if schema_type == "array":
            items_schema = schema.get("items", {})
            item_type = self._json_schema_to_python_type(items_schema)
            return List[item_type]

        return Any

    def _convert_openwebui_tool_to_sdk(
        self,
        tool_name: str,
        tool_dict: dict,
        __event_emitter__=None,
        __event_call__=None,
        user_lang: Optional[str] = None,
    ):
        """Convert OpenWebUI tool definition to Copilot SDK tool."""
        # Sanitize tool name to match pattern ^[a-zA-Z0-9_-]+$
        sanitized_tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_name)

        # If sanitized name is empty or consists only of separators (e.g. pure Chinese name), generate a fallback name
        if not sanitized_tool_name or re.match(r"^[_.-]+$", sanitized_tool_name):
            hash_suffix = hashlib.md5(tool_name.encode("utf-8")).hexdigest()[:8]
            sanitized_tool_name = f"tool_{hash_suffix}"

        if sanitized_tool_name != tool_name:
            logger.debug(
                f"Sanitized tool name '{tool_name}' to '{sanitized_tool_name}'"
            )

        spec = tool_dict.get("spec", {}) if isinstance(tool_dict, dict) else {}
        params_schema = spec.get("parameters", {}) if isinstance(spec, dict) else {}
        properties = params_schema.get("properties", {})
        required = params_schema.get("required", [])

        if not isinstance(properties, dict):
            properties = {}
        if not isinstance(required, list):
            required = []

        required_set = set(required)
        fields = {}
        for param_name, param_schema in properties.items():
            param_type = self._json_schema_to_python_type(param_schema)
            description = ""
            if isinstance(param_schema, dict):
                description = param_schema.get("description", "")

            # Extract default value if present
            default_value = None
            if isinstance(param_schema, dict) and "default" in param_schema:
                default_value = param_schema.get("default")

            if param_name in required_set:
                if description:
                    fields[param_name] = (
                        param_type,
                        Field(..., description=description),
                    )
                else:
                    fields[param_name] = (param_type, ...)
            else:
                # If not required, wrap in Optional and use default_value
                optional_type = Optional[param_type]
                if description:
                    fields[param_name] = (
                        optional_type,
                        Field(default=default_value, description=description),
                    )
                else:
                    fields[param_name] = (optional_type, default_value)

        if fields:
            ParamsModel = create_model(f"{sanitized_tool_name}_Params", **fields)
        else:
            ParamsModel = create_model(f"{sanitized_tool_name}_Params")

        tool_callable = tool_dict.get("callable")
        tool_description = spec.get("description", "") if isinstance(spec, dict) else ""
        if not tool_description and isinstance(spec, dict):
            tool_description = spec.get("summary", "")

        # Determine tool source/group for description prefix
        tool_id = tool_dict.get("tool_id", "")
        tool_type = tool_dict.get(
            "type", ""
        )  # "builtin", "external", or empty (user-defined)

        if tool_type == "builtin":
            # OpenWebUI Built-in Tool (system tools like web search, memory, notes)
            group_prefix = "[OpenWebUI Built-in]"
        elif tool_type == "external" or tool_id.startswith("server:"):
            # OpenAPI Tool Server - use metadata if available
            tool_group_name = tool_dict.get("_tool_group_name")
            tool_group_desc = tool_dict.get("_tool_group_description")
            server_id = (
                tool_id.replace("server:", "").split("|")[0]
                if tool_id.startswith("server:")
                else tool_id
            )

            if tool_group_name:
                if tool_group_desc:
                    group_prefix = (
                        f"[Tool Server: {tool_group_name} - {tool_group_desc}]"
                    )
                else:
                    group_prefix = f"[Tool Server: {tool_group_name}]"
            else:
                group_prefix = f"[Tool Server: {server_id}]"
        else:
            # User-defined Python script tool - use metadata if available
            tool_group_name = tool_dict.get("_tool_group_name")
            tool_group_desc = tool_dict.get("_tool_group_description")

            if tool_group_name:
                # Use the tool's title from docstring, e.g., "Prefect API Tools"
                if tool_group_desc:
                    group_prefix = f"[User Tool: {tool_group_name} - {tool_group_desc}]"
                else:
                    group_prefix = f"[User Tool: {tool_group_name}]"
            else:
                group_prefix = f"[User Tool: {tool_id}]" if tool_id else "[User Tool]"

        # Build final description with group prefix
        if sanitized_tool_name != tool_name:
            # Include original name if it was sanitized
            tool_description = (
                f"{group_prefix} Function '{tool_name}': {tool_description}"
            )
        else:
            tool_description = f"{group_prefix} {tool_description}"

        async def _tool(params):
            # Crucial Fix: Use exclude_unset=True.
            # This ensures that parameters not explicitly provided by the LLM
            # (which default to None in the Pydantic model) are COMPLETELY OMITTED
            # from the function call. This allows the underlying Python function's
            # own default values to take effect, instead of receiving an explicit None.
            payload = (
                params.model_dump(exclude_unset=True)
                if hasattr(params, "model_dump")
                else {}
            )

            try:
                if self.valves.DEBUG:
                    payload_debug = {}
                    for key, value in payload.items():
                        if isinstance(value, str):
                            payload_debug[key] = {
                                "type": "str",
                                "len": len(value),
                                "preview": value[:160],
                            }
                        elif isinstance(value, (list, tuple)):
                            payload_debug[key] = {
                                "type": type(value).__name__,
                                "len": len(value),
                            }
                        elif isinstance(value, dict):
                            payload_debug[key] = {
                                "type": "dict",
                                "keys": list(value.keys())[:12],
                            }
                        else:
                            payload_debug[key] = {"type": type(value).__name__}

                    await self._emit_debug_log(
                        f"🛠️ Invoking {sanitized_tool_name} with params: {list(payload.keys())}; payload={payload_debug}",
                        __event_call__,
                    )

                if tool_callable is None:
                    raise RuntimeError(
                        f"Tool {sanitized_tool_name} has no callable registered"
                    )
                result = await tool_callable(**payload)

                if self.valves.DEBUG:
                    if isinstance(result, str):
                        result_debug = {
                            "type": "str",
                            "len": len(result),
                            "preview": result[:220],
                        }
                    elif isinstance(result, tuple):
                        result_debug = {
                            "type": "tuple",
                            "len": len(result),
                            "item_types": [type(item).__name__ for item in result[:3]],
                        }
                    elif isinstance(result, dict):
                        result_debug = {
                            "type": "dict",
                            "keys": list(result.keys())[:20],
                        }
                    elif isinstance(result, HTMLResponse):
                        body_data = result.body
                        body_text = (
                            body_data.decode("utf-8", errors="ignore")
                            if isinstance(body_data, (bytes, bytearray))
                            else str(body_data)
                        )
                        result_debug = {
                            "type": "HTMLResponse",
                            "body_len": len(body_text),
                            "headers": dict(result.headers),
                            "body_preview": body_text[:300],
                        }
                    else:
                        result_debug = {"type": type(result).__name__}

                    await self._emit_debug_log(
                        f"🧾 Tool result summary '{sanitized_tool_name}': {result_debug}",
                        __event_call__,
                    )

                # Support v0.8.0+ Action-style returns (tuple with  headers)
                if isinstance(result, tuple) and len(result) == 2:
                    data, headers = result
                    # Basic heuristic to detect response headers (aiohttp headers or dict)
                    if hasattr(headers, "get") and hasattr(headers, "items"):
                        # If Content-Disposition is 'inline', it's a Direct HTML/Embed result
                        if (
                            "inline"
                            in str(headers.get("Content-Disposition", "")).lower()
                        ):
                            embed_payload = self._prepare_richui_embed_html(
                                data, user_lang=user_lang
                            )
                            if __event_emitter__:
                                await __event_emitter__(
                                    {
                                        "type": "embeds",
                                        "data": {"embeds": [embed_payload]},
                                    }
                                )
                            # Follow OpenWebUI official process_tool_result format
                            final_result = {
                                "status": "success",
                                "code": "ui_component",
                                "message": f"{sanitized_tool_name}: Embedded UI result is active and visible to the user.",
                            }
                            if self.valves.DEBUG:
                                await self._emit_debug_log(
                                    f"📤 Returning inline tuple dict result: {final_result}",
                                    __event_call__,
                                )
                            return final_result

                        # Standard tuple return for OpenAPI tools etc.
                        if self.valves.DEBUG:
                            final_data = data
                            if isinstance(final_data, str):
                                await self._emit_debug_log(
                                    f"📤 Returning tuple[0] (data): type='str', len={len(final_data)}, preview={repr(final_data[:160])}",
                                    __event_call__,
                                )
                            else:
                                await self._emit_debug_log(
                                    f"📤 Returning tuple[0] (data): type={type(final_data).__name__}",
                                    __event_call__,
                                )
                        return data

                # Support FastAPI/Starlette HTMLResponse (e.g., from smart_mind_map_tool)
                if isinstance(result, HTMLResponse):
                    disposition = str(
                        result.headers.get("Content-Disposition", "")
                        or result.headers.get("content-disposition", "")
                    ).lower()
                    if "inline" in disposition:
                        body_data = result.body
                        body_text = (
                            body_data.decode("utf-8", errors="ignore")
                            if isinstance(body_data, (bytes, bytearray))
                            else str(body_data)
                        )
                        body_text = self._prepare_richui_embed_html(
                            body_text, user_lang=user_lang
                        )

                        # Extract markdown-source content for diagnostic
                        import re as _re

                        _md_match = _re.search(
                            r'<script[^>]*id="markdown-source-[^"]*"[^>]*>([\s\S]*?)</script>',
                            body_text,
                        )
                        _md_content = _md_match.group(1) if _md_match else "(not found)"
                        await self._emit_debug_log(
                            f"[Embed] HTMLResponse from '{sanitized_tool_name}': "
                            f"body_len={len(body_text)}, "
                            f"emitter_available={__event_emitter__ is not None}, "
                            f"markdown_source_len={len(_md_content)}, "
                            f"markdown_source_preview={repr(_md_content[:600])}",
                            __event_call__,
                        )

                        if __event_emitter__ and body_text:
                            await __event_emitter__(
                                {
                                    "type": "embeds",
                                    "data": {"embeds": [body_text]},
                                }
                            )

                        # Return string (not dict): Copilot SDK backend expects string tool results
                        final_result = f"{sanitized_tool_name}: Embedded UI result is active and visible to the user."

                        if self.valves.DEBUG:
                            await self._emit_debug_log(
                                f"📤 Returning from HTMLResponse: type='str', len={len(final_result)}",
                                __event_call__,
                            )
                        return final_result

                    # Non-inline HTMLResponse: return decoded body text
                    body_data = result.body
                    final_result = (
                        body_data.decode("utf-8", errors="replace")
                        if isinstance(body_data, (bytes, bytearray))
                        else str(body_data)
                    )

                    if self.valves.DEBUG:
                        await self._emit_debug_log(
                            f"📤 Returning from non-inline HTMLResponse: type='str', len={len(final_result)}, preview={repr(final_result[:160])}",
                            __event_call__,
                        )
                    return final_result

                # Generic return for all other types
                if self.valves.DEBUG:
                    if isinstance(result, str):
                        await self._emit_debug_log(
                            f"📤 Returning string result: len={len(result)}, preview={repr(result[:160])}",
                            __event_call__,
                        )
                    else:
                        await self._emit_debug_log(
                            f"📤 Returning {type(result).__name__} result",
                            __event_call__,
                        )
                return result
            except Exception as e:
                # detailed traceback
                err_msg = f"{str(e)}"
                await self._emit_debug_log(
                    f"❌ Tool Execution Failed '{sanitized_tool_name}': {err_msg}",
                    __event_call__,
                )

                # Re-raise with a clean message so the LLM sees the error
                raise RuntimeError(f"Tool {sanitized_tool_name} failed: {err_msg}")

        _tool.__name__ = sanitized_tool_name
        _tool.__doc__ = tool_description

        # Debug log for tool conversion
        logger.debug(
            f"Converting tool '{sanitized_tool_name}': {tool_description[:50]}..."
        )

        # Core Fix: Explicitly pass params_type and name
        return define_tool(  # type: ignore[call-overload]
            name=sanitized_tool_name,
            description=tool_description,
            params_type=ParamsModel,
        )(_tool)

    async def _read_tool_server_connections(self) -> list:
        """
        Read tool server connections directly from the database to avoid stale
        in-memory state in multi-worker deployments.
        Falls back to the in-memory PersistentConfig value if DB read fails.
        """
        try:
            from open_webui.config import get_config

            config_data = await _call_openwebui_compat(
                get_config,
                prefer_thread_for_sync=True,
            )
            if hasattr(config_data, "model_dump"):
                config_data = config_data.model_dump()
            elif hasattr(config_data, "dict"):
                config_data = config_data.dict()
            connections = config_data.get("tool_server", {}).get("connections", None)
            if connections is not None:
                return connections if isinstance(connections, list) else []
        except Exception as e:
            logger.debug(
                f"[Tools] DB config read failed, using in-memory fallback: {e}"
            )

        # Fallback: in-memory value (may be stale in multi-worker)
        if hasattr(TOOL_SERVER_CONNECTIONS, "value") and isinstance(
            TOOL_SERVER_CONNECTIONS.value, list
        ):
            return TOOL_SERVER_CONNECTIONS.value
        return []

    async def _build_openwebui_request(
        self,
        user: Optional[dict] = None,
        token: Optional[str] = None,
        body: Optional[dict] = None,
    ):
        """Build a more complete request-like object with dynamically loaded OpenWebUI configs."""
        # Dynamically build config from the official registry
        config = SimpleNamespace()
        for item in PERSISTENT_CONFIG_REGISTRY:
            # Special handling for TOOL_SERVER_CONNECTIONS which might be a list/dict object
            # rather than a simple primitive value, though .value handles the latest state
            val = item.value
            if hasattr(val, "value"):  # Handling nested structures if any
                val = val.value
            setattr(config, item.env_name, val)

        # Critical Fix: Explicitly sync TOOL_SERVER_CONNECTIONS to ensure OpenAPI tools work
        # Read directly from DB to avoid stale in-memory state in multi-worker deployments
        fresh_connections = await self._read_tool_server_connections()
        config.TOOL_SERVER_CONNECTIONS = fresh_connections

        # Try to populate real models to avoid "Model not found" in generate_chat_completion
        # Keep entries as dict-like payloads to avoid downstream `.get()` crashes
        # when OpenWebUI internals treat model records as mappings.
        system_models = {}
        try:
            from open_webui.models.models import Models as _Models

            all_models = await _call_openwebui_compat(
                _Models.get_all_models,
                prefer_thread_for_sync=True,
            )
            for m in all_models:
                model_payload = None
                if isinstance(m, dict):
                    model_payload = m
                elif hasattr(m, "model_dump"):
                    try:
                        dumped = m.model_dump()
                        if isinstance(dumped, dict):
                            model_payload = dumped
                    except Exception:
                        model_payload = None

                if model_payload is None:
                    model_payload = {
                        "id": getattr(m, "id", None),
                        "name": getattr(m, "name", None),
                        "base_model_id": getattr(m, "base_model_id", None),
                    }

                model_id = (
                    model_payload.get("id") if isinstance(model_payload, dict) else None
                )
                model_name = (
                    model_payload.get("name")
                    if isinstance(model_payload, dict)
                    else None
                )

                # Map both ID and name for maximum compatibility during resolution
                if model_id:
                    system_models[str(model_id)] = model_payload
                if model_name:
                    system_models[str(model_name)] = model_payload
        except Exception:
            pass

        app_state = SimpleNamespace(
            config=config,
            TOOLS={},
            TOOL_CONTENTS={},
            FUNCTIONS={},
            FUNCTION_CONTENTS={},
            MODELS=system_models,
            redis=None,  # Crucial: prevent AttributeError in get_tool_servers
            TOOL_SERVERS=[],  # Initialize as empty list
        )

        def url_path_for(name: str, **path_params):
            """Mock url_path_for for tool compatibility."""
            if name == "get_file_content_by_id":
                return f"/api/v1/files/{path_params.get('id')}/content"
            return f"/mock/{name}"

        app = SimpleNamespace(
            state=app_state,
            url_path_for=url_path_for,
        )

        # Mocking generic request attributes
        req_headers = {
            "user-agent": "Mozilla/5.0 (OpenWebUI Plugin/GitHub-Copilot-SDK)",
            "host": "localhost:8080",
            "accept": "*/*",
        }
        if token:
            req_headers["Authorization"] = (
                token if str(token).startswith("Bearer ") else f"Bearer {token}"
            )

        async def _json():
            return body or {}

        async def _body():
            import json

            return json.dumps(body or {}).encode("utf-8")

        request = SimpleNamespace(
            app=app,
            url=SimpleNamespace(
                path="/api/chat/completions",
                base_url="http://localhost:8080",
                __str__=lambda s: "http://localhost:8080/api/chat/completions",
            ),
            base_url="http://localhost:8080",
            headers=req_headers,
            method="POST",
            cookies={},
            state=SimpleNamespace(
                token=SimpleNamespace(credentials=token if token else ""),
                user=user if user else {},
            ),
            json=_json,
            body=_body,
        )
        return request

    async def _load_openwebui_tools(
        self,
        body: Optional[dict] = None,
        __user__=None,
        __request__=None,
        __event_emitter__=None,
        __event_call__=None,
        enable_tools: bool = True,
        enable_openapi: bool = True,
        chat_tool_ids: Optional[list] = None,
        __metadata__: Optional[dict] = None,
        __messages__: Optional[list] = None,
        __files__: Optional[list] = None,
        __task__: Optional[str] = None,
        __task_body__: Optional[str] = None,
        __session_id__: Optional[str] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ):
        """Load OpenWebUI tools and convert them to Copilot SDK tools."""
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        if not user_data:
            return []

        user_id = user_data.get("id") or user_data.get("user_id")
        user_lang = user_data.get("language") or "en-US"
        if not user_id:
            return []

        metadata_dict: Dict[str, Any] = {}
        if isinstance(__metadata__, dict):
            metadata_dict = __metadata__
        elif __metadata__ is not None and hasattr(__metadata__, "model_dump"):
            try:
                dumped = __metadata__.model_dump()
                if isinstance(dumped, dict):
                    metadata_dict = dumped
            except Exception:
                metadata_dict = {}

        # Normalize metadata.model shape to avoid downstream `.get()` crashes
        # when OpenWebUI injects Pydantic model objects (e.g., ModelModel).
        raw_meta_model = metadata_dict.get("model")
        if raw_meta_model is not None and not isinstance(raw_meta_model, (dict, str)):
            normalized_model: Any = None

            if hasattr(raw_meta_model, "model_dump"):
                try:
                    dumped_model = raw_meta_model.model_dump()
                    if isinstance(dumped_model, dict):
                        normalized_model = dumped_model
                except Exception:
                    normalized_model = None

            if normalized_model is None:
                normalized_model = (
                    getattr(raw_meta_model, "id", None)
                    or getattr(raw_meta_model, "base_model_id", None)
                    or getattr(raw_meta_model, "model", None)
                )

            if normalized_model is not None:
                metadata_dict["model"] = normalized_model
            else:
                metadata_dict["model"] = str(raw_meta_model)

        # --- PROBE LOG ---
        if __event_call__:
            conn_list = await self._read_tool_server_connections()
            conn_summary = []
            for i, s in enumerate(conn_list):
                if isinstance(s, dict):
                    s_id = s.get("info", {}).get("id") or s.get("id") or str(i)
                    s_type = s.get("type", "openapi")
                    s_enabled = s.get("config", {}).get("enable", False)
                    conn_summary.append(
                        {"id": s_id, "type": s_type, "enable": s_enabled}
                    )

            await self._emit_debug_log(
                f"[Tools] TOOL_SERVER_CONNECTIONS ({len(conn_summary)} entries): {conn_summary}",
                __event_call__,
            )
        # -----------------

        user = await _call_openwebui_compat(
            Users.get_user_by_id,
            user_id,
            prefer_thread_for_sync=True,
        )
        if not user:
            return []

        tool_ids = []
        # 1. Get User defined tools (Python scripts)
        if enable_tools:
            tool_items = await _call_openwebui_compat(
                Tools.get_tools_by_user_id,
                user_id,
                permission="read",
                prefer_thread_for_sync=True,
            )
            if tool_items:
                tool_ids.extend([tool.id for tool in tool_items])

        # 2. Get OpenAPI Tool Server tools
        if enable_openapi:
            raw_connections = await self._read_tool_server_connections()

            # Handle Pydantic model vs List vs Dict
            connections = []
            if isinstance(raw_connections, list):
                connections = raw_connections
            elif hasattr(raw_connections, "dict"):
                connections = raw_connections.dict()
            elif hasattr(raw_connections, "model_dump"):
                connections = raw_connections.model_dump()

            # Debug logging for connections
            if self.valves.DEBUG:
                await self._emit_debug_log(
                    f"[Tools] Found {len(connections)} server connections (Type: {type(raw_connections)})",
                    __event_call__,
                )

            for idx, server in enumerate(connections):
                # Handle server item type
                s_type = (
                    server.get("type", "openapi")
                    if isinstance(server, dict)
                    else getattr(server, "type", "openapi")
                )

                # P2: config.enable check — skip admin-disabled servers
                s_config = (
                    server.get("config", {})
                    if isinstance(server, dict)
                    else getattr(server, "config", {})
                )
                s_enabled = (
                    s_config.get("enable", False)
                    if isinstance(s_config, dict)
                    else getattr(s_config, "enable", False)
                )
                if not s_enabled:
                    if self.valves.DEBUG:
                        await self._emit_debug_log(
                            f"[Tools] Skipped disabled server at index {idx}",
                            __event_call__,
                        )
                    continue

                # Handle server ID: Priority info.id > server.id > index
                s_id = None
                if isinstance(server, dict):
                    info = server.get("info", {})
                    s_id = info.get("id") or server.get("id")
                else:
                    info = getattr(server, "info", {})
                    if isinstance(info, dict):
                        s_id = info.get("id")
                    else:
                        s_id = getattr(info, "id", None)

                    if not s_id:
                        s_id = getattr(server, "id", None)

                if not s_id:
                    s_id = str(idx)

                if self.valves.DEBUG:
                    await self._emit_debug_log(
                        f"[Tools] Checking Server: ID={s_id}, Type={s_type}",
                        __event_call__,
                    )

                if s_type == "openapi":
                    # Ensure we don't add empty IDs, though fallback to idx should prevent this
                    if s_id:
                        tool_ids.append(f"server:{s_id}")
                elif self.valves.DEBUG:
                    await self._emit_debug_log(
                        f"[Tools] Skipped non-OpenAPI server: {s_id} ({s_type})",
                        __event_call__,
                    )

        if (
            not tool_ids and not enable_tools
        ):  # No IDs and no built-ins either if tools disabled
            if self.valves.DEBUG:
                await self._emit_debug_log(
                    "[Tools] No tool IDs found and built-ins disabled.", __event_call__
                )
            return []

        # P4: Chat tool_ids whitelist — only active when user explicitly selected tools
        selected_custom_tool_ids = self._extract_selected_custom_tool_ids(chat_tool_ids)
        if selected_custom_tool_ids:
            chat_tool_ids_set = set(selected_custom_tool_ids)
            filtered = [tid for tid in tool_ids if tid in chat_tool_ids_set]
            await self._emit_debug_log(
                f"[Tools] custom tool_ids whitelist active: {len(tool_ids)} → {len(filtered)} (selected: {selected_custom_tool_ids})",
                __event_call__,
            )
            tool_ids = filtered

        if self.valves.DEBUG and tool_ids:
            await self._emit_debug_log(
                f"[Tools] Requesting tool IDs: {tool_ids}", __event_call__
            )

        # Extract token and messages from body first (before building request)
        token = None
        messages = []
        if isinstance(body, dict):
            token = body.get("token") or metadata_dict.get("token")
            messages = body.get("messages", [])

        # If token is still missing, try to extract from current __request__
        if not token and __request__ is not None:
            try:
                auth = getattr(__request__, "headers", {}).get("Authorization", "")
                if auth.startswith("Bearer "):
                    token = auth.split(" ", 1)[1]
            except Exception:
                pass

        # Sanitize request body to avoid passing Pydantic model objects
        # (e.g., ModelModel) into downstream request.json() consumers.
        request_body: Dict[str, Any] = body if isinstance(body, dict) else {}
        if isinstance(body, dict):
            request_body = dict(body)
            raw_body_meta = request_body.get("metadata")
            body_meta = dict(raw_body_meta) if isinstance(raw_body_meta, dict) else {}

            # Fill missing metadata keys from normalized injected metadata
            for key in (
                "model",
                "base_model_id",
                "model_id",
                "tool_ids",
                "files",
                "task",
                "task_body",
            ):
                if key in metadata_dict and key not in body_meta:
                    body_meta[key] = metadata_dict.get(key)

            body_model = body_meta.get("model")
            if body_model is not None and not isinstance(body_model, (dict, str)):
                normalized_body_model: Any = None

                if hasattr(body_model, "model_dump"):
                    try:
                        dumped_model = body_model.model_dump()
                        if isinstance(dumped_model, dict):
                            normalized_body_model = dumped_model
                    except Exception:
                        normalized_body_model = None

                if normalized_body_model is None:
                    normalized_body_model = (
                        getattr(body_model, "id", None)
                        or getattr(body_model, "base_model_id", None)
                        or getattr(body_model, "model", None)
                        or str(body_model)
                    )

                body_meta["model"] = normalized_body_model

            request_body["metadata"] = body_meta

        # Build request with context if available
        request = await self._build_openwebui_request(
            user_data, token=token, body=request_body
        )
        tool_request = __request__ if __request__ is not None else request

        # Pass OAuth/Auth details in extra_params
        chat_ctx = self._get_chat_context(body, __metadata__, __event_call__)
        extra_params = {
            "__request__": tool_request,
            "request": tool_request,  # Many tools expect 'request' without __
            "__user__": user_data,
            "__event_emitter__": __event_emitter__,
            "__event_call__": __event_call__,
            "__messages__": __messages__ if __messages__ is not None else messages,
            "__metadata__": metadata_dict,
            "__chat_id__": __chat_id__ or chat_ctx.get("chat_id"),
            "__message_id__": __message_id__ or chat_ctx.get("message_id"),
            "__session_id__": __session_id__ or chat_ctx.get("session_id"),
            "__files__": __files__ or metadata_dict.get("files", []),
            "__task__": __task__ or metadata_dict.get("task"),
            "__task_body__": __task_body__ or metadata_dict.get("task_body"),
            "__model_knowledge__": (body or {})
            .get("metadata", {})
            .get("knowledge", []),
            "body": request_body,  # many tools take 'body' in signature
            "__oauth_token__": ({"access_token": token} if token else None),
        }

        # Try to inject __model__ and update __metadata__['model'] if available
        model_id = (body or {}).get("model")
        if model_id:
            try:
                from open_webui.models.models import Models as _Models

                model_record = await _call_openwebui_compat(
                    _Models.get_model_by_id,
                    model_id,
                    prefer_thread_for_sync=True,
                )
                resolved_base_id = None

                if model_record:
                    m_dump = model_record.model_dump()
                    extra_params["__model__"] = {"info": m_dump}
                    # Standard tools often look for __metadata__['model'] or base_model_id
                    resolved_base_id = (
                        getattr(model_record, "base_model_id", None) or model_id
                    )
                    # Strip pipe/manifold prefix so tools never get the pipe-prefixed ID
                    # (e.g. "github_copilot_official_sdk_pipe.gemini-3-flash-preview" → "gemini-3-flash-preview")
                    resolved_base_id = self._strip_model_prefix(resolved_base_id)
                    if "__metadata__" in extra_params:
                        # Patch m_dump so that tools reading metadata["model"]["id"] also get the clean ID
                        if isinstance(m_dump, dict) and resolved_base_id:
                            m_dump = dict(m_dump)
                            m_dump["id"] = resolved_base_id
                        extra_params["__metadata__"]["model"] = m_dump
                else:
                    # Pipe-generated virtual model (not in DB) — strip the pipe prefix
                    resolved_base_id = self._strip_model_prefix(model_id)

                if resolved_base_id and "__metadata__" in extra_params:
                    # Always write the clean ID into base_model_id
                    extra_params["__metadata__"]["base_model_id"] = resolved_base_id
                    existing_model = extra_params["__metadata__"].get("model")
                    if isinstance(existing_model, dict):
                        # Patch the existing dict in-place (create a new dict to avoid mutating shared state)
                        patched = dict(existing_model)
                        patched["id"] = resolved_base_id
                        # Also clear any nested "model" key that some tools use as a second lookup
                        if "model" in patched and isinstance(patched["model"], str):
                            patched["model"] = resolved_base_id
                        extra_params["__metadata__"]["model"] = patched
                    else:
                        # Not a dict yet — replace with clean string ID
                        extra_params["__metadata__"]["model"] = resolved_base_id
            except Exception:
                pass

        # Log the final extra_params state AFTER all patches are applied
        if self.valves.DEBUG:
            try:
                tool_messages = extra_params.get("__messages__") or []
                tool_msg_samples = []
                for msg in tool_messages[-3:]:
                    if isinstance(msg, dict):
                        role = msg.get("role", "")
                        text = self._extract_text_from_content(msg.get("content", ""))
                    else:
                        role = ""
                        text = str(msg)
                    tool_msg_samples.append(
                        {"role": role, "len": len(text), "preview": text[:100]}
                    )

                meta_for_tool = extra_params.get("__metadata__", {})
                meta_model = (
                    meta_for_tool.get("model")
                    if isinstance(meta_for_tool, dict)
                    else None
                )
                if isinstance(meta_model, dict):
                    meta_model_repr = {
                        "id": meta_model.get("id"),
                        "base_model_id": meta_model.get("base_model_id"),
                        "model": meta_model.get("model"),
                    }
                else:
                    meta_model_repr = meta_model

                await self._emit_debug_log(
                    f"[Tools Input] extra_params (after patch): "
                    f"chat_id={extra_params.get('__chat_id__')}, "
                    f"message_id={extra_params.get('__message_id__')}, "
                    f"session_id={extra_params.get('__session_id__')}, "
                    f"messages_count={len(tool_messages)}, last3={tool_msg_samples}, "
                    f"metadata.model={meta_model_repr}, "
                    f"metadata.base_model_id={(meta_for_tool.get('base_model_id') if isinstance(meta_for_tool, dict) else None)}",
                    __event_call__,
                )
            except Exception as e:
                await self._emit_debug_log(
                    f"[Tools Input] extra_params diagnostics failed: {e}",
                    __event_call__,
                )

        # Fetch User/Server Tools (OpenWebUI Native)
        tools_dict = {}
        if tool_ids:
            tool_load_diag = {
                "metadata_type": (
                    type(__metadata__).__name__
                    if __metadata__ is not None
                    else "NoneType"
                ),
                "metadata_model_type": (
                    type(metadata_dict.get("model")).__name__
                    if metadata_dict
                    else "NoneType"
                ),
                "body_metadata_type": (
                    type(request_body.get("metadata")).__name__
                    if isinstance(request_body, dict)
                    else "NoneType"
                ),
                "body_metadata_model_type": (
                    type((request_body.get("metadata", {}) or {}).get("model")).__name__
                    if isinstance(request_body, dict)
                    else "NoneType"
                ),
                "tool_ids_count": len(tool_ids),
            }
            try:
                if self.valves.DEBUG:
                    await self._emit_debug_log(
                        f"[Tools] Calling get_openwebui_tools with IDs: {tool_ids}",
                        __event_call__,
                    )

                import time

                t_get_opw_start = time.perf_counter()
                tools_dict = await _call_openwebui_compat(
                    get_openwebui_tools,
                    tool_request,  # type: ignore[arg-type]
                    tool_ids,
                    user,
                    extra_params,
                    prefer_thread_for_sync=True,
                )
                t_get_opw_done = time.perf_counter()
                logger.info(
                    f"[Perf] get_openwebui_tools ({len(tool_ids)} IDs): {(t_get_opw_done - t_get_opw_start) * 1000:.2f}ms"
                )

                if self.valves.DEBUG:
                    if tools_dict:
                        tool_list = []
                        for k, v in tools_dict.items():
                            desc = v.get("description", "No description")[:50]
                            tool_list.append(f"{k} ({desc}...)")
                        await self._emit_debug_log(
                            f"[Tools] Successfully loaded {len(tools_dict)} tools: {tool_list}",
                            __event_call__,
                        )
                    else:
                        await self._emit_debug_log(
                            f"[Tools] get_openwebui_tools returned EMPTY dictionary.",
                            __event_call__,
                        )

            except Exception as e:
                await self._emit_debug_log(
                    f"[Tools] CRITICAL ERROR in get_openwebui_tools: {e}",
                    __event_call__,
                )
                if __event_call__:
                    try:
                        js_code = f"""
                            (async function() {{
                                console.group("❌ Copilot Pipe Tool Load Error");
                                console.error({json.dumps(str(e), ensure_ascii=False)});
                                console.log({json.dumps(tool_load_diag, ensure_ascii=False)});
                                console.groupEnd();
                            }})();
                        """
                        await __event_call__(
                            {"type": "execute", "data": {"code": js_code}}
                        )
                    except Exception:
                        pass
                import traceback

                traceback.print_exc()
                await self._emit_debug_log(
                    f"Error fetching user/server tools: {e}", __event_call__
                )

        # Fetch Built-in Tools (Web Search, Memory, etc.)
        if enable_tools:
            try:
                # Resolve real model dict from DB to respect meta.builtinTools config
                model_dict = {}
                model_id = body.get("model", "") if isinstance(body, dict) else ""
                if model_id:
                    try:
                        from open_webui.models.models import Models as _Models

                        model_record = await _call_openwebui_compat(
                            _Models.get_model_by_id,
                            model_id,
                            prefer_thread_for_sync=True,
                        )
                        if model_record:
                            model_dict = {"info": model_record.model_dump()}
                    except Exception:
                        pass

                # Force web_search enabled when OpenWebUI tools are enabled,
                # regardless of request feature flags, model meta defaults, or UI toggles.
                model_info = (
                    model_dict.get("info") if isinstance(model_dict, dict) else None
                )
                if isinstance(model_info, dict):
                    model_meta = model_info.get("meta")
                    if not isinstance(model_meta, dict):
                        model_meta = {}
                        model_info["meta"] = model_meta
                    builtin_meta = model_meta.get("builtinTools")
                    if not isinstance(builtin_meta, dict):
                        builtin_meta = {}
                    builtin_meta["web_search"] = True
                    model_meta["builtinTools"] = builtin_meta

                # Force feature selection to True for web_search to bypass UI session toggles
                if isinstance(body, dict):
                    features = body.get("features")
                    if not isinstance(features, dict):
                        features = {}
                        body["features"] = features
                    features["web_search"] = True

                # Get builtin tools
                # Code interpreter is STRICT opt-in: only enabled when request
                # explicitly sets feature code_interpreter=true. Missing means disabled.
                code_interpreter_enabled = self._is_code_interpreter_feature_enabled(
                    body, __metadata__
                )
                all_features = {
                    "memory": True,
                    "web_search": True,
                    "image_generation": True,
                    "code_interpreter": code_interpreter_enabled,
                }
                builtin_tools = await _call_openwebui_compat(
                    get_builtin_tools,
                    tool_request,  # type: ignore[arg-type]
                    extra_params,
                    features=all_features,
                    model=model_dict,  # model.meta.builtinTools controls which categories are active
                    prefer_thread_for_sync=True,
                )
                if builtin_tools:
                    tools_dict.update(builtin_tools)
            except Exception as e:
                await self._emit_debug_log(
                    f"Error fetching built-in tools: {e}", __event_call__
                )

        if not tools_dict:
            return []

        # Enrich tools with metadata from their source
        # 1. User-defined tools: name, description from docstring
        # 2. OpenAPI Tool Server tools: name, description from server config info
        tool_metadata_cache = {}
        server_metadata_cache = {}

        # Pre-build server metadata cache from DB-fresh tool server connections
        for server in await self._read_tool_server_connections():
            server_id = server.get("id") or server.get("info", {}).get("id")
            if server_id:
                info = server.get("info", {})
                server_metadata_cache[server_id] = {
                    "name": info.get("name") or server_id,
                    "description": info.get("description", ""),
                }

        for tool_name, tool_def in tools_dict.items():
            tool_id = tool_def.get("tool_id", "")
            tool_type = tool_def.get("type", "")

            if tool_type == "builtin":
                # Built-in tools don't need additional metadata
                continue
            elif tool_type == "external" or tool_id.startswith("server:"):
                # OpenAPI Tool Server - extract server ID and get metadata
                server_id = (
                    tool_id.replace("server:", "").split("|")[0]
                    if tool_id.startswith("server:")
                    else ""
                )
                if server_id and server_id in server_metadata_cache:
                    tool_def["_tool_group_name"] = server_metadata_cache[server_id].get(
                        "name"
                    )
                    tool_def["_tool_group_description"] = server_metadata_cache[
                        server_id
                    ].get("description")
            else:
                # User-defined Python script tool
                if tool_id and tool_id not in tool_metadata_cache:
                    try:
                        tool_model = await _call_openwebui_compat(
                            Tools.get_tool_by_id,
                            tool_id,
                            prefer_thread_for_sync=True,
                        )
                        if tool_model:
                            tool_metadata_cache[tool_id] = {
                                "name": tool_model.name,
                                "description": (
                                    tool_model.meta.description
                                    if tool_model.meta
                                    else None
                                ),
                            }
                    except Exception:
                        pass

                if tool_id in tool_metadata_cache:
                    tool_def["_tool_group_name"] = tool_metadata_cache[tool_id].get(
                        "name"
                    )
                    tool_def["_tool_group_description"] = tool_metadata_cache[
                        tool_id
                    ].get("description")

        converted_tools = []
        for tool_name, t_dict in tools_dict.items():
            if isinstance(tool_name, str) and tool_name.startswith("_"):
                if self.valves.DEBUG:
                    await self._emit_debug_log(
                        f"[Tools] Skip private tool: {tool_name}",
                        __event_call__,
                    )
                continue
            tool_type = t_dict.get("type", "")
            tool_id = t_dict.get("tool_id", "")
            if tool_type == "terminal" or str(tool_id).startswith("terminal:"):
                continue
            try:
                copilot_tool = self._convert_openwebui_tool_to_sdk(
                    tool_name,
                    t_dict,
                    __event_emitter__=__event_emitter__,
                    __event_call__=__event_call__,
                    user_lang=user_lang,
                )
                converted_tools.append(copilot_tool)
            except Exception as e:
                await self._emit_debug_log(
                    f"Failed to load OpenWebUI tool '{tool_name}': {e}",
                    __event_call__,
                )

        return converted_tools

    async def _parse_mcp_servers(
        self,
        __event_call__=None,
        enable_mcp: bool = True,
        chat_tool_ids: Optional[list] = None,
    ) -> Optional[dict]:
        """
        Dynamically load MCP servers from OpenWebUI TOOL_SERVER_CONNECTIONS.
        Returns a dict of mcp_servers compatible with CopilotClient.
        """
        if not enable_mcp:
            return None

        mcp_servers = {}
        selected_custom_tool_ids = self._extract_selected_custom_tool_ids(chat_tool_ids)

        # Read MCP servers directly from DB to avoid stale in-memory cache
        connections = await self._read_tool_server_connections()

        if __event_call__:
            mcp_summary = []
            for s in connections if isinstance(connections, list) else []:
                if isinstance(s, dict) and s.get("type") == "mcp":
                    s_id = s.get("info", {}).get("id") or s.get("id", "?")
                    s_enabled = s.get("config", {}).get("enable", False)
                    mcp_summary.append({"id": s_id, "enable": s_enabled})
            self._emit_debug_log_sync(
                f"[MCP] TOOL_SERVER_CONNECTIONS MCP entries ({len(mcp_summary)}): {mcp_summary}",
                __event_call__,
            )

        for conn in connections:
            if conn.get("type") == "mcp":
                info = conn.get("info", {})
                # Use ID from info or generate one
                raw_id = info.get("id", f"mcp-server-{len(mcp_servers)}")

                # P2: config.enable check — skip admin-disabled servers
                mcp_config = conn.get("config", {})
                if not mcp_config.get("enable", False):
                    self._emit_debug_log_sync(
                        f"[MCP] Skipped disabled server: {raw_id}", __event_call__
                    )
                    continue

                # P4: chat tool whitelist for MCP servers
                # OpenWebUI MCP tool IDs use "server:mcp:{id}" (not just "server:{id}").
                # Only enforce MCP server filtering when MCP server IDs are explicitly selected.
                selected_mcp_server_ids = {
                    tid[len("server:mcp:") :]
                    for tid in selected_custom_tool_ids
                    if isinstance(tid, str) and tid.startswith("server:mcp:")
                }
                if selected_mcp_server_ids and raw_id not in selected_mcp_server_ids:
                    continue

                # Sanitize server_id (using same logic as tools)
                server_id = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id)
                if not server_id or re.match(r"^[_.-]+$", server_id):
                    hash_suffix = hashlib.md5(raw_id.encode("utf-8")).hexdigest()[:8]
                    server_id = f"server_{hash_suffix}"

                url = conn.get("url")
                if not url:
                    continue

                # Build Headers (Handle Auth)
                headers = {}
                auth_type = str(conn.get("auth_type", "bearer")).lower()
                key = conn.get("key", "")

                if auth_type == "bearer" and key:
                    headers["Authorization"] = f"Bearer {key}"
                elif auth_type == "basic" and key:
                    # Fix: Basic auth requires base64 encoding
                    headers["Authorization"] = (
                        f"Basic {base64.b64encode(key.encode()).decode()}"
                    )
                elif auth_type in ["api_key", "apikey"]:
                    headers["X-API-Key"] = key

                # Merge custom headers if any
                custom_headers = conn.get("headers", {})
                if isinstance(custom_headers, dict):
                    headers.update(custom_headers)

                # Get filtering configuration
                function_filter = mcp_config.get("function_name_filter_list", "")

                allowed_tools = ["*"]
                parsed_filter = self._parse_mcp_function_filter(function_filter)
                expanded_filter = self._expand_mcp_filter_aliases(
                    parsed_filter,
                    raw_server_id=raw_id,
                    sanitized_server_id=server_id,
                )
                self._emit_debug_log_sync(
                    f"[MCP] function_name_filter_list raw={function_filter!r} parsed={parsed_filter} expanded={expanded_filter}",
                    __event_call__,
                )
                if expanded_filter:
                    allowed_tools = expanded_filter

                mcp_servers[server_id] = {
                    "type": "http",
                    "url": url,
                    "headers": headers,
                    "tools": allowed_tools,
                }
                self._emit_debug_log_sync(
                    f"🔌 MCP Integrated: {server_id}", __event_call__
                )

        return mcp_servers if mcp_servers else None

    async def _emit_debug_log(
        self, message: str, __event_call__=None, debug_enabled: Optional[bool] = None
    ):
        """Emit debug log to frontend (console) when DEBUG is enabled."""
        should_log = (
            debug_enabled
            if debug_enabled is not None
            else getattr(self.valves, "DEBUG", False)
        )
        if not should_log:
            return

        logger.debug(f"[Copilot Pipe] {message}")

        if not __event_call__:
            return

        try:
            js_code = f"""
                (async function() {{
                    console.debug("%c[Copilot Pipe] " + {json.dumps(message, ensure_ascii=False)}, "color: #3b82f6;");
                }})();
            """
            await __event_call__({"type": "execute", "data": {"code": js_code}})
        except Exception as e:
            logger.debug(f"[Copilot Pipe] Frontend debug log failed: {e}")

    def _emit_debug_log_sync(
        self, message: str, __event_call__=None, debug_enabled: Optional[bool] = None
    ):
        """Sync wrapper for debug logging."""
        should_log = (
            debug_enabled
            if debug_enabled is not None
            else getattr(self.valves, "DEBUG", False)
        )
        if not should_log:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._emit_debug_log(message, __event_call__, debug_enabled=True)
            )
        except RuntimeError:
            logger.debug(f"[Copilot Pipe] {message}")

    def _extract_text_from_content(self, content) -> str:
        """Extract text content from various message content formats."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return " ".join(text_parts)
        return ""

    def _apply_formatting_hint(self, prompt: str) -> str:
        """Return the prompt as-is (formatting hints removed)."""
        return prompt

    def _dedupe_preserve_order(self, items: List[str]) -> List[str]:
        """Deduplicate while preserving order."""
        seen = set()
        result = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def _strip_model_prefix(self, model_id: str) -> str:
        """Sequential prefix stripping: OpenWebUI plugin ID then internal pipe prefix."""
        if not model_id:
            return ""

        res = model_id
        # 1. Strip OpenWebUI plugin prefix (e.g. 'github_copilot_sdk.copilot-gpt-4o' -> 'copilot-gpt-4o')
        if "." in res:
            res = res.split(".", 1)[-1]

        # 2. Strip our own internal prefix (e.g. 'copilot-gpt-4o' -> 'gpt-4o')
        internal_prefix = f"{self.id}-"
        if res.startswith(internal_prefix):
            res = res[len(internal_prefix) :]

        # 3. Handle legacy/variant dash-based prefix
        if res.startswith("copilot - "):
            res = res[10:]

        return res

    def _collect_model_ids(
        self, body: dict, request_model: str, real_model_id: str
    ) -> List[str]:
        """Collect possible model IDs from request/metadata/body params."""
        model_ids: List[str] = []
        if request_model:
            model_ids.append(request_model)
            stripped = self._strip_model_prefix(request_model)
            if stripped != request_model:
                model_ids.append(stripped)
        if real_model_id:
            model_ids.append(real_model_id)

        metadata = body.get("metadata", {})
        if isinstance(metadata, dict):
            meta_model = metadata.get("model")
            meta_model_id = metadata.get("model_id")
            if isinstance(meta_model, str):
                model_ids.append(meta_model)
            if isinstance(meta_model_id, str):
                model_ids.append(meta_model_id)

        body_params = body.get("params", {})
        if isinstance(body_params, dict):
            for key in ("model", "model_id", "modelId"):
                val = body_params.get(key)
                if isinstance(val, str):
                    model_ids.append(val)

        return self._dedupe_preserve_order(model_ids)

    def _parse_csv_items(self, value: Optional[str]) -> List[str]:
        if not value or not isinstance(value, str):
            return []
        items = [item.strip() for item in value.split(",")]
        return self._dedupe_preserve_order([item for item in items if item])

    def _normalize_chat_tool_ids(self, raw_tool_ids: Any) -> List[str]:
        """Normalize chat tool_ids payload to a clean list[str]."""
        if not raw_tool_ids:
            return []

        normalized: List[str] = []

        if isinstance(raw_tool_ids, str):
            text = raw_tool_ids.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    return self._normalize_chat_tool_ids(parsed)
                except Exception:
                    pass
            normalized = [p.strip() for p in re.split(r"[,\n;]+", text) if p.strip()]
            return self._dedupe_preserve_order(normalized)

        if isinstance(raw_tool_ids, (list, tuple, set)):
            for item in raw_tool_ids:
                if isinstance(item, str):
                    value = item.strip()
                    if value:
                        normalized.append(value)
                    continue

                if isinstance(item, dict):
                    for key in ("id", "tool_id", "value", "name"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            normalized.append(value.strip())
                            break

        return self._dedupe_preserve_order(normalized)

    def _extract_selected_custom_tool_ids(self, chat_tool_ids: Any) -> List[str]:
        """Return selected non-builtin tool IDs only."""
        normalized = self._normalize_chat_tool_ids(chat_tool_ids)
        return self._dedupe_preserve_order(
            [
                tid
                for tid in normalized
                if isinstance(tid, str) and not tid.startswith("builtin:")
            ]
        )

    def _parse_mcp_function_filter(self, raw_filter: Any) -> List[str]:
        """Parse MCP function filter list from string/list/json into normalized names."""
        if not raw_filter:
            return []

        if isinstance(raw_filter, (list, tuple, set)):
            return self._dedupe_preserve_order(
                [
                    str(item).strip().strip('"').strip("'")
                    for item in raw_filter
                    if str(item).strip().strip('"').strip("'")
                ]
            )

        if isinstance(raw_filter, str):
            text = raw_filter.strip()
            if not text:
                return []

            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    return self._parse_mcp_function_filter(parsed)
                except Exception:
                    pass

            parts = re.split(r"[,\n;，、]+", text)
            cleaned: List[str] = []
            for part in parts:
                value = part.strip().strip('"').strip("'")
                if value.startswith("- "):
                    value = value[2:].strip()
                if value:
                    cleaned.append(value)
            return self._dedupe_preserve_order(cleaned)

        return []

    def _expand_mcp_filter_aliases(
        self,
        tool_names: List[str],
        raw_server_id: str,
        sanitized_server_id: str,
    ) -> List[str]:
        """Expand MCP filter names with common server-prefixed aliases.

        Some MCP providers expose namespaced tool names such as:
        - github__get_me
        - github/get_me
        - github.get_me
        while admins often configure bare names like `get_me`.
        """
        if not tool_names:
            return []

        prefixes = self._dedupe_preserve_order(
            [
                str(raw_server_id or "").strip(),
                str(sanitized_server_id or "").strip(),
            ]
        )

        variants: List[str] = []
        for name in tool_names:
            clean_name = str(name).strip()
            if not clean_name:
                continue

            # Keep original configured name first.
            variants.append(clean_name)

            # If admin already provided a namespaced value, keep it as-is only.
            if any(sep in clean_name for sep in ("__", "/", ".")):
                continue

            for prefix in prefixes:
                if not prefix:
                    continue
                variants.extend(
                    [
                        f"{prefix}__{clean_name}",
                        f"{prefix}/{clean_name}",
                        f"{prefix}.{clean_name}",
                    ]
                )

        return self._dedupe_preserve_order(variants)

    def _is_manage_skills_intent(self, text: str) -> bool:
        """Detect whether the user is asking to manage/install skills.

        When true, route to the deterministic `manage_skills` tool workflow.
        """
        if not text or not isinstance(text, str):
            return False

        t = text.lower()

        patterns = [
            r"\bskills?-manager\b",
            r"\binstall\b.*\bskills?\b",
            r"\binstall\b.*github\.com/.*/skills",
            r"\bmanage\b.*\bskills?\b",
            r"\blist\b.*\bskills?\b",
            r"\bdelete\b.*\bskills?\b",
            r"\bremove\b.*\bskills?\b",
            r"\bedit\b.*\bskills?\b",
            r"\bupdate\b.*\bskills?\b",
            r"安装.*技能",
            r"安装.*skills?",
            r"管理.*技能",
            r"管理.*skills?",
            r"列出.*技能",
            r"删除.*技能",
            r"编辑.*技能",
            r"更新.*技能",
            r"skills码",
            r"skill\s*code",
        ]

        for p in patterns:
            if re.search(p, t):
                return True
        return False

    def _collect_skill_names_for_routing(
        self,
        resolved_cwd: str,
        user_id: str,
        enable_openwebui_skills: bool,
    ) -> List[str]:
        """Collect current skill names from shared directory."""
        skill_names: List[str] = []

        def _scan_skill_dir(parent_dir: str):
            parent = Path(parent_dir)
            if not parent.exists() or not parent.is_dir():
                return
            for skill_dir in parent.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    parsed_name, _, _ = self._parse_skill_md_meta(
                        content, skill_dir.name
                    )
                    skill_names.append(parsed_name or skill_dir.name)
                except Exception:
                    skill_names.append(skill_dir.name)

        if enable_openwebui_skills:
            shared_dir = self._sync_openwebui_skills(resolved_cwd, user_id)
        else:
            shared_dir = self._get_shared_skills_dir(resolved_cwd)
        _scan_skill_dir(shared_dir)

        return self._dedupe_preserve_order(skill_names)

    def _skill_dir_name_from_skill_name(self, skill_name: str) -> str:
        name = (skill_name or "owui-skill").strip()
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]+', "_", name)
        name = name.strip().strip(".")
        if not name:
            name = "owui-skill"
        return name[:128]

    def _get_copilot_config_dir(self) -> str:
        """Get the effective directory for Copilot SDK config/metadata."""
        # 1. Valve override
        if getattr(self.valves, "COPILOTSDK_CONFIG_DIR", ""):
            return os.path.expanduser(self.valves.COPILOTSDK_CONFIG_DIR)

        # 2. Container persistence (Shared data volume)
        if os.path.exists("/app/backend/data"):
            path = "/app/backend/data/.copilot"
            try:
                os.makedirs(path, exist_ok=True)
                return path
            except Exception as e:
                logger.warning(f"Failed to create .copilot dir in data volume: {e}")

        # 3. Fallback to standard path
        return os.path.expanduser("~/.copilot")

    def _get_session_metadata_dir(self, chat_id: str) -> str:
        """Get the directory where a specific chat's session state is stored."""
        config_dir = self._get_copilot_config_dir()
        path = os.path.join(config_dir, "session-state", chat_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _initialize_interactive_controls_table(self, chat_id: str) -> None:
        """Initialize the interactive_controls table in session.db if not exists."""
        if not chat_id:
            return
        try:
            metadata_dir = self._get_session_metadata_dir(chat_id)
            db_path = os.path.join(metadata_dir, "session.db")
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interactive_controls (
                        id TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        action TEXT NOT NULL,
                        status TEXT DEFAULT 'visible',
                        likelihood REAL DEFAULT 0.5,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
        except Exception as e:
            logger.warning(
                f"Failed to initialize interactive_controls table for {chat_id}: {e}"
            )

    def _get_plan_file_path(self, chat_id: Optional[str]) -> Optional[str]:
        """Return the canonical plan.md path for the current chat session."""
        if not chat_id:
            return None
        return os.path.join(self._get_session_metadata_dir(chat_id), "plan.md")

    def _persist_plan_text(
        self, chat_id: Optional[str], content: Optional[str]
    ) -> None:
        """Persist plan text into the chat-specific session metadata directory."""
        plan_path = self._get_plan_file_path(chat_id)
        if not plan_path or not isinstance(content, str):
            return

        try:
            Path(plan_path).write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to persist plan.md for chat '{chat_id}': {e}")

    def _build_adaptive_workstyle_context(
        self, plan_path: str, session_mode: str = "autopilot"
    ) -> str:
        """Return task-adaptive planning and execution guidance, tuned to the active session mode."""
        # Mode-specific preamble: align the agent's self-described working style with the
        # active SDK mode so the Adaptive Workstyle section never contradicts [Active Session Mode].
        if session_mode == "interactive":
            mode_preamble = (
                "You are in step-by-step interactive mode. After completing each action present the result clearly, then STOP and wait for the user's next instruction.\n"
                "Do not chain independent steps without user acknowledgement — let the user drive the pace."
            )
        elif session_mode == "plan":
            mode_preamble = (
                "You are in plan-first mode. Research the problem thoroughly, surface assumptions and constraints, then present a structured plan BEFORE touching any code or files.\n"
                "Do not execute implementation steps until the user explicitly approves the plan."
            )
        else:  # autopilot (default)
            mode_preamble = (
                "You are in autonomous autopilot mode. Drive every task to full completion end-to-end without stopping between steps.\n"
                "Call `task_complete` only when every open item is resolved — nothing pending, no errors unaddressed, all verification steps passed."
            )
        return (
            "\n[Adaptive Workstyle Context]\n"
            f"{mode_preamble}\n"
            f"**Plan File**: `{plan_path}`. This file lives in the **session metadata directory**, not in the isolated workspace. Update it when you create a concrete plan worth persisting across turns.\n\n"
            "<rules>\n"
            "- If the request is clear and low-risk, execute directly (autopilot) or present result and wait (interactive/plan).\n"
            "- If the request is ambiguous, high-risk, architectural, or explicitly asks for a plan, switch into planning-first behavior before implementation.\n"
            "- Use clarifying questions ONLY when research reveals ambiguity that materially affects the outcome and cannot be resolved by a reasonable default decision.\n"
            "- When you do create a plan, make it scannable, detailed, and executable by a later implementation turn or by yourself in a follow-up step.\n"
            "- `plan.md` is a session-state artifact in the metadata area, not a project file in the workspace. Do not place planning markdown inside the repository unless explicitly asked.\n"
            "</rules>\n\n"
            "<workflow>\n"
            "1. Assess: Decide whether this task is best handled by direct execution or planning-first analysis.\n"
            "2. Research: Inspect the codebase, analogous features, constraints, and blockers before committing to an approach when uncertainty exists.\n"
            "3. Act: Either draft a comprehensive plan or implement the change directly, depending on the assessment above.\n"
            "4. Re-evaluate: If new complexity appears mid-task, change strategy explicitly instead of forcing the original approach.\n"
            "</workflow>\n\n"
            "<key_principles>\n"
            "- Ground both plans and implementation in real codebase findings rather than assumptions.\n"
            "- If the user wants research or planning, present findings in a structured plan/report style before changing code.\n"
            "- The plan file is for persistence only; if you create or revise a plan, you must still show the plan to the user in the chat.\n"
            f"- PERSISTENCE: When you produce a concrete plan, save it to `{plan_path}` so the UI can keep the plan view synchronized.\n"
            "</key_principles>\n\n"
            "<plan_format>\n"
            "When presenting your findings or plan in the chat, structure it clearly:\n"
            "## Plan / Report: {Title}\n"
            "**TL;DR**: {What, why, and recommended approach}\n"
            "**Steps**: {Implementation steps with explicit dependencies or parallelism notes}\n"
            "**Relevant Files**: \n- `full/path/to/file` — {what to modify or reuse}\n"
            "**Verification**: {Specific validation steps, tests, commands, or manual checks}\n"
            "**Decisions**: {Key assumptions, included scope, and excluded scope when applicable}\n"
            "**Further Considerations**: {1-3 follow-up considerations or options when useful}\n"
            "</plan_format>\n"
            "Use the plan style above whenever you choose a planning-first response. Otherwise, execute decisively and summarize the completed work clearly."
        )

    def _find_session_todo_db(self, chat_id: str) -> Optional[str]:
        """Locate the per-session SQLite database that contains the todos table."""
        if not chat_id:
            return None

        session_dir = Path(self._get_session_metadata_dir(chat_id))
        candidates: List[Path] = []

        preferred = session_dir / "session.db"
        if preferred.exists():
            candidates.append(preferred)

        for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
            for candidate in sorted(session_dir.glob(pattern)):
                if candidate not in candidates:
                    candidates.append(candidate)

        for candidate in candidates:
            try:
                with sqlite3.connect(f"file:{candidate}?mode=ro", uri=True) as conn:
                    row = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
                    ).fetchone()
                    if row:
                        return str(candidate)
            except Exception:
                continue

        return None

    def _read_todo_status_from_session_db(
        self, chat_id: str
    ) -> Optional[Dict[str, Any]]:
        """Read live todo statistics from the session SQLite database."""
        db_path = self._find_session_todo_db(chat_id)
        if not db_path:
            return None

        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row

                rows = conn.execute(
                    "SELECT id, title, status FROM todos ORDER BY rowid"
                ).fetchall()
                if not rows:
                    return None

                counts = {
                    "pending": 0,
                    "in_progress": 0,
                    "done": 0,
                    "blocked": 0,
                }
                for row in rows:
                    status = str(row["status"] or "pending")
                    counts[status] = counts.get(status, 0) + 1

                ready_rows = conn.execute(
                    """
                    SELECT t.id
                    FROM todos t
                    WHERE t.status = 'pending'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM todo_deps td
                          JOIN todos dep ON td.depends_on = dep.id
                          WHERE td.todo_id = t.id
                            AND dep.status != 'done'
                      )
                    ORDER BY rowid
                    LIMIT 3
                    """
                ).fetchall()
                ready_count_row = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM todos t
                    WHERE t.status = 'pending'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM todo_deps td
                          JOIN todos dep ON td.depends_on = dep.id
                          WHERE td.todo_id = t.id
                            AND dep.status != 'done'
                      )
                    """
                ).fetchone()

                return {
                    "db_path": db_path,
                    "total": len(rows),
                    "pending": counts.get("pending", 0),
                    "in_progress": counts.get("in_progress", 0),
                    "done": counts.get("done", 0),
                    "blocked": counts.get("blocked", 0),
                    "ready_count": int(ready_count_row[0]) if ready_count_row else 0,
                    "ready_ids": [str(row["id"]) for row in ready_rows],
                    "items": [
                        {
                            "id": str(row["id"]),
                            "title": str(row["title"] or row["id"]),
                            "status": str(row["status"] or "pending"),
                        }
                        for row in rows
                    ],
                }
        except Exception as e:
            logger.debug(f"[Todo Status] Failed to read session DB '{db_path}': {e}")
            return None

    def _format_todo_widget_summary(self, lang: str, stats: Dict[str, Any]) -> str:
        """Format a compact TODO summary using widget-localized labels only."""
        widget_texts = self._get_todo_widget_texts(lang)
        total = int(stats.get("total", 0))
        pending = int(stats.get("pending", 0))
        in_progress = int(stats.get("in_progress", 0))
        done = int(stats.get("done", 0))
        blocked = int(stats.get("blocked", 0))

        parts = [
            f"{widget_texts['title']}: {widget_texts['total']} {total}",
            f"⏳ {widget_texts['pending']} {pending}",
            f"🚧 {widget_texts['doing']} {in_progress}",
            f"✅ {widget_texts['done']} {done}",
            f"⛔ {widget_texts['blocked']} {blocked}",
        ]
        return " | ".join(parts)

    def _get_todo_widget_state_path(self, chat_id: str) -> str:
        """Return the persisted hash path for the live TODO widget."""
        return os.path.join(self._get_session_metadata_dir(chat_id), "todo_widget.hash")

    def _compute_todo_widget_hash(self, stats: Optional[Dict[str, Any]]) -> str:
        """Create a stable hash of the TODO snapshot so only real changes trigger a refresh."""
        payload = {
            "total": int((stats or {}).get("total", 0)),
            "pending": int((stats or {}).get("pending", 0)),
            "in_progress": int((stats or {}).get("in_progress", 0)),
            "done": int((stats or {}).get("done", 0)),
            "blocked": int((stats or {}).get("blocked", 0)),
            "ready_count": int((stats or {}).get("ready_count", 0)),
            "ready_ids": list((stats or {}).get("ready_ids", []) or []),
            "items": list((stats or {}).get("items", []) or []),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _read_todo_widget_hash(self, chat_id: str) -> str:
        """Read the last emitted TODO widget hash for this chat."""
        if not chat_id:
            return ""
        state_path = self._get_todo_widget_state_path(chat_id)
        try:
            return Path(state_path).read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _write_todo_widget_hash(self, chat_id: str, snapshot_hash: str) -> None:
        """Persist the last emitted TODO widget hash for this chat."""
        if not chat_id:
            return
        state_path = Path(self._get_todo_widget_state_path(chat_id))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(snapshot_hash, encoding="utf-8")

    def _build_todo_widget_html(
        self, lang: str, stats: Optional[Dict[str, Any]]
    ) -> str:
        """Build a compact TODO widget: always-expanded flat list."""

        def esc(value: Any) -> str:
            return (
                str(value or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        stats = stats or {
            "total": 0,
            "pending": 0,
            "in_progress": 0,
            "done": 0,
            "blocked": 0,
            "ready_count": 0,
            "items": [],
        }
        widget_texts = self._get_todo_widget_texts(lang)
        pending = int(stats.get("pending", 0))
        in_progress = int(stats.get("in_progress", 0))
        done = int(stats.get("done", 0))
        blocked = int(stats.get("blocked", 0))
        ready_count = int(stats.get("ready_count", 0))
        items = list(stats.get("items", []) or [])

        S = {
            "pending": ("pend", "⏳"),
            "in_progress": ("prog", "🚧"),
            "done": ("done", "✅"),
            "blocked": ("blk", "⛔"),
        }

        # ── header pills ──
        pills = []
        if ready_count > 0:
            pills.append(
                f'<span class="pill ready">{esc(widget_texts["ready_now"].format(ready_count=ready_count))}</span>'
            )
        if in_progress > 0:
            pills.append(f'<span class="pill prog">🚧 {in_progress}</span>')
        if pending > 0:
            pills.append(f'<span class="pill pend">⏳ {pending}</span>')
        if blocked > 0:
            pills.append(f'<span class="pill blk">⛔ {blocked}</span>')
        if done > 0:
            pills.append(f'<span class="pill done">✅ {done}</span>')
        pills_html = "".join(pills)

        # ── flat list rows ──
        status_order = {"in_progress": 0, "blocked": 1, "pending": 2, "done": 3}
        sorted_items = sorted(
            items, key=lambda x: status_order.get(str(x.get("status") or "pending"), 2)
        )

        rows_html = ""
        for item in sorted_items[:24]:
            s = str(item.get("status") or "pending")
            cls, icon = S.get(s, ("pend", "⏳"))
            label = esc(widget_texts.get(f"status_{s}", s))
            title = esc(item.get("title") or item.get("id") or "todo")
            iid = esc(item.get("id") or "")
            description = esc(item.get("description") or "")
            id_part = f' <span class="rid">{iid}</span>' if iid else ""
            desc_part = (
                f'<span class="rdesc">{description}</span>' if description else ""
            )
            rows_html += (
                f'<div class="row {cls}">'
                f'<span class="ricon">{icon}</span>'
                f'<span class="rmain"><span class="rtitle">{title}{id_part}</span>{desc_part}</span>'
                f'<span class="chip {cls}">{label}</span>'
                f"</div>"
            )
        if not rows_html:
            rows_html = f'<div class="empty">{esc(widget_texts["empty"])}</div>'

        ts = datetime.now().strftime("%H:%M:%S")
        footer = esc(widget_texts["updated_at"].format(time=ts))
        title_text = esc(widget_texts["title"])
        ready_hint = esc(widget_texts["ready_now"].format(ready_count=ready_count))

        return f"""<!DOCTYPE html>
<html lang="{esc(self._resolve_language(lang))}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
  :root{{
    --bg:#ffffff;--bd:#e5e7eb;--tx:#111827;--mu:#9ca3af;--row-h:#f3f4f6;
    --done-c:#059669;--done-b:#ecfdf5;--done-bd:#a7f3d0;
    --prog-c:#2563eb;--prog-b:#eff6ff;--prog-bd:#bfdbfe;
    --pend-c:#b45309;--pend-b:#fffbeb;--pend-bd:#fde68a;
    --blk-c:#dc2626; --blk-b:#fef2f2;--blk-bd:#fecaca;
    --dot:#6366f1;
  }}
  html.dark,
  html[data-openwebui-applied-theme="dark"]{{
    --bg:#1e1e2e;--bd:#313244;--tx:#cdd6f4;--mu:#6c7086;--row-h:#232336;
    --done-c:#a6e3a1;--done-b:#1e3a2a;--done-bd:#2d5c3e;
    --prog-c:#89b4fa;--prog-b:#1a2a4a;--prog-bd:#2a4070;
    --pend-c:#f9e2af;--pend-b:#3a2e1a;--pend-bd:#5a4820;
    --blk-c:#f38ba8; --blk-b:#3a1a20;--blk-bd:#5a2830;
    --dot:#cba6f7;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  html,body{{width:100%;height:auto;min-height:0;overflow:hidden}}
  body{{background:transparent;font-family:"Inter","Segoe UI",system-ui,sans-serif;font-size:13px;color:var(--tx)}}
  .w{{background:var(--bg);border:1px solid var(--bd);border-radius:8px;overflow:hidden;display:block}}
  /* ── header ── */
  .hd{{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid var(--bd)}}
  .ttl{{font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;flex:0 0 auto}}
  .sep{{width:1px;height:14px;background:var(--bd);flex:0 0 auto}}
  .pills{{display:flex;gap:4px;flex-wrap:wrap}}
  .pill{{font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px;border:1px solid transparent;white-space:nowrap}}
  .pill.ready{{color:var(--prog-c);background:var(--prog-b);border-color:var(--prog-bd)}}
  .pill.done{{color:var(--done-c);background:var(--done-b);border-color:var(--done-bd)}}
  .pill.prog{{color:var(--prog-c);background:var(--prog-b);border-color:var(--prog-bd)}}
  .pill.pend{{color:var(--pend-c);background:var(--pend-b);border-color:var(--pend-bd)}}
  .pill.blk {{color:var(--blk-c); background:var(--blk-b); border-color:var(--blk-bd)}}
  .dot{{width:6px;height:6px;border-radius:50%;background:var(--dot);animation:blink 2s ease-in-out infinite;margin-left:auto;flex:0 0 auto}}
  @keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
  /* ── rows ── */
  .row{{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid var(--bd)}}
  .row:last-child{{border-bottom:none}}
  .row.done .rtitle{{color:var(--mu);text-decoration:line-through;text-decoration-color:var(--done-bd)}}
  .ricon{{font-size:13px;flex:0 0 auto;line-height:1}}
  .rmain{{display:flex;flex:1 1 0;min-width:0;flex-direction:column;gap:2px}}
  .rtitle{{min-width:0;font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .rdesc{{font-size:10px;color:var(--mu);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .rid{{font-size:10px;color:var(--mu);font-family:ui-monospace,monospace;margin-left:5px}}
  .chip{{font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;flex:0 0 auto;border:1px solid transparent;white-space:nowrap}}
  .chip.done{{color:var(--done-c);background:var(--done-b);border-color:var(--done-bd)}}
  .chip.prog{{color:var(--prog-c);background:var(--prog-b);border-color:var(--prog-bd)}}
  .chip.pend{{color:var(--pend-c);background:var(--pend-b);border-color:var(--pend-bd)}}
  .chip.blk {{color:var(--blk-c); background:var(--blk-b); border-color:var(--blk-bd)}}
  .empty{{padding:10px;font-size:12px;color:var(--mu)}}
  .foot{{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:5px 10px;font-size:10px;color:var(--mu);border-top:1px solid var(--bd)}}
  .foot .hint{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
</style>
</head>
<body>
<div class="w">
  <div class="hd">
    <span class="ttl">📋 {title_text}</span>
    <span class="sep"></span>
    <span class="pills">{pills_html}</span>
    <span class="dot"></span>
  </div>
  <div>
    {rows_html}
  </div>
  <div class="foot">
    <span class="hint">{ready_hint}</span>
    <span>{footer}</span>
  </div>
</div>
</body>
</html>
"""

    async def _emit_todo_widget(
        self,
        chat_id: str,
        lang: str,
        emitter,
        stats: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Emit the TODO widget immediately when the snapshot actually changed."""
        if not chat_id:
            return {"emitted": False, "changed": False, "reason": "missing_chat_id"}
        if not emitter:
            return {"emitted": False, "changed": False, "reason": "missing_emitter"}

        current_stats = (
            stats
            if stats is not None
            else self._read_todo_status_from_session_db(chat_id)
        )

        # If there are tasks but they are all done, do not emit the widget.
        # We also clear the previous hash so if a new task is added later, it will re-trigger.
        if current_stats:
            total_tasks = int(current_stats.get("total", 0))
            done_tasks = int(current_stats.get("done", 0))
            if total_tasks > 0 and done_tasks == total_tasks:
                self._write_todo_widget_hash(chat_id, "")  # Reset hash
                return {
                    "emitted": False,
                    "changed": False,
                    "reason": "all_tasks_done",
                }

        snapshot_hash = self._compute_todo_widget_hash(current_stats)
        previous_hash = self._read_todo_widget_hash(chat_id)
        changed = force or snapshot_hash != previous_hash
        if not changed:
            return {
                "emitted": False,
                "changed": False,
                "reason": "unchanged",
            }

        html_doc = self._prepare_richui_embed_html(
            self._build_todo_widget_html(lang, current_stats),
            user_lang=lang,
        )
        try:
            await emitter({"type": "embeds", "data": {"embeds": [html_doc]}})
            self._write_todo_widget_hash(chat_id, snapshot_hash)
            return {
                "emitted": True,
                "changed": True,
                "reason": "widget_updated",
            }
        except Exception as e:
            logger.debug(f"[Todo Widget] Failed to emit widget: {e}")
            return {"emitted": False, "changed": changed, "reason": str(e)}

    def _query_mentions_todo_tables(self, query: str) -> bool:
        """Return whether a SQL query is operating on todo tables."""
        if not query:
            return False
        return bool(re.search(r"\b(todos|todo_deps)\b", query, re.IGNORECASE))

    def _get_shared_skills_dir(self, resolved_cwd: str) -> str:
        """Returns (and creates) the unified shared skills directory.

        Both OpenWebUI page skills and pipe-installed skills live here.
        The directory is persistent and shared across all sessions.
        """
        shared_base = Path(self.valves.OPENWEBUI_SKILLS_SHARED_DIR or "").expanduser()
        if not shared_base.is_absolute():
            shared_base = Path(resolved_cwd) / shared_base
        shared_dir = shared_base / "shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        return str(shared_dir)

    def _normalize_skill_md_newlines(self, text: str) -> str:
        """Normalize CRLF/CR text to LF for stable SKILL.md parsing."""
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _strip_skill_meta_quotes(self, value: str) -> str:
        """Remove matching wrapping quotes from a frontmatter scalar."""
        value = (value or "").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value

    def _collect_skill_meta_block(
        self, lines: List[str], start_index: int
    ) -> Tuple[List[str], int]:
        """Collect indented frontmatter block lines until the next top-level key."""
        block_lines: List[str] = []
        index = start_index

        while index < len(lines):
            line = lines[index]
            if not line.strip():
                block_lines.append("")
                index += 1
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent == 0 and re.match(r"^[A-Za-z0-9_-]+:(.*)$", line):
                break
            if indent == 0:
                break

            block_lines.append(line)
            index += 1

        non_empty_indents = [
            len(line) - len(line.lstrip(" ")) for line in block_lines if line.strip()
        ]
        min_indent = min(non_empty_indents) if non_empty_indents else 0
        dedented = [line[min_indent:] if line else "" for line in block_lines]
        return dedented, index

    def _fold_skill_meta_block(self, lines: List[str]) -> str:
        """Fold YAML `>` block lines into paragraphs separated by blank lines."""
        parts: List[str] = []
        paragraph: List[str] = []

        for line in lines:
            if line == "":
                if paragraph:
                    parts.append(" ".join(segment.strip() for segment in paragraph))
                    paragraph = []
                if parts and parts[-1] != "":
                    parts.append("")
                continue
            paragraph.append(line.strip())

        if paragraph:
            parts.append(" ".join(segment.strip() for segment in paragraph))

        return "\n".join(parts).strip()

    def _parse_skill_frontmatter_scalars(self, frontmatter_text: str) -> Dict[str, str]:
        """Parse simple top-level YAML frontmatter scalars, including block scalars."""
        lines = self._normalize_skill_md_newlines(frontmatter_text).split("\n")
        metadata: Dict[str, str] = {}
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or line.startswith(" "):
                index += 1
                continue

            match = re.match(r"^([A-Za-z0-9_-]+):(.*)$", line)
            if not match:
                index += 1
                continue

            key = match.group(1)
            raw_value = match.group(2).lstrip()

            if raw_value[:1] in {"|", ">"}:
                block_lines, index = self._collect_skill_meta_block(lines, index + 1)
                metadata[key] = (
                    "\n".join(block_lines).strip()
                    if raw_value.startswith("|")
                    else self._fold_skill_meta_block(block_lines)
                )
                continue

            block_lines, next_index = self._collect_skill_meta_block(lines, index + 1)
            if block_lines:
                segments = [self._strip_skill_meta_quotes(raw_value)] + [
                    segment.strip() for segment in block_lines
                ]
                metadata[key] = self._fold_skill_meta_block(segments)
                index = next_index
                continue

            metadata[key] = self._strip_skill_meta_quotes(raw_value)
            index += 1

        return metadata

    def _parse_skill_md_meta(self, content: str, fallback_name: str) -> tuple:
        """Parse SKILL.md content into (name, description, body).

        Handles files with or without YAML frontmatter.
        Strips quotes from frontmatter string values.
        """
        normalized_content = self._normalize_skill_md_newlines(content)
        fm_match = re.match(
            r"^---\s*\n(.*?)\n---\s*(?:\n|$)", normalized_content, re.DOTALL
        )
        if fm_match:
            fm_text = fm_match.group(1)
            body = normalized_content[fm_match.end() :].strip()
            metadata = self._parse_skill_frontmatter_scalars(fm_text)
            name = (
                metadata.get("name") or metadata.get("title") or fallback_name
            ).strip()
            description = (metadata.get("description") or "").strip()
            return name, description, body
        # No frontmatter: try to extract H1 as name
        stripped_content = normalized_content.strip()
        h1_match = re.search(r"^#\s+(.+)$", stripped_content, re.MULTILINE)
        name = h1_match.group(1).strip() if h1_match else fallback_name
        return name, "", stripped_content

    def _build_skill_md_content(self, name: str, description: str, body: str) -> str:
        """Construct a SKILL.md file string from name, description, and body."""
        desc_value = (description or name).strip()
        if "\n" in desc_value:
            desc_body = "\n".join(
                f"  {line}" if line else "" for line in desc_value.split("\n")
            )
            desc_line = f"|\n{desc_body}"
        else:
            desc_line = desc_value
            if any(c in desc_line for c in ":#"):
                desc_line = f'"{desc_line}"'
        return (
            f"---\nname: {name}\ndescription: {desc_line}\n---\n\n# {name}\n\n{body}\n"
        )

    def _sync_openwebui_skills(self, resolved_cwd: str, user_id: str) -> str:
        """Bidirectionally sync skills between OpenWebUI DB and the shared/ directory.

        Sync rules (per skill):
          DB → File: if a skill exists in OpenWebUI but has no directory entry, or the
                     DB is newer than the file → write/update SKILL.md in shared/.
          File → DB: if a skill directory has no .owui_id or the file is newer than the
                     DB entry → create/update the skill in OpenWebUI DB.

        Change detection uses MD5 content hash (skip if identical) then falls back to
        timestamp comparison (db.updated_at vs file mtime) to determine direction.

        A `.owui_id` marker file inside each skill directory tracks the OpenWebUI skill ID.
        Skills installed via pipe that have no OpenWebUI counterpart are registered in DB.
        If a directory has `.owui_id` but the corresponding OpenWebUI skill is gone,
        the local directory is removed (UI is source of truth for deletions).

        Returns the shared skills directory path (always, even on sync failure).
        """
        shared_dir = Path(self._get_shared_skills_dir(resolved_cwd))

        try:
            from open_webui.models.skills import SkillForm, SkillMeta, Skills

            sync_stats = {
                "db_to_file_updates": 0,
                "db_to_file_creates": 0,
                "file_to_db_updates": 0,
                "file_to_db_creates": 0,
                "file_to_db_links": 0,
                "orphan_dir_deletes": 0,
            }

            # ------------------------------------------------------------------
            # Step 1: Load all accessible OpenWebUI skills
            # ------------------------------------------------------------------
            owui_by_id: Dict[str, dict] = {}
            for skill in Skills.get_skills_by_user_id(user_id, "read") or []:
                if not skill or not getattr(skill, "is_active", False):
                    continue
                content = (getattr(skill, "content", "") or "").strip()
                sk_id = str(getattr(skill, "id", "") or "")
                sk_name = (getattr(skill, "name", "") or sk_id or "owui-skill").strip()
                if not sk_id or not sk_name or not content:
                    continue
                owui_by_id[sk_id] = {
                    "id": sk_id,
                    "name": sk_name,
                    "description": (getattr(skill, "description", "") or "")
                    .replace("\n", " ")
                    .strip(),
                    "content": content,
                    "updated_at": getattr(skill, "updated_at", 0) or 0,
                }

            # ------------------------------------------------------------------
            # Step 2: Load directory skills (shared/) and build lookup maps
            # ------------------------------------------------------------------
            dir_skills: Dict[str, dict] = {}  # dir_name → dict
            for skill_dir in shared_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md_path = skill_dir / "SKILL.md"
                if not skill_md_path.exists():
                    continue
                owui_id_file = skill_dir / ".owui_id"
                owui_id = (
                    owui_id_file.read_text(encoding="utf-8").strip()
                    if owui_id_file.exists()
                    else None
                )
                try:
                    file_content = skill_md_path.read_text(encoding="utf-8")
                    file_mtime = skill_md_path.stat().st_mtime
                except Exception:
                    continue
                dir_skills[skill_dir.name] = {
                    "path": skill_dir,
                    "owui_id": owui_id,
                    "mtime": file_mtime,
                    "content": file_content,
                }

            # Reverse map: owui_id → dir_name (for skills already linked)
            id_to_dir: Dict[str, str] = {
                info["owui_id"]: dn
                for dn, info in dir_skills.items()
                if info["owui_id"]
            }

            # ------------------------------------------------------------------
            # Step 3: DB → File  (OpenWebUI skills written to shared/)
            # ------------------------------------------------------------------
            for sk_id, sk in owui_by_id.items():
                expected_file_content = self._build_skill_md_content(
                    sk["name"], sk["description"], sk["content"]
                )

                if sk_id in id_to_dir:
                    dir_name = id_to_dir[sk_id]
                    dir_info = dir_skills[dir_name]
                    existing_hash = hashlib.md5(
                        dir_info["content"].encode("utf-8", errors="replace")
                    ).hexdigest()
                    new_hash = hashlib.md5(
                        expected_file_content.encode("utf-8", errors="replace")
                    ).hexdigest()
                    if (
                        existing_hash != new_hash
                        and sk["updated_at"] > dir_info["mtime"]
                    ):
                        # DB is newer — update file
                        (dir_info["path"] / "SKILL.md").write_text(
                            expected_file_content, encoding="utf-8"
                        )
                        dir_skills[dir_name]["content"] = expected_file_content
                        dir_skills[dir_name]["mtime"] = (
                            (dir_info["path"] / "SKILL.md").stat().st_mtime
                        )
                        sync_stats["db_to_file_updates"] += 1
                else:
                    # No directory for this OpenWebUI skill → create one
                    dir_name = self._skill_dir_name_from_skill_name(sk["name"])
                    # Avoid collision with existing dir names
                    base = dir_name
                    suffix = 1
                    while dir_name in dir_skills:
                        dir_name = f"{base}-{suffix}"
                        suffix += 1
                    skill_dir = shared_dir / dir_name
                    skill_dir.mkdir(parents=True, exist_ok=True)
                    (skill_dir / "SKILL.md").write_text(
                        expected_file_content, encoding="utf-8"
                    )
                    (skill_dir / ".owui_id").write_text(sk_id, encoding="utf-8")
                    dir_skills[dir_name] = {
                        "path": skill_dir,
                        "owui_id": sk_id,
                        "mtime": (skill_dir / "SKILL.md").stat().st_mtime,
                        "content": expected_file_content,
                    }
                    id_to_dir[sk_id] = dir_name
                    sync_stats["db_to_file_creates"] += 1

            # ------------------------------------------------------------------
            # Step 4: File → DB  (directory skills written to OpenWebUI)
            # ------------------------------------------------------------------
            owui_by_name: Dict[str, str] = {
                info["name"]: sid for sid, info in owui_by_id.items()
            }

            for dir_name, dir_info in dir_skills.items():
                owui_id = dir_info["owui_id"]
                file_content = dir_info["content"]
                file_mtime = dir_info["mtime"]
                parsed_name, parsed_desc, parsed_body = self._parse_skill_md_meta(
                    file_content, dir_name
                )

                if owui_id and owui_id in owui_by_id:
                    # Skill is linked to DB — check if file is newer and content differs
                    db_info = owui_by_id[owui_id]
                    # Re-construct what the file would look like from DB to compare
                    db_file_content = self._build_skill_md_content(
                        db_info["name"], db_info["description"], db_info["content"]
                    )
                    file_hash = hashlib.md5(
                        file_content.encode("utf-8", errors="replace")
                    ).hexdigest()
                    db_hash = hashlib.md5(
                        db_file_content.encode("utf-8", errors="replace")
                    ).hexdigest()
                    if file_hash != db_hash and file_mtime > db_info["updated_at"]:
                        # File is newer — push to DB
                        Skills.update_skill_by_id(
                            owui_id,
                            {
                                "name": parsed_name,
                                "description": parsed_desc or parsed_name,
                                "content": parsed_body or file_content,
                            },
                        )
                        sync_stats["file_to_db_updates"] += 1
                elif owui_id and owui_id not in owui_by_id:
                    # .owui_id points to a removed skill in OpenWebUI UI.
                    # UI is source of truth — delete local dir.
                    try:
                        shutil.rmtree(dir_info["path"], ignore_errors=False)
                        sync_stats["orphan_dir_deletes"] += 1
                    except Exception as e:
                        logger.warning(
                            f"[Skills Sync] Failed to remove orphaned skill dir '{dir_info['path']}': {e}"
                        )
                else:
                    # No OpenWebUI link — try to match by name, then create new
                    matched_id = owui_by_name.get(parsed_name)
                    if matched_id:
                        # Link to existing skill with same name
                        (dir_info["path"] / ".owui_id").write_text(
                            matched_id, encoding="utf-8"
                        )
                        sync_stats["file_to_db_links"] += 1
                        db_info = owui_by_id[matched_id]
                        db_file_content = self._build_skill_md_content(
                            db_info["name"], db_info["description"], db_info["content"]
                        )
                        file_hash = hashlib.md5(
                            file_content.encode("utf-8", errors="replace")
                        ).hexdigest()
                        db_hash = hashlib.md5(
                            db_file_content.encode("utf-8", errors="replace")
                        ).hexdigest()
                        if file_hash != db_hash and file_mtime > db_info["updated_at"]:
                            Skills.update_skill_by_id(
                                matched_id,
                                {
                                    "name": parsed_name,
                                    "description": parsed_desc or parsed_name,
                                    "content": parsed_body or file_content,
                                },
                            )
                            sync_stats["file_to_db_updates"] += 1
                    else:
                        # Truly new skill from file — register in OpenWebUI
                        new_skill = Skills.insert_new_skill(
                            user_id=user_id,
                            form_data=SkillForm(
                                id=str(uuid.uuid4()),
                                name=parsed_name,
                                description=parsed_desc or parsed_name,
                                content=parsed_body or file_content,
                                meta=SkillMeta(),
                                is_active=True,
                            ),
                        )
                        if new_skill:
                            new_id = str(getattr(new_skill, "id", "") or "")
                            (dir_info["path"] / ".owui_id").write_text(
                                new_id, encoding="utf-8"
                            )
                            sync_stats["file_to_db_creates"] += 1

            logger.debug(f"[Skills Sync] Summary: {sync_stats}")

        except ImportError:
            # Running outside OpenWebUI environment — directory is still usable
            pass
        except Exception as e:
            logger.debug(f"[Copilot] Skills sync failed: {e}", exc_info=True)

        return str(shared_dir)

    def _resolve_session_skill_config(
        self,
        resolved_cwd: str,
        user_id: Optional[str],
        enable_openwebui_skills: bool,
        disabled_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        skill_directories: List[str] = []

        # Unified shared directory — always included.
        # When enable_openwebui_skills is True, run bidirectional sync first so
        # OpenWebUI page skills and directory skills are kept in sync.
        if enable_openwebui_skills and user_id:
            shared_dir = self._sync_openwebui_skills(resolved_cwd, user_id)
        else:
            shared_dir = self._get_shared_skills_dir(resolved_cwd)
        skill_directories.append(shared_dir)

        config: Dict[str, Any] = {}
        if skill_directories:
            config["skill_directories"] = self._dedupe_preserve_order(skill_directories)

        if disabled_skills:
            normalized_disabled = self._dedupe_preserve_order(disabled_skills)
            if normalized_disabled:
                config["disabled_skills"] = normalized_disabled

        return config

    def _is_code_interpreter_feature_enabled(
        self, body: Optional[dict], __metadata__: Optional[dict] = None
    ) -> bool:
        """Code interpreter must be explicitly enabled by request feature flags."""

        def _extract_flag(container: Any) -> Optional[bool]:
            if not isinstance(container, dict):
                return None
            features = container.get("features")
            if isinstance(features, dict) and "code_interpreter" in features:
                return bool(features.get("code_interpreter"))
            return None

        # 1) top-level body.features
        flag = _extract_flag(body)
        if flag is not None:
            return flag

        # 2) body.metadata.features
        if isinstance(body, dict):
            flag = _extract_flag(body.get("metadata"))
            if flag is not None:
                return flag

        # 3) injected __metadata__.features
        flag = _extract_flag(__metadata__)
        if flag is not None:
            return flag

        return False

    async def _extract_system_prompt(
        self,
        body: dict,
        messages: List[dict],
        request_model: str,
        real_model_id: str,
        code_interpreter_enabled: bool = False,
        __event_call__=None,
        debug_enabled: bool = False,
    ) -> Tuple[Optional[str], str]:
        """Extract system prompt from metadata/model DB/body/messages."""
        system_prompt_content: Optional[str] = None
        system_prompt_source = ""

        # 0) body.get("system_prompt") - Explicit Override (Highest Priority)
        if hasattr(body, "get") and body.get("system_prompt"):
            system_prompt_content = body.get("system_prompt")
            system_prompt_source = "body_explicit_system_prompt"
            await self._emit_debug_log(
                f"Extracted system prompt from explicit body field (length: {len(system_prompt_content or '')})",
                __event_call__,
                debug_enabled=debug_enabled,
            )

        # 1) metadata.model.params.system
        if not system_prompt_content:
            metadata = body.get("metadata", {})
            if isinstance(metadata, dict):
                meta_model = metadata.get("model")
                if isinstance(meta_model, dict):
                    meta_params = meta_model.get("params")
                    if isinstance(meta_params, dict) and meta_params.get("system"):
                        system_prompt_content = meta_params.get("system")
                        system_prompt_source = "metadata.model.params"
                        await self._emit_debug_log(
                            f"Extracted system prompt from metadata.model.params (length: {len(system_prompt_content or '')})",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )

        # 2) model DB lookup
        if not system_prompt_content:
            try:
                from open_webui.models.models import Models

                model_ids_to_try = self._collect_model_ids(
                    body, request_model, real_model_id
                )
                await self._emit_debug_log(
                    f"Checking system prompt for models: {model_ids_to_try}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                for mid in model_ids_to_try:
                    model_record = await _call_openwebui_compat(
                        Models.get_model_by_id,
                        mid,
                        prefer_thread_for_sync=True,
                    )
                    if model_record:
                        await self._emit_debug_log(
                            f"Checking Model DB for: {mid} (Record found: {model_record.id if hasattr(model_record, 'id') else 'Yes'})",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )
                        if hasattr(model_record, "params"):
                            params = model_record.params
                            if isinstance(params, dict):
                                system_prompt_content = params.get("system")
                                if system_prompt_content:
                                    system_prompt_source = f"model_db:{mid}"
                                    await self._emit_debug_log(
                                        f"Success! Extracted system prompt from model DB using ID: {mid} (length: {len(system_prompt_content)})",
                                        __event_call__,
                                        debug_enabled=debug_enabled,
                                    )
                                    break
            except Exception as e:
                await self._emit_debug_log(
                    f"Failed to extract system prompt from model DB: {e}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

        # 3) body.params.system
        if not system_prompt_content:
            body_params = body.get("params", {})
            if isinstance(body_params, dict):
                system_prompt_content = body_params.get("system")
                if system_prompt_content:
                    system_prompt_source = "body_params"
                    await self._emit_debug_log(
                        f"Extracted system prompt from body.params.system (length: {len(system_prompt_content)})",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )

        # 4) messages (role=system) - Last found wins or First found wins?
        # Typically OpenWebUI puts the active system prompt as the FIRST message.
        if not system_prompt_content:
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt_content = self._extract_text_from_content(
                        msg.get("content", "")
                    )
                    if system_prompt_content:
                        system_prompt_source = "messages_system"
                        await self._emit_debug_log(
                            f"Extracted system prompt from messages (reverse search) (length: {len(system_prompt_content)})",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )
                    break

        # Append Code Interpreter Warning only when feature is explicitly enabled
        if code_interpreter_enabled:
            code_interpreter_warning = (
                "\n\n[System Note]\n"
                "The `execute_code` tool (builtin category: `code_interpreter`) executes code in a remote, ephemeral environment. "
                "It cannot access files in your local workspace or persist changes. "
                "Use it only for calculation or logic verification, not for file manipulation."
                "\n"
                "always use relative paths that start with `/api/v1/files/`. "
                "Do not output `api/...` and do not prepend any domain or protocol (e.g., NEVER use `https://same.ai/api/...`)."
            )
            if system_prompt_content:
                system_prompt_content += code_interpreter_warning
            else:
                system_prompt_content = code_interpreter_warning.strip()

        return system_prompt_content, system_prompt_source

    def _get_workspace_dir(
        self, user_id: Optional[str] = None, chat_id: Optional[str] = None
    ) -> str:
        """Get the effective workspace directory with user and chat isolation."""
        # Fixed base directory for OpenWebUI container
        if os.path.exists("/app/backend/data"):
            base_cwd = "/app/backend/data/copilot_workspace"
        else:
            # Local fallback for development environment
            base_cwd = os.path.join(os.getcwd(), "copilot_workspace")

        cwd = base_cwd
        if user_id:
            # Sanitize user_id to prevent path traversal
            safe_user_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id))
            cwd = os.path.join(cwd, safe_user_id)
        if chat_id:
            # Sanitize chat_id
            safe_chat_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(chat_id))
            cwd = os.path.join(cwd, safe_chat_id)

        # Ensure directory exists
        if not os.path.exists(cwd):
            try:
                os.makedirs(cwd, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creating workspace {cwd}: {e}")
                return base_cwd

        return cwd

    def _record_user_chat_mapping(
        self, user_id: Optional[str], chat_id: Optional[str]
    ) -> None:
        """Persist the latest chat_id for the current user."""
        if not user_id or not chat_id:
            return

        mapping_file = CHAT_MAPPING_FILE

        try:
            mapping_file.parent.mkdir(parents=True, exist_ok=True)

            mapping: Dict[str, str] = {}
            if mapping_file.exists():
                try:
                    loaded = json.loads(mapping_file.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        mapping = {str(k): str(v) for k, v in loaded.items()}
                except Exception as e:
                    logger.warning(
                        f"[Session Tracking] Failed to read mapping file {mapping_file}: {e}"
                    )

            mapping[str(user_id)] = str(chat_id)

            temp_file = mapping_file.with_suffix(mapping_file.suffix + ".tmp")
            temp_file.write_text(
                json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            temp_file.replace(mapping_file)
        except Exception as e:
            logger.warning(f"[Session Tracking] Failed to persist mapping: {e}")

    def _build_client_config(
        self,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """Build CopilotClient config from valves and request body."""
        from copilot import SubprocessConfig

        cwd = self._get_workspace_dir(user_id=user_id, chat_id=chat_id)
        config_dir = self._get_copilot_config_dir()

        client_config = {}
        if os.environ.get("COPILOT_CLI_PATH"):
            client_config["cli_path"] = os.environ["COPILOT_CLI_PATH"]
        client_config["cwd"] = cwd
        client_config["github_token"] = token

        if self.valves.LOG_LEVEL:
            client_config["log_level"] = self.valves.LOG_LEVEL

        # Setup persistent CLI tool installation directories
        agent_env = dict(os.environ)

        # Safely inject token and config dir into the local agent environment
        agent_env["COPILOTSDK_CONFIG_DIR"] = config_dir
        if token:
            agent_env["GH_TOKEN"] = token
            agent_env["GITHUB_TOKEN"] = token
        if os.path.exists("/app/backend/data"):
            tools_dir = "/app/backend/data/.copilot_tools"
            npm_dir = f"{tools_dir}/npm"
            venv_dir = f"{tools_dir}/venv"

            try:
                os.makedirs(f"{npm_dir}/bin", exist_ok=True)

                # Setup Python Virtual Environment to strictly protect system python
                if not os.path.exists(f"{venv_dir}/bin/activate"):
                    import sys

                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "venv",
                            "--system-site-packages",
                            venv_dir,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )

                agent_env["NPM_CONFIG_PREFIX"] = npm_dir
                agent_env["VIRTUAL_ENV"] = venv_dir
                agent_env.pop("PYTHONUSERBASE", None)
                agent_env.pop("PIP_USER", None)

                agent_env["PATH"] = (
                    f"{npm_dir}/bin:{venv_dir}/bin:{agent_env.get('PATH', '')}"
                )
            except Exception as e:
                logger.warning(f"Failed to setup Python venv or tool dirs: {e}")

        if self.valves.CUSTOM_ENV_VARS:
            try:
                custom_env = json.loads(self.valves.CUSTOM_ENV_VARS)
                if isinstance(custom_env, dict):
                    agent_env.update(custom_env)
            except:
                pass

        client_config["env"] = agent_env

        return SubprocessConfig(**client_config)

    # ==================== Agent Team Helpers ====================

    async def _get_openwebui_models_by_tag(
        self, tag: str, user_id: str = "unknown"
    ) -> list:
        """Fetch OpenWebUI custom models that carry the given tag."""
        try:
            from open_webui.models.models import Models as OWModels

            result = await _call_openwebui_compat(
                OWModels.search_models,
                user_id=user_id,
                filter={},
                limit=200,
                prefer_thread_for_sync=True,
            )
            matched = []
            for m in _extract_search_result_items(result):
                if hasattr(m, "meta") and m.meta:
                    meta_obj = m.meta
                    if hasattr(meta_obj, "model_dump"):
                        meta = meta_obj.model_dump()
                    elif isinstance(meta_obj, dict):
                        meta = meta_obj
                    else:
                        meta = {}
                    raw_tags = meta.get("tags", []) or []
                    tag_names = set()
                    for t in raw_tags:
                        if isinstance(t, dict):
                            n = t.get("name", "")
                        else:
                            n = str(t) if t else ""
                        if n:
                            tag_names.add(n)
                    if tag in tag_names:
                        matched.append(m)
            return matched
        except Exception as e:
            logger.warning(f"[AgentTeam] Failed to fetch models by tag '{tag}': {e}")
            return []

    async def _get_openwebui_model_by_id(self, model_id: str, user_id: str = "unknown"):
        """Fetch a single OpenWebUI custom model by ID."""
        try:
            from open_webui.models.models import Models as OWModels

            result = await _call_openwebui_compat(
                OWModels.search_models,
                user_id=user_id,
                filter={},
                limit=200,
                prefer_thread_for_sync=True,
            )
            for m in _extract_search_result_items(result):
                if m.id == model_id:
                    return m
            return None
        except Exception as e:
            logger.warning(f"[AgentTeam] Failed to fetch model '{model_id}': {e}")
            return None

    def _build_custom_agent_from_model(
        self,
        model,
        mcp_servers: Optional[dict] = None,
        session_tools: Optional[list] = None,
    ) -> Optional[dict]:
        """
        Convert an OpenWebUI custom model object into a CustomAgentConfig dict.

        - session_tools: the pipe's resolved Tool list (already filtered by valve
          settings such as ENABLE_OPENWEBUI_TOOLS).  When provided, the agent's
          "tools" field is set to the exact same tool names so each agent has
          *precisely* the same capability as the base session — no more, no less.
          If session_tools is None/empty (no custom tools registered), "tools" is
          omitted from the agent config and the CLI default applies (all tools).
        - mcp_servers mirrors the pipe session's resolved MCP config.
        """
        try:
            model_id = getattr(model, "id", None)
            if not model_id:
                return None
            model_name = getattr(model, "name", "") or model_id

            # Extract system prompt: params.system > meta.system_prompt
            # Both params and meta may be Pydantic objects (ModelParams/ModelMeta).
            system_prompt = ""
            if hasattr(model, "params") and model.params:
                params_obj = model.params
                if hasattr(params_obj, "model_dump"):
                    params = params_obj.model_dump()
                elif isinstance(params_obj, dict):
                    params = params_obj
                else:
                    params = {}
                system_prompt = params.get("system", "") or ""
            if not system_prompt and hasattr(model, "meta") and model.meta:
                meta_obj = model.meta
                if hasattr(meta_obj, "model_dump"):
                    meta = meta_obj.model_dump()
                elif isinstance(meta_obj, dict):
                    meta = meta_obj
                else:
                    meta = {}
                system_prompt = meta.get("system_prompt", "") or ""

            # SDK agent name: alphanumeric + underscore/dash only
            agent_name = re.sub(r"[^a-zA-Z0-9_-]", "_", model_id)
            cfg: dict = {
                "name": agent_name,
                "display_name": model_name,
                "prompt": system_prompt
                or f"You are {model_name}, a helpful AI assistant.",
                "infer": True,
            }

            # Mirror the session's exact tool list so each agent has the same
            # capability as the base session (respects ENABLE_OPENWEBUI_TOOLS,
            # ENABLE_OPENAPI_SERVER, etc.).  Tool objects expose a .name str.
            # Omit the key entirely when no custom tools are registered — the CLI
            # will apply its own default rather than sending an empty list.
            if session_tools:
                tool_names = [
                    t.name for t in session_tools if hasattr(t, "name") and t.name
                ]
                if tool_names:
                    cfg["tools"] = tool_names
            # else: key absent → CLI default (all available tools)

            # Inject the pipe's resolved MCP servers so each agent has the same
            # server access as the default (no-agent-team) session path.
            if mcp_servers:
                cfg["mcp_servers"] = mcp_servers
            return cfg
        except Exception as e:
            logger.warning(f"[AgentTeam] Failed to build agent config from model: {e}")
            return None

    async def _resolve_agent_team(
        self,
        user_valves,
        user_id: str = "unknown",
        session_tools: Optional[list] = None,
        session_mcp_servers: Optional[dict] = None,
    ) -> tuple:
        """
        Resolve Agent Team from valves (async — awaits OpenWebUI model queries).
        Priority: user_valves TAG > valves TAG > user_valves MODEL_IDS > valves MODEL_IDS.

        Each resolved agent is configured with:
        - tools: the exact same tool names as the pipe's session_tools list so
          each agent has precisely the same capability as the base session
          (respects ENABLE_OPENWEBUI_TOOLS and other valve toggles).
        - The same mcp_servers as the pipe session (respects ENABLE_MCP_SERVER valve).

        Returns (custom_agents: list | None, agent_leader_name: str | None).
        """
        effective_tag = (getattr(user_valves, "AGENT_TEAM_TAG", "") or "").strip() or (
            self.valves.AGENT_TEAM_TAG or ""
        ).strip()
        effective_model_ids = (
            getattr(user_valves, "AGENT_TEAM_MODEL_IDS", "") or ""
        ).strip() or (self.valves.AGENT_TEAM_MODEL_IDS or "").strip()
        effective_leader = (
            getattr(user_valves, "AGENT_TEAM_LEADER", "") or ""
        ).strip() or (self.valves.AGENT_TEAM_LEADER or "").strip()

        owui_models = []
        if effective_tag:
            owui_models = await self._get_openwebui_models_by_tag(
                effective_tag, user_id=user_id
            )
            logger.debug(
                f"[AgentTeam] TAG='{effective_tag}' matched {len(owui_models)} models."
            )
        elif effective_model_ids:
            ids = [mid.strip() for mid in effective_model_ids.split(",") if mid.strip()]
            for mid in ids:
                m = await self._get_openwebui_model_by_id(mid, user_id=user_id)
                if m:
                    owui_models.append(m)
            logger.debug(
                f"[AgentTeam] MODEL_IDS matched {len(owui_models)}/{len(ids)} models."
            )

        if not owui_models:
            return None, None

        agents = []
        for m in owui_models:
            cfg = self._build_custom_agent_from_model(
                m,
                mcp_servers=session_mcp_servers,
                session_tools=session_tools,
            )
            if cfg:
                agents.append(cfg)

        if not agents:
            return None, None

        # Determine leader
        leader_name = None
        if effective_leader:
            desired = re.sub(r"[^a-zA-Z0-9_-]", "_", effective_leader)
            for a in agents:
                if a["name"] == desired:
                    leader_name = desired
                    break
        if not leader_name:
            leader_name = agents[0]["name"]

        logger.debug(
            f"[AgentTeam] Resolved {len(agents)} agent(s). Leader: '{leader_name}'. "
            f"MCP servers: {list(session_mcp_servers.keys()) if session_mcp_servers else []}."
        )
        return agents, leader_name

    # ============================================================

    def _build_final_system_message(
        self,
        system_prompt_content: Optional[str],
        is_admin: bool,
        user_id: Optional[str],
        chat_id: Optional[str],
        manage_skills_intent: bool = False,
        custom_agents: Optional[list] = None,
        agent_leader: Optional[str] = None,
        session_mode: str = "autopilot",
    ) -> str:
        """Build the final system prompt content used for both new and resumed sessions."""
        try:
            # -time.timezone is offset in seconds. UTC+8 is 28800.
            is_china_tz = (-time.timezone / 3600) == 8.0
        except Exception:
            is_china_tz = False

        if is_china_tz:
            pkg_mirror_hint = " (Note: Server is in UTC+8. You MUST append `-i https://pypi.tuna.tsinghua.edu.cn/simple` for pip/uv and `--registry=https://registry.npmmirror.com` for npm to prevent network timeouts.)"
        else:
            pkg_mirror_hint = " (Note: If network is slow or times out, proactively use a fast regional mirror suitable for the current timezone.)"

        system_parts = []
        if system_prompt_content:
            system_parts.append(system_prompt_content.strip())

        if custom_agents:
            member_labels = []
            leader_label = agent_leader or ""
            for agent in custom_agents:
                if not isinstance(agent, dict):
                    continue
                agent_name = str(agent.get("name") or "").strip()
                display_name = str(
                    agent.get("display_name") or agent.get("displayName") or agent_name
                ).strip()
                if display_name:
                    member_labels.append(display_name)
                if agent_leader and agent_name == agent_leader:
                    leader_label = display_name or agent_leader

            _my_identity = leader_label or agent_leader or "team coordinator"
            _members_str = (
                ", ".join(member_labels)
                if member_labels
                else "configured custom agents"
            )
            team_context_lines = [
                "[Agent Team Runtime Context — READ CAREFULLY]",
                "- Agent Team is currently ENABLED for this conversation.",
                f"- YOUR IDENTITY: You ARE the `{_my_identity}` agent. This is your name and role RIGHT NOW — not a mode you 'can switch to', not a capability, but your current identity.",
                f"- Sub-agents available for delegation: {_members_str}",
                f"- SELF-INTRODUCTION RULE: When the user asks 'who are you', 'what is your role', 'introduce yourself', or anything similar — your response MUST begin by identifying yourself as `{_my_identity}`. Example: 'I am {_my_identity}, the team leader for this session...' Do NOT say 'I can act as {_my_identity}' — you already ARE {_my_identity}.",
                "- FORBIDDEN: Never introduce yourself as a generic AI assistant, ChatGPT, Copilot, or any unnamed model. You have a specific agent identity assigned above.",
                "- Model Clarification: The underlying LLM is the Copilot SDK model configured for this chat. The agent name/role is a layer on top — both are true simultaneously.",
                "- Team Collaboration Mandate: You MUST actively use the agent team structure to solve problems. For every non-trivial task, think: (1) Can this be decomposed into focused sub-tasks? (2) Which sub-agent's specialty fits each part? (3) Delegate via the team rather than attempting to produce the full answer solo. You are the coordinator — synthesize and present the final result after leveraging your sub-agents.",
            ]
            system_parts.append("\n".join(team_context_lines))

        if manage_skills_intent:
            system_parts.append(
                "[Skill Management]\n"
                "If the user wants to install, create, delete, edit, or list skills, use the `manage_skills` tool.\n"
                "Supported operations: list, install, create, edit, delete, show.\n"
                "When installing skills that require CLI tools, you MAY run installation commands.\n"
                f"To avoid hanging the session, ALWAYS append `-q` or `--silent` to package managers, and confirm unattended installations (e.g., `npm install -g -q <pkg>` or `pip install -q <pkg>`).{pkg_mirror_hint}\n"
                "When running `npm install -g`, it will automatically use prefix `/app/backend/data/.copilot_tools/npm`. No need to set the prefix manually, but you MUST be aware this is the installation target.\n"
                "When running `pip install`, it operates within an isolated Python Virtual Environment (`VIRTUAL_ENV=/app/backend/data/.copilot_tools/venv`) that has access to system packages (`--system-site-packages`). This protects the system Python while allowing you to use pre-installed generic libraries. DO NOT attempt to bypass this isolation."
            )

        resolved_cwd = self._get_workspace_dir(user_id=user_id, chat_id=chat_id)
        config_dir = self._get_copilot_config_dir()
        plan_path = self._get_plan_file_path(chat_id) or os.path.join(
            config_dir, "session-state", "<chat_id>", "plan.md"
        )
        path_context = (
            f"\n[Session Context]\n"
            f"- **Your Isolated Workspace**: `{resolved_cwd}`\n"
            f"- **Active User ID**: `{user_id}`\n"
            f"- **Active Chat ID**: `{chat_id}`\n"
            f"- **Skills Directory**: `{self.valves.OPENWEBUI_SKILLS_SHARED_DIR}/shared/` — contains user-installed skills.\n"
            f"- **Config Directory / Metadata Area**: `{config_dir}` — contains session state, including per-chat metadata files.\n"
            f"- **Plan File**: `{plan_path}` — this file is in the **metadata area**, not in the workspace. If you decide to create or revise a reusable plan, update this file instead of writing a planning markdown file inside the repository or workspace.\n"
            f"- **CLI Tools Path**: `/app/backend/data/.copilot_tools/` — Global tools installed via npm or pip will automatically go here and be in your $PATH. Python tools are strictly isolated in a venv here.\n"
            "**CRITICAL INSTRUCTION**: You MUST use the above workspace for ALL file operations.\n"
            "- **Exception**: The plan file above is a session metadata artifact and lives outside the workspace on purpose.\n"
            "- DO NOT create files in `/tmp` or any other system directories.\n"
            "- Always interpret 'current directory' as your Isolated Workspace."
        )
        system_parts.append(path_context)

        native_tools_context = (
            "\n[Available Native System Tools]\n"
            "The host environment is rich. Based on the official OpenWebUI Docker deployment baseline (backend image), the following CLI tools are expected to be preinstalled and globally available in $PATH:\n"
            "- **Network/Data**: `curl`, `jq`, `netcat-openbsd`\n"
            "- **Media/Doc**: `pandoc` (format conversion), `ffmpeg` (audio/video)\n"
            "- **Build/System**: `git`, `gcc`, `make`, `build-essential`, `zstd`, `bash`\n"
            "- **Python/Runtime**: `python3`, `pip3`, `uv`\n"
            f"- **Package Mgr Guidance**: Prefer `uv pip install <pkg>` over plain `pip install` for speed and stability.{pkg_mirror_hint}\n"
            "- **Verification Rule**: Before installing any CLI/tool dependency, first check availability with `which <tool>` or a lightweight version probe (e.g. `<tool> --version`).\n"
            "- **Python Libs**: The active virtual environment inherits `--system-site-packages`. Advanced libraries like `pandas`, `numpy`, `pillow`, `opencv-python-headless`, `pypdf`, `langchain`, `playwright`, `httpx`, and `beautifulsoup4` are ALREADY installed. Try importing them before attempting to install.\n"
        )
        system_parts.append(native_tools_context)

        system_parts.append(BASE_GUIDELINES)

        # ── Active session mode directive ──────────────────────────────────────
        # This MUST appear after BASE_GUIDELINES (which defines the mode options)
        # so the LLM immediately knows which mode is currently configured.
        # Language is intentionally aligned with the Copilot SDK agent-loop docs:
        # https://github.com/github/copilot-sdk/blob/main/docs/features/agent-loop.md
        _mode_directives = {
            "autopilot": (
                "**ACTIVE SESSION MODE: `autopilot`** (SDK-enforced autonomous loop)\n"
                "When autopilot mode is active at the SDK level, the Copilot CLI automatically sends a continuation "
                "nudge if you stop without calling `task_complete`.\n\n"
                "You MUST:\n"
                "- Work continuously end-to-end without pausing for confirmation between steps.\n"
                "- Call `task_complete` (with a concise summary) only when the task is **definitively done**: "
                "every step resolved, errors fixed, verification passed.\n\n"
                "You MUST NOT call `task_complete` prematurely — specifically:\n"
                "- NOT if you have open questions: make a decision and keep working.\n"
                "- NOT if you hit an error: try to resolve it.\n"
                "- NOT if remaining steps exist: complete them first.\n\n"
                "Never ask 'shall I proceed?' or 'would you like me to continue?' — just continue."
            ),
            "interactive": (
                "**ACTIVE SESSION MODE: `interactive`** (step-by-step chat)\n"
                "The CLI does NOT inject continuation nudges in this mode. You answer the user's request, then **stop and wait** for their next message.\n\n"
                "You MUST:\n"
                "- Complete the immediate request fully and present results clearly.\n"
                "- After each logical action or deliverable, STOP and wait for the user's next instruction, "
                "unless the user explicitly says to proceed or chain steps.\n"
                "- Never chain multiple independent steps autonomously — let the user drive the pace.\n\n"
                "You MAY still use `task_complete` to mark a discrete task done, but it is optional in this mode."
            ),
            "plan": (
                "**ACTIVE SESSION MODE: `plan`** (plan-first, approval-gated execution)\n"
                "You MUST research and plan BEFORE taking any concrete action. Surface constraints, ambiguities, and risks first.\n\n"
                "You MUST:\n"
                "- Produce a clear, structured plan and present it to the user before writing or modifying any file.\n"
                "- Save the plan to the plan file path shown above.\n"
                "- WAIT for explicit user approval (e.g. 'proceed', 'looks good', 'execute') before implementing, "
                "unless the user explicitly instructs otherwise (e.g., 'just do it') — their direct instruction takes priority.\n\n"
                "Once approved, switch execution style to **autopilot** to complete the approved plan end-to-end, "
                "calling `task_complete` when done."
            ),
        }
        _mode_hint = _mode_directives.get(
            session_mode,
            f"**ACTIVE SESSION MODE: `{session_mode}`**\nOperate according to the `{session_mode}` mode guidelines above.",
        )
        system_parts.append(f"\n[Active Session Mode]\n{_mode_hint}")

        system_parts.append(
            self._build_adaptive_workstyle_context(plan_path, session_mode=session_mode)
        )

        if not self._is_version_at_least("0.8.0"):
            version_note = (
                f"\n**[CRITICAL VERSION NOTE]**\n"
                f"The host OpenWebUI version is `{open_webui_version}`, which is older than 0.8.0.\n"
                "- **Rich UI Disabled**: Integration features like `type: embeds` or automated iframe overlays are NOT supported.\n"
                "- **Protocol Fallback**: You MUST NOT rely on the 'Premium Delivery Protocol' for visuals. Instead, you SHOULD output the HTML code block manually in your message if you want the user to see the result."
            )
            system_parts.append(version_note)

        if is_admin:
            system_parts.append(ADMIN_EXTENSIONS)
        else:
            system_parts.append(USER_RESTRICTIONS)

        adaptive_console_note = (
            "\n[Adaptive Interactive Console Guidelines]\n"
            "Your generated views (e.g., `<iframe>`, `<richui>`, or HTML embeds) act as a Dynamic Operational State machine.\n"
            "- **Continuous Dashboarding**: When the user interacts (clicks), in your NEXT response, evaluate what previous controls are still useful.\n"
            "- **DO NOT blindly clone**: Do not copy 100% of previous buttons if they aren't relevant.\n"
            "- **Predictive Retention**: If a previous button was unclicked but is logical next step, merge it into current view.\n"
            "- **Selective Recall (有选择地召回)**: You must be highly selective! Just because an item is in the DB does NOT mean it should be rendered. Evaluate the CURRENT state and render ONLY items with high probability of being clicked next to prevent clutter.\n"
            "- **Pre-Initialized UI State Table**: An `interactive_controls` table has been created for you in the local `session.db` workspace for adaptive UI/control state.\n"
            "  - **Schema**: `id (TEXT PRIMARY KEY)`, `label (TEXT NOT NULL)`, `action (TEXT NOT NULL)`, `status (TEXT DEFAULT 'visible')`, `likelihood (REAL)`, `created_at`, `updated_at`.\n"
            "  - **Usage**: Use your `sql` tool to `SELECT`, `INSERT`, or `UPDATE` this table when you need persistent UI/control state for buttons, cards, or adaptive dashboards. Do NOT store TODO/task tracking here; keep task tracking in `todos` / `todo_deps` and use `interactive_controls` only for Rich UI state.\n"
            "- **Goal**: The latest output is always the single source of active operations."
        )
        system_parts.append(adaptive_console_note)

        return "\n".join(system_parts)

    def _build_session_config(
        self,
        chat_id: Optional[str],
        real_model_id: str,
        custom_tools: List[Any],
        system_prompt_content: Optional[str],
        is_streaming: bool,
        provider_config: Optional[dict] = None,
        reasoning_effort: str = "medium",
        is_reas_model: bool = False,
        is_admin: bool = False,
        user_id: Optional[str] = None,
        enable_mcp: bool = True,
        enable_openwebui_skills: bool = True,
        disabled_skills: Optional[List[str]] = None,
        chat_tool_ids: Optional[list] = None,
        __event_call__=None,
        manage_skills_intent: bool = False,
        custom_agents: Optional[list] = None,
        agent_leader: Optional[str] = None,
        session_mode: str = "autopilot",
    ):
        """Build SessionConfig for Copilot SDK."""
        from copilot.session import InfiniteSessionConfig, SessionConfig

        infinite_session_config = None
        if self.valves.INFINITE_SESSION:
            infinite_session_config = InfiniteSessionConfig(
                enabled=True,
                background_compaction_threshold=self.valves.COMPACTION_THRESHOLD,
                buffer_exhaustion_threshold=self.valves.BUFFER_THRESHOLD,
            )

        final_system_msg = self._build_final_system_message(
            system_prompt_content=system_prompt_content,
            is_admin=is_admin,
            user_id=user_id,
            chat_id=chat_id,
            manage_skills_intent=manage_skills_intent,
            custom_agents=custom_agents,
            agent_leader=agent_leader,
            session_mode=session_mode,
        )
        resolved_cwd = self._get_workspace_dir(user_id=user_id, chat_id=chat_id)

        # Design Choice: ALWAYS use 'replace' mode to ensure full control and avoid duplicates.
        system_message_config = {
            "mode": "replace",
            "content": final_system_msg,
        }

        mcp_servers = _resolve_awaitable_sync(
            self._parse_mcp_servers(
                __event_call__, enable_mcp=enable_mcp, chat_tool_ids=chat_tool_ids
            )
        )

        # Prepare session config parameters
        session_params = {
            "session_id": chat_id if chat_id else None,
            "model": real_model_id,
            "streaming": is_streaming,
            "tools": custom_tools,
            "system_message": system_message_config,
            "config_dir": self._get_copilot_config_dir(),
            "infinite_sessions": infinite_session_config,
            "working_directory": resolved_cwd,
        }

        permission_request_handler = getattr(PermissionHandler, "approve_all", None)
        if callable(permission_request_handler):
            session_params["on_permission_request"] = permission_request_handler

        if is_reas_model and reasoning_effort:
            # Map requested effort to supported efforts if possible
            m = next(
                (
                    m
                    for m in (self._model_cache or [])
                    if m.get("raw_id") == real_model_id
                ),
                None,
            )
            supp = (
                m.get("meta", {})
                .get("capabilities", {})
                .get("supported_reasoning_efforts", [])
                if m
                else []
            )
            s_supp = [str(e).lower() for e in supp]
            if s_supp:
                session_params["reasoning_effort"] = (
                    reasoning_effort
                    if reasoning_effort.lower() in s_supp
                    else ("high" if "high" in s_supp else "medium")
                )
            else:
                session_params["reasoning_effort"] = reasoning_effort

        if mcp_servers:
            session_params["mcp_servers"] = mcp_servers

        # Always set available_tools=None so the Copilot CLI's built-in tools
        # (e.g. bash, create_file) remain accessible alongside our custom tools.
        # Custom tools are registered via the 'tools' param; whitelist filtering
        # via available_tools would silently block CLI built-ins.
        session_params["available_tools"] = None

        if provider_config:
            session_params["provider"] = provider_config

        # Inject hooks for automatic large file handling
        session_params["hooks"] = self._build_session_hooks(
            cwd=resolved_cwd, __event_call__=__event_call__
        )

        session_params.update(
            self._resolve_session_skill_config(
                resolved_cwd=resolved_cwd,
                user_id=user_id,
                enable_openwebui_skills=enable_openwebui_skills,
                disabled_skills=disabled_skills,
            )
        )

        try:
            skill_dirs_dbg = session_params.get("skill_directories") or []
            if skill_dirs_dbg:
                logger.info(f"[Copilot] skill_directories={skill_dirs_dbg}")
                for sd in skill_dirs_dbg:
                    path = Path(sd)
                    skill_md_count = sum(
                        1 for p in path.glob("*/SKILL.md") if p.is_file()
                    )
                    logger.info(
                        f"[Copilot] skill_dir check: {sd} exists={path.exists()} skill_md_count={skill_md_count}"
                    )
        except Exception as e:
            logger.debug(f"[Copilot] skill directory debug check failed: {e}")

        # Inject agent team if configured
        if custom_agents:
            session_params["custom_agents"] = custom_agents
        if agent_leader:
            session_params["agent"] = agent_leader

        return session_params

    async def _abort_stale_resumed_turn_if_needed(
        self,
        session,
        __event_call__=None,
        debug_enabled: bool = False,
    ) -> bool:
        """
        Abort unfinished assistant work left in a resumed session before a new send.

        Without this guard, a resumed chat can continue stale in-flight work from a
        previous interrupted request, which may cause unrelated extra model turns.
        """
        try:
            history = await session.get_messages()
        except Exception as e:
            await self._emit_debug_log(
                f"Failed to inspect resumed session history: {e}",
                __event_call__,
                debug_enabled=debug_enabled,
            )
            return False

        if not history:
            return False

        last_user_index = -1
        for idx in range(len(history) - 1, -1, -1):
            if getattr(history[idx], "type", "") == "user.message":
                last_user_index = idx
                break

        if last_user_index < 0:
            return False

        pending_turn_depth = 0
        for event in history[last_user_index + 1 :]:
            event_type = getattr(event, "type", "")
            if event_type == "assistant.turn_start":
                pending_turn_depth += 1
            elif event_type == "assistant.turn_end":
                pending_turn_depth = max(0, pending_turn_depth - 1)
            elif event_type in {"session.idle", "session.error"}:
                pending_turn_depth = 0

        if pending_turn_depth <= 0:
            return False

        await self._emit_debug_log(
            (
                "Detected unfinished assistant work in resumed session; "
                "aborting stale turn before sending the new prompt."
            ),
            __event_call__,
            debug_enabled=debug_enabled,
        )

        try:
            await session.abort()
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            await self._emit_debug_log(
                f"Failed to abort stale resumed turn: {e}",
                __event_call__,
                debug_enabled=debug_enabled,
            )
            return False

    def _build_session_hooks(self, cwd: str, __event_call__=None):
        """
        Build session lifecycle hooks.
        Currently implements:
        - on_post_tool_use: Auto-copy large files from /tmp to workspace
        """

        async def on_post_tool_use(input_data, invocation):
            result = input_data.get("result", "")

            # Logic to detect and move large files saved to /tmp
            # Pattern: "Saved to: /tmp/copilot_result_xxxx.txt"
            import re
            import shutil

            # We search for potential /tmp file paths in the output
            # Common patterns from CLI: "Saved to: /tmp/..." or just "/tmp/..."
            match = re.search(r"(/tmp/[\w\-\.]+)", str(result))
            if match:
                tmp_path = match.group(1)
                if os.path.exists(tmp_path):
                    try:
                        filename = os.path.basename(tmp_path)
                        target_path = os.path.join(cwd, f"auto_output_{filename}")
                        shutil.copy2(tmp_path, target_path)

                        self._emit_debug_log_sync(
                            f"Hook [on_post_tool_use]: Auto-moved large output from {tmp_path} to {target_path}",
                            __event_call__,
                        )

                        return {
                            "additionalContext": (
                                f"\n[SYSTEM AUTO-MANAGEMENT] The output was large and originally saved to {tmp_path}. "
                                f"I have automatically moved it to your workspace as: `{os.path.basename(target_path)}`. "
                                f"You should now use the session's file-reading or search tools on this file to access the content."
                            )
                        }
                    except Exception as e:
                        self._emit_debug_log_sync(
                            f"Hook [on_post_tool_use] Error moving file: {e}",
                            __event_call__,
                        )

            return {}

        return {
            "on_post_tool_use": on_post_tool_use,
        }

    def _get_chat_context(
        self,
        body: Optional[dict],
        __metadata__: Optional[dict] = None,
        __event_call__=None,
        debug_enabled: bool = False,
    ) -> Dict[str, str]:
        """
        Highly reliable chat context extraction logic.
        Priority: __metadata__ > body['chat_id'] > body['metadata']['chat_id']
        """
        chat_id = ""
        session_id = ""
        message_id = ""
        source = "none"

        # 1. Prioritize __metadata__ (most reliable source injected by OpenWebUI)
        if __metadata__ and isinstance(__metadata__, dict):
            chat_id = __metadata__.get("chat_id", "")
            session_id = __metadata__.get("session_id", "")
            message_id = __metadata__.get("message_id", "")
            if chat_id:
                source = "__metadata__"

        # 2. Then try body root
        if not chat_id and isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            session_id = session_id or body.get("session_id", "")
            message_id = message_id or body.get("message_id", "")
            if chat_id:
                source = "body_root"

        # 3. Finally try body.metadata
        if not chat_id and isinstance(body, dict):
            body_metadata = body.get("metadata", {})
            if isinstance(body_metadata, dict):
                chat_id = body_metadata.get("chat_id", "")
                session_id = session_id or body_metadata.get("session_id", "")
                message_id = message_id or body_metadata.get("message_id", "")
                if chat_id:
                    source = "body_metadata"

        # Debug: Log ID source
        if chat_id:
            self._emit_debug_log_sync(
                f"Extracted ChatID: {chat_id} (Source: {source})",
                __event_call__,
                debug_enabled=debug_enabled,
            )
        else:
            # If still not found, log body keys for troubleshooting
            keys = list(body.keys()) if isinstance(body, dict) else "not a dict"
            self._emit_debug_log_sync(
                f"Warning: Failed to extract ChatID. Body keys: {keys}",
                __event_call__,
                debug_enabled=debug_enabled,
            )

        return {
            "chat_id": str(chat_id or "").strip(),
            "session_id": str(session_id or "").strip(),
            "message_id": str(message_id or "").strip(),
        }

    async def _fetch_byok_models(
        self, uv: Optional["Pipe.UserValves"] = None
    ) -> List[dict]:
        """Fetch BYOK models from configured provider."""
        model_list = []

        # Resolve effective settings (User > Global)
        # Note: We handle the case where uv might be None
        effective_base_url = (
            uv.BYOK_BASE_URL if uv else ""
        ) or self.valves.BYOK_BASE_URL
        effective_type = (uv.BYOK_TYPE if uv else "") or self.valves.BYOK_TYPE
        effective_api_key = (uv.BYOK_API_KEY if uv else "") or self.valves.BYOK_API_KEY
        effective_bearer_token = (
            uv.BYOK_BEARER_TOKEN if uv else ""
        ) or self.valves.BYOK_BEARER_TOKEN
        effective_models = (uv.BYOK_MODELS if uv else "") or self.valves.BYOK_MODELS

        # If user explicitly configured BYOK_MODELS, use them directly (skip API fetch)
        if effective_models.strip():
            model_list = [
                m.strip() for m in effective_models.split(",") if m.strip()
            ]
            await self._emit_debug_log(
                f"BYOK: Using user-configured BYOK_MODELS ({len(model_list)} models)."
            )
        elif effective_base_url:
            try:
                base_url = effective_base_url.rstrip("/")
                url = f"{base_url}/models"
                headers = {}
                provider_type = effective_type.lower()

                if provider_type == "anthropic":
                    if effective_api_key:
                        headers["x-api-key"] = effective_api_key
                    headers["anthropic-version"] = "2023-06-01"
                else:
                    if effective_bearer_token:
                        headers["Authorization"] = f"Bearer {effective_bearer_token}"
                    elif effective_api_key:
                        headers["Authorization"] = f"Bearer {effective_api_key}"

                timeout = aiohttp.ClientTimeout(total=60)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    for attempt in range(3):
                        try:
                            async with session.get(url, headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if (
                                        isinstance(data, dict)
                                        and "data" in data
                                        and isinstance(data["data"], list)
                                    ):
                                        for item in data["data"]:
                                            if isinstance(item, dict) and "id" in item:
                                                model_list.append(item["id"])
                                    elif isinstance(data, list):
                                        for item in data:
                                            if isinstance(item, dict) and "id" in item:
                                                model_list.append(item["id"])

                                    await self._emit_debug_log(
                                        f"BYOK: Fetched {len(model_list)} models from {url}"
                                    )
                                    break
                                else:
                                    await self._emit_debug_log(
                                        f"BYOK: Failed to fetch models from {url} (Attempt {attempt + 1}/3). Status: {resp.status}"
                                    )
                        except Exception as e:
                            await self._emit_debug_log(
                                f"BYOK: Model fetch error (Attempt {attempt + 1}/3): {e}"
                            )

                        if attempt < 2:
                            await asyncio.sleep(1)
            except Exception as e:
                await self._emit_debug_log(f"BYOK: Setup error: {e}")

        # Infer per-model provider from ID string (BYOK endpoints can return multi-provider lists)
        byok_models = [
            {
                "id": m,
                "name": f"-{self._clean_model_id(m)}",
                "source": "byok",
                "provider": self._infer_provider_from_id(m),
                "raw_id": m,
            }
            for m in model_list
        ]

        # Sort BYOK models by provider + name
        _provider_order = {"openai": 0, "anthropic": 1, "google": 2, "unknown": 3}
        byok_models.sort(
            key=lambda x: (
                _provider_order.get(x.get("provider", "unknown"), 3),
                x.get("raw_id", ""),
            )
        )

        return byok_models

    def _clean_model_id(self, model_id: str) -> str:
        """Remove copilot prefixes from model ID."""
        if model_id.startswith("copilot-"):
            return model_id[8:]
        elif model_id.startswith("copilot - "):
            return model_id[10:]
        return model_id

    def _get_provider_name(self, m_info: Any) -> str:
        """Identify provider from model metadata."""
        m_id = getattr(m_info, "id", str(m_info)).lower()
        if any(k in m_id for k in ["gpt", "codex"]):
            return "OpenAI"
        if "claude" in m_id:
            return "Anthropic"
        if "gemini" in m_id:
            return "Google"
        p = getattr(m_info, "policy", None)
        if p:
            t = str(getattr(p, "terms", "")).lower()
            if "openai" in t:
                return "OpenAI"
            if "anthropic" in t:
                return "Anthropic"
            if "google" in t:
                return "Google"
        return "Unknown"

    def _infer_provider_from_id(self, model_id: str) -> str:
        """Infer provider from model ID string — used for BYOK models where API doesn't expose provider."""
        id_lower = model_id.lower()
        if any(
            k in id_lower for k in ["gpt", "codex", "o1", "o3", "o4", "o5", "chatgpt"]
        ):
            return "openai"
        if any(k in id_lower for k in ["claude", "anthropic"]):
            return "anthropic"
        if any(k in id_lower for k in ["gemini", "aistudio", "vertex"]):
            return "google"
        # Third-party providers grouped with OpenAI for sorting
        if any(
            k in id_lower
            for k in [
                "qwen",
                "qwen3",
                "qwq",
                "deepseek",
                "mistral",
                "mixtral",
                "llama",
                "llm",
            ]
        ):
            return "openai"
        if "/" in model_id:  # OpenRouter format: provider/model
            return "openai"
        return "unknown"

    def _get_user_valves(self, __user__: Optional[dict]) -> "Pipe.UserValves":
        """Robustly extract UserValves from __user__ context."""
        if not __user__:
            return self.UserValves()

        # Handle list/tuple wrap
        user_data = __user__[0] if isinstance(__user__, (list, tuple)) else __user__
        if not isinstance(user_data, dict):
            return self.UserValves()

        raw_valves = user_data.get("valves")
        if isinstance(raw_valves, self.UserValves):
            return raw_valves
        if isinstance(raw_valves, dict):
            try:
                return self.UserValves(**raw_valves)
            except Exception as e:
                logger.warning(f"[Copilot] Failed to parse UserValves: {e}")
        return self.UserValves()

    def _format_model_item(self, m: Any, source: str = "copilot") -> Optional[dict]:
        """Standardize model item into OpenWebUI pipe format."""
        try:
            # 1. Resolve ID
            mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", "")
            if not mid:
                return None

            # 2. Extract Multiplier (billing info)
            bill = (
                m.get("billing") if isinstance(m, dict) else getattr(m, "billing", {})
            )
            if bill is not None and hasattr(bill, "to_dict"):
                bill = bill.to_dict()  # type: ignore[union-attr]
            mult = float(bill.get("multiplier", 1.0)) if isinstance(bill, dict) else 1.0

            # 3. Clean ID and build display name
            cid = self._clean_model_id(mid)

            # Format name based on source
            if source == "byok":
                display_name = f"-{cid}"
            else:
                display_name = f"-{cid} ({mult}x)" if mult > 0 else f"-🔥 {cid} (0x)"

            return {
                "id": f"{self.id}-{mid}" if source == "copilot" else mid,
                "name": display_name,
                "multiplier": mult,
                "raw_id": mid,
                "source": source,
                "provider": (
                    self._get_provider_name(m).lower()
                    if source == "copilot"
                    else "byok"
                ),
            }
        except Exception as e:
            logger.debug(f"[Pipes] Format error for model {m}: {e}")
            return None

    async def pipes(self, __user__: Optional[dict] = None) -> List[dict]:
        """Model discovery: Fetches standard and BYOK models with config-isolated caching."""
        uv = self._get_user_valves(__user__)
        token = uv.GH_TOKEN or self.valves.GH_TOKEN

        now = datetime.now().timestamp()
        cache_ttl = self.valves.MODEL_CACHE_TTL

        # Fingerprint the context so different users/tokens DO NOT evict each other
        current_config_str = f"{token}|{uv.BYOK_BASE_URL or self.valves.BYOK_BASE_URL}|{uv.BYOK_API_KEY or self.valves.BYOK_API_KEY}|{self.valves.BYOK_BEARER_TOKEN}"
        current_config_hash = hashlib.md5(current_config_str.encode()).hexdigest()

        # Dictionary-based Cache lookup (Solves the flapping bug)
        if hasattr(self.__class__, "_discovery_cache"):
            cached = self.__class__._discovery_cache.get(current_config_hash)
            if cached and cache_ttl > 0 and (now - cached["time"]) <= cache_ttl:
                self.__class__._model_cache = cached[
                    "models"
                ]  # Update global for pipeline capability fallbacks
                return self._apply_model_filters(cached["models"], uv)

        # 1. Core discovery logic (Always fresh)
        results = await asyncio.gather(
            self._fetch_standard_models(token, __user__),
            self._fetch_byok_models(uv),
            return_exceptions=True,
        )

        standard_results: List[dict] = (
            results[0] if not isinstance(results[0], Exception) else []
        )  # type: ignore[assignment]
        byok_results: List[dict] = (
            results[1] if not isinstance(results[1], Exception) else []
        )  # type: ignore[assignment]

        # Merge all discovered models and sort by source (copilot=0, byok=1), then provider, then multiplier
        # Ensure explicit group: copilot models always before byok models
        all_models = standard_results + byok_results
        _provider_order = {"openai": 0, "anthropic": 1, "google": 2, "unknown": 3}
        all_models.sort(
            key=lambda x: (
                0 if x.get("source") == "copilot" else 1,  # copilot=0, byok=1, explicit
                _provider_order.get(x.get("provider", "unknown"), 3),
                (0.0 if x.get("multiplier") is None else x.get("multiplier", 1.0)),
                x.get("raw_id", ""),
            )
        )

        # Insert visual separator between copilot and byok groups if both exist
        if byok_results and standard_results:
            sep_idx = next(
                (i for i, m in enumerate(all_models) if m.get("source") == "byok"),
                None,
            )
            if sep_idx and sep_idx > 0:
                all_models.insert(
                    sep_idx,
                    {
                        "id": "__byok__",
                        "name": "───── BYOK ─────",
                        "source": "separator",
                        "provider": "separator",
                        "raw_id": "__byok__",
                    },
                )

        # Update local instance cache for validation purposes in _pipe_impl
        self.__class__._model_cache = all_models

        # Update Config-isolated dict cache
        if not hasattr(self.__class__, "_discovery_cache"):
            self.__class__._discovery_cache = {}

        if all_models:
            self.__class__._discovery_cache[current_config_hash] = {
                "time": now,
                "models": all_models,
            }
        else:
            # If discovery completely failed, cache for a very short duration (10s) to prevent spam but allow quick recovery
            self.__class__._discovery_cache[current_config_hash] = {
                "time": now - cache_ttl + 10,
                "models": all_models,
            }

        # 2. Return results with real-time user-specific filtering
        return self._apply_model_filters(all_models, uv)

    async def _get_client(self, token: str) -> Any:
        """Get or create the persistent CopilotClient from the pool based on token."""
        # Use an MD5 hash of the token as the key for the client pool.
        # If no token is provided (BYOK-only mode), use a dedicated cache key.
        safe_token = token or "byok_only_mode"
        token_hash = hashlib.md5(safe_token.encode()).hexdigest()

        async with self.__class__._shared_client_lock:
            # Check if client exists for this token and is healthy
            client = self.__class__._shared_clients.get(token_hash)
            if client:
                try:
                    state = client.get_state()
                    if state == "connected":
                        return client
                    if state == "error":
                        try:
                            await client.stop()
                        except:
                            pass
                        del self.__class__._shared_clients[token_hash]
                except Exception:
                    del self.__class__._shared_clients[token_hash]

            # Ensure environment discovery is done
            if not self.__class__._env_setup_done:
                self._setup_env(token=token)

            # Build configuration and start persistent client
            client_config = self._build_client_config(
                user_id=None, chat_id=None, token=token
            )

            new_client = CopilotClient(client_config, auto_start=True)
            await new_client.start()
            self.__class__._shared_clients[token_hash] = new_client
            return new_client

    async def _fetch_standard_models(
        self, token: str, __user__: Optional[dict]
    ) -> List[dict]:
        """Fetch models using the shared persistent client pool."""
        if not token:
            return []

        try:
            client = await self._get_client(token)
            raw = await client.list_models()

            models = []
            for m in raw if isinstance(raw, list) else []:
                formatted = self._format_model_item(m, source="copilot")
                if formatted:
                    models.append(formatted)

            # Sort: OpenAI first, then Anthropic, then others; within same provider by multiplier ascending (free/0x first)
            _provider_order = {"openai": 0, "anthropic": 1, "google": 2, "unknown": 3}
            models.sort(
                key=lambda x: (
                    _provider_order.get(x.get("provider", "unknown").lower(), 3),
                    (0.0 if x.get("multiplier") is None else x.get("multiplier", 1.0)),
                    x.get("raw_id", ""),
                )
            )
            return models
        except Exception as e:
            logger.error(f"[Pipes] Standard fetch failed: {e}")
            return []

    def _apply_model_filters(
        self, models: List[dict], uv: "Pipe.UserValves"
    ) -> List[dict]:
        """Apply user-defined multiplier and keyword exclusions to the model list."""
        if not models:
            # Check if BYOK or GH_TOKEN is configured at all
            has_byok_config = (uv.BYOK_BASE_URL or self.valves.BYOK_BASE_URL) and (
                uv.BYOK_API_KEY
                or self.valves.BYOK_API_KEY
                or uv.BYOK_BEARER_TOKEN
                or self.valves.BYOK_BEARER_TOKEN
            )
            if not (uv.GH_TOKEN or self.valves.GH_TOKEN) and not has_byok_config:
                return [
                    {
                        "id": "no_credentials",
                        "name": "⚠️ No credentials configured. Please set GH_TOKEN or BYOK settings in Valves.",
                    }
                ]
            return [{"id": "warming_up", "name": "Waiting for model discovery..."}]

        # Resolve constraints
        global_max = getattr(self.valves, "MAX_MULTIPLIER", 1.0)
        user_max = getattr(uv, "MAX_MULTIPLIER", None)
        eff_max = (
            min(float(user_max), float(global_max))
            if user_max is not None
            else float(global_max)
        )

        ex_kw = [
            k.strip().lower()
            for k in (self.valves.EXCLUDE_KEYWORDS + "," + uv.EXCLUDE_KEYWORDS).split(
                ","
            )
            if k.strip()
        ]
        res = []
        epsilon = 0.0001

        for m in models:
            mid = (m.get("raw_id") or m.get("id", "")).lower()
            mname = m.get("name", "").lower()
            msource = m.get("source", "")

            # 1. Official GitHub Model Hard-coded Filters
            if msource == "copilot":
                # Filter out experimental GPT-5 series which are often redundant or confusing
                if any(
                    target in mid
                    for target in [
                        "gpt-5.2-codex",
                        "gpt-5.2",
                        "gpt-5.1-codex-max",
                        "gpt-5.1-codex",
                        "gpt-5.1",
                    ]
                ):
                    continue

                # Filter out older iterations of Claude Sonnet (4, 4.5) as 4.6 is now available.
                # Use exact/prefix-safe match: must equal or end with "-<target>" to avoid
                # "claude-sonnet-4" matching "claude-sonnet-4.6".
                def is_target(mid: str, target: str) -> bool:
                    return mid == target or mid.endswith("-" + target)

                if any(
                    is_target(mid, t) or is_target(mname, t)
                    for t in [
                        "claude-sonnet-4",
                        "claude-sonnet-4.5",
                    ]
                ):
                    continue

                # Filter out older Opus (4) keeping only 4.6
                if any(
                    is_target(mid, t) or is_target(mname, t)
                    for t in [
                        "claude-opus-4",
                        "claude-opus-4.5",
                    ]
                ):
                    continue

            # 2. User-defined Keyword Filter
            if any(kw in mid or kw in mname for kw in ex_kw):
                continue

            # 3. Multiplier Filter (Copilot source only)
            if msource == "copilot":
                if float(m.get("multiplier", 1.0)) > (eff_max + epsilon):
                    continue

            # 4. Filter out separator items — they are display-only, not selectable models
            if msource == "separator":
                continue

            res.append(m)

        return (
            res
            if res
            else [
                {"id": "none", "name": "No models matched your current Valve filters"}
            ]
        )

    def _setup_env(
        self,
        __event_call__=None,
        debug_enabled: bool = False,
        token: Optional[str] = None,
        enable_mcp: bool = True,
    ):
        """Setup environment variables and resolve the deterministic Copilot CLI path."""

        # 1. Real-time Token Injection
        # Note: We no longer set os.environ["GH_TOKEN"] globally here to prevent cross-user token pollution.
        # It is handled securely via CopilotClient configuration and local agent_env.
        effective_token = token or self.valves.GH_TOKEN

        if self._env_setup_done:
            return

        # 2. Deterministic CLI Path Discovery
        # We prioritize the bundled CLI from the SDK to ensure version compatibility.
        cli_path = ""
        try:
            from copilot.client import _get_bundled_cli_path

            cli_path = _get_bundled_cli_path() or ""
        except ImportError:
            pass

        # Fallback to environment or system PATH only if bundled path is invalid
        if not cli_path or not os.path.exists(cli_path):
            cli_path = (
                os.environ.get("COPILOT_CLI_PATH") or shutil.which("copilot") or ""
            )

        cli_ready = bool(cli_path and os.path.exists(cli_path))

        # 3. Finalize Environment
        if cli_ready:
            os.environ["COPILOT_CLI_PATH"] = cli_path
            # Add to PATH for subprocess visibility
            cli_bin_dir = os.path.dirname(cli_path)
            current_path = os.environ.get("PATH", "")
            if cli_bin_dir and cli_bin_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = cli_bin_dir + os.pathsep + current_path

        self.__class__._env_setup_done = cli_ready
        self.__class__._last_update_check = datetime.now().timestamp()

        self._emit_debug_log_sync(
            f"Deterministic Env Setup: CLI ready={cli_ready}, Path={cli_path}",
            __event_call__,
            debug_enabled=debug_enabled,
        )

    def _process_attachments(
        self,
        messages,
        cwd=None,
        files=None,
        __event_call__=None,
        debug_enabled: bool = False,
    ):
        attachments = []
        text_content = ""
        saved_files_info = []

        # 1. Process OpenWebUI Uploaded Files (body['files'])
        if files and cwd:
            for file_item in files:
                try:
                    # Adapt to different file structures
                    file_obj = file_item.get("file", file_item)
                    file_id = file_obj.get("id")
                    filename = (
                        file_obj.get("filename") or file_obj.get("name") or "upload.bin"
                    )

                    if file_id:
                        # Construct source path
                        src_path = os.path.join(
                            self.valves.OPENWEBUI_UPLOAD_PATH, f"{file_id}_{filename}"
                        )

                        if os.path.exists(src_path):
                            # Copy to workspace
                            dst_path = os.path.join(cwd, filename)
                            shutil.copy2(src_path, dst_path)

                            saved_files_info.append(
                                f"- User uploaded file: `{filename}` (Saved to workspace)"
                            )
                            self._emit_debug_log_sync(
                                f"Copied file to workspace: {dst_path}",
                                __event_call__,
                                debug_enabled,
                            )
                        else:
                            self._emit_debug_log_sync(
                                f"Source file not found: {src_path}",
                                __event_call__,
                                debug_enabled,
                            )
                except Exception as e:
                    self._emit_debug_log_sync(
                        f"Error processing file {file_item}: {e}",
                        __event_call__,
                        debug_enabled,
                    )

        # 2. Process Base64 Images in Messages
        if not messages:
            return "", []
        last_msg = messages[-1]
        content = last_msg.get("content", "")

        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    text_content += item.get("text", "")
                elif item.get("type") == "image_url":
                    image_url = item.get("image_url", {}).get("url", "")
                    if image_url.startswith("data:image"):
                        try:
                            header, encoded = image_url.split(",", 1)
                            ext = header.split(";")[0].split("/")[-1]
                            file_name = f"image_{len(attachments)}.{ext}"
                            file_path = os.path.join(self.temp_dir, file_name)
                            with open(file_path, "wb") as f:
                                f.write(base64.b64decode(encoded))
                            attachments.append(
                                {
                                    "type": "file",
                                    "path": file_path,
                                    "display_name": file_name,
                                }
                            )
                            self._emit_debug_log_sync(
                                f"Image processed: {file_path}",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                        except Exception as e:
                            self._emit_debug_log_sync(
                                f"Image error: {e}",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
        else:
            text_content = str(content)

        # Append saved files info to the text content seen by the agent
        if saved_files_info:
            info_block = (
                "\n\n[System Notification: New Files Available]\n"
                + "\n".join(saved_files_info)
                + "\nYou can access these files directly using their filenames in your workspace."
            )
            text_content += info_block

        return text_content, attachments

    # ==================== Internal Implementation ====================
    # _pipe_impl() contains the main request handling logic.
    # ================================================================
    async def _pipe_impl(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
        __request__=None,
        __messages__: Optional[list] = None,
        __files__: Optional[list] = None,
        __task__: Optional[str] = None,
        __task_body__: Optional[str] = None,
        __session_id__: Optional[str] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ) -> Union[str, AsyncGenerator]:
        request_start_ts = time.monotonic()
        # --- PROBE LOG ---
        if __event_call__:
            await self._emit_debug_log(
                f"🔔 Pipe initialized. User: {__user__.get('name') if __user__ else 'Unknown'}",
                __event_call__,
                debug_enabled=True,
            )
        # -----------------

        # 1. Determine user role and settings
        user_data = (
            __user__[0] if isinstance(__user__, (list, tuple)) else (__user__ or {})
        )
        is_admin = user_data.get("role") == "admin"

        self._record_user_chat_mapping(user_data.get("id"), __chat_id__)

        # Robustly parse User Valves
        user_valves = self._get_user_valves(__user__)

        # --- DEBUG LOGGING ---
        if self.valves.DEBUG:
            logger.info(
                f"[Copilot] Request received. Model: {body.get('model')}, Stream: {body.get('stream', False)}"
            )
            logger.info(
                f"[Copilot] User Context: {bool(__user__)}, Event Call: {bool(__event_call__)}"
            )
        # ---------------------

        user_id = user_data.get("id") or user_data.get("user_id") or "default_user"

        effective_debug = self.valves.DEBUG or user_valves.DEBUG
        effective_token = user_valves.GH_TOKEN or self.valves.GH_TOKEN
        token = effective_token  # For compatibility with _get_client(token)

        # Get Chat ID using improved helper
        chat_ctx = self._get_chat_context(
            body, __metadata__, __event_call__, debug_enabled=effective_debug
        )
        chat_id = chat_ctx.get("chat_id") or "default"

        # Initialize Adaptive Interactive Controls Table pre-emptively
        if chat_id and chat_id != "default":
            self._initialize_interactive_controls_table(chat_id)

        # Determine effective MCP settings
        effective_mcp = user_valves.ENABLE_MCP_SERVER
        effective_openwebui_skills = user_valves.ENABLE_OPENWEBUI_SKILLS
        effective_disabled_skills = self._parse_csv_items(
            user_valves.DISABLED_SKILLS or self.valves.DISABLED_SKILLS
        )

        # Resolve effective session mode (global, applies to ALL sessions).
        # SESSION_MODE: user override > global > "autopilot".
        effective_session_mode = (
            (user_valves.SESSION_MODE or "").strip()
            or (self.valves.SESSION_MODE or "").strip()
            or "autopilot"
        )

        # P4: Chat tool_ids whitelist — extract once, reuse for both OpenAPI and MCP
        chat_tool_ids = self._normalize_chat_tool_ids(
            __metadata__.get("tool_ids") if isinstance(__metadata__, dict) else None
        )

        # Agent Team is resolved later, after custom_tools and mcp_servers are available
        agent_team_agents: Optional[list] = None
        agent_team_leader: Optional[str] = None

        user_ctx = await self._get_user_context(__user__, __event_call__, __request__)
        user_lang = user_ctx["user_language"]

        # 2. Setup environment with effective settings
        self._setup_env(
            __event_call__,
            debug_enabled=effective_debug,
            token=effective_token,
            enable_mcp=effective_mcp,
        )

        cwd = self._get_workspace_dir(user_id=user_id, chat_id=chat_id)
        await self._emit_debug_log(
            f"{self._get_translation(user_lang, 'debug_agent_working_in', path=cwd)} (Admin: {is_admin}, MCP: {effective_mcp})",
            __event_call__,
            debug_enabled=effective_debug,
        )

        # Determine effective BYOK settings
        byok_api_key = user_valves.BYOK_API_KEY or self.valves.BYOK_API_KEY
        byok_bearer_token = (
            user_valves.BYOK_BEARER_TOKEN or self.valves.BYOK_BEARER_TOKEN
        )
        byok_base_url = user_valves.BYOK_BASE_URL or self.valves.BYOK_BASE_URL
        byok_active = bool(byok_base_url and (byok_api_key or byok_bearer_token))

        # Check that either GH_TOKEN or BYOK is configured
        gh_token = user_valves.GH_TOKEN or self.valves.GH_TOKEN
        if not gh_token and not byok_active:
            return "Error: Please configure GH_TOKEN or BYOK settings in Valves."

        # Parse user selected model
        request_model = body.get("model", "")
        real_model_id = request_model
        code_interpreter_enabled = self._is_code_interpreter_feature_enabled(
            body, __metadata__
        )

        def _container_get(container: Any, key: str, default: Any = None) -> Any:
            if isinstance(container, dict):
                return container.get(key, default)
            if container is None:
                return default

            value = getattr(container, key, default)
            if value is default and hasattr(container, "model_dump"):
                try:
                    dumped = container.model_dump()
                    if isinstance(dumped, dict):
                        return dumped.get(key, default)
                except Exception:
                    return default
            return value

        # Determine effective reasoning effort
        effective_reasoning_effort = (
            user_valves.REASONING_EFFORT
            if user_valves.REASONING_EFFORT
            else self.valves.REASONING_EFFORT
        )

        # Apply SHOW_THINKING user setting (prefer user override when provided)
        show_thinking = (
            user_valves.SHOW_THINKING
            if user_valves.SHOW_THINKING is not None
            else self.valves.SHOW_THINKING
        )

        # 1. Determine the actual model ID to use
        # Priority: __metadata__.base_model_id (for custom models/characters) > request_model
        resolved_id = request_model
        model_source_type = "selected"

        base_model_id = _container_get(__metadata__, "base_model_id", "")
        if isinstance(base_model_id, str) and base_model_id:
            resolved_id = base_model_id
            model_source_type = "base"

        # 2. Strip prefixes to get the clean model ID (e.g. 'gpt-4o')
        real_model_id = self._strip_model_prefix(resolved_id)

        # 3. Enforce Multiplier Constraint (Safety Check)
        global_max = self.valves.MAX_MULTIPLIER
        user_max = user_valves.MAX_MULTIPLIER
        if user_max is not None:
            eff_max = min(float(user_max), float(global_max))
        else:
            eff_max = float(global_max)

        # Try to find model info. If missing, force refresh cache.
        m_info = next(
            (m for m in (self._model_cache or []) if m.get("raw_id") == real_model_id),
            None,
        )
        if not m_info:
            logger.info(
                f"[Pipe Impl] Model info missing for {real_model_id}, refreshing cache..."
            )
            await self.pipes(__user__)
            m_info = next(
                (
                    m
                    for m in (self._model_cache or [])
                    if m.get("raw_id") == real_model_id
                ),
                None,
            )

        # --- DEBUG MULTIPLIER ---
        if m_info:
            logger.info(
                f"[Pipe Impl] Model Info: ID={real_model_id}, Source={m_info.get('source')}, Mult={m_info.get('multiplier')}, EffMax={eff_max}"
            )
        else:
            logger.warning(
                f"[Pipe Impl] Model Info STILL NOT FOUND for ID: {real_model_id}. Treating as multiplier=1.0"
            )
        # ------------------------

        # Check multiplier (If model not found, assume Copilot source and multiplier 1.0 for safety)
        is_copilot_source = m_info.get("source") == "copilot" if m_info else True
        current_mult = float(m_info.get("multiplier", 1.0)) if m_info else 1.0

        if is_copilot_source:
            epsilon = 0.0001
            if current_mult > (eff_max + epsilon):
                err_msg = f"Error: Model '{real_model_id}' (multiplier {current_mult}x) exceeds your allowed maximum of {eff_max}x."
                await self._emit_debug_log(err_msg, __event_call__, debug_enabled=True)
                return err_msg

        # 4. Log the resolution result
        if real_model_id != request_model:
            log_msg = (
                f"Using {model_source_type} model: {real_model_id} "
                f"(Cleaned from '{resolved_id}')"
            )
            await self._emit_debug_log(
                log_msg,
                __event_call__,
                debug_enabled=effective_debug,
            )

        messages = body.get("messages", [])
        if not messages:
            return "No messages."

        if effective_debug:
            try:
                msg_samples = []
                for msg in messages[-3:]:
                    role = msg.get("role", "") if isinstance(msg, dict) else ""
                    content = (
                        self._extract_text_from_content(msg.get("content", ""))
                        if isinstance(msg, dict)
                        else str(msg)
                    )
                    msg_samples.append(
                        {
                            "role": role,
                            "len": len(content),
                            "preview": content[:120],
                        }
                    )

                await self._emit_debug_log(
                    f"[Pipe Input] model={request_model}, real_model={real_model_id}, "
                    f"messages_count={len(messages)}, body_stream={body.get('stream', False)}, "
                    f"last3={msg_samples}",
                    __event_call__,
                    debug_enabled=effective_debug,
                )
            except Exception as e:
                await self._emit_debug_log(
                    f"[Pipe Input] diagnostics failed: {e}",
                    __event_call__,
                    debug_enabled=effective_debug,
                )

        # Extract system prompt from multiple sources
        system_prompt_content, system_prompt_source = await self._extract_system_prompt(
            body,
            messages,
            request_model,
            real_model_id,
            code_interpreter_enabled=code_interpreter_enabled,
            __event_call__=__event_call__,
            debug_enabled=effective_debug,
        )

        if system_prompt_content:
            preview = system_prompt_content[:60].replace("\n", " ")
            await self._emit_debug_log(
                f"Resolved system prompt source: {system_prompt_source} (length: {len(system_prompt_content) if system_prompt_content else 0})",
                __event_call__,
                debug_enabled=effective_debug,
            )

        live_todo_stats = self._read_todo_status_from_session_db(chat_id or "")
        if live_todo_stats:
            total_tasks = int(live_todo_stats.get("total", 0))
            done_tasks = int(live_todo_stats.get("done", 0))

            # Only show the widget if there are tasks and not ALL of them are done.
            if total_tasks > 0 and done_tasks < total_tasks:
                await self._emit_todo_widget(
                    chat_id=chat_id or "",
                    lang=user_lang,
                    emitter=__event_emitter__,
                    stats=live_todo_stats,
                    force=True,
                )

        is_streaming = body.get("stream", False)
        await self._emit_debug_log(
            f"Streaming request: {is_streaming}",
            __event_call__,
            debug_enabled=effective_debug,
        )

        # Retrieve files (support 'copilot_files' from filter override)
        files = body.get("copilot_files") or body.get("files")

        last_text, attachments = self._process_attachments(
            messages,
            cwd=cwd,
            files=files,
            __event_call__=__event_call__,
            debug_enabled=effective_debug,
        )

        if effective_debug:
            try:
                attachment_summary = []
                for item in attachments[:5]:
                    if isinstance(item, dict):
                        attachment_summary.append(
                            {
                                "name": item.get("filename") or item.get("name") or "",
                                "mime": item.get("mime_type")
                                or item.get("mimeType")
                                or "",
                                "has_data": bool(
                                    item.get("data") or item.get("content")
                                ),
                            }
                        )
                    else:
                        attachment_summary.append({"type": type(item).__name__})

                await self._emit_debug_log(
                    f"[Pipe Input] processed_prompt_len={len(last_text or '')}, "
                    f"prompt_preview={repr((last_text or '')[:200])}, "
                    f"attachments_count={len(attachments)}, attachments={attachment_summary}",
                    __event_call__,
                    debug_enabled=effective_debug,
                )
            except Exception as e:
                await self._emit_debug_log(
                    f"[Pipe Input] prompt diagnostics failed: {e}",
                    __event_call__,
                    debug_enabled=effective_debug,
                )

        # Skill-manager intent diagnostics/routing hint (without disabling other skills).
        manage_skills_intent = self._is_manage_skills_intent(last_text)
        if manage_skills_intent:
            try:
                await self._emit_debug_log(
                    "[Skills] Skill management intent detected. `manage_skills` tool routing enabled.",
                    __event_call__,
                    debug_enabled=effective_debug,
                )
            except Exception as e:
                await self._emit_debug_log(
                    f"[Skills] Skill-manager intent diagnostics failed: {e}",
                    __event_call__,
                    debug_enabled=effective_debug,
                )

        # Determine prompt strategy
        # If we have a chat_id, we try to resume session.
        # If resumed, we assume the session has history, so we only send the last message.
        # If new session, we send full (accumulated) messages.

        # 1. Determine model capabilities and BYOK status
        import re

        m_info = next(
            (
                m
                for m in (self._model_cache or [])
                if m.get("raw_id") == real_model_id
                or m.get("id") == real_model_id
                or m.get("id") == f"{self.id}-{real_model_id}"
            ),
            None,
        )

        is_reasoning = (
            m_info.get("meta", {}).get("capabilities", {}).get("reasoning", False)
            if m_info
            else False
        )

        # Detection priority for BYOK
        # 1. Check metadata.model.name for multiplier (Standard Copilot format)
        body_metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
        body_model = _container_get(body_metadata, "model", {})
        model_display_name = _container_get(body_model, "name", "")

        if not model_display_name:
            metadata_model = _container_get(__metadata__, "model", {})
            model_display_name = _container_get(metadata_model, "name", "")

        if not isinstance(model_display_name, str):
            model_display_name = str(model_display_name or "")
        has_multiplier = bool(
            re.search(r"[\(（]\d+(?:\.\d+)?x[\)）]", model_display_name)
        )

        if m_info and "source" in m_info:
            is_byok_model = m_info["source"] == "byok"
        else:
            is_byok_model = not has_multiplier and byok_active

        # Mode Selection Info
        await self._emit_debug_log(
            f"Mode: {'BYOK' if is_byok_model else 'Standard'}, Reasoning: {is_reasoning}, Admin: {is_admin}",
            __event_call__,
            debug_enabled=effective_debug,
        )

        # Shared state for delayed HTML embeds (Premium Experience)
        pending_embeds = []

        # ==================== REVERT TO 0.9.1 EPHEMERAL CLIENT ====================
        t_before_client = time.monotonic()
        client_config = self._build_client_config(
            user_id=user_id, chat_id=chat_id, token=effective_token
        )
        client = CopilotClient(client_config)
        should_stop_client = True
        try:
            await client.start()
            t_after_client = time.monotonic()

            # Initialize custom tools (Handles caching internally)
            t_before_tools = time.monotonic()
            custom_tools = await self._initialize_custom_tools(
                body=body,
                __user__=__user__,
                user_lang=user_lang,
                __event_emitter__=__event_emitter__,
                __event_call__=__event_call__,
                __request__=__request__,
                __metadata__=__metadata__,
                pending_embeds=pending_embeds,
                __messages__=__messages__,
                __files__=__files__,
                __task__=__task__,
                __task_body__=__task_body__,
                __session_id__=__session_id__,
                __chat_id__=__chat_id__,
                __message_id__=__message_id__,
            )
            t_after_tools = time.monotonic()

            if custom_tools:
                await self._emit_debug_log(
                    f"Enabled {len(custom_tools)} tools (Custom/Built-in)",
                    __event_call__,
                )

            # Check MCP Servers
            t_before_mcp = time.monotonic()
            mcp_servers = await self._parse_mcp_servers(
                __event_call__, enable_mcp=effective_mcp, chat_tool_ids=chat_tool_ids
            )
            t_after_mcp = time.monotonic()

            # Emit Profiling Log to Frontend
            self._emit_debug_log_sync(
                f"⏱️ [Profiling] Client.start: {t_after_client - t_before_client:.3f}s | "
                f"Tools Init: {t_after_tools - t_before_tools:.3f}s | "
                f"MCP Parse: {t_after_mcp - t_before_mcp:.3f}s",
                __event_call__,
                debug_enabled=True,
            )

            mcp_server_names = list(mcp_servers.keys()) if mcp_servers else []
            if mcp_server_names:
                await self._emit_debug_log(
                    f"🔌 MCP Servers Configured: {mcp_server_names}",
                    __event_call__,
                )
            else:
                await self._emit_debug_log(
                    "ℹ️ No MCP tool servers found in OpenWebUI Connections.",
                    __event_call__,
                )

            # Resolve Agent Team now that custom_tools and mcp_servers are available.
            # Each agent inherits the same tools/MCP as the pipe's default behavior,
            # fully respecting ENABLE_OPENWEBUI_TOOLS, ENABLE_MCP_SERVER, etc.
            agent_team_agents, agent_team_leader = await self._resolve_agent_team(
                user_valves,
                user_id=user_id,
                session_tools=custom_tools,
                session_mcp_servers=mcp_servers,
            )

            # Create or Resume Session
            session = None

            # Build BYOK Provider Config
            provider_config = None

            if is_byok_model:
                byok_type = (user_valves.BYOK_TYPE or self.valves.BYOK_TYPE).lower()
                if byok_type not in ["openai", "anthropic"]:
                    byok_type = "openai"

                byok_wire_api = user_valves.BYOK_WIRE_API or self.valves.BYOK_WIRE_API

                provider_config = {
                    "type": byok_type,
                    "wire_api": byok_wire_api,
                    "base_url": byok_base_url,
                }
                if byok_api_key:
                    provider_config["api_key"] = byok_api_key
                if byok_bearer_token:
                    provider_config["bearer_token"] = byok_bearer_token
                pass

            if chat_id:
                try:
                    resolved_cwd = self._get_workspace_dir(
                        user_id=user_id, chat_id=chat_id
                    )
                    # Prepare resume config (Requires github-copilot-sdk >= 0.1.23)
                    resume_params = {
                        "model": real_model_id,
                        "streaming": is_streaming,
                        "tools": custom_tools,
                        "config_dir": self._get_copilot_config_dir(),
                    }

                    permission_request_handler = getattr(
                        PermissionHandler, "approve_all", None
                    )
                    if callable(permission_request_handler):
                        resume_params["on_permission_request"] = (
                            permission_request_handler
                        )

                    if is_reasoning and effective_reasoning_effort:
                        # Re-use mapping logic or just pass it through
                        resume_params["reasoning_effort"] = effective_reasoning_effort

                    # Use already parsed mcp_servers to avoid redundant heavy IO
                    if mcp_servers:
                        resume_params["mcp_servers"] = mcp_servers

                    # Always None: let CLI built-ins (bash etc.) remain available.
                    resume_params["available_tools"] = None

                    t_skills_start = time.monotonic()
                    resume_params.update(
                        self._resolve_session_skill_config(
                            resolved_cwd=resolved_cwd,
                            user_id=user_id,
                            enable_openwebui_skills=effective_openwebui_skills,
                            disabled_skills=effective_disabled_skills,
                        )
                    )
                    t_skills_elapsed = time.monotonic() - t_skills_start

                    # Only run heavy IO skill debugging if debug is actually on
                    if effective_debug:
                        try:
                            skill_dirs_dbg = (
                                resume_params.get("skill_directories") or []
                            )
                            for sd in skill_dirs_dbg:
                                path = Path(sd)
                                skill_md_count = sum(
                                    1 for p in path.glob("*/SKILL.md") if p.is_file()
                                )
                                logger.info(
                                    f"[Copilot] resume skill_dir check: {sd} skill_md_count={skill_md_count}"
                                )
                        except:
                            pass

                    # Always inject the latest system prompt in 'replace' mode
                    # This handles both custom models and user-defined system messages
                    final_system_msg = self._build_final_system_message(
                        system_prompt_content=system_prompt_content,
                        is_admin=is_admin,
                        user_id=user_id,
                        chat_id=chat_id,
                        manage_skills_intent=manage_skills_intent,
                        custom_agents=agent_team_agents,
                        agent_leader=agent_team_leader,
                        session_mode=effective_session_mode,
                    )

                    resume_params["system_message"] = {
                        "mode": "replace",
                        "content": final_system_msg,
                    }

                    preview = final_system_msg[:100].replace("\n", " ")
                    await self._emit_debug_log(
                        f"Resuming session {chat_id}. Injecting System Prompt ({len(final_system_msg)} chars). Mode: REPLACE. Content Preview: {preview}...",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )

                    # Update provider if needed (BYOK support during resume)
                    if provider_config:
                        resume_params["provider"] = provider_config
                        await self._emit_debug_log(
                            f"BYOK provider config included: type={provider_config.get('type')}, base_url={provider_config.get('base_url')}",
                            __event_call__,
                            debug_enabled=effective_debug,
                        )

                    # Inject Agent Team if configured
                    if agent_team_agents:
                        resume_params["custom_agents"] = agent_team_agents
                    if agent_team_leader:
                        resume_params["agent"] = agent_team_leader

                    # Debug: Log the full resume_params structure
                    await self._emit_debug_log(
                        f"resume_params keys: {list(resume_params.keys())}. system_message mode: {resume_params.get('system_message', {}).get('mode')}",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )

                    t_before_rpc = time.monotonic()
                    session = await client.resume_session(
                        session_id=chat_id, **resume_params
                    )
                    t_after_rpc = time.monotonic()

                    self._emit_debug_log_sync(
                        f"⏱️ [Profiling] Skills Resolve: {t_skills_elapsed:.3f}s | RPC resume_session: {t_after_rpc - t_before_rpc:.3f}s",
                        __event_call__,
                        debug_enabled=True,
                    )

                    await self._emit_debug_log(
                        f"Successfully resumed session {chat_id} with model {real_model_id}",
                        __event_call__,
                    )

                    # Set SDK agent mode (global session parameter, applies to all sessions).
                    # The system prompt already carries the active-mode directive, so this
                    # is an additional SDK-level hint.  A 5-second timeout prevents hangs.
                    try:
                        mode_enum = Mode(effective_session_mode)
                        await asyncio.wait_for(
                            session.rpc.mode.set(SessionModeSetParams(mode=mode_enum)),
                            timeout=5.0,
                        )
                        logger.info(
                            f"[Session] Mode set to '{effective_session_mode}' for resumed session {chat_id}."
                        )
                        await self._emit_debug_log(
                            f"[Session] SDK mode set to '{effective_session_mode}' (resumed session).",
                            __event_call__,
                            debug_enabled=effective_debug,
                        )
                    except Exception as e:
                        logger.warning(
                            f"[Session] Failed to set SDK mode '{effective_session_mode}': {e}"
                        )
                        await self._emit_debug_log(
                            f"[Session] ⚠️ SDK mode.set('{effective_session_mode}') failed (resumed): {e}. "
                            f"System-prompt mode directive is still active.",
                            __event_call__,
                            debug_enabled=effective_debug,
                        )

                    await self._abort_stale_resumed_turn_if_needed(
                        session,
                        __event_call__=__event_call__,
                        debug_enabled=effective_debug,
                    )
                except Exception as e:
                    await self._emit_debug_log(
                        f"Session {chat_id} not found or failed to resume ({str(e)}), creating new.",
                        __event_call__,
                    )

            if session is None:
                session_config = self._build_session_config(
                    chat_id,
                    real_model_id,
                    custom_tools,
                    system_prompt_content,
                    is_streaming,
                    provider_config=provider_config,
                    reasoning_effort=effective_reasoning_effort,
                    is_reas_model=is_reasoning,
                    is_admin=is_admin,
                    user_id=user_id,
                    enable_mcp=effective_mcp,
                    enable_openwebui_skills=effective_openwebui_skills,
                    disabled_skills=effective_disabled_skills,
                    manage_skills_intent=manage_skills_intent,
                    chat_tool_ids=chat_tool_ids,
                    __event_call__=__event_call__,
                    custom_agents=agent_team_agents,
                    agent_leader=agent_team_leader,
                    session_mode=effective_session_mode,
                )

                await self._emit_debug_log(
                    "Injecting system prompt into new session",
                    __event_call__,
                )

                t_before_rpc2 = time.monotonic()
                session = await client.create_session(**session_config)
                t_after_rpc2 = time.monotonic()

                self._emit_debug_log_sync(
                    f"⏱️ [Profiling] RPC create_session: {t_after_rpc2 - t_before_rpc2:.3f}s",
                    __event_call__,
                    debug_enabled=True,
                )

                model_type_label = "BYOK" if is_byok_model else "Copilot"
                await self._emit_debug_log(
                    f"New {model_type_label} session created. Selected: '{request_model}', Effective ID: '{real_model_id}'",
                    __event_call__,
                    debug_enabled=effective_debug,
                )

                # Set SDK agent mode (global session parameter, applies to all sessions).
                # The system prompt already carries the active-mode directive, so this
                # is an additional SDK-level hint.  A 5-second timeout prevents hangs.
                try:
                    mode_enum = Mode(effective_session_mode)
                    await asyncio.wait_for(
                        session.rpc.mode.set(SessionModeSetParams(mode=mode_enum)),
                        timeout=5.0,
                    )
                    logger.info(
                        f"[Session] Mode set to '{effective_session_mode}' for new session."
                    )
                    await self._emit_debug_log(
                        f"[Session] SDK mode set to '{effective_session_mode}' (new session).",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )
                except Exception as e:
                    logger.warning(
                        f"[Session] Failed to set SDK mode '{effective_session_mode}': {e}"
                    )
                    await self._emit_debug_log(
                        f"[Session] ⚠️ SDK mode.set('{effective_session_mode}') failed (new session): {e}. "
                        f"System-prompt mode directive is still active.",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )

                # Show workspace info for new sessions
                if self.valves.DEBUG:
                    if session.workspace_path:
                        await self._emit_debug_log(
                            f"Session workspace: {session.workspace_path}",
                            __event_call__,
                        )

            # Construct Prompt (session-based: send only latest user input)
            # SDK testing confirmed session.resume correctly applies system_message updates,
            # so we simply use the user's input as the prompt.
            prompt = last_text

            await self._emit_debug_log(
                f"Sending prompt ({len(prompt)} chars) to Agent...",
                __event_call__,
            )

            send_payload = {"prompt": prompt, "mode": "immediate"}
            if attachments:
                send_payload["attachments"] = attachments

            if effective_debug:
                try:
                    await self._emit_debug_log(
                        f"[Pipe Send] prompt_len={len(prompt or '')}, prompt_preview={repr((prompt or '')[:220])}, "
                        f"attachments_count={len(attachments) if attachments else 0}",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )
                except Exception as e:
                    await self._emit_debug_log(
                        f"[Pipe Send] payload diagnostics failed: {e}",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )

            # Note: temperature, top_p, max_tokens are not supported by the SDK's
            # session.send() method. These generation parameters would need to be
            # handled at a different level if the underlying provider supports them.

            if body.get("stream", False):
                init_msg = ""
                if effective_debug:
                    init_msg = f"> [Debug] {self._get_translation(user_lang, 'debug_agent_working_in', path=self._get_workspace_dir(user_id=user_id, chat_id=chat_id))}\n"
                    if mcp_server_names:
                        init_msg += f"> [Debug] {self._get_translation(user_lang, 'debug_mcp_servers', servers=', '.join(mcp_server_names))}\n"

                # Transfer client ownership to stream_response
                should_stop_client = False
                return self.stream_response(
                    client,
                    session,
                    send_payload,
                    chat_id=chat_id,
                    user_id=user_id,
                    init_message=init_msg,
                    __event_call__=__event_call__,
                    __event_emitter__=__event_emitter__,
                    reasoning_effort=(
                        effective_reasoning_effort
                        if (is_reasoning and not is_byok_model)
                        else "off"
                    ),
                    show_thinking=show_thinking,
                    debug_enabled=effective_debug,
                    user_lang=user_lang,
                    pending_embeds=pending_embeds,
                    request_start_ts=request_start_ts,
                )
            else:
                try:
                    response = await session.send_and_wait(
                        send_payload["prompt"],
                        attachments=send_payload.get("attachments"),
                        mode=send_payload.get("mode"),
                    )
                    _resp_content = response.data.content if response else None
                    return (
                        str(_resp_content)
                        if _resp_content is not None
                        else "Empty response."
                    )
                finally:
                    # Cleanup: destroy session if no chat_id (temporary session)
                    if not chat_id:
                        try:
                            await session.destroy()
                        except Exception as cleanup_error:
                            await self._emit_debug_log(
                                f"Session cleanup warning: {cleanup_error}",
                                __event_call__,
                            )
        except Exception as e:
            await self._emit_debug_log(
                f"Request Error: {e}", __event_call__, debug_enabled=effective_debug
            )
            return f"Error: {str(e)}"
        finally:
            # Cleanup client if not transferred to stream
            if should_stop_client:
                try:
                    await client.stop()
                except Exception as e:
                    await self._emit_debug_log(
                        f"Client cleanup warning: {e}",
                        __event_call__,
                        debug_enabled=effective_debug,
                    )

    async def stream_response(
        self,
        client,
        session,
        send_payload,
        chat_id: str,
        user_id: Optional[str] = None,
        init_message: str = "",
        __event_call__=None,
        __event_emitter__=None,
        reasoning_effort: str = "",
        show_thinking: bool = True,
        debug_enabled: bool = False,
        user_lang: str = "en-US",
        pending_embeds: Optional[List[dict]] = None,
        request_start_ts: float = 0.0,
    ) -> AsyncGenerator:
        """
        Stream response from Copilot SDK, handling various event types.
        Follows official SDK patterns for event handling and streaming.
        """
        queue = asyncio.Queue()
        done = asyncio.Event()
        SENTINEL = object()
        stream_start_ts = time.monotonic()
        # Use local state to handle concurrency and tracking
        state = {
            "thinking_started": False,
            "content_sent": False,
            "last_status_desc": None,
            "idle_reached": False,
            "session_finalized": False,
            "turn_started": False,
            "turn_ended": False,
            "turn_started_ts": None,
            "turn_end_ts": None,
            "last_event_ts": stream_start_ts,
            "last_error_msg": "",
            "embeds_flushed": False,
            "reasoning_sent": False,
            "final_status_desc": self._get_translation(
                user_lang, "status_task_completed"
            ),
        }
        has_content = False  # Track if any content has been yielded
        active_tools = {}  # Map tool_call_id to tool_name
        running_tool_calls = set()
        skill_invoked_in_turn = False
        last_wait_status_ts = 0.0
        wait_status_interval = 15.0
        queue_poll_interval = max(1.0, min(float(self.valves.TIMEOUT), 5.0))

        IDLE_SENTINEL = object()
        ERROR_SENTINEL = object()
        SENTINEL = object()

        def get_event_type(event) -> str:
            """Extract event type as string, handling both enum and string types."""
            if hasattr(event, "type"):
                event_type = event.type
                # Handle SessionEventType enum
                if hasattr(event_type, "value"):
                    return event_type.value
                return str(event_type)
            return "unknown"

        def safe_get_data_attr(event, attr: str, default=None):
            """
            Safely extract attribute from event.data.
            Handles both dict access and object attribute access.
            """
            if not hasattr(event, "data") or event.data is None:
                return default

            data = event.data

            # Try as dict first
            if isinstance(data, dict):
                return data.get(attr, default)

            # Try as object attribute
            return getattr(data, attr, default)

        async def _flush_pending_embeds(flush_source: str) -> List[str]:
            if state.get("embeds_flushed"):
                return []
            if not pending_embeds:
                return []

            state["embeds_flushed"] = True
            artifacts_to_yield: List[str] = []
            embeds_to_process = list(pending_embeds)
            pending_embeds.clear()

            self._emit_debug_log_sync(
                f"Flushing {len(embeds_to_process)} pending embed(s) via {flush_source}",
                __event_call__,
                debug_enabled=debug_enabled,
            )

            for embed in embeds_to_process:
                if not isinstance(embed, dict):
                    continue

                embed_type = embed.get("type")
                embed_filename = embed.get("filename", "")
                embed_content = embed.get("content", "")
                if embed_type not in {"richui", "artifacts"}:
                    continue

                if __event_emitter__:
                    try:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": self._get_translation(
                                        user_lang,
                                        "status_publishing_file",
                                        filename=embed_filename,
                                    ),
                                    "done": True,
                                },
                            }
                        )
                        await __event_emitter__(
                            {
                                "type": "notification",
                                "data": {
                                    "type": "success",
                                    "content": self._get_translation(
                                        user_lang, "publish_success"
                                    ),
                                },
                            }
                        )
                    except Exception as emit_error:
                        self._emit_debug_log_sync(
                            f"Embed status/notification emission failed via {flush_source}: {emit_error}",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )

                if embed_type == "richui":
                    if __event_emitter__:
                        try:
                            await __event_emitter__(
                                {
                                    "type": "embeds",
                                    "data": {"embeds": [embed_content]},
                                }
                            )
                        except Exception as emit_error:
                            self._emit_debug_log_sync(
                                f"RichUI embed emission failed via {flush_source}: {emit_error}",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                elif embed_content:
                    artifacts_to_yield.append(embed_content)

            return artifacts_to_yield

        def handler(event):
            """
            Event handler following official SDK patterns.
            Processes streaming deltas, reasoning, tool events, and session state.
            """
            event_type = get_event_type(event)
            state["last_event_ts"] = time.monotonic()

            # --- Status Emission Helper ---
            async def _emit_status_helper(description: str, is_done: bool = False):
                if not __event_emitter__:
                    return
                try:
                    allowed_final_desc = state.get(
                        "final_status_desc"
                    ) or self._get_translation(user_lang, "status_task_completed")
                    # BLOCKING LOCK: If we are in the safe-haven of turn completion,
                    # discard any stray async status updates from earlier pending tasks.
                    if (
                        state.get("session_finalized")
                        and description != allowed_final_desc
                    ):
                        return

                    # Optimized emission: we try to minimize context switches

                    # 1. Close the OLD one if it's different
                    if (
                        state.get("last_status_desc")
                        and state["last_status_desc"] != description
                    ):
                        try:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": state["last_status_desc"],
                                        "done": True,
                                    },
                                }
                            )
                        except:
                            pass

                    # CRITICAL: Re-check session_finalized after the inner await above.
                    # The coroutine may have been suspended at await point #1 while the
                    # main loop set session_finalized=True and emitted the final done=True.
                    # Without this re-check, the done=False emission below would fire
                    # AFTER all finalization, becoming the last statusHistory entry
                    # and leaving a permanent shimmer on the UI.
                    if (
                        state.get("session_finalized")
                        and description != allowed_final_desc
                    ):
                        return

                    # 2. Emit the requested status
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": description, "done": is_done},
                        }
                    )

                    # 3. Track the active status
                    if not is_done:
                        state["last_status_desc"] = description
                    elif state.get("last_status_desc") == description:
                        state["last_status_desc"] = None
                except:
                    pass

            def emit_status(desc: str, is_done: bool = False):
                """Sync wrapper to schedule the async status emission."""
                if __event_emitter__ and desc:
                    # We use a task because this is often called from sync tool handlers
                    asyncio.create_task(_emit_status_helper(desc, is_done))

            # === Turn Management Events ===
            if event_type == "assistant.turn_start":
                state["turn_started"] = True
                state["turn_ended"] = False
                state["turn_started_ts"] = state["last_event_ts"]
                state["turn_end_ts"] = None

                # Calculate and log request latency (TTFT)
                if request_start_ts > 0:
                    elapsed = state["last_event_ts"] - request_start_ts
                    net_elapsed = ""
                    if "send_start_ts" in state:
                        net_roundtrip = state["last_event_ts"] - state["send_start_ts"]
                        net_elapsed = f" | Cloud Network Trip: {net_roundtrip:.3f}s"
                    self._emit_debug_log_sync(
                        f"⏱️ [Copilot] Total TTFT: {elapsed:.3f}s{net_elapsed}",
                        __event_call__,
                        debug_enabled=True,
                    )

                state["message_stream_tail"] = ""
                state["reasoning_sent"] = False
                state["reasoning_stream_tail"] = ""
                state["content_sent"] = False
                self._emit_debug_log_sync(
                    "Assistant Turn Started",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

                initial_status = self._get_translation(
                    user_lang, "status_assistant_processing"
                )
                # Route through emit_status → _emit_status_helper so the session_finalized
                # guard is respected. Direct create_task(__event_emitter__) bypasses the guard
                # and can fire AFTER finalization, leaving a stale done=False spinner.
                emit_status(initial_status)

            elif event_type == "assistant.intent":
                intent = safe_get_data_attr(event, "intent")
                if intent:
                    localized_intent = self._localize_intent_text(user_lang, intent)
                    self._emit_debug_log_sync(
                        f"Assistant Intent: {intent}",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )
                    emit_status(
                        self._get_translation(
                            user_lang,
                            "status_intent",
                            intent=localized_intent,
                        )
                    )

            # === Message Delta Events (Primary streaming content) ===
            elif event_type == "assistant.message_delta":
                # Close any pending thinking status when content starts
                if not state["content_sent"]:
                    state["content_sent"] = True
                    if state.get("last_status_desc"):
                        emit_status(state["last_status_desc"], is_done=True)

                # Official: event.data.delta_content for Python SDK
                delta = safe_get_data_attr(
                    event, "delta_content"
                ) or safe_get_data_attr(event, "deltaContent")
                if delta:
                    state["content_sent"] = True
                    if state["thinking_started"]:
                        queue.put_nowait("\n</think>\n")
                        state["thinking_started"] = False

                    queue.put_nowait(delta)

            # === Complete Message Event (Non-streaming response) ===
            elif event_type == "assistant.message":
                if state["content_sent"]:
                    return
                content = safe_get_data_attr(event, "content") or safe_get_data_attr(
                    event, "message"
                )
                if content:
                    state["content_sent"] = True
                    if state.get("last_status_desc"):
                        emit_status(state["last_status_desc"], is_done=True)
                    if state["thinking_started"]:
                        queue.put_nowait("\n</think>\n")
                        state["thinking_started"] = False
                    queue.put_nowait(content)

            # === Reasoning Delta Events (Chain-of-thought streaming) ===
            elif event_type == "assistant.reasoning_delta":
                delta = safe_get_data_attr(
                    event, "delta_content"
                ) or safe_get_data_attr(event, "deltaContent")
                if delta:
                    # Suppress late-arriving reasoning if content already started
                    if state["content_sent"]:
                        return

                    state["reasoning_sent"] = True
                    # Use UserValves or Global Valve for thinking visibility
                    if not state["thinking_started"] and show_thinking:
                        queue.put_nowait("<think>\n")
                        state["thinking_started"] = True
                    if state["thinking_started"]:
                        queue.put_nowait(delta)

            # === Complete Reasoning Event (Non-streaming reasoning) ===
            elif event_type == "assistant.reasoning":
                # 按同样架构要求，直接摒弃 reasoning 全包复读。
                pass

            # === Skill Invocation Events ===
            elif event_type == "skill.invoked":
                nonlocal skill_invoked_in_turn
                skill_invoked_in_turn = True
                skill_name = (
                    safe_get_data_attr(event, "name")
                    or safe_get_data_attr(event, "skill_name")
                    or safe_get_data_attr(event, "skill")
                    or safe_get_data_attr(event, "id")
                    or "unknown-skill"
                )
                skill_status_text = self._get_translation(
                    user_lang, "status_skill_invoked", skill=skill_name
                )

                self._emit_debug_log_sync(
                    f"Skill Invoked: {skill_name}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

                # Also send status bubble when possible.
                emit_status(skill_status_text, is_done=True)

            # === Tool Execution Events ===
            elif event_type == "tool.execution_start":
                tool_name = (
                    safe_get_data_attr(event, "name")
                    or safe_get_data_attr(event, "tool_name")
                    or "Unknown Tool"
                )
                tool_call_id = safe_get_data_attr(event, "tool_call_id", "")

                # Get tool arguments
                tool_args = {}
                try:
                    args_obj = safe_get_data_attr(event, "arguments")
                    if isinstance(args_obj, dict):
                        tool_args = args_obj
                    elif isinstance(args_obj, str):
                        tool_args = json.loads(args_obj)
                except:
                    pass

                # Try to detect filename in arguments for better status (e.g., create_file, bash)
                tool_status_text = self._get_translation(
                    user_lang,
                    "status_tool_using",
                    name=tool_name,
                )

                # Enhanced filenames detection for common tools
                filename_hint = (
                    tool_args.get("filename")
                    or tool_args.get("file")
                    or tool_args.get("path")
                )
                if not filename_hint and tool_name == "bash":
                    command = tool_args.get("command", "")
                    # Detect output file from common bash redirect patterns (>>, >, tee, cat >)
                    # Use alternation group (not char class) to avoid matching '|' pipe symbols
                    match = re.search(r"(?:>>|>|tee|cat\s*>)\s*([^\s;&|<>]+)", command)
                    if match:
                        candidate = match.group(1).strip().split("/")[-1]
                        # Only use as hint if it looks like a filename (has extension or is not a flag)
                        if (
                            candidate
                            and not candidate.startswith("-")
                            and "." in candidate
                        ):
                            filename_hint = candidate

                if filename_hint:
                    tool_status_text += f" ({filename_hint})"

                # --- High-level User Experience Enhancements ---
                # Better status for reporting intent (common in Plan/Autopilot mode)
                if tool_name == "report_intent":
                    intent = tool_args.get("intent", "")
                    if intent:
                        localized_intent = self._localize_intent_text(user_lang, intent)
                        tool_status_text = self._get_translation(
                            user_lang, "status_intent", intent=localized_intent
                        )
                # Better status for task completion with summary
                elif tool_name == "task_complete":
                    summary = tool_args.get("summary", "")
                    if summary:
                        tool_status_text = (
                            self._get_translation(user_lang, "status_task_completed")
                            + f": {summary}"
                        )
                # ---------------------------------------------

                if tool_call_id:
                    active_tools[tool_call_id] = {
                        "name": tool_name,
                        "arguments": tool_args,
                        "status_text": tool_status_text if __event_emitter__ else None,
                    }
                    running_tool_calls.add(tool_call_id)

                    # Use the richer tool status text (which contains filenames/arguments context)
                    # and ensure it's only printed to the stream ONCE per unique tool run.
                    # queue.put_nowait(f"\n> 🧩 **{tool_status_text}**\n")

                # Close thinking tag if open before showing tool
                if state["thinking_started"]:
                    queue.put_nowait("\n</think>\n")
                    state["thinking_started"] = False

                # Show status bubble for tool usage
                emit_status(tool_status_text)

                self._emit_debug_log_sync(
                    f"Tool Start: {tool_name}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            elif event_type == "tool.execution_complete":
                tool_call_id = safe_get_data_attr(event, "tool_call_id", "")
                if tool_call_id:
                    running_tool_calls.discard(tool_call_id)
                tool_info = active_tools.get(tool_call_id)

                tool_name = "tool"
                status_text = None
                if isinstance(tool_info, dict):
                    tool_name = tool_info.get("name", "tool")
                    status_text = tool_info.get("status_text")
                    tool_args = tool_info.get("arguments", {})
                elif isinstance(tool_info, str):
                    tool_name = tool_info
                    tool_args = {}
                else:
                    tool_args = {}

                # Mark tool status as done if it was the last one
                if status_text:
                    emit_status(status_text, is_done=True)

                # Try to get result content
                result_content = ""
                result_type = "success"
                result_obj: Any = None
                try:
                    result_obj = safe_get_data_attr(event, "result")
                    if hasattr(result_obj, "content"):
                        result_content = getattr(result_obj, "content", "")
                    elif isinstance(result_obj, dict):
                        result_content = result_obj.get("content", "")
                        result_type = result_obj.get("result_type", "success")
                        if not result_content:
                            # Try to serialize the entire dict if no content field
                            result_content = json.dumps(
                                result_obj, indent=2, ensure_ascii=False
                            )
                    elif isinstance(result_obj, str):
                        result_content = result_obj
                    result_type = (
                        safe_get_data_attr(event, "type", "success") or "success"
                    )
                except Exception as e:
                    self._emit_debug_log_sync(
                        f"Error extracting result: {e}",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )
                    result_type = "failure"
                    result_content = f"Error: {str(e)}"

                # User-friendly completion status (success/failure) after the tool finishes.
                # We emit this as done=True so it cleanly replaces transient "Using tool..." states.
                if str(result_type).lower() in {"success", "ok", "completed"}:
                    emit_status(
                        self._get_translation(
                            user_lang, "status_tool_done", name=tool_name
                        ),
                        is_done=True,
                    )
                else:
                    emit_status(
                        self._get_translation(
                            user_lang, "status_tool_failed", name=tool_name
                        ),
                        is_done=True,
                    )

                # --- TODO Sync Logic (File only) ---
                if tool_name == "update_todo" and result_type == "success":
                    try:
                        # Extract todo content with fallback strategy
                        todo_text = ""

                        # 1. Try detailedContent (Best source)
                        if isinstance(result_obj, dict) and result_obj.get(
                            "detailedContent"
                        ):
                            todo_text = result_obj["detailedContent"]
                        # 2. Try content (Second best)
                        elif isinstance(result_obj, dict) and result_obj.get("content"):
                            todo_text = result_obj["content"]
                        elif hasattr(result_obj, "content"):
                            todo_text = getattr(result_obj, "content", "")

                        # 3. Fallback: If content is just a status message, try to recover from arguments
                        if (
                            not todo_text or len(todo_text) < 50
                        ):  # Threshold to detect "TODO list updated"
                            if tool_call_id in active_tools:
                                args = active_tools[tool_call_id].get("arguments", {})
                                if isinstance(args, dict) and "todos" in args:
                                    todo_text = args["todos"]
                                    self._emit_debug_log_sync(
                                        f"Recovered TODO from arguments (Result was too short)",
                                        __event_call__,
                                        debug_enabled=debug_enabled,
                                    )

                        if todo_text:
                            # Use the explicit chat_id passed to stream_response
                            target_chat_id = chat_id or "default"

                            # 1. Sync to file
                            ws_dir = self._get_workspace_dir(
                                user_id=user_id, chat_id=target_chat_id
                            )
                            todo_path = os.path.join(ws_dir, "TODO.md")
                            with open(todo_path, "w") as f:
                                f.write(todo_text)

                            self._emit_debug_log_sync(
                                f"Synced TODO to file (Chat: {target_chat_id})",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                    except Exception as sync_err:
                        self._emit_debug_log_sync(
                            f"TODO Sync Failed: {sync_err}",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )

                if (
                    tool_name == "sql"
                    and str(result_type).lower() in {"success", "ok", "completed"}
                    and self._query_mentions_todo_tables(
                        str(tool_args.get("query", ""))
                    )
                ):
                    todo_stats = self._read_todo_status_from_session_db(chat_id or "")

                    async def _refresh_todo_widget():
                        result = await self._emit_todo_widget(
                            chat_id=chat_id or "",
                            lang=user_lang,
                            emitter=__event_emitter__,
                            stats=todo_stats,
                        )
                        if result.get("changed"):
                            self._emit_debug_log_sync(
                                f"TODO widget refreshed from SQLite: {todo_stats}",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )

                    asyncio.create_task(_refresh_todo_widget())
                # ------------------------

                # --- Build native OpenWebUI 0.8.3 tool_calls block ---
                # Serialize input args (from execution_start)
                tool_args_for_block = {}
                if tool_call_id and tool_call_id in active_tools:
                    tool_args_for_block = active_tools[tool_call_id].get(
                        "arguments", {}
                    )
                    tool_name = active_tools[tool_call_id].get("name", tool_name)

                try:
                    args_json_str = json.dumps(tool_args_for_block, ensure_ascii=False)
                except Exception:
                    args_json_str = "{}"

                def escape_html_attr(s: str) -> str:
                    if not isinstance(s, str):
                        return ""
                    return (
                        str(s)
                        .replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                        .replace("\n", "&#10;")
                        .replace("\r", "&#13;")
                    )

                # MUST escape both arguments and result with &quot; and &#10; to satisfy OpenWebUI's strict regex /="([^"]*)"/
                args_for_attr = (
                    escape_html_attr(args_json_str) if args_json_str else "{}"
                )
                # Use "Success" if result_content is empty to ensure card renders
                # Truncate long results to prevent massive HTML attributes that cause
                # page height explosion in OpenWebUI (e.g. large crawl/scrape outputs)
                _max_result_display = 2000
                _result_raw = result_content or "Success"
                if len(_result_raw) > _max_result_display:
                    _result_raw = (
                        _result_raw[:_max_result_display]
                        + f"\n... ({len(result_content)} chars total, truncated)"
                    )
                result_for_attr = escape_html_attr(_result_raw)

                # Emit the unified native tool_calls block:
                # OpenWebUI 0.8.3 frontend regex explicitly expects: name="xxx" arguments="..." result="..." done="true"
                tool_block = (
                    f'\n<details type="tool_calls"'
                    f' id="{tool_call_id}"'
                    f' name="{tool_name}"'
                    f' arguments="{args_for_attr}"'
                    f' result="{result_for_attr}"'
                    f' done="true">\n'
                    f"<summary>Tool Executed</summary>\n"
                    f"</details>\n\n"
                )
                state["content_sent"] = True
                queue.put_nowait(tool_block)

                self._emit_debug_log_sync(
                    f"Tool Complete: {tool_name} - {result_type}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            elif event_type == "tool.execution_progress":
                # Tool execution progress update (for long-running tools)
                tool_call_id = safe_get_data_attr(event, "tool_call_id", "")
                tool_info = active_tools.get(tool_call_id)
                tool_name = (
                    tool_info.get("name", "Unknown Tool")
                    if isinstance(tool_info, dict)
                    else "Unknown Tool"
                )

                progress = safe_get_data_attr(event, "progress", 0)
                message = safe_get_data_attr(event, "message", "")

                status_text = self._get_translation(
                    user_lang,
                    "status_tool_progress",
                    name=tool_name,
                    progress=progress,
                    msg=message,
                )

                # Route through emit_status to respect session_finalized guard
                emit_status(status_text)

                self._emit_debug_log_sync(
                    f"Tool Progress: {tool_name} - {progress}%",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            elif event_type == "tool.execution_partial_result":
                # Streaming tool results (for tools that output incrementally)
                tool_call_id = safe_get_data_attr(event, "tool_call_id", "")
                tool_info = active_tools.get(tool_call_id)
                tool_name = (
                    tool_info.get("name", "Unknown Tool")
                    if isinstance(tool_info, dict)
                    else "Unknown Tool"
                )

                partial_content = safe_get_data_attr(event, "content", "")
                if partial_content:
                    queue.put_nowait(partial_content)

                self._emit_debug_log_sync(
                    f"Tool Partial Result: {tool_name}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            # === Sub-agent Events ===
            elif event_type == "subagent.started":
                agent_name = safe_get_data_attr(event, "name") or "Agent"
                self._emit_debug_log_sync(
                    f"Sub-agent Started: {agent_name}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                emit_status(
                    self._get_translation(
                        user_lang, "status_subagent_start", name=agent_name
                    )
                )

            elif event_type == "subagent.completed":
                agent_name = safe_get_data_attr(event, "name") or "Agent"
                self._emit_debug_log_sync(
                    f"Sub-agent Completed: {agent_name}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                emit_status(
                    self._get_translation(
                        user_lang, "status_subagent_start", name=agent_name
                    ),
                    is_done=True,
                )

            elif event_type == "subagent.failed":
                agent_name = safe_get_data_attr(event, "name") or "Agent"
                error = safe_get_data_attr(event, "error") or "Unknown error"
                self._emit_debug_log_sync(
                    f"Sub-agent Failed: {agent_name} - {error}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                emit_status(
                    self._get_translation(
                        user_lang, "status_subagent_start", name=agent_name
                    ),
                    is_done=True,
                )
                self._emit_debug_log_sync(
                    f"Sub-agent Failed: {agent_name} - {error}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            elif event_type == "assistant.turn_end":
                # Fallback: clear orphaned tool call tracking to unblock stall detection
                if running_tool_calls:
                    self._emit_debug_log_sync(
                        f"Turn ended with {len(running_tool_calls)} orphaned tool call(s), clearing",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )
                    running_tool_calls.clear()
                state["turn_started"] = False
                state["turn_ended"] = True
                state["turn_end_ts"] = state["last_event_ts"]

                self._emit_debug_log_sync(
                    "Assistant Turn Ended",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                if state.get("last_status_desc"):
                    emit_status(state["last_status_desc"], is_done=True)

                final_status_desc = state.get(
                    "final_status_desc"
                ) or self._get_translation(user_lang, "status_task_completed")
                emit_status(final_status_desc, is_done=True)

            # === Usage Statistics Events ===
            elif event_type == "assistant.usage":
                # Token usage for current assistant turn
                if self.valves.DEBUG:
                    input_tokens = safe_get_data_attr(event, "input_tokens", 0)
                    output_tokens = safe_get_data_attr(event, "output_tokens", 0)
                    total_tokens = safe_get_data_attr(event, "total_tokens", 0)
                pass

            elif event_type == "session.usage_info":
                # Cumulative session usage information
                pass

            elif event_type == "session.compaction_start":
                self._emit_debug_log_sync(
                    "Session Compaction Started",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                emit_status(self._get_translation(user_lang, "status_compaction_start"))

            elif event_type == "session.compaction_complete":
                self._emit_debug_log_sync(
                    "Session Compaction Completed",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )
                emit_status(
                    self._get_translation(user_lang, "status_compaction_complete"),
                    is_done=True,
                )

            elif event_type == "session.idle":
                # Session finished processing - signal to the generator loop to finalize
                state["idle_reached"] = True
                state["turn_started"] = False
                state["turn_ended"] = False
                try:
                    queue.put_nowait(IDLE_SENTINEL)
                except:
                    pass

            elif event_type == "session.error":
                state["turn_started"] = False
                state["turn_ended"] = False
                # Fallback: clear orphaned tool call tracking on session error
                running_tool_calls.clear()
                error_msg = safe_get_data_attr(event, "message", "Unknown Error")
                state["last_error_msg"] = error_msg
                state["final_status_desc"] = error_msg
                emit_status(
                    self._get_translation(
                        user_lang, "status_session_error", error=error_msg
                    ),
                    is_done=True,
                )
                queue.put_nowait(f"\n[Error: {error_msg}]")
                try:
                    queue.put_nowait(ERROR_SENTINEL)
                except:
                    pass

            # === Plan Persistence Events ===
            elif event_type == "session.plan_changed":
                operation = safe_get_data_attr(event, "operation", "update")
                emit_status(
                    self._get_translation(
                        user_lang, "status_plan_changed", operation=operation
                    )
                )
                self._emit_debug_log_sync(
                    f"Plan Changed: {operation}",
                    __event_call__,
                    debug_enabled=debug_enabled,
                )

            # === Context Changes ===
            elif event_type == "session.context_changed":
                new_ctx = safe_get_data_attr(event, "new_context")
                if isinstance(new_ctx, dict) and "cwd" in new_ctx:
                    emit_status(
                        self._get_translation(
                            user_lang, "status_context_changed", path=new_ctx["cwd"]
                        )
                    )

        # Clear any stale handlers from abandoned generators before subscribing.
        # When OpenWebUI cancels a request without awaiting generator.aclose(), the
        # old handler stays registered on the session object. Clearing first ensures
        # we never have more than one active handler per stream.
        try:
            with session._event_handlers_lock:
                stale_count = len(session._event_handlers)
                if stale_count:
                    session._event_handlers.clear()
                    self._emit_debug_log_sync(
                        f"Cleared {stale_count} stale handler(s) before subscribing",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )
        except Exception:
            pass  # SDK internals may change; fail silently

        unsubscribe = session.on(handler)

        # Diagnostic: log handler and queue identity for duplicate-output debugging.
        # If you see multiple "[HandlerRegistered]" logs with different handler_id
        # values but the same session_id, multiple handlers are registered concurrently.
        self._emit_debug_log_sync(
            f"[HandlerRegistered] handler_id={id(handler)}, queue_id={id(queue)}, "
            f"session_id={getattr(session, 'session_id', '?')}, "
            f"total_handlers={len(getattr(session, '_event_handlers', set()))}",
            __event_call__,
            debug_enabled=debug_enabled,
        )

        # Use asyncio.create_task used to prevent session.send from blocking the stream reading
        # if the SDK implementation waits for completion.
        state["send_start_ts"] = time.monotonic()
        send_task = asyncio.create_task(
            session.send(
                send_payload["prompt"],
                attachments=send_payload.get("attachments"),
                mode=send_payload.get("mode"),
            )
        )

        def _handle_send_task_done(task: asyncio.Task):
            if done.is_set():
                return
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                return
            except Exception as callback_err:
                exc = callback_err
            if not exc:
                return
            error_msg = f"Copilot send failed: {exc}"
            state["last_error_msg"] = error_msg
            state["final_status_desc"] = error_msg
            self._emit_debug_log_sync(
                error_msg,
                __event_call__,
                debug_enabled=debug_enabled,
            )
            try:
                queue.put_nowait(f"\n[Error: {error_msg}]")
                queue.put_nowait(ERROR_SENTINEL)
            except Exception:
                pass

        send_task.add_done_callback(_handle_send_task_done)
        self._emit_debug_log_sync(
            f"Prompt sent (async task started)",
            __event_call__,
            debug_enabled=debug_enabled,
        )

        # Safe initial yield with error handling
        try:
            if debug_enabled and __event_emitter__:
                # Emit debug info as UI status rather than reasoning block
                async def _emit_status(key: str, desc: Optional[str] = None, **kwargs):
                    try:
                        final_desc = (
                            desc
                            if desc
                            else self._get_translation(user_lang, key, **kwargs)
                        )
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {"description": final_desc, "done": True},
                            }
                        )
                    except:
                        pass

                if init_message:
                    for line in init_message.split("\n"):
                        if line.strip():
                            clean_msg = line.replace("> [Debug] ", "").strip()
                            asyncio.create_task(_emit_status("custom", desc=clean_msg))

                if reasoning_effort and reasoning_effort != "off":
                    asyncio.create_task(
                        _emit_status(
                            "status_reasoning_inj", effort=reasoning_effort.upper()
                        )
                    )

                asyncio.create_task(_emit_status("status_conn_est"))
        except Exception as e:
            # If initial yield fails, log but continue processing
            self._emit_debug_log_sync(
                f"Initial status warning: {e}",
                __event_call__,
                debug_enabled=debug_enabled,
            )

        try:
            while not done.is_set():
                try:
                    chunk = await asyncio.wait_for(
                        queue.get(), timeout=queue_poll_interval
                    )
                    if chunk is SENTINEL:
                        done.set()
                        break

                    if chunk is IDLE_SENTINEL:
                        artifact_chunks = []
                        # --- [FINAL STEP] Emit Rich UI Integrated View & Task Completion ---
                        if __event_emitter__:
                            try:
                                # 1b. Clear any tracked last tool/intent status
                                if state.get("last_status_desc"):
                                    await __event_emitter__(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": state[
                                                    "last_status_desc"
                                                ],
                                                "done": True,
                                            },
                                        }
                                    )
                                    state["last_status_desc"] = None

                                # 1c. CRITICAL: Close all tool statuses and REWRITE their description
                                # In some versions of OpenWebUI, just marking as done doesn't update the summary.
                                # We explicitly change the text to 'Completed' to force UI refresh.
                                for _tool_id, _tool_info in active_tools.items():
                                    if isinstance(_tool_info, dict) and _tool_info.get(
                                        "status_text"
                                    ):
                                        try:
                                            # Append a checkmark to the tool status to force a string change
                                            final_tool_status = f"✅ {_tool_info['status_text'].replace('...', '')}"
                                            await __event_emitter__(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": final_tool_status,
                                                        "done": True,
                                                    },
                                                }
                                            )
                                        except Exception:
                                            pass

                                artifact_chunks = await _flush_pending_embeds(
                                    "session.idle"
                                )

                                # 3. LOCK internal status emission for background tasks
                                # (Stray Task A from tool.execution_complete will now be discarded)
                                state["session_finalized"] = True

                                # 4. [PULSE LOCK] Trigger a UI refresh by pulsing a non-done status
                                # This forces OpenWebUI's summary line to re-evaluate the description.
                                # 4. [PULSE LOCK] Trigger a UI refresh by pulsing a non-done status
                                final_status_desc = state.get(
                                    "final_status_desc"
                                ) or self._get_translation(
                                    user_lang, "status_task_completed"
                                )
                                finalized_msg = "✔️ " + final_status_desc

                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": finalized_msg,
                                            "done": False,
                                        },
                                    }
                                )

                                # Increased window to ensure the 'done: False' is processed before the pipe closes
                                await asyncio.sleep(0.2)

                                # 5. FINAL emit
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": finalized_msg,
                                            "done": True,
                                            "hidden": False,
                                        },
                                    }
                                )
                            except Exception as emit_error:
                                self._emit_debug_log_sync(
                                    f"Final emission error: {emit_error}",
                                    __event_call__,
                                    debug_enabled=debug_enabled,
                                )
                        else:
                            artifact_chunks = await _flush_pending_embeds(
                                "session.idle.no_emitter"
                            )

                        for artifact_chunk in artifact_chunks:
                            if artifact_chunk:
                                has_content = True
                                yield artifact_chunk

                        done.set()
                        break

                    if chunk is ERROR_SENTINEL:
                        # Extract error message if possible or use default
                        error_desc = state.get(
                            "last_error_msg", "Error during processing"
                        )
                        artifact_chunks = await _flush_pending_embeds("error")
                        for artifact_chunk in artifact_chunks:
                            if artifact_chunk:
                                has_content = True
                                yield artifact_chunk
                        state["session_finalized"] = True
                        if __event_emitter__:
                            try:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": error_desc,
                                            "done": True,
                                        },
                                    }
                                )
                            except:
                                pass
                        done.set()
                        break

                    if chunk:
                        has_content = True
                        try:
                            yield chunk
                        except Exception as yield_error:
                            # Connection closed by client, stop gracefully
                            self._emit_debug_log_sync(
                                f"Yield error (client disconnected?): {yield_error}",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                            break
                except asyncio.TimeoutError:
                    if done.is_set():
                        break

                    now_ts = time.monotonic()
                    no_progress_timeout = float(self.valves.TIMEOUT)
                    time_since_last_event = now_ts - state.get(
                        "last_event_ts", stream_start_ts
                    )
                    turn_end_ts = state.get("turn_end_ts") or now_ts
                    time_since_turn_end = now_ts - turn_end_ts

                    if (
                        state.get("turn_ended")
                        and not state["idle_reached"]
                        and time_since_turn_end >= 3.0
                    ):
                        self._emit_debug_log_sync(
                            "assistant.turn_end received but session.idle did not arrive in time; synthesizing idle for final flush",
                            __event_call__,
                            debug_enabled=debug_enabled,
                        )
                        state["idle_reached"] = True
                        try:
                            queue.put_nowait(IDLE_SENTINEL)
                        except Exception:
                            pass
                        continue

                    # --- Primary Stall Detection: no content started yet ---
                    if (
                        state.get("turn_started")
                        and not state["content_sent"]
                        and not state["thinking_started"]
                        and not running_tool_calls
                        and time_since_last_event >= no_progress_timeout
                    ):
                        # Attempt to rescue via Ping before aborting
                        try:
                            await asyncio.wait_for(client.ping(), timeout=5.0)
                            state["last_event_ts"] = time.monotonic()
                            self._emit_debug_log_sync(
                                "Stall detection threshold reached, but client is alive (Ping successful). Extended wait time.",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                            continue
                        except Exception as ping_err:
                            stall_msg = f"Copilot stalled after assistant.turn_start. Ping failed ({ping_err}). The request was aborted."
                            state["last_error_msg"] = stall_msg
                            state["final_status_desc"] = stall_msg
                            self._emit_debug_log_sync(
                                stall_msg,
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                            try:
                                await asyncio.wait_for(session.abort(), timeout=5.0)
                            except asyncio.TimeoutError:
                                self._emit_debug_log_sync(
                                    "session.abort() itself timed out (5s) — connection likely dead",
                                    __event_call__,
                                    debug_enabled=debug_enabled,
                                )
                            except Exception as abort_err:
                                self._emit_debug_log_sync(
                                    f"Failed to abort stalled session: {abort_err}",
                                    __event_call__,
                                    debug_enabled=debug_enabled,
                                )
                            try:
                                queue.put_nowait(f"\n[Error: {stall_msg}]")
                                queue.put_nowait(ERROR_SENTINEL)
                            except Exception:
                                pass
                            continue

                    # --- Secondary Absolute Inactivity Guard ---
                    # If tools are actively running (e.g. long bash crawl task),
                    # allow the full TIMEOUT before force-aborting.
                    # Otherwise use a shorter limit for faster recovery.
                    if running_tool_calls:
                        absolute_inactivity_limit = float(self.valves.TIMEOUT)
                    else:
                        absolute_inactivity_limit = no_progress_timeout * 2.0
                    if time_since_last_event >= absolute_inactivity_limit:
                        # Attempt to rescue via Ping before aborting
                        try:
                            await asyncio.wait_for(client.ping(), timeout=5.0)
                            state["last_event_ts"] = time.monotonic()
                            self._emit_debug_log_sync(
                                f"Inactivity limit ({absolute_inactivity_limit}s) reached, but client is alive (Ping successful). Extended wait time.",
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                            continue
                        except Exception as ping_err:
                            stall_msg = (
                                f"Copilot session inactive for {int(time_since_last_event)}s "
                                f"(limit: {int(absolute_inactivity_limit)}s). Ping failed ({ping_err}). "
                                f"Force-aborting to prevent permanent hang."
                            )
                            state["last_error_msg"] = stall_msg
                            state["final_status_desc"] = stall_msg
                            self._emit_debug_log_sync(
                                stall_msg,
                                __event_call__,
                                debug_enabled=debug_enabled,
                            )
                            running_tool_calls.clear()
                            try:
                                await asyncio.wait_for(session.abort(), timeout=5.0)
                            except asyncio.TimeoutError:
                                self._emit_debug_log_sync(
                                    "session.abort() itself timed out (5s) — connection likely dead",
                                    __event_call__,
                                    debug_enabled=debug_enabled,
                                )
                            except Exception as abort_err:
                                self._emit_debug_log_sync(
                                    f"Failed to abort inactive session: {abort_err}",
                                    __event_call__,
                                    debug_enabled=debug_enabled,
                                )
                            try:
                                queue.put_nowait(f"\n[Error: {stall_msg}]")
                                queue.put_nowait(ERROR_SENTINEL)
                            except Exception:
                                pass
                            continue

                    if __event_emitter__ and (
                        now_ts - last_wait_status_ts >= wait_status_interval
                    ):
                        elapsed = int(now_ts - stream_start_ts)
                        try:
                            asyncio.create_task(
                                __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": self._get_translation(
                                                user_lang,
                                                "status_still_working",
                                                seconds=elapsed,
                                            ),
                                            "done": False,
                                        },
                                    }
                                )
                            )
                        except Exception:
                            pass
                        last_wait_status_ts = now_ts
                    continue

            while not queue.empty():
                chunk = queue.get_nowait()
                if chunk in (SENTINEL, IDLE_SENTINEL, ERROR_SENTINEL):
                    break
                if chunk:
                    has_content = True
                    try:
                        yield chunk
                    except:
                        # Connection closed, stop yielding
                        break

            if state["thinking_started"]:
                try:
                    yield "\n</think>\n"
                    has_content = True
                except:
                    pass  # Connection closed

            if hasattr(session, "rpc"):
                try:
                    plan_result = await session.rpc.plan.read()
                    if getattr(plan_result, "exists", False) and getattr(
                        plan_result, "content", None
                    ):
                        plan_content = plan_result.content
                        self._persist_plan_text(chat_id, plan_content)
                        plan_msg = (
                            f"\n\n> 📋 **{self._get_translation(user_lang, 'plan_title')}**\n"
                            f"> \n> " + "\n> ".join(plan_content.splitlines())
                        )
                        yield plan_msg
                        has_content = True
                except Exception as plan_err:
                    self._emit_debug_log_sync(
                        f"Failed to fetch plan: {plan_err}",
                        __event_call__,
                        debug_enabled=debug_enabled,
                    )

            # Core fix: If no content was yielded, return a fallback message to prevent OpenWebUI error
            if not has_content:
                try:
                    yield "⚠️ Copilot returned no content. Please check if the Model ID is correct or enable DEBUG mode in Valves for details."
                except:
                    pass  # Connection already closed

        except Exception as e:
            try:
                yield f"\n[Stream Error: {str(e)}]"
            except:
                pass  # Connection already closed
        finally:
            try:
                if not send_task.done():
                    send_task.cancel()
            except Exception:
                pass
            # Final Status Cleanup: Emergency mark all as done if not already
            if __event_emitter__:
                try:
                    # Clear any specific tool/intent statuses tracked
                    if state.get("last_status_desc"):
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": state["last_status_desc"],
                                    "done": True,
                                },
                            }
                        )

                    # Clear all active tool statuses before final completion status,
                    # so Task completed remains the last visible summary in OpenWebUI.
                    for tool_id, tool_info in active_tools.items():
                        if isinstance(tool_info, dict) and tool_info.get("status_text"):
                            try:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": tool_info["status_text"],
                                            "done": True,
                                        },
                                    }
                                )
                            except:
                                pass

                    # Final final confirmation to prevent any stuck status bubbles
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": state.get("final_status_desc")
                                or self._get_translation(
                                    user_lang, "status_task_completed"
                                ),
                                "done": True,
                                "hidden": False,
                            },
                        }
                    )
                except:
                    pass

            unsubscribe()
            try:
                await client.stop()
            except Exception:
                pass


# Triggering release after CI fix
