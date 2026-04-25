#!/usr/bin/env python3
"""
CLI Node Editor - Éditeur nodal pour créer des scripts BAT
Permet de créer des noeuds personnalisés réutilisables pour n'importe quelle application CLI

Version améliorée avec:
- Édition des noeuds existants dans la bibliothèque
- Utilisation de noeuds existants comme templates
- Affichage et édition des paramètres directement sur les noeuds
- Ordre d'exécution visible sur chaque noeud
"""

import sys
import json
import os
import math
import uuid
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                              QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
                              QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QComboBox, QPushButton, QLineEdit, QTextEdit, QFileDialog,
                              QMessageBox, QWidget, QFormLayout, QScrollArea, QListWidget,
                              QListWidgetItem,
                              QSplitter, QGroupBox, QCheckBox, QSpinBox, QTabWidget,
                              QTableWidget, QTableWidgetItem, QHeaderView, QGraphicsProxyWidget,
                              QFrame, QSizePolicy, QInputDialog)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QLineF, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import (QPen, QBrush, QColor, QPainter, QFont, QPainterPath,
                         QPainterPathStroker, QCursor, QTextCharFormat, QTransform,
                         QSyntaxHighlighter)


def normalize_output_extension(extension):
    """Normalise une extension de sortie explicite."""
    if extension is None:
        return ""

    extension = str(extension).strip()
    if not extension:
        return ""

    if extension.startswith(".") or "%" in extension or ("{" in extension and "}" in extension):
        return extension

    return f".{extension}"


def get_display_node_name(node_data):
    """Retourne un nom court pour l'affichage en évitant les préfixes redondants."""
    explicit_display_name = str(node_data.get('display_name', '')).strip()
    if explicit_display_name:
        return explicit_display_name

    name = str(node_data.get('name', '')).strip()
    category = str(node_data.get('category', '')).strip()
    if not name or not category:
        return name

    prefix = f"{category} - "
    if name.lower().startswith(prefix.lower()):
        return name[len(prefix):].strip()

    return name


def get_display_category(node_data):
    """Retourne la catégorie enrichie avec la sous-catégorie si disponible."""
    category = str(node_data.get('category', '')).strip() or 'Custom'
    subcategory = str(node_data.get('subcategory', '')).strip()
    return f"{category} / {subcategory}" if subcategory else category


def remove_connection_safely(scene, conn):
    """Supprime une connexion et nettoie ses références sans lever d'erreur."""
    if conn is None:
        return

    dirty_rect = None
    try:
        dirty_rect = conn.sceneBoundingRect().adjusted(-8, -8, 8, 8)
    except RuntimeError:
        dirty_rect = None

    try:
        if scene is not None and conn.scene() is scene:
            scene.removeItem(conn)
    except RuntimeError:
        pass

    try:
        if conn.start_port and conn in conn.start_port.connections:
            conn.start_port.connections.remove(conn)
    except RuntimeError:
        pass

    try:
        if conn.end_port and conn in conn.end_port.connections:
            conn.end_port.connections.remove(conn)
    except RuntimeError:
        pass

    try:
        conn.start_port = None
        conn.end_port = None
        conn.temp_end_pos = None
    except RuntimeError:
        pass

    try:
        if scene is not None:
            if dirty_rect is not None:
                scene.update(dirty_rect)
            else:
                scene.update()
    except RuntimeError:
        pass


def quote_shell_string(value):
    """Quote une chaîne pour Bash avec apostrophes sûres."""
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


SYSTEM_SOURCE_NODE_NAMES = ["Fichier Input", "Fichier Source", "Fichier Destination", "Multi-fichiers"]
MULTI_FILE_NODE_NAME = "Multi-fichiers"
MULTI_FILE_MAX_SLOTS = 4
GLOBAL_VARIABLES_NODE_NAME = "Variables Globales"
GLOBAL_VARIABLES_MAX_INPUTS = 12
GLOBAL_VARIABLES_MAX_SLOTS = 12
INPUT_VARIABLES_NODE_NAME = "Variables d'entrée"
INPUT_VARIABLES_MAX_SLOTS = 12
SWITCH_NODE_NAME = "Switch"
SWITCH_MAX_CONDITIONS = 6
MERGE_NODE_NAME = "Merge"
MERGE_MAX_INPUTS = 6


def build_global_variables_parameters():
    """Construit les parametres du noeud Variables Globales."""
    parameters = [
        {"name": "Nombre de variables", "type": "number", "default": "2"}
    ]
    for index in range(1, GLOBAL_VARIABLES_MAX_SLOTS + 1):
        parameters.extend([
            {"name": f"Nom {index}", "type": "text", "default": "size" if index == 1 else ""},
            {"name": f"Valeur {index}", "type": "text", "default": "{input}x{input2}" if index == 1 else ""}
        ])
    return parameters


def build_input_variables_parameters():
    """Construit les parametres du noeud Variables d'entree."""
    parameters = [
        {"name": "Nombre de variables", "type": "number", "default": "2"}
    ]
    for index in range(1, INPUT_VARIABLES_MAX_SLOTS + 1):
        parameters.extend([
            {"name": f"Question {index}", "type": "text", "default": f"Valeur pour la variable {index} ?" if index > 1 else "Quel nom utiliser ?"},
            {"name": f"Nom {index}", "type": "text", "default": "nom" if index == 1 else ""},
            {"name": f"Valeur par défaut {index}", "type": "text", "default": ""}
        ])
    return parameters


def build_switch_parameters():
    """Construit les paramètres du noeud Switch."""
    parameters = [
        {"name": "Variable", "type": "text", "default": "%INPUT_EXT%"},
        {"name": "Nombre de conditions", "type": "number", "default": "2"}
    ]
    for index in range(1, SWITCH_MAX_CONDITIONS + 1):
        parameters.extend([
            {"name": f"Opérateur {index}", "type": "choice", "default": "==", "choices": [">", ">=", "<", "<=", "==", "!="]},
            {"name": f"Valeur {index}", "type": "text", "default": ""},
            {"name": f"Label sortie {index}", "type": "text", "default": f"Cas {index}"}
        ])
    return parameters


def build_merge_parameters():
    """Construit les paramètres du noeud Merge."""
    return [
        {"name": "Nombre d'entrées", "type": "number", "default": "2"}
    ]


class DependencyManager:
    """Gestion des chemins vers les dépendances et applications CLI personnalisées"""
    
    def __init__(self, config_file="dependencies.json"):
        self.config_file = config_file
        self.dependencies = {}
        self.load()
    
    def load(self):
        """Charge la configuration des dépendances"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.dependencies = json.load(f)
            except:
                self.dependencies = self._get_defaults()
        else:
            self.dependencies = self._get_defaults()
            self.save()
    
    def save(self):
        """Sauvegarde la configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.dependencies, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur de sauvegarde des dépendances: {e}")
    
    def _get_defaults(self):
        """Dépendances par défaut"""
        return {
            "ffmpeg": {"path": "ffmpeg", "description": "Outil de manipulation audio/vidéo", "version_arg": "-version"},
            "sox": {"path": "sox", "description": "Swiss Army knife of audio", "version_arg": "--version"},
            "magick": {"path": "magick", "description": "ImageMagick - manipulation d'images", "version_arg": "--version"},
            "yt-dlp": {"path": "yt-dlp", "description": "Téléchargeur YouTube", "version_arg": "--version"},
            "exiftool": {"path": "exiftool", "description": "Manipulation de métadonnées", "version_arg": "-ver"},
            "7z": {"path": "7z", "description": "Compression/décompression d'archives", "version_arg": ""},
            "curl": {"path": "curl", "description": "Transfert de données URL", "version_arg": "--version"},
            "pandoc": {"path": "pandoc", "description": "Convertisseur de documents", "version_arg": "--version"},
            "HandBrakeCLI": {"path": "HandBrakeCLI", "description": "Encodeur vidéo", "version_arg": "--version"},
            "lame": {"path": "lame", "description": "Encodeur MP3", "version_arg": "--version"},
            "flac": {"path": "flac", "description": "Encodeur FLAC", "version_arg": "--version"},
            "tesseract": {"path": "tesseract", "description": "OCR - reconnaissance de texte", "version_arg": "--version"},
            "whisper": {"path": "whisper", "description": "Transcription audio OpenAI", "version_arg": "--help"},
            "rclone": {"path": "rclone", "description": "Sync cloud storage", "version_arg": "version"},
            "optipng": {"path": "optipng", "description": "Optimisation PNG", "version_arg": "-version"},
            "jpegoptim": {"path": "jpegoptim", "description": "Optimisation JPEG", "version_arg": "--version"}
        }
    
    def get(self, tool_name):
        """Récupère le chemin d'un outil"""
        tool = self.dependencies.get(tool_name, {})
        if isinstance(tool, dict):
            return tool.get('path', tool_name)
        return tool  # Rétrocompatibilité avec ancien format
    
    def get_info(self, tool_name):
        """Récupère les infos complètes d'un outil"""
        tool = self.dependencies.get(tool_name, {})
        if isinstance(tool, dict):
            return tool
        # Rétrocompatibilité
        return {"path": tool, "description": "", "version_arg": "--version"}
    
    def set(self, tool_name, path, description="", version_arg="--version"):
        """Définit le chemin d'un outil"""
        self.dependencies[tool_name] = {
            "path": path,
            "description": description,
            "version_arg": version_arg
        }
        self.save()
    
    def add_tool(self, tool_name, path, description="", version_arg="--version"):
        """Ajoute un nouvel outil CLI"""
        self.set(tool_name, path, description, version_arg)
    
    def remove_tool(self, tool_name):
        """Supprime un outil"""
        if tool_name in self.dependencies:
            del self.dependencies[tool_name]
            self.save()
    
    def get_all_tools(self):
        """Retourne tous les outils"""
        return self.dependencies
    
    def get_tool_names(self):
        """Retourne la liste des noms d'outils"""
        return list(self.dependencies.keys())


class NodeLibrary:
    """Gestion de la bibliothèque de noeuds personnalisés"""
    
    def __init__(self, library_file="node_library.json"):
        self.library_file = library_file
        self.nodes = {}
        self.load()
    
    def load(self):
        """Charge la bibliothèque depuis le fichier JSON"""
        if os.path.exists(self.library_file):
            try:
                with open(self.library_file, 'r', encoding='utf-8') as f:
                    raw_nodes = json.load(f)
                    changed = False
                    self.nodes = {}
                    for node_name, node_data in raw_nodes.items():
                        normalized = self._normalize_node_data(node_data)
                        self.nodes[node_name] = normalized
                        if normalized != node_data:
                            changed = True
                    default_nodes = self._get_default_nodes()
                    for node_name, node_data in default_nodes.items():
                        if node_name not in self.nodes:
                            self.nodes[node_name] = self._normalize_node_data(node_data)
                            changed = True
                    if changed:
                        self.save()
            except Exception as e:
                print(f"Erreur de chargement de la bibliothèque: {e}")
                self.nodes = {}
        else:
            self.nodes = self._get_default_nodes()
            self.save()
    
    def save(self):
        """Sauvegarde la bibliothèque dans le fichier JSON"""
        try:
            with open(self.library_file, 'w', encoding='utf-8') as f:
                json.dump(self.nodes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur de sauvegarde de la bibliothèque: {e}")
    
    def add_node(self, node_data):
        """Ajoute un noeud à la bibliothèque"""
        node_id = node_data['name']
        self.nodes[node_id] = node_data
        self.save()
    
    def update_node(self, old_name, node_data):
        """Met à jour un noeud existant (avec possibilité de renommer)"""
        if old_name in self.nodes and old_name != node_data['name']:
            del self.nodes[old_name]
        self.nodes[node_data['name']] = node_data
        self.save()
    
    def remove_node(self, node_id):
        """Supprime un noeud de la bibliothèque"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.save()
    
    def get_node(self, node_id):
        """Récupère un noeud de la bibliothèque"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self):
        """Retourne tous les noeuds"""
        return self.nodes
    
    def _get_default_nodes(self):
        """Noeuds par défaut pour démarrer"""
        return {
            "Fichier Input": {
                "name": "Fichier Input",
                "category": "Fichier",
                "command": "",
                "description": "Point d'entrée - Représente chaque fichier passé au BAT (via SendTo ou drag&drop)",
                "color": "#FFB6C1",
                "verified": True,
                "inputs": [],
                "outputs": ["file"],
                "parameters": [],
                "template": "",
                "output_extension": "",
                "use_batch_vars": True
            },
            "Fichier Source": {
                "name": "Fichier Source",
                "category": "Fichier",
                "command": "",
                "description": "Point d'entrée avec chemin fixe (pour workflow one-shot)",
                "color": "#FFB6C1",
                "verified": True,
                "inputs": [],
                "outputs": ["file"],
                "parameters": [
                    {"name": "Chemin fichier", "type": "file", "default": ""}
                ],
                "template": "",
                "output_extension": ""
            },
            "Fichier Destination": {
                "name": "Fichier Destination",
                "category": "Fichier",
                "command": "",
                "description": "Point de sortie - Utilisez %INPUT_NAME% pour le nom original, %INPUT_PATH% pour le dossier",
                "color": "#FFB6C1",
                "verified": True,
                "inputs": ["file"],
                "outputs": [],
                "parameters": [
                    {"name": "Nom fichier", "type": "text", "default": "%INPUT_NAME%_converted"},
                    {"name": "Extension", "type": "text", "default": ".mp4"},
                    {"name": "Dossier de sortie", "type": "text", "default": ""}
                ],
                "template": "",
                "output_extension": ""
            },
            MULTI_FILE_NODE_NAME: {
                "name": MULTI_FILE_NODE_NAME,
                "category": "Fichier",
                "command": "",
                "description": "Point d'entrée multi-fichiers pour le mode flux unique. Identifie chaque fichier par extension et expose une sortie par type attendu.",
                "color": "#FFD1A9",
                "inputs": [],
                "outputs": ["file", "file"],
                "parameters": [
                    {"name": "Nombre de fichiers", "type": "number", "default": "2"},
                    {"name": "Type fichier 1", "type": "text", "default": "Vidéo"},
                    {"name": "Extensions fichier 1", "type": "text", "default": ".mp4,.mov,.avi,.mkv,.webm"},
                    {"name": "Type fichier 2", "type": "text", "default": "Sous-titres"},
                    {"name": "Extensions fichier 2", "type": "text", "default": ".srt,.ssa,.ass,.sub,.idx"},
                    {"name": "Type fichier 3", "type": "text", "default": "Fichier 3"},
                    {"name": "Extensions fichier 3", "type": "text", "default": ""},
                    {"name": "Type fichier 4", "type": "text", "default": "Fichier 4"},
                    {"name": "Extensions fichier 4", "type": "text", "default": ""}
                ],
                "template": "",
                "output_extension": ""
            },
            GLOBAL_VARIABLES_NODE_NAME: {
                "name": GLOBAL_VARIABLES_NODE_NAME,
                "category": "SystÃ¨me",
                "command": "",
                "description": "Lit plusieurs fichiers texte et expose des variables globales utilisables dans tous les noeuds via {nom_variable}.",
                "color": "#B8E6B8",
                "inputs": ["file", "file"],
                "outputs": [],
                "parameters": build_global_variables_parameters(),
                "template": "",
                "output_extension": ""
            },
            INPUT_VARIABLES_NODE_NAME: {
                "name": INPUT_VARIABLES_NODE_NAME,
                "category": "Système",
                "command": "",
                "description": "Pose des questions au debut du script et expose les reponses dans tout le workflow via {nom_variable}.",
                "color": "#B8D8FF",
                "inputs": [],
                "outputs": [],
                "parameters": build_input_variables_parameters(),
                "template": "",
                "output_extension": ""
            },
            SWITCH_NODE_NAME: {
                "name": SWITCH_NODE_NAME,
                "category": "Système",
                "command": "",
                "description": "Branchement conditionnel. Compare une valeur comme %INPUT_EXT% et route le fichier vers la première sortie correspondante, sinon vers Défaut.",
                "color": "#F4D35E",
                "verified": True,
                "inputs": ["file"],
                "outputs": ["file", "file", "file"],
                "parameters": build_switch_parameters(),
                "template": "",
                "output_extension": ""
            },
            MERGE_NODE_NAME: {
                "name": MERGE_NODE_NAME,
                "category": "Système",
                "command": "",
                "description": "Fusionne plusieurs branches en un seul flux. La première entrée disponible est renvoyée vers la sortie.",
                "color": "#9BC1BC",
                "verified": True,
                "inputs": ["file", "file"],
                "outputs": ["file"],
                "parameters": build_merge_parameters(),
                "template": "",
                "output_extension": ""
            }
        }

    def _normalize_node_data(self, node_data):
        """Uniformise le schéma des noeuds et migre l'ancien champ d'extension implicite."""
        normalized = dict(node_data)
        if normalized.get('name') == GLOBAL_VARIABLES_NODE_NAME:
            normalized['category'] = 'SystÃ¨me'
            normalized['command'] = ''
            normalized['description'] = (
                "Lit plusieurs fichiers texte et expose des variables globales "
                "utilisables dans tous les noeuds via {nom_variable}."
            )
            normalized['color'] = '#B8E6B8'
            normalized['inputs'] = ['file', 'file']
            normalized['outputs'] = []
            normalized['parameters'] = build_global_variables_parameters()
            normalized['template'] = ''
            normalized['output_extension'] = ''
        if normalized.get('name') == INPUT_VARIABLES_NODE_NAME:
            normalized['category'] = 'Système'
            normalized['command'] = ''
            normalized['description'] = (
                "Pose des questions au debut du script et expose les reponses "
                "dans tout le workflow via {nom_variable}."
            )
            normalized['color'] = '#B8D8FF'
            normalized['inputs'] = []
            normalized['outputs'] = []
            normalized['parameters'] = build_input_variables_parameters()
            normalized['template'] = ''
            normalized['output_extension'] = ''
        if normalized.get('name') == GLOBAL_VARIABLES_NODE_NAME:
            normalized['category'] = 'Système'
            normalized['subcategory'] = 'Variables'
            normalized['verified'] = True
        elif normalized.get('name') == INPUT_VARIABLES_NODE_NAME:
            normalized['category'] = 'Système'
            normalized['subcategory'] = 'Variables'
            normalized['verified'] = True
        elif normalized.get('name') == SWITCH_NODE_NAME:
            normalized['category'] = 'Système'
            normalized['subcategory'] = 'Contrôle'
            normalized['command'] = ''
            normalized['description'] = (
                "Branchement conditionnel. Compare une valeur comme %INPUT_EXT% "
                "et route le fichier vers la première sortie correspondante, "
                "sinon vers Défaut."
            )
            normalized['color'] = '#F4D35E'
            normalized['verified'] = True
            normalized['inputs'] = ['file']
            normalized['parameters'] = build_switch_parameters()
            try:
                condition_count = int(normalized.get('parameters', [{}])[1].get('default', '2') or 2)
            except Exception:
                condition_count = 2
            condition_count = max(1, min(SWITCH_MAX_CONDITIONS, condition_count))
            normalized['outputs'] = ['file'] * (condition_count + 1)
        elif normalized.get('name') == MERGE_NODE_NAME:
            normalized['category'] = 'Système'
            normalized['subcategory'] = 'Contrôle'
            normalized['command'] = ''
            normalized['description'] = (
                "Fusionne plusieurs branches en un seul flux. La première "
                "entrée disponible est renvoyée vers la sortie."
            )
            normalized['color'] = '#9BC1BC'
            normalized['verified'] = True
            normalized['parameters'] = build_merge_parameters()
            try:
                input_count = int(normalized.get('parameters', [{}])[0].get('default', '2') or 2)
            except Exception:
                input_count = 2
            input_count = max(2, min(MERGE_MAX_INPUTS, input_count))
            normalized['inputs'] = ['file'] * input_count
            normalized['outputs'] = ['file']
        elif normalized.get('name') in ['Fichier Input', 'Fichier Source', 'Fichier Destination']:
            normalized['verified'] = True
        if 'display_name' not in normalized:
            normalized['display_name'] = get_display_node_name(normalized)
        if 'subcategory' not in normalized:
            normalized['subcategory'] = ''
        if 'verified' not in normalized:
            normalized['verified'] = False
        if 'output_extension' not in normalized:
            normalized['output_extension'] = self._infer_legacy_output_extension(normalized)
        else:
            normalized['output_extension'] = normalize_output_extension(normalized.get('output_extension'))
        if 'output_extension_choices' not in normalized:
            normalized['output_extension_choices'] = self._suggest_output_extensions(
                normalized,
                normalized.get('output_extension', '')
            )
        else:
            normalized['output_extension_choices'] = [
                normalize_output_extension(choice)
                for choice in normalized.get('output_extension_choices', [])
                if str(choice).strip()
            ]
            if normalized.get('output_extension') and normalized['output_extension'] not in normalized['output_extension_choices']:
                normalized['output_extension_choices'].insert(0, normalized['output_extension'])
        return normalized

    def _suggest_output_extensions(self, node_data, default_extension=""):
        """Retourne une liste de formats suggérés pour l'édition directe sur le noeud."""
        name = node_data.get('name', '').lower()
        template = node_data.get('template', '').lower()
        command_name = node_data.get('command', '').lower()
        default_extension = normalize_output_extension(default_extension)

        choices = []

        if command_name == 'whisper':
            choices = ['.txt', '.srt', '.vtt', '.json', '{output_format}']
        elif command_name == 'magick':
            choices = ['.png', '.jpg', '.webp', '.gif', '.tiff']
        elif command_name == 'tesseract':
            choices = ['.txt']
        elif command_name == 'yt-dlp' and 'audio' in name:
            choices = ['.mp3', '.aac', '.flac', '.opus', '.wav', '{format}']
        elif command_name == 'yt-dlp' and 'miniature' in name:
            choices = ['.jpg', '.png', '.webp']
        else:
            if any(kw in template or kw in name for kw in ['audio', 'mp3', 'flac', 'wav', 'aac', 'opus', 'ogg', 'sox', 'lame']):
                choices = ['.wav', '.mp3', '.flac', '.aac', '.opus', '.ogg']
            elif any(kw in template or kw in name for kw in ['video', 'mp4', 'mkv', 'avi', 'webm', 'mov', 'libx264', 'libx265', 'vp9', 'av1', 'prores']):
                choices = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
            elif any(kw in template or kw in name for kw in ['image', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'tiff', 'magick']):
                choices = ['.png', '.jpg', '.webp', '.gif', '.tiff']
            elif 'pandoc' in template or command_name == 'pandoc':
                choices = ['.md', '.html', '.pdf', '.docx', '.txt']
            elif '7z' in template or command_name == '7z':
                choices = ['.zip', '.7z']
            else:
                choices = ['.tmp']

        normalized_choices = []
        for choice in choices:
            choice = normalize_output_extension(choice)
            if choice and choice not in normalized_choices:
                normalized_choices.append(choice)

        if default_extension:
            normalized_choices = [default_extension] + [
                choice for choice in normalized_choices if choice != default_extension
            ]

        return normalized_choices

    def _infer_legacy_output_extension(self, node_data):
        """Migration douce depuis l'ancien comportement basé sur l'inférence."""
        name = node_data.get('name', '')
        if name in ['Fichier Input', 'Fichier Source', 'Fichier Destination']:
            return ""

        if not node_data.get('outputs'):
            return ""

        template = node_data.get('template', '').lower()
        node_name = name.lower()
        command_name = node_data.get('command', '').lower()

        if command_name == 'tesseract':
            return '.txt'
        if command_name == 'whisper':
            return '{output_format}'
        if command_name == 'magick':
            return '.png'
        if command_name == 'yt-dlp' and 'miniature' in node_name:
            return '.jpg'
        if command_name == 'yt-dlp' and 'audio' in node_name:
            return '{format}'

        audio_keywords = ['audio', 'mp3', 'flac', 'wav', 'aac', 'opus', 'ogg', 'lame',
                         'loudnorm', 'normaliser audio', 'sox', 'pitch', 'tempo',
                         'reverb', 'echo', 'fade', 'bass', 'treble', 'compand']
        if any(kw in template or kw in node_name for kw in audio_keywords):
            if 'libmp3lame' in template or 'mp3' in node_name:
                return '.mp3'
            if 'flac' in template or 'flac' in node_name:
                return '.flac'
            if 'aac' in template:
                return '.aac'
            if 'opus' in template or 'libopus' in template:
                return '.opus'
            if 'pcm_s16le' in template or 'wav' in node_name or 'sox' in template:
                return '.wav'
            return '.wav'

        video_keywords = ['video', 'mp4', 'mkv', 'avi', 'webm', 'mov', 'libx264',
                         'libx265', 'vp9', 'av1', 'prores', 'scale', 'fps',
                         'transpose', 'hflip', 'vflip', 'crop']
        if any(kw in template or kw in node_name for kw in video_keywords):
            if 'webm' in template or 'vp9' in template or 'webm' in node_name:
                return '.webm'
            if 'mkv' in node_name:
                return '.mkv'
            if 'mov' in node_name or 'prores' in template:
                return '.mov'
            if 'avi' in node_name:
                return '.avi'
            return '.mp4'

        image_keywords = ['image', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'tiff',
                         'magick', 'resize', 'crop', 'blur', 'sharpen', 'rotate']
        if any(kw in template or kw in node_name for kw in image_keywords):
            if 'png' in node_name or 'png' in template:
                return '.png'
            if 'gif' in node_name or 'gif' in template:
                return '.gif'
            if 'webp' in node_name:
                return '.webp'
            if 'tiff' in node_name or 'tif' in node_name:
                return '.tiff'
            return '.jpg'

        if 'pandoc' in template:
            if 'html' in template:
                return '.html'
            if 'pdf' in template:
                return '.pdf'
            if 'docx' in template:
                return '.docx'
            return '.md'

        if '7z' in template:
            if '-tzip' in template:
                return '.zip'
            return '.7z'

        if 'tesseract' in template:
            return '.txt'
        if 'whisper' in template:
            if 'json' in template:
                return '.json'
            if 'vtt' in template:
                return '.vtt'
            if 'srt' in template:
                return '.srt'
            return '.txt'
        if 'yt-dlp' in template and 'thumbnail' in node_name:
            return '.jpg'

        return '.tmp'


class BatchSyntaxHighlighter(QSyntaxHighlighter):
    """Coloration syntaxique légère pour la prévisualisation Batch."""

    def __init__(self, document):
        super().__init__(document)
        self.comment_format = self._make_format("#6A9955")
        self.label_format = self._make_format("#C586C0", bold=True)
        self.keyword_format = self._make_format("#569CD6", bold=True)
        self.variable_format = self._make_format("#4EC9B0")
        self.string_format = self._make_format("#CE9178")
        self.command_format = self._make_format("#DCDCAA")
        self.error_format = self._make_format("#F44747", bold=True)

        self.keywords = {
            "if", "else", "for", "set", "setlocal", "endlocal", "goto", "call",
            "shift", "exit", "pause", "copy", "del", "mkdir", "echo", "timeout",
            "not", "exist", "neq", "gtr"
        }
        self.commands = {"ffmpeg", "sox", "magick", "curl", "pandoc", "robocopy", "powershell"}

    def _make_format(self, color, bold=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def highlightBlock(self, text):
        stripped = text.lstrip()
        if not stripped:
            return

        if stripped.upper().startswith("REM"):
            self.setFormat(0, len(text), self.comment_format)
            return

        if stripped.startswith("::") or stripped.startswith(":"):
            self.setFormat(0, len(text), self.label_format)
            return

        for start_token, end_token in [('"', '"')]:
            start = text.find(start_token)
            while start != -1:
                end = text.find(end_token, start + 1)
                if end == -1:
                    end = len(text) - 1
                self.setFormat(start, end - start + 1, self.string_format)
                start = text.find(start_token, end + 1)

        idx = 0
        while idx < len(text):
            if text[idx] == "%":
                end = text.find("%", idx + 1)
                if end != -1:
                    self.setFormat(idx, end - idx + 1, self.variable_format)
                    idx = end + 1
                    continue
            if text[idx] == "!":
                end = text.find("!", idx + 1)
                if end != -1:
                    self.setFormat(idx, end - idx + 1, self.variable_format)
                    idx = end + 1
                    continue
            idx += 1

        words = text.replace("(", " ").replace(")", " ").replace("=", " ").split()
        cursor = 0
        for word in words:
            start = text.find(word, cursor)
            if start == -1:
                continue
            lower_word = word.lower()
            if lower_word in self.keywords:
                self.setFormat(start, len(word), self.keyword_format)
            elif lower_word in self.commands or word.startswith('"') and lower_word.strip('"') in self.commands:
                self.setFormat(start, len(word), self.command_format)
            elif "erreur" in lower_word:
                self.setFormat(start, len(word), self.error_format)
            cursor = start + len(word)


class NodePort(QGraphicsEllipseItem):
    """Port de connexion sur un noeud"""
    
    def __init__(self, parent, port_type, index=0):
        super().__init__(-6, -6, 12, 12, parent)
        self.parent_node = parent
        self.port_type = port_type  # 'input' ou 'output'
        self.index = index
        self.connections = []
        
        # Style du port
        self.setBrush(QBrush(QColor('#4ECDC4')))
        self.setPen(QPen(QColor('#2C3E50'), 2))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor('#FFFFFF')))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor('#4ECDC4')))
        super().hoverLeaveEvent(event)


