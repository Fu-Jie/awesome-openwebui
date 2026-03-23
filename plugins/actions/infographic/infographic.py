"""
title: Smart Infographic
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPgogIDxsaW5lIHgxPSIxMiIgeTE9IjIwIiB4Mj0iMTIiIHkyPSIxMCIgLz4KICA8bGluZSB4MT0iMTgiIHkxPSIyMCIgeDI9IjE4IiB5Mj0iNCIgLz4KICA8bGluZSB4MT0iNiIgeTE9IjIwIiB4Mj0iNiIgeTI9IjE2IiAvPgo8L3N2Zz4=
version: 1.6.0
openwebui_id: ad6f0c7f-c571-4dea-821d-8e71697274cf
description: AI-powered infographic generator based on AntV Infographic. Supports professional templates, auto-icon matching, and SVG/PNG downloads.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Callable, Awaitable
import logging
import time
import re
from fastapi import Request
from datetime import datetime
import asyncio

from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TRANSLATIONS = {
    "en-US": {
        "status_starting": "Smart Infographic is starting, generating infographic for you...",
        "error_no_content": "Unable to retrieve valid user message content.",
        "error_text_too_short": "Text content is too short ({len} characters), unable to perform effective analysis. Please provide at least {min_len} characters of text.",
        "status_analyzing": "Smart Infographic: Analyzing text structure in depth...",
        "status_drawing": "Smart Infographic: Drawing completed!",
        "notification_success": "Mind map has been generated, {user_name}!",
        "error_processing": "Smart Infographic processing failed: {error}",
        "error_user_facing": "Sorry, Smart Infographic encountered an error during processing: {error}.\nPlease check the Open WebUI backend logs for more details.",
        "status_failed": "Smart Infographic: Processing failed.",
        "notification_failed": "Smart Infographic generation failed, {user_name}!",
        "status_rendering_image": "Smart Infographic: Rendering image...",
        "status_image_generated": "Smart Infographic: Image generated!",
        "notification_image_success": "Mind map image has been generated, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "User:",
        "ui_time": "Time:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Reset",
        "ui_zoom_in": "+",
        "ui_depth_select": "Expand Level",
        "ui_depth_all": "Expand All",
        "ui_depth_2": "Level 2",
        "ui_depth_3": "Level 3",
        "ui_fullscreen": "Fullscreen",
        "ui_theme": "Theme",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Unable to load infographic: Missing valid content.",
        "html_error_load_failed": "⚠️ Resource loading failed, please try again later.",
        "js_done": "Done",
        "js_failed": "Failed",
        "js_generating": "Generating...",
        "js_filename": "infographic.png",
        "js_upload_failed": "Upload failed: ",
        "md_image_alt": "🧠 Infographic",
    },
    "zh-CN": {
        "status_starting": "信息图已启动，正在为您生成信息图...",
        "error_no_content": "无法获取有效的用户消息内容。",
        "error_text_too_short": "文本内容过短（{len}字符），无法进行有效分析。请提供至少{min_len}字符的文本。",
        "status_analyzing": "信息图：深入分析文本结构...",
        "status_drawing": "信息图：绘制完成！",
        "notification_success": "信息图已生成，{user_name}！",
        "error_processing": "信息图处理失败：{error}",
        "error_user_facing": "抱歉，信息图在处理时遇到错误：{error}。\n请检查Open WebUI后端日志获取更多详情。",
        "status_failed": "信息图：处理失败。",
        "notification_failed": "信息图生成失败，{user_name}！",
        "status_rendering_image": "信息图：正在渲染图片...",
        "status_image_generated": "信息图：图片已生成！",
        "notification_image_success": "信息图图片已生成，{user_name}！",
        "ui_title": "🧠 智能信息图",
        "ui_user": "用户：",
        "ui_time": "时间：",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "缩小",
        "ui_zoom_reset": "重置",
        "ui_zoom_in": "放大",
        "ui_depth_select": "展开层级",
        "ui_depth_all": "全部展开",
        "ui_depth_2": "展开 2 级",
        "ui_depth_3": "展开 3 级",
        "ui_fullscreen": "全屏",
        "ui_theme": "主题",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ 无法加载信息图：缺少有效内容。",
        "html_error_load_failed": "⚠️ 资源加载失败，请稍后重试。",
        "js_done": "完成",
        "js_failed": "失败",
        "js_generating": "生成中...",
        "js_filename": "信息图.png",
        "js_upload_failed": "上传失败：",
        "md_image_alt": "🧠 信息图",
    },
    "zh-HK": {
        "status_starting": "信息圖已啟動，正在為您生成信息圖...",
        "error_no_content": "無法獲取有效的用戶消息內容。",
        "error_text_too_short": "文本內容過短（{len}字元），無法進行有效分析。請提供至少{min_len}字元的文本。",
        "status_analyzing": "信息圖：深入分析文本結構...",
        "status_drawing": "信息圖：繪製完成！",
        "notification_success": "信息圖已生成，{user_name}！",
        "error_processing": "信息圖處理失敗：{error}",
        "error_user_facing": "抱歉，信息圖在處理時遇到錯誤：{error}。\n請檢查Open WebUI後端日誌獲取更多詳情。",
        "status_failed": "信息圖：處理失敗。",
        "notification_failed": "信息圖生成失敗，{user_name}！",
        "status_rendering_image": "信息圖：正在渲染圖片...",
        "status_image_generated": "信息圖：圖片已生成！",
        "notification_image_success": "信息圖圖片已生成，{user_name}！",
        "ui_title": "🧠 智能信息圖",
        "ui_user": "用戶：",
        "ui_time": "時間：",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "縮小",
        "ui_zoom_reset": "重置",
        "ui_zoom_in": "放大",
        "ui_depth_select": "展開層級",
        "ui_depth_all": "全部展開",
        "ui_depth_2": "展開 2 級",
        "ui_depth_3": "展開 3 級",
        "ui_fullscreen": "全屏",
        "ui_theme": "主題",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ 無法加載信息圖：缺少有效內容。",
        "html_error_load_failed": "⚠️ 資源加載失敗，請稍後重試。",
        "js_done": "完成",
        "js_failed": "失敗",
        "js_generating": "生成中...",
        "js_filename": "信息圖.png",
        "js_upload_failed": "上傳失敗：",
        "md_image_alt": "🧠 信息圖",
    },
    "zh-TW": {
        "status_starting": "信息圖已啟動，正在為您生成信息圖...",
        "error_no_content": "無法獲取有效的用戶消息內容。",
        "error_text_too_short": "文本內容過短（{len}字元），無法進行有效分析。請提供至少{min_len}字元的文本。",
        "status_analyzing": "信息圖：深入分析文本結構...",
        "status_drawing": "信息圖：繪製完成！",
        "notification_success": "信息圖已生成，{user_name}！",
        "error_processing": "信息圖處理失敗：{error}",
        "error_user_facing": "抱歉，信息圖在處理時遇到錯誤：{error}。\n請檢查Open WebUI後端日誌獲取更多詳情。",
        "status_failed": "信息圖：處理失敗。",
        "notification_failed": "信息圖生成失敗，{user_name}！",
        "status_rendering_image": "信息圖：正在渲染圖片...",
        "status_image_generated": "信息圖：圖片已生成！",
        "notification_image_success": "信息圖圖片已生成，{user_name}！",
        "ui_title": "🧠 智能信息圖",
        "ui_user": "用戶：",
        "ui_time": "時間：",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "縮小",
        "ui_zoom_reset": "重置",
        "ui_zoom_in": "放大",
        "ui_depth_select": "展開層級",
        "ui_depth_all": "全部展開",
        "ui_depth_2": "展開 2 級",
        "ui_depth_3": "展開 3 級",
        "ui_fullscreen": "全屏",
        "ui_theme": "主題",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ 無法加載信息圖：缺少有效內容。",
        "html_error_load_failed": "⚠️ 資源加載失敗，請稍後重試。",
        "js_done": "完成",
        "js_failed": "失敗",
        "js_generating": "生成中...",
        "js_filename": "信息圖.png",
        "js_upload_failed": "上傳失敗：",
        "md_image_alt": "🧠 信息圖",
    },
    "ko-KR": {
        "status_starting": "스마트 마인드맵이 시작되었습니다, 마인드맵을 생성 중입니다...",
        "error_no_content": "유효한 사용자 메시지 내용을 가져올 수 없습니다.",
        "error_text_too_short": "텍스트 내용이 너무 짧아({len}자), 효과적인 분석을 수행할 수 없습니다. 최소 {min_len}자 이상의 텍스트를 제공해 주세요.",
        "status_analyzing": "스마트 마인드맵: 텍스트 구조 심층 분석 중...",
        "status_drawing": "스마트 마인드맵: 그리기 완료!",
        "notification_success": "마인드맵이 생성되었습니다, {user_name}님!",
        "error_processing": "스마트 마인드맵 처리 실패: {error}",
        "error_user_facing": "죄송합니다, 스마트 마인드맵 처리 중 오류가 발생했습니다: {error}.\n자세한 내용은 Open WebUI 백엔드 로그를 확인해 주세요.",
        "status_failed": "스마트 마인드맵: 처리 실패.",
        "notification_failed": "스마트 마인드맵 생성 실패, {user_name}님!",
        "status_rendering_image": "스마트 마인드맵: 이미지 렌더링 중...",
        "status_image_generated": "스마트 마인드맵: 이미지 생성됨!",
        "notification_image_success": "마인드맵 이미지가 생성되었습니다, {user_name}님!",
        "ui_title": "🧠 스마트 마인드맵",
        "ui_user": "사용자:",
        "ui_time": "시간:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "초기화",
        "ui_zoom_in": "+",
        "ui_depth_select": "레벨 확장",
        "ui_depth_all": "모두 확장",
        "ui_depth_2": "레벨 2",
        "ui_depth_3": "레벨 3",
        "ui_fullscreen": "전체 화면",
        "ui_theme": "테마",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ 마인드맵을 로드할 수 없습니다: 유효한 내용이 없습니다.",
        "html_error_load_failed": "⚠️ 리소스 로드 실패, 나중에 다시 시도해 주세요.",
        "js_done": "완료",
        "js_failed": "실패",
        "js_generating": "생성 중...",
        "js_filename": "infographic.png",
        "js_upload_failed": "업로드 실패: ",
        "md_image_alt": "🧠 마인드맵",
    },
    "ja-JP": {
        "status_starting": "スマートマインドマップが起動しました。マインドマップを生成しています...",
        "error_no_content": "有効なユーザーメッセージの内容を取得できませんでした。",
        "error_text_too_short": "テキストの内容が短すぎるため（{len}文字）、効果的な分析を実行できません。少なくとも{min_len}文字のテキストを提供してください。",
        "status_analyzing": "スマートマインドマップ：テキスト構造を詳細に分析中...",
        "status_drawing": "スマートマインドマップ：描画完了！",
        "notification_success": "マインドマップが生成されました、{user_name}さん！",
        "error_processing": "スマートマインドマップ処理失敗：{error}",
        "error_user_facing": "申し訳ありません、スマートマインドマップの処理中にエラーが発生しました：{error}。\n詳細については、Open WebUIバックエンドログを確認してください。",
        "status_failed": "スマートマインドマップ：処理失敗。",
        "notification_failed": "スマートマインドマップ生成失敗、{user_name}さん！",
        "status_rendering_image": "スマートマインドマップ：画像レンダリング中...",
        "status_image_generated": "スマートマインドマップ：画像生成完了！",
        "notification_image_success": "マインドマップ画像が生成されました、{user_name}さん！",
        "ui_title": "🧠 スマートマインドマップ",
        "ui_user": "ユーザー：",
        "ui_time": "時間：",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "リセット",
        "ui_zoom_in": "+",
        "ui_depth_select": "レベル展開",
        "ui_depth_all": "すべて展開",
        "ui_depth_2": "レベル2",
        "ui_depth_3": "レベル3",
        "ui_fullscreen": "全画面",
        "ui_theme": "テーマ",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ マインドマップを読み込めません：有効なコンテンツがありません。",
        "html_error_load_failed": "⚠️ リソースの読み込みに失敗しました。後でもう一度お試しください。",
        "js_done": "完了",
        "js_failed": "失敗",
        "js_generating": "生成中...",
        "js_filename": "infographic.png",
        "js_upload_failed": "アップロード失敗：",
        "md_image_alt": "🧠 マインドマップ",
    },
    "fr-FR": {
        "status_starting": "Smart Infographic démarre, génération de la carte heuristique en cours...",
        "error_no_content": "Impossible de récupérer le contenu valide du message utilisateur.",
        "error_text_too_short": "Le contenu du texte est trop court ({len} caractères), impossible d'effectuer une analyse efficace. Veuillez fournir au moins {min_len} caractères de texte.",
        "status_analyzing": "Smart Infographic : Analyse approfondie de la structure du texte...",
        "status_drawing": "Smart Infographic : Dessin terminé !",
        "notification_success": "La carte heuristique a été générée, {user_name} !",
        "error_processing": "Échec du traitement de Smart Infographic : {error}",
        "error_user_facing": "Désolé, Smart Infographic a rencontré une erreur lors du traitement : {error}.\nVeuillez vérifier les journaux backend d'Open WebUI pour plus de détails.",
        "status_failed": "Smart Infographic : Échec du traitement.",
        "notification_failed": "Échec de la génération de la carte heuristique, {user_name} !",
        "status_rendering_image": "Smart Infographic : Rendu de l'image...",
        "status_image_generated": "Smart Infographic : Image générée !",
        "notification_image_success": "L'image de la carte heuristique a été générée, {user_name} !",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Utilisateur :",
        "ui_time": "Heure :",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Rénitialiser",
        "ui_zoom_in": "+",
        "ui_depth_select": "Niveau d'expansion",
        "ui_depth_all": "Tout développer",
        "ui_depth_2": "Niveau 2",
        "ui_depth_3": "Niveau 3",
        "ui_fullscreen": "Plein écran",
        "ui_theme": "Thème",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Impossible de charger la carte heuristique : contenu valide manquant.",
        "html_error_load_failed": "⚠️ Échec du chargement des ressources, veuillez réessayer plus tard.",
        "js_done": "Terminé",
        "js_failed": "Échec",
        "js_generating": "Génération...",
        "js_filename": "carte_heuristique.png",
        "js_upload_failed": "Échec du téléchargement : ",
        "md_image_alt": "🧠 Carte Heuristique",
    },
    "de-DE": {
        "status_starting": "Smart Infographic startet, Infographic wird für Sie erstellt...",
        "error_no_content": "Gültiger Inhalt der Benutzernachricht konnte nicht abgerufen werden.",
        "error_text_too_short": "Der Textinhalt ist zu kurz ({len} Zeichen), eine effektive Analyse ist nicht möglich. Bitte geben Sie mindestens {min_len} Zeichen Text an.",
        "status_analyzing": "Smart Infographic: Detaillierte Analyse der Textstruktur...",
        "status_drawing": "Smart Infographic: Zeichnen abgeschlossen!",
        "notification_success": "Infographic wurde erstellt, {user_name}!",
        "error_processing": "Smart Infographic Verarbeitung fehlgeschlagen: {error}",
        "error_user_facing": "Entschuldigung, bei der Verarbeitung von Smart Infographic ist ein Fehler aufgetreten: {error}.\nBitte überprüfen Sie die Open WebUI Backend-Protokolle für weitere Details.",
        "status_failed": "Smart Infographic: Verarbeitung fehlgeschlagen.",
        "notification_failed": "Erstellung der Infographic fehlgeschlagen, {user_name}!",
        "status_rendering_image": "Smart Infographic: Bild wird gerendert...",
        "status_image_generated": "Smart Infographic: Bild erstellt!",
        "notification_image_success": "Infographic-Bild wurde erstellt, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Benutzer:",
        "ui_time": "Zeit:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Zurücksetzen",
        "ui_zoom_in": "+",
        "ui_depth_select": "Ebene erweitern",
        "ui_depth_all": "Alles erweitern",
        "ui_depth_2": "Ebene 2",
        "ui_depth_3": "Ebene 3",
        "ui_fullscreen": "Vollbild",
        "ui_theme": "Thema",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Infographic kann nicht geladen werden: Gültiger Inhalt fehlt.",
        "html_error_load_failed": "⚠️ Ressourcenladen fehlgeschlagen, bitte versuchen Sie es später erneut.",
        "js_done": "Fertig",
        "js_failed": "Fehlgeschlagen",
        "js_generating": "Generiere...",
        "js_filename": "infographic.png",
        "js_upload_failed": "Upload fehlgeschlagen: ",
        "md_image_alt": "🧠 Infographic",
    },
    "es-ES": {
        "status_starting": "Smart Infographic se está iniciando, generando mapa mental para usted...",
        "error_no_content": "No se puede recuperar el contenido válido del mensaje del usuario.",
        "error_text_too_short": "El contenido del texto es demasiado corto ({len} caracteres), no se puede realizar un análisis efectivo. Proporcione al menos {min_len} caracteres de texto.",
        "status_analyzing": "Smart Infographic: Analizando la estructura del texto en profundidad...",
        "status_drawing": "Smart Infographic: ¡Dibujo completado!",
        "notification_success": "¡El mapa mental ha sido generado, {user_name}!",
        "error_processing": "Falló el procesamiento de Smart Infographic: {error}",
        "error_user_facing": "Lo sentimos, Smart Infographic encontró un error durante el procesamiento: {error}.\nConsulte los registros del backend de Open WebUI para más detalles.",
        "status_failed": "Smart Infographic: Procesamiento fallido.",
        "notification_failed": "¡La generación del mapa mental falló, {user_name}!",
        "status_rendering_image": "Smart Infographic: Renderizando imagen...",
        "status_image_generated": "Smart Infographic: ¡Imagen generada!",
        "notification_image_success": "¡La imagen del mapa mental ha sido generada, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Usuario:",
        "ui_time": "Hora:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Restablecer",
        "ui_zoom_in": "+",
        "ui_depth_select": "Expandir Nivel",
        "ui_depth_all": "Expandir Todo",
        "ui_depth_2": "Nivel 2",
        "ui_depth_3": "Nivel 3",
        "ui_fullscreen": "Pantalla completa",
        "ui_theme": "Tema",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ No se puede cargar el mapa mental: Falta contenido válido.",
        "html_error_load_failed": "⚠️ Falló la carga de recursos, inténtelo de nuevo más tarde.",
        "js_done": "Hecho",
        "js_failed": "Fallido",
        "js_generating": "Generando...",
        "js_filename": "mapa_mental.png",
        "js_upload_failed": "Carga fallida: ",
        "md_image_alt": "🧠 Mapa Mental",
    },
    "it-IT": {
        "status_starting": "Smart Infographic si sta avviando, generazione mappa mentale in corso...",
        "error_no_content": "Impossibile recuperare il contenuto valido del messaggio utente.",
        "error_text_too_short": "Il testo è troppo breve ({len} caratteri), impossibile eseguire un'analisi efficace. Fornire almeno {min_len} caratteri di testo.",
        "status_analyzing": "Smart Infographic: Analisi approfondita della struttura del testo...",
        "status_drawing": "Smart Infographic: Disegno completato!",
        "notification_success": "La mappa mentale è stata generata, {user_name}!",
        "error_processing": "Elaborazione Smart Infographic fallita: {error}",
        "error_user_facing": "Spiacenti, Smart Infographic ha riscontrato un errore durante l'elaborazione: {error}.\nControllare i log del backend di Open WebUI per ulteriori dettagli.",
        "status_failed": "Smart Infographic: Elaborazione fallita.",
        "notification_failed": "Generazione mappa mentale fallita, {user_name}!",
        "status_rendering_image": "Smart Infographic: Rendering immagine...",
        "status_image_generated": "Smart Infographic: Immagine generata!",
        "notification_image_success": "L'immagine della mappa mentale è stata generata, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Utente:",
        "ui_time": "Ora:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Reimposta",
        "ui_zoom_in": "+",
        "ui_depth_select": "Espandi Livello",
        "ui_depth_all": "Espandi Tutto",
        "ui_depth_2": "Livello 2",
        "ui_depth_3": "Livello 3",
        "ui_fullscreen": "Schermo intero",
        "ui_theme": "Tema",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Impossibile caricare la mappa mentale: Contenuto valido mancante.",
        "html_error_load_failed": "⚠️ Caricamento risorse fallito, riprovare più tardi.",
        "js_done": "Fatto",
        "js_failed": "Fallito",
        "js_generating": "Generazione...",
        "js_filename": "mappa_mentale.png",
        "js_upload_failed": "Caricamento fallito: ",
        "md_image_alt": "🧠 Mappa Mentale",
    },
    "vi-VN": {
        "status_starting": "Smart Infographic đang khởi động, đang tạo sơ đồ tư duy cho bạn...",
        "error_no_content": "Không thể lấy nội dung tin nhắn người dùng hợp lệ.",
        "error_text_too_short": "Nội dung văn bản quá ngắn ({len} ký tự), không thể thực hiện phân tích hiệu quả. Vui lòng cung cấp ít nhất {min_len} ký tự văn bản.",
        "status_analyzing": "Smart Infographic: Phân tích sâu cấu trúc văn bản...",
        "status_drawing": "Smart Infographic: Vẽ hoàn tất!",
        "notification_success": "Sơ đồ tư duy đã được tạo, {user_name}!",
        "error_processing": "Xử lý Smart Infographic thất bại: {error}",
        "error_user_facing": "Xin lỗi, Smart Infographic đã gặp lỗi trong quá trình xử lý: {error}.\nVui lòng kiểm tra nhật ký backend Open WebUI để biết thêm chi tiết.",
        "status_failed": "Smart Infographic: Xử lý thất bại.",
        "notification_failed": "Tạo sơ đồ tư duy thất bại, {user_name}!",
        "status_rendering_image": "Smart Infographic: Đang render hình ảnh...",
        "status_image_generated": "Smart Infographic: Hình ảnh đã tạo!",
        "notification_image_success": "Hình ảnh sơ đồ tư duy đã được tạo, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Người dùng:",
        "ui_time": "Thời gian:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Đặt lại",
        "ui_zoom_in": "+",
        "ui_depth_select": "Mở rộng Cấp độ",
        "ui_depth_all": "Mở rộng Tất cả",
        "ui_depth_2": "Cấp độ 2",
        "ui_depth_3": "Cấp độ 3",
        "ui_fullscreen": "Toàn màn hình",
        "ui_theme": "Chủ đề",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Không thể tải sơ đồ tư duy: Thiếu nội dung hợp lệ.",
        "html_error_load_failed": "⚠️ Tải tài nguyên thất bại, vui lòng thử lại sau.",
        "js_done": "Xong",
        "js_failed": "Thất bại",
        "js_generating": "Đang tạo...",
        "js_filename": "sodo_tuduy.png",
        "js_upload_failed": "Tải lên thất bại: ",
        "md_image_alt": "🧠 Sơ đồ Tư duy",
    },
    "id-ID": {
        "status_starting": "Smart Infographic sedang dimulai, membuat peta pikiran untuk Anda...",
        "error_no_content": "Tidak dapat mengambil konten pesan pengguna yang valid.",
        "error_text_too_short": "Konten teks terlalu pendek ({len} karakter), tidak dapat melakukan analisis efektif. Harap berikan setidaknya {min_len} karakter teks.",
        "status_analyzing": "Smart Infographic: Menganalisis struktur teks secara mendalam...",
        "status_drawing": "Smart Infographic: Menggambar selesai!",
        "notification_success": "Peta pikiran telah dibuat, {user_name}!",
        "error_processing": "Pemrosesan Smart Infographic gagal: {error}",
        "error_user_facing": "Maaf, Smart Infographic mengalami kesalahan saat memproses: {error}.\nSilakan periksa log backend Open WebUI untuk detail lebih lanjut.",
        "status_failed": "Smart Infographic: Pemrosesan gagal.",
        "notification_failed": "Pembuatan peta pikiran gagal, {user_name}!",
        "status_rendering_image": "Smart Infographic: Merender gambar...",
        "status_image_generated": "Smart Infographic: Gambar dibuat!",
        "notification_image_success": "Gambar peta pikiran telah dibuat, {user_name}!",
        "ui_title": "🧠 Smart Infographic",
        "ui_user": "Pengguna:",
        "ui_time": "Waktu:",
        "ui_download_png": "PNG",
        "ui_download_svg": "SVG",
        "ui_download_md": "Markdown",
        "ui_zoom_out": "-",
        "ui_zoom_reset": "Atur Ulang",
        "ui_zoom_in": "+",
        "ui_depth_select": "Perluas Level",
        "ui_depth_all": "Perluas Semua",
        "ui_depth_2": "Level 2",
        "ui_depth_3": "Level 3",
        "ui_fullscreen": "Layar Penuh",
        "ui_theme": "Tema",
        "ui_footer": "<b>Powered by</b> <a href='https://markmap.js.org/' target='_blank' rel='noopener noreferrer'>Markmap</a>",
        "html_error_missing_content": "⚠️ Tidak dapat memuat peta pikiran: Konten valid hilang.",
        "html_error_load_failed": "⚠️ Gagal memuat sumber daya, silakan coba lagi nanti.",
        "js_done": "Selesai",
        "js_failed": "Gagal",
        "js_generating": "Membuat...",
        "js_filename": "peta_pikiran.png",
        "js_upload_failed": "Unggah gagal: ",
        "md_image_alt": "🧠 Peta Pikiran",
    },
}

# =================================================================
# LLM Prompts
# =================================================================

SYSTEM_PROMPT_INFOGRAPHIC_ASSISTANT = """
You are a professional infographic design expert who can analyze user-provided text content and convert it into AntV Infographic syntax format.

