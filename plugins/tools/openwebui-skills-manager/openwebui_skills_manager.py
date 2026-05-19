"""
title: OpenWebUI Skills Manager Tool
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
version: 0.3.3
openwebui_id: b4bce8e4-08e7-4f90-bea7-dc31d463a0bb
requirements:
description: Standalone OpenWebUI tool for managing native Workspace Skills (list/show/install/create/update/delete) for any model.
"""

import asyncio
import json
import logging
import re
import tarfile
import tempfile
import uuid
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from pydantic import BaseModel, Field
from inspect import isawaitable, iscoroutinefunction

logger = logging.getLogger(__name__)

try:
    from open_webui.models.skills import Skills, SkillForm, SkillMeta
except Exception:
    Skills = None
    SkillForm = None
    SkillMeta = None


BASE_TRANSLATIONS = {
    "status_listing": "Listing your skills...",
    "status_showing": "Reading skill details...",
    "status_installing": "Installing skill from URL...",
    "status_installing_batch": "Installing {total} skill(s)...",
    "status_discovering_skills": "Discovering skills in {url}...",
    "status_detecting_repo_root": "Detected GitHub repo root: {url}. Auto-converting to discovery mode...",
    "status_batch_duplicates_removed": "Removed {count} duplicate URL(s) from batch.",
    "status_duplicate_skill_name": "Warning: Duplicate skill name '{name}' - {action} multiple times.",
    "status_creating": "Creating skill...",
    "status_updating": "Updating skill...",
    "status_deleting": "Deleting skill...",
    "status_done": "Done.",
    "status_list_done": "Found {count} skills ({active_count} active).",
    "status_show_done": "Loaded skill: {name}.",
    "status_install_done": "Installed skill: {name}.",
    "status_install_overwrite_done": "Installed by updating existing skill: {name}.",
    "status_create_done": "Created skill: {name}.",
    "status_create_overwrite_done": "Updated existing skill: {name}.",
    "status_update_done": "Updated skill: {name}.",
    "status_delete_done": "Deleted skill: {name}.",
    "status_install_batch_done": "Batch install completed: {succeeded} succeeded, {failed} failed.",
    "err_unavailable": "OpenWebUI Skills model is unavailable in this runtime.",
    "err_user_required": "User context is required.",
    "err_name_required": "Skill name is required.",
    "err_not_found": "Skill not found.",
    "err_no_update_fields": "No update fields provided.",
    "err_url_required": "Skill URL is required.",
    "err_install_fetch": "Failed to fetch skill content from URL.",
    "err_install_parse": "Failed to parse skill package/content.",
    "err_invalid_url": "Invalid URL. Only http(s) URLs are supported.",
    "err_untrusted_domain": "Domain not in whitelist. Trusted domains: {domains}",
    "msg_created": "Skill created successfully.",
    "msg_updated": "Skill updated successfully.",
    "msg_deleted": "Skill deleted successfully.",
    "msg_installed": "Skill installed successfully.",
    "confirm_update_title": "Update skill?",
    "confirm_update_message": "Update skill \"{name}\".\nDescription: {description}",
    "confirm_delete_title": "Delete skill?",
    "confirm_delete_message": "Permanently delete skill \"{name}\". This cannot be undone.\nDescription: {description}",
    "status_update_cancelled": "Update cancelled by user.",
    "status_delete_cancelled": "Deletion cancelled by user.",
    "msg_update_cancelled": "Skill update cancelled by user.",
    "msg_delete_cancelled": "Skill deletion cancelled by user.",
    "confirm_overwrite_title": "Overwrite existing skill?",
    "confirm_overwrite_message": "Overwrite skill \"{name}\". Its description and content will be replaced.\nCurrent description: {description}",
    "status_overwrite_cancelled": "Overwrite cancelled by user.",
    "msg_overwrite_cancelled": "Skill overwrite cancelled by user.",
    "err_confirmation_unavailable": "Cannot prompt for confirmation in this context (no interactive event channel). Disable REQUIRE_CONFIRMATION in valves to proceed without prompting.",
    "no_description": "(no description)",
}