class Connection(QGraphicsItem):
    """Connexion entre deux ports avec courbe de Bézier"""
    
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.temp_end_pos = None
        
        # Style de la connexion
        self.line_color = QColor('#4ECDC4')
        self.line_width = 3
        self.hover_color = QColor('#FFFFFF')
        self.is_hovered = False
        
        # Animation parameters
        self.curvature = 0.5  # Contrôle la courbure (0.0 - 1.0)
        
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        
    def boundingRect(self):
        """Rectangle englobant pour le rendu"""
        if self.start_port:
            try:
                start_pos = self.start_port.scenePos()
                if self.end_port:
                    end_pos = self.end_port.scenePos()
                elif self.temp_end_pos:
                    end_pos = self.temp_end_pos
                else:
                    return QRectF()
            except RuntimeError:
                return QRectF()
            
            # Ajouter une marge pour la courbe
            min_x = min(start_pos.x(), end_pos.x()) - 50
            min_y = min(start_pos.y(), end_pos.y()) - 50
            max_x = max(start_pos.x(), end_pos.x()) + 50
            max_y = max(start_pos.y(), end_pos.y()) + 50
            
            return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        return QRectF()
    
    def shape(self):
        """Forme pour la détection de collision/sélection"""
        path = self._create_bezier_path()
        stroker = QPainterPathStroker()
        stroker.setWidth(15)  # Zone de sélection plus large
        return stroker.createStroke(path)
    
    def _create_bezier_path(self):
        """Crée le chemin de Bézier"""
        path = QPainterPath()
        
        if not self.start_port:
            return path

        try:
            start_pos = self.start_port.scenePos()

            if self.end_port:
                end_pos = self.end_port.scenePos()
            elif self.temp_end_pos:
                end_pos = self.temp_end_pos
            else:
                return path
        except RuntimeError:
            return path
        
        path.moveTo(start_pos)
        
        # Calcul des points de contrôle pour une courbe élégante
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        
        # Distance horizontale pour les points de contrôle
        ctrl_offset = abs(dx) * self.curvature
        ctrl_offset = max(ctrl_offset, 50)  # Minimum de courbure
        
        # Points de contrôle
        ctrl1 = QPointF(start_pos.x() + ctrl_offset, start_pos.y())
        ctrl2 = QPointF(end_pos.x() - ctrl_offset, end_pos.y())
        
        # Si la connexion va vers la gauche, ajuster les points de contrôle
        if dx < 0:
            # Connexion qui "revient en arrière" - faire une boucle élégante
            vertical_offset = max(abs(dy) * 0.5, 80)
            ctrl1 = QPointF(start_pos.x() + 80, start_pos.y() + vertical_offset)
            ctrl2 = QPointF(end_pos.x() - 80, end_pos.y() + vertical_offset)
        
        path.cubicTo(ctrl1, ctrl2, end_pos)
        
        return path
    
    def paint(self, painter, option, widget):
        """Dessine la courbe de Bézier"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = self._create_bezier_path()
        
        if path.isEmpty():
            return
        
        # Couleur selon l'état
        if self.is_hovered or self.isSelected():
            color = self.hover_color
            width = self.line_width + 2
        else:
            color = self.line_color
            width = self.line_width
        
        # Ombre portée pour effet de profondeur
        shadow_pen = QPen(QColor(0, 0, 0, 50), width + 4)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(shadow_pen)
        painter.drawPath(path.translated(2, 2))
        
        # Ligne principale
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # Effet de brillance (ligne plus fine au centre)
        if not self.is_hovered:
            highlight_pen = QPen(QColor(255, 255, 255, 60), width * 0.4)
            highlight_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(highlight_pen)
            painter.drawPath(path)
        
        # Flèche directionnelle au milieu de la courbe
        self._draw_direction_arrow(painter, path)
    
    def _draw_direction_arrow(self, painter, path):
        """Dessine une petite flèche au milieu de la courbe"""
        if path.isEmpty():
            return
        
        # Point au milieu de la courbe
        mid_point = path.pointAtPercent(0.5)
        
        # Tangente au point médian pour l'orientation
        t = 0.5
        delta = 0.01
        p1 = path.pointAtPercent(max(0, t - delta))
        p2 = path.pointAtPercent(min(1, t + delta))
        
        # Angle de la tangente
        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        
        # Dessiner un petit triangle
        arrow_size = 8
        arrow_path = QPainterPath()
        
        # Points du triangle
        p_tip = QPointF(
            mid_point.x() + arrow_size * math.cos(angle),
            mid_point.y() + arrow_size * math.sin(angle)
        )
        p_left = QPointF(
            mid_point.x() + arrow_size * 0.6 * math.cos(angle + 2.5),
            mid_point.y() + arrow_size * 0.6 * math.sin(angle + 2.5)
        )
        p_right = QPointF(
            mid_point.x() + arrow_size * 0.6 * math.cos(angle - 2.5),
            mid_point.y() + arrow_size * 0.6 * math.sin(angle - 2.5)
        )
        
        arrow_path.moveTo(p_tip)
        arrow_path.lineTo(p_left)
        arrow_path.lineTo(p_right)
        arrow_path.closeSubpath()
        
        # Dessiner la flèche
        color = self.hover_color if self.is_hovered else self.line_color
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(arrow_path)
    
    def hoverEnterEvent(self, event):
        """Survol de la connexion"""
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Fin du survol"""
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.setSelected(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction("Supprimer la liaison")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            scene = self.scene()
            remove_connection_safely(scene, self)
            if scene is not None:
                main_window = scene.views()[0].window() if scene.views() else None
                if main_window is not None and hasattr(main_window, 'mark_workflow_dirty'):
                    main_window.mark_workflow_dirty()
            event.accept()
            return
        super().contextMenuEvent(event)
    
    def update_position(self):
        """Met à jour la position de la courbe"""
        try:
            self.prepareGeometryChange()
            self.update()
        except RuntimeError:
            pass


class ChoicePopupDialog(QDialog):
    """Popup flottant pour sélectionner une valeur sans dépendre du canvas."""

    valueSelected = pyqtSignal(str)

    def __init__(self, choices, current_value="", parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(140)

        layout = QVBoxLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 10px;
                background: white;
                border: 1px solid #bdc3c7;
                outline: none;
            }
            QListWidget::item {
                padding: 4px 8px;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background: #eaf4fb;
            }
        """)

        for choice in choices:
            item = QListWidgetItem(str(choice))
            self.list_widget.addItem(item)
            if str(choice) == str(current_value):
                self.list_widget.setCurrentItem(item)

        self.list_widget.itemClicked.connect(self._select_item)
        self.list_widget.itemActivated.connect(self._select_item)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.resize(self.minimumWidth(), min(260, max(90, self.list_widget.sizeHintForRow(0) * max(1, min(len(choices), 8)) + 6)))

    def _select_item(self, item):
        self.valueSelected.emit(item.text())
        self.accept()


class ParameterWidget(QWidget):
    """Widget pour afficher et éditer un paramètre directement sur le noeud"""
    
    parameterChanged = pyqtSignal(str, str)  # (param_name, new_value)
    linkRequested = pyqtSignal(str)
    unlinkRequested = pyqtSignal(str)
    
    def __init__(self, param_name, param_type, param_value, param_choices=None, parent=None):
        super().__init__(parent)
        self.param_name = param_name
        self.param_type = param_type
        self.param_choices = [str(choice) for choice in (param_choices or [])]
        self.choice_button = None
        self.choice_line_edit = None
        self.choice_popup = None
        self.label_widget = None
        self.is_linked = False
        self.link_description = ""
        
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)
        
        # Label du paramètre
        label = QLabel(f"{param_name}:")
        label.setStyleSheet("color: #2C3E50; font-size: 9px; font-weight: bold;")
        label.setFixedWidth(70)
        self.label_widget = label
        layout.addWidget(label)
        
        # Widget d'édition selon le type
        if param_type == 'choice' and self.param_choices:
            self.edit_widget = self._create_choice_widget(param_value)
        elif param_type == 'editable_choice':
            self.edit_widget = self._create_editable_choice_widget(param_value)
        elif param_type == 'checkbox':
            self.edit_widget = QCheckBox()
            self.edit_widget.setChecked(param_value == 'true')
            self.edit_widget.stateChanged.connect(lambda: self._on_value_changed(
                'true' if self.edit_widget.isChecked() else 'false'))
        elif param_type == 'number':
            self.edit_widget = QSpinBox()
            self.edit_widget.setMinimum(-999999)
            self.edit_widget.setMaximum(999999)
            try:
                self.edit_widget.setValue(int(param_value) if param_value else 0)
            except:
                self.edit_widget.setValue(0)
            self.edit_widget.valueChanged.connect(lambda v: self._on_value_changed(str(v)))
        else:
            # Texte par défaut
            self.edit_widget = QLineEdit()
            self.edit_widget.setText(str(param_value) if param_value else "")
            self.edit_widget.setPlaceholderText("...")
            self.edit_widget.textChanged.connect(self._on_value_changed)
        
        # Style compact
        self._apply_compact_style(self.edit_widget)
        
        layout.addWidget(self.edit_widget)
        self.setLayout(layout)
        self.setFixedHeight(24)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        for widget in self._iter_interactive_widgets():
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, current_widget=widget: self._show_context_menu(self.mapFromGlobal(current_widget.mapToGlobal(pos)))
            )

    def _apply_compact_style(self, widget):
        """Applique le style compact aux widgets de paramètres."""
        widget.setFixedHeight(20)
        widget.setStyleSheet("""
            QLineEdit, QComboBox, QSpinBox, QPushButton {
                font-size: 9px;
                padding: 1px 3px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background: white;
            }
            QPushButton {
                text-align: left;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPushButton:focus {
                border: 1px solid #3498db;
            }
            QMenu {
                font-size: 10px;
                background: white;
            }
        """)

    def _iter_interactive_widgets(self):
        if isinstance(self.edit_widget, QWidget):
            yield self.edit_widget
        if self.choice_button is not None and self.choice_button is not self.edit_widget:
            yield self.choice_button
        if self.choice_line_edit is not None and self.choice_line_edit is not self.edit_widget:
            yield self.choice_line_edit

    def _show_context_menu(self, position):
        menu = QMenu(self)
        link_action = menu.addAction("Lier à un autre paramètre...")
        unlink_action = None
        if self.is_linked:
            menu.addSeparator()
            info_action = menu.addAction(f"Liaison: {self.link_description}")
            info_action.setEnabled(False)
            unlink_action = menu.addAction("Supprimer la liaison")

        action = menu.exec(self.mapToGlobal(position))
        if action == link_action:
            self.linkRequested.emit(self.param_name)
        elif unlink_action is not None and action == unlink_action:
            self.unlinkRequested.emit(self.param_name)

    def _create_choice_widget(self, param_value):
        """Crée un sélecteur de choix via menu popup natif."""
        button = QPushButton()
        button.clicked.connect(lambda: self._show_choice_menu(button))
        self.choice_button = button
        current_value = str(param_value) if param_value else (self.param_choices[0] if self.param_choices else "")
        self._set_choice_button_value(current_value)
        return button

    def _create_editable_choice_widget(self, param_value):
        """Crée un champ texte avec menu de suggestions."""
        container = QWidget()
        container.setFixedHeight(20)
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)

        line_edit = QLineEdit()
        line_edit.setText(str(param_value) if param_value else "")
        line_edit.setPlaceholderText("...")
        line_edit.textChanged.connect(self._on_value_changed)
        self._apply_compact_style(line_edit)
        self.choice_line_edit = line_edit

        button = QPushButton("▼")
        button.setFixedWidth(22)
        button.clicked.connect(lambda: self._show_choice_menu(button, editable=True))
        self._apply_compact_style(button)
        self.choice_button = button

        container_layout.addWidget(line_edit)
        container_layout.addWidget(button)
        container.setLayout(container_layout)
        return container

    def _show_choice_menu(self, anchor_widget, editable=False):
        """Affiche un popup flottant de choix."""
        if not self.param_choices:
            return

        current_value = self.get_value()
        popup = ChoicePopupDialog(self.param_choices, current_value)
        popup.valueSelected.connect(
            lambda selected, is_editable=editable: self._apply_choice_selection(selected, is_editable)
        )
        self.choice_popup = popup

        popup_pos = QCursor.pos() + QPoint(0, 6)
        popup.move(popup_pos)
        popup.exec()

    def _apply_choice_selection(self, value, editable=False):
        """Applique une valeur sélectionnée depuis le menu."""
        if editable and self.choice_line_edit is not None:
            self.choice_line_edit.setText(value)
        else:
            self._set_choice_button_value(value)
            self._on_value_changed(value)

    def _set_choice_button_value(self, value):
        """Met à jour le libellé du bouton de sélection."""
        if self.choice_button is not None:
            self.choice_button.setText(str(value))
    
    def set_display_value(self, value):
        """Met à jour l'affichage de la valeur sans déclencher de logique externe."""
        value = str(value) if value is not None else ""
        if self.param_type == 'choice' and self.choice_button is not None:
            self._set_choice_button_value(value)
        elif self.param_type == 'editable_choice' and self.choice_line_edit is not None:
            previous = self.choice_line_edit.blockSignals(True)
            self.choice_line_edit.setText(value)
            self.choice_line_edit.blockSignals(previous)
        elif isinstance(self.edit_widget, QCheckBox):
            previous = self.edit_widget.blockSignals(True)
            self.edit_widget.setChecked(value == 'true')
            self.edit_widget.blockSignals(previous)
        elif isinstance(self.edit_widget, QSpinBox):
            previous = self.edit_widget.blockSignals(True)
            try:
                self.edit_widget.setValue(int(value) if value else 0)
            except Exception:
                self.edit_widget.setValue(0)
            self.edit_widget.blockSignals(previous)
        elif isinstance(self.edit_widget, QLineEdit):
            previous = self.edit_widget.blockSignals(True)
            self.edit_widget.setText(value)
            self.edit_widget.blockSignals(previous)

    def set_link_state(self, linked, description=""):
        """Affiche visuellement l'état de liaison du paramètre."""
        self.is_linked = bool(linked)
        self.link_description = str(description or "")

        label_text = f"{self.param_name}:"
        if self.is_linked:
            label_text = f"{self.param_name} ↔"
        self.label_widget.setText(label_text)

        label_style = "color: #2C3E50; font-size: 9px; font-weight: bold;"
        if self.is_linked:
            label_style = "color: #8E44AD; font-size: 9px; font-weight: bold;"
        self.label_widget.setStyleSheet(label_style)

        tooltip = self.link_description if self.is_linked else ""
        self.setToolTip(tooltip)
        self.label_widget.setToolTip(tooltip)

        for widget in self._iter_interactive_widgets():
            widget.setToolTip(tooltip)
            widget.setEnabled(not self.is_linked)

    def _on_value_changed(self, value):
        self.parameterChanged.emit(self.param_name, str(value))
    
    def get_value(self):
        if self.param_type == 'choice' and self.choice_button is not None:
            return self.choice_button.text()
        elif self.param_type == 'editable_choice' and self.choice_line_edit is not None:
            return self.choice_line_edit.text()
        elif isinstance(self.edit_widget, QCheckBox):
            return 'true' if self.edit_widget.isChecked() else 'false'
        elif isinstance(self.edit_widget, QSpinBox):
            return str(self.edit_widget.value())
        else:
            return self.edit_widget.text()



class Node(QGraphicsItem):
    """Noeud représentant une commande CLI"""
    
    def __init__(self, node_data, x=0, y=0):
        super().__init__()
        self.node_data = node_data.copy()
        self.node_uid = self.node_data.get('node_uid') or str(uuid.uuid4())
        self.parameters = {}
        self.parameter_links = {}
        self.output_extension = normalize_output_extension(self.node_data.get('output_extension', ''))
        self.output_extension_choices = self.node_data.get('output_extension_choices', []) or []
        self.execution_order = None  # Ordre d'exécution
        self.parameter_widgets = []  # Widgets des paramètres
        self.proxy_widgets = []  # Proxy widgets pour les paramètres
        self.output_format_widget = None
        self.output_format_proxy = None
        self._parameter_rebuild_pending = False
        
        # Initialiser les paramètres avec les valeurs par défaut
        for param in self.node_data.get('parameters', []):
            self.parameters[param['name']] = param.get('default', '')
        
        # Dimensions de base
        self.width = 220
        self.header_height = 28
        self.param_height = 26
        
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.input_ports = []
        self.output_ports = []
        self._rebuild_ports()

    def _is_multi_file_node(self):
        return self.node_data.get('name') == MULTI_FILE_NODE_NAME

    def _is_global_variables_node(self):
        return self.node_data.get('name') == GLOBAL_VARIABLES_NODE_NAME

    def _is_input_variables_node(self):
        return self.node_data.get('name') == INPUT_VARIABLES_NODE_NAME

    def _is_switch_node(self):
        return self.node_data.get('name') == SWITCH_NODE_NAME

    def _is_merge_node(self):
        return self.node_data.get('name') == MERGE_NODE_NAME

    def _has_dynamic_ports(self):
        return (
            self._is_multi_file_node()
            or self._is_global_variables_node()
            or self._is_input_variables_node()
            or self._is_switch_node()
            or self._is_merge_node()
        )

    def _get_multi_file_output_count(self):
        value_source = self.parameters.get('Nombre de fichiers', '2')
        main_window = self.get_main_window()
        if main_window is not None:
            value_source = main_window.resolve_node_parameter_value(self, 'Nombre de fichiers')
        try:
            value = int(value_source or 2)
        except Exception:
            value = 2
        return max(1, min(MULTI_FILE_MAX_SLOTS, value))

    def _get_global_variables_count(self):
        value_source = self.parameters.get('Nombre de variables', '2')
        main_window = self.get_main_window()
        if main_window is not None:
            value_source = main_window.resolve_node_parameter_value(self, 'Nombre de variables')
        try:
            value = int(value_source or 2)
        except Exception:
            value = 2
        return max(1, min(GLOBAL_VARIABLES_MAX_SLOTS, value))

    def _get_input_variables_count(self):
        value_source = self.parameters.get('Nombre de variables', '2')
        main_window = self.get_main_window()
        if main_window is not None:
            value_source = main_window.resolve_node_parameter_value(self, 'Nombre de variables')
        try:
            value = int(value_source or 2)
        except Exception:
            value = 2
        return max(1, min(INPUT_VARIABLES_MAX_SLOTS, value))

    def _get_switch_condition_count(self):
        value_source = self.parameters.get('Nombre de conditions', '2')
        main_window = self.get_main_window()
        if main_window is not None:
            value_source = main_window.resolve_node_parameter_value(self, 'Nombre de conditions')
        try:
            value = int(value_source or 2)
        except Exception:
            value = 2
        return max(1, min(SWITCH_MAX_CONDITIONS, value))

    def _get_merge_input_count(self):
        value_source = self.parameters.get("Nombre d'entrées", '2')
        main_window = self.get_main_window()
        if main_window is not None:
            value_source = main_window.resolve_node_parameter_value(self, "Nombre d'entrées")
        try:
            value = int(value_source or 2)
        except Exception:
            value = 2
        return max(2, min(MERGE_MAX_INPUTS, value))

    def _get_visible_parameters(self):
        parameters = self.node_data.get('parameters', [])
        if not self._is_global_variables_node() and not self._is_input_variables_node() and not self._is_switch_node() and not self._is_merge_node():
            return parameters

        visible = [parameters[0]] if parameters else []
        if self._is_global_variables_node():
            count = self._get_global_variables_count()
            for index in range(1, count + 1):
                visible.extend([
                    next((param for param in parameters if param.get('name') == f'Nom {index}'), None),
                    next((param for param in parameters if param.get('name') == f'Valeur {index}'), None)
                ])
        elif self._is_input_variables_node():
            count = self._get_input_variables_count()
            for index in range(1, count + 1):
                visible.extend([
                    next((param for param in parameters if param.get('name') == f'Question {index}'), None),
                    next((param for param in parameters if param.get('name') == f'Nom {index}'), None),
                    next((param for param in parameters if param.get('name') == f'Valeur par défaut {index}'), None)
                ])
        elif self._is_switch_node():
            visible.append(parameters[1] if len(parameters) > 1 else None)
            count = self._get_switch_condition_count()
            for index in range(1, count + 1):
                visible.extend([
                    next((param for param in parameters if param.get('name') == f'Opérateur {index}'), None),
                    next((param for param in parameters if param.get('name') == f'Valeur {index}'), None),
                    next((param for param in parameters if param.get('name') == f'Label sortie {index}'), None)
                ])
        else:
            return visible
        return [param for param in visible if param]

    def _get_effective_inputs(self):
        if self._is_global_variables_node():
            return ['file'] * self._get_global_variables_count()
        if self._is_merge_node():
            return ['file'] * self._get_merge_input_count()
        return self.node_data.get('inputs', [])

    def _get_effective_outputs(self):
        if self._is_multi_file_node():
            return ['file'] * self._get_multi_file_output_count()
        if self._is_switch_node():
            return ['file'] * (self._get_switch_condition_count() + 1)
        return self.node_data.get('outputs', [])

    def _remove_port(self, port):
        if self.scene() and hasattr(self.scene(), 'cancel_temp_connection_for_port'):
            self.scene().cancel_temp_connection_for_port(port)
        for conn in port.connections[:]:
            remove_connection_safely(self.scene(), conn)
        if self.scene():
            self.scene().removeItem(port)
            self.scene().update()
        port.setParentItem(None)

    def _recalculate_geometry(self):
        num_params = len(self._get_visible_parameters())
        extra_rows = 1 if self._should_show_output_format() else 0
        self.params_section_height = num_params * self.param_height if num_params > 0 else 0
        self.params_section_height += extra_rows * self.param_height

        max_ports = max(len(self.input_ports), len(self.output_ports), 1)
        min_body_height = 20 + max_ports * 20
        self.height = self.header_height + max(30 + self.params_section_height, min_body_height + self.params_section_height) + 10

    def _rebuild_ports(self):
        """Crée ou ajuste les ports selon la configuration courante du noeud."""
        inputs = self._get_effective_inputs()
        outputs = self._get_effective_outputs()

        while len(self.input_ports) > len(inputs):
            self._remove_port(self.input_ports.pop())
        while len(self.output_ports) > len(outputs):
            self._remove_port(self.output_ports.pop())

        while len(self.input_ports) < len(inputs):
            self.input_ports.append(NodePort(self, 'input', len(self.input_ports)))
        while len(self.output_ports) < len(outputs):
            self.output_ports.append(NodePort(self, 'output', len(self.output_ports)))

        for i, port in enumerate(self.input_ports):
            port.index = i
            port.setPos(0, self.header_height + 15 + i * 20)
        for i, port in enumerate(self.output_ports):
            port.index = i
            port.setPos(self.width, self.header_height + 15 + i * 20)

        self.prepareGeometryChange()
        self._recalculate_geometry()
        self.update()
        if self.scene():
            self.scene().update_scene_bounds()

    def get_main_window(self):
        if not self.scene() or not self.scene().views():
            return None
        return self.scene().views()[0].window()

    def get_parameter_link(self, param_name):
        return self.parameter_links.get(param_name)

    def set_parameter_link(self, param_name, source_node, source_param_name):
        self.parameter_links[param_name] = {
            'node_uid': source_node.node_uid,
            'node_name': source_node.node_data.get('name', ''),
            'param_name': source_param_name
        }
        if self._is_multi_file_node() and param_name == 'Nombre de fichiers':
            self._rebuild_ports()
        elif self._is_switch_node() and param_name == 'Nombre de conditions':
            self._rebuild_ports()
        elif self._is_merge_node() and param_name == "Nombre d'entrées":
            self._rebuild_ports()
        self.refresh_parameter_widgets()
        main_window = self.get_main_window()
        if main_window is not None:
            main_window.refresh_all_parameter_links()
            main_window.schedule_bat_preview_refresh()

    def remove_parameter_link(self, param_name):
        if param_name in self.parameter_links:
            del self.parameter_links[param_name]
            if self._is_multi_file_node() and param_name == 'Nombre de fichiers':
                self._rebuild_ports()
            elif self._is_switch_node() and param_name == 'Nombre de conditions':
                self._rebuild_ports()
            elif self._is_merge_node() and param_name == "Nombre d'entrées":
                self._rebuild_ports()
            self.refresh_parameter_widgets()
            main_window = self.get_main_window()
            if main_window is not None:
                main_window.refresh_all_parameter_links()
                main_window.schedule_bat_preview_refresh()

    def refresh_parameter_widgets(self):
        if not self.scene():
            return

        self._parameter_rebuild_pending = False

        main_window = self.get_main_window()
        for widget in self.parameter_widgets:
            resolved_value = self.parameters.get(widget.param_name, "")
            link = self.get_parameter_link(widget.param_name)
            if link and main_window is not None:
                resolved_value = main_window.resolve_node_parameter_value(self, widget.param_name)
                description = main_window.describe_parameter_link(self, widget.param_name)
                widget.set_link_state(True, description)
            else:
                widget.set_link_state(False, "")
            widget.set_display_value(resolved_value)
    
    def create_parameter_widgets(self):
        """Crée les widgets de paramètres une fois le noeud ajouté à la scène"""
        if not self.scene():
            return
            
        # Nettoyer les anciens widgets
        for proxy in self.proxy_widgets:
            self.scene().removeItem(proxy)
        self.proxy_widgets.clear()
        self.parameter_widgets.clear()
        if self.output_format_proxy:
            self.scene().removeItem(self.output_format_proxy)
            self.output_format_proxy = None
            self.output_format_widget = None

        parameters = self._get_visible_parameters()
        for i, param in enumerate(parameters):
            widget = ParameterWidget(
                param['name'],
                param.get('type', 'text'),
                self.parameters.get(param['name'], param.get('default', '')),
                param.get('choices', [])
            )
            widget.parameterChanged.connect(self._on_parameter_changed)
            widget.linkRequested.connect(self._request_parameter_link)
            widget.unlinkRequested.connect(self._remove_parameter_link_request)
            widget.setFixedWidth(self.width - 10)
            
            proxy = QGraphicsProxyWidget(self)
            proxy.setWidget(widget)
            proxy.setPos(5, self.header_height + 35 + i * self.param_height)
            proxy.setZValue(1)
            
            self.parameter_widgets.append(widget)
            self.proxy_widgets.append(proxy)

        if self._should_show_output_format():
            output_widget = ParameterWidget(
                "Sortie",
                "editable_choice",
                self.output_extension,
                self.output_extension_choices
            )
            output_widget.parameterChanged.connect(self._on_output_extension_changed)
            output_widget.setFixedWidth(self.width - 10)

            output_proxy = QGraphicsProxyWidget(self)
            output_proxy.setWidget(output_widget)
            output_proxy.setPos(5, self.header_height + 35 + len(parameters) * self.param_height)
            output_proxy.setZValue(1)

            self.output_format_widget = output_widget
            self.output_format_proxy = output_proxy

        self.refresh_parameter_widgets()
        self.scene().update_scene_bounds()

    def schedule_parameter_widgets_rebuild(self):
        """Differe la recreation des widgets pour eviter un crash pendant un signal Qt."""
        if self._parameter_rebuild_pending:
            return
        self._parameter_rebuild_pending = True
        QTimer.singleShot(0, self.create_parameter_widgets)

    def _on_parameter_changed(self, param_name, new_value):
        """Appelé quand un paramètre est modifié"""
        self.parameters[param_name] = new_value
        if self._is_multi_file_node() and param_name == 'Nombre de fichiers':
            self._rebuild_ports()
            self.schedule_parameter_widgets_rebuild()
        elif self._is_switch_node() and param_name == 'Nombre de conditions':
            self._rebuild_ports()
            self.schedule_parameter_widgets_rebuild()
        elif self._is_merge_node() and param_name == "Nombre d'entrées":
            self._rebuild_ports()
            self.schedule_parameter_widgets_rebuild()
        elif (self._is_global_variables_node() or self._is_input_variables_node()) and param_name == 'Nombre de variables':
            self._rebuild_ports()
            self.schedule_parameter_widgets_rebuild()
        main_window = self.get_main_window()
        if main_window is not None:
            main_window.refresh_all_parameter_links()
            main_window.schedule_bat_preview_refresh()
        self.update()

    def _request_parameter_link(self, param_name):
        main_window = self.get_main_window()
        if main_window is None:
            return
        main_window.prompt_parameter_link(self, param_name)

    def _remove_parameter_link_request(self, param_name):
        self.remove_parameter_link(param_name)

    def _on_output_extension_changed(self, _param_name, new_value):
        """Appelé quand le format de sortie est modifié sur le noeud."""
        self.output_extension = normalize_output_extension(new_value)
        self.update()

    def _should_show_output_format(self):
        """Affiche le format de sortie pour les noeuds qui produisent un fichier intermédiaire."""
        if self.node_data.get('name') in [
            'Fichier Input',
            'Fichier Source',
            'Fichier Destination',
            MULTI_FILE_NODE_NAME,
            SWITCH_NODE_NAME,
            MERGE_NODE_NAME,
            GLOBAL_VARIABLES_NODE_NAME,
            INPUT_VARIABLES_NODE_NAME
        ]:
            return False
        return bool(self.node_data.get('outputs'))
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_position()
            if self.scene():
                self.scene().update_scene_bounds()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
            # Créer les widgets quand ajouté à la scène
            if self.scene():
                self.create_parameter_widgets()
                self.scene().update_scene_bounds()
        return super().itemChange(change, value)
    
    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)
    
    def paint(self, painter, option, widget):
        # Fond du noeud
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 10, 10)
        
        color = QColor(self.node_data.get('color', '#95E1D3'))
        if self.isSelected():
            color = color.lighter(120)
            
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor('#2C3E50'), 2))
        painter.drawPath(path)
        
        # En-tête
        header_path = QPainterPath()
        header_path.addRoundedRect(0, 0, self.width, self.header_height, 10, 10)
        # Rectangle pour cacher les coins arrondis du bas de l'en-tête
        header_path.addRect(0, 15, self.width, self.header_height - 15)
        painter.setBrush(QBrush(color.darker(110)))
        painter.drawPath(header_path)
        
        # Badge d'ordre d'exécution
        if self.execution_order is not None:
            badge_size = 22
            badge_x = self.width - badge_size - 5
            badge_y = 3
            
            # Cercle du badge
            painter.setBrush(QBrush(QColor('#E74C3C')))
            painter.setPen(QPen(QColor('#FFFFFF'), 2))
            painter.drawEllipse(int(badge_x), int(badge_y), badge_size, badge_size)
            
            # Numéro
            painter.setPen(QPen(QColor('#FFFFFF')))
            font = QFont('Arial', 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(badge_x, badge_y, badge_size, badge_size),
                           Qt.AlignmentFlag.AlignCenter, str(self.execution_order))
        
        # Texte catégorie
        painter.setPen(QPen(QColor('#FFFFFF')))
        font = QFont('Arial', 9, QFont.Weight.Bold)
        painter.setFont(font)
        
        category = get_display_category(self.node_data)
        text_width = self.width - 35 if self.execution_order is not None else self.width - 10
        painter.drawText(QRectF(5, 5, text_width, 20), 
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, category)
        
        # Nom du noeud
        font = QFont('Arial', 9)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#2C3E50')))
        painter.drawText(QRectF(5, self.header_height + 5, self.width - 10, 25), 
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, 
                        get_display_node_name(self.node_data))
        
        # Ligne de séparation avant les paramètres (si paramètres ou format de sortie)
        if self.node_data.get('parameters') or self._should_show_output_format():
            painter.setPen(QPen(QColor('#bdc3c7'), 1))
            y_line = self.header_height + 32
            painter.drawLine(10, int(y_line), self.width - 10, int(y_line))
    
    def contextMenuEvent(self, event):
        menu = QMenu()
        config_action = menu.addAction("⚙️ Configurer")
        focus_action = menu.addAction("🎯 Centrer dans la vue")
        menu.addSeparator()
        duplicate_action = menu.addAction("📋 Dupliquer")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Supprimer")
        
        action = menu.exec(event.screenPos())
        if action == config_action:
            self.configure_node()
        elif action == focus_action:
            self.focus_in_view()
        elif action == duplicate_action:
            self.duplicate_node()
        elif action == delete_action:
            self.delete_node()

    def focus_in_view(self):
        """Recentre et cadre ce noeud dans la vue principale."""
        if not self.scene() or not self.scene().views():
            return
        self.setSelected(True)
        self.scene().views()[0].focus_on_node(self)
    
    def configure_node(self):
        """Ouvre le dialog de configuration"""
        dialog = NodeConfigDialog(self, self.scene().views()[0])
        dialog.exec()
        
    def duplicate_node(self):
        """Duplique le noeud"""
        new_node = Node(self.node_data, self.pos().x() + 30, self.pos().y() + 30)
        new_node.parameters.update(self.parameters.copy())
        new_node.parameter_links = {key: value.copy() for key, value in self.parameter_links.items()}
        if new_node._has_dynamic_ports():
            new_node._rebuild_ports()
        new_node.output_extension = self.output_extension
        self.scene().addItem(new_node)
        self.scene().update_scene_bounds()
        
    def delete_node(self):
        """Supprime le noeud"""
        for port in self.input_ports + self.output_ports:
            if self.scene() and hasattr(self.scene(), 'cancel_temp_connection_for_port'):
                self.scene().cancel_temp_connection_for_port(port)
            for conn in port.connections[:]:
                remove_connection_safely(self.scene(), conn)
        
        # Supprimer les widgets proxy
        for proxy in self.proxy_widgets:
            self.scene().removeItem(proxy)
        
        scene = self.scene()
        scene.removeItem(self)
        if scene:
            main_window = self.get_main_window()
            if main_window is not None:
                main_window.refresh_all_parameter_links()
            scene.update_scene_bounds()
            if main_window is not None:
                main_window.mark_workflow_dirty()