## Important Language Rule
- **GENERATE CONTENT IN INPUT LANGUAGE**: You must generate the text content of the infographic in the **exact same language** as the user's input content (the text you are analyzing).
- **Format Consistency**: Even if this system prompt is in English, if the user input is in Chinese, the infographic content must be in Chinese. If input is Japanese, output Japanese.

## Infographic Syntax Specification

Infographic syntax is a Mermaid-like declarative syntax for describing infographic templates, data, and themes.

### Syntax Rules
- Entry uses `infographic <template-name>`
- Key-value pairs are separated by spaces, **absolutely NO colons allowed**
- Use two spaces for indentation
- Object arrays use `-` with line breaks

⚠️ **IMPORTANT WARNING: This is NOT YAML format!**
- ❌ Wrong: `children:` `items:` `data:` (with colons)
- ✅ Correct: `children` `items` `data` (without colons)

### Template Library & Selection Guide

Choose the most appropriate template based on content structure.

**Template Selection Guidelines (Official):**
- Strict sequential order (processes/steps/trends) → `sequence-*` series
  - Timeline → `sequence-timeline-simple`
  - Roadmap → `sequence-roadmap-vertical-simple`
  - Zigzag steps → `sequence-horizontal-zigzag-underline-text`
  - Snake steps → `sequence-snake-steps-compact-card`
