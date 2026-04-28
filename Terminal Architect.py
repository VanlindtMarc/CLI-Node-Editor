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
import shutil
import tempfile
import traceback
import copy
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, QProcess, QProcessEnvironment


from cli_node_editor.core import (
    SYSTEM_SOURCE_NODE_NAMES,
    ensure_file_extension,
    get_display_category,
    get_display_node_name,
    normalize_output_extension,
    DependencyManager,
    NodeLibrary,
)
from cli_node_editor.highlighter import BatchSyntaxHighlighter
from cli_node_editor.script_generation import ScriptGenerationMixin

from cli_node_editor.dialogs import DependencyConfigDialog, NodeCreatorDialog
from cli_node_editor.graphics import Connection, Node, NodeEditorScene, NodeEditorView



class MainWindow(ScriptGenerationMixin, QMainWindow):
    """Fenêtre principale"""

    node_class = Node
    connection_class = Connection
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Terminal Architect")
        self.setGeometry(100, 100, 1400, 800)
        
        self.dep_manager = DependencyManager()
        self.library = NodeLibrary()
        self.workflow_mode = "per_file"
        self.script_type = "batch"
        self.debug_enabled = False
        self.debug_pause_enabled = True
        self.library_filter_mode = "all"
        self.preview_dirty = True
        self.panel_expanded_sizes = {"left": 320, "right": 380}
        self.node_index_by_uid = {}
        self._resolved_params_cache = {}
        self.execution_process = None
        self.execution_output_buffer = ""
        self.execution_temp_script = None
        self.execution_temp_root = None
        self.current_running_node_uid = None
        self.recent_workflows_file = os.path.join(os.getcwd(), "recent_workflows.json")
        self.help_file = os.path.join(os.getcwd(), "AIDE.md")
        self.recent_workflows = []
        
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
        self.scene.changed.connect(self.schedule_bat_preview_refresh)
        
        self.create_menus()
        self.load_recent_workflows()
        self.populate_default_canvas()
        self.update_preview_highlighter()
        self.generate_workflow_preview()
        
        self.statusBar().showMessage("Double-cliquez sur un noeud de la bibliothèque pour l'ajouter au canvas")

    def invalidate_runtime_caches(self):
        """Invalide les caches dépendants du contenu du workflow."""
        self.node_index_by_uid = {}
        self._resolved_params_cache = {}

    def rebuild_node_index(self):
        """Reconstruit l'index UID -> noeud à partir de la scène."""
        self.node_index_by_uid = {
            node.node_uid: node
            for node in self.scene.items()
            if isinstance(node, Node)
        }
        return self.node_index_by_uid
    
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

        self.debug_checkbox = QCheckBox("Mode debug")
        self.debug_checkbox.setChecked(self.debug_enabled)
        self.debug_checkbox.setToolTip(
            "Ajoute des traces détaillées dans le script exporté pour suivre"
            " l'exécution du workflow."
        )
        self.debug_checkbox.toggled.connect(self.on_debug_mode_changed)
        layout.addWidget(self.debug_checkbox)

        self.debug_pause_checkbox = QCheckBox("Pause avant chaque action")
        self.debug_pause_checkbox.setChecked(self.debug_pause_enabled)
        self.debug_pause_checkbox.setToolTip(
            "Insère une pause avant chaque noeud pour avancer pas à pas dans"
            " le flux."
        )
        self.debug_pause_checkbox.setEnabled(self.debug_enabled)
        self.debug_pause_checkbox.toggled.connect(self.on_debug_pause_changed)
        layout.addWidget(self.debug_pause_checkbox)

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
        self.run_workflow_btn = QPushButton("Lancer")
        self.run_workflow_btn.clicked.connect(self.run_workflow_from_ui)
        preview_toolbar.addWidget(self.run_workflow_btn)
        self.stop_workflow_btn = QPushButton("Stop")
        self.stop_workflow_btn.clicked.connect(self.stop_running_workflow)
        self.stop_workflow_btn.setEnabled(False)
        preview_toolbar.addWidget(self.stop_workflow_btn)

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
        exec_label = QLabel("Logs d'exÃ©cution")
        exec_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 6px;")
        layout.addWidget(exec_label)
        self.execution_log_text = QTextEdit()
        self.execution_log_text.setReadOnly(True)
        self.execution_log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.execution_log_text.setMinimumHeight(180)
        self.execution_log_text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; "
            "background: #101820; color: #d8e6f3;"
        )
        layout.addWidget(self.execution_log_text)

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
        self._resolved_params_cache = {}
        self.node_index_by_uid = {}
        self.preview_dirty = True
        self.update_preview_status()

    def generate_workflow_preview(self):
        """Recalcule l'ordre puis met à jour l'aperçu du script."""
        if hasattr(self, 'preview_refresh_timer'):
            self.preview_refresh_timer.stop()
        self.scene.update_execution_order()
        self.refresh_bat_preview()

    def schedule_bat_preview_refresh(self, *_args):
        """Déclenche une mise à jour différée de l'aperçu BAT."""
        if getattr(self.scene, 'temp_connection', None) is not None:
            return
        self.mark_workflow_dirty()
        if hasattr(self, 'preview_refresh_timer'):
            self.preview_refresh_timer.start(180)
    
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

    def sync_library_node_to_canvas(self, old_name, new_name=None):
        """Met a jour sur le canvas les noeuds bases sur un noeud de bibliotheque modifie."""
        target_name = (new_name or old_name or "").strip()
        if not old_name or not target_name:
            return 0

        library_node = self.library.get_node(target_name)
        if not library_node:
            return 0

        updated_count = 0
        for node in self.get_canvas_nodes():
            if node.node_data.get('name') != old_name:
                continue
            self._apply_library_data_to_canvas_node(node, library_node)
            updated_count += 1

        if updated_count:
            self.rebuild_node_index()
            self.scene.update_scene_bounds()
            self.refresh_all_parameter_links()
            self.mark_workflow_dirty()
            self.generate_workflow_preview()

        return updated_count

    def _apply_library_data_to_canvas_node(self, node, library_node):
        """Remplace la definition d'un noeud du canvas par la version bibliotheque."""
        current_params = dict(node.parameters)
        current_links = {
            key: value.copy() if isinstance(value, dict) else value
            for key, value in node.parameter_links.items()
        }
        current_output_extension = node.output_extension

        node.node_data = copy.deepcopy(library_node)

        new_params = {}
        for param in node.node_data.get('parameters', []):
            param_name = param.get('name')
            if not param_name:
                continue
            new_params[param_name] = current_params.get(param_name, param.get('default', ''))
        node.parameters = new_params
        node.parameter_links = {
            key: value for key, value in current_links.items()
            if key in node.parameters
        }

        if node.node_data.get('outputs'):
            fallback_extension = node.node_data.get('output_extension', '')
            node.output_extension = normalize_output_extension(current_output_extension or fallback_extension)
        else:
            node.output_extension = ""

        node._rebuild_ports()
        node.schedule_parameter_widgets_rebuild()
        node.update()

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
                new_name = dialog.name_edit.text().strip() or node_name
                updated_count = self.sync_library_node_to_canvas(node_name, new_name)
                if updated_count:
                    self.statusBar().showMessage(
                        f"Noeud mis a jour dans le workflow: {updated_count} occurrence(s) synchronisee(s)"
                    )
    
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
        self.node_index_by_uid[node.node_uid] = node
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
        if not self.node_index_by_uid:
            self.rebuild_node_index()
        return sorted(
            self.node_index_by_uid.values(),
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
        self.schedule_bat_preview_refresh()

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
        self.schedule_bat_preview_refresh()

    def on_debug_mode_changed(self, checked):
        """Active ou désactive les traces de débogage dans le script."""
        self.debug_enabled = bool(checked)
        if hasattr(self, 'debug_pause_checkbox'):
            self.debug_pause_checkbox.setEnabled(self.debug_enabled)
        status = "activé" if self.debug_enabled else "désactivé"
        self.statusBar().showMessage(f"Mode debug {status}")
        self.schedule_bat_preview_refresh()

    def on_debug_pause_changed(self, checked):
        """Active ou désactive la pause pas à pas avant chaque noeud."""
        self.debug_pause_enabled = bool(checked)
        status = "activée" if self.debug_pause_enabled else "désactivée"
        self.statusBar().showMessage(f"Pause avant chaque action {status}")
        self.schedule_bat_preview_refresh()

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
        existing_nodes = self.get_canvas_nodes()
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
        self.rebuild_node_index()
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
    
    def create_menus(self):
        """Crée les menus."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Fichier")
        self.file_menu = file_menu
        save_workflow = file_menu.addAction("Sauvegarder workflow")
        save_workflow.triggered.connect(self.save_workflow)
        load_workflow = file_menu.addAction("Charger workflow")
        load_workflow.triggered.connect(self.load_workflow)
        self.recent_workflows_menu = file_menu.addMenu("Flux récents")
        self.refresh_recent_workflows_menu()
        file_menu.addSeparator()
        export_script = file_menu.addAction("Exporter le script")
        export_script.triggered.connect(self.export_to_bat)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quitter")
        quit_action.triggered.connect(self.close)

        edit_menu = menubar.addMenu("Édition")
        refresh_order = edit_menu.addAction("Recalculer l'ordre d'exécution")
        refresh_order.triggered.connect(self.generate_workflow_preview)
        edit_menu.addSeparator()
        focus_selected = edit_menu.addAction("Centrer sur le noeud sélectionné")
        focus_selected.setShortcut("F")
        focus_selected.triggered.connect(self.focus_selected_node)
        find_node = edit_menu.addAction("Aller à un noeud...")
        find_node.setShortcut("Ctrl+F")
        find_node.triggered.connect(self.find_and_focus_node)
        fit_workflow = edit_menu.addAction("Cadrer tout le workflow")
        fit_workflow.setShortcut("Ctrl+0")
        fit_workflow.triggered.connect(self.fit_workflow_in_view)
        edit_menu.addSeparator()
        clear_action = edit_menu.addAction("Effacer le canvas")
        clear_action.triggered.connect(self.clear_canvas)

        lib_menu = menubar.addMenu("Bibliothèque")
        new_node = lib_menu.addAction("Créer nouveau noeud")
        new_node.triggered.connect(self.create_new_node)
        lib_menu.addSeparator()
        import_library = lib_menu.addAction("Importer bibliothèque")
        import_library.triggered.connect(self.import_library)
        export_library = lib_menu.addAction("Exporter bibliothèque")
        export_library.triggered.connect(self.export_library)

        tools_menu = menubar.addMenu("Outils")
        config_deps = tools_menu.addAction("Configurer les dépendances")
        config_deps.triggered.connect(self.configure_dependencies)

        help_menu = menubar.addMenu("Aide")
        help_action = help_menu.addAction("Guide de Terminal Architect")
        help_action.triggered.connect(self.show_help_dialog)

    def load_recent_workflows(self):
        """Charge l'historique des workflows récents."""
        try:
            if os.path.exists(self.recent_workflows_file):
                with open(self.recent_workflows_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if isinstance(items, list):
                    self.recent_workflows = [str(item) for item in items if str(item).strip()]
        except Exception:
            self.recent_workflows = []
        self.recent_workflows = self.recent_workflows[:16]
        if hasattr(self, "recent_workflows_menu"):
            self.refresh_recent_workflows_menu()

    def save_recent_workflows(self):
        """Sauvegarde l'historique des workflows récents."""
        try:
            with open(self.recent_workflows_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_workflows[:16], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def register_recent_workflow(self, filename):
        """Ajoute un workflow à la liste des récents."""
        path = os.path.abspath(str(filename or "").strip())
        if not path:
            return
        self.recent_workflows = [item for item in self.recent_workflows if os.path.abspath(item) != path]
        self.recent_workflows.insert(0, path)
        self.recent_workflows = self.recent_workflows[:16]
        self.save_recent_workflows()
        if hasattr(self, "recent_workflows_menu"):
            self.refresh_recent_workflows_menu()

    def refresh_recent_workflows_menu(self):
        """Reconstruit le sous-menu des workflows récents."""
        if not hasattr(self, "recent_workflows_menu"):
            return
        self.recent_workflows_menu.clear()
        existing = [item for item in self.recent_workflows if os.path.exists(item)]
        self.recent_workflows = existing[:16]
        if not self.recent_workflows:
            empty_action = self.recent_workflows_menu.addAction("Aucun flux récent")
            empty_action.setEnabled(False)
            return
        for path in self.recent_workflows:
            action = self.recent_workflows_menu.addAction(path)
            action.triggered.connect(lambda checked=False, current_path=path: self.load_workflow(current_path))

    def show_help_dialog(self):
        """Affiche le guide utilisateur embarqué."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Aide - Terminal Architect")
        dialog.resize(800, 600)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        try:
            with open(self.help_file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            content = "# Aide indisponible\n\nLe fichier `AIDE.md` est introuvable."
        browser.setMarkdown(content)
        layout.addWidget(browser)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.setLayout(layout)
        dialog.exec()

    def save_workflow(self):
        """Sauvegarde le workflow"""
        filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder le workflow", 
                                                   "workflow.workflow", "Workflow Files (*.workflow)")
        if not filename:
            return
        filename = ensure_file_extension(filename, ".workflow")
        
        workflow = {
            'mode': self.workflow_mode,
            'script_type': self.script_type,
            'debug_enabled': self.debug_enabled,
            'debug_pause_enabled': self.debug_pause_enabled,
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
                                                   "", "Workflow Files (*.workflow)")
        if not filename:
            return
        
        with open(filename, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        self.workflow_mode = workflow.get('mode', 'per_file')
        self.script_type = workflow.get('script_type', 'batch')
        self.debug_enabled = bool(workflow.get('debug_enabled', False))
        self.debug_pause_enabled = bool(workflow.get('debug_pause_enabled', True))
        self.loop_mode_checkbox.setChecked(self.workflow_mode == 'per_file')
        combo_index = self.script_type_combo.findData(self.script_type)
        if combo_index >= 0:
            self.script_type_combo.setCurrentIndex(combo_index)
        self.debug_checkbox.setChecked(self.debug_enabled)
        self.debug_pause_checkbox.setChecked(self.debug_pause_enabled)
        self.debug_pause_checkbox.setEnabled(self.debug_enabled)
        
        # Effacer sans demander confirmation
        for item in self.scene.items():
            self.scene.removeItem(item)
        self.invalidate_runtime_caches()
        
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
        
        self.rebuild_node_index()
        self.scene.update_scene_bounds()
        self.fit_workflow_in_view()
        self.statusBar().showMessage(f"Workflow chargé: {filename}")
        self.mark_workflow_dirty()
    
    def save_workflow(self):
        """Sauvegarde le workflow."""
        filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder le workflow", "workflow.workflow", "Workflow Files (*.workflow)")
        if not filename:
            return
        filename = ensure_file_extension(filename, ".workflow")

        workflow = {
            'mode': self.workflow_mode,
            'script_type': self.script_type,
            'debug_enabled': self.debug_enabled,
            'debug_pause_enabled': self.debug_pause_enabled,
            'nodes': [],
            'connections': []
        }

        node_id_map = {}
        for item in self.scene.items():
            if isinstance(item, Node):
                node_id = len(workflow['nodes'])
                node_id_map[id(item)] = node_id
                workflow['nodes'].append({
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
                })

        for item in self.scene.items():
            if isinstance(item, Connection) and item.end_port:
                from_id = node_id_map.get(id(item.start_port.parent_node))
                to_id = node_id_map.get(id(item.end_port.parent_node))
                if from_id is not None and to_id is not None:
                    workflow['connections'].append({
                        'from_node': from_id,
                        'from_port': item.start_port.index,
                        'to_node': to_id,
                        'to_port': item.end_port.index
                    })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)

        self.register_recent_workflow(filename)
        self.statusBar().showMessage(f"Workflow sauvegardé: {filename}")

    def load_workflow(self, filename=None):
        """Charge un workflow."""
        if not filename:
            filename, _ = QFileDialog.getOpenFileName(self, "Charger un workflow", "", "Workflow Files (*.workflow)")
            if not filename:
                return

        with open(filename, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        self.workflow_mode = workflow.get('mode', 'per_file')
        self.script_type = workflow.get('script_type', 'batch')
        self.debug_enabled = bool(workflow.get('debug_enabled', False))
        self.debug_pause_enabled = bool(workflow.get('debug_pause_enabled', True))
        self.loop_mode_checkbox.setChecked(self.workflow_mode == 'per_file')
        combo_index = self.script_type_combo.findData(self.script_type)
        if combo_index >= 0:
            self.script_type_combo.setCurrentIndex(combo_index)
        self.debug_checkbox.setChecked(self.debug_enabled)
        self.debug_pause_checkbox.setChecked(self.debug_pause_enabled)
        self.debug_pause_checkbox.setEnabled(self.debug_enabled)

        for item in self.scene.items():
            self.scene.removeItem(item)
        self.invalidate_runtime_caches()

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
                node.output_extension = normalize_output_extension(node_data.get('output_extension', node.output_extension))
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

        self.rebuild_node_index()
        self.scene.update_scene_bounds()
        self.fit_workflow_in_view()
        self.register_recent_workflow(filename)
        self.statusBar().showMessage(f"Workflow chargé: {filename}")
        self.mark_workflow_dirty()

    def configure_dependencies(self):
        """Configure les chemins des dépendances"""
        dialog = DependencyConfigDialog(self.dep_manager, self)
        dialog.exec()

    def append_execution_log(self, text):
        """Ajoute du texte dans la console d'execution."""
        if not text:
            return
        cursor = self.execution_log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.execution_log_text.setTextCursor(cursor)
        self.execution_log_text.ensureCursorVisible()

    def clear_execution_log(self):
        """Vide la console d'execution."""
        self.execution_log_text.clear()
        self.execution_output_buffer = ""

    def reset_runtime_node_states(self):
        """Remet tous les noeuds a leur etat visuel neutre."""
        for node in self.get_canvas_nodes():
            node.set_runtime_state("idle")
        self.current_running_node_uid = None

    def set_active_execution_node(self, node_uid):
        """Met en avant le noeud en cours d'execution."""
        if self.current_running_node_uid and self.current_running_node_uid != node_uid:
            previous = self.get_node_by_uid(self.current_running_node_uid)
            if previous is not None:
                previous.set_runtime_state("success")
        self.current_running_node_uid = node_uid
        node = self.get_node_by_uid(node_uid)
        if node is not None:
            node.set_runtime_state("running")
            node.setSelected(True)
            self.view.centerOn(node)

    def mark_execution_node_finished(self, node_uid, success=True):
        """Marque un noeud comme termine."""
        node = self.get_node_by_uid(node_uid)
        if node is not None:
            node.set_runtime_state("success" if success else "error")
        if self.current_running_node_uid == node_uid:
            self.current_running_node_uid = None

    def _consume_execution_output(self, raw_text):
        """Parse la sortie du process et intercepte les marqueurs de noeud."""
        if not raw_text:
            return
        self.execution_output_buffer += raw_text
        lines = self.execution_output_buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            self.execution_output_buffer = lines.pop()
        else:
            self.execution_output_buffer = ""

        for line in lines:
            marker = line.strip()
            if marker.startswith("__NODE_START__:"):
                self.set_active_execution_node(marker.split(":", 1)[1])
                continue
            if marker.startswith("__NODE_END__:"):
                self.mark_execution_node_finished(marker.split(":", 1)[1], True)
                continue
            self.append_execution_log(line)

    def _read_process_output(self):
        """Lit la sortie fusionnee du process en cours."""
        if self.execution_process is None:
            return
        data = bytes(self.execution_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._consume_execution_output(data)

    def _is_workflow_input_driven(self):
        """Indique si le workflow attend des fichiers en argument."""
        names = {node.node_data.get('name') for node in self.get_canvas_nodes()}
        return bool(names.intersection({"Fichier Input", "Liste", "Multi-fichiers"}))

    def _select_execution_inputs(self):
        """Demande les fichiers a traiter pour l'execution locale."""
        if not self._is_workflow_input_driven():
            return []
        if any(node.node_data.get('name') == 'Liste' for node in self.get_canvas_nodes()):
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir le fichier liste",
                "",
                "Text Files (*.txt);;All Files (*.*)"
            )
            if not filename:
                return None
            return [filename]
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Choisir les fichiers a traiter",
            "",
            "All Files (*.*)"
        )
        if not filenames:
            return None
        return filenames

    def _build_temporary_execution_script(self, script_content):
        """Ecrit un script temporaire instrumente pour l'execution UI."""
        suffix_map = {"batch": ".bat", "bash": ".sh", "powershell": ".ps1"}
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix_map.get(self.script_type, ".bat"),
            mode="w",
            encoding="utf-8"
        )
        with temp_file:
            temp_file.write(script_content)
        return temp_file.name

    def _build_process_command(self, script_path, input_files):
        """Construit la commande a lancer selon le type de script."""
        if self.script_type == "powershell":
            return "powershell.exe", ["-ExecutionPolicy", "Bypass", "-File", script_path, *input_files]
        if self.script_type == "bash":
            return "bash", [script_path, *input_files]
        return "cmd.exe", ["/c", script_path, *input_files]

    def _build_execution_temp_root(self):
        """Cree un dossier temporaire unique pour une execution."""
        return tempfile.mkdtemp(prefix="cline_run_")

    def _set_execution_controls_running(self, running):
        self.run_workflow_btn.setEnabled(not running)
        self.stop_workflow_btn.setEnabled(running)
        self.generate_preview_btn.setEnabled(not running)

    def run_workflow_from_ui(self):
        """Genere puis execute le workflow depuis l'interface."""
        if self.execution_process is not None:
            QMessageBox.information(self, "Execution en cours", "Un workflow est deja en cours d'execution.")
            return
        input_files = self._select_execution_inputs()
        if input_files is None:
            return
        previous_flag = getattr(self, "_ui_execution_instrumented", False)
        try:
            if self.preview_dirty:
                self.generate_workflow_preview()
            self._ui_execution_instrumented = True
            script_content, warnings = self._get_script_preview_content()
            if warnings:
                QMessageBox.warning(self, "Attention", "\n".join(warnings))
            script_path = self._build_temporary_execution_script(script_content)
            program, arguments = self._build_process_command(script_path, input_files)
            self.clear_execution_log()
            self.reset_runtime_node_states()
            self.append_execution_log(f"[Execution] Script temporaire: {script_path}\n")
            for filename in input_files:
                self.append_execution_log(f"[Execution] Input: {filename}\n")
            if input_files:
                self.append_execution_log("\n")
            self.execution_temp_script = script_path
            self.execution_temp_root = self._build_execution_temp_root()
            self.execution_process = QProcess(self)
            process_env = QProcessEnvironment.systemEnvironment()
            process_env.insert("CLI_NODE_TEMP_ROOT", self.execution_temp_root)
            self.execution_process.setProcessEnvironment(process_env)
            self.execution_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.execution_process.readyReadStandardOutput.connect(self._read_process_output)
            self.execution_process.finished.connect(self._on_execution_finished)
            self.execution_process.errorOccurred.connect(self._on_execution_error)
            self.execution_process.setWorkingDirectory(os.path.dirname(script_path) or os.getcwd())
            self.execution_process.start(program, arguments)
            if not self.execution_process.waitForStarted(3000):
                raise RuntimeError(f"Impossible de lancer le process: {program}")
            self._set_execution_controls_running(True)
            self.statusBar().showMessage("Execution du workflow en cours...")
        except Exception as e:
            self._ui_execution_instrumented = previous_flag
            self._set_execution_controls_running(False)
            self.reset_runtime_node_states()
            self._finalize_execution_temp_script()
            if self.execution_process is not None:
                self.execution_process.deleteLater()
            self.execution_process = None
            QMessageBox.critical(self, "Erreur d'execution", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")

    def stop_running_workflow(self):
        """Arrete le workflow en cours."""
        if self.execution_process is None:
            return
        self.append_execution_log("\n[Execution] Arret demande par l'utilisateur.\n")
        self.execution_process.kill()

    def _finalize_execution_temp_script(self):
        """Nettoie le script temporaire et son dossier de travail."""
        if self.execution_temp_script and os.path.exists(self.execution_temp_script):
            try:
                os.remove(self.execution_temp_script)
            except OSError:
                pass
        self.execution_temp_script = None
        if self.execution_temp_root and os.path.exists(self.execution_temp_root):
            try:
                shutil.rmtree(self.execution_temp_root, ignore_errors=True)
            except OSError:
                pass
        self.execution_temp_root = None

    def _on_execution_finished(self, exit_code, _exit_status):
        """Traite la fin du process."""
        self._read_process_output()
        if self.execution_output_buffer:
            self.append_execution_log(self.execution_output_buffer)
            self.execution_output_buffer = ""
        success = exit_code == 0
        if self.current_running_node_uid:
            self.mark_execution_node_finished(self.current_running_node_uid, success)
        self.append_execution_log(f"\n[Execution] Terminee avec code {exit_code}.\n")
        self._set_execution_controls_running(False)
        self.statusBar().showMessage("Execution terminee" if success else "Execution terminee avec erreur")
        if self.execution_process is not None:
            self.execution_process.deleteLater()
        self.execution_process = None
        self._finalize_execution_temp_script()
        self._ui_execution_instrumented = False

    def _on_execution_error(self, process_error):
        """Affiche les erreurs du process."""
        self.append_execution_log(f"\n[Execution] Erreur process: {process_error}\n")

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
            self.invalidate_runtime_caches()
            self.populate_default_canvas()
            self.schedule_bat_preview_refresh()
    
    def import_library(self):
        """Importe une bibliothèque"""
        filename, _ = QFileDialog.getOpenFileName(self, "Importer bibliothèque", 
                                                   "", "Node Files (*.node)")
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                imported_nodes = json.load(f)
            
            self.library.add_nodes(imported_nodes.values())
            
            self.refresh_library_list()
            QMessageBox.information(self, "Succès", f"{len(imported_nodes)} noeuds importés")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur d'importation:\n{str(e)}")
    
    def export_library(self):
        """Exporte la bibliothèque"""
        filename, _ = QFileDialog.getSaveFileName(self, "Exporter bibliothèque", 
                                                   "my_library.node", "Node Files (*.node)")
        if not filename:
            return
        filename = ensure_file_extension(filename, ".node")
        
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