TRANSLATIONS = {
    "en-US": BASE_TRANSLATIONS,
    "zh-CN": {
        "status_listing": "正在列出你的技能...",
        "status_showing": "正在读取技能详情...",
        "status_installing": "正在从 URL 安装技能...",
        "status_installing_batch": "正在安装 {total} 个技能...",
        "status_discovering_skills": "正在从 {url} 发现技能...",
        "status_detecting_repo_root": "检测到 GitHub repo 根目录：{url}。自动转换为发现模式...",
        "status_batch_duplicates_removed": "已从批量队列中移除 {count} 个重复 URL。",
        "status_duplicate_skill_name": "警告：技能名称 '{name}' 重复 - 多次 {action}。",
        "status_creating": "正在创建技能...",
        "status_updating": "正在更新技能...",
        "status_deleting": "正在删除技能...",
        "status_done": "已完成。",
        "status_list_done": "已找到 {count} 个技能（启用 {active_count} 个）。",
        "status_show_done": "已加载技能：{name}。",
        "status_install_done": "技能安装完成：{name}。",
        "status_install_overwrite_done": "已通过覆盖更新完成安装：{name}。",
        "status_create_done": "技能创建完成：{name}。",
        "status_create_overwrite_done": "已更新同名技能：{name}。",
        "status_update_done": "技能更新完成：{name}。",
        "status_delete_done": "技能删除完成：{name}。",
        "status_install_batch_done": "批量安装完成：成功 {succeeded} 个，失败 {failed} 个。",
        "err_unavailable": "当前运行环境不可用 OpenWebUI Skills 模型。",
        "err_user_required": "需要用户上下文。",
        "err_name_required": "技能名称不能为空。",
        "err_not_found": "未找到技能。",
        "err_no_update_fields": "未提供可更新字段。",
        "err_url_required": "技能 URL 不能为空。",
        "err_install_fetch": "从 URL 获取技能内容失败。",
        "err_install_parse": "解析技能包或内容失败。",
        "err_invalid_url": "URL 无效，仅支持 http(s) 地址。",
        "err_untrusted_domain": "域名不在白名单中。授信域名：{domains}",
        "msg_created": "技能创建成功。",
        "msg_updated": "技能更新成功。",
        "msg_deleted": "技能删除成功。",
        "msg_installed": "技能安装成功。",
        "confirm_update_title": "更新技能？",
        "confirm_update_message": "更新技能 \"{name}\"。\n描述：{description}",
        "confirm_delete_title": "删除技能？",
        "confirm_delete_message": "将永久删除技能 \"{name}\"。此操作无法撤销。\n描述：{description}",
        "status_update_cancelled": "用户已取消更新。",
        "status_delete_cancelled": "用户已取消删除。",
        "msg_update_cancelled": "技能更新已由用户取消。",
        "msg_delete_cancelled": "技能删除已由用户取消。",
        "confirm_overwrite_title": "覆盖已存在的技能？",
        "confirm_overwrite_message": "覆盖技能 \"{name}\"。其描述和内容将被替换。\n当前描述：{description}",
        "status_overwrite_cancelled": "用户已取消覆盖。",
        "msg_overwrite_cancelled": "技能覆盖已由用户取消。",
        "err_confirmation_unavailable": "当前上下文无法弹出确认提示（无交互事件通道）。请在阀门设置中关闭 REQUIRE_CONFIRMATION 以跳过确认。",
        "no_description": "（无描述）",
    },
    "zh-TW": {
        "status_listing": "正在列出你的技能...",
        "status_showing": "正在讀取技能詳情...",
        "status_installing": "正在從 URL 安裝技能...",
        "status_installing_batch": "正在安裝 {total} 個技能...",
        "status_discovering_skills": "正在從 {url} 發現技能...",
        "status_detecting_repo_root": "偵測到 GitHub repo 根目錄：{url}。自動轉換為發現模式...",
        "status_batch_duplicates_removed": "已從批次佇列中移除 {count} 個重複 URL。",
        "status_duplicate_skill_name": "警告：技能名稱 '{name}' 重複 - 多次 {action}。",
        "status_creating": "正在建立技能...",
        "status_updating": "正在更新技能...",
        "status_deleting": "正在刪除技能...",
        "status_done": "已完成。",
        "status_list_done": "已找到 {count} 個技能（啟用 {active_count} 個）。",
        "status_show_done": "已載入技能：{name}。",
        "status_install_done": "技能安裝完成：{name}。",
        "status_install_overwrite_done": "已透過覆蓋更新完成安裝：{name}。",
        "status_create_done": "技能建立完成：{name}。",
        "status_create_overwrite_done": "已更新同名技能：{name}。",
        "status_update_done": "技能更新完成：{name}。",
        "status_delete_done": "技能刪除完成：{name}。",
        "status_install_batch_done": "批次安裝完成：成功 {succeeded} 個，失敗 {failed} 個。",
        "err_unavailable": "目前執行環境不可用 OpenWebUI Skills 模型。",
        "err_user_required": "需要使用者上下文。",
        "err_name_required": "技能名稱不能為空。",
        "err_not_found": "未找到技能。",
        "err_no_update_fields": "未提供可更新欄位。",
        "err_url_required": "技能 URL 不能為空。",
        "err_install_fetch": "從 URL 取得技能內容失敗。",
        "err_install_parse": "解析技能包或內容失敗。",
        "err_invalid_url": "URL 無效，僅支援 http(s) 位址。",
        "msg_created": "技能建立成功。",
        "msg_updated": "技能更新成功。",
        "msg_deleted": "技能刪除成功。",
        "msg_installed": "技能安裝成功。",
        "confirm_update_title": "更新技能？",
        "confirm_update_message": "更新技能 \"{name}\"。\n描述：{description}",
        "confirm_delete_title": "刪除技能？",
        "confirm_delete_message": "將永久刪除技能 \"{name}\"。此操作無法復原。\n描述：{description}",
        "status_update_cancelled": "使用者已取消更新。",
        "status_delete_cancelled": "使用者已取消刪除。",
        "msg_update_cancelled": "技能更新已由使用者取消。",
        "msg_delete_cancelled": "技能刪除已由使用者取消。",
        "confirm_overwrite_title": "覆寫已存在的技能？",
        "confirm_overwrite_message": "覆寫技能 \"{name}\"。其描述和內容將被取代。\n目前描述：{description}",
        "status_overwrite_cancelled": "使用者已取消覆寫。",
        "msg_overwrite_cancelled": "技能覆寫已由使用者取消。",
        "err_confirmation_unavailable": "目前上下文無法彈出確認提示（無互動事件通道）。請在閥門設定中關閉 REQUIRE_CONFIRMATION 以略過確認。",
        "no_description": "（無描述）",
    },
    "zh-HK": {
        "status_listing": "正在列出你的技能...",
        "status_showing": "正在讀取技能詳情...",
        "status_installing": "正在從 URL 安裝技能...",
        "status_installing_batch": "正在安裝 {total} 個技能...",
        "status_discovering_skills": "正在從 {url} 發現技能...",
        "status_detecting_repo_root": "偵測到 GitHub repo 根目錄：{url}。自動轉換為發現模式...",
        "status_batch_duplicates_removed": "已從批次佇列中移除 {count} 個重複 URL。",
        "status_duplicate_skill_name": "警告：技能名稱 '{name}' 重複 - 多次 {action}。",
        "status_creating": "正在建立技能...",
        "status_updating": "正在更新技能...",
        "status_deleting": "正在刪除技能...",
        "status_done": "已完成。",
        "status_list_done": "已找到 {count} 個技能（啟用 {active_count} 個）。",
        "status_show_done": "已載入技能：{name}。",
        "status_install_done": "技能安裝完成：{name}。",
        "status_install_overwrite_done": "已透過覆蓋更新完成安裝：{name}。",
        "status_create_done": "技能建立完成：{name}。",
        "status_create_overwrite_done": "已更新同名技能：{name}。",
        "status_update_done": "技能更新完成：{name}。",
        "status_delete_done": "技能刪除完成：{name}。",
        "status_install_batch_done": "批次安裝完成：成功 {succeeded} 個，失敗 {failed} 個。",
        "err_unavailable": "目前執行環境不可用 OpenWebUI Skills 模型。",
        "err_user_required": "需要使用者上下文。",
        "err_name_required": "技能名稱不能為空。",
        "err_not_found": "未找到技能。",
        "err_no_update_fields": "未提供可更新欄位。",
        "err_url_required": "技能 URL 不能為空。",
        "err_install_fetch": "從 URL 取得技能內容失敗。",
        "err_install_parse": "解析技能包或內容失敗。",
        "err_invalid_url": "URL 無效，僅支援 http(s) 位址。",
        "msg_created": "技能建立成功。",
        "msg_updated": "技能更新成功。",
        "msg_deleted": "技能刪除成功。",
        "msg_installed": "技能安裝成功。",
        "confirm_update_title": "更新技能？",
        "confirm_update_message": "更新技能 \"{name}\"。\n描述：{description}",
        "confirm_delete_title": "刪除技能？",
        "confirm_delete_message": "將永久刪除技能 \"{name}\"。此操作無法復原。\n描述：{description}",
        "status_update_cancelled": "使用者已取消更新。",
        "status_delete_cancelled": "使用者已取消刪除。",
        "msg_update_cancelled": "技能更新已由使用者取消。",
        "msg_delete_cancelled": "技能刪除已由使用者取消。",
        "confirm_overwrite_title": "覆寫已存在的技能？",
        "confirm_overwrite_message": "覆寫技能 \"{name}\"。其描述和內容將被取代。\n目前描述：{description}",
        "status_overwrite_cancelled": "使用者已取消覆寫。",
        "msg_overwrite_cancelled": "技能覆寫已由使用者取消。",
        "err_confirmation_unavailable": "目前上下文無法彈出確認提示（無互動事件通道）。請在閥門設定中關閉 REQUIRE_CONFIRMATION 以略過確認。",
        "no_description": "（無描述）",
    },
    "ja-JP": {
        "status_listing": "スキル一覧を取得しています...",
        "status_showing": "スキル詳細を読み込み中...",
        "status_installing": "URL からスキルをインストール中...",
        "status_installing_batch": "{total} 件のスキルをインストール中...",
        "status_discovering_skills": "{url} からスキルを検出中...",
        "status_detecting_repo_root": "GitHub リポジトリルートを検出しました: {url}。自動検出モードに変換しています...",
        "status_batch_duplicates_removed": "バッチから {count} 個の重複 URL を削除しました。",
        "status_duplicate_skill_name": "警告: スキル名 '{name}' の重複 - {action} が複数回実行されました。",
        "status_creating": "スキルを作成中...",
        "status_updating": "スキルを更新中...",
        "status_deleting": "スキルを削除中...",
        "status_done": "完了しました。",
        "status_list_done": "{count} 件のスキルが見つかりました（有効: {active_count} 件）。",
        "status_show_done": "スキルを読み込みました: {name}。",
        "status_install_done": "スキルをインストールしました: {name}。",
        "status_install_overwrite_done": "既存スキルを更新してインストールしました: {name}。",
        "status_create_done": "スキルを作成しました: {name}。",
        "status_create_overwrite_done": "同名スキルを更新しました: {name}。",
        "status_update_done": "スキルを更新しました: {name}。",
        "status_delete_done": "スキルを削除しました: {name}。",
        "status_install_batch_done": "一括インストール完了: 成功 {succeeded} 件、失敗 {failed} 件。",
        "err_unavailable": "この実行環境では OpenWebUI Skills モデルを利用できません。",
        "err_user_required": "ユーザーコンテキストが必要です。",
        "err_name_required": "スキル名は必須です。",
        "err_not_found": "スキルが見つかりません。",
        "err_no_update_fields": "更新する項目が指定されていません。",
        "err_url_required": "スキル URL は必須です。",
        "err_install_fetch": "URL からスキル内容の取得に失敗しました。",
        "err_install_parse": "スキルパッケージ/内容の解析に失敗しました。",
        "err_invalid_url": "無効な URL です。http(s) のみサポートします。",
        "msg_created": "スキルを作成しました。",
        "msg_updated": "スキルを更新しました。",
        "msg_deleted": "スキルを削除しました。",
        "msg_installed": "スキルをインストールしました。",
        "confirm_update_title": "スキルを更新しますか？",
        "confirm_update_message": "スキル \"{name}\" を更新します。\n説明: {description}",
        "confirm_delete_title": "スキルを削除しますか？",
        "confirm_delete_message": "スキル \"{name}\" を完全に削除します。この操作は取り消せません。\n説明: {description}",
        "status_update_cancelled": "ユーザーが更新をキャンセルしました。",
        "status_delete_cancelled": "ユーザーが削除をキャンセルしました。",
        "msg_update_cancelled": "スキルの更新がユーザーによりキャンセルされました。",
        "msg_delete_cancelled": "スキルの削除がユーザーによりキャンセルされました。",
        "confirm_overwrite_title": "既存のスキルを上書きしますか？",
        "confirm_overwrite_message": "スキル \"{name}\" を上書きします。説明と内容が置き換えられます。\n現在の説明: {description}",
        "status_overwrite_cancelled": "ユーザーが上書きをキャンセルしました。",
        "msg_overwrite_cancelled": "スキルの上書きがユーザーによりキャンセルされました。",
        "err_confirmation_unavailable": "現在のコンテキストでは確認プロンプトを表示できません（対話型イベントチャネルなし）。確認なしで実行するにはバルブの REQUIRE_CONFIRMATION を無効にしてください。",
        "no_description": "(説明なし)",
    },
    "ko-KR": {
        "status_listing": "스킬 목록을 불러오는 중...",
        "status_showing": "스킬 상세 정보를 읽는 중...",
        "status_installing": "URL에서 스킬 설치 중...",
        "status_installing_batch": "스킬 {total}개를 설치하는 중...",
        "status_discovering_skills": "{url}에서 스킬 발견 중...",
        "status_detecting_repo_root": "GitHub 저장소 루트 검출: {url}。자동 발견 모드로 변환 중...",
        "status_batch_duplicates_removed": "배치에서 {count}개의 중복 URL을 제거했습니다.",
        "status_duplicate_skill_name": "경고: 스킬 이름 '{name}'이 중복됨 - {action}이 여러 번 실행됨.",
        "status_creating": "스킬 생성 중...",
        "status_updating": "스킬 업데이트 중...",
        "status_deleting": "스킬 삭제 중...",
        "status_done": "완료되었습니다.",
        "status_list_done": "스킬 {count}개를 찾았습니다(활성 {active_count}개).",
        "status_show_done": "스킬을 불러왔습니다: {name}.",
        "status_install_done": "스킬 설치 완료: {name}.",
        "status_install_overwrite_done": "기존 스킬을 업데이트하여 설치 완료: {name}.",
        "status_create_done": "스킬 생성 완료: {name}.",
        "status_create_overwrite_done": "동일 이름 스킬 업데이트 완료: {name}.",
        "status_update_done": "스킬 업데이트 완료: {name}.",
        "status_delete_done": "스킬 삭제 완료: {name}.",
        "status_install_batch_done": "일괄 설치 완료: 성공 {succeeded}개, 실패 {failed}개.",
        "err_unavailable": "현재 런타임에서 OpenWebUI Skills 모델을 사용할 수 없습니다.",
        "err_user_required": "사용자 컨텍스트가 필요합니다.",
        "err_name_required": "스킬 이름은 필수입니다.",
        "err_not_found": "스킬을 찾을 수 없습니다.",
        "err_no_update_fields": "업데이트할 필드가 제공되지 않았습니다.",
        "err_url_required": "스킬 URL이 필요합니다.",
        "err_install_fetch": "URL에서 스킬 내용을 가져오지 못했습니다.",
        "err_install_parse": "스킬 패키지/내용 파싱에 실패했습니다.",
        "err_invalid_url": "잘못된 URL입니다. http(s)만 지원됩니다.",
        "msg_created": "스킬이 생성되었습니다.",
        "msg_updated": "스킬이 업데이트되었습니다.",
        "msg_deleted": "스킬이 삭제되었습니다.",
        "msg_installed": "스킬이 설치되었습니다.",
        "confirm_update_title": "스킬을 업데이트하시겠습니까?",
        "confirm_update_message": "스킬 \"{name}\"을(를) 업데이트합니다.\n설명: {description}",
        "confirm_delete_title": "스킬을 삭제하시겠습니까?",
        "confirm_delete_message": "스킬 \"{name}\"을(를) 영구적으로 삭제합니다. 이 작업은 되돌릴 수 없습니다.\n설명: {description}",
        "status_update_cancelled": "사용자가 업데이트를 취소했습니다.",
        "status_delete_cancelled": "사용자가 삭제를 취소했습니다.",
        "msg_update_cancelled": "스킬 업데이트가 사용자에 의해 취소되었습니다.",
        "msg_delete_cancelled": "스킬 삭제가 사용자에 의해 취소되었습니다.",
        "confirm_overwrite_title": "기존 스킬을 덮어쓰시겠습니까?",
        "confirm_overwrite_message": "스킬 \"{name}\"을(를) 덮어씁니다. 설명과 내용이 교체됩니다.\n현재 설명: {description}",
        "status_overwrite_cancelled": "사용자가 덮어쓰기를 취소했습니다.",
        "msg_overwrite_cancelled": "스킬 덮어쓰기가 사용자에 의해 취소되었습니다.",
        "err_confirmation_unavailable": "현재 컨텍스트에서 확인 프롬프트를 표시할 수 없습니다(대화형 이벤트 채널 없음). 확인 없이 진행하려면 밸브에서 REQUIRE_CONFIRMATION을 비활성화하세요.",
        "no_description": "(설명 없음)",
    },
    "fr-FR": {
        "status_listing": "Liste des skills en cours...",
        "status_showing": "Lecture des détails du skill...",
        "status_installing": "Installation du skill depuis l'URL...",
        "status_installing_batch": "Installation de {total} skill(s)...",
        "status_discovering_skills": "Découverte de skills dans {url}...",
        "status_detecting_repo_root": "Racine du dépôt GitHub détectée: {url}. Conversion en mode découverte automatique...",
        "status_batch_duplicates_removed": "{count} URL en doublon(s) supprimée(s) du lot.",
        "status_duplicate_skill_name": "Attention: Nom du skill '{name}' en doublon - {action} plusieurs fois.",
        "status_creating": "Création du skill...",
        "status_updating": "Mise à jour du skill...",
        "status_deleting": "Suppression du skill...",
        "status_done": "Terminé.",
        "status_list_done": "{count} skills trouvés ({active_count} actifs).",
        "status_show_done": "Skill chargé : {name}.",
        "status_install_done": "Skill installé : {name}.",
        "status_install_overwrite_done": "Skill installé en mettant à jour l'existant : {name}.",
        "status_create_done": "Skill créé : {name}.",
        "status_create_overwrite_done": "Skill existant mis à jour : {name}.",
        "status_update_done": "Skill mis à jour : {name}.",
        "status_delete_done": "Skill supprimé : {name}.",
        "status_install_batch_done": "Installation en lot terminée : {succeeded} réussies, {failed} échouées.",
        "err_unavailable": "Le modèle OpenWebUI Skills n'est pas disponible dans cet environnement.",
        "err_user_required": "Le contexte utilisateur est requis.",
        "err_name_required": "Le nom du skill est requis.",
        "err_not_found": "Skill introuvable.",
        "err_no_update_fields": "Aucun champ à mettre à jour n'a été fourni.",
        "err_url_required": "L'URL du skill est requise.",
        "err_install_fetch": "Échec de récupération du contenu du skill depuis l'URL.",
        "err_install_parse": "Échec de l'analyse du package/contenu du skill.",
        "err_invalid_url": "URL invalide. Seules les URL http(s) sont prises en charge.",
        "msg_created": "Skill créé avec succès.",
        "msg_updated": "Skill mis à jour avec succès.",
        "msg_deleted": "Skill supprimé avec succès.",
        "msg_installed": "Skill installé avec succès.",
        "confirm_update_title": "Mettre à jour le skill ?",
        "confirm_update_message": "Mettre à jour le skill \"{name}\".\nDescription : {description}",
        "confirm_delete_title": "Supprimer le skill ?",
        "confirm_delete_message": "Supprimer définitivement le skill \"{name}\". Cette action est irréversible.\nDescription : {description}",
        "status_update_cancelled": "Mise à jour annulée par l'utilisateur.",
        "status_delete_cancelled": "Suppression annulée par l'utilisateur.",
        "msg_update_cancelled": "Mise à jour du skill annulée par l'utilisateur.",
        "msg_delete_cancelled": "Suppression du skill annulée par l'utilisateur.",
        "confirm_overwrite_title": "Écraser le skill existant ?",
        "confirm_overwrite_message": "Écraser le skill \"{name}\". Sa description et son contenu seront remplacés.\nDescription actuelle : {description}",
        "status_overwrite_cancelled": "Écrasement annulé par l'utilisateur.",
        "msg_overwrite_cancelled": "Écrasement du skill annulé par l'utilisateur.",
        "err_confirmation_unavailable": "Impossible d'afficher une invite de confirmation dans ce contexte (aucun canal d'événement interactif). Désactivez REQUIRE_CONFIRMATION dans les valves pour continuer sans invite.",
        "no_description": "(aucune description)",
    },
    "de-DE": {
        "status_listing": "Deine Skills werden aufgelistet...",
        "status_showing": "Skill-Details werden gelesen...",
        "status_installing": "Skill wird von URL installiert...",
        "status_installing_batch": "{total} Skill(s) werden installiert...",
        "status_discovering_skills": "Suche nach Skills in {url}...",
        "status_creating": "Skill wird erstellt...",
        "status_updating": "Skill wird aktualisiert...",
        "status_deleting": "Skill wird gelöscht...",
        "status_done": "Fertig.",
        "status_list_done": "{count} Skills gefunden ({active_count} aktiv).",
        "status_show_done": "Skill geladen: {name}.",
        "status_install_done": "Skill installiert: {name}.",
        "status_install_overwrite_done": "Skill durch Aktualisierung installiert: {name}.",
        "status_create_done": "Skill erstellt: {name}.",
        "status_create_overwrite_done": "Bestehender Skill aktualisiert: {name}.",
        "status_update_done": "Skill aktualisiert: {name}.",
        "status_delete_done": "Skill gelöscht: {name}.",
        "status_install_batch_done": "Batch-Installation abgeschlossen: {succeeded} erfolgreich, {failed} fehlgeschlagen.",
        "err_unavailable": "Das OpenWebUI-Skills-Modell ist in dieser Laufzeit nicht verfügbar.",
        "err_user_required": "Benutzerkontext ist erforderlich.",
        "err_name_required": "Skill-Name ist erforderlich.",
        "err_not_found": "Skill nicht gefunden.",
        "err_no_update_fields": "Keine zu aktualisierenden Felder angegeben.",
        "err_url_required": "Skill-URL ist erforderlich.",
        "err_install_fetch": "Skill-Inhalt konnte nicht von URL geladen werden.",
        "err_install_parse": "Skill-Paket/Inhalt konnte nicht geparst werden.",
        "err_invalid_url": "Ungültige URL. Nur http(s)-URLs werden unterstützt.",
        "msg_created": "Skill erfolgreich erstellt.",
        "msg_updated": "Skill erfolgreich aktualisiert.",
        "msg_deleted": "Skill erfolgreich gelöscht.",
        "msg_installed": "Skill erfolgreich installiert.",
        "confirm_update_title": "Skill aktualisieren?",
        "confirm_update_message": "Skill \"{name}\" aktualisieren.\nBeschreibung: {description}",
        "confirm_delete_title": "Skill löschen?",
        "confirm_delete_message": "Skill \"{name}\" dauerhaft löschen. Dies kann nicht rückgängig gemacht werden.\nBeschreibung: {description}",
        "status_update_cancelled": "Aktualisierung vom Benutzer abgebrochen.",
        "status_delete_cancelled": "Löschung vom Benutzer abgebrochen.",
        "msg_update_cancelled": "Skill-Aktualisierung vom Benutzer abgebrochen.",
        "msg_delete_cancelled": "Skill-Löschung vom Benutzer abgebrochen.",
        "confirm_overwrite_title": "Vorhandenen Skill überschreiben?",
        "confirm_overwrite_message": "Skill \"{name}\" überschreiben. Seine Beschreibung und sein Inhalt werden ersetzt.\nAktuelle Beschreibung: {description}",
        "status_overwrite_cancelled": "Überschreiben vom Benutzer abgebrochen.",
        "msg_overwrite_cancelled": "Skill-Überschreiben vom Benutzer abgebrochen.",
        "err_confirmation_unavailable": "In diesem Kontext kann keine Bestätigung angezeigt werden (kein interaktiver Ereigniskanal). Deaktiviere REQUIRE_CONFIRMATION in den Valves, um ohne Bestätigung fortzufahren.",
        "no_description": "(keine Beschreibung)",
    },
    "es-ES": {
        "status_listing": "Listando tus skills...",
        "status_showing": "Leyendo detalles del skill...",
        "status_installing": "Instalando skill desde URL...",
        "status_installing_batch": "Instalando {total} skill(s)...",
        "status_discovering_skills": "Descubriendo skills en {url}...",
        "status_creating": "Creando skill...",
        "status_updating": "Actualizando skill...",
        "status_deleting": "Eliminando skill...",
        "status_done": "Hecho.",
        "status_list_done": "Se encontraron {count} skills ({active_count} activos).",
        "status_show_done": "Skill cargado: {name}.",
        "status_install_done": "Skill instalado: {name}.",
        "status_install_overwrite_done": "Skill instalado actualizando el existente: {name}.",
        "status_create_done": "Skill creado: {name}.",
        "status_create_overwrite_done": "Skill existente actualizado: {name}.",
        "status_update_done": "Skill actualizado: {name}.",
        "status_delete_done": "Skill eliminado: {name}.",
        "status_install_batch_done": "Instalación por lotes completada: {succeeded} correctas, {failed} fallidas.",
        "err_unavailable": "El modelo OpenWebUI Skills no está disponible en este entorno.",
        "err_user_required": "Se requiere contexto de usuario.",
        "err_name_required": "Se requiere el nombre del skill.",
        "err_not_found": "Skill no encontrado.",
        "err_no_update_fields": "No se proporcionaron campos para actualizar.",
        "err_url_required": "Se requiere la URL del skill.",
        "err_install_fetch": "No se pudo obtener el contenido del skill desde la URL.",
        "err_install_parse": "No se pudo analizar el paquete/contenido del skill.",
        "err_invalid_url": "URL inválida. Solo se admiten URLs http(s).",
        "msg_created": "Skill creado correctamente.",
        "msg_updated": "Skill actualizado correctamente.",
        "msg_deleted": "Skill eliminado correctamente.",
        "msg_installed": "Skill instalado correctamente.",
        "confirm_update_title": "¿Actualizar skill?",
        "confirm_update_message": "Actualizar skill \"{name}\".\nDescripción: {description}",
        "confirm_delete_title": "¿Eliminar skill?",
        "confirm_delete_message": "Eliminar permanentemente el skill \"{name}\". Esta acción no se puede deshacer.\nDescripción: {description}",
        "status_update_cancelled": "Actualización cancelada por el usuario.",
        "status_delete_cancelled": "Eliminación cancelada por el usuario.",
        "msg_update_cancelled": "Actualización del skill cancelada por el usuario.",
        "msg_delete_cancelled": "Eliminación del skill cancelada por el usuario.",
        "confirm_overwrite_title": "¿Sobrescribir skill existente?",
        "confirm_overwrite_message": "Sobrescribir el skill \"{name}\". Su descripción y contenido serán reemplazados.\nDescripción actual: {description}",
        "status_overwrite_cancelled": "Sobrescritura cancelada por el usuario.",
        "msg_overwrite_cancelled": "Sobrescritura del skill cancelada por el usuario.",
        "err_confirmation_unavailable": "No se puede mostrar la confirmación en este contexto (no hay canal de eventos interactivo). Desactiva REQUIRE_CONFIRMATION en las valves para continuar sin confirmación.",
        "no_description": "(sin descripción)",
    },
    "it-IT": {
        "status_listing": "Elenco delle skill in corso...",
        "status_showing": "Lettura dei dettagli della skill...",
        "status_installing": "Installazione della skill da URL...",
        "status_installing_batch": "Installazione di {total} skill in corso...",
        "status_discovering_skills": "Scoperta di skills in {url}...",
        "status_creating": "Creazione della skill...",
        "status_updating": "Aggiornamento della skill...",
        "status_deleting": "Eliminazione della skill...",
        "status_done": "Fatto.",
        "status_list_done": "Trovate {count} skill ({active_count} attive).",
        "status_show_done": "Skill caricata: {name}.",
        "status_install_done": "Skill installata: {name}.",
        "status_install_overwrite_done": "Skill installata aggiornando l'esistente: {name}.",
        "status_create_done": "Skill creata: {name}.",
        "status_create_overwrite_done": "Skill esistente aggiornata: {name}.",
        "status_update_done": "Skill aggiornata: {name}.",
        "status_delete_done": "Skill eliminata: {name}.",
        "status_install_batch_done": "Installazione batch completata: {succeeded} riuscite, {failed} non riuscite.",
        "err_unavailable": "Il modello OpenWebUI Skills non è disponibile in questo runtime.",
        "err_user_required": "È richiesto il contesto utente.",
        "err_name_required": "Il nome della skill è obbligatorio.",
        "err_not_found": "Skill non trovata.",
        "err_no_update_fields": "Nessun campo da aggiornare fornito.",
        "err_url_required": "L'URL della skill è obbligatoria.",
        "err_install_fetch": "Impossibile recuperare il contenuto della skill dall'URL.",
        "err_install_parse": "Impossibile analizzare il pacchetto/contenuto della skill.",
        "err_invalid_url": "URL non valido. Sono supportati solo URL http(s).",
        "msg_created": "Skill creata con successo.",
        "msg_updated": "Skill aggiornata con successo.",
        "msg_deleted": "Skill eliminata con successo.",
        "msg_installed": "Skill installata con successo.",
        "confirm_update_title": "Aggiornare la skill?",
        "confirm_update_message": "Aggiornare la skill \"{name}\".\nDescrizione: {description}",
        "confirm_delete_title": "Eliminare la skill?",
        "confirm_delete_message": "Eliminare definitivamente la skill \"{name}\". L'operazione non può essere annullata.\nDescrizione: {description}",
        "status_update_cancelled": "Aggiornamento annullato dall'utente.",
        "status_delete_cancelled": "Eliminazione annullata dall'utente.",
        "msg_update_cancelled": "Aggiornamento della skill annullato dall'utente.",
        "msg_delete_cancelled": "Eliminazione della skill annullata dall'utente.",
        "confirm_overwrite_title": "Sovrascrivere la skill esistente?",
        "confirm_overwrite_message": "Sovrascrivere la skill \"{name}\". La descrizione e il contenuto saranno sostituiti.\nDescrizione attuale: {description}",
        "status_overwrite_cancelled": "Sovrascrittura annullata dall'utente.",
        "msg_overwrite_cancelled": "Sovrascrittura della skill annullata dall'utente.",
        "err_confirmation_unavailable": "Impossibile mostrare la conferma in questo contesto (nessun canale di eventi interattivo). Disattiva REQUIRE_CONFIRMATION nelle valvole per procedere senza conferma.",
        "no_description": "(nessuna descrizione)",
    },
    "vi-VN": {
        "status_listing": "Đang liệt kê kỹ năng của bạn...",
        "status_showing": "Đang đọc chi tiết kỹ năng...",
        "status_installing": "Đang cài đặt kỹ năng từ URL...",
        "status_installing_batch": "Đang cài đặt {total} kỹ năng...",
        "status_discovering_skills": "Đang phát hiện kỹ năng trong {url}...",
        "status_creating": "Đang tạo kỹ năng...",
        "status_updating": "Đang cập nhật kỹ năng...",
        "status_deleting": "Đang xóa kỹ năng...",
        "status_done": "Hoàn tất.",
        "status_list_done": "Đã tìm thấy {count} kỹ năng ({active_count} đang bật).",
        "status_show_done": "Đã tải kỹ năng: {name}.",
        "status_install_done": "Cài đặt kỹ năng hoàn tất: {name}.",
        "status_install_overwrite_done": "Đã cài đặt bằng cách cập nhật kỹ năng hiện có: {name}.",
        "status_create_done": "Tạo kỹ năng hoàn tất: {name}.",
        "status_create_overwrite_done": "Đã cập nhật kỹ năng cùng tên: {name}.",
        "status_update_done": "Cập nhật kỹ năng hoàn tất: {name}.",
        "status_delete_done": "Xóa kỹ năng hoàn tất: {name}.",
        "status_install_batch_done": "Cài đặt hàng loạt hoàn tất: thành công {succeeded}, thất bại {failed}.",
        "err_unavailable": "Mô hình OpenWebUI Skills không khả dụng trong môi trường hiện tại.",
        "err_user_required": "Cần có ngữ cảnh người dùng.",
        "err_name_required": "Tên kỹ năng là bắt buộc.",
        "err_not_found": "Không tìm thấy kỹ năng.",
        "err_no_update_fields": "Không có trường nào để cập nhật.",
        "err_url_required": "URL kỹ năng là bắt buộc.",
        "err_install_fetch": "Không thể tải nội dung kỹ năng từ URL.",
        "err_install_parse": "Không thể phân tích gói/nội dung kỹ năng.",
        "err_invalid_url": "URL không hợp lệ. Chỉ hỗ trợ URL http(s).",
        "msg_created": "Tạo kỹ năng thành công.",
        "msg_updated": "Cập nhật kỹ năng thành công.",
        "msg_deleted": "Xóa kỹ năng thành công.",
        "msg_installed": "Cài đặt kỹ năng thành công.",
        "confirm_update_title": "Cập nhật kỹ năng?",
        "confirm_update_message": "Cập nhật kỹ năng \"{name}\".\nMô tả: {description}",
        "confirm_delete_title": "Xóa kỹ năng?",
        "confirm_delete_message": "Xóa vĩnh viễn kỹ năng \"{name}\". Hành động này không thể hoàn tác.\nMô tả: {description}",
        "status_update_cancelled": "Người dùng đã hủy cập nhật.",
        "status_delete_cancelled": "Người dùng đã hủy xóa.",
        "msg_update_cancelled": "Người dùng đã hủy cập nhật kỹ năng.",
        "msg_delete_cancelled": "Người dùng đã hủy xóa kỹ năng.",
        "confirm_overwrite_title": "Ghi đè kỹ năng đã tồn tại?",
        "confirm_overwrite_message": "Ghi đè kỹ năng \"{name}\". Mô tả và nội dung sẽ bị thay thế.\nMô tả hiện tại: {description}",
        "status_overwrite_cancelled": "Người dùng đã hủy ghi đè.",
        "msg_overwrite_cancelled": "Người dùng đã hủy ghi đè kỹ năng.",
        "err_confirmation_unavailable": "Không thể hiển thị xác nhận trong ngữ cảnh này (không có kênh sự kiện tương tác). Tắt REQUIRE_CONFIRMATION trong valves để tiếp tục mà không cần xác nhận.",
        "no_description": "(không có mô tả)",
    },
    "id-ID": {
        "status_listing": "Sedang menampilkan daftar skill Anda...",
        "status_showing": "Sedang membaca detail skill...",
        "status_installing": "Sedang memasang skill dari URL...",
        "status_installing_batch": "Sedang memasang {total} skill...",
        "status_discovering_skills": "Sedang mencari skill di {url}...",
        "status_creating": "Sedang membuat skill...",
        "status_updating": "Sedang memperbarui skill...",
        "status_deleting": "Sedang menghapus skill...",
        "status_done": "Selesai.",
        "status_list_done": "Ditemukan {count} skill ({active_count} aktif).",
        "status_show_done": "Skill dimuat: {name}.",
        "status_install_done": "Skill berhasil dipasang: {name}.",
        "status_install_overwrite_done": "Skill dipasang dengan memperbarui skill yang ada: {name}.",
        "status_create_done": "Skill berhasil dibuat: {name}.",
        "status_create_overwrite_done": "Skill dengan nama sama berhasil diperbarui: {name}.",
        "status_update_done": "Skill berhasil diperbarui: {name}.",
        "status_delete_done": "Skill berhasil dihapus: {name}.",
        "status_install_batch_done": "Pemasangan batch selesai: {succeeded} berhasil, {failed} gagal.",
        "err_unavailable": "Model OpenWebUI Skills tidak tersedia di runtime ini.",
        "err_user_required": "Konteks pengguna diperlukan.",
        "err_name_required": "Nama skill wajib diisi.",
        "err_not_found": "Skill tidak ditemukan.",
        "err_no_update_fields": "Tidak ada field pembaruan yang diberikan.",
        "err_url_required": "URL skill wajib diisi.",
        "err_install_fetch": "Gagal mengambil konten skill dari URL.",
        "err_install_parse": "Gagal mem-parsing paket/konten skill.",
        "err_invalid_url": "URL tidak valid. Hanya URL http(s) yang didukung.",
        "msg_created": "Skill berhasil dibuat.",
        "msg_updated": "Skill berhasil diperbarui.",
        "msg_deleted": "Skill berhasil dihapus.",
        "msg_installed": "Skill berhasil dipasang.",
        "confirm_update_title": "Perbarui skill?",
        "confirm_update_message": "Perbarui skill \"{name}\".\nDeskripsi: {description}",
        "confirm_delete_title": "Hapus skill?",
        "confirm_delete_message": "Hapus skill \"{name}\" secara permanen. Tindakan ini tidak dapat dibatalkan.\nDeskripsi: {description}",
        "status_update_cancelled": "Pembaruan dibatalkan oleh pengguna.",
        "status_delete_cancelled": "Penghapusan dibatalkan oleh pengguna.",
        "msg_update_cancelled": "Pembaruan skill dibatalkan oleh pengguna.",
        "msg_delete_cancelled": "Penghapusan skill dibatalkan oleh pengguna.",
        "confirm_overwrite_title": "Timpa skill yang ada?",
        "confirm_overwrite_message": "Timpa skill \"{name}\". Deskripsi dan kontennya akan diganti.\nDeskripsi saat ini: {description}",
        "status_overwrite_cancelled": "Penimpaan dibatalkan oleh pengguna.",
        "msg_overwrite_cancelled": "Penimpaan skill dibatalkan oleh pengguna.",
        "err_confirmation_unavailable": "Tidak dapat menampilkan konfirmasi dalam konteks ini (tidak ada saluran event interaktif). Nonaktifkan REQUIRE_CONFIRMATION di valves untuk melanjutkan tanpa konfirmasi.",
        "no_description": "(tanpa deskripsi)",
    },
}