- Listing viewpoints → `list-row-horizontal-icon-arrow` or `list-column-simple-vertical-arrow`
- Comparative analysis (A vs B) → `compare-binary-horizontal-underline-text-vs`
- SWOT analysis → `compare-swot`
- Hierarchical structure (tree) → `hierarchy-tree-tech-style-capsule-item`
- Data charts → `chart-*` series
- Quadrant analysis → `quadrant-quarter-simple-card`
- Grid lists (bullet points) → `list-grid-candy-card-lite`
- Relationship display → `relation-circle-icon-badge`

**Available Templates:**

*Sequence (时序/流程):*
`sequence-timeline-simple`, `sequence-roadmap-vertical-simple`, `sequence-horizontal-zigzag-underline-text`, 
`sequence-snake-steps-compact-card`, `sequence-zigzag-steps-underline-text`, `sequence-circular-simple`,
`sequence-pyramid-simple`, `sequence-ascending-steps`

*List (列表):*
`list-grid-candy-card-lite`, `list-grid-badge-card`, `list-row-horizontal-icon-arrow`,
`list-column-simple-vertical-arrow`, `list-column-done-list`

*Compare (对比):*
`compare-binary-horizontal-underline-text-vs`, `compare-binary-horizontal-simple-fold`,
`compare-hierarchy-left-right-circle-node-pill-badge`, `compare-swot`

*Hierarchy (层级):*
`hierarchy-tree-tech-style-capsule-item`, `hierarchy-tree-curved-line-rounded-rect-node`, `hierarchy-structure`

*Chart (图表):*
`chart-column-simple`, `chart-bar-plain-text`, `chart-line-plain-text`, 
`chart-pie-plain-text`, `chart-pie-donut-plain-text`, `chart-wordcloud`

*Other:*
`quadrant-quarter-simple-card`, `relation-circle-icon-badge`, `relation-dagre-flow-tb-simple-circle-node`

**Text Capacity by Template Type:**
- HIGH capacity (long descriptions OK): `list-column-*`, `compare-binary-*`, `sequence-timeline-*`
- MEDIUM capacity: `list-row-*`, `sequence-roadmap-*`
- LOW capacity (short text only): `list-grid-*`, `hierarchy-*`, `sequence-steps`

### Icon and Illustration Resources

**Icons (Iconify):**
- Format: `<collection>/<icon-name>`, e.g., `mdi/rocket-launch`
- Popular: `mdi/*` (Material Design), `fa/*` (Font Awesome), `bi/*` (Bootstrap)
- Examples: `mdi/code-tags`, `mdi/chart-line`, `mdi/account-group`, `mdi/cloud`

**Illustrations (unDraw):**
- Format: filename without .svg, e.g., `coding`, `team-work`
- Use `illus` field instead of `icon`

### 📊 Template to Data Field Mapping (CRITICAL)
For maximum rendering speed and stability, match the list identifier to the template kind structure. Do NOT just use `items` if a specific field exists:

| Template Prefix | Data Field Identifier | Core Variables on Items |
| :--- | :--- | :--- |
| `list-*` | **`lists`** | `label`, `desc`, `icon` |
| `sequence-*` | **`sequences`** | `label`, `desc` |
| `compare-*` | **`compares`** | `label`, `value`, `children` |
| `chart-*` | **`values`** | `label`, `value` |
| `hierarchy-*` | **`root` + `children`** | 嵌套嵌套组合 |

*Note: `items` can be used as a universal fallback adapter if template categorization is ambiguous.*

### Data Structure Examples

#### A. Standard List/Tree (Default)
Use `items` and `children` structure.

```infographic
infographic list-grid
data
  title Project Modules
  items
    - label Module A
      desc Description of A
    - label Module B
      desc Description of B
```


#### B. Binary Comparison
Use `items` for two sides and `children` for comparison points.

```infographic
infographic compare-binary
data
  title Advantages vs Disadvantages
  desc Compare two aspects side by side
  items
    - label Advantages
      children
        - label Strong R&D
          desc Leading technology and innovation capability
        - label High customer loyalty
          desc Repurchase rate over 60%
    - label Disadvantages
      children
        - label Weak brand exposure
          desc Insufficient marketing, low awareness
        - label Narrow channel coverage
          desc Limited online channels
```

#### C. SWOT Analysis
Use `children` to define the 4 quadrants (Strengths, Weaknesses, Opportunities, Threats).

```infographic
infographic compare-swot
data
  title Product SWOT Analysis
  items
    - label Internal Factors
      children
        - label Strengths
          children
            - label High Performance
            - label Low Cost
        - label Weaknesses
          children
            - label Limited Features
    - label External Factors
      children
        - label Opportunities
          children
            - label Growing Market
        - label Threats
          children
            - label New Competitors
```

#### D. Quadrant Chart
Use `items` for quadrants and `illus` for icons.

```infographic
infographic quadrant-quarter
data
  title Priority Matrix
  items
    - label High Importance
      children
        - label Urgent
          desc Do it now
          illus mdi/alert
        - label Not Urgent
          desc Schedule it
          illus mdi/calendar
    - label Low Importance
      children
        - label Urgent
          desc Delegate it
          illus mdi/account-arrow-right
        - label Not Urgent
          desc Delete it
          illus mdi/delete
```

#### E. Stylize Configuration
You can apply specific visual styles using the `theme` block.

**Supported Styles (`stylize`):**
- `rough`: Hand-drawn style
- `pattern`: Pattern fill
- `linear-gradient`: Linear gradient fill
- `radial-gradient`: Radial gradient fill

**Example (Rough Style):**
```infographic
infographic list-row-simple-horizontal-arrow
theme
  stylize rough
data
  ...
```

**Example (Gradient Style):**
```infographic
infographic chart-bar
theme
  stylize linear-gradient
data
  ...
```
#### F. Charts (Bar/Column/Line/Pie)
Use `items` with `label` and `value`.

```infographic
infographic chart-bar
data
  title Quarterly Revenue
  items
    - label Q1
      value 120
    - label Q2
      value 150
    - label Q3
      value 180
    - label Q4
      value 220
```

### Common Data Fields
- `label`: Main title/label (Required)
- `desc`: Description text
- `value`: Numeric value. **ONLY displayed on `chart-*` series templates**. For cards or lists, put data into `desc` instead.
- `icon`: Icon name (e.g., `mdi/home`, `mdi/account`) or `ref:search:<keyword>`
- `children`: Nested items (for trees, SWOT, etc.)
- `illus`: Illustration icon (specific to some templates like Quadrant)

### 📊 Data & Numeric Fields Standard
1. **Value Specification**: `value` MUST be a **pure number** (integer or float), without any symbols like `$`, `%`, or `¥`.
2. **Units Placement**: Put units or currency symbols into the `label` or `desc` instead.
   - ❌ Wrong: `value $1.234` / `value 5.2%`
   - ✅ Correct: `label USD ($)` -> `value 1.234` OR `label Rate` -> `desc 5.2%`

### ⚠️ Strict Styling & Layout Rules
1. **Color Palette (`palette`)**: MUST use space-separated naked Hex values. Do NOT use quotes (`"`) or commas (`,`).
   - ✅ Correct: `palette #4f46e5 #06b6d4 #10b981`
   - ❌ Wrong: `palette "#4f46e5", "#06b6d4"`
2. **Binary Compare (`compare-binary-*`)**: The root of `compares` tree MUST contain **EXACTLY TWO** comparison objects.

### Content Refinement Principles
1. **Brevity is King**: Infographics are visual. Keep text to a minimum.
2. **Title Limit**: Keep `label` (item titles) under 15 characters (approx. 10 Chinese characters).
3. **Description Limit**: Keep `desc` (item descriptions) under 40 characters (approx. 20 Chinese characters / 2 lines).
4. **Impact**: Use strong verbs and nouns. Avoid filler words.

## Output Requirements
1. **Language**: Output content in the user's language.
2. **Format**: Wrap output in ```infographic ... ```.
3. **No Colons**: Do NOT use colons after keys.
4. **Indentation**: Use 2 spaces.
"""

import json

USER_PROMPT_GENERATE_INFOGRAPHIC = """
Please analyze the following text content and convert its core information into AntV Infographic syntax format.

---
**User Context:**
User Name: {user_name}
Current Date/Time: {current_date_time_str}
User Language: {user_language}
OpenWebUI Theme: {user_theme}
---

**Text Content:**
{long_text_content}

Please select the most appropriate infographic template based on text characteristics and output standard infographic syntax. Pay attention to correct indentation format (two spaces).

**Visual Optimization Guide (MUST FOLLOW):**
- **Point-based Generation:** Infographics are not articles. Extract KEYWORDS ONLY, avoid complete sentences.
- **Main Title (`data.title`):** **MUST** be ≤ **15 Chinese characters** (or ≤30 English characters). Trim version numbers or details if needed.
- **Subtitle (`data.desc`):** **MUST** be ≤ **20 Chinese characters** (or ≤40 English characters).
- **Card Title (`label`):** **MUST** be ≤ **6 Chinese characters** (or ≤12 English characters). Use 2-4 keywords only.
- **Card Description (`desc`):** **MUST** be ≤ **12 Chinese characters** (or ≤24 English characters). Use short phrases.
- **Numeric Strictness:** `value` MUST be a pure number (no `$`, `%`, etc.). Append units to `label` or `desc` instead.
- **Dynamic Selection:** For multiple stats/currencies, use structures like `list-grid-*` or `list-row-*` for dense layouts.