class NodeConfigDialog(QDialog):
    """Dialog de configuration d'un noeud"""
    
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.node = node
        self.setWindowTitle(f"Configuration: {get_display_node_name(node.node_data)}")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Description
        if node.node_data.get('description'):
            desc_label = QLabel(node.node_data['description'])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
            layout.addWidget(desc_label)
        
        # Commande
        if node.node_data.get('command'):
            cmd_label = QLabel(f"Commande: <b>{node.node_data['command']}</b>")
            cmd_label.setStyleSheet("padding: 5px; background: #f0f0f0; border-radius: 3px;")
            layout.addWidget(cmd_label)
        
        # Template
        if node.node_data.get('template'):
            tmpl_label = QLabel(f"Template: <code>{node.node_data['template']}</code>")
            tmpl_label.setStyleSheet("padding: 5px; background: #f8f8f8; border-radius: 3px; font-family: monospace;")
            tmpl_label.setWordWrap(True)
            layout.addWidget(tmpl_label)

        output_extension = node.output_extension or node.node_data.get('output_extension', '')
        if output_extension:
            format_label = QLabel(f"Format de sortie: <b>{output_extension}</b>")
            format_label.setStyleSheet("padding: 5px; background: #eef7ff; border-radius: 3px;")
            layout.addWidget(format_label)
        
        # Formulaire des paramètres
        form_widget = QWidget()
        form_layout = QFormLayout()
        
        self.param_widgets = {}
        parameters = node.node_data.get('parameters', [])
        
        for param in parameters:
            param_name = param['name']
            param_type = param.get('type', 'text')
            param_default = param.get('default', '')
            param_choices = param.get('choices', [])
            
            if param_type == 'choice' and param_choices:
                widget = QComboBox()
                widget.addItems(param_choices)
                if param_name in node.parameters:
                    idx = widget.findText(node.parameters[param_name])
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
            elif param_type == 'file':
                file_widget = QWidget()
                file_layout = QHBoxLayout()
                file_layout.setContentsMargins(0, 0, 0, 0)
                
                line_edit = QLineEdit()
                if param_name in node.parameters:
                    line_edit.setText(node.parameters[param_name])
                
                browse_btn = QPushButton("...")
                browse_btn.setMaximumWidth(30)
                browse_btn.clicked.connect(lambda checked, le=line_edit: self.browse_file(le))
                
                file_layout.addWidget(line_edit)
                file_layout.addWidget(browse_btn)
                file_widget.setLayout(file_layout)
                
                widget = line_edit
                form_layout.addRow(f"{param_name}:", file_widget)
                self.param_widgets[param_name] = widget
                continue
            elif param_type == 'number':
                widget = QSpinBox()
                widget.setMinimum(-999999)
                widget.setMaximum(999999)
                if param_name in node.parameters:
                    try:
                        widget.setValue(int(node.parameters[param_name]))
                    except:
                        pass
            elif param_type == 'checkbox':
                widget = QCheckBox()
                if param_name in node.parameters:
                    widget.setChecked(node.parameters[param_name] == 'true')
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(str(param_default))
                if param_name in node.parameters:
                    widget.setText(node.parameters[param_name])
            
            self.param_widgets[param_name] = widget
            form_layout.addRow(f"{param_name}:", widget)
        
        form_widget.setLayout(form_layout)
        
        scroll = QScrollArea()
        scroll.setWidget(form_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Boutons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Annuler")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def browse_file(self, line_edit):
        """Ouvre un dialog de sélection de fichier"""
        filename, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier")
        if filename:
            line_edit.setText(filename)
    
    def accept(self):
        # Sauvegarder les paramètres
        for param_name, widget in self.param_widgets.items():
            if isinstance(widget, QComboBox):
                self.node.parameters[param_name] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                self.node.parameters[param_name] = str(widget.value())
            elif isinstance(widget, QCheckBox):
                self.node.parameters[param_name] = 'true' if widget.isChecked() else 'false'
            else:
                self.node.parameters[param_name] = widget.text()
        
        if self.node._has_dynamic_ports():
            self.node._rebuild_ports()

        # Mettre à jour les widgets sur le noeud
        self.node.create_parameter_widgets()
        self.node.update()
        super().accept()


class NodeEditorScene(QGraphicsScene):
    """Scène contenant les noeuds"""
    
    executionOrderChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.reset_scene_rect()
        self.temp_connection = None
        self.start_port = None

    def _get_item_at_scene_pos(self, scene_pos):
        if self.views():
            return self.itemAt(scene_pos, self.views()[0].transform())
        return self.itemAt(scene_pos, QTransform())

    def _is_port_usable(self, port):
        if port is None:
            return False
        try:
            parent_node = getattr(port, 'parent_node', None)
            return port.scene() is self and parent_node is not None and parent_node.scene() is self
        except RuntimeError:
            return False

    def cancel_temp_connection(self):
        if self.temp_connection is not None:
            remove_connection_safely(self, self.temp_connection)
        self.temp_connection = None
        self.start_port = None

    def cancel_temp_connection_for_port(self, port):
        if port is None:
            return
        try:
            if self.start_port is port:
                self.cancel_temp_connection()
                return
            if self.temp_connection is not None and (
                self.temp_connection.start_port is port or self.temp_connection.end_port is port
            ):
                self.cancel_temp_connection()
        except RuntimeError:
            self.cancel_temp_connection()

    def reset_scene_rect(self):
        """RÃ©initialise la scÃ¨ne Ã  une zone de travail confortable."""
        self.setSceneRect(-2000, -2000, 4000, 4000)

    def update_scene_bounds(self):
        """Agrandit automatiquement la scÃ¨ne pour englober tous les noeuds."""
        nodes = [item for item in self.items() if isinstance(item, Node)]
        if not nodes:
            self.reset_scene_rect()
            return

        bounds = QRectF()
        for node in nodes:
            node_rect = node.sceneBoundingRect()
            bounds = node_rect if bounds.isNull() else bounds.united(node_rect)

        padding = 400
        min_bounds = QRectF(-2000, -2000, 4000, 4000)
        padded = bounds.adjusted(-padding, -padding, padding, padding).united(min_bounds)
        self.setSceneRect(padded)
        
    def mousePressEvent(self, event):
        item = self._get_item_at_scene_pos(event.scenePos())
        
        if isinstance(item, NodePort):
            if item.port_type == 'output' and self._is_port_usable(item):
                self.start_port = item
                self.temp_connection = Connection(item)
                self.addItem(self.temp_connection)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.temp_connection:
            if not self._is_port_usable(self.start_port):
                self.cancel_temp_connection()
            else:
                try:
                    self.temp_connection.temp_end_pos = event.scenePos()
                    self.temp_connection.update_position()
                except RuntimeError:
                    self.cancel_temp_connection()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self.temp_connection:
            try:
                if not self._is_port_usable(self.start_port):
                    self.cancel_temp_connection()
                    super().mouseReleaseEvent(event)
                    return

                item = self._get_item_at_scene_pos(event.scenePos())
                
                if isinstance(item, NodePort) and item.port_type == 'input' and self._is_port_usable(item):
                    if item.parent_node is self.start_port.parent_node:
                        self.cancel_temp_connection()
                        super().mouseReleaseEvent(event)
                        return

                    if self.start_port.port_type != 'output':
                        self.cancel_temp_connection()
                        super().mouseReleaseEvent(event)
                        return

                    # Supprimer les connexions existantes sur le port d'entrée
                    for conn in item.connections[:]:
                        remove_connection_safely(self, conn)
                    
                    # Créer la connexion
                    self.temp_connection.end_port = item
                    self.temp_connection.update_position()
                    if self.temp_connection not in self.start_port.connections:
                        self.start_port.connections.append(self.temp_connection)
                    if self.temp_connection not in item.connections:
                        item.connections.append(self.temp_connection)
                    
                    # Mettre à jour l'ordre d'exécution, et annuler si la liaison casse le graphe.
                    main_window = self.views()[0].window() if self.views() else None
                    if main_window is not None and hasattr(main_window, 'mark_workflow_dirty'):
                        main_window.mark_workflow_dirty()
                else:
                    self.cancel_temp_connection()
            except Exception as e:
                self.cancel_temp_connection()
                QMessageBox.warning(
                    self.views()[0] if self.views() else None,
                    "Liaison impossible",
                    f"La liaison a été annulée car elle a déclenché une erreur:\n{type(e).__name__}: {e}"
                )
            
            self.temp_connection = None
            self.start_port = None
            self.update()
        
        super().mouseReleaseEvent(event)
    
    def update_execution_order(self):
        """Calcule et met à jour l'ordre d'exécution de tous les noeuds"""
        if self.views():
            main_window = self.views()[0].window()
            if main_window is not None and hasattr(main_window, '_get_execution_nodes'):
                try:
                    main_window._get_execution_nodes()
                    self.executionOrderChanged.emit()
                    return
                except Exception:
                    pass

        nodes_list = [item for item in self.items() if isinstance(item, Node)]
        
        # Réinitialiser les ordres
        for node in nodes_list:
            node.execution_order = None
        
        # Tri topologique
        executed = set()
        order = 1
        
        def find_ready_nodes():
            ready = []
            for node in nodes_list:
                if id(node) in executed:
                    continue
                
                all_inputs_ready = True
                for port in node.input_ports:
                    for conn in port.connections:
                        if id(conn.start_port.parent_node) not in executed:
                            all_inputs_ready = False
                            break
                
                if all_inputs_ready:
                    ready.append(node)
            return ready
        
        while len(executed) < len(nodes_list):
            ready = find_ready_nodes()
            if not ready:
                # Cycle détecté - on arrête
                break
            
            # Trier par position X pour un ordre cohérent
            ready.sort(key=lambda n: (n.pos().x(), n.pos().y()))
            
            for node in ready:
                node.execution_order = order
                order += 1
                executed.add(id(node))
                node.update()
        
        self.executionOrderChanged.emit()


class NodeEditorView(QGraphicsView):
    """Vue de l'éditeur nodal"""

    backgroundContextMenuRequested = pyqtSignal(QPoint, QPointF)
    
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor('#34495E')))
        self.min_zoom = 0.2
        self.max_zoom = 3.0
        self.zoom_step = 1.2
        
    def wheelEvent(self, event):
        factor = self.zoom_step if event.angleDelta().y() > 0 else 1 / self.zoom_step
        self.apply_zoom_factor(factor)

    def get_zoom_level(self):
        return self.transform().m11()

    def apply_zoom_factor(self, factor):
        current_zoom = self.get_zoom_level()
        target_zoom = current_zoom * factor
        if target_zoom < self.min_zoom:
            factor = self.min_zoom / current_zoom
        elif target_zoom > self.max_zoom:
            factor = self.max_zoom / current_zoom
        self.scale(factor, factor)

    def reset_zoom(self):
        self.resetTransform()

    def fit_scene_rect(self, rect, padding=80):
        if rect.isNull() or rect.isEmpty():
            return
        self.fitInView(rect.adjusted(-padding, -padding, padding, padding), Qt.AspectRatioMode.KeepAspectRatio)

    def focus_on_node(self, node, padding=120):
        if node is None:
            return
        self.centerOn(node)
        self.fit_scene_rect(node.sceneBoundingRect(), padding)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            self.backgroundContextMenuRequested.emit(event.globalPos(), self.mapToScene(event.pos()))
            event.accept()
            return

        super().contextMenuEvent(event)