FALLBACK_MAP = {
    "zh": "zh-CN",
    "zh-TW": "zh-TW",
    "zh-HK": "zh-HK",
    "en": "en-US",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "it": "it-IT",
    "vi": "vi-VN",
    "id": "id-ID",
}


def _resolve_language(user_language: str) -> str:
    """Normalize user language code to a supported translation key."""
    value = str(user_language or "").strip()
    if not value:
        return "en-US"

    normalized = value.replace("_", "-")

    if normalized in TRANSLATIONS:
        return normalized

    lower_to_lang = {k.lower(): k for k in TRANSLATIONS.keys()}
    if normalized.lower() in lower_to_lang:
        return lower_to_lang[normalized.lower()]

    if normalized in FALLBACK_MAP:
        return FALLBACK_MAP[normalized]

    lower_fallback = {k.lower(): v for k, v in FALLBACK_MAP.items()}
    if normalized.lower() in lower_fallback:
        return lower_fallback[normalized.lower()]

    base = normalized.split("-")[0].lower()
    return lower_fallback.get(base, "en-US")


def _t(lang: str, key: str, **kwargs) -> str:
    """Return translated text for key with safe formatting."""
    lang_key = _resolve_language(lang)
    text = TRANSLATIONS.get(lang_key, TRANSLATIONS["en-US"]).get(
        key, TRANSLATIONS["en-US"].get(key, key)
    )
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