⚠️ **CRITICAL**: If the original text is too long, you MUST rephrase and shorten it. Do NOT simply truncate with "...".
Examples:
- ❌ "多步任务与工具协作能力" → ✅ "多步任务协作"
- ❌ "Open WebUI v0.7.x 重大版本更新" → ✅ "v0.7 核心更新"
- ❌ "自动查找历史聊天记录" → ✅ "历史检索"
"""

# =================================================================
# HTML Container Template
# =================================================================

HTML_WRAPPER_TEMPLATE = """
<!-- OPENWEBUI_PLUGIN_OUTPUT -->
<!DOCTYPE html>
<html lang="{user_language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            margin: 0; 
            padding: 10px; 
            background-color: transparent; 
        }
        #main-container { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 20px; 
            align-items: flex-start; 
            width: 100%;
        }
        .plugin-item { 
            flex: 1 1 400px;
            min-width: 300px; 
            border-radius: 12px; 
            overflow: hidden; 
            transition: all 0.3s ease;
        }
        .plugin-item:hover {
            transform: translateY(-2px);
        }
        @media (max-width: 768px) { 
            .plugin-item { flex: 1 1 100%; } 
        }
        /* STYLES_INSERTION_POINT */
    </style>
</head>
<body>
    <div id="main-container">
        <!-- CONTENT_INSERTION_POINT -->
    </div>
    <!-- SCRIPTS_INSERTION_POINT -->
