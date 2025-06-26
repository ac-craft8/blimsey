# ===============================================================
#  File: summary_manager.py
#  Description: User summary loading and updating utilities
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import json
import os
import re
import traceback
from datetime import datetime

import ollama

from config_loader import load_keyword_phrases, load_model_from_settings

# ================================
#  Function Definitions
# ================================

def get_user_summary_path(user_id):
    """Return path to user's summary file"""
    user_dir = os.path.join('logs', str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, 'summary.json')


def load_user_summary(user_id):
    """Load user summary JSON if present"""
    path = get_user_summary_path(user_id)
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'personal_info': {},
            'preferences': {},
            'important_topics': [],
            'last_updated': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"ERROR loading summary for user {user_id}: {e}")
        return {
            'personal_info': {},
            'preferences': {},
            'important_topics': [],
            'last_updated': datetime.now().isoformat()
        }


def save_user_summary(user_id, summary):
    """Persist merged summary data to disk"""
    path = get_user_summary_path(user_id)
    try:
        summary['last_updated'] = datetime.now().isoformat()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        else:
            existing = {
                'personal_info': {},
                'preferences': {},
                'important_topics': [],
                'contradictions': {},
                'last_updated': datetime.now().isoformat()
            }

        def normalize_to_list(value):
            if isinstance(value, list):
                result = []
                for item in value:
                    if isinstance(item, list):
                        result.extend(item)
                    else:
                        result.append(item)
                return result
            return [value]

        def clean_values(values):
            flat = normalize_to_list(values)
            result = []
            for val in flat:
                if isinstance(val, str):
                    result.extend([v.strip() for v in val.split(',')])
                else:
                    result.append(str(val).strip())
            return sorted(set(v for v in result if v and v.lower() != "no se proporcionó"))

        for key, value in summary.get('personal_info', {}).items():
            new_vals = clean_values(value)
            old_vals = clean_values(existing['personal_info'].get(key, []))
            merged = sorted(set(old_vals + new_vals))
            if merged:
                existing['personal_info'][key] = merged[0] if len(merged) == 1 else merged

        for key, value in summary.get('preferences', {}).items():
            new_vals = clean_values(value)
            old_vals = clean_values(existing['preferences'].get(key, []))
            merged = sorted(set(old_vals + new_vals))
            if merged:
                existing['preferences'][key] = merged[0] if len(merged) == 1 else merged

        new_topics = clean_values(summary.get('important_topics', []))
        for topic in new_topics:
            if topic and topic not in existing['important_topics']:
                existing['important_topics'].append(topic)
        existing['important_topics'] = existing['important_topics'][-10:]
        existing['last_updated'] = summary['last_updated']

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ERROR saving summary for user {user_id}: {e}")


def should_update_summary(prompt, response):
    """Return True if summary should be updated based on keywords"""
    keywords = load_keyword_phrases()
    prompt_lower = prompt.lower()

    for kw in keywords:
        if kw in prompt_lower:
            return True

    patterns = [
        r'\bme llamo \w+', r'\bmi nombre es \w+', r'\bsoy \w+',
        r'\btrabajo en \w+', r'\bvivo en \w+', r'\btengo \d+',
        r'\bmi .+ es \w+', r'\bestoy aprendiendo \w+',
        r'\bme dedico a \w+', r'\bmi profesión es \w+',
        r'\bmi edad es \d+', r'\btengo \d+ años'
    ]
    for pattern in patterns:
        if re.search(pattern, prompt_lower):
            return True

    if len(prompt.split()) > 20:
        return True
    return False


MODEL_NAME = load_model_from_settings()