async def _get_user_context(
    __user__: Optional[dict],
    __event_call__: Optional[Any] = None,
    __request__: Optional[Any] = None,
) -> Dict[str, str]:
    """Extract robust user context with frontend language fallback."""
    if isinstance(__user__, (list, tuple)):
        user_data = __user__[0] if __user__ else {}
    elif isinstance(__user__, dict):
        user_data = __user__
    else:
        user_data = {}

    user_language = user_data.get("language", "en-US")

    if __request__ and hasattr(__request__, "headers"):
        accept_lang = __request__.headers.get("accept-language", "")
        if accept_lang:
            user_language = accept_lang.split(",")[0].split(";")[0]

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
        except Exception as e:
            logger.warning(f"Failed to retrieve frontend language: {e}")

    return {
        "user_id": str(user_data.get("id", "")).strip(),
        "user_name": user_data.get("name", "User"),
        "user_language": user_language,
    }


async def _resolve_awaitable_compat(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


async def _call_openwebui_compat(
    func: Any,
    *args: Any,
    prefer_thread_for_sync: bool = False,
    **kwargs: Any,
) -> Any:
    if prefer_thread_for_sync and not iscoroutinefunction(func):
        result = await asyncio.to_thread(func, *args, **kwargs)
    else:
        result = func(*args, **kwargs)
    return await _resolve_awaitable_compat(result)



async def _emit_notification(
    emitter: Optional[Any],
    content: str,
    ntype: str = "info",
):
    """Emit notification event (info, success, warning, error)."""
    if emitter:
        await emitter(
            {"type": "notification", "data": {"type": ntype, "content": content}}
        )


async def _emit_status(
    valves,
    emitter: Optional[Any],
    description: str,
    done: bool = False,
):
    """Emit status event to OpenWebUI status bar when enabled."""
    if valves.SHOW_STATUS and emitter:
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done},
            }
        )


