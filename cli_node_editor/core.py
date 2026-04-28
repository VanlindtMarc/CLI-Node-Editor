"""Core data structures and helpers for CLI Node Editor."""

import json
import os
from pathlib import Path

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


def ensure_file_extension(path, extension):
    """Ajoute une extension par défaut si le chemin n'en possède pas."""
    path = str(path or "").strip()
    if not path:
        return path
    if Path(path).suffix:
        return path
    return path + extension


def replace_indexed_placeholders(text, values, transform=None, suffix=""):
    """Remplace {input}/{input2}... et leurs variantes suffixées."""
    text = str(text or "")
    if "{input" not in text:
        return text

    transform = transform or (lambda v: v)
    default_value = transform("")
    text = text.replace(f"{{input{suffix}}}", transform(values[0]) if values else default_value)

    upper_bound = max(len(values), 10)
    for input_index in range(1, upper_bound):
        placeholder = f"{{input{input_index + 1}{suffix}}}"
        input_value = transform(values[input_index]) if input_index < len(values) else default_value
        text = text.replace(placeholder, input_value)

    return text


SYSTEM_SOURCE_NODE_NAMES = ["Fichier Input", "Fichier Source", "Fichier Destination", "Multi-fichiers", "Liste"]
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
LIST_INPUT_NODE_NAME = "Liste"
DEBUG_NODE_NAME = "Debug"


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


def build_debug_parameters():
    """Construit les parametres du noeud Debug."""
    return [
        {"name": "Mode sortie", "type": "choice", "default": "Console + fichier", "choices": ["Console", "Fichier", "Console + fichier"]},
        {"name": "Message", "type": "text", "default": "Point de debug"},
        {"name": "Nom fichier log", "type": "text", "default": "workflow_debug.log"},
        {"name": "Dossier log", "type": "text", "default": ""}
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
            self.nodes = {
                node_name: self._normalize_node_data(node_data)
                for node_name, node_data in self._get_default_nodes().items()
            }
            self.save()
    
    def save(self):
        """Sauvegarde la bibliothèque dans le fichier JSON"""
        try:
            with open(self.library_file, 'w', encoding='utf-8') as f:
                json.dump(self.nodes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur de sauvegarde de la bibliothèque: {e}")
    
    def add_node(self, node_data, save=True):
        """Ajoute un noeud à la bibliothèque"""
        normalized = self._normalize_node_data(node_data)
        node_id = normalized['name']
        self.nodes[node_id] = normalized
        if save:
            self.save()

    def add_nodes(self, nodes_data, save=True):
        """Ajoute plusieurs noeuds en une seule opération disque."""
        changed = False
        for node_data in nodes_data:
            normalized = self._normalize_node_data(node_data)
            self.nodes[normalized['name']] = normalized
            changed = True
        if changed and save:
            self.save()

    def update_node(self, old_name, node_data, save=True):
        """Met à jour un noeud existant (avec possibilité de renommer)"""
        normalized = self._normalize_node_data(node_data)
        if old_name in self.nodes and old_name != normalized['name']:
            del self.nodes[old_name]
        self.nodes[normalized['name']] = normalized
        if save:
            self.save()

    def remove_node(self, node_id, save=True):
        """Supprime un noeud de la bibliothèque"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            if save:
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
            LIST_INPUT_NODE_NAME: {
                "name": LIST_INPUT_NODE_NAME,
                "category": "Fichier",
                "command": "",
                "description": "Point d'entrée depuis un fichier texte. Chaque ligne non vide du fichier est traitée comme une entrée du flux.",
                "color": "#FFCC99",
                "verified": True,
                "inputs": [],
                "outputs": ["file"],
                "parameters": [],
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
            },
            DEBUG_NODE_NAME: {
                "name": DEBUG_NODE_NAME,
                "category": "SystÃ¨me",
                "command": "",
                "description": "Affiche et/ou enregistre des informations de debug puis laisse passer le flux inchangÃ©.",
                "color": "#CDB4DB",
                "verified": True,
                "inputs": ["file"],
                "outputs": ["file"],
                "parameters": build_debug_parameters(),
                "template": "",
                "output_extension": ""
            }
        }

    def _normalize_node_data(self, node_data):
        """Uniformise le schéma des noeuds et migre l'ancien champ d'extension implicite."""
        normalized = dict(node_data)
        if normalized.get('name') == DEBUG_NODE_NAME:
            normalized['category'] = 'SystÃ¨me'
            normalized['command'] = ''
            normalized['description'] = (
                "Affiche et/ou enregistre des informations de debug puis "
                "laisse passer le flux inchangÃ©."
            )
            normalized['color'] = '#CDB4DB'
            normalized['inputs'] = ['file']
            normalized['outputs'] = ['file']
            normalized['parameters'] = build_debug_parameters()
            normalized['template'] = ''
            normalized['output_extension'] = ''
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
        elif normalized.get('name') == DEBUG_NODE_NAME:
            normalized['category'] = 'SystÃ¨me'
            normalized['subcategory'] = 'Debug'
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
        elif normalized.get('name') == LIST_INPUT_NODE_NAME:
            normalized['category'] = 'Fichier'
            normalized['subcategory'] = 'Entrées / Sorties'
            normalized['verified'] = True
            normalized['command'] = ''
            normalized['description'] = (
                "Point d'entrée depuis un fichier texte. Chaque ligne non vide "
                "du fichier est traitée comme une entrée du flux."
            )
            normalized['color'] = '#FFCC99'
            normalized['inputs'] = []
            normalized['outputs'] = ['file']
            normalized['parameters'] = []
            normalized['template'] = ''
            normalized['output_extension'] = ''
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


def repair_mojibake(value):
    """Corrige quelques sequences d'encodage courantes."""
    text = str(value or "")
    replacements = {
        "SystÃ¨me": "Système",
        "SystÃƒÂ¨me": "Système",
        "inchangÃ©": "inchangé",
        "inchangÃƒÂ©": "inchangé",
        "premiÃ¨re": "première",
        "DÃ©faut": "Défaut",
        "ContrÃ´le": "Contrôle",
        "entrÃ©e": "entrée",
        "entrÃ©es": "entrées",
        "rÃ©ponse": "réponse",
        "rÃ©ponses": "réponses",
        "embarquÃ©": "embarqué",
        "schÃ©ma": "schéma",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def get_display_node_name(node_data):
    """Retourne un nom court pour l'affichage en évitant les préfixes redondants."""
    explicit_display_name = repair_mojibake(node_data.get('display_name', '')).strip()
    if explicit_display_name:
        return explicit_display_name

    name = repair_mojibake(node_data.get('name', '')).strip()
    category = repair_mojibake(node_data.get('category', '')).strip()
    if not name or not category:
        return name

    prefix = f"{category} - "
    if name.lower().startswith(prefix.lower()):
        return name[len(prefix):].strip()

    return name


def get_display_category(node_data):
    """Retourne la catégorie enrichie avec la sous-catégorie si disponible."""
    category = repair_mojibake(node_data.get('category', '')).strip() or 'Custom'
    subcategory = repair_mojibake(node_data.get('subcategory', '')).strip()
    return f"{category} / {subcategory}" if subcategory else category