def update_user_summary(user_id, prompt, response):
    """Analyze conversation and update stored summary"""
    if not should_update_summary(prompt, response):
        print(f"[{user_id}] Summary update not needed - no important keywords detected")
        return

    summary = load_user_summary(user_id)
    print(f"[{user_id}] Summary update triggered - processing...")

    update_prompt = f"""Analiza esta conversación y extrae información importante del usuario:

Conversación:
Usuario: {prompt}
Asistente: {response}

Extrae SOLO información nueva e importante sobre:
- Nombre, edad, ubicación, profesión
- Gustos, preferencias, intereses
- Proyectos, objetivos, metas
- Cualquier dato personal relevante

Responde en formato JSON simple:
{{"personal_info": {{"nombre": "valor", "trabajo": "valor"}}, "preferences": {{"le_gusta": "valor"}}, "important_topics": ["tema"], "changes_made": ["cambio realizado"]}}"""
    try:
        print(f"[{user_id}] Calling AI for summary extraction...")
        ai_response = ollama.generate(model=MODEL_NAME, prompt=update_prompt)['response']
        print(f"[{user_id}] AI Response for summary: {ai_response[:200]}...")

        update_data = None
        patterns = [r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\{.*?\}']
        for pattern in patterns:
            matches = re.findall(pattern, ai_response, re.DOTALL)
            for match in matches:
                try:
                    update_data = json.loads(match.strip())
                    print(f"[{user_id}] JSON parsed successfully with pattern")
                    break
                except json.JSONDecodeError:
                    continue
            if update_data:
                break

        if not update_data:
            print(f"[{user_id}] JSON parsing failed, attempting manual extraction...")
            update_data = {"personal_info": {}, "preferences": {}, "important_topics": [], "changes_made": []}
            name_match = re.search(r'(?:mi nombre es|me llamo|soy)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if name_match:
                update_data["personal_info"]["nombre"] = name_match.group(1).strip().title()
                update_data["changes_made"].append(f"Nombre identificado: {name_match.group(1).strip().title()}")
            work_match = re.search(r'(?:trabajo en|soy|mi trabajo es)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if work_match and 'nombre' not in work_match.group(1).lower():
                update_data["personal_info"]["trabajo"] = work_match.group(1).strip()
                update_data["changes_made"].append(f"Trabajo identificado: {work_match.group(1).strip()}")
            like_match = re.search(r'(?:me gusta|prefiero|amo)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if like_match:
                update_data["preferences"]["le_gusta"] = like_match.group(1).strip()
                update_data["changes_made"].append(f"Preferencia identificada: {like_match.group(1).strip()}")

        if update_data:
            changes_made = False
            if update_data.get('personal_info'):
                for key, value in update_data['personal_info'].items():
                    incoming = ", ".join(value) if isinstance(value, list) else str(value).strip()
                    if incoming:
                        existing = summary['personal_info'].get(key, "")
                        summary['personal_info'][key] = f"{existing}, {incoming}" if existing else incoming
                        changes_made = True
            if update_data.get('preferences'):
                for key, value in update_data['preferences'].items():
                    incoming = ", ".join(value) if isinstance(value, list) else str(value).strip()
                    if incoming:
                        existing = summary['preferences'].get(key, "")
                        summary['preferences'][key] = f"{existing}, {incoming}" if existing else incoming
                        changes_made = True
            if update_data.get('important_topics'):
                for topic in update_data['important_topics']:
                    if topic and topic.strip() and topic not in summary['important_topics']:
                        summary['important_topics'].append(topic.strip())
                        changes_made = True
            summary['important_topics'] = summary['important_topics'][-10:]
            if changes_made:
                save_user_summary(user_id, summary)
                changes = update_data.get('changes_made', ['Información actualizada'])
                print(f"[{user_id}] Summary updated successfully: {changes}")
            else:
                print(f"[{user_id}] No new information to add to summary")
        else:
            print(f"[{user_id}] Could not extract information for summary")
    except Exception as e:
        print(f"ERROR updating summary for user {user_id}: {e}")
        traceback.print_exc()


def get_summary_text(user_id):
    """Return formatted summary text for prompt injection"""
    summary = load_user_summary(user_id)
    parts = []
    if summary['personal_info']:
        info_text = ", ".join([f"{k}: {v}" for k, v in summary['personal_info'].items()])
        parts.append(f"Información personal: {info_text}")
    if summary['preferences']:
        pref_text = ", ".join([f"{k}: {v}" for k, v in summary['preferences'].items()])
        parts.append(f"Preferencias: {pref_text}")
    if summary['important_topics']:
        topics_text = ", ".join(summary['important_topics'])
        parts.append(f"Temas importantes: {topics_text}")
    return ". ".join(parts) if parts else "No hay información de resumen disponible."