async def _request_confirmation(
    event_call: Optional[Any],
    title: str,
    message: str,
) -> Optional[bool]:
    """Prompt the user for a yes/no confirmation via __event_call__.
    Returns True if confirmed, False if the user declined, or None if no
    interactive event channel is available (caller decides how to handle).
    """
    if not event_call:
        return None
    try:
        result = await _call_openwebui_compat(
            event_call,
            {
                "type": "confirmation",
                "data": {"title": title, "message": message},
            },
        )
    except Exception as e:
        logger.warning(f"Confirmation prompt failed: {e}")
        return None
    # Only trust an explicit bool True/False from the event channel.
    # Any other truthy value (e.g. an error dict returned on channel disconnect)
    # must be treated as unavailable so callers can block the destructive action.
    if isinstance(result, bool):
        return result
    return None


def _format_description_for_prompt(description: Any, lang: str, max_len: int = 200) -> str:
    """Render a skill description for inclusion in a confirmation dialog."""
    text = str(description or "").strip()
    if not text:
        return _t(lang, "no_description")
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _require_skills_model():
    """Ensure OpenWebUI Skills model APIs are available."""
    if Skills is None or SkillForm is None or SkillMeta is None:
        raise RuntimeError("skills_model_unavailable")


async def _user_skills(user_id: str, access: str = "read") -> List[Any]:
    """Load user-scoped skills using OpenWebUI Skills model."""
    return await _call_openwebui_compat(
        Skills.get_skills_by_user_id,
        user_id,
        access,
        prefer_thread_for_sync=True,
    ) or []


async def _find_skill(
    user_id: str,
    skill_id: str = "",
    name: str = "",
) -> Optional[Any]:
    """Find a skill by id or case-insensitive name within user scope."""
    skills = await _user_skills(user_id, "read")
    target_id = (skill_id or "").strip()
    target_name = (name or "").strip().lower()

    for skill in skills:
        sid = str(getattr(skill, "id", "") or "")
        sname = str(getattr(skill, "name", "") or "")
        if target_id and sid == target_id:
            return skill
        if target_name and sname.lower() == target_name:
            return skill
    return None


def _extract_folder_name_from_url(url: str) -> str:
    """Extract folder name from GitHub URL path.
    Examples:
      - https://github.com/.../tree/main/skills/xlsx -> xlsx
      - https://github.com/.../blob/main/skills/SKILL.md -> skills
      - https://raw.githubusercontent.com/.../main/skills/SKILL.md -> skills
    """
    try:
        # Remove query string and fragments
        path = url.split("?")[0].split("#")[0]
        # Get last path component
        parts = path.rstrip("/").split("/")
        if parts:
            last = parts[-1]
            # Skip if it's a file extension
            if "." not in last or last.startswith("."):
                return last
            # Return parent directory if it's a filename
            if len(parts) > 1:
                return parts[-2]
    except Exception:
        pass
    return ""


async def _discover_skills_from_github_directory(
    valves, url: str, lang: str
) -> List[str]:
    """
    Discover all skill subdirectories from a GitHub tree URL.
    Uses GitHub Git Trees API to find all SKILL.md files recursively.

    Example: https://github.com/anthropics/skills/tree/main/skills
    Returns: List of individual skill tree URLs for each directory containing SKILL.md
    """
    skill_urls = []
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)(/.*)?\Z", url)
    if not match:
        return skill_urls

    owner = match.group(1)
    repo = match.group(2)
    branch = match.group(3)
    target_path = (match.group(4) or "").strip("/")

    try:
        # Use recursive git trees API to find all SKILL.md files in the repository
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response_bytes = await _fetch_bytes(valves, api_url)
        data = json.loads(response_bytes.decode("utf-8"))
        
        if "tree" in data:
            for item in data["tree"]:
                item_path = item.get("path", "")
                
                # Check for SKILL.md paths (case-insensitive for convenience)
                if not item_path.lower().endswith("skill.md"):
                    continue
                    
                # If a specific target path was provided (like /skills), we only discover skills inside it
                if target_path:
                    # Must be exactly the target_path/SKILL.md or inside the target_path/ directory
                    if not (item_path.startswith(f"{target_path}/") or item_path == f"{target_path}/SKILL.md"):
                        continue
                    
                # Get the directory containing SKILL.md
                if "/" in item_path:
                    skill_dir = item_path.rsplit("/", 1)[0]
                    skill_url = f"https://github.com/{owner}/{repo}/tree/{branch}/{skill_dir}"
                else:
                    skill_url = f"https://github.com/{owner}/{repo}/tree/{branch}"
                    
                # De-duplicate
                if skill_url not in skill_urls:
                    skill_urls.append(skill_url)

        skill_urls.sort()
    except Exception as e:
        logger.warning(f"Failed to discover skills from GitHub directory {url}: {e}")
        
    return skill_urls


def _is_github_repo_root(url: str) -> bool:
    """Check if URL is a GitHub repo root (e.g., https://github.com/owner/repo)."""
    match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", url)
    return match is not None


def _normalize_github_repo_url(url: str) -> str:
    """Convert GitHub repo root URL to tree discovery URL (assuming main/master branch)."""
    match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", url)
    if match:
        owner = match.group(1)
        repo = match.group(2)
        # Try main branch first, API will handle if it doesn't exist
        return f"https://github.com/{owner}/{repo}/tree/main"
    return url


def _resolve_github_tree_urls(url: str) -> List[str]:
    """For GitHub tree URLs, resolve to direct file URL.

    Example: https://github.com/anthropics/skills/tree/main/skills/xlsx
    Returns: [
        https://raw.githubusercontent.com/anthropics/skills/main/skills/xlsx/SKILL.md,
    ]
    """
    urls = []
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)(/.*)?\Z", url)
    if match:
        owner = match.group(1)
        repo = match.group(2)
        branch = match.group(3)
        path = match.group(4) or ""
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}{path}"
        # Only look for SKILL.md
        urls.append(f"{base}/SKILL.md")
    return urls


def _normalize_url(url: str) -> str:
    """Normalize supported URLs (GitHub blob -> raw, tree -> try direct files first)."""
    value = (url or "").strip()
    if not value.startswith("http://") and not value.startswith("https://"):
        raise ValueError("invalid_url")

    # Handle GitHub blob URLs -> convert to raw
    if "github.com" in value and "/blob/" in value:
        value = value.replace("github.com", "raw.githubusercontent.com")
        value = value.replace("/blob/", "/")

    # Note: GitHub tree URLs are handled separately in install_skill
    # via _resolve_github_tree_urls()

    return value