class DependencyConfigDialog(QDialog):
    """Dialog de configuration des chemins des dépendances et ajout d'outils CLI"""
    
    def __init__(self, dep_manager, parent=None):
        super().__init__(parent)
        self.dep_manager = dep_manager
        self.setWindowTitle("🔧 Gestionnaire d'Applications CLI")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        layout = QVBoxLayout()
        
        # Tabs
        tabs = QTabWidget()
        
        # === Tab 1: Liste des outils ===
        tools_tab = QWidget()
        tools_layout = QVBoxLayout()
        
        info_label = QLabel(
            "Gérez vos applications CLI. Ajoutez vos propres outils ou configurez les chemins existants."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background: #e8f4f8; border-radius: 5px;")
        tools_layout.addWidget(info_label)
        
        # Table des outils
        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(4)
        self.tools_table.setHorizontalHeaderLabels(['Nom', 'Chemin', 'Description', 'Arg Version'])
        self.tools_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tools_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tools_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        self.refresh_tools_table()
        tools_layout.addWidget(self.tools_table)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Ajouter outil")
        add_btn.clicked.connect(self.add_tool)
        btn_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Modifier")
        edit_btn.clicked.connect(self.edit_tool)
        btn_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("🗑️ Supprimer")
        remove_btn.clicked.connect(self.remove_tool)
        btn_layout.addWidget(remove_btn)
        
        btn_layout.addStretch()
        
        test_btn = QPushButton("🧪 Tester sélection")
        test_btn.clicked.connect(self.test_selected_tool)
        btn_layout.addWidget(test_btn)
        
        test_all_btn = QPushButton("🧪 Tester tous")
        test_all_btn.clicked.connect(self.test_all_tools)
        btn_layout.addWidget(test_all_btn)
        
        tools_layout.addLayout(btn_layout)
        
        # Zone de résultats
        self.test_result = QTextEdit()
        self.test_result.setMaximumHeight(120)
        self.test_result.setReadOnly(True)
        self.test_result.setStyleSheet("font-family: Consolas, monospace;")
        tools_layout.addWidget(self.test_result)
        
        tools_tab.setLayout(tools_layout)
        tabs.addTab(tools_tab, "📋 Liste des outils")
        
        # === Tab 2: Ajouter un outil ===
        add_tab = QWidget()
        add_layout = QVBoxLayout()
        
        add_info = QLabel(
            "Ajoutez une nouvelle application CLI à utiliser dans vos workflows.\n"
            "Le nom sera utilisé comme identifiant dans les templates de commande."
        )
        add_info.setWordWrap(True)
        add_info.setStyleSheet("padding: 10px; background: #f0f8e8; border-radius: 5px;")
        add_layout.addWidget(add_info)
        
        form_layout = QFormLayout()
        
        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText("Ex: myconverter, audioproc, etc.")
        form_layout.addRow("Nom de l'outil:", self.new_name_edit)
        
        path_widget = QWidget()
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.new_path_edit = QLineEdit()
        self.new_path_edit.setPlaceholderText("Chemin complet vers l'exécutable ou nom si dans PATH")
        browse_btn = QPushButton("📁")
        browse_btn.setMaximumWidth(40)
        browse_btn.clicked.connect(lambda: self.browse_executable(self.new_path_edit))
        path_layout.addWidget(self.new_path_edit)
        path_layout.addWidget(browse_btn)
        path_widget.setLayout(path_layout)
        form_layout.addRow("Chemin:", path_widget)
        
        self.new_desc_edit = QLineEdit()
        self.new_desc_edit.setPlaceholderText("Description courte de l'outil")
        form_layout.addRow("Description:", self.new_desc_edit)
        
        self.new_version_edit = QLineEdit()
        self.new_version_edit.setPlaceholderText("--version, -v, version, etc.")
        self.new_version_edit.setText("--version")
        form_layout.addRow("Argument version:", self.new_version_edit)
        
        add_layout.addLayout(form_layout)
        
        add_tool_btn = QPushButton("💾 Ajouter cet outil")
        add_tool_btn.clicked.connect(self.save_new_tool)
        add_layout.addWidget(add_tool_btn)
        
        add_layout.addStretch()
        
        # Exemples
        examples_group = QGroupBox("💡 Exemples d'outils courants")
        examples_layout = QVBoxLayout()
        
        examples_text = QLabel(
            "• <b>ffmpeg</b> - Manipulation audio/vidéo (ffmpeg, --version)\n"
            "• <b>magick</b> - ImageMagick pour les images (magick, --version)\n"
            "• <b>sox</b> - Swiss Army knife audio (sox, --version)\n"
            "• <b>yt-dlp</b> - Téléchargeur YouTube (yt-dlp, --version)\n"
            "• <b>pandoc</b> - Convertisseur de documents (pandoc, --version)\n"
            "• <b>7z</b> - Compression d'archives (7z, sans argument)\n"
            "• <b>curl</b> - Transfert de données (curl, --version)\n"
            "• <b>HandBrakeCLI</b> - Encodeur vidéo (HandBrakeCLI, --version)\n"
            "• <b>tesseract</b> - OCR (tesseract, --version)\n"
            "• <b>whisper</b> - Transcription audio (whisper, --help)"
        )
        examples_text.setWordWrap(True)
        examples_layout.addWidget(examples_text)
        examples_group.setLayout(examples_layout)
        add_layout.addWidget(examples_group)
        
        add_tab.setLayout(add_layout)
        tabs.addTab(add_tab, "➕ Ajouter un outil")
        
        layout.addWidget(tabs)
        
        # Boutons principaux
        button_layout = QHBoxLayout()
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def refresh_tools_table(self):
        """Rafraîchit la table des outils"""
        tools = self.dep_manager.get_all_tools()
        self.tools_table.setRowCount(len(tools))
        
        for row, (name, info) in enumerate(sorted(tools.items())):
            if isinstance(info, dict):
                path = info.get('path', name)
                desc = info.get('description', '')
                version_arg = info.get('version_arg', '--version')
            else:
                path = info
                desc = ''
                version_arg = '--version'
            
            self.tools_table.setItem(row, 0, QTableWidgetItem(name))
            self.tools_table.setItem(row, 1, QTableWidgetItem(path))
            self.tools_table.setItem(row, 2, QTableWidgetItem(desc))
            self.tools_table.setItem(row, 3, QTableWidgetItem(version_arg))
    
    def browse_executable(self, line_edit):
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Sélectionner l'exécutable",
            "",
            "Executables (*.exe);;All Files (*.*)"
        )
        if filename:
            line_edit.setText(filename)
    
    def add_tool(self):
        """Ouvre le dialog d'ajout rapide"""
        name, ok = QInputDialog.getText(self, "Ajouter un outil", "Nom de l'outil:")
        if ok and name:
            path, ok = QInputDialog.getText(self, "Chemin", f"Chemin vers {name}:", text=name)
            if ok:
                self.dep_manager.add_tool(name, path)
                self.refresh_tools_table()
                self.test_result.setText(f"✓ Outil '{name}' ajouté")
    
    def edit_tool(self):
        """Édite l'outil sélectionné"""
        row = self.tools_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un outil à modifier")
            return
        
        name = self.tools_table.item(row, 0).text()
        current_path = self.tools_table.item(row, 1).text()
        current_desc = self.tools_table.item(row, 2).text()
        current_version = self.tools_table.item(row, 3).text()
        
        # Dialog d'édition
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Modifier: {name}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        
        path_edit = QLineEdit(current_path)
        desc_edit = QLineEdit(current_desc)
        version_edit = QLineEdit(current_version)
        
        path_widget = QWidget()
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(path_edit)
        browse_btn = QPushButton("📁")
        browse_btn.setMaximumWidth(40)
        browse_btn.clicked.connect(lambda: self.browse_executable(path_edit))
        path_layout.addWidget(browse_btn)
        path_widget.setLayout(path_layout)
        
        form.addRow("Chemin:", path_widget)
        form.addRow("Description:", desc_edit)
        form.addRow("Arg version:", version_edit)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("💾 Sauvegarder")
        cancel_btn = QPushButton("Annuler")
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        dialog.setLayout(layout)
        
        def save():
            self.dep_manager.set(name, path_edit.text(), desc_edit.text(), version_edit.text())
            self.refresh_tools_table()
            dialog.accept()
        
        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def remove_tool(self):
        """Supprime l'outil sélectionné"""
        row = self.tools_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un outil à supprimer")
            return
        
        name = self.tools_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Supprimer l'outil '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.dep_manager.remove_tool(name)
            self.refresh_tools_table()
            self.test_result.setText(f"✓ Outil '{name}' supprimé")
    
    def save_new_tool(self):
        """Sauvegarde un nouvel outil depuis le formulaire"""
        name = self.new_name_edit.text().strip()
        path = self.new_path_edit.text().strip()
        desc = self.new_desc_edit.text().strip()
        version_arg = self.new_version_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de l'outil est obligatoire")
            return
        
        if not path:
            path = name
        
        self.dep_manager.add_tool(name, path, desc, version_arg)
        self.refresh_tools_table()
        
        # Réinitialiser le formulaire
        self.new_name_edit.clear()
        self.new_path_edit.clear()
        self.new_desc_edit.clear()
        self.new_version_edit.setText("--version")
        
        self.test_result.setText(f"✓ Outil '{name}' ajouté avec succès!")
        QMessageBox.information(self, "Succès", f"L'outil '{name}' a été ajouté")
    
    def test_selected_tool(self):
        """Teste l'outil sélectionné"""
        row = self.tools_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un outil à tester")
            return
        
        name = self.tools_table.item(row, 0).text()
        self.test_tools([name])
    
    def test_all_tools(self):
        """Teste tous les outils"""
        tools = self.dep_manager.get_tool_names()
        self.test_tools(tools)
    
    def test_tools(self, tool_names):
        """Teste une liste d'outils"""
        import subprocess
        results = []
        
        for name in tool_names:
            info = self.dep_manager.get_info(name)
            path = info.get('path', name)
            version_arg = info.get('version_arg', '--version')
            
            try:
                cmd = [path]
                if version_arg:
                    cmd.append(version_arg)
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                
                output = result.stdout or result.stderr
                version = output.split('\n')[0][:60] if output else "(pas d'output)"
                
                if result.returncode == 0 or output:
                    results.append(f"✓ {name}: {version}")
                else:
                    results.append(f"⚠ {name}: Code retour {result.returncode}")
            except FileNotFoundError:
                results.append(f"✗ {name}: Non trouvé - vérifiez le chemin")
            except subprocess.TimeoutExpired:
                results.append(f"⚠ {name}: Timeout (mais probablement OK)")
            except Exception as e:
                results.append(f"✗ {name}: {str(e)[:50]}")
        
        self.test_result.setText("\n".join(results))