</body>
</html>
"""

# =================================================================
# CSS Style Template
# =================================================================

CSS_TEMPLATE_INFOGRAPHIC = """
:root {
    --ig-primary-color: #6366f1;
    --ig-secondary-color: #8b5cf6;
    --ig-tertiary-color: #10b981;
    --ig-background-color: #f8fafc;
    --ig-card-bg-color: #ffffff;
    --ig-text-color: #1e293b;
    --ig-muted-text-color: #64748b;
    --ig-border-color: #e2e8f0;
    --ig-header-gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
}
.infographic-container-wrapper.dark {
    --ig-primary-color: #818cf8;
    --ig-secondary-color: #a78bfa;
    --ig-tertiary-color: #34d399;
    --ig-background-color: #0f172a;
    --ig-card-bg-color: #1e293b;
    --ig-text-color: #f8fafc;
    --ig-muted-text-color: #94a3b8;
    --ig-border-color: #334155;
    --ig-header-gradient: linear-gradient(135deg, #4338ca, #6d28d9);
}
.infographic-container-wrapper {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6;
    color: var(--ig-text-color);
    background-color: var(--ig-background-color);
    height: 100%;
    display: flex;
    flex-direction: column;
}
.infographic-container-wrapper .header {
    background: var(--ig-header-gradient);
    color: white;
    padding: 20px 24px;
    text-align: center;
}
.infographic-container-wrapper .header h1 {
    margin: 0;
    font-size: 1.5em;
    font-weight: 600;
}
.infographic-container-wrapper .user-context {
    font-size: 0.8em;
    color: var(--ig-muted-text-color);
    background-color: var(--ig-card-bg-color);
    padding: 8px 16px;
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--ig-border-color);
}
.infographic-container-wrapper .content-area {
    padding: 20px;
    flex-grow: 1;
}
.infographic-container-wrapper .infographic-render-container {
    border-radius: 8px;
    padding: 16px;
    min-height: 600px;
    background: var(--ig-card-bg-color);
    overflow: visible;
    transition: height 0.3s ease;
}
.infographic-render-container svg text {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
}
.infographic-render-container svg foreignObject {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    line-height: 1.3 !important;
    overflow: visible !important;
}
.infographic-container-wrapper.dark .infographic-render-container svg text {
    fill: var(--ig-text-color) !important;
}
.infographic-container-wrapper.dark .infographic-render-container svg foreignObject * {
    color: var(--ig-text-color) !important;
}
/* Main title styles */
.infographic-render-container svg foreignObject[data-element-type="title"] > * {
    font-size: 1.3em !important;
    font-weight: 800 !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    word-break: break-word !important;
    display: -webkit-box !important;
    -webkit-line-clamp: 2 !important;
    -webkit-box-orient: vertical !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    text-align: center !important;
}
/* Page subtitle styles */
.infographic-render-container svg foreignObject[data-element-type="desc"] > * {
    font-size: 0.85em !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    word-break: break-word !important;
    overflow: visible !important;
    text-align: center !important;
    display: block !important;
    color: var(--ig-muted-text-color) !important;
}
/* Card title styles */
.infographic-render-container svg foreignObject[data-element-type="item-label"] > * {
    font-size: 0.9em !important;
    font-weight: 600 !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    word-break: break-word !important;
    display: -webkit-box !important;
    -webkit-line-clamp: 2 !important;
    -webkit-box-orient: vertical !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    padding-bottom: 2px !important;
}
/* Card description text */
.infographic-render-container svg foreignObject[data-element-type="item-desc"] > * {
    font-size: 0.8em !important;
    line-height: 1.4 !important;
    white-space: normal !important;
    word-break: break-word !important;
    display: -webkit-box !important;
    -webkit-line-clamp: 2 !important;
    -webkit-box-orient: vertical !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.infographic-container-wrapper .download-area {
    text-align: center;
    padding-top: 20px;
    margin-top: 20px;
    border-top: 1px solid var(--ig-border-color);
}
.infographic-container-wrapper .download-btn {
    background-color: var(--ig-primary-color);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 0.9em;
    cursor: pointer;
    transition: all 0.2s;
    margin: 4px 6px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.infographic-container-wrapper .download-btn.secondary {
    background-color: var(--ig-secondary-color);
}
.infographic-container-wrapper .download-btn.tertiary {
    background-color: var(--ig-tertiary-color);
}
.infographic-container-wrapper .download-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.infographic-container-wrapper .footer {
    text-align: center;
    padding: 16px;
    font-size: 0.8em;
    color: var(--ig-muted-text-color);
    background-color: #f8fafc;
    border-top: 1px solid var(--ig-border-color);
}
.infographic-container-wrapper .error-message {
    color: #dc2626;
    background-color: #fef2f2;
    border: 1px solid #fecaca;
    padding: 16px;
    border-radius: 8px;
    text-align: center;
}
"""

# =================================================================
# HTML Content Template
# =================================================================

CONTENT_TEMPLATE_INFOGRAPHIC = """
<div class="infographic-container-wrapper">
    <div class="header">
        <h1>📊 Smart Infographic</h1>
    </div>
    <div class="user-context">
        <span><strong>User:</strong> {user_name}</span>
        <span><strong>Time:</strong> {current_date_time_str}</span>
    </div>
    <div class="content-area">
        <div class="infographic-render-container" id="infographic-container-{unique_id}"></div>
        <div class="download-area">
            <button id="download-svg-btn-{unique_id}" class="download-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span class="btn-text">Download SVG</span>
            </button>
            <button id="download-png-btn-{unique_id}" class="download-btn secondary">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
                <span class="btn-text">Download PNG</span>
            </button>
            <button id="download-html-btn-{unique_id}" class="download-btn tertiary">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="16 18 22 12 16 6"/>
                    <polyline points="8 6 2 12 8 18"/>
                </svg>
                <span class="btn-text">Download HTML</span>
            </button>
        </div>
    </div>
    <div class="footer">
        <p>© {current_year} Infographic • <a href="https://infographic.antv.vision/" target="_blank" style="display: inline-flex; align-items: center; vertical-align: middle;">
            <svg width="24" height="25" viewBox="0 0 291 300" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-left: 4px;">
                <g><path d="M140.904 239.376C128.83 239.683 119.675 239.299 115.448 243.843C110.902 248.07 111.288 257.227 110.979 269.302C111.118 274.675 111.118 279.478 111.472 283.52C111.662 285.638 111.95 287.547 112.406 289.224C112.411 289.243 112.416 289.259 112.422 289.28C112.462 289.419 112.496 289.558 112.539 289.691C113.168 291.787 114.088 293.491 115.446 294.758C116.662 296.064 118.283 296.963 120.264 297.59C120.36 297.614 120.464 297.646 120.555 297.675C120.56 297.68 120.56 297.68 120.566 297.68C120.848 297.768 121.142 297.846 121.443 297.923C121.454 297.923 121.464 297.928 121.478 297.934C122.875 298.272 124.424 298.507 126.11 298.678C126.326 298.696 126.542 298.718 126.763 298.739C130.79 299.086 135.558 299.088 140.904 299.222C152.974 298.912 162.128 299.302 166.36 294.758C170.904 290.526 170.515 281.371 170.824 269.302C170.515 257.227 170.907 248.07 166.36 243.843C162.131 239.299 152.974 239.683 140.904 239.376Z" fill="#FF6376"></path><path d="M21.2155 128.398C12.6555 128.616 6.16484 128.339 3.16751 131.56C-0.0538222 134.56 0.218178 141.054 -0.000488281 149.608C0.218178 158.168 -0.0538222 164.659 3.16751 167.656C6.16484 170.878 12.6555 170.606 21.2155 170.824C25.0262 170.726 28.4288 170.726 31.2955 170.475C32.7968 170.342 34.1488 170.136 35.3382 169.814C35.3542 169.811 35.3648 169.806 35.3782 169.803C35.4768 169.774 35.5755 169.747 35.6688 169.718C37.1568 169.272 38.3648 168.622 39.2635 167.656C40.1915 166.795 40.8262 165.646 41.2715 164.243C41.2875 164.174 41.3115 164.102 41.3328 164.035C41.3328 164.035 41.3355 164.032 41.3355 164.027C41.3968 163.827 41.4529 163.622 41.5062 163.406C41.5062 163.398 41.5115 163.392 41.5142 163.382C41.7542 162.392 41.9222 161.294 42.0422 160.096C42.0555 159.944 42.0715 159.792 42.0848 159.635C42.3328 156.779 42.3328 153.398 42.4262 149.608C42.2075 141.054 42.4848 134.56 39.2635 131.56C36.2635 128.339 29.7728 128.616 21.2155 128.398Z" fill="#FFCCCC"></path><path d="M81.0595 184.171C70.8568 184.433 63.1208 184.102 59.5475 187.942C55.7075 191.518 56.0328 199.254 55.7742 209.454C56.0328 219.657 55.7075 227.393 59.5475 230.963C63.1208 234.803 70.8568 234.478 81.0595 234.739C85.6008 234.622 89.6595 234.622 93.0728 234.323C94.8648 234.163 96.4755 233.921 97.8942 233.534C97.9102 233.529 97.9235 233.526 97.9422 233.521C98.0568 233.486 98.1742 233.457 98.2888 233.422C100.06 232.889 101.5 232.113 102.569 230.963C103.676 229.937 104.433 228.566 104.964 226.894C104.985 226.811 105.012 226.726 105.036 226.646C105.041 226.643 105.041 226.643 105.041 226.638C105.116 226.401 105.18 226.153 105.244 225.897C105.244 225.889 105.249 225.881 105.254 225.867C105.54 224.689 105.74 223.379 105.881 221.953C105.9 221.771 105.916 221.59 105.934 221.403C106.228 218.001 106.228 213.969 106.342 209.454C106.081 199.254 106.412 191.518 102.572 187.942C98.9955 184.102 91.2568 184.433 81.0595 184.171Z" fill="#FF939F"></path><path d="M260.591 151.87C215.652 151.87 203.02 164.523 203.02 209.462H198.476C198.476 164.523 185.836 151.881 140.895 151.881V147.337C185.836 147.337 198.487 134.705 198.487 89.7659H203.02C203.02 134.705 215.652 147.337 260.591 147.337V151.87ZM286.052 124.158C281.82 119.614 272.66 120.001 260.591 119.689C248.521 119.385 239.361 119.771 235.129 115.227C230.585 110.995 230.983 101.846 230.671 89.7659C230.513 83.7312 230.535 78.4272 230.023 74.1019C229.513 69.7659 228.481 66.4219 226.209 64.3046C221.967 59.7606 212.817 60.1472 200.748 59.8459C188.681 60.1472 179.519 59.7606 175.287 64.3046C170.753 68.5366 171.129 77.6966 170.828 89.7659C170.516 101.835 170.9 110.995 166.356 115.227C162.124 119.771 152.985 119.374 140.905 119.689C138.873 119.739 136.924 119.771 135.071 119.811C119.313 118.697 106.337 112.318 106.337 89.7659C106.212 84.6699 106.233 80.1792 105.807 76.5206C105.367 72.8726 104.492 70.0379 102.575 68.2566C99.0013 64.4112 91.2573 64.7446 81.0653 64.4832C70.86 64.7446 63.1186 64.4112 59.5533 68.2566C55.708 71.8299 56.0306 79.5632 55.7693 89.7659C56.0306 99.9686 55.708 107.702 59.5533 111.278C63.1186 115.113 70.86 114.79 81.0653 115.049C103.617 115.049 109.996 128.035 111.1 143.803C111.068 145.659 111.028 147.587 110.975 149.619C111.121 154.987 111.121 159.79 111.476 163.835C111.663 165.95 111.945 167.857 112.404 169.534C112.412 169.555 112.412 169.566 112.423 169.598C112.465 169.734 112.497 169.867 112.537 170.003C113.164 172.099 114.092 173.809 115.447 175.07C116.665 176.371 118.281 177.278 120.271 177.905C120.364 177.934 120.46 177.955 120.564 177.987C120.855 178.081 121.145 178.153 121.439 178.238C121.46 178.238 121.471 178.238 121.479 178.249C122.876 178.582 124.42 178.822 126.108 178.987C126.327 179.009 126.545 179.03 126.764 179.051C130.788 179.395 135.559 179.395 140.905 179.529C152.975 179.843 162.124 179.457 166.356 184.001C170.9 188.233 170.516 197.371 170.828 209.451C171.129 221.529 170.743 230.681 175.287 234.91C179.519 239.454 188.681 239.07 200.748 239.371C206.127 239.235 210.921 239.235 214.975 238.881C217.079 238.694 218.985 238.403 220.676 237.955C220.695 237.945 220.705 237.934 220.727 237.934C220.873 237.891 220.999 237.859 221.135 237.819C223.228 237.193 224.937 236.265 226.209 234.91C227.511 233.691 228.409 232.065 229.044 230.097C229.065 230.003 229.095 229.899 229.127 229.803V229.793C229.22 229.513 229.295 229.222 229.367 228.918C229.367 228.897 229.377 228.897 229.377 228.878C229.721 227.481 229.951 225.937 230.127 224.249C230.137 224.03 230.169 223.811 230.191 223.593C230.535 219.571 230.535 214.798 230.671 209.451C230.972 197.371 230.585 188.233 235.129 184.001C239.361 179.457 248.511 179.843 260.591 179.529C272.66 179.227 281.82 179.614 286.052 175.07C290.596 170.838 290.209 161.689 290.511 149.619C290.209 137.539 290.596 128.379 286.052 124.158Z" fill="#FF356A"></path><path d="M112.405 49.848C112.411 49.8694 112.416 49.8827 112.421 49.904C112.461 50.0427 112.499 50.1814 112.539 50.3147C113.171 52.4134 114.088 54.1147 115.448 55.384C116.661 56.6907 118.283 57.5894 120.264 58.2134C120.36 58.24 120.464 58.2694 120.555 58.3014C120.56 58.3067 120.56 58.3067 120.565 58.3067C120.848 58.3947 121.141 58.4694 121.443 58.5467C121.453 58.5467 121.464 58.552 121.48 58.5574C122.875 58.896 124.424 59.1334 126.112 59.3014C126.325 59.3227 126.541 59.3414 126.763 59.3627C130.789 59.712 135.56 59.712 140.904 59.8454C152.973 59.5387 162.128 59.928 166.36 55.384C170.907 51.152 170.515 41.9947 170.824 29.9254C170.517 17.8507 170.907 8.69602 166.363 4.46935C162.131 -0.0746511 152.973 0.309349 140.904 1.52588e-05C128.829 0.309349 119.675 -0.0746511 115.448 4.46935C110.904 8.69602 111.288 17.8507 110.979 29.9254C111.117 35.3014 111.117 40.1014 111.472 44.144C111.661 46.2614 111.949 48.1707 112.405 49.848Z" fill="#FF6376"></path></g>
            </svg>
        </a></p>
    </div>
</div>

<script type="text/template" id="infographic-source-{unique_id}">{infographic_syntax}</script>
"""

# =================================================================
# JavaScript Rendering Script
# =================================================================

SCRIPT_TEMPLATE_INFOGRAPHIC = """
<script src="https://unpkg.com/@antv/infographic@latest/dist/infographic.min.js"></script>
<script>
(function() {{
    const renderInfographic = () => {{
        const uniqueId = "{unique_id}";
        const containerEl = document.getElementById('infographic-container-' + uniqueId);
        if (!containerEl || containerEl.dataset.infographicRendered) return;

        const sourceEl = document.getElementById('infographic-source-' + uniqueId);
        if (!sourceEl) return;

        let syntaxContent = sourceEl.textContent.trim();
        if (!syntaxContent) {{
            containerEl.innerHTML = '<div class="error-message">⚠️ Unable to load infographic: missing valid content.</div>';
            return;
        }}

        console.log('[Infographic] Original syntax content:', syntaxContent);

        // Remove code block markers - use more robust string handling
        const backtick = String.fromCharCode(96);
        const prefix = backtick + backtick + backtick + 'infographic';
        const simplePrefix = backtick + backtick + backtick;
        
        if (syntaxContent.toLowerCase().startsWith(prefix)) {{
            syntaxContent = syntaxContent.substring(prefix.length).trim();
        }} else if (syntaxContent.startsWith(simplePrefix)) {{
            syntaxContent = syntaxContent.substring(simplePrefix.length).trim();
        }}
        
        if (syntaxContent.endsWith(simplePrefix)) {{
            syntaxContent = syntaxContent.substring(0, syntaxContent.length - simplePrefix.length).trim();
        }}

        // Fix syntax: remove colons after keywords (LLM may incorrectly add them)
        // e.g.: children: -> children, items: -> items, data: -> data
        syntaxContent = syntaxContent.replace(/^(data|items|children|theme|config):/gm, '$1');
        syntaxContent = syntaxContent.replace(/(\\s)(children|items):/g, '$1$2');

        // 1. Fallback check: ensure infographic prefix
        if (!syntaxContent.trim().toLowerCase().startsWith('infographic')) {{
            const firstWord = syntaxContent.trim().split(/\\s+/)[0].toLowerCase();
            if (!['data', 'theme', 'design', 'items'].includes(firstWord)) {{
                console.log('[Infographic] Missing prefix detected, auto-completing');
                syntaxContent = 'infographic ' + syntaxContent;
            }}
        }}

        // 2. Template Mapping Configuration (Official AntV Structure IDs)
        const TEMPLATE_MAPPING = {{
            // List & Hierarchy - map short names to full template names
            'list-grid': 'list-grid-compact-card',
            'list-column': 'list-column-simple-vertical-arrow',
            'list-row': 'list-row-simple-horizontal-arrow',
            'hierarchy-tree': 'hierarchy-tree-tech-style-capsule-item',
            
            // Sequence & Timeline
            'sequence-roadmap-vertical': 'sequence-roadmap-vertical-simple',
            'sequence-timeline': 'sequence-timeline-simple',
            'sequence-steps': 'sequence-steps-simple',
            'sequence-horizontal-zigzag': 'sequence-horizontal-zigzag-simple',
            
            // Comparison
            'compare-binary-horizontal': 'compare-binary-horizontal-simple-vs',
            'compare-hierarchy-row': 'compare-hierarchy-row-simple',
            
            // Charts
            'chart-column': 'chart-column-simple',
            'quadrant': 'quadrant-quarter-simple-card',
            'relation-dagre': 'relation-dagre-flow-tb-simple-circle-node',
            
            // Legacy mappings for backward compatibility
            'list-vertical': 'list-column-simple-vertical-arrow',
            'tree-vertical': 'hierarchy-tree-tech-style-capsule-item',
            'sequence-roadmap': 'sequence-roadmap-vertical-simple',
            'sequence-zigzag': 'sequence-horizontal-zigzag-simple',
            'compare-binary': 'compare-binary-horizontal-simple-vs',
            'chart-bar': 'chart-bar-plain-text',
            'chart-line': 'chart-line-plain-text',
            'chart-pie': 'chart-pie-plain-text',
            'chart-doughnut': 'chart-pie-donut-plain-text'
        }};


        // 3. Apply Mapping Strategy
        for (const [key, value] of Object.entries(TEMPLATE_MAPPING)) {{
            const regex = new RegExp(`infographic\\\\s+${{key}}(?=\\\\s|$)`, 'i');
            if (regex.test(syntaxContent)) {{
                console.log(`[Infographic] Auto-mapping template: ${{key}} -> ${{value}}`);
                syntaxContent = syntaxContent.replace(regex, `infographic ${{value}}`);
                break; 
            }}
        }}

        // --- Style Extraction & Application ---
        const bgMatch = syntaxContent.match(/backgroundColor\\s+(#[0-9a-fA-F]{{6}}|#[0-9a-fA-F]{{3}}|[a-zA-Z]+)/);
        if (bgMatch && bgMatch[1]) {{
            containerEl.style.backgroundColor = bgMatch[1];
        }} else {{
            containerEl.style.backgroundColor = '#ffffff';
        }}

        const textMatch = syntaxContent.match(/textColor\\s+(#[0-9a-fA-F]{{6}}|#[0-9a-fA-F]{{3}}|[a-zA-Z]+)/);
        if (textMatch && textMatch[1]) {{
            containerEl.style.color = textMatch[1];
        }} else {{
             containerEl.style.color = '';
        }}

        // --- Syntax Cleaning ---
        // Remove unsupported theme properties
        const nl = String.fromCharCode(10);
        const cleanRegex = new RegExp('^\\\\s*(roughness|stylize|backgroundColor|textColor|colorBg).*(' + nl + '\\\\s+.*)*', 'gm');
        syntaxContent = syntaxContent.replace(cleanRegex, '');
        
        syntaxContent = syntaxContent.trim();
        
        // Temporary fallback strategy
        if (/infographic\\s+list-vertical/.test(syntaxContent)) {{
             console.log('[Infographic] Detected list-vertical, temporarily downgrading to list-row-simple-horizontal-arrow');
             syntaxContent = syntaxContent.replace(/infographic\\s+list-vertical/, 'infographic list-row-simple-horizontal-arrow');
        }}

        console.log('[Infographic] Cleaned syntax content:', syntaxContent);

        if (typeof AntVInfographic === 'undefined') {{
            console.error('[Infographic] AntVInfographic library not loaded');
            containerEl.innerHTML = '<div class="error-message">⚠️ Unable to load AntV Infographic library. Please check your network connection.</div>';
            return;
        }}

        // --- Auto Theme Loading ---
        try {{
            const html = document.documentElement;
            const body = document.body;
            const htmlClass = html ? html.className : '';
            const bodyClass = body ? body.className : '';
            const htmlDataTheme = html ? html.getAttribute('data-theme') : '';
            
            const wrapper = containerEl.closest('.infographic-container-wrapper');
            if (wrapper) {{
                if (htmlDataTheme === 'dark' || bodyClass.includes('dark') || htmlClass.includes('dark')) {{
                    wrapper.classList.add('dark');
                }}
            }}
        }} catch (e) {{
            console.warn('[Infographic] Failed to apply theme class', e);
        }}

        try {{
            const {{ Infographic }} = AntVInfographic;
            
            // Use ID selector string
            const containerId = '#' + containerEl.id;
            
            const instance = new Infographic({{
                container: containerId,
                width: '100%',
                // height: '100%', // Remove fixed height to allow auto-sizing
                padding: 24,
            }});
            
            console.log('[Infographic] Rendering...');
            instance.render(syntaxContent);
            containerEl.dataset.infographicRendered = 'true';
            console.log('[Infographic] Rendering complete');

            // Auto-adjust height and tag elements
            setTimeout(() => {
                const svg = containerEl.querySelector('svg');
                if (svg) {
                    // 1. Tag elements for CSS styling
                    const fos = Array.from(svg.querySelectorAll('foreignObject'));
                    let titleFound = false;
                    let descFound = false;
                    
                    fos.forEach((fo) => {
                        const text = fo.textContent.trim();
                        if (!text || fo.querySelector('i') || (fo.querySelector('svg') && fo.querySelectorAll('*').length < 5)) {
                            fo.setAttribute('data-element-type', 'icon');
                            return;
                        }
                        
                        // Dynamically increase height and width to accommodate wrapped text
                        const currentHeight = parseInt(fo.getAttribute('height') || '0');
                        if (currentHeight > 0 && currentHeight < 200) {
                            fo.setAttribute('height', Math.round(currentHeight * 1.8).toString());
                        }
                        const currentWidth = parseInt(fo.getAttribute('width') || '0');
                        if (currentWidth > 0 && currentWidth < 300) {
                            fo.setAttribute('width', Math.max(Math.round(currentWidth * 1.2), 180).toString());
                        }

                        if (!titleFound) {
                            fo.setAttribute('data-element-type', 'title');
                            titleFound = true;
                        } else if (!descFound) {
                            fo.setAttribute('data-element-type', 'desc');
                            descFound = true;
                        } else {
                            if (fo.querySelector('strong') || fo.style.fontWeight === 'bold' || text.length < 15) {
                                fo.setAttribute('data-element-type', 'item-label');
                            } else {
                                fo.setAttribute('data-element-type', 'item-desc');
                            }
                        }
                    });

                    // 2. Adjust height
                    const bbox = svg.getBoundingClientRect();
                    let contentHeight = bbox.height;
                    if (svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.height) {
                        contentHeight = svg.viewBox.baseVal.height;
                    }
                    const finalHeight = contentHeight + 40; 
                    containerEl.style.minHeight = finalHeight + 'px';
                    containerEl.style.height = 'auto';
                }
            }, 500);
            
            attachDownloadHandlers(uniqueId, syntaxContent);

        }} catch (error) {{
            console.error('[Infographic] Rendering error:', error);
            containerEl.innerHTML = '<div class="error-message">⚠️ Infographic rendering failed!<br>Reason: ' + error.message + '</div>';
        }}
    }};

    const attachDownloadHandlers = (uniqueId, syntaxContent) => {{
        const downloadSvgBtn = document.getElementById('download-svg-btn-' + uniqueId);
        const downloadPngBtn = document.getElementById('download-png-btn-' + uniqueId);
        const downloadHtmlBtn = document.getElementById('download-html-btn-' + uniqueId);
        const containerEl = document.getElementById('infographic-container-' + uniqueId);

        const showFeedback = (button, isSuccess, msg) => {{
            const buttonText = button.querySelector('.btn-text');
            const originalText = buttonText.textContent;
            button.disabled = true;
            buttonText.textContent = isSuccess ? '✅ ' + (msg || 'Success') : '❌ Failed';
            setTimeout(() => {{
                buttonText.textContent = originalText;
                button.disabled = false;
            }}, 2000);
        }};

        const downloadFile = (content, filename, mimeType) => {{
            const blob = new Blob([content], {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }};

        if (downloadSvgBtn) {{
            downloadSvgBtn.addEventListener('click', (event) => {{
                event.stopPropagation();
                const svgEl = containerEl.querySelector('svg');
                if (svgEl) {{
                    const svgData = new XMLSerializer().serializeToString(svgEl);
                    downloadFile(svgData, 'infographic_' + uniqueId + '.svg', 'image/svg+xml');
                    showFeedback(downloadSvgBtn, true, 'Downloaded');
                }} else {{
                    showFeedback(downloadSvgBtn, false);
                }}
            }});
        }}

        if (downloadPngBtn) {{
            downloadPngBtn.addEventListener('click', (event) => {{
                event.stopPropagation();
                const svgEl = containerEl.querySelector('svg');
                if (svgEl) {{
                    // Get SVG actual dimensions
                    const bbox = svgEl.getBoundingClientRect();
                    const width = bbox.width || svgEl.viewBox?.baseVal?.width || 800;
                    const height = bbox.height || svgEl.viewBox?.baseVal?.height || 600;
                    
                    // Clone SVG and set explicit dimensions
                    const clonedSvg = svgEl.cloneNode(true);
                    clonedSvg.setAttribute('width', width);
                    clonedSvg.setAttribute('height', height);
                    clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
                    
                    const svgData = new XMLSerializer().serializeToString(clonedSvg);
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    const img = new Image();
                    
                    // Use Base64 encoding to avoid special character issues
                    const base64Data = btoa(unescape(encodeURIComponent(svgData)));
                    const dataUrl = 'data:image/svg+xml;base64,' + base64Data;
                    
                    img.onload = () => {{
                        const scale = 2;
                        canvas.width = width * scale;
                        canvas.height = height * scale;
                        ctx.scale(scale, scale);
                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(0, 0, canvas.width, canvas.height);
                        ctx.drawImage(img, 0, 0, width, height);
                        
                        canvas.toBlob((blob) => {{
                            if (blob) {{
                                const pngUrl = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = pngUrl;
                                a.download = 'infographic_' + uniqueId + '.png';
                                a.click();
                                URL.revokeObjectURL(pngUrl);
                                showFeedback(downloadPngBtn, true, 'Downloaded');
                            }} else {{
                                console.error('[Infographic] PNG blob creation failed');
                                showFeedback(downloadPngBtn, false);
                            }}
                        }}, 'image/png');
                    }};
                    
                    img.onerror = (err) => {{
                        console.error('[Infographic] SVG to image conversion failed:', err);
                        showFeedback(downloadPngBtn, false);
                    }};
                    
                    img.src = dataUrl;
                }} else {{
                    showFeedback(downloadPngBtn, false);
                }}
            }});
        }}

        if (downloadHtmlBtn) {{
            downloadHtmlBtn.addEventListener('click', (event) => {{
                event.stopPropagation();
                const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Infographic</title>
    <script src="https://unpkg.com/@antv/infographic@latest/dist/infographic.min.js"><\\/script>
    <style>
        body {{ margin: 0; padding: 20px; background: #f5f5f5; }}
        #container {{ background: white; border-radius: 8px; padding: 20px; max-width: 900px; margin: 0 auto; }}
    </style>
</head>
<body>
    <div id="container"></div>
    <script>
        const {{ Infographic }} = AntVInfographic;
        const instance = new Infographic({{
            container: '#container',
            width: '100%',
            padding: 24,
        }});
        instance.render(\`${{syntaxContent.replace(/`/g, '\\\\`')}}\`);
    <\\/script>
</body>
</html>`;
                downloadFile(htmlContent, 'infographic_' + uniqueId + '.html', 'text/html');
                showFeedback(downloadHtmlBtn, true, 'Downloaded');
            }});
        }}
    }};

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', renderInfographic);
    }} else {{
        renderInfographic();
    }}
}})();
</script>
"""


class Action:
    class Valves(BaseModel):
        SHOW_STATUS: bool = Field(
            default=True, description="Show operation status updates in chat interface."
        )
        MODEL_ID: str = Field(
            default="",
            description="Built-in LLM model ID for text analysis. If empty, uses current conversation model.",
        )
        MIN_TEXT_LENGTH: int = Field(
            default=100,
            description="Minimum text length (characters) required for infographic analysis.",
        )
        CLEAR_PREVIOUS_HTML: bool = Field(
            default=False,
            description="Force clear old plugin results (if True, overwrite instead of merge).",
        )
        MESSAGE_COUNT: int = Field(
            default=1,
            description="Number of recent messages to use for generation. Set to 1 for just the last message, or higher for more context.",
        )
        OUTPUT_MODE: str = Field(
            default="image",
            description="Output mode: 'html' for interactive HTML, or 'image' to embed as Markdown image (default).",
        )
        SHOW_DEBUG_LOG: bool = Field(
            default=False,
            description="Whether to print debug logs in the browser console.",
        )

    def __init__(self):
        self.valves = self.Valves()
        # Fallback mapping for variants not in TRANSLATIONS keys
        self.fallback_map = {
            "es-AR": "es-ES",
            "es-MX": "es-ES",
            "fr-CA": "fr-FR",
            "en-CA": "en-US",
            "en-GB": "en-US",
            "en-AU": "en-US",
            "de-AT": "de-DE",
        }

    async def _get_user_context(
        self,
        __user__: Optional[Dict[str, Any]],
        __event_call__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __request__: Optional[Request] = None,
    ) -> Dict[str, str]:
        """Extract basic user context with safe fallbacks."""
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        user_id = user_data.get("id", "unknown_user")
        user_name = user_data.get("name", "User")
        # Default from profile
        user_language = user_data.get("language", "en-US")
        user_theme = "light"

        # Level 1 Fallback: Accept-Language from __request__ headers
        if (
            __request__
            and hasattr(__request__, "headers")
            and "accept-language" in __request__.headers
        ):
            raw_lang = __request__.headers.get("accept-language", "")
            if raw_lang:
                user_language = raw_lang.split(",")[0].split(";")[0]

        # Priority: Document Lang > LocalStorage (Frontend) > Browser > Request Header > Profile
        if __event_call__:
            try:
                js_code = """
                    try {
                        const html = document.documentElement;
                        const body = document.body;
                        const htmlClass = html ? html.className : '';
                        const bodyClass = body ? body.className : '';
                        const htmlDataTheme = html ? html.getAttribute('data-theme') : '';
                        
                        let theme = 'light';
                        
                        // 1. Check parent document's html/body class or data-theme
                        if (htmlDataTheme === 'dark' || bodyClass.includes('dark') || htmlClass.includes('dark')) {
                            theme = 'dark';
                        } else if (htmlDataTheme === 'light' || bodyClass.includes('light') || htmlClass.includes('light')) {
                            theme = 'light';
                        } else {
                            // 2. Check meta theme-color luma
                            const metas = document.querySelectorAll('meta[name="theme-color"]');
                            let foundMeta = false;
                            if (metas.length > 0) {
                                const color = metas[metas.length - 1].content.trim();
                                const m = color.match(/^#?([0-9a-f]{6})$/i);
                                if (m) {
                                    const hex = m[1];
                                    const r = parseInt(hex.slice(0, 2), 16);
                                    const g = parseInt(hex.slice(2, 4), 16);
                                    const b = parseInt(hex.slice(4, 6), 16);
                                    const luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
                                    theme = luma < 0.5 ? 'dark' : 'light';
                                    foundMeta = true;
                                }
                            }
                            // 3. Check system preference
                            if (!foundMeta && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                                theme = 'dark';
                            }
                        }

                        const lang = document.documentElement.lang ||
                                     localStorage.getItem('locale') || 
                                     localStorage.getItem('language') || 
                                     navigator.language || 
                                     'en-US';

                        return JSON.stringify({ lang, theme });
                    } catch (e) {
                        return JSON.stringify({ lang: 'en-US', theme: 'light' });
                    }
                """
                # Use asyncio.wait_for to prevent hanging if frontend fails to callback
                frontend_res_str = await asyncio.wait_for(
                    __event_call__({"type": "execute", "data": {"code": js_code}}),
                    timeout=2.0,
                )
                if frontend_res_str and isinstance(frontend_res_str, str):
                    try:
                        import json
                        frontend_res = json.loads(frontend_res_str)
                        user_language = frontend_res.get("lang", user_language)
                        user_theme = frontend_res.get("theme", user_theme)
                    except Exception:
                        user_language = frontend_res_str
            except Exception as e:
                logger.warning(f"Failed to retrieve frontend language/theme: {e}")

        return {
            "user_id": user_id,
            "user_name": user_name,
            "user_language": user_language,
            "user_theme": user_theme,
        }

    def _resolve_language(self, lang: str) -> str:
        """Resolve the best matching language code from the TRANSLATIONS dict."""
        target_lang = lang
        if target_lang in TRANSLATIONS:
            return target_lang
        if hasattr(self, 'fallback_map') and target_lang in self.fallback_map:
            target_lang = self.fallback_map[target_lang]
            if target_lang in TRANSLATIONS:
                return target_lang
        if "-" in lang:
            base_lang = lang.split("-")[0]
            for supported_lang in TRANSLATIONS:
                if supported_lang.startswith(base_lang + "-"):
                    return supported_lang
        return "en-US"

    def _get_translation(self, lang: str, key: str, **kwargs) -> str:
        """Get translated string for the given language and key."""
        target_lang = self._resolve_language(lang)
        lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS["en-US"])
        text = lang_dict.get(key, TRANSLATIONS["en-US"].get(key, key))
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception as e:
                logger.warning(f"Translation formatting failed for {key}: {e}")
        return text

    def _get_chat_context(
        self, body: dict, __metadata__: Optional[dict] = None
    ) -> Dict[str, str]:
        """
        Unified extraction of chat context information (chat_id, message_id).
        Prioritizes extraction from body, then metadata.
        """
        chat_id = ""
        message_id = ""

        # 1. Try to get from body
        if isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            message_id = body.get("id", "")  # message_id is usually 'id' in body

            # Check body.metadata as fallback
            if not chat_id or not message_id:
                body_metadata = body.get("metadata", {})
                if isinstance(body_metadata, dict):
                    if not chat_id:
                        chat_id = body_metadata.get("chat_id", "")
                    if not message_id:
                        message_id = body_metadata.get("message_id", "")

        # 2. Try to get from __metadata__ (as supplement)
        if __metadata__ and isinstance(__metadata__, dict):
            if not chat_id:
                chat_id = __metadata__.get("chat_id", "")
            if not message_id:
                message_id = __metadata__.get("message_id", "")

        return {
            "chat_id": str(chat_id).strip(),
            "message_id": str(message_id).strip(),
        }

    def _extract_infographic_syntax(self, llm_output: str) -> str:
        """Extract infographic syntax from LLM output"""
        match = re.search(r"```infographic\s*(.*?)\s*```", llm_output, re.DOTALL)
        if match:
            extracted_content = match.group(1).strip()
        else:
            logger.warning(
                "LLM output did not follow expected format, treating entire output as syntax."
            )
            extracted_content = llm_output.strip()

        return extracted_content.replace("</script>", "<\\/script>")

    async def _emit_status(self, emitter, description: str, done: bool = False):
        """Send status update event"""
        if self.valves.SHOW_STATUS and emitter:
            await emitter(
                {"type": "status", "data": {"description": description, "done": done}}
            )

    async def _emit_notification(self, emitter, content: str, ntype: str = "info"):
        """Send notification event (info/success/warning/error)"""
        if emitter:
            await emitter(
                {"type": "notification", "data": {"type": ntype, "content": content}}
            )

    async def _emit_debug_log(self, emitter, title: str, data: dict):
        """Print structured debug logs in the browser console"""
        if not self.valves.SHOW_DEBUG_LOG or not emitter:
            return

        try:
            js_code = f"""
                (async function() {{
                    console.group("🛠️ {title}");
                    console.log({json.dumps(data, ensure_ascii=False)});
                    console.groupEnd();
                }})();
            """

            await emitter({"type": "execute", "data": {"code": js_code}})
        except Exception as e:
            print(f"Error emitting debug log: {e}")

    def _remove_existing_html(self, content: str) -> str:
        """Remove existing plugin-generated HTML code blocks from content"""
        pattern = r"```html\s*<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?```"
        return re.sub(pattern, "", content).strip()

    def _extract_text_content(self, content) -> str:
        """Extract text from message content, supporting multimodal message formats"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Multimodal message: [{"type": "text", "text": "..."}, {"type": "image_url", ...}]
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        return str(content) if content else ""

    def _merge_html(
        self,
        existing_html_code: str,
        new_content: str,
        new_styles: str = "",
        new_scripts: str = "",
        user_language: str = "en",
    ) -> str:
        """Merge new content into existing HTML container or create a new one"""
        if (
            "<!-- OPENWEBUI_PLUGIN_OUTPUT -->" in existing_html_code
            and "<!-- CONTENT_INSERTION_POINT -->" in existing_html_code
        ):
            base_html = existing_html_code
            base_html = re.sub(r"^```html\s*", "", base_html)
            base_html = re.sub(r"\s*```$", "", base_html)
        else:
            base_html = HTML_WRAPPER_TEMPLATE.replace("{user_language}", user_language)

        wrapped_content = f'<div class="plugin-item">\n{new_content}\n</div>'

        if new_styles:
            base_html = base_html.replace(
                "/* STYLES_INSERTION_POINT */",
                f"{new_styles}\n/* STYLES_INSERTION_POINT */",
            )

        base_html = base_html.replace(
            "<!-- CONTENT_INSERTION_POINT -->",
            f"{wrapped_content}\n<!-- CONTENT_INSERTION_POINT -->",
        )

        if new_scripts:
            base_html = base_html.replace(
                "<!-- SCRIPTS_INSERTION_POINT -->",
                f"{new_scripts}\n<!-- SCRIPTS_INSERTION_POINT -->",
            )

        return base_html.strip()

    def _generate_image_js_code(
        self,
        unique_id: str,
        chat_id: str,
        message_id: str,
        infographic_syntax: str,
    ) -> str:
        """Generate JavaScript code for frontend SVG rendering and image embedding"""

        # Escape the syntax for JS embedding
        syntax_escaped = (
            infographic_syntax.replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
            .replace("</script>", "<\\/script>")
        )

        return f"""
(async function() {{
    const uniqueId = "{unique_id}";
    const chatId = "{chat_id}";
    const messageId = "{message_id}";
    const defaultWidth = 1100;
    const defaultHeight = 500;
    
    // Auto-detect chat container width for responsive sizing
    let svgWidth = defaultWidth;
    let svgHeight = defaultHeight;
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {{
        const containerWidth = chatContainer.clientWidth;
        if (containerWidth > 100) {{
            // Use container width with padding (80% of container, leaving more space on the right)
            svgWidth = Math.floor(containerWidth * 0.8);
            // Maintain aspect ratio based on default dimensions
            svgHeight = Math.floor(svgWidth * (defaultHeight / defaultWidth));
            console.log("[Infographic Image] Auto-detected container width:", containerWidth, "-> SVG:", svgWidth, "x", svgHeight);
        }}
    }}
    
    console.log("[Infographic Image] Starting render...");
    console.log("[Infographic Image] chatId:", chatId, "messageId:", messageId);
    
    try {{
        // Load AntV Infographic if not loaded
        if (typeof AntVInfographic === 'undefined') {{
            console.log("[Infographic Image] Loading AntV Infographic...");
            await new Promise((resolve, reject) => {{
                const script = document.createElement('script');
                script.src = 'https://unpkg.com/@antv/infographic@latest/dist/infographic.min.js';
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            }});
        }}
        
        const {{ Infographic }} = AntVInfographic;
        
        // Get syntax content
        let syntaxContent = `{syntax_escaped}`;
        console.log("[Infographic Image] Syntax length:", syntaxContent.length);
        
        // Clean up syntax: remove code block markers
        const backtick = String.fromCharCode(96);
        const prefix = backtick + backtick + backtick + 'infographic';
        const simplePrefix = backtick + backtick + backtick;
        
        if (syntaxContent.toLowerCase().startsWith(prefix)) {{
            syntaxContent = syntaxContent.substring(prefix.length).trim();
        }} else if (syntaxContent.startsWith(simplePrefix)) {{
            syntaxContent = syntaxContent.substring(simplePrefix.length).trim();
        }}
        
        if (syntaxContent.endsWith(simplePrefix)) {{
            syntaxContent = syntaxContent.substring(0, syntaxContent.length - simplePrefix.length).trim();
        }}
        
        // Fix syntax: remove colons after keywords
        syntaxContent = syntaxContent.replace(/^(data|items|children|theme|config):/gm, '$1');
        syntaxContent = syntaxContent.replace(/(\\s)(children|items):/g, '$1$2');
        
        // Ensure infographic prefix
        if (!syntaxContent.trim().toLowerCase().startsWith('infographic')) {{
            const firstWord = syntaxContent.trim().split(/\\s+/)[0].toLowerCase();
            if (!['data', 'theme', 'design', 'items'].includes(firstWord)) {{
                syntaxContent = 'infographic ' + syntaxContent;
            }}
        }}
        
        // Template mapping
        const TEMPLATE_MAPPING = {{
            'list-grid': 'list-grid-compact-card',
            'list-vertical': 'list-column-simple-vertical-arrow',
            'tree-vertical': 'hierarchy-tree-tech-style-capsule-item',
            'tree-horizontal': 'hierarchy-tree-lr-tech-style-capsule-item',
            'mindmap': 'hierarchy-mindmap-branch-gradient-capsule-item',
            'sequence-roadmap': 'sequence-roadmap-vertical-simple',
            'sequence-zigzag': 'sequence-horizontal-zigzag-simple',
            'sequence-horizontal': 'sequence-horizontal-zigzag-simple',
            'relation-sankey': 'relation-sankey-simple',
            'relation-circle': 'relation-circle-icon-badge',
            'relation-dagre': 'relation-dagre-flow-tb-simple-circle-node',
            'compare-binary': 'compare-binary-horizontal-simple-vs',
            'compare-swot': 'compare-swot',
            'quadrant-quarter': 'quadrant-quarter-simple-card',
            'statistic-card': 'list-grid-compact-card',
            'chart-bar': 'chart-bar-plain-text',
            'chart-column': 'chart-column-simple',
            'chart-line': 'chart-line-plain-text',
            'chart-area': 'chart-area-simple',
            'chart-pie': 'chart-pie-plain-text',
            'chart-doughnut': 'chart-pie-donut-plain-text'
        }};
        
        for (const [key, value] of Object.entries(TEMPLATE_MAPPING)) {{
            const regex = new RegExp(`infographic\\\\s+${{key}}(?=\\\\s|$)`, 'i');
            if (regex.test(syntaxContent)) {{
                syntaxContent = syntaxContent.replace(regex, `infographic ${{value}}`);
                break;
            }}
        }}
        
        // Create offscreen container
        const container = document.createElement('div');
        container.id = 'infographic-offscreen-' + uniqueId;
        container.style.cssText = 'position:absolute;left:-9999px;top:-9999px;width:' + svgWidth + 'px;height:' + svgHeight + 'px;background:#ffffff;';
        document.body.appendChild(container);
        
        // Create infographic instance
        const instance = new Infographic({{
            container: '#' + container.id,
            width: svgWidth,
            height: svgHeight,
            padding: 12,
        }});
        
        console.log("[Infographic Image] Rendering infographic...");
        instance.render(syntaxContent);
        
        // Wait for render to complete
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Get SVG element
        const svgEl = container.querySelector('svg');
        if (!svgEl) {{
            throw new Error('SVG element not found after rendering');
        }}
        
        // Get actual dimensions
        const bbox = svgEl.getBoundingClientRect();
        const width = bbox.width || svgWidth;
        const height = bbox.height || svgHeight;
        
        // Clone and prepare SVG for export
        const clonedSvg = svgEl.cloneNode(true);
        clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
        clonedSvg.setAttribute('width', width);
        clonedSvg.setAttribute('height', height);
        
        // Add background rect
        const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bgRect.setAttribute('width', '100%');
        bgRect.setAttribute('height', '100%');
        bgRect.setAttribute('fill', '#ffffff');
        clonedSvg.insertBefore(bgRect, clonedSvg.firstChild);
        
        // Serialize SVG to string
        const svgData = new XMLSerializer().serializeToString(clonedSvg);
        
        // Cleanup container
        document.body.removeChild(container);
        
        // Convert SVG to PNG using canvas for better compatibility
        console.log("[Infographic Image] Converting SVG to PNG...");
        const pngBlob = await new Promise((resolve, reject) => {{
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const scale = 2; // Higher resolution for clarity
            canvas.width = Math.round(width * scale);
            canvas.height = Math.round(height * scale);
            
            // Fill white background
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.scale(scale, scale);
            
            const img = new Image();
            img.onload = () => {{
                ctx.drawImage(img, 0, 0, width, height);
                canvas.toBlob((blob) => {{
                    if (blob) {{
                        resolve(blob);
                    }} else {{
                        reject(new Error('Canvas toBlob failed'));
                    }}
                }}, 'image/png');
            }};
            img.onerror = (e) => reject(new Error('Failed to load SVG as image: ' + e));
            img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
        }});
        
        const file = new File([pngBlob], `infographic-${{uniqueId}}.png`, {{ type: 'image/png' }});
        
        // Upload file to OpenWebUI API
        console.log("[Infographic Image] Uploading PNG file...");
        const token = localStorage.getItem("token");
        const formData = new FormData();
        formData.append('file', file);
        
        const uploadResponse = await fetch('/api/v1/files/', {{
            method: 'POST',
            headers: {{
                'Authorization': `Bearer ${{token}}`
            }},
            body: formData
        }});
        
        if (!uploadResponse.ok) {{
            throw new Error(`Upload failed: ${{uploadResponse.statusText}}`);
        }}
        
        const fileData = await uploadResponse.json();
        const fileId = fileData.id;
        const imageUrl = `/api/v1/files/${{fileId}}/content`;
        
        console.log("[Infographic Image] PNG file uploaded, ID:", fileId);
        
        // Generate markdown image with file URL
        const markdownImage = `![📊 Infographic](${{imageUrl}})`;
        
        // Update message via API
        if (chatId && messageId) {{
            
            // Helper function with retry logic
            const fetchWithRetry = async (url, options, retries = 3) => {{
                for (let i = 0; i < retries; i++) {{
                    try {{
                        const response = await fetch(url, options);
                        if (response.ok) return response;
                        if (i < retries - 1) {{
                            console.log(`[Infographic Image] Retry ${{i + 1}}/${{retries}} for ${{url}}`);
                            await new Promise(r => setTimeout(r, 1000 * (i + 1)));
                        }}
                    }} catch (e) {{
                        if (i === retries - 1) throw e;
                        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
                    }}
                }}
                return null;
            }};
            
            // Get current chat data
            const getResponse = await fetch(`/api/v1/chats/${{chatId}}`, {{
                method: "GET",
                headers: {{ "Authorization": `Bearer ${{token}}` }}
            }});
            
            if (!getResponse.ok) {{
                throw new Error("Failed to get chat data: " + getResponse.status);
            }}
            
            const chatData = await getResponse.json();
            let updatedMessages = [];
            let newContent = "";
            
            if (chatData.chat && chatData.chat.messages) {{
                updatedMessages = chatData.chat.messages.map(m => {{
                    if (m.id === messageId) {{
                        const originalContent = m.content || "";
                        // Remove existing infographic images
                        const infographicPattern = /\\n*!\\[📊[^\\]]*\\]\\((?:data:image\\/[^)]+|(?:\\/api\\/v1\\/files\\/[^)]+))\\)/g;
                        let cleanedContent = originalContent.replace(infographicPattern, "");
                        cleanedContent = cleanedContent.replace(/\\n{{3,}}/g, "\\n\\n").trim();
                        // Append new image
                        newContent = cleanedContent + "\\n\\n" + markdownImage;
                        
                        // Update history object as well
                        if (chatData.chat.history && chatData.chat.history.messages) {{
                            if (chatData.chat.history.messages[messageId]) {{
                                chatData.chat.history.messages[messageId].content = newContent;
                            }}
                        }}
                        
                        return {{ ...m, content: newContent }};
                    }}
                    return m;
                }});
            }}
            
            if (!newContent) {{
                console.warn("[Infographic Image] Could not find message to update");
                return;
            }}
            
            // Try to update frontend display via event API
            try {{
                await fetch(`/api/v1/chats/${{chatId}}/messages/${{messageId}}/event`, {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${{token}}`
                    }},
                    body: JSON.stringify({{
                        type: "chat:message",
                        data: {{ content: newContent }}
                    }})
                }});
            }} catch (eventErr) {{
                console.log("[Infographic Image] Event API not available, continuing...");
            }}
            
            // Persist to database
            const updatePayload = {{
                chat: {{
                    ...chatData.chat,
                    messages: updatedMessages
                }}
            }};
            
            const persistResponse = await fetchWithRetry(`/api/v1/chats/${{chatId}}`, {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${{token}}`
                }},
                body: JSON.stringify(updatePayload)
            }});
            
            if (persistResponse && persistResponse.ok) {{
                console.log("[Infographic Image] ✅ Message persisted successfully!");
            }} else {{
                console.error("[Infographic Image] ❌ Failed to persist message after retries");
            }}
        }} else {{
            console.warn("[Infographic Image] ⚠️ Missing chatId or messageId, cannot persist");
        }}
        
    }} catch (error) {{
        console.error("[Infographic Image] Error:", error);
    }}
}})();
"""

    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __event_call__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __metadata__: Optional[dict] = None,
        __request__: Optional[Request] = None,
    ) -> Optional[dict]:
        logger.info("Action: Infographic started (v1.6.0)")

        # Get user information
        user_ctx = await self._get_user_context(__user__, __event_call__, __request__)
        user_name = user_ctx["user_name"]
        user_id = user_ctx["user_id"]
        user_language = user_ctx["user_language"]
        user_theme = user_ctx.get("user_theme", "light")

        # Get current time
        now = datetime.now()
        current_date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        current_year = now.strftime("%Y")

        original_content = ""
        try:
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("Unable to get valid user message content.")

            # Get last N messages based on MESSAGE_COUNT
            message_count = min(self.valves.MESSAGE_COUNT, len(messages))
            recent_messages = messages[-message_count:]

            # Aggregate content from selected messages with labels
            aggregated_parts = []
            for i, msg in enumerate(recent_messages, 1):
                text_content = self._extract_text_content(msg.get("content"))
                if text_content:
                    role = msg.get("role", "unknown")
                    role_label = (
                        "User"
                        if role == "user"
                        else "Assistant" if role == "assistant" else role
                    )
                    aggregated_parts.append(f"{text_content}")

            if not aggregated_parts:
                raise ValueError("Unable to get valid user message content.")

            original_content = "\n\n---\n\n".join(aggregated_parts)

            # Extract non-HTML text
            parts = re.split(r"```html.*?```", original_content, flags=re.DOTALL)
            long_text_content = ""
            if parts:
                for part in reversed(parts):
                    if part.strip():
                        long_text_content = part.strip()
                        break

            if not long_text_content:
                long_text_content = original_content.strip()

            # Check text length
            if len(long_text_content) < self.valves.MIN_TEXT_LENGTH:
                short_text_message = f"Text content too short ({len(long_text_content)} characters). Please provide at least {self.valves.MIN_TEXT_LENGTH} characters for effective analysis."
                await self._emit_notification(
                    __event_emitter__, short_text_message, "warning"
                )
                return {
                    "messages": [
                        {"role": "assistant", "content": f"⚠️ {short_text_message}"}
                    ]
                }

            await self._emit_notification(
                __event_emitter__, self._get_translation(user_language, "status_starting"), "info"
            )
            await self._emit_status(
                __event_emitter__,
                self._get_translation(user_language, "status_starting"),
                False,
            )

            # Generate unique ID
            unique_id = f"id_{int(time.time() * 1000)}"

            # Build prompt
            await self._emit_status(
                __event_emitter__,
                self._get_translation(user_language, "status_analyzing"),
                False,
            )
            formatted_user_prompt = USER_PROMPT_GENERATE_INFOGRAPHIC.format(
                user_name=user_name,
                current_date_time_str=current_date_time_str,
                user_language=user_language,
                user_theme=user_theme,
                long_text_content=long_text_content,
            )

            # Determine model to use
            target_model = self.valves.MODEL_ID
            if not target_model:
                target_model = body.get("model")

            llm_payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_INFOGRAPHIC_ASSISTANT},
                    {"role": "user", "content": formatted_user_prompt},
                ],
                "stream": False,
            }

            user_obj = Users.get_user_by_id(user_id)
            if not user_obj:
                raise ValueError(f"Unable to get user object, user ID: {user_id}")

            llm_response = await generate_chat_completion(
                __request__, llm_payload, user_obj
            )

            if (
                not llm_response
                or "choices" not in llm_response
                or not llm_response["choices"]
            ):
                raise ValueError("Invalid LLM response format or empty.")

            await self._emit_status(
                __event_emitter__,
                self._get_translation(user_language, "status_analyzing"),
                False,
            )

            assistant_response_content = llm_response["choices"][0]["message"][
                "content"
            ]
            infographic_syntax = self._extract_infographic_syntax(
                assistant_response_content
            )

            # Prepare content components
            await self._emit_status(
                __event_emitter__,
                self._get_translation(user_language, "status_rendering_image"),
                False,
            )
            content_html = (
                CONTENT_TEMPLATE_INFOGRAPHIC.replace("{unique_id}", unique_id)
                .replace("{user_name}", user_name)
                .replace("{current_date_time_str}", current_date_time_str)
                .replace("{current_year}", current_year)
                .replace("{infographic_syntax}", infographic_syntax)
            )

            # Replace placeholder first, then convert {{ to { and }} to }
            script_html = SCRIPT_TEMPLATE_INFOGRAPHIC.replace("{unique_id}", unique_id)
            script_html = script_html.replace("{{", "{").replace("}}", "}")

            # Extract existing HTML if any
            existing_html_block = ""
            match = re.search(
                r"```html\s*(<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?)```",
                original_content,
            )
            if match:
                existing_html_block = match.group(1)

            if self.valves.CLEAR_PREVIOUS_HTML:
                original_content = self._remove_existing_html(original_content)
                final_html = self._merge_html(
                    "",
                    content_html,
                    CSS_TEMPLATE_INFOGRAPHIC,
                    script_html,
                    user_language,
                )
            else:
                if existing_html_block:
                    original_content = self._remove_existing_html(original_content)
                    final_html = self._merge_html(
                        existing_html_block,
                        content_html,
                        CSS_TEMPLATE_INFOGRAPHIC,
                        script_html,
                        user_language,
                    )
                else:
                    final_html = self._merge_html(
                        "",
                        content_html,
                        CSS_TEMPLATE_INFOGRAPHIC,
                        script_html,
                        user_language,
                    )

            # Check output mode
            if self.valves.OUTPUT_MODE == "image":
                # Image mode: use JavaScript to render and embed as Markdown image
                chat_ctx = self._get_chat_context(body, __metadata__)
                chat_id = chat_ctx["chat_id"]
                message_id = chat_ctx["message_id"]

                await self._emit_status(
                    __event_emitter__,
                    self._get_translation(user_language, "status_rendering_image"),
                    False,
                )

                if __event_call__:
                    js_code = self._generate_image_js_code(
                        unique_id=unique_id,
                        chat_id=chat_id,
                        message_id=message_id,
                        infographic_syntax=infographic_syntax,
                    )

                    await __event_call__(
                        {
                            "type": "execute",
                            "data": {"code": js_code},
                        }
                    )

                await self._emit_status(
                    __event_emitter__, self._get_translation(user_language, "status_image_generated"), True
                )
                await self._emit_notification(
                    __event_emitter__,
                    self._get_translation(user_language, "notification_image_success", user_name=user_name),
                    "success",
                )
                logger.info("Infographic generation completed in image mode")
                return body

            # HTML mode (default): embed as HTML block
            html_embed_tag = f"```html\n{final_html}\n```"
            body["messages"][-1]["content"] = f"{original_content}\n\n{html_embed_tag}"

            await self._emit_status(
                __event_emitter__, self._get_translation(user_language, "status_drawing"), True
            )
            await self._emit_notification(
                __event_emitter__,
                self._get_translation(user_language, "notification_success", user_name=user_name),
                "success",
            )
            logger.info("Infographic generation completed")

        except Exception as e:
            error_message = f"Infographic processing failed: {str(e)}"
            logger.error(f"Infographic error: {error_message}", exc_info=True)
            user_facing_error = f"Sorry, infographic encountered an error during processing: {str(e)}.\nPlease check the Open WebUI backend logs for more details."
            body["messages"][-1][
                "content"
            ] = f"{original_content}\n\n❌ **Error:** {user_facing_error}"

            await self._emit_status(
                __event_emitter__, self._get_translation(user_language, "status_failed"), True
            )
            await self._emit_notification(
                __event_emitter__,
                self._get_translation(user_language, "notification_failed", user_name=user_name),
                "error",
            )

        return body