def _is_safe_url(valves, url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that URL is safe for downloading from trusted domains.

    Checks:
    1. URL must use http/https scheme
    2. Hostname must be in the trusted domains whitelist

    Returns: Tuple of (is_safe: bool, error_message: Optional[str])
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").strip()

        if not hostname:
            return False, "URL is malformed: missing hostname"

        # Check scheme: only http/https allowed
        if parsed.scheme not in ("http", "https"):
            return False, f"URL scheme not allowed: {parsed.scheme}"

        # Domain whitelist check (enforced)
        trusted_domains = [
            d.strip().lower()
            for d in (valves.TRUSTED_DOMAINS or "").split(",")
            if d.strip()
        ]

        if not trusted_domains:
            return False, "No trusted domains configured."

        hostname_lower = hostname.lower()

        # Check if hostname matches any trusted domain (exact or subdomain)
        is_trusted = False
        for trusted_domain in trusted_domains:
            if hostname_lower == trusted_domain or hostname_lower.endswith(
                "." + trusted_domain
            ):
                is_trusted = True
                break

        if not is_trusted:
            return (
                False,
                f"Domain '{hostname}' not in whitelist. Allowed: {', '.join(trusted_domains)}",
            )

        return True, None
    except Exception as e:
        return False, f"URL validation error: {e}"


async def _fetch_bytes(valves, url: str) -> bytes:
    """Fetch bytes from URL with timeout guard and SSRF protection."""
    # Validate URL safety before fetching
    is_safe, error_message = _is_safe_url(valves, url)
    if not is_safe:
        raise ValueError(error_message or "Unsafe URL")

    def _sync_fetch(target: str) -> bytes:
        with urllib.request.urlopen(
            target, timeout=valves.INSTALL_FETCH_TIMEOUT
        ) as resp:
            return resp.read()

    return await asyncio.wait_for(
        asyncio.to_thread(_sync_fetch, url),
        timeout=valves.INSTALL_FETCH_TIMEOUT + 1.0,
    )


_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


def _normalize_newlines(text: str) -> str:
    """Normalize CRLF/CR text to LF for stable frontmatter parsing."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_matching_quotes(value: str) -> str:
    """Remove matching wrapping quotes from a scalar value."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _collect_frontmatter_block(lines: List[str], start_index: int) -> Tuple[List[str], int]:
    """Collect indented block lines until the next top-level frontmatter key."""
    block_lines: List[str] = []
    index = start_index

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            block_lines.append("")
            index += 1
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and _FRONTMATTER_KEY_RE.match(line):
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


def _fold_yaml_block(lines: List[str]) -> str:
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


def _parse_frontmatter_scalars(frontmatter_text: str) -> Dict[str, str]:
    """Parse simple top-level YAML frontmatter scalars, including block scalars."""
    lines = _normalize_newlines(frontmatter_text).split("\n")
    metadata: Dict[str, str] = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or line.startswith(" "):
            index += 1
            continue

        match = _FRONTMATTER_KEY_RE.match(line)
        if not match:
            index += 1
            continue

        key = match.group(1)
        raw_value = match.group(2).lstrip()

        if raw_value[:1] in {"|", ">"}:
            block_lines, index = _collect_frontmatter_block(lines, index + 1)
            metadata[key] = (
                "\n".join(block_lines).strip()
                if raw_value.startswith("|")
                else _fold_yaml_block(block_lines)
            )
            continue

        block_lines, next_index = _collect_frontmatter_block(lines, index + 1)
        if block_lines:
            segments = [_strip_matching_quotes(raw_value)] + [
                segment.strip() for segment in block_lines
            ]
            metadata[key] = _fold_yaml_block(segments)
            index = next_index
            continue

        metadata[key] = _strip_matching_quotes(raw_value)
        index += 1

    return metadata


def _parse_skill_md_meta(content: str, fallback_name: str) -> Tuple[str, str, str]:
    """Parse markdown skill content into (name, description, body)."""
    normalized_content = _normalize_newlines(content)
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", normalized_content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = normalized_content[fm_match.end() :].strip()
        metadata = _parse_frontmatter_scalars(fm_text)
        name = (
            metadata.get("name")
            or metadata.get("title")
            or fallback_name
        ).strip()
        description = (metadata.get("description") or "").strip()
        return name, description, body

    stripped_content = normalized_content.strip()
    h1_match = re.search(r"^#\s+(.+)$", stripped_content, re.MULTILINE)
    name = h1_match.group(1).strip() if h1_match else fallback_name
    return name, "", stripped_content


def _append_source_url_to_content(content: str, url: str, lang: str = "en-US") -> str:
    """
    Append installation source URL information to skill content.
    Adds a reference link at the bottom of the content.
    """
    if not content or not url:
        return content

    # Remove any existing source references (to prevent duplication when updating)
    content = re.sub(
        r"\n*---\n+\*\*Installation Source.*?\*\*:.*?\n+---\n*$",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Determine the appropriate language for the label
    source_label = {
        "en-US": "Installation Source",
        "zh-CN": "安装源",
        "zh-TW": "安裝來源",
        "zh-HK": "安裝來源",
        "ja-JP": "インストールソース",
        "ko-KR": "설치 소스",
        "fr-FR": "Source d'installation",
        "de-DE": "Installationsquelle",
        "es-ES": "Fuente de instalación",
    }.get(lang, "Installation Source")

    reference_text = {
        "en-US": "For additional related files or documentation, you can reference the installation source below:",
        "zh-CN": "如需获取相关文件或文档，可以参考下面的安装源：",
        "zh-TW": "如需獲取相關檔案或文件，可以參考下面的安裝來源：",
        "zh-HK": "如需獲取相關檔案或文件，可以參考下面的安裝來源：",
        "ja-JP": "関連ファイルまたはドキュメントについては、以下のインストールソースを参照できます：",
        "ko-KR": "관련 파일 또는 문서를 확인하려면 아래 설치 소스를 참조할 수 있습니다:",
        "fr-FR": "Pour obtenir des fichiers ou des documents connexes, vous pouvez vous reporter à la source d'installation ci-dessous :",
        "de-DE": "Für zusätzliche verwandte Dateien oder Dokumentation können Sie die folgende Installationsquelle referenzieren:",
        "es-ES": "Para archivos o documentación relacionados, puede consultar la siguiente fuente de instalación:",
    }.get(
        lang,
        "For additional related files or documentation, you can reference the installation source below:",
    )

    # Append source URL with reference
    source_block = (
        f"\n\n---\n**{source_label}**: [{url}]({url})\n\n*{reference_text}*\n---"
    )
    return content + source_block


def _safe_extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """
    Safely extract a ZIP file, validating member paths to prevent path traversal.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            # Check for path traversal attempts
            member_path = Path(extract_dir) / member
            try:
                # Ensure the resolved path is within extract_dir
                member_path.resolve().relative_to(extract_dir.resolve())
            except ValueError:
                # Path is outside extract_dir (traversal attempt)
                logger.warning(f"Skipping unsafe ZIP member: {member}")
                continue

            # Extract the member
            zf.extract(member, extract_dir)


def _safe_extract_tar(tar_path: Path, extract_dir: Path) -> None:
    """
    Safely extract a TAR file, validating member paths to prevent path traversal.
    """
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            # Check for path traversal attempts
            member_path = Path(extract_dir) / member.name
            try:
                # Ensure the resolved path is within extract_dir
                member_path.resolve().relative_to(extract_dir.resolve())
            except ValueError:
                # Path is outside extract_dir (traversal attempt)
                logger.warning(f"Skipping unsafe TAR member: {member.name}")
                continue

            # Extract the member
            tf.extract(member, extract_dir)


def _extract_skill_from_archive(payload: bytes) -> Tuple[str, str, str]:
    """Extract SKILL.md from zip/tar archives with path traversal protection."""
    with tempfile.TemporaryDirectory(prefix="owui-skill-") as tmp:
        root = Path(tmp)
        archive_path = root / "pkg"
        archive_path.write_bytes(payload)

        extract_dir = root / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        extracted = False
        try:
            _safe_extract_zip(archive_path, extract_dir)
            extracted = True
        except Exception as e:
            logger.debug(f"Failed to extract as ZIP: {e}")
            pass

        if not extracted:
            try:
                _safe_extract_tar(archive_path, extract_dir)
                extracted = True
            except Exception as e:
                logger.debug(f"Failed to extract as TAR: {e}")
                pass

        if not extracted:
            raise ValueError("install_parse")

        # Only look for SKILL.md
        candidates = list(extract_dir.rglob("SKILL.md"))
        if not candidates:
            raise ValueError("install_parse")

        chosen = candidates[0]
        text = chosen.read_text(encoding="utf-8", errors="ignore")
        fallback_name = chosen.parent.name or "installed-skill"
        return _parse_skill_md_meta(text, fallback_name)


async def _install_single_skill(
    valves,
    url: str,
    name: str,
    user_id: str,
    lang: str,
    overwrite: bool,
    __event_emitter__: Optional[Any] = None,
    __event_call__: Optional[Any] = None,
) -> Dict[str, Any]:
    """Internal method to install a single skill from URL."""
    try:
        if not (url or "").strip():
            raise ValueError(_t(lang, "err_url_required"))

        # Extract potential folder name from URL before normalization
        url_folder = _extract_folder_name_from_url(url).strip()

        parsed_name = ""
        parsed_desc = ""
        parsed_body = ""
        payload = None

        # Special handling for GitHub tree URLs
        if "github.com" in url and "/tree/" in url:
            fallback_file_urls = _resolve_github_tree_urls(url)
            # Try to fetch SKILL.md directly from the tree path
            for file_url in fallback_file_urls:
                try:
                    payload = await _fetch_bytes(valves, file_url)
                    if payload:
                        break
                except Exception:
                    continue

            if payload:
                # Successfully fetched direct file
                text = payload.decode("utf-8", errors="ignore")
                fallback = url_folder or "installed-skill"
                parsed_name, parsed_desc, parsed_body = _parse_skill_md_meta(
                    text, fallback
                )
            else:
                # No direct file found at this GitHub tree URL path
                raise ValueError(f"Could not find SKILL.md in {url}")
        else:
            # Handle other URL types (blob, direct markdown, archives)
            normalized = _normalize_url(url)
            payload = await _fetch_bytes(valves, normalized)

            if normalized.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
                parsed_name, parsed_desc, parsed_body = _extract_skill_from_archive(
                    payload
                )
            else:
                text = payload.decode("utf-8", errors="ignore")
                # Use extracted folder name as fallback
                fallback = url_folder or "installed-skill"
                parsed_name, parsed_desc, parsed_body = _parse_skill_md_meta(
                    text, fallback
                )

        final_name = (name or parsed_name or url_folder or "installed-skill").strip()
        final_desc = (parsed_desc or final_name).strip()
        final_content = (parsed_body or final_desc).strip()

        # Append installation source URL to the skill content
        final_content = _append_source_url_to_content(final_content, url, lang)

        if not final_name:
            raise ValueError(_t(lang, "err_name_required"))

        existing = await _find_skill(user_id=user_id, name=final_name)
        # install_skill always overwrites by default (overwrite=True);
        # ALLOW_OVERWRITE_ON_CREATE valve also controls this.
        allow_overwrite = overwrite or valves.ALLOW_OVERWRITE_ON_CREATE
        if existing:
            sid = str(getattr(existing, "id", "") or "")
            if not allow_overwrite:
                # Should not normally reach here since install defaults overwrite=True
                return {
                    "error": f"Skill already exists: {final_name}",
                    "hint": "Pass overwrite=true to replace the existing skill.",
                }
            if valves.REQUIRE_CONFIRMATION:
                confirmed = await _request_confirmation(
                    __event_call__,
                    _t(lang, "confirm_overwrite_title"),
                    _t(
                        lang,
                        "confirm_overwrite_message",
                        name=final_name,
                        description=_format_description_for_prompt(
                            getattr(existing, "description", ""), lang
                        ),
                    ),
                )
                if confirmed is None:
                    # Batch caller aggregates per-URL results; do not raise.
                    return {
                        "error": _t(lang, "err_confirmation_unavailable"),
                        "url": url,
                    }
                if not confirmed:
                    await _emit_status(
                        valves,
                        __event_emitter__,
                        _t(lang, "status_overwrite_cancelled"),
                        done=True,
                    )
                    return {
                        "cancelled": True,
                        "action": "overwrite_cancelled",
                        "id": sid,
                        "name": final_name,
                        "source_url": url,
                        "message": _t(lang, "msg_overwrite_cancelled"),
                    }
            updated = await _call_openwebui_compat(
                Skills.update_skill_by_id,
                sid,
                {
                    "name": final_name,
                    "description": final_desc,
                    "content": final_content,
                    "is_active": True,
                },
                prefer_thread_for_sync=True,
            )
            await _emit_status(valves, __event_emitter__, _t(lang, "status_install_overwrite_done", name=final_name),
                done=True,
            )
            return {
                "success": True,
                "action": "updated",
                "id": str(getattr(updated, "id", "") or sid),
                "name": final_name,
                "source_url": url,
            }

        new_skill = await _call_openwebui_compat(
            Skills.insert_new_skill,
            user_id=user_id,
            form_data=SkillForm(
                id=str(uuid.uuid4()),
                name=final_name,
                description=final_desc,
                content=final_content,
                meta=SkillMeta(),
                is_active=True,
            ),
            prefer_thread_for_sync=True,
        )

        await _emit_status(valves, __event_emitter__, _t(lang, "status_install_done", name=final_name),
            done=True,
        )
        return {
            "success": True,
            "action": "installed",
            "id": str(getattr(new_skill, "id", "") or ""),
            "name": final_name,
            "source_url": url,
        }
    except Exception as e:
        key = None
        if str(e) in {"invalid_url", "install_parse"}:
            key = "err_invalid_url" if str(e) == "invalid_url" else "err_install_parse"
        msg = (
            _t(lang, key)
            if key
            else (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
        )
        logger.error(f"_install_single_skill failed for {url}: {msg}", exc_info=True)
        return {"error": msg, "url": url}


class Tools:
    """OpenWebUI native tools for simple skill lifecycle management."""

    class Valves(BaseModel):
        """Configurable plugin valves."""

        SHOW_STATUS: bool = Field(
            default=True,
            description="Whether to show operation status updates.",
        )
        REQUIRE_CONFIRMATION: bool = Field(
            default=True,
            description="Require an interactive yes/no confirmation before destructive actions (update_skill, delete_skill, and overwrite on create_skill/install_skill). Disable to allow these without prompting.",
        )
        ALLOW_OVERWRITE_ON_CREATE: bool = Field(
            default=True,
            description="Allow create_skill/install_skill to overwrite same-name skill by default.",
        )
        INSTALL_FETCH_TIMEOUT: float = Field(
            default=12.0,
            description="Timeout in seconds for URL fetch when installing a skill.",
        )
        TRUSTED_DOMAINS: str = Field(
            default="github.com,huggingface.co,githubusercontent.com",
            description="Comma-separated list of primary trusted domains for skill downloads (always enforced). URLs with domains matching or containing these primary domains (including subdomains) are allowed. E.g., 'github.com' allows github.com and *.github.com.",
        )

    def __init__(self):
        """Initialize plugin valves."""
        self.valves = self.Valves()

    async def list_skills(
        self,
        include_content: bool = False,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """List current user's OpenWebUI skills."""
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_listing"))

            skills = await _user_skills(user_id, "read")
            rows = []
            for skill in skills:
                row = {
                    "id": str(getattr(skill, "id", "") or ""),
                    "name": getattr(skill, "name", ""),
                    "description": getattr(skill, "description", ""),
                    "is_active": bool(getattr(skill, "is_active", True)),
                    "updated_at": str(getattr(skill, "updated_at", "") or ""),
                }
                if include_content:
                    row["content"] = getattr(skill, "content", "")
                rows.append(row)

            rows.sort(key=lambda x: (x.get("name") or "").lower())
            active_count = sum(1 for row in rows if row.get("is_active"))

            await _emit_status(self.valves, __event_emitter__, _t(
                    lang,
                    "status_list_done",
                    count=len(rows),
                    active_count=active_count,
                ),
                done=True,
            )
            return {"count": len(rows), "skills": rows}
        except Exception as e:
            msg = (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            return {"error": msg}

    async def show_skill(
        self,
        skill_id: str = "",
        name: str = "",
        include_content: bool = True,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Show one skill by id or name."""
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_showing"))

            skill = await _find_skill(user_id=user_id, skill_id=skill_id, name=name)
            if not skill:
                raise ValueError(_t(lang, "err_not_found"))

            result = {
                "id": str(getattr(skill, "id", "") or ""),
                "name": getattr(skill, "name", ""),
                "description": getattr(skill, "description", ""),
                "is_active": bool(getattr(skill, "is_active", True)),
                "updated_at": str(getattr(skill, "updated_at", "") or ""),
            }
            if include_content:
                result["content"] = getattr(skill, "content", "")

            skill_name = result.get("name") or result.get("id") or "unknown"
            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_show_done", name=skill_name),
                done=True,
            )
            return result
        except Exception as e:
            msg = (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            return {"error": msg}

    async def install_skill(
        self,
        url: str,
        name: str = "",
        overwrite: bool = True,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Install one or more skills from URL(s), with support for GitHub directory auto-discovery.

        Args:
            url: A single URL string OR a JSON array of URL strings for batch install.
                 Examples:
                   Single: "https://github.com/owner/repo/tree/main/skills/xlsx"
                   Directory: "https://github.com/owner/repo/tree/main/skills"
                   Batch:  ["https://github.com/owner/repo/tree/main/skills/xlsx",
                            "https://github.com/owner/repo/tree/main/skills/csv"]
            name: Optional custom name for the skill (single install only).
            overwrite: If True (default), overwrites any existing skill with the same name.

        Auto-Discovery Feature:
        If a GitHub tree URL points to a directory that contains multiple skill subdirectories,
        this tool will automatically discover all subdirectories and batch install them.
        Example: "https://github.com/anthropics/skills/tree/main/skills" will auto-discover
        all skill folders under /skills and install them all at once.

        Supported URL formats:
        - GitHub tree URL: https://github.com/owner/repo/tree/branch/path/to/skill
        - GitHub skill directory (auto-discovery): https://github.com/owner/repo/tree/branch/path
        - GitHub blob URL: https://github.com/owner/repo/blob/branch/path/SKILL.md
        - Raw markdown URL: https://raw.githubusercontent.com/.../SKILL.md
        - Archive URL: https://example.com/skill.zip (must contain SKILL.md)
        """
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            # Stage 1: Check for directory auto-discovery (GitHub URLs)
            if isinstance(url, str) and "github.com" in url:
                # Auto-convert repo root URL to tree discovery URL
                if _is_github_repo_root(url):
                    await _emit_status(self.valves, __event_emitter__, _t(lang, "status_detecting_repo_root", url=url[-50:]),
                    )
                    url = _normalize_github_repo_url(url)

                # If URL contains /tree/, auto-discover all skill subdirectories
                if "/tree/" in url:
                    await _emit_status(self.valves, __event_emitter__, _t(lang, "status_discovering_skills", url=(url or "")[-50:]),
                    )
                    discover_fn = _discover_skills_from_github_directory
                    discovered = []
                    if callable(discover_fn):
                        discovered = await discover_fn(self.valves, url, lang)
                    else:
                        logger.warning(
                            "_discover_skills_from_github_directory is unavailable on current Tools instance."
                        )
                    if discovered:
                        # Auto-discovered subdirectories, treat as batch
                        url = discovered

            # Stage 2: Check if url is a list/tuple (batch mode)
            if isinstance(url, (list, tuple)):
                urls = list(url)
                if not urls:
                    raise ValueError(_t(lang, "err_url_required"))

                # Deduplicate URLs while preserving order
                seen_urls = set()
                unique_urls = []
                duplicates_removed = 0
                for url_item in urls:
                    url_str = str(url_item).strip()
                    if url_str not in seen_urls:
                        unique_urls.append(url_str)
                        seen_urls.add(url_str)
                    else:
                        duplicates_removed += 1

                # Notify if duplicates were found
                if duplicates_removed > 0:
                    await _emit_notification(
                        __event_emitter__,
                        _t(
                            lang,
                            "status_batch_duplicates_removed",
                            count=duplicates_removed,
                        ),
                        ntype="info",
                    )

                await _emit_status(self.valves, __event_emitter__, _t(lang, "status_installing_batch", total=len(unique_urls)),
                )

                results = []
                installed_names = {}  # Track installed skill names to detect duplicates

                for idx, single_url in enumerate(unique_urls, 1):
                    result = await _install_single_skill(
                        self.valves,
                        url=single_url,
                        name="",  # Batch mode doesn't support per-item names
                        user_id=user_id,
                        lang=lang,
                        overwrite=overwrite,
                        __event_emitter__=__event_emitter__,
                        __event_call__=__event_call__,
                    )

                    # Track installed name to detect duplicates
                    if result.get("success"):
                        installed_name = result.get("name", "").lower()
                        if installed_name in installed_names:
                            # Duplicate skill name detected
                            prev_url = installed_names[installed_name]
                            logger.warning(
                                f"Duplicate skill name detected: '{result.get('name')}' "
                                f"from {single_url} (previously from {prev_url})"
                            )
                            await _emit_notification(
                                __event_emitter__,
                                _t(
                                    lang,
                                    "status_duplicate_skill_name",
                                    name=result.get("name"),
                                    action=result.get("action", "installed"),
                                ),
                                ntype="warning",
                            )
                        else:
                            installed_names[installed_name] = single_url

                    results.append(result)

                # Summary
                success_count = sum(1 for r in results if r.get("success"))
                error_count = len(results) - success_count

                await _emit_status(self.valves, __event_emitter__, _t(
                        lang,
                        "status_install_batch_done",
                        succeeded=success_count,
                        failed=error_count,
                    ),
                    done=True,
                )

                return {
                    "batch": True,
                    "total": len(results),
                    "succeeded": success_count,
                    "failed": error_count,
                    "results": results,
                }
            else:
                # Single mode
                if not (url or "").strip():
                    raise ValueError(_t(lang, "err_url_required"))

                await _emit_status(self.valves, __event_emitter__, _t(lang, "status_installing"))

                result = await _install_single_skill(
                    self.valves,
                    url=str(url).strip(),
                    name=name,
                    user_id=user_id,
                    lang=lang,
                    overwrite=overwrite,
                    __event_emitter__=__event_emitter__,
                    __event_call__=__event_call__,
                )
                return result

        except Exception as e:
            key = None
            if str(e) in {"invalid_url", "install_parse"}:
                key = (
                    "err_invalid_url"
                    if str(e) == "invalid_url"
                    else "err_install_parse"
                )
            msg = (
                _t(lang, key)
                if key
                else (
                    _t(lang, "err_unavailable")
                    if str(e) == "skills_model_unavailable"
                    else str(e)
                )
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            logger.error(f"install_skill failed: {msg}", exc_info=True)
            return {"error": msg}

    async def create_skill(
        self,
        name: str,
        description: str = "",
        content: str = "",
        overwrite: bool = True,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Create a new skill, or update same-name skill when overwrite is enabled."""
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            skill_name = (name or "").strip()
            if not skill_name:
                raise ValueError(_t(lang, "err_name_required"))

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_creating"))

            existing = await _find_skill(user_id=user_id, name=skill_name)
            allow_overwrite = overwrite or self.valves.ALLOW_OVERWRITE_ON_CREATE

            final_description = (description or skill_name).strip()
            final_content = (content or final_description).strip()

            if existing:
                if not allow_overwrite:
                    return {
                        "error": f"Skill already exists: {skill_name}",
                        "hint": "Use overwrite=true to update existing skill.",
                    }

                sid = str(getattr(existing, "id", "") or "")
                if self.valves.REQUIRE_CONFIRMATION:
                    confirmed = await _request_confirmation(
                        __event_call__,
                        _t(lang, "confirm_overwrite_title"),
                        _t(
                            lang,
                            "confirm_overwrite_message",
                            name=skill_name,
                            description=_format_description_for_prompt(
                                getattr(existing, "description", ""), lang
                            ),
                        ),
                    )
                    if confirmed is None:
                        raise ValueError(_t(lang, "err_confirmation_unavailable"))
                    if not confirmed:
                        await _emit_status(
                            self.valves,
                            __event_emitter__,
                            _t(lang, "status_overwrite_cancelled"),
                            done=True,
                        )
                        return {
                            "cancelled": True,
                            "action": "overwrite_cancelled",
                            "id": sid,
                            "name": skill_name,
                            "message": _t(lang, "msg_overwrite_cancelled"),
                        }
                updated = await _call_openwebui_compat(
                    Skills.update_skill_by_id,
                    sid,
                    {
                        "name": skill_name,
                        "description": final_description,
                        "content": final_content,
                        "is_active": True,
                    },
                    prefer_thread_for_sync=True,
                )
                await _emit_status(self.valves, __event_emitter__, _t(lang, "status_create_overwrite_done", name=skill_name),
                    done=True,
                )
                return {
                    "success": True,
                    "action": "updated",
                    "id": str(getattr(updated, "id", "") or sid),
                    "name": skill_name,
                }

            new_skill = await _call_openwebui_compat(
                Skills.insert_new_skill,
                user_id=user_id,
                form_data=SkillForm(
                    id=str(uuid.uuid4()),
                    name=skill_name,
                    description=final_description,
                    content=final_content,
                    meta=SkillMeta(),
                    is_active=True,
                ),
                prefer_thread_for_sync=True,
            )

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_create_done", name=skill_name),
                done=True,
            )
            return {
                "success": True,
                "action": "created",
                "id": str(getattr(new_skill, "id", "") or ""),
                "name": skill_name,
            }
        except Exception as e:
            msg = (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            logger.error(f"create_skill failed: {msg}", exc_info=True)
            return {"error": msg}

    async def update_skill(
        self,
        skill_id: str = "",
        name: str = "",
        new_name: str = "",
        description: str = "",
        content: str = "",
        is_active: Optional[bool] = None,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Modify an existing skill by updating one or more fields.

        Locate skill by `skill_id` or `name` (case-insensitive). Update any of:
        - `new_name`: Rename the skill (checked for name uniqueness)
        - `description`: Update skill description
        - `content`: Modify skill code/content
        - `is_active`: Enable or disable the skill

        Returns updated skill info and list of modified fields.
        """
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_updating"))

            skill = await _find_skill(user_id=user_id, skill_id=skill_id, name=name)
            if not skill:
                raise ValueError(_t(lang, "err_not_found"))

            # Get skill ID early for collision detection
            sid = str(getattr(skill, "id", "") or "")

            updates: Dict[str, Any] = {}
            if new_name.strip():
                # Check for name collision with other skills
                new_name_clean = new_name.strip()
                # Check if another skill already has this name (case-insensitive)
                for other_skill in await _user_skills(user_id, "read"):
                    other_id = str(getattr(other_skill, "id", "") or "")
                    other_name = str(getattr(other_skill, "name", "") or "")
                    # Skip the current skill being updated
                    if other_id == sid:
                        continue
                    if other_name.lower() == new_name_clean.lower():
                        return {
                            "error": f'Another skill already has the name "{new_name_clean}".',
                            "hint": "Choose a different name or delete the conflicting skill first.",
                        }

                updates["name"] = new_name_clean
            if description.strip():
                updates["description"] = description.strip()
            if content.strip():
                updates["content"] = content.strip()
            if is_active is not None:
                updates["is_active"] = bool(is_active)

            if not updates:
                raise ValueError(_t(lang, "err_no_update_fields"))

            if self.valves.REQUIRE_CONFIRMATION:
                current_name = str(getattr(skill, "name", "") or sid)
                confirmed = await _request_confirmation(
                    __event_call__,
                    _t(lang, "confirm_update_title"),
                    _t(
                        lang,
                        "confirm_update_message",
                        name=current_name,
                        description=_format_description_for_prompt(
                            getattr(skill, "description", ""), lang
                        ),
                    ),
                )
                if confirmed is None:
                    raise ValueError(_t(lang, "err_confirmation_unavailable"))
                if not confirmed:
                    await _emit_status(
                        self.valves,
                        __event_emitter__,
                        _t(lang, "status_update_cancelled"),
                        done=True,
                    )
                    return {
                        "cancelled": True,
                        "id": sid,
                        "name": current_name,
                        "message": _t(lang, "msg_update_cancelled"),
                    }

            updated = await _call_openwebui_compat(Skills.update_skill_by_id, sid, updates, prefer_thread_for_sync=True)
            updated_name = str(
                getattr(updated, "name", "")
                or updates.get("name")
                or getattr(skill, "name", "")
                or sid
            )

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_update_done", name=updated_name),
                done=True,
            )
            return {
                "success": True,
                "id": str(getattr(updated, "id", "") or sid),
                "name": str(
                    getattr(updated, "name", "")
                    or updates.get("name")
                    or getattr(skill, "name", "")
                ),
                "updated_fields": list(updates.keys()),
            }
        except Exception as e:
            msg = (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            return {"error": msg}

    async def delete_skill(
        self,
        skill_id: str = "",
        name: str = "",
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Delete one skill by id or name."""
        user_ctx = await _get_user_context(__user__, __event_call__, __request__)
        lang = user_ctx["user_language"]
        user_id = user_ctx["user_id"]

        try:
            _require_skills_model()
            if not user_id:
                raise ValueError(_t(lang, "err_user_required"))

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_deleting"))

            skill = await _find_skill(user_id=user_id, skill_id=skill_id, name=name)
            if not skill:
                raise ValueError(_t(lang, "err_not_found"))

            sid = str(getattr(skill, "id", "") or "")
            sname = str(getattr(skill, "name", "") or "")

            if self.valves.REQUIRE_CONFIRMATION:
                confirmed = await _request_confirmation(
                    __event_call__,
                    _t(lang, "confirm_delete_title"),
                    _t(
                        lang,
                        "confirm_delete_message",
                        name=sname or "unknown",
                        description=_format_description_for_prompt(
                            getattr(skill, "description", ""), lang
                        ),
                    ),
                )
                if confirmed is None:
                    raise ValueError(_t(lang, "err_confirmation_unavailable"))
                if not confirmed:
                    await _emit_status(
                        self.valves,
                        __event_emitter__,
                        _t(lang, "status_delete_cancelled"),
                        done=True,
                    )
                    return {
                        "cancelled": True,
                        "id": sid,
                        "name": sname,
                        "message": _t(lang, "msg_delete_cancelled"),
                    }

            await _call_openwebui_compat(Skills.delete_skill_by_id, sid, prefer_thread_for_sync=True)
            deleted_name = sname or sid or "unknown"

            await _emit_status(self.valves, __event_emitter__, _t(lang, "status_delete_done", name=deleted_name),
                done=True,
            )
            return {
                "success": True,
                "id": sid,
                "name": sname,
            }
        except Exception as e:
            msg = (
                _t(lang, "err_unavailable")
                if str(e) == "skills_model_unavailable"
                else str(e)
            )
            await _emit_status(self.valves, __event_emitter__, msg, done=True)
            return {"error": msg}