class NodeCreatorDialog(QDialog):
    """Dialog pour créer ou éditer un noeud personnalisé"""
    
    def __init__(self, library, parent=None, edit_node=None, template_node=None):
        super().__init__(parent)
        self.library = library
        self.edit_mode = edit_node is not None
        self.original_name = edit_node['name'] if edit_node else None
        
        # Déterminer les données initiales
        if edit_node:
            self.init_data = edit_node.copy()
            self.setWindowTitle(f"Éditer le noeud: {edit_node['name']}")
        elif template_node:
            self.init_data = template_node.copy()
            self.init_data['name'] = f"{template_node['name']} (copie)"
            self.setWindowTitle(f"Nouveau noeud basé sur: {template_node['name']}")
        else:
            self.init_data = None
            self.setWindowTitle("Créer un nouveau noeud")
        
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)
        
        layout = QVBoxLayout()
        
        # Onglets
        tabs = QTabWidget()
        
        # === Onglet Informations générales ===
        general_tab = QWidget()
        general_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.display_name_edit = QLineEdit()
        self.category_edit = QLineEdit()
        self.subcategory_edit = QLineEdit()
        self.command_edit = QLineEdit()
        self.output_extension_edit = QLineEdit()
        self.output_choices_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.color_edit = QLineEdit("#95E1D3")
        self.verified_checkbox = QCheckBox("Noeud vérifié")
        
        # Bouton pour choisir la couleur
        color_widget = QWidget()
        color_layout = QHBoxLayout()
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.color_edit)
        color_btn = QPushButton("🎨")
        color_btn.setMaximumWidth(30)
        color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(color_btn)
        color_widget.setLayout(color_layout)
        
        # Remplir si édition ou template
        if self.init_data:
            self.name_edit.setText(self.init_data.get('name', ''))
            self.display_name_edit.setText(self.init_data.get('display_name', ''))
            self.category_edit.setText(self.init_data.get('category', ''))
            self.subcategory_edit.setText(self.init_data.get('subcategory', ''))
            self.command_edit.setText(self.init_data.get('command', ''))
            self.output_extension_edit.setText(self.init_data.get('output_extension', ''))
            self.output_choices_edit.setText(', '.join(self.init_data.get('output_extension_choices', [])))
            self.description_edit.setText(self.init_data.get('description', ''))
            self.color_edit.setText(self.init_data.get('color', '#95E1D3'))
            self.verified_checkbox.setChecked(bool(self.init_data.get('verified', False)))

        general_layout.addRow("Nom du noeud:", self.name_edit)
        general_layout.addRow("Nom affiché:", self.display_name_edit)
        general_layout.addRow("Catégorie:", self.category_edit)
        general_layout.addRow("Sous-catégorie:", self.subcategory_edit)
        general_layout.addRow("Commande CLI:", self.command_edit)
        general_layout.addRow("Format de sortie:", self.output_extension_edit)
        general_layout.addRow("Formats suggérés:", self.output_choices_edit)
        general_layout.addRow("Description:", self.description_edit)
        general_layout.addRow("Couleur (hex):", color_widget)
        general_layout.addRow("", self.verified_checkbox)
        
        general_tab.setLayout(general_layout)
        tabs.addTab(general_tab, "📋 Général")
        
        # === Onglet Ports ===
        ports_tab = QWidget()
        ports_layout = QVBoxLayout()
        
        input_group = QGroupBox("Ports d'entrée")
        input_layout = QVBoxLayout()
        self.input_spin = QSpinBox()
        self.input_spin.setMinimum(0)
        self.input_spin.setMaximum(10)
        if self.init_data:
            self.input_spin.setValue(len(self.init_data.get('inputs', [])))
        input_layout.addWidget(QLabel("Nombre d'entrées:"))
        input_layout.addWidget(self.input_spin)
        input_group.setLayout(input_layout)
        
        output_group = QGroupBox("Ports de sortie")
        output_layout = QVBoxLayout()
        self.output_spin = QSpinBox()
        self.output_spin.setMinimum(0)
        self.output_spin.setMaximum(10)
        if self.init_data:
            self.output_spin.setValue(len(self.init_data.get('outputs', [])))
        output_layout.addWidget(QLabel("Nombre de sorties:"))
        output_layout.addWidget(self.output_spin)
        output_group.setLayout(output_layout)
        
        ports_layout.addWidget(input_group)
        ports_layout.addWidget(output_group)
        ports_layout.addStretch()
        
        ports_tab.setLayout(ports_layout)
        tabs.addTab(ports_tab, "🔌 Ports")
        
        # === Onglet Paramètres ===
        params_tab = QWidget()
        params_layout = QVBoxLayout()
        
        self.params_table = QTableWidget()
        self.params_table.setColumnCount(4)
        self.params_table.setHorizontalHeaderLabels(['Nom', 'Type', 'Défaut', 'Choix (séparés par ,)'])
        self.params_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Remplir si édition ou template
        if self.init_data and self.init_data.get('parameters'):
            for param in self.init_data['parameters']:
                self.add_parameter_row(param)
        
        params_btn_layout = QHBoxLayout()
        add_param_btn = QPushButton("➕ Ajouter paramètre")
        remove_param_btn = QPushButton("➖ Supprimer paramètre")
        add_param_btn.clicked.connect(lambda: self.add_parameter_row())
        remove_param_btn.clicked.connect(self.remove_parameter_row)
        params_btn_layout.addWidget(add_param_btn)
        params_btn_layout.addWidget(remove_param_btn)
        params_btn_layout.addStretch()
        
        params_layout.addWidget(self.params_table)
        params_layout.addLayout(params_btn_layout)
        
        params_tab.setLayout(params_layout)
        tabs.addTab(params_tab, "⚙️ Paramètres")
        
        # === Onglet Template ===
        template_tab = QWidget()
        template_layout = QVBoxLayout()
        
        help_text = QLabel(
            "Utilisez les variables suivantes dans le template:\n"
            "• {input} - Fichier d'entrée\n"
            "• {output} - Fichier de sortie\n"
            "• {nom_paramètre} - Valeur d'un paramètre\n"
            "• {size} / {ma_variable} - Variable définie par le noeud Variables Globales\n\n"
            "Le format de sortie utilisé pour les fichiers temporaires vient désormais\n"
            "uniquement du champ 'Format de sortie' de ce noeud.\n"
            "Exemples: .mp4, .png, {output_format}, %INPUT_EXT%"
        )
        help_text.setStyleSheet("padding: 10px; background: #e8f4f8; border-radius: 5px;")
        template_layout.addWidget(help_text)
        
        template_layout.addWidget(QLabel("Template de la commande:"))
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText("Exemple: ffmpeg -i {input} -c:v {codec} -b:v {bitrate} {output}")
        if self.init_data:
            self.template_edit.setText(self.init_data.get('template', ''))
        template_layout.addWidget(self.template_edit)
        
        template_tab.setLayout(template_layout)
        tabs.addTab(template_tab, "📝 Template")
        
        layout.addWidget(tabs)
        
        # Boutons
        button_layout = QHBoxLayout()
        save_button = QPushButton("💾 Sauvegarder")
        cancel_button = QPushButton("Annuler")
        save_button.clicked.connect(self.save_node)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def choose_color(self):
        """Ouvre un dialog pour choisir une couleur"""
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_edit.setText(color.name())
    
    def add_parameter_row(self, param_data=None):
        """Ajoute une ligne de paramètre"""
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        
        # Nom
        name_item = QTableWidgetItem(param_data.get('name', '') if param_data else '')
        self.params_table.setItem(row, 0, name_item)
        
        # Type
        type_combo = QComboBox()
        type_combo.addItems(['text', 'choice', 'file', 'number', 'checkbox'])
        if param_data:
            idx = type_combo.findText(param_data.get('type', 'text'))
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
        self.params_table.setCellWidget(row, 1, type_combo)
        
        # Défaut
        default_item = QTableWidgetItem(str(param_data.get('default', '')) if param_data else '')
        self.params_table.setItem(row, 2, default_item)
        
        # Choix
        choices_item = QTableWidgetItem(
            ','.join(param_data.get('choices', [])) if param_data and param_data.get('choices') else ''
        )
        self.params_table.setItem(row, 3, choices_item)
    
    def remove_parameter_row(self):
        """Supprime la ligne sélectionnée"""
        current_row = self.params_table.currentRow()
        if current_row >= 0:
            self.params_table.removeRow(current_row)
    
    def save_node(self):
        """Sauvegarde le noeud dans la bibliothèque"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du noeud est obligatoire")
            return

        output_extension = normalize_output_extension(self.output_extension_edit.text())
        output_extension_choices = [
            normalize_output_extension(choice)
            for choice in self.output_choices_edit.text().split(',')
            if choice.strip()
        ]
        has_outputs = self.output_spin.value() > 0
        is_system_passthrough = name in SYSTEM_SOURCE_NODE_NAMES

        if has_outputs and not is_system_passthrough and not output_extension:
            QMessageBox.warning(
                self,
                "Erreur",
                "Indiquez un format de sortie explicite pour ce noeud."
            )
            return

        if output_extension and output_extension not in output_extension_choices:
            output_extension_choices.insert(0, output_extension)
        
        # Vérifier si le nom existe déjà (sauf en mode édition du même noeud)
        if not self.edit_mode or (self.edit_mode and name != self.original_name):
            if name in self.library.get_all_nodes():
                reply = QMessageBox.question(
                    self, "Noeud existant", 
                    f"Un noeud '{name}' existe déjà. Voulez-vous le remplacer?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
        
        # Collecter les paramètres
        parameters = []
        for row in range(self.params_table.rowCount()):
            param_name = self.params_table.item(row, 0)
            param_type_widget = self.params_table.cellWidget(row, 1)
            param_default = self.params_table.item(row, 2)
            param_choices = self.params_table.item(row, 3)
            
            if param_name and param_name.text().strip():
                param = {
                    'name': param_name.text().strip(),
                    'type': param_type_widget.currentText() if param_type_widget else 'text',
                    'default': param_default.text() if param_default else ''
                }
                
                if param_choices and param_choices.text().strip():
                    param['choices'] = [c.strip() for c in param_choices.text().split(',') if c.strip()]
                
                parameters.append(param)
        
        # Créer les ports
        inputs = ['file'] * self.input_spin.value()
        outputs = ['file'] * self.output_spin.value()
        
        node_data = {
            'name': name,
            'display_name': self.display_name_edit.text().strip() or get_display_node_name({'name': name, 'category': self.category_edit.text().strip() or 'Custom'}),
            'category': self.category_edit.text().strip() or 'Custom',
            'subcategory': self.subcategory_edit.text().strip(),
            'command': self.command_edit.text().strip(),
            'output_extension': output_extension if has_outputs else '',
            'output_extension_choices': output_extension_choices if has_outputs else [],
            'description': self.description_edit.toPlainText().strip(),
            'color': self.color_edit.text().strip() or '#95E1D3',
            'verified': self.verified_checkbox.isChecked(),
            'inputs': inputs,
            'outputs': outputs,
            'parameters': parameters,
            'template': self.template_edit.toPlainText().strip()
        }
        
        if self.edit_mode:
            self.library.update_node(self.original_name, node_data)
            QMessageBox.information(self, "Succès", f"Le noeud '{name}' a été mis à jour")
        else:
            self.library.add_node(node_data)
            QMessageBox.information(self, "Succès", f"Le noeud '{name}' a été ajouté à la bibliothèque")
        
        self.accept()


class MainWindow(QMainWindow):
    """Fenêtre principale"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CLI Node Editor - Créateur de scripts BAT")
        self.setGeometry(100, 100, 1400, 800)
        
        self.dep_manager = DependencyManager()
        self.library = NodeLibrary()
        self.workflow_mode = "per_file"
        self.script_type = "batch"
        self.library_filter_mode = "all"
        self.preview_dirty = True
        self.panel_expanded_sizes = {"left": 320, "right": 380}
        
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel de gauche - Bibliothèque
        self.left_panel = self.create_library_panel()
        self.main_splitter.addWidget(self.left_panel)
        
        # Panel central - Canvas nodal
        self.scene = NodeEditorScene()
        self.scene.executionOrderChanged.connect(self.on_execution_order_changed)
        self.view = NodeEditorView(self.scene)
        self.view.backgroundContextMenuRequested.connect(self.show_canvas_context_menu)
        self.main_splitter.addWidget(self.view)

        # Panel de droite - Prévisualisation BAT
        self.right_panel = self.create_preview_panel()
        self.main_splitter.addWidget(self.right_panel)
        
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([self.panel_expanded_sizes["left"], 900, self.panel_expanded_sizes["right"]])
        
        main_layout.addWidget(self.main_splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.preview_refresh_timer = QTimer(self)
        self.preview_refresh_timer.setSingleShot(True)
        self.preview_refresh_timer.timeout.connect(self.refresh_bat_preview)
        self.scene.changed.connect(self.mark_workflow_dirty)
        
        self.create_menus()
        self.populate_default_canvas()
        self.update_preview_highlighter()
        self.generate_workflow_preview()
        
        self.statusBar().showMessage("Double-cliquez sur un noeud de la bibliothèque pour l'ajouter au canvas")
    
    def create_library_panel(self):
        """Crée le panel de bibliothèque"""
        content = QWidget()
        layout = QVBoxLayout()
        
        # Titre
        title = QLabel("📚 Bibliothèque de Noeuds")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        new_node_btn = QPushButton("➕ Nouveau")
        new_node_btn.clicked.connect(self.create_new_node)
        new_node_btn.setToolTip("Créer un nouveau noeud vide")
        btn_layout.addWidget(new_node_btn)
        layout.addLayout(btn_layout)

        self.loop_mode_checkbox = QCheckBox("Boucler sur chaque fichier")
        self.loop_mode_checkbox.setChecked(True)
        self.loop_mode_checkbox.setToolTip(
            "Activé: le workflow s'applique séparément à chaque fichier.\n"
            "Désactivé: tous les fichiers fournis alimentent un seul flux."
        )
        self.loop_mode_checkbox.toggled.connect(self.on_workflow_mode_changed)
        layout.addWidget(self.loop_mode_checkbox)

        script_type_layout = QHBoxLayout()
        script_type_layout.addWidget(QLabel("Type de script:"))
        self.script_type_combo = QComboBox()
        self.script_type_combo.addItem("Batch (.bat)", "batch")
        self.script_type_combo.addItem("Bash (.sh)", "bash")
        self.script_type_combo.addItem("PowerShell (.ps1)", "powershell")
        self.script_type_combo.currentIndexChanged.connect(self.on_script_type_changed)
        script_type_layout.addWidget(self.script_type_combo)
        layout.addLayout(script_type_layout)

        library_filter_layout = QHBoxLayout()
        library_filter_layout.addWidget(QLabel("Afficher:"))
        self.library_filter_combo = QComboBox()
        self.library_filter_combo.addItem("Tous les noeuds", "all")
        self.library_filter_combo.addItem("Noeuds vérifiés", "verified")
        self.library_filter_combo.currentIndexChanged.connect(self.on_library_filter_changed)
        library_filter_layout.addWidget(self.library_filter_combo)
        layout.addLayout(library_filter_layout)
        
        # Liste des noeuds
        self.node_list = QListWidget()
        self.node_list.itemDoubleClicked.connect(self.add_node_from_library)
        self.node_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.node_list.customContextMenuRequested.connect(self.show_library_context_menu)
        self.refresh_library_list()
        layout.addWidget(self.node_list)
        
        # Boutons d'édition
        edit_btn_layout = QHBoxLayout()
        
        edit_btn = QPushButton("✏️ Éditer")
        edit_btn.clicked.connect(self.edit_library_node)
        edit_btn.setToolTip("Éditer le noeud sélectionné")
        edit_btn_layout.addWidget(edit_btn)
        
        template_btn = QPushButton("📋 Template")
        template_btn.clicked.connect(self.use_as_template)
        template_btn.setToolTip("Utiliser comme base pour un nouveau noeud")
        edit_btn_layout.addWidget(template_btn)
        
        layout.addLayout(edit_btn_layout)
        
        # Bouton supprimer
        delete_btn = QPushButton("🗑️ Supprimer")
        delete_btn.clicked.connect(self.delete_library_node)
        layout.addWidget(delete_btn)
        
        # Légende
        legend = QLabel("💡 Double-clic: ajouter au canvas\n📝 Clic droit: menu contextuel")
        legend.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        layout.addWidget(legend)
        
        content.setLayout(layout)
        return self.create_collapsible_panel("Bibliothèque de Noeuds", content, "left")

    def create_preview_panel(self):
        """Crée le panneau de prévisualisation du BAT."""
        content = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "Prévisualisation du script exporté. Le contenu est mis à jour automatiquement "
            "quand le workflow change."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background: #eef7ff; border-radius: 5px;")
        layout.addWidget(info_label)

        preview_toolbar = QHBoxLayout()
        self.generate_preview_btn = QPushButton("Générer")
        self.generate_preview_btn.clicked.connect(self.generate_workflow_preview)
        preview_toolbar.addWidget(self.generate_preview_btn)

        self.preview_status_label = QLabel("")
        self.preview_status_label.setStyleSheet("color: #555; padding-left: 8px;")
        preview_toolbar.addWidget(self.preview_status_label)
        preview_toolbar.addStretch()
        layout.addLayout(preview_toolbar)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.preview_text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; "
            "background: #1e1e1e; color: #d4d4d4;"
        )
        self.preview_highlighter = BatchSyntaxHighlighter(self.preview_text.document())
        layout.addWidget(self.preview_text)

        content.setLayout(layout)
        return self.create_collapsible_panel("Prévisualisation Script", content, "right")

    def create_collapsible_panel(self, title, content_widget, side):
        """Crée un panneau latéral pliable/dépliable."""
        panel = QWidget()
        panel.setProperty("panel_side", side)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(6)

        toggle_btn = QPushButton("◀" if side == "left" else "▶")
        toggle_btn.setFixedWidth(28)
        toggle_btn.clicked.connect(lambda checked=False, current_side=side: self.toggle_side_panel(current_side))
        header_layout.addWidget(toggle_btn)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header.setLayout(header_layout)
        header.setStyleSheet("background: #dfe6e9; border-bottom: 1px solid #bdc3c7;")

        layout.addWidget(header)
        layout.addWidget(content_widget)
        panel.setLayout(layout)
        panel.setMinimumWidth(36)

        if side == "left":
            panel.setMaximumWidth(16777215)
            self.left_panel_content = content_widget
            self.left_panel_toggle_btn = toggle_btn
            self.left_panel_title = title_label
        else:
            panel.setMaximumWidth(16777215)
            self.right_panel_content = content_widget
            self.right_panel_toggle_btn = toggle_btn
            self.right_panel_title = title_label

        return panel

    def toggle_side_panel(self, side):
        """Plie ou déplie un panneau latéral."""
        panel = self.left_panel if side == "left" else self.right_panel
        content = self.left_panel_content if side == "left" else self.right_panel_content
        button = self.left_panel_toggle_btn if side == "left" else self.right_panel_toggle_btn
        title = self.left_panel_title if side == "left" else self.right_panel_title
        expanded_size = self.panel_expanded_sizes[side]
        is_collapsed = content.isVisible()

        if is_collapsed:
            current_width = max(panel.width(), expanded_size)
            self.panel_expanded_sizes[side] = current_width
            content.hide()
            title.hide()
            panel.setMinimumWidth(36)
            panel.setMaximumWidth(36)
            button.setText("▶" if side == "left" else "◀")
        else:
            content.show()
            title.show()
            panel.setMinimumWidth(220 if side == "left" else 260)
            panel.setMaximumWidth(16777215)
            button.setText("◀" if side == "left" else "▶")

        center_size = max(500, self.width() - self.panel_expanded_sizes["left"] - self.panel_expanded_sizes["right"])
        left_size = 36 if not self.left_panel_content.isVisible() else self.panel_expanded_sizes["left"]
        right_size = 36 if not self.right_panel_content.isVisible() else self.panel_expanded_sizes["right"]
        self.main_splitter.setSizes([left_size, center_size, right_size])

    def update_preview_status(self):
        """Affiche si l'aperçu doit être régénéré."""
        if not hasattr(self, 'preview_status_label'):
            return
        if self.preview_dirty:
            self.preview_status_label.setText("Aperçu non à jour")
            self.preview_status_label.setStyleSheet("color: #c0392b; padding-left: 8px; font-weight: bold;")
        else:
            self.preview_status_label.setText("Aperçu à jour")
            self.preview_status_label.setStyleSheet("color: #1e8449; padding-left: 8px; font-weight: bold;")

    def mark_workflow_dirty(self, *_args):
        """Marque le workflow comme modifié sans relancer de génération automatique."""
        if getattr(self.scene, 'temp_connection', None) is not None:
            return
        self.preview_dirty = True
        self.update_preview_status()

    def generate_workflow_preview(self):
        """Recalcule l'ordre puis met à jour l'aperçu du script."""
        self.scene.update_execution_order()
        self.refresh_bat_preview()

    def schedule_bat_preview_refresh(self, *_args):
        """Déclenche une mise à jour différée de l'aperçu BAT."""
        if getattr(self.scene, 'temp_connection', None) is not None:
            return
        self.mark_workflow_dirty()
    
    def show_library_context_menu(self, position):
        """Affiche le menu contextuel pour la bibliothèque"""
        item = self.node_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        add_action = menu.addAction("➕ Ajouter au canvas")
        menu.addSeparator()
        edit_action = menu.addAction("✏️ Éditer")
        template_action = menu.addAction("📋 Utiliser comme template")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Supprimer")
        
        action = menu.exec(self.node_list.mapToGlobal(position))
        
        if action == add_action:
            self.add_node_from_library(item)
        elif action == edit_action:
            self.edit_library_node()
        elif action == template_action:
            self.use_as_template()
        elif action == delete_action:
            self.delete_library_node()
    
    def refresh_library_list(self):
        """Rafraîchit la liste des noeuds (triée par catégorie puis nom)"""
        self.node_list.clear()
        for node_name, node in self.get_sorted_library_nodes():
            if self.library_filter_mode == "verified" and not bool(node.get('verified', False)):
                continue
            category = get_display_category(node)
            display_name = get_display_node_name(node)
            verified_prefix = "✓ " if bool(node.get('verified', False)) else ""
            item = QListWidgetItem(f"{verified_prefix}[{category}] {display_name}")
            item.setData(Qt.ItemDataRole.UserRole, node_name)
            self.node_list.addItem(item)

    def on_library_filter_changed(self, _index):
        """Met à jour le filtre de la liste de bibliothèque."""
        self.library_filter_mode = self.library_filter_combo.currentData() or "all"
        self.refresh_library_list()

    def get_sorted_library_nodes(self):
        """Retourne les noeuds de la bibliothèque triés par catégorie/sous-catégorie/nom."""
        return sorted(
            self.library.get_all_nodes().items(),
            key=lambda x: (
                str(x[1].get('category', 'ZZZ')).lower(),
                str(x[1].get('subcategory', '')).lower(),
                get_display_node_name(x[1]).lower(),
                x[0].lower()
            )
        )
    
    def get_selected_node_name(self):
        """Retourne le nom du noeud sélectionné"""
        current_item = self.node_list.currentItem()
        if not current_item:
            return None
        
        stored_name = current_item.data(Qt.ItemDataRole.UserRole)
        if stored_name:
            return stored_name

        node_text = current_item.text()
        return node_text.split('] ', 1)[1] if '] ' in node_text else node_text
    
    def create_new_node(self):
        """Ouvre le dialog de création de noeud"""
        dialog = NodeCreatorDialog(self.library, self)
        if dialog.exec():
            self.refresh_library_list()
    
    def edit_library_node(self):
        """Édite le noeud sélectionné"""
        node_name = self.get_selected_node_name()
        if not node_name:
            QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord un noeud")
            return
        
        # Ne pas permettre d'éditer les noeuds système essentiels
        if node_name in SYSTEM_SOURCE_NODE_NAMES:
            reply = QMessageBox.question(
                self, "Noeud système",
                "Ce noeud est un noeud système. Voulez-vous vraiment le modifier?\n"
                "(Cela pourrait affecter le fonctionnement du programme)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        node_data = self.library.get_node(node_name)
        if node_data:
            dialog = NodeCreatorDialog(self.library, self, edit_node=node_data)
            if dialog.exec():
                self.refresh_library_list()
    
    def use_as_template(self):
        """Utilise le noeud sélectionné comme template pour un nouveau noeud"""
        node_name = self.get_selected_node_name()
        if not node_name:
            QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord un noeud")
            return
        
        node_data = self.library.get_node(node_name)
        if node_data:
            dialog = NodeCreatorDialog(self.library, self, template_node=node_data)
            if dialog.exec():
                self.refresh_library_list()
    
    def add_node_by_name(self, node_name, scene_pos=None):
        """Ajoute un noeud au canvas depuis son nom de bibliothèque."""
        if not node_name:
            return

        node_data = self.library.get_node(node_name)
        if not node_data:
            return

        if scene_pos is None:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            x = center.x() - 100
            y = center.y() - 40
        else:
            x = scene_pos.x() - 100
            y = scene_pos.y() - 40

        node = Node(node_data, x, y)
        self.scene.addItem(node)
        self.scene.update_scene_bounds()
        self.mark_workflow_dirty()
        self.statusBar().showMessage(f"Noeud ajouté: {get_display_node_name(node_data)}")

    def add_node_from_library(self, item):
        """Ajoute un noeud au canvas depuis la bibliothèque"""
        node_name = item.data(Qt.ItemDataRole.UserRole)
        if not node_name:
            node_text = item.text()
            node_name = node_text.split('] ', 1)[1] if '] ' in node_text else node_text

        self.add_node_by_name(node_name)

    def get_canvas_nodes(self):
        """Retourne les noeuds présents sur le canvas, triés par ordre puis position."""
        return sorted(
            [item for item in self.scene.items() if isinstance(item, Node)],
            key=lambda node: (
                node.execution_order if node.execution_order is not None else 10**9,
                get_display_node_name(node.node_data).lower(),
                node.pos().x(),
                node.pos().y()
            )
        )

    def fit_workflow_in_view(self):
        """Cadre l'ensemble du workflow dans la vue."""
        self.scene.update_scene_bounds()
        nodes = self.get_canvas_nodes()
        if not nodes:
            return

        bounds = QRectF()
        for node in nodes:
            node_rect = node.sceneBoundingRect()
            bounds = node_rect if bounds.isNull() else bounds.united(node_rect)

        self.view.fit_scene_rect(bounds, 140)
        self.statusBar().showMessage("Workflow cadré dans la vue")

    def focus_selected_node(self):
        """Centre la vue sur le noeud actuellement sélectionné."""
        selected_node = next((item for item in self.scene.selectedItems() if isinstance(item, Node)), None)
        if not selected_node:
            QMessageBox.information(self, "Centrer sur la sélection", "Sélectionnez d'abord un noeud.")
            return

        self.view.focus_on_node(selected_node)
        self.statusBar().showMessage(f"Noeud ciblé: {get_display_node_name(selected_node.node_data)}")

    def find_and_focus_node(self):
        """Permet de retrouver rapidement un noeud dans un grand workflow."""
        nodes = self.get_canvas_nodes()
        if not nodes:
            QMessageBox.information(self, "Aller au noeud", "Le canvas ne contient encore aucun noeud.")
            return

        labels = []
        node_lookup = {}
        for index, node in enumerate(nodes, start=1):
            order_label = f"#{node.execution_order}" if node.execution_order is not None else "sans ordre"
            position_label = f"x={int(node.pos().x())}, y={int(node.pos().y())}"
            label = f"{index}. {get_display_node_name(node.node_data)} ({order_label}, {position_label})"
            labels.append(label)
            node_lookup[label] = node

        selected_label, accepted = QInputDialog.getItem(
            self,
            "Aller au noeud",
            "Choisissez le noeud à afficher :",
            labels,
            0,
            False
        )
        if not accepted or not selected_label:
            return

        node = node_lookup[selected_label]
        node.setSelected(True)
        self.view.focus_on_node(node)
        self.statusBar().showMessage(f"Noeud ciblé: {get_display_node_name(node.node_data)}")

    def show_canvas_context_menu(self, global_pos, scene_pos):
        """Affiche un menu contextuel sur le canvas avec les noeuds triés par catégorie."""
        menu = QMenu(self)
        menu.setTitle("Ajouter un noeud")

        categories = {}
        for node_name, node_data in self.get_sorted_library_nodes():
            category = str(node_data.get('category', '')).strip() or 'Autres'
            subcategory = str(node_data.get('subcategory', '')).strip()
            categories.setdefault(category, {}).setdefault(subcategory, []).append((node_name, node_data))

        for category_name, subcategories in categories.items():
            category_menu = menu.addMenu(category_name)

            direct_nodes = subcategories.pop('', [])
            for node_name, node_data in direct_nodes:
                action = category_menu.addAction(get_display_node_name(node_data))
                action.triggered.connect(
                    lambda checked=False, name=node_name, pos=QPointF(scene_pos):
                    self.add_node_by_name(name, pos)
                )

            if direct_nodes and len(subcategories) > 0:
                category_menu.addSeparator()

            for subcategory_name, nodes in subcategories.items():
                subcategory_menu = category_menu.addMenu(subcategory_name)
                for node_name, node_data in nodes:
                    action = subcategory_menu.addAction(get_display_node_name(node_data))
                    action.triggered.connect(
                        lambda checked=False, name=node_name, pos=QPointF(scene_pos):
                        self.add_node_by_name(name, pos)
                    )

        menu.exec(global_pos)
    
    def delete_library_node(self):
        """Supprime un noeud de la bibliothèque"""
        node_name = self.get_selected_node_name()
        if not node_name:
            return
        
        # Ne pas permettre de supprimer les noeuds système
        if node_name in SYSTEM_SOURCE_NODE_NAMES:
            QMessageBox.warning(self, "Erreur", "Impossible de supprimer les noeuds système")
            return
        
        reply = QMessageBox.question(self, "Confirmation", 
                                     f"Supprimer le noeud '{node_name}' de la bibliothèque ?")
        if reply == QMessageBox.StandardButton.Yes:
            self.library.remove_node(node_name)
            self.refresh_library_list()
    
    def on_execution_order_changed(self):
        """Appelé quand l'ordre d'exécution change"""
        self.statusBar().showMessage("Ordre d'exécution mis à jour")
        self.update_preview_status()

    def on_workflow_mode_changed(self, checked):
        """Met à jour le mode d'exécution du workflow."""
        self.workflow_mode = "per_file" if checked else "single_flow"
        mode_label = "boucle par fichier" if checked else "flux unique"
        self.statusBar().showMessage(f"Mode du workflow: {mode_label}")
        self.mark_workflow_dirty()

    def on_script_type_changed(self, _index):
        """Met à jour le type de script exporté."""
        self.script_type = self.script_type_combo.currentData() or "batch"
        labels = {
            "batch": "Batch (.bat)",
            "bash": "Bash (.sh)",
            "powershell": "PowerShell (.ps1)"
        }
        mode_label = labels.get(self.script_type, self.script_type)
        self.statusBar().showMessage(f"Type de script: {mode_label}")
        self.update_preview_highlighter()
        self.mark_workflow_dirty()

    def update_preview_highlighter(self):
        """Active la coloration adaptée dans la prévisualisation."""
        enabled = self.script_type == "batch"
        self.preview_highlighter.setDocument(self.preview_text.document() if enabled else None)
        self.preview_text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; "
            "background: #1e1e1e; color: #d4d4d4;"
        )

    def populate_default_canvas(self):
        """Ajoute les noeuds de base sur un canvas vide."""
        existing_nodes = [item for item in self.scene.items() if isinstance(item, Node)]
        if existing_nodes:
            return

        input_data = self.library.get_node("Fichier Input")
        destination_data = self.library.get_node("Fichier Destination")
        if not input_data or not destination_data:
            return

        input_node = Node(input_data, -220, -20)
        destination_node = Node(destination_data, 80, -20)
        self.scene.addItem(input_node)
        self.scene.addItem(destination_node)
        self.scene.update_scene_bounds()
        self.refresh_all_parameter_links()
        self.fit_workflow_in_view()
        self.mark_workflow_dirty()
    
    def create_menus(self):
        """Crée les menus"""
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu("Fichier")
        
        save_workflow = file_menu.addAction("💾 Sauvegarder workflow")
        save_workflow.triggered.connect(self.save_workflow)
        
        load_workflow = file_menu.addAction("📂 Charger workflow")
        load_workflow.triggered.connect(self.load_workflow)
        
        file_menu.addSeparator()
        
        export_script = file_menu.addAction("▶️ Exporter le script")
        export_script.triggered.connect(self.export_to_bat)
        
        file_menu.addSeparator()
        
        quit_action = file_menu.addAction("Quitter")
        quit_action.triggered.connect(self.close)
        
        # Menu Édition
        edit_menu = menubar.addMenu("Édition")
        
        refresh_order = edit_menu.addAction("🔄 Recalculer l'ordre d'exécution")
        refresh_order.triggered.connect(self.generate_workflow_preview)
        
        edit_menu.addSeparator()

        focus_selected = edit_menu.addAction("🎯 Centrer sur le noeud sélectionné")
        focus_selected.setShortcut("F")
        focus_selected.triggered.connect(self.focus_selected_node)

        find_node = edit_menu.addAction("🔎 Aller à un noeud...")
        find_node.setShortcut("Ctrl+F")
        find_node.triggered.connect(self.find_and_focus_node)

        fit_workflow = edit_menu.addAction("🗺️ Cadrer tout le workflow")
        fit_workflow.setShortcut("Ctrl+0")
        fit_workflow.triggered.connect(self.fit_workflow_in_view)

        edit_menu.addSeparator()
        
        clear_action = edit_menu.addAction("🗑️ Effacer le canvas")
        clear_action.triggered.connect(self.clear_canvas)
        
        # Menu Bibliothèque
        lib_menu = menubar.addMenu("Bibliothèque")
        
        new_node = lib_menu.addAction("➕ Créer nouveau noeud")
        new_node.triggered.connect(self.create_new_node)
        
        lib_menu.addSeparator()
        
        import_library = lib_menu.addAction("📥 Importer bibliothèque")
        import_library.triggered.connect(self.import_library)
        
        export_library = lib_menu.addAction("📤 Exporter bibliothèque")
        export_library.triggered.connect(self.export_library)
        
        # Menu Outils
        tools_menu = menubar.addMenu("Outils")
        
        config_deps = tools_menu.addAction("⚙️ Configurer les dépendances")
        config_deps.triggered.connect(self.configure_dependencies)
    
    def save_workflow(self):
        """Sauvegarde le workflow"""
        filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder le workflow", 
                                                   "", "JSON Files (*.json)")
        if not filename:
            return
        
        workflow = {
            'mode': self.workflow_mode,
            'script_type': self.script_type,
            'nodes': [],
            'connections': []
        }
        
        node_id_map = {}
        
        for item in self.scene.items():
            if isinstance(item, Node):
                node_id = len(workflow['nodes'])
                node_id_map[id(item)] = node_id
                
                node_data = {
                    'id': node_id,
                    'node_uid': item.node_uid,
                    'name': item.node_data['name'],
                    'x': item.pos().x(),
                    'y': item.pos().y(),
                    'verified': bool(item.node_data.get('verified', False)),
                    'parameters': item.parameters,
                    'parameter_links': item.parameter_links,
                    'output_extension': item.output_extension,
                    'execution_order': item.execution_order
                }
                workflow['nodes'].append(node_data)
        
        for item in self.scene.items():
            if isinstance(item, Connection) and item.end_port:
                from_id = node_id_map.get(id(item.start_port.parent_node))
                to_id = node_id_map.get(id(item.end_port.parent_node))
                
                if from_id is not None and to_id is not None:
                    conn_data = {
                        'from_node': from_id,
                        'from_port': item.start_port.index,
                        'to_node': to_id,
                        'to_port': item.end_port.index
                    }
                    workflow['connections'].append(conn_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        
        self.statusBar().showMessage(f"Workflow sauvegardé: {filename}")
    
    def load_workflow(self):
        """Charge un workflow"""
        filename, _ = QFileDialog.getOpenFileName(self, "Charger un workflow", 
                                                   "", "JSON Files (*.json)")
        if not filename:
            return
        
        with open(filename, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        self.workflow_mode = workflow.get('mode', 'per_file')
        self.script_type = workflow.get('script_type', 'batch')
        self.loop_mode_checkbox.setChecked(self.workflow_mode == 'per_file')
        combo_index = self.script_type_combo.findData(self.script_type)
        if combo_index >= 0:
            self.script_type_combo.setCurrentIndex(combo_index)
        
        # Effacer sans demander confirmation
        for item in self.scene.items():
            self.scene.removeItem(item)
        
        node_map = {}
        for node_data in workflow['nodes']:
            library_node = self.library.get_node(node_data['name'])
            if library_node:
                node = Node(library_node, node_data['x'], node_data['y'])
                node.node_uid = node_data.get('node_uid', node.node_uid)
                node.node_data['verified'] = bool(node_data.get('verified', node.node_data.get('verified', False)))
                node.parameters.update(node_data.get('parameters', {}))
                node.parameter_links = node_data.get('parameter_links', {})
                if node._has_dynamic_ports():
                    node._rebuild_ports()
                node.output_extension = normalize_output_extension(
                    node_data.get('output_extension', node.output_extension)
                )
                self.scene.addItem(node)
                node_map[node_data['id']] = node
        
        for conn_data in workflow['connections']:
            from_node = node_map.get(conn_data['from_node'])
            to_node = node_map.get(conn_data['to_node'])
            
            if from_node and to_node:
                from_port_idx = conn_data['from_port']
                to_port_idx = conn_data['to_port']
                
                if from_port_idx < len(from_node.output_ports) and to_port_idx < len(to_node.input_ports):
                    from_port = from_node.output_ports[from_port_idx]
                    to_port = to_node.input_ports[to_port_idx]
                    
                    connection = Connection(from_port, to_port)
                    self.scene.addItem(connection)
                    from_port.connections.append(connection)
                    to_port.connections.append(connection)
        
        self.scene.update_scene_bounds()
        self.fit_workflow_in_view()
        self.statusBar().showMessage(f"Workflow chargé: {filename}")
        self.mark_workflow_dirty()
    
    def configure_dependencies(self):
        """Configure les chemins des dépendances"""
        dialog = DependencyConfigDialog(self.dep_manager, self)
        dialog.exec()

    def get_node_by_uid(self, node_uid):
        for item in self.scene.items():
            if isinstance(item, Node) and item.node_uid == node_uid:
                return item
        return None

    def describe_parameter_link(self, node, param_name):
        link = node.get_parameter_link(param_name)
        if not link:
            return ""

        source_node = self.get_node_by_uid(link.get('node_uid'))
        source_node_name = get_display_node_name(source_node.node_data) if source_node else link.get('node_name', 'Noeud supprimé')
        source_param = link.get('param_name', '')
        return f"{source_node_name} -> {source_param}"

    def resolve_node_parameter_value(self, node, param_name, visited=None):
        if visited is None:
            visited = set()

        visit_key = (node.node_uid, param_name)
        if visit_key in visited:
            return str(node.parameters.get(param_name, ""))

        visited.add(visit_key)
        link = node.get_parameter_link(param_name)
        if not link:
            return str(node.parameters.get(param_name, ""))

        source_node = self.get_node_by_uid(link.get('node_uid'))
        source_param_name = link.get('param_name')
        if source_node is None or not source_param_name:
            return str(node.parameters.get(param_name, ""))

        return self.resolve_node_parameter_value(source_node, source_param_name, visited)

    def would_create_parameter_cycle(self, target_node, target_param_name, source_node, source_param_name, visited=None):
        if visited is None:
            visited = set()

        visit_key = (source_node.node_uid, source_param_name)
        if visit_key in visited:
            return False

        if source_node is target_node and source_param_name == target_param_name:
            return True

        visited.add(visit_key)
        source_link = source_node.get_parameter_link(source_param_name)
        if not source_link:
            return False

        upstream_node = self.get_node_by_uid(source_link.get('node_uid'))
        upstream_param_name = source_link.get('param_name')
        if upstream_node is None or not upstream_param_name:
            return False

        return self.would_create_parameter_cycle(
            target_node,
            target_param_name,
            upstream_node,
            upstream_param_name,
            visited
        )

    def get_resolved_node_parameters(self, node):
        return {
            param['name']: self.resolve_node_parameter_value(node, param['name'])
            for param in node.node_data.get('parameters', [])
        }

    def refresh_all_parameter_links(self):
        for item in self.scene.items():
            if isinstance(item, Node):
                item.refresh_parameter_widgets()

    def prompt_parameter_link(self, target_node, target_param_name):
        candidates = []
        for item in self.scene.items():
            if not isinstance(item, Node) or item is target_node:
                continue
            for param in item.node_data.get('parameters', []):
                source_param_name = param.get('name')
                if not source_param_name:
                    continue
                label = f"{get_display_node_name(item.node_data)} -> {source_param_name}"
                candidates.append((label, item, source_param_name))

        if not candidates:
            QMessageBox.information(
                self,
                "Lier un paramètre",
                "Aucun autre paramètre de noeud n'est disponible pour créer une liaison."
            )
            return

        labels = [label for label, _node, _param in candidates]
        selected_label, accepted = QInputDialog.getItem(
            self,
            "Lier un paramètre",
            f"Source pour {get_display_node_name(target_node.node_data)} -> {target_param_name} :",
            labels,
            0,
            False
        )
        if not accepted or not selected_label:
            return

        for label, source_node, source_param_name in candidates:
            if label != selected_label:
                continue

            if self.would_create_parameter_cycle(target_node, target_param_name, source_node, source_param_name):
                QMessageBox.warning(
                    self,
                    "Lier un paramètre",
                    "Cette liaison créerait une boucle entre paramètres."
                )
                return

            target_node.set_parameter_link(target_param_name, source_node, source_param_name)
            target_node.update()
            self.schedule_bat_preview_refresh()
            self.statusBar().showMessage(
                f"Liaison créée: {get_display_node_name(target_node.node_data)}.{target_param_name} <- {label}"
            )
            return

    def _is_multi_file_node(self, node):
        return node.node_data['name'] == MULTI_FILE_NODE_NAME

    def _is_switch_node(self, node):
        return node.node_data['name'] == SWITCH_NODE_NAME

    def _is_merge_node(self, node):
        return node.node_data['name'] == MERGE_NODE_NAME

    def _make_output_key(self, node, port_index=0):
        return (node.node_uid, port_index)

    def _resolve_node_input_files(self, node, node_outputs):
        input_files = []
        for port in node.input_ports:
            for conn in port.connections:
                source_node = conn.start_port.parent_node
                key = self._make_output_key(source_node, conn.start_port.index)
                if key in node_outputs:
                    input_files.append(node_outputs[key])
        return input_files

    def _split_brace_placeholders(self, value):
        value = str(value or "")
        parts = []
        cursor = 0
        while cursor < len(value):
            start = value.find("{", cursor)
            if start < 0:
                parts.append(("text", value[cursor:]))
                break
            if start > cursor:
                parts.append(("text", value[cursor:start]))
            end = value.find("}", start + 1)
            if end < 0:
                parts.append(("text", value[start:]))
                break
            parts.append(("placeholder", value[start + 1:end]))
            cursor = end + 1
        return [part for part in parts if part[1] != ""]

    def _sanitize_global_name(self, name):
        sanitized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(name or "").strip())
        return sanitized.strip("_") or "GLOBAL_VALUE"

    def _get_global_variable_entries(self, node, resolved_params=None):
        if node.node_data.get('name') != GLOBAL_VARIABLES_NODE_NAME:
            return []
        resolved_params = resolved_params or self.get_resolved_node_parameters(node)
        entries = []
        try:
            count = int(resolved_params.get('Nombre de variables', '2') or 2)
        except Exception:
            count = 2
        count = max(1, min(GLOBAL_VARIABLES_MAX_SLOTS, count))
        for index in range(1, count + 1):
            name = str(resolved_params.get(f'Nom {index}', '') or '').strip()
            value = str(resolved_params.get(f'Valeur {index}', '') or '')
            if name:
                entries.append((name, value, index))
        return entries

    def _get_input_variable_entries(self, node, resolved_params=None):
        if node.node_data.get('name') != INPUT_VARIABLES_NODE_NAME:
            return []
        resolved_params = resolved_params or self.get_resolved_node_parameters(node)
        entries = []
        try:
            count = int(resolved_params.get('Nombre de variables', '2') or 2)
        except Exception:
            count = 2
        count = max(1, min(INPUT_VARIABLES_MAX_SLOTS, count))
        for index in range(1, count + 1):
            question = str(resolved_params.get(f'Question {index}', '') or '').strip()
            name = str(resolved_params.get(f'Nom {index}', '') or '').strip()
            default_value = str(resolved_params.get(f'Valeur par défaut {index}', '') or '')
            if name:
                entries.append((name, question, default_value, index))
        return entries

    def _extract_placeholder_names(self, value):
        names = []
        for part_type, part_value in self._split_brace_placeholders(value):
            if part_type == "placeholder":
                names.append(str(part_value).strip())
        return names

    def _replace_global_placeholders_in_text(self, value, global_values):
        rendered_parts = []
        for part_type, part_value in self._split_brace_placeholders(value):
            if part_type == "text":
                rendered_parts.append(part_value)
            else:
                rendered_parts.append(global_values.get(part_value, f"{{{part_value}}}"))
        return "".join(rendered_parts)

    def _render_global_value_text(self, value, input_values, global_values):
        rendered_parts = []
        for part_type, part_value in self._split_brace_placeholders(value):
            if part_type == "text":
                rendered_parts.append(part_value)
                continue

            placeholder = str(part_value).strip()
            if placeholder == "input":
                rendered_parts.append(input_values[0] if len(input_values) >= 1 else "")
            elif placeholder.startswith("input") and placeholder[5:].isdigit():
                input_index = int(placeholder[5:]) - 1
                rendered_parts.append(input_values[input_index] if 0 <= input_index < len(input_values) else "")
            else:
                rendered_parts.append(global_values.get(placeholder, f"{{{placeholder}}}"))
        return "".join(rendered_parts)

    def _render_batch_global_value(self, lines, node, slot_index, value, input_files, global_values, runtime_index):
        runtime_var = f"GLOBAL_EXPR_{node.execution_order or 0}_{slot_index}_{runtime_index}"
        lines.append(f'set "{runtime_var}="')

        for part_type, part_value in self._split_brace_placeholders(value):
            if part_type == "text":
                text = str(part_value).replace('%INPUT_NAME%', '!INPUT_NAME!')
                text = text.replace('%INPUT_PATH%', '!INPUT_PATH!')
                text = text.replace('%INPUT_EXT%', '!INPUT_EXT!')
                text = text.replace('"', '^"')
                lines.append(f'set "{runtime_var}=!{runtime_var}!{text}"')
                continue

            placeholder = str(part_value).strip()
            if placeholder == "input":
                input_index = 0
            elif placeholder.startswith("input") and placeholder[5:].isdigit():
                input_index = int(placeholder[5:]) - 1
            else:
                input_index = None

            if input_index is not None:
                if 0 <= input_index < len(input_files):
                    lines.append(f'for /f "usebackq delims=" %%A in ({input_files[input_index]}) do set "{runtime_var}=!{runtime_var}!%%A"')
            else:
                rendered_value = global_values.get(placeholder, f"{{{placeholder}}}")
                lines.append(f'set "{runtime_var}=!{runtime_var}!{rendered_value}"')

        return f'!{runtime_var}!', runtime_index + 1

    def _get_multi_file_specs(self, node):
        resolved_params = self.get_resolved_node_parameters(node)
        try:
            count = int(resolved_params.get('Nombre de fichiers', '2') or 2)
        except Exception:
            count = 2
        count = max(1, min(MULTI_FILE_MAX_SLOTS, count))
        specs = []
        for idx in range(count):
            label = str(resolved_params.get(f'Type fichier {idx + 1}', f'Fichier {idx + 1}') or f'Fichier {idx + 1}').strip()
            raw_exts = str(resolved_params.get(f'Extensions fichier {idx + 1}', '') or '')
            extensions = []
            for ext in raw_exts.split(','):
                normalized = normalize_output_extension(ext)
                if normalized:
                    extensions.append(normalized.lower())
            specs.append({
                "label": label,
                "extensions": extensions
            })
        return specs

    def _get_switch_specs(self, node, resolved_params=None):
        if not self._is_switch_node(node):
            return []

        resolved_params = resolved_params or self.get_resolved_node_parameters(node)
        try:
            count = int(resolved_params.get('Nombre de conditions', '2') or 2)
        except Exception:
            count = 2
        count = max(1, min(SWITCH_MAX_CONDITIONS, count))

        specs = []
        for index in range(1, count + 1):
            specs.append({
                "operator": str(resolved_params.get(f'Opérateur {index}', '==') or '==').strip() or '==',
                "value": str(resolved_params.get(f'Valeur {index}', '') or ''),
                "label": str(resolved_params.get(f'Label sortie {index}', f'Cas {index}') or f'Cas {index}').strip() or f'Cas {index}'
            })
        return specs

    def _strip_wrapping_quotes(self, value):
        value = str(value or "")
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value

    def _extract_batch_runtime_var(self, expression):
        expression = str(expression or "").strip()
        if expression.startswith('"!') and expression.endswith('!"'):
            return expression[2:-2]
        if expression.startswith('!') and expression.endswith('!'):
            return expression[1:-1]
        return None

    def _extract_bash_runtime_var(self, expression):
        expression = str(expression or "").strip()
        if expression.startswith('"${') and expression.endswith('}"'):
            return expression[3:-2]
        if expression.startswith('${') and expression.endswith('}'):
            return expression[2:-1]
        return None

    def _extract_powershell_runtime_var(self, expression):
        expression = str(expression or "").strip()
        if expression.startswith('$') and expression[1:].replace('_', '').isalnum():
            return expression
        return None

    def _build_batch_node_input_guard(self, input_files):
        checks = []
        for input_file in input_files:
            var_name = self._extract_batch_runtime_var(input_file)
            if var_name:
                checks.append(f'if not defined {var_name} set "NODE_READY=0"')
        return checks

    def _build_bash_node_input_guard(self, input_files):
        conditions = []
        for input_file in input_files:
            var_name = self._extract_bash_runtime_var(input_file)
            if var_name:
                conditions.append(f'[ -n "${{{var_name}:-}}" ]')
        return conditions

    def _build_powershell_node_input_guard(self, input_files):
        conditions = []
        for input_file in input_files:
            var_name = self._extract_powershell_runtime_var(input_file)
            if var_name:
                conditions.append(f'(-not [string]::IsNullOrWhiteSpace({var_name}))')
        return conditions

    def _get_switch_batch_ps_operator(self, operator):
        mapping = {
            "==": "-eq",
            "!=": "-ne",
            ">": "-gt",
            ">=": "-ge",
            "<": "-lt",
            "<=": "-le"
        }
        return mapping.get(operator, "-eq")

    def _build_bash_switch_condition(self, left_var, right_var, operator):
        left_ref = f'${{{left_var}}}'
        right_ref = f'${{{right_var}}}'
        if operator == "==":
            return f'[[ "{left_ref}" == "{right_ref}" ]]'
        if operator == "!=":
            return f'[[ "{left_ref}" != "{right_ref}" ]]'
        if operator == ">":
            return f'[[ "{left_ref}" > "{right_ref}" ]]'
        if operator == ">=":
            return f'[[ "{left_ref}" == "{right_ref}" || "{left_ref}" > "{right_ref}" ]]'
        if operator == "<":
            return f'[[ "{left_ref}" < "{right_ref}" ]]'
        if operator == "<=":
            return f'[[ "{left_ref}" == "{right_ref}" || "{left_ref}" < "{right_ref}" ]]'
        return f'[[ "{left_ref}" == "{right_ref}" ]]'

    def _build_powershell_switch_condition(self, left_expr, right_expr, operator):
        mapping = {
            "==": "-eq",
            "!=": "-ne",
            ">": "-gt",
            ">=": "-ge",
            "<": "-lt",
            "<=": "-le"
        }
        return f'({left_expr} {mapping.get(operator, "-eq")} {right_expr})'

    def _make_runtime_output_var_name(self, node, port_index=0):
        return f"NODE_OUT_{node.execution_order or 0}_{port_index}"

    def _get_required_input_count(self, execution_order):
        count = 0
        for node in execution_order:
            if node.node_data['name'] == 'Fichier Input':
                count += 1
            elif self._is_multi_file_node(node):
                count += len(self._get_multi_file_specs(node))
        return count
    
    def _get_node_output_extension(self, node, global_values=None):
        """Retourne l'extension de sortie explicitement configurée sur le noeud."""
        if node.node_data['name'] in SYSTEM_SOURCE_NODE_NAMES or node.node_data['name'] in [GLOBAL_VARIABLES_NODE_NAME, INPUT_VARIABLES_NODE_NAME]:
            return ""

        extension = normalize_output_extension(node.output_extension or node.node_data.get('output_extension', ''))
        for param_name, param_value in self.get_resolved_node_parameters(node).items():
            extension = extension.replace(f'{{{param_name}}}', str(param_value))
        if global_values:
            extension = self._replace_global_placeholders_in_text(extension, global_values)
        extension = extension.replace('%INPUT_EXT%', '!INPUT_EXT!')
        return normalize_output_extension(extension) or '.tmp'

    def _get_execution_nodes(self):
        """Retourne les noeuds du workflow triés par ordre d'exécution."""
        nodes_list = [item for item in self.scene.items() if isinstance(item, Node)]
        if not nodes_list:
            return [], []

        resolved_params_map = {
            node: self.get_resolved_node_parameters(node)
            for node in nodes_list
        }

        global_producers = {}
        for node in sorted(nodes_list, key=lambda n: (n.pos().x(), n.pos().y())):
            for var_name, _var_value, _slot_index in self._get_global_variable_entries(node, resolved_params_map[node]):
                global_producers[var_name] = node
            for var_name, _question, _default_value, _slot_index in self._get_input_variable_entries(node, resolved_params_map[node]):
                global_producers[var_name] = node

        dependencies = {node: set() for node in nodes_list}
        for node in nodes_list:
            for port in node.input_ports:
                for conn in port.connections:
                    dependencies[node].add(conn.start_port.parent_node)

            builtin_placeholders = {"input", "output"}
            builtin_placeholders.update(f"input{i}" for i in range(2, 11))
            builtin_placeholders.update(param.get('name', '') for param in node.node_data.get('parameters', []))

            texts_to_scan = [node.node_data.get('template', ''), node.output_extension or node.node_data.get('output_extension', '')]
            texts_to_scan.extend(resolved_params_map[node].values())
            for text in texts_to_scan:
                for placeholder in self._extract_placeholder_names(text):
                    if placeholder in builtin_placeholders:
                        continue
                    producer = global_producers.get(placeholder)
                    if producer is not None and producer is not node:
                        dependencies[node].add(producer)

        pending = set(nodes_list)
        execution_order = []
        while pending:
            ready = [node for node in pending if all(dep not in pending for dep in dependencies[node])]
            if not ready:
                ready = sorted(pending, key=lambda n: (n.pos().x(), n.pos().y()))[:1]
            else:
                ready.sort(key=lambda n: (n.pos().x(), n.pos().y()))

            for node in ready:
                execution_order.append(node)
                pending.remove(node)

        for node in nodes_list:
            node.execution_order = None
        for index, node in enumerate(execution_order, start=1):
            node.execution_order = index
            node.update()
        return nodes_list, execution_order

    def _replace_leading_command(self, cmd, command_name, replacement):
        """Remplace la commande de tête par le chemin complet sur chaque ligne du template."""
        cmd = str(cmd)
        command_name = str(command_name or "").strip()
        if not command_name:
            return cmd

        quoted_name = f'"{command_name}"'
        replaced_lines = []

        for line in cmd.splitlines():
            stripped = line.lstrip()
            leading_spaces = line[:len(line) - len(stripped)]

            if stripped.startswith(quoted_name):
                replaced_lines.append(leading_spaces + replacement + stripped[len(quoted_name):])
                continue

            if stripped == command_name:
                replaced_lines.append(leading_spaces + replacement)
                continue

            if stripped.startswith(command_name):
                next_index = len(command_name)
                if next_index == len(stripped) or stripped[next_index].isspace():
                    replaced_lines.append(leading_spaces + replacement + stripped[next_index:])
                    continue

            replaced_lines.append(line)

        return "\n".join(replaced_lines)

    def _get_script_preview_content(self):
        """Construit le contenu du script correspondant au workflow courant."""
        if self.script_type == "powershell":
            return self.generate_powershell_preview_content()
        if self.script_type == "bash":
            return self.generate_bash_preview_content()
        return self.generate_batch_preview_content()

    def generate_batch_preview_content(self):
        """Construit le contenu Batch correspondant au workflow courant."""
        nodes_list, execution_order = self._get_execution_nodes()

        warnings = []
        if len(execution_order) != len(nodes_list):
            warnings.append(
                "ATTENTION: certains noeuds n'ont pas d'ordre d'exécution défini. "
                "Vérifiez les connexions du workflow."
            )

        required_input_count = self._get_required_input_count(execution_order)
        is_single_flow = self.workflow_mode == "single_flow"
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        startup_global_values = {}

        def append_startup_input_variables(lines):
            for node in execution_order:
                resolved_params = self.get_resolved_node_parameters(node)
                for var_name, question, default_value, _slot_index in self._get_input_variable_entries(node, resolved_params):
                    env_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                    prompt_text = self._replace_global_placeholders_in_text(str(question), startup_global_values).replace('"', '^"')
                    rendered_default = self._replace_global_placeholders_in_text(str(default_value), startup_global_values)
                    if rendered_default:
                        prompt_text = f"{prompt_text} [{rendered_default}] "
                    else:
                        prompt_text = f"{prompt_text} "
                    lines.append(f'set /p "{env_name}={prompt_text}"')
                    if rendered_default:
                        lines.append(f'if not defined {env_name} set "{env_name}={rendered_default}"')
                    startup_global_values[var_name] = f'!{env_name}!'
            if startup_global_values:
                lines.append("")

        def append_flow_body(lines, mode):
            temp_counter = 0
            runtime_global_counter = 0
            node_outputs = {}
            temp_files = []
            input_node_index = 0
            global_values = dict(startup_global_values)

            for node in execution_order:
                lines.append(f"REM --- Etape {node.execution_order}: {node.node_data['name']} ---")

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(
                        str(param_value).replace('%INPUT_NAME%', '!INPUT_NAME!').replace('%INPUT_PATH%', '!INPUT_PATH!').replace('%INPUT_EXT%', '!INPUT_EXT!'),
                        global_values
                    )
                    for param_name, param_value in resolved_params.items()
                }
                output_var_name = self._make_runtime_output_var_name(node, 0)
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source'] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
                    lines.append(f'set "{output_var_name}="')
                if node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    for var_name, _var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        env_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        lines.append(f'set "{env_name}="')
                skip_label = f"SKIP_NODE_{node.execution_order or 0}"
                should_guard_inputs = bool(node.input_ports) and not self._is_merge_node(node)
                if should_guard_inputs:
                    lines.append('set "NODE_READY=1"')
                    lines.extend(self._build_batch_node_input_guard(input_files))
                    lines.append(f'if "!NODE_READY!"=="0" goto {skip_label}')

                if node.node_data['name'] == 'Fichier Input':
                    if mode == "single_flow":
                        input_node_index += 1
                        node_outputs[self._make_output_key(node, 0)] = f'"%~f{input_node_index}"'
                    else:
                        node_outputs[self._make_output_key(node, 0)] = '"%INPUT_FULL%"'

                elif self._is_multi_file_node(node):
                    if mode != "single_flow":
                        lines.append("echo ERREUR: Le noeud Multi-fichiers nécessite le mode flux unique")
                        lines.append("goto FLOW_ERROR")
                    else:
                        specs = self._get_multi_file_specs(node)
                        start_arg = input_node_index + 1
                        end_arg = input_node_index + len(specs)
                        prefix = f"MULTI_{node.execution_order or 0}"

                        for spec_index, spec in enumerate(specs, start=1):
                            var_name = f"{prefix}_{spec_index}"
                            lines.append(f'set "{var_name}="')

                        for arg_index in range(start_arg, end_arg + 1):
                            lines.append(f'set "CANDIDATE_FILE=%~f{arg_index}"')
                            lines.append(f'set "CANDIDATE_EXT=%~x{arg_index}"')
                            lines.append('set "CANDIDATE_MATCHED="')
                            for spec_index, spec in enumerate(specs, start=1):
                                var_name = f"{prefix}_{spec_index}"
                                for ext in spec["extensions"]:
                                    lines.append(
                                        f'if not defined CANDIDATE_MATCHED if not defined {var_name} if /I "!CANDIDATE_EXT!"=="{ext}" (set "{var_name}=!CANDIDATE_FILE!" & set "CANDIDATE_MATCHED=1")'
                                    )
                            lines.append("")

                        for spec_index, spec in enumerate(specs, start=1):
                            var_name = f"{prefix}_{spec_index}"
                            lines.append(f'if not defined {var_name} (')
                            lines.append(f'    echo ERREUR: Impossible d''identifier le fichier attendu pour {spec["label"]}')
                            lines.append('    goto FLOW_ERROR')
                            lines.append(')')
                            node_outputs[self._make_output_key(node, spec_index - 1)] = f'"!{var_name}!"'

                        input_node_index += len(specs)

                elif self._is_switch_node(node):
                    specs = self._get_switch_specs(node, resolved_params)
                    switch_prefix = f"SWITCH_{node.execution_order or 0}"
                    switch_input_var = f"{switch_prefix}_INPUT"
                    switch_value_var = f"{switch_prefix}_VALUE"
                    switch_matched_var = f"{switch_prefix}_MATCHED"
                    switch_input_value = self._strip_wrapping_quotes(input_files[0]) if input_files else ""

                    lines.append(f'set "{switch_input_var}={switch_input_value}"')
                    lines.append(f'set "{switch_value_var}={rendered_params.get("Variable", "!INPUT_EXT!")}"')
                    lines.append(f'set "{switch_matched_var}="')

                    for spec_index, spec in enumerate(specs, start=1):
                        out_var = f"{switch_prefix}_OUT_{spec_index - 1}"
                        test_var = f"{switch_prefix}_TEST_{spec_index}"
                        compare_value = str(rendered_params.get(f'Valeur {spec_index}', spec['value']) or '').replace("'", "''")
                        compare_operator = self._get_switch_batch_ps_operator(spec['operator'])
                        lines.append(f'set "{out_var}="')
                        lines.append(f'set "{test_var}=0"')
                        lines.append(
                            f'for /f %%R in (\'powershell -NoProfile -Command "$left = $env:{switch_value_var}; $right = \'{compare_value}\'; if ($left {compare_operator} $right) {{ \'1\' }} else {{ \'0\' }}"\') do set "{test_var}=%%R"'
                        )
                        lines.append(
                            f'if not defined {switch_matched_var} if "!{test_var}!"=="1" (set "{out_var}=!{switch_input_var}!" & set "{switch_matched_var}=1")'
                        )
                        node_outputs[self._make_output_key(node, spec_index - 1)] = f'"!{out_var}!"'

                    default_out_var = f"{switch_prefix}_OUT_{len(specs)}"
                    lines.append(f'set "{default_out_var}="')
                    lines.append(f'if not defined {switch_matched_var} set "{default_out_var}=!{switch_input_var}!"')
                    node_outputs[self._make_output_key(node, len(specs))] = f'"!{default_out_var}!"'

                elif self._is_merge_node(node):
                    node_outputs[self._make_output_key(node, 0)] = f'"!{output_var_name}!"'
                    for input_file in input_files:
                        runtime_var = self._extract_batch_runtime_var(input_file)
                        if runtime_var:
                            lines.append(f'if not defined {output_var_name} if defined {runtime_var} set "{output_var_name}=!{runtime_var}!"')
                        else:
                            lines.append(f'if not defined {output_var_name} set "{output_var_name}={self._strip_wrapping_quotes(input_file)}"')

                elif node.node_data['name'] == 'Fichier Source':
                    output_file = rendered_params.get('Chemin fichier', '')
                    if output_file:
                        lines.append(f'set "{output_var_name}={output_file}"')
                        node_outputs[self._make_output_key(node, 0)] = f'"!{output_var_name}!"'
                    else:
                        lines.append("echo ERREUR: Aucun fichier source defini!")
                        lines.append("goto FLOW_ERROR")

                elif node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    for var_name, var_value, slot_index in self._get_global_variable_entries(node, resolved_params):
                        rendered_value, runtime_global_counter = self._render_batch_global_value(
                            lines,
                            node,
                            slot_index,
                            var_value,
                            input_files,
                            global_values,
                            runtime_global_counter
                        )
                        env_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        lines.append(f'set "{env_name}={rendered_value}"')
                        global_values[var_name] = f'!{env_name}!'

                elif node.node_data['name'] == 'Fichier Destination':
                    if input_files:
                        nom = rendered_params.get('Nom fichier', '%INPUT_NAME%')
                        ext = rendered_params.get('Extension', '.mp4')
                        dossier = rendered_params.get('Dossier de sortie', '')

                        if dossier:
                            lines.append(f'if not exist "{dossier}" mkdir "{dossier}"')
                            output_file = f'{dossier}\\{nom}{ext}'
                        else:
                            output_file = f'!INPUT_PATH!{nom}{ext}'

                        clean_input = input_files[0]
                        lines.append(f'copy {clean_input} "{output_file}" >nul')
                        lines.append('if !errorlevel! neq 0 (')
                        lines.append('    echo ERREUR: Copie du fichier final echouee')
                        lines.append('    goto FLOW_ERROR')
                        lines.append(')')
                        lines.append(f'echo   Output: {nom}{ext}')

                else:
                    temp_counter += 1
                    temp_ext = self._get_node_output_extension(node, global_values)
                    output_file = f'%TEMP%\\cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = f'"!{output_var}!"'
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'set "{output_var}={output_file}"')

                    if template:
                        cmd = template
                        cmd = cmd.replace('{input}', input_files[0] if input_files else '""')

                        for input_index in range(1, max(len(input_files), len(node.input_ports))):
                            placeholder = f'{{input{input_index + 1}}}'
                            input_value = input_files[input_index] if input_index < len(input_files) else '""'
                            cmd = cmd.replace(placeholder, input_value)

                        cmd = cmd.replace('{output}', f'"{output_file}"')

                        for param_name, param_value in rendered_params.items():
                            cmd = cmd.replace(f'{{{param_name}}}', param_value)

                        cmd = self._replace_global_placeholders_in_text(cmd, global_values)

                        if command_name:
                            cmd = self._replace_leading_command(cmd, command_name, f'"{command_path}"')

                        lines.append(cmd)
                        lines.append('if !errorlevel! neq 0 (')
                        lines.append(f'    echo ERREUR: {node.node_data["name"]} a echoue')
                        lines.append('    goto FLOW_ERROR')
                        lines.append(')')
                    elif command_path:
                        cmd = f'"{command_path}"'
                        if input_files:
                            cmd += f' {input_files[0]}'
                        cmd += f' "{output_file}"'
                        lines.append(cmd)

                if should_guard_inputs:
                    lines.append(f":{skip_label}")
                lines.append("")

            if temp_files:
                lines.append("REM Nettoyage temporaires")
                for temp_file in temp_files:
                    lines.append(f'if exist "{temp_file}" del "{temp_file}"')
                lines.append("")

        bat_lines = []
        bat_lines.append("@echo off")
        bat_lines.append("setlocal enabledelayedexpansion")
        bat_lines.append("chcp 65001 >nul")
        bat_lines.append("REM ============================================================")
        bat_lines.append("REM Script généré par CLI Node Editor")
        bat_lines.append("REM Compatible SendTo - Supporte plusieurs fichiers")
        bat_lines.append("REM ============================================================")
        bat_lines.append("")
        bat_lines.append("REM Vérification des arguments")
        bat_lines.append('if "%~1"=="" (')
        bat_lines.append("    echo ERREUR: Aucun fichier specifie")
        bat_lines.append("    echo.")
        bat_lines.append("    echo Usage: %~nx0 fichier1.ext [fichier2.ext] [...]")
        bat_lines.append("    echo Ou glissez-deposez des fichiers sur ce script")
        bat_lines.append("    pause")
        bat_lines.append("    exit /b 1")
        bat_lines.append(")")
        bat_lines.append("")

        bat_lines.append("set TOTAL_FILES=0")
        bat_lines.append("set SUCCESS_COUNT=0")
        bat_lines.append("set ERROR_COUNT=0")
        bat_lines.append("")

        bat_lines.append("REM Comptage des fichiers")
        bat_lines.append("for %%A in (%*) do set /a TOTAL_FILES+=1")
        bat_lines.append("echo.")
        bat_lines.append("echo ============================================================")
        if is_single_flow:
            bat_lines.append("echo    Execution d'un flux unique")
            bat_lines.append("echo    Fichiers en entree: %TOTAL_FILES%")
        else:
            bat_lines.append("echo    Traitement de %TOTAL_FILES% fichier(s)")
        bat_lines.append("echo ============================================================")
        bat_lines.append("echo.")
        bat_lines.append("")
        append_startup_input_variables(bat_lines)

        if is_single_flow:
            if required_input_count > 1:
                for input_index in range(2, required_input_count + 1):
                    bat_lines.append(f'if "%~{input_index}"=="" goto FLOW_ARG_ERROR')
                bat_lines.append("")

            bat_lines.append("REM ============================================================")
            bat_lines.append("REM FLUX UNIQUE")
            bat_lines.append("REM ============================================================")
            bat_lines.append('set "CURRENT_FILE=%~1"')
            bat_lines.append('set "INPUT_NAME=%~n1"')
            bat_lines.append('set "INPUT_EXT=%~x1"')
            bat_lines.append('set "INPUT_DRIVE=%~d1"')
            bat_lines.append('set "INPUT_PATH=%~dp1"')
            bat_lines.append('set "INPUT_FULL=%~f1"')
            bat_lines.append("")
            bat_lines.append("echo ------------------------------------------------------------")
            bat_lines.append("echo Flux unique")
            bat_lines.append("echo ------------------------------------------------------------")
            bat_lines.append("")
            append_flow_body(bat_lines, "single_flow")
            bat_lines.append("echo   [OK] Flux termine avec succes")
            bat_lines.append("set SUCCESS_COUNT=1")
            bat_lines.append("goto END_FLOW")
            bat_lines.append("")
            bat_lines.append(":FLOW_ARG_ERROR")
            bat_lines.append("echo ERREUR: Nombre de fichiers insuffisant pour les entrées du flux unique")
            bat_lines.append("set ERROR_COUNT=1")
            bat_lines.append("goto END_FLOW")
            bat_lines.append("")
            bat_lines.append(":FLOW_ERROR")
            bat_lines.append("echo   [ERREUR] Echec du flux")
            bat_lines.append("set ERROR_COUNT=1")
            bat_lines.append("goto END_FLOW")
            bat_lines.append("")
            bat_lines.append(":END_FLOW")
        else:
            bat_lines.append("REM ============================================================")
            bat_lines.append("REM BOUCLE SUR TOUS LES FICHIERS")
            bat_lines.append("REM ============================================================")
            bat_lines.append(":PROCESS_LOOP")
            bat_lines.append('if "%~1"=="" goto END_LOOP')
            bat_lines.append("")
            bat_lines.append("REM Variables du fichier courant")
            bat_lines.append('set "CURRENT_FILE=%~1"')
            bat_lines.append('set "INPUT_NAME=%~n1"')
            bat_lines.append('set "INPUT_EXT=%~x1"')
            bat_lines.append('set "INPUT_DRIVE=%~d1"')
            bat_lines.append('set "INPUT_PATH=%~dp1"')
            bat_lines.append('set "INPUT_FULL=%~f1"')
            bat_lines.append("")
            bat_lines.append("echo ------------------------------------------------------------")
            bat_lines.append('echo Traitement: %INPUT_NAME%%INPUT_EXT%')
            bat_lines.append("echo ------------------------------------------------------------")
            bat_lines.append("")
            append_flow_body(bat_lines, "per_file")
            bat_lines.append("echo   [OK] Termine avec succes")
            bat_lines.append("set /a SUCCESS_COUNT+=1")
            bat_lines.append("goto NEXT_FILE")
            bat_lines.append("")
            bat_lines.append(":FLOW_ERROR")
            bat_lines.append("echo   [ERREUR] Echec du traitement")
            bat_lines.append("set /a ERROR_COUNT+=1")
            bat_lines.append("")
            bat_lines.append(":NEXT_FILE")
            bat_lines.append("echo.")
            bat_lines.append("shift")
            bat_lines.append("goto PROCESS_LOOP")
            bat_lines.append("")
            bat_lines.append(":END_LOOP")

        bat_lines.append("echo ============================================================")
        bat_lines.append("echo    RESUME")
        bat_lines.append("echo ============================================================")
        bat_lines.append("echo   Total:   %TOTAL_FILES% fichier(s)")
        bat_lines.append("echo   Succes:  %SUCCESS_COUNT%")
        bat_lines.append("echo   Erreurs: %ERROR_COUNT%")
        bat_lines.append("echo ============================================================")
        bat_lines.append("echo.")
        bat_lines.append("")
        bat_lines.append("if %ERROR_COUNT% gtr 0 (")
        bat_lines.append("    echo Certains fichiers ont echoue.")
        bat_lines.append("    pause")
        bat_lines.append("    exit /b 1")
        bat_lines.append(")")
        bat_lines.append("")
        bat_lines.append("echo Tous les fichiers ont ete traites avec succes!")
        bat_lines.append("timeout /t 3 >nul")
        bat_lines.append("exit /b 0")

        return "\n".join(bat_lines), warnings

    def generate_bash_preview_content(self):
        """Construit le contenu Bash correspondant au workflow courant."""
        nodes_list, execution_order = self._get_execution_nodes()

        warnings = []
        if len(execution_order) != len(nodes_list):
            warnings.append(
                "ATTENTION: certains noeuds n'ont pas d'ordre d'exécution défini. "
                "Vérifiez les connexions du workflow."
            )

        required_input_count = self._get_required_input_count(execution_order)
        is_single_flow = self.workflow_mode == "single_flow"
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        def bashify_value(value):
            value = str(value)
            value = value.replace('%INPUT_NAME%', '${INPUT_NAME}')
            value = value.replace('%INPUT_PATH%', '${INPUT_PATH}')
            value = value.replace('%INPUT_EXT%', '${INPUT_EXT}')
            return value

        startup_global_values = {}

        def append_startup_input_variables(lines):
            for node in execution_order:
                resolved_params = self.get_resolved_node_parameters(node)
                for var_name, question, default_value, _slot_index in self._get_input_variable_entries(node, resolved_params):
                    shell_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                    prompt_text = self._replace_global_placeholders_in_text(bashify_value(question), startup_global_values).replace('"', '\\"')
                    rendered_default = self._replace_global_placeholders_in_text(bashify_value(default_value), startup_global_values)
                    if rendered_default:
                        lines.append(f'read -r -p "{prompt_text} [{rendered_default}] " {shell_name}')
                        lines.append(f'if [ -z "${{{shell_name}}}" ]; then {shell_name}="{rendered_default}"; fi')
                    else:
                        lines.append(f'read -r -p "{prompt_text} " {shell_name}')
                    startup_global_values[var_name] = f"${{{shell_name}}}"
            if startup_global_values:
                lines.append("")

        def append_flow_body(lines, mode):
            temp_counter = 0
            node_outputs = {}
            temp_files = []
            input_node_index = 0
            global_values = dict(startup_global_values)

            for node in execution_order:
                lines.append(f"# --- Etape {node.execution_order}: {node.node_data['name']} ---")

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(bashify_value(param_value), global_values)
                    for param_name, param_value in resolved_params.items()
                }
                output_var_name = f"node_out_{node.execution_order or 0}_0"
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source'] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
                    lines.append(f'{output_var_name}=""')
                if node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    for var_name, _var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        shell_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        lines.append(f'{shell_name}=""')
                guard_conditions = self._build_bash_node_input_guard(input_files) if node.input_ports and not self._is_merge_node(node) else []
                if guard_conditions:
                    lines.append(f'if {" && ".join(guard_conditions)}; then')

                if node.node_data['name'] == 'Fichier Input':
                    if mode == "single_flow":
                        input_node_index += 1
                        node_outputs[self._make_output_key(node, 0)] = f'"${{resolved_inputs[{input_node_index - 1}]}}"'
                    else:
                        node_outputs[self._make_output_key(node, 0)] = '"$INPUT_FULL"'

                elif self._is_multi_file_node(node):
                    if mode != "single_flow":
                        lines.append('echo "ERREUR: Le noeud Multi-fichiers nécessite le mode flux unique"')
                        lines.append("flow_error=1")
                        lines.append("break")
                    else:
                        specs = self._get_multi_file_specs(node)
                        prefix = f"multi_{node.execution_order or 0}"
                        for spec_index, spec in enumerate(specs, start=1):
                            lines.append(f'{prefix}_{spec_index}=""')
                        for arg_index in range(input_node_index, input_node_index + len(specs)):
                            lines.append(f'candidate_file="${{resolved_inputs[{arg_index}]}}"')
                            lines.append('candidate_ext="${candidate_file##*.}"')
                            lines.append('if [ "$candidate_ext" = "$candidate_file" ]; then candidate_ext=""; else candidate_ext=".${candidate_ext,,}"; fi')
                            lines.append('candidate_matched=0')
                            for spec_index, spec in enumerate(specs, start=1):
                                var_name = f"{prefix}_{spec_index}"
                                for ext in spec["extensions"]:
                                    lines.append(
                                        f'if [ "$candidate_matched" -eq 0 ] && [ -z "${{{var_name}}}" ] && [ "$candidate_ext" = "{ext}" ]; then {var_name}="$candidate_file"; candidate_matched=1; fi'
                                    )
                            lines.append("")
                        for spec_index, spec in enumerate(specs, start=1):
                            var_name = f"{prefix}_{spec_index}"
                            lines.append(f'if [ -z "${{{var_name}}}" ]; then')
                            lines.append(f'    echo "ERREUR: Impossible d identifier le fichier attendu pour {spec["label"]}"')
                            lines.append('    flow_error=1')
                            lines.append('    break')
                            lines.append('fi')
                            node_outputs[self._make_output_key(node, spec_index - 1)] = f'"${{{var_name}}}"'
                        input_node_index += len(specs)

                elif self._is_switch_node(node):
                    specs = self._get_switch_specs(node, resolved_params)
                    switch_prefix = f"switch_{node.execution_order or 0}"
                    switch_input_var = f"{switch_prefix}_input"
                    switch_value_expr_var = f"{switch_prefix}_value_expr"
                    switch_value_var = f"{switch_prefix}_value"
                    switch_matched_var = f"{switch_prefix}_matched"
                    switch_input_value = self._strip_wrapping_quotes(input_files[0]) if input_files else '""'

                    lines.append(f'{switch_input_var}="{switch_input_value}"')
                    lines.append(f'{switch_value_expr_var}={quote_shell_string(rendered_params.get("Variable", "${INPUT_EXT}"))}')
                    lines.append(f'eval "{switch_value_var}=${switch_value_expr_var}"')
                    lines.append(f'{switch_matched_var}=0')

                    for spec_index, spec in enumerate(specs, start=1):
                        compare_expr_var = f"{switch_prefix}_cmp_expr_{spec_index}"
                        compare_var = f"{switch_prefix}_cmp_{spec_index}"
                        out_var = f"{switch_prefix}_out_{spec_index - 1}"
                        lines.append(f'{compare_expr_var}={quote_shell_string(rendered_params.get(f"Valeur {spec_index}", spec["value"]))}')
                        lines.append(f'eval "{compare_var}=${compare_expr_var}"')
                        lines.append(f'{out_var}=""')
                        lines.append(f'if [ "${{{switch_matched_var}}}" -eq 0 ] && {self._build_bash_switch_condition(switch_value_var, compare_var, spec["operator"])}; then')
                        lines.append(f'    {out_var}="${{{switch_input_var}}}"')
                        lines.append(f'    {switch_matched_var}=1')
                        lines.append('fi')
                        node_outputs[self._make_output_key(node, spec_index - 1)] = f'"${{{out_var}}}"'

                    default_out_var = f"{switch_prefix}_out_{len(specs)}"
                    lines.append(f'{default_out_var}=""')
                    lines.append(f'if [ "${{{switch_matched_var}}}" -eq 0 ]; then {default_out_var}="${{{switch_input_var}}}"; fi')
                    node_outputs[self._make_output_key(node, len(specs))] = f'"${{{default_out_var}}}"'

                elif self._is_merge_node(node):
                    node_outputs[self._make_output_key(node, 0)] = f'"${{{output_var_name}}}"'
                    for input_file in input_files:
                        runtime_var = self._extract_bash_runtime_var(input_file)
                        if runtime_var:
                            lines.append(f'if [ -z "${{{output_var_name}:-}}" ] && [ -n "${{{runtime_var}:-}}" ]; then {output_var_name}="${{{runtime_var}}}"; fi')
                        else:
                            lines.append(f'if [ -z "${{{output_var_name}:-}}" ]; then {output_var_name}={input_file}; fi')

                elif node.node_data['name'] == 'Fichier Source':
                    output_file = rendered_params.get('Chemin fichier', '')
                    if output_file:
                        lines.append(f'{output_var_name}={quote_shell_string(output_file)}')
                        node_outputs[self._make_output_key(node, 0)] = f'"${{{output_var_name}}}"'
                    else:
                        lines.append('echo "ERREUR: Aucun fichier source defini!"')
                        lines.append("flow_error=1")
                        lines.append("break")

                elif node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    input_values = [f"$(tr -d '\\r\\n' < {input_file})" for input_file in input_files]
                    for var_name, var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        shell_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        rendered_value = self._render_global_value_text(bashify_value(var_value), input_values, global_values)
                        rendered_value = rendered_value.replace('"', '\\"')
                        lines.append(f'{shell_name}="{rendered_value}"')
                        global_values[var_name] = f"${{{shell_name}}}"

                elif node.node_data['name'] == 'Fichier Destination':
                    if input_files:
                        nom = rendered_params.get('Nom fichier', bashify_value('%INPUT_NAME%'))
                        ext = rendered_params.get('Extension', '.mp4')
                        dossier = rendered_params.get('Dossier de sortie', '')

                        if dossier:
                            lines.append(f'dossier={quote_shell_string(dossier)}')
                            lines.append('eval "dossier_expanded=$dossier"')
                            lines.append('mkdir -p "$dossier_expanded"')
                            lines.append(f'nom_final={quote_shell_string(nom)}')
                            lines.append('eval "nom_final_expanded=$nom_final"')
                            lines.append(f'output_file="$dossier_expanded/$nom_final_expanded{ext}"')
                        else:
                            lines.append(f'nom_final={quote_shell_string(nom)}')
                            lines.append('eval "nom_final_expanded=$nom_final"')
                            lines.append(f'output_file="${{INPUT_PATH}}${{nom_final_expanded}}{ext}"')

                        clean_input = input_files[0]
                        lines.append(f'cp {clean_input} "$output_file"')
                        lines.append('if [ $? -ne 0 ]; then')
                        lines.append('    echo "ERREUR: Copie du fichier final echouee"')
                        lines.append('    flow_error=1')
                        lines.append('    break')
                        lines.append('fi')
                        lines.append('echo "  Output: $output_file"')

                else:
                    temp_counter += 1
                    temp_ext = self._get_node_output_extension(node, global_values)
                    output_file = f'${{TMPDIR:-/tmp}}/cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = f'"${{{output_var}}}"'
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'{output_var}="{output_file}"')

                    if template:
                        cmd = template
                        cmd = cmd.replace('{input}', input_files[0] if input_files else '""')

                        for input_index in range(1, max(len(input_files), len(node.input_ports))):
                            placeholder = f'{{input{input_index + 1}}}'
                            input_value = input_files[input_index] if input_index < len(input_files) else '""'
                            cmd = cmd.replace(placeholder, input_value)

                        cmd = cmd.replace('{output}', f'"{output_file}"')

                        for param_name, param_value in rendered_params.items():
                            cmd = cmd.replace(f'{{{param_name}}}', param_value)

                        cmd = self._replace_global_placeholders_in_text(cmd, global_values)

                        if command_name:
                            cmd = self._replace_leading_command(
                                cmd,
                                command_name,
                                quote_shell_string(command_path)
                            )

                        cmd = bashify_value(cmd).replace('""', '""')
                        lines.append(cmd)
                        lines.append('if [ $? -ne 0 ]; then')
                        lines.append(f'    echo "ERREUR: {node.node_data["name"]} a echoue"')
                        lines.append('    flow_error=1')
                        lines.append('    break')
                        lines.append('fi')
                    elif command_path:
                        cmd = quote_shell_string(command_path)
                        if input_files:
                            cmd += f' {input_files[0]}'
                        cmd += f' "{output_file}"'
                        lines.append(cmd)
                        lines.append('if [ $? -ne 0 ]; then')
                        lines.append(f'    echo "ERREUR: {node.node_data["name"]} a echoue"')
                        lines.append('    flow_error=1')
                        lines.append('    break')
                        lines.append('fi')

                if guard_conditions:
                    lines.append("fi")
                lines.append("")

            if temp_files:
                lines.append("# Nettoyage temporaires")
                for temp_file in temp_files:
                    lines.append(f'rm -f "{temp_file}"')
                lines.append("")

        sh_lines = []
        sh_lines.append("#!/usr/bin/env bash")
        sh_lines.append("set -u")
        sh_lines.append("")
        sh_lines.append("# ============================================================")
        sh_lines.append("# Script généré par CLI Node Editor")
        sh_lines.append("# Compatible Bash - Supporte plusieurs fichiers")
        sh_lines.append("# ============================================================")
        sh_lines.append("")
        sh_lines.append('if [ "$#" -eq 0 ]; then')
        sh_lines.append('    echo "ERREUR: Aucun fichier specifie"')
        sh_lines.append('    echo')
        sh_lines.append('    echo "Usage: $0 fichier1.ext [fichier2.ext] [...]"')
        sh_lines.append('    exit 1')
        sh_lines.append("fi")
        sh_lines.append("")
        sh_lines.append("TOTAL_FILES=$#")
        sh_lines.append("SUCCESS_COUNT=0")
        sh_lines.append("ERROR_COUNT=0")
        sh_lines.append('resolved_inputs=("$@")')
        sh_lines.append("")
        sh_lines.append('echo "============================================================"')
        if is_single_flow:
            sh_lines.append('echo "   Execution d un flux unique"')
            sh_lines.append('echo "   Fichiers en entree: $TOTAL_FILES"')
        else:
            sh_lines.append('echo "   Traitement de $TOTAL_FILES fichier(s)"')
        sh_lines.append('echo "============================================================"')
        sh_lines.append('echo')
        sh_lines.append("")
        append_startup_input_variables(sh_lines)

        if is_single_flow:
            if required_input_count > 1:
                sh_lines.append(f'if [ "$#" -lt {required_input_count} ]; then')
                sh_lines.append('    echo "ERREUR: Nombre de fichiers insuffisant pour les entrées du flux unique"')
                sh_lines.append('    exit 1')
                sh_lines.append("fi")
                sh_lines.append("")

            sh_lines.append('CURRENT_FILE="${resolved_inputs[0]}"')
            sh_lines.append('INPUT_NAME="$(basename "${CURRENT_FILE%.*}")"')
            sh_lines.append('INPUT_EXT="${CURRENT_FILE##*.}"')
            sh_lines.append('if [ "$INPUT_EXT" = "$CURRENT_FILE" ]; then INPUT_EXT=""; else INPUT_EXT=".$INPUT_EXT"; fi')
            sh_lines.append('INPUT_PATH="$(dirname "$CURRENT_FILE")/"')
            sh_lines.append('INPUT_FULL="$(realpath "$CURRENT_FILE" 2>/dev/null || printf "%s" "$CURRENT_FILE")"')
            sh_lines.append('flow_error=0')
            sh_lines.append("")
            append_flow_body(sh_lines, "single_flow")
            sh_lines.append('if [ "$flow_error" -ne 0 ]; then')
            sh_lines.append('    echo "  [ERREUR] Echec du flux"')
            sh_lines.append('    ERROR_COUNT=1')
            sh_lines.append("else")
            sh_lines.append('    echo "  [OK] Flux termine avec succes"')
            sh_lines.append('    SUCCESS_COUNT=1')
            sh_lines.append("fi")
        else:
            sh_lines.append('for CURRENT_FILE in "$@"; do')
            sh_lines.append('    INPUT_NAME="$(basename "${CURRENT_FILE%.*}")"')
            sh_lines.append('    INPUT_EXT="${CURRENT_FILE##*.}"')
            sh_lines.append('    if [ "$INPUT_EXT" = "$CURRENT_FILE" ]; then INPUT_EXT=""; else INPUT_EXT=".$INPUT_EXT"; fi')
            sh_lines.append('    INPUT_PATH="$(dirname "$CURRENT_FILE")/"')
            sh_lines.append('    INPUT_FULL="$(realpath "$CURRENT_FILE" 2>/dev/null || printf "%s" "$CURRENT_FILE")"')
            sh_lines.append('    flow_error=0')
            sh_lines.append('    echo "------------------------------------------------------------"')
            sh_lines.append('    echo "Traitement: ${INPUT_NAME}${INPUT_EXT}"')
            sh_lines.append('    echo "------------------------------------------------------------"')
            sh_lines.append('    echo')
            append_flow_body(sh_lines, "per_file")
            sh_lines.append('    if [ "$flow_error" -ne 0 ]; then')
            sh_lines.append('        echo "  [ERREUR] Echec du traitement"')
            sh_lines.append('        ERROR_COUNT=$((ERROR_COUNT + 1))')
            sh_lines.append("    else")
            sh_lines.append('        echo "  [OK] Termine avec succes"')
            sh_lines.append('        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))')
            sh_lines.append("    fi")
            sh_lines.append('    echo')
            sh_lines.append("done")

        sh_lines.append("")
        sh_lines.append('echo "============================================================"')
        sh_lines.append('echo "   RESUME"')
        sh_lines.append('echo "============================================================"')
        sh_lines.append('echo "  Total:   $TOTAL_FILES fichier(s)"')
        sh_lines.append('echo "  Succes:  $SUCCESS_COUNT"')
        sh_lines.append('echo "  Erreurs: $ERROR_COUNT"')
        sh_lines.append('echo "============================================================"')
        sh_lines.append("")
        sh_lines.append('if [ "$ERROR_COUNT" -gt 0 ]; then')
        sh_lines.append('    echo "Certains fichiers ont echoue."')
        sh_lines.append('    exit 1')
        sh_lines.append("fi")
        sh_lines.append("")
        sh_lines.append('echo "Tous les fichiers ont ete traites avec succes!"')
        sh_lines.append("exit 0")

        return "\n".join(sh_lines), warnings

    def generate_powershell_preview_content(self):
        """Construit le contenu PowerShell correspondant au workflow courant."""
        nodes_list, execution_order = self._get_execution_nodes()

        warnings = []
        if len(execution_order) != len(nodes_list):
            warnings.append(
                "ATTENTION: certains noeuds n'ont pas d'ordre d'exécution défini. "
                "Vérifiez les connexions du workflow."
            )

        required_input_count = self._get_required_input_count(execution_order)
        is_single_flow = self.workflow_mode == "single_flow"
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        def ps_quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        def psify_value(value):
            value = str(value)
            value = value.replace('%INPUT_NAME%', '$INPUT_NAME')
            value = value.replace('%INPUT_PATH%', '$INPUT_PATH')
            value = value.replace('%INPUT_EXT%', '$INPUT_EXT')
            return value

        startup_global_values = {}

        def append_startup_input_variables(lines):
            for node in execution_order:
                resolved_params = self.get_resolved_node_parameters(node)
                for var_name, question, default_value, _slot_index in self._get_input_variable_entries(node, resolved_params):
                    ps_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                    prompt_text = self._replace_global_placeholders_in_text(psify_value(question), startup_global_values).replace("`", "``").replace('"', '`"')
                    rendered_default = self._replace_global_placeholders_in_text(psify_value(default_value), startup_global_values)
                    rendered_default = rendered_default.replace("`", "``").replace('"', '`"')
                    if rendered_default:
                        lines.append(f'${ps_name} = Read-Host "{prompt_text} [{rendered_default}]"')
                        lines.append(f'if ([string]::IsNullOrWhiteSpace(${ps_name})) {{ ${ps_name} = "{rendered_default}" }}')
                    else:
                        lines.append(f'${ps_name} = Read-Host "{prompt_text}"')
                    startup_global_values[var_name] = f'${ps_name}'
            if startup_global_values:
                lines.append("")

        def append_flow_body(lines, mode):
            temp_counter = 0
            node_outputs = {}
            temp_files = []
            input_node_index = 0
            global_values = dict(startup_global_values)

            for node in execution_order:
                lines.append(f"# --- Etape {node.execution_order}: {node.node_data['name']} ---")

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(psify_value(param_value), global_values)
                    for param_name, param_value in resolved_params.items()
                }
                output_var_name = f'$NodeOut{node.execution_order or 0}_0'
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source'] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
                    lines.append(f'{output_var_name} = $null')
                if node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    for var_name, _var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        ps_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        lines.append(f'${ps_name} = $null')
                guard_conditions = self._build_powershell_node_input_guard(input_files) if node.input_ports and not self._is_merge_node(node) else []
                if guard_conditions:
                    lines.append(f'if ({" -and ".join(guard_conditions)}) {{')

                if node.node_data['name'] == 'Fichier Input':
                    if mode == "single_flow":
                        input_node_index += 1
                        node_outputs[self._make_output_key(node, 0)] = f'$resolvedInputs[{input_node_index - 1}]'
                    else:
                        node_outputs[self._make_output_key(node, 0)] = '$INPUT_FULL'

                elif self._is_multi_file_node(node):
                    if mode != "single_flow":
                        lines.append('Write-Host "ERREUR: Le noeud Multi-fichiers nécessite le mode flux unique"')
                        lines.append('$flowError = $true')
                        lines.append('break')
                    else:
                        specs = self._get_multi_file_specs(node)
                        prefix = f"Multi{node.execution_order or 0}"
                        for spec_index, spec in enumerate(specs, start=1):
                            lines.append(f'${prefix}_{spec_index} = $null')
                        for arg_index in range(input_node_index, input_node_index + len(specs)):
                            lines.append(f'$candidateFile = $resolvedInputs[{arg_index}]')
                            lines.append('$candidateExt = [System.IO.Path]::GetExtension($candidateFile).ToLowerInvariant()')
                            lines.append('$candidateMatched = $false')
                            for spec_index, spec in enumerate(specs, start=1):
                                var_name = f"${prefix}_{spec_index}"
                                for ext in spec["extensions"]:
                                    lines.append(
                                        f'if (-not $candidateMatched -and -not {var_name} -and $candidateExt -eq {ps_quote(ext)}) {{ {var_name} = $candidateFile; $candidateMatched = $true }}'
                                    )
                            lines.append("")
                        for spec_index, spec in enumerate(specs, start=1):
                            var_name = f"${prefix}_{spec_index}"
                            lines.append(f'if (-not {var_name}) {{')
                            lines.append(f'    Write-Host "ERREUR: Impossible d identifier le fichier attendu pour {spec["label"]}"')
                            lines.append('    $flowError = $true')
                            lines.append('    break')
                            lines.append('}')
                            node_outputs[self._make_output_key(node, spec_index - 1)] = var_name
                        input_node_index += len(specs)

                elif self._is_switch_node(node):
                    specs = self._get_switch_specs(node, resolved_params)
                    switch_prefix = f"Switch{node.execution_order or 0}"
                    switch_input_var = f"${switch_prefix}Input"
                    switch_value_expr_var = f"${switch_prefix}ValueExpr"
                    switch_value_var = f"${switch_prefix}Value"
                    switch_matched_var = f"${switch_prefix}Matched"
                    switch_input_value = self._strip_wrapping_quotes(input_files[0]) if input_files else '$null'

                    lines.append(f'{switch_input_var} = {switch_input_value}')
                    lines.append(f'{switch_value_expr_var} = {ps_quote(rendered_params.get("Variable", "$INPUT_EXT"))}')
                    lines.append(f'{switch_value_var} = $ExecutionContext.InvokeCommand.ExpandString({switch_value_expr_var})')
                    lines.append(f'{switch_matched_var} = $false')

                    for spec_index, spec in enumerate(specs, start=1):
                        compare_expr_var = f"${switch_prefix}CompareExpr{spec_index}"
                        compare_var = f"${switch_prefix}Compare{spec_index}"
                        out_var = f"${switch_prefix}Out{spec_index - 1}"
                        lines.append(f'{compare_expr_var} = {ps_quote(rendered_params.get(f"Valeur {spec_index}", spec["value"]))}')
                        lines.append(f'{compare_var} = $ExecutionContext.InvokeCommand.ExpandString({compare_expr_var})')
                        lines.append(f'{out_var} = $null')
                        lines.append(f'if (-not {switch_matched_var} -and {self._build_powershell_switch_condition(switch_value_var, compare_var, spec["operator"])}) {{')
                        lines.append(f'    {out_var} = {switch_input_var}')
                        lines.append(f'    {switch_matched_var} = $true')
                        lines.append('}')
                        node_outputs[self._make_output_key(node, spec_index - 1)] = out_var

                    default_out_var = f"${switch_prefix}Out{len(specs)}"
                    lines.append(f'{default_out_var} = $null')
                    lines.append(f'if (-not {switch_matched_var}) {{ {default_out_var} = {switch_input_var} }}')
                    node_outputs[self._make_output_key(node, len(specs))] = default_out_var

                elif self._is_merge_node(node):
                    node_outputs[self._make_output_key(node, 0)] = output_var_name
                    for input_file in input_files:
                        runtime_var = self._extract_powershell_runtime_var(input_file)
                        if runtime_var:
                            lines.append(f'if (-not {output_var_name} -and -not [string]::IsNullOrWhiteSpace({runtime_var})) {{ {output_var_name} = {runtime_var} }}')
                        else:
                            lines.append(f'if (-not {output_var_name}) {{ {output_var_name} = {input_file} }}')

                elif node.node_data['name'] == 'Fichier Source':
                    output_file = rendered_params.get('Chemin fichier', '')
                    if output_file:
                        lines.append(f'{output_var_name} = {ps_quote(output_file)}')
                        node_outputs[self._make_output_key(node, 0)] = output_var_name
                    else:
                        lines.append('Write-Host "ERREUR: Aucun fichier source defini!"')
                        lines.append('$flowError = $true')
                        lines.append('break')

                elif node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    input_values = [f"$((Get-Content -LiteralPath {input_file} -Raw -ErrorAction SilentlyContinue).Trim())" for input_file in input_files]
                    for var_name, var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        ps_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        rendered_value = self._render_global_value_text(psify_value(var_value), input_values, global_values)
                        rendered_value = rendered_value.replace("`", "``").replace('"', '`"')
                        lines.append(f'${ps_name} = "{rendered_value}"')
                        global_values[var_name] = f'${ps_name}'

                elif node.node_data['name'] == 'Fichier Destination':
                    if input_files:
                        nom = rendered_params.get('Nom fichier', psify_value('%INPUT_NAME%'))
                        ext = rendered_params.get('Extension', '.mp4')
                        dossier = rendered_params.get('Dossier de sortie', '')

                        if dossier:
                            lines.append(f"$dossier = {ps_quote(dossier)}")
                            lines.append('$ExecutionContext.InvokeCommand.ExpandString($dossier) | Out-Null')
                            lines.append('$dossierExpanded = $ExecutionContext.InvokeCommand.ExpandString($dossier)')
                            lines.append('New-Item -ItemType Directory -Force -Path $dossierExpanded | Out-Null')
                            lines.append(f"$nomFinal = {ps_quote(nom)}")
                            lines.append('$nomFinalExpanded = $ExecutionContext.InvokeCommand.ExpandString($nomFinal)')
                            lines.append(f'$outputFile = Join-Path $dossierExpanded ($nomFinalExpanded + {ps_quote(ext)})')
                        else:
                            lines.append(f"$nomFinal = {ps_quote(nom)}")
                            lines.append('$nomFinalExpanded = $ExecutionContext.InvokeCommand.ExpandString($nomFinal)')
                            lines.append(f'$outputFile = Join-Path $INPUT_PATH ($nomFinalExpanded + {ps_quote(ext)})')

                        clean_input = input_files[0]
                        lines.append(f'Copy-Item -LiteralPath {clean_input} -Destination $outputFile -Force')
                        lines.append('if (-not $?) {')
                        lines.append('    Write-Host "ERREUR: Copie du fichier final echouee"')
                        lines.append('    $flowError = $true')
                        lines.append('    break')
                        lines.append('}')
                        lines.append('Write-Host "  Output: $outputFile"')

                else:
                    temp_counter += 1
                    temp_ext = self._get_node_output_extension(node, global_values)
                    output_file = f'$env:TEMP\\cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = output_var
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'{output_var} = $ExecutionContext.InvokeCommand.ExpandString({ps_quote(output_file)})')

                    if template:
                        cmd = template
                        cmd = cmd.replace('{input}', input_files[0] if input_files else '""')

                        for input_index in range(1, max(len(input_files), len(node.input_ports))):
                            placeholder = f'{{input{input_index + 1}}}'
                            input_value = input_files[input_index] if input_index < len(input_files) else '""'
                            cmd = cmd.replace(placeholder, input_value)

                        cmd = cmd.replace('{output}', output_file)

                        for param_name, param_value in rendered_params.items():
                            cmd = cmd.replace(f'{{{param_name}}}', param_value)

                        cmd = self._replace_global_placeholders_in_text(cmd, global_values)

                        if command_name:
                            cmd = self._replace_leading_command(
                                cmd,
                                command_name,
                                f'& {ps_quote(command_path)}'
                            )

                        lines.append(psify_value(cmd))
                        lines.append('if (-not $?) {')
                        lines.append(f'    Write-Host "ERREUR: {node.node_data["name"]} a echoue"')
                        lines.append('    $flowError = $true')
                        lines.append('    break')
                        lines.append('}')
                    elif command_path:
                        cmd = f'& {ps_quote(command_path)}'
                        if input_files:
                            cmd += f' {input_files[0]}'
                        cmd += f' {output_file}'
                        lines.append(cmd)
                        lines.append('if (-not $?) {')
                        lines.append(f'    Write-Host "ERREUR: {node.node_data["name"]} a echoue"')
                        lines.append('    $flowError = $true')
                        lines.append('    break')
                        lines.append('}')

                if guard_conditions:
                    lines.append('}')
                lines.append("")

            if temp_files:
                lines.append("# Nettoyage temporaires")
                for temp_file in temp_files:
                    lines.append(f'Remove-Item -LiteralPath {temp_file} -Force -ErrorAction SilentlyContinue')
                lines.append("")

        ps_lines = []
        ps_lines.append("param(")
        ps_lines.append("    [Parameter(ValueFromRemainingArguments = $true)]")
        ps_lines.append("    [string[]]$InputFiles")
        ps_lines.append(")")
        ps_lines.append("")
        ps_lines.append("$ErrorActionPreference = 'Continue'")
        ps_lines.append("")
        ps_lines.append("# ============================================================")
        ps_lines.append("# Script généré par CLI Node Editor")
        ps_lines.append("# Compatible PowerShell - Supporte plusieurs fichiers")
        ps_lines.append("# ============================================================")
        ps_lines.append("")
        ps_lines.append("if (-not $InputFiles -or $InputFiles.Count -eq 0) {")
        ps_lines.append('    Write-Host "ERREUR: Aucun fichier specifie"')
        ps_lines.append('    Write-Host ""')
        ps_lines.append('    Write-Host "Usage: .\\workflow.ps1 fichier1.ext [fichier2.ext] [...]"')
        ps_lines.append("    exit 1")
        ps_lines.append("}")
        ps_lines.append("")
        ps_lines.append("$TOTAL_FILES = $InputFiles.Count")
        ps_lines.append("$SUCCESS_COUNT = 0")
        ps_lines.append("$ERROR_COUNT = 0")
        ps_lines.append("$resolvedInputs = @($InputFiles | ForEach-Object { (Resolve-Path $_ -ErrorAction SilentlyContinue)?.Path ?? $_ })")
        ps_lines.append("")
        ps_lines.append('Write-Host "============================================================"')
        if is_single_flow:
            ps_lines.append('Write-Host "   Execution d''un flux unique"')
            ps_lines.append('Write-Host "   Fichiers en entree: $TOTAL_FILES"')
        else:
            ps_lines.append('Write-Host "   Traitement de $TOTAL_FILES fichier(s)"')
        ps_lines.append('Write-Host "============================================================"')
        ps_lines.append('Write-Host ""')
        ps_lines.append("")
        append_startup_input_variables(ps_lines)

        if is_single_flow:
            if required_input_count > 1:
                ps_lines.append(f"if ($InputFiles.Count -lt {required_input_count}) {{")
                ps_lines.append('    Write-Host "ERREUR: Nombre de fichiers insuffisant pour les entrées du flux unique"')
                ps_lines.append("    exit 1")
                ps_lines.append("}")
                ps_lines.append("")

            ps_lines.append("$CURRENT_FILE = $resolvedInputs[0]")
            ps_lines.append("$INPUT_NAME = [System.IO.Path]::GetFileNameWithoutExtension($CURRENT_FILE)")
            ps_lines.append("$INPUT_EXT = [System.IO.Path]::GetExtension($CURRENT_FILE)")
            ps_lines.append("$INPUT_PATH = [System.IO.Path]::GetDirectoryName($CURRENT_FILE)")
            ps_lines.append('if (-not [string]::IsNullOrEmpty($INPUT_PATH)) { $INPUT_PATH += [System.IO.Path]::DirectorySeparatorChar }')
            ps_lines.append("$INPUT_FULL = $CURRENT_FILE")
            ps_lines.append("$flowError = $false")
            ps_lines.append("")
            append_flow_body(ps_lines, "single_flow")
            ps_lines.append("if ($flowError) {")
            ps_lines.append('    Write-Host "  [ERREUR] Echec du flux"')
            ps_lines.append("    $ERROR_COUNT = 1")
            ps_lines.append("} else {")
            ps_lines.append('    Write-Host "  [OK] Flux termine avec succes"')
            ps_lines.append("    $SUCCESS_COUNT = 1")
            ps_lines.append("}")
        else:
            ps_lines.append("foreach ($CURRENT_FILE in $resolvedInputs) {")
            ps_lines.append("    $INPUT_NAME = [System.IO.Path]::GetFileNameWithoutExtension($CURRENT_FILE)")
            ps_lines.append("    $INPUT_EXT = [System.IO.Path]::GetExtension($CURRENT_FILE)")
            ps_lines.append("    $INPUT_PATH = [System.IO.Path]::GetDirectoryName($CURRENT_FILE)")
            ps_lines.append('    if (-not [string]::IsNullOrEmpty($INPUT_PATH)) { $INPUT_PATH += [System.IO.Path]::DirectorySeparatorChar }')
            ps_lines.append("    $INPUT_FULL = $CURRENT_FILE")
            ps_lines.append("    $flowError = $false")
            ps_lines.append('    Write-Host "------------------------------------------------------------"')
            ps_lines.append('    Write-Host "Traitement: $INPUT_NAME$INPUT_EXT"')
            ps_lines.append('    Write-Host "------------------------------------------------------------"')
            ps_lines.append('    Write-Host ""')
            append_flow_body(ps_lines, "per_file")
            ps_lines.append("    if ($flowError) {")
            ps_lines.append('        Write-Host "  [ERREUR] Echec du traitement"')
            ps_lines.append("        $ERROR_COUNT += 1")
            ps_lines.append("    } else {")
            ps_lines.append('        Write-Host "  [OK] Termine avec succes"')
            ps_lines.append("        $SUCCESS_COUNT += 1")
            ps_lines.append("    }")
            ps_lines.append('    Write-Host ""')
            ps_lines.append("}")

        ps_lines.append("")
        ps_lines.append('Write-Host "============================================================"')
        ps_lines.append('Write-Host "   RESUME"')
        ps_lines.append('Write-Host "============================================================"')
        ps_lines.append('Write-Host "  Total:   $TOTAL_FILES fichier(s)"')
        ps_lines.append('Write-Host "  Succes:  $SUCCESS_COUNT"')
        ps_lines.append('Write-Host "  Erreurs: $ERROR_COUNT"')
        ps_lines.append('Write-Host "============================================================"')
        ps_lines.append("")
        ps_lines.append("if ($ERROR_COUNT -gt 0) {")
        ps_lines.append('    Write-Host "Certains fichiers ont echoue."')
        ps_lines.append("    exit 1")
        ps_lines.append("}")
        ps_lines.append("")
        ps_lines.append('Write-Host "Tous les fichiers ont ete traites avec succes!"')
        ps_lines.append("exit 0")

        return "\n".join(ps_lines), warnings

    def refresh_bat_preview(self):
        """Met à jour la zone de prévisualisation du script."""
        try:
            bat_content, warnings = self._get_script_preview_content()
            preview_parts = []
            if warnings:
                preview_parts.append(":: AVERTISSEMENTS ::")
                preview_parts.extend(f"- {warning}" for warning in warnings)
                preview_parts.append("")
            preview_parts.append(bat_content)
            new_text = "\n".join(preview_parts)
            if self.preview_text.toPlainText() == new_text:
                self.preview_dirty = False
                self.update_preview_status()
                return

            v_scroll = self.preview_text.verticalScrollBar().value()
            h_scroll = self.preview_text.horizontalScrollBar().value()
            self.preview_text.setUpdatesEnabled(False)
            self.preview_text.setPlainText(new_text)
            self.preview_text.verticalScrollBar().setValue(v_scroll)
            self.preview_text.horizontalScrollBar().setValue(h_scroll)
            self.preview_text.setUpdatesEnabled(True)
            self.preview_dirty = False
            self.update_preview_status()
        except Exception as e:
            error_text = (
                "Impossible de générer l'aperçu du script.\n\n"
                f"{type(e).__name__}: {e}"
            )
            if self.preview_text.toPlainText() != error_text:
                self.preview_text.setPlainText(error_text)
            self.preview_dirty = True
            self.update_preview_status()
    
    def export_to_bat(self):
        """Exporte le workflow en script Batch ou Bash selon le mode choisi."""
        export_config = {
            "batch": ("workflow.bat", "Batch Files (*.bat)", "Exporter en BAT"),
            "bash": ("workflow.sh", "Shell Scripts (*.sh)", "Exporter en Bash"),
            "powershell": ("workflow.ps1", "PowerShell Scripts (*.ps1)", "Exporter en PowerShell")
        }
        default_name, file_filter, title = export_config.get(
            self.script_type,
            ("workflow.bat", "Batch Files (*.bat)", "Exporter le script")
        )
        filename, _ = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not filename:
            return
        
        try:
            if self.preview_dirty:
                self.generate_workflow_preview()
            bat_content, warnings = self._get_script_preview_content()
            if warnings:
                QMessageBox.warning(self, "Attention", "\n".join(warnings))
            
            # Écrire le fichier
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            
            if self.script_type == "batch":
                info_text = (
                    f"Fichier BAT créé: {filename}\n\n"
                    "Utilisation:\n"
                    "• Placez ce fichier dans votre dossier SendTo\n"
                    "  (Win+R → shell:sendto)\n\n"
                    "• Clic droit sur un ou plusieurs fichiers\n"
                    "  → Envoyer vers → Votre script\n\n"
                    "• Ou glissez-déposez des fichiers sur le .bat\n\n"
                    "Variables disponibles dans vos nœuds:\n"
                    "• %INPUT_NAME% → Nom du fichier (sans extension)\n"
                    "• %INPUT_PATH% → Dossier du fichier source"
                )
            elif self.script_type == "bash":
                info_text = (
                    f"Script Bash créé: {filename}\n\n"
                    "Utilisation:\n"
                    "• Rendez-le exécutable avec: chmod +x votre_script.sh\n"
                    "• Lancez-le avec un ou plusieurs fichiers en argument\n\n"
                    "Variables disponibles dans vos nœuds:\n"
                    "• %INPUT_NAME% sera converti en ${INPUT_NAME}\n"
                    "• %INPUT_PATH% sera converti en ${INPUT_PATH}"
                )
            else:
                info_text = (
                    f"Script PowerShell créé: {filename}\n\n"
                    "Utilisation:\n"
                    "• Lancez-le avec: powershell -ExecutionPolicy Bypass -File votre_script.ps1 ...\n"
                    "• Ou depuis PowerShell: .\\votre_script.ps1 fichier1 fichier2\n\n"
                    "Variables disponibles dans vos nœuds:\n"
                    "• %INPUT_NAME% sera converti en $INPUT_NAME\n"
                    "• %INPUT_PATH% sera converti en $INPUT_PATH"
                )

            QMessageBox.information(self, "Export réussi", info_text)
        
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export:\n{str(e)}\n\n{traceback.format_exc()}")
    
    def clear_canvas(self):
        """Efface le canvas"""
        reply = QMessageBox.question(self, "Confirmation", "Effacer tout le canvas ?")
        if reply == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.populate_default_canvas()
            self.schedule_bat_preview_refresh()
    
    def import_library(self):
        """Importe une bibliothèque"""
        filename, _ = QFileDialog.getOpenFileName(self, "Importer bibliothèque", 
                                                   "", "JSON Files (*.json)")
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                imported_nodes = json.load(f)
            
            for node_name, node_data in imported_nodes.items():
                self.library.add_node(node_data)
            
            self.refresh_library_list()
            QMessageBox.information(self, "Succès", f"{len(imported_nodes)} noeuds importés")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur d'importation:\n{str(e)}")
    
    def export_library(self):
        """Exporte la bibliothèque"""
        filename, _ = QFileDialog.getSaveFileName(self, "Exporter bibliothèque", 
                                                   "my_library.json", "JSON Files (*.json)")
        if not filename:
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.library.get_all_nodes(), f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, "Succès", f"Bibliothèque exportée:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur d'export:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    
    # Style global
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
