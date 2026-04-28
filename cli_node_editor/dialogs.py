"""Dialogs and parameter widgets for CLI Node Editor."""

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QColor, QCursor

from .core import SYSTEM_SOURCE_NODE_NAMES, get_display_node_name, normalize_output_extension

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
            "• {input} - Fichier d'entrée quoté\n"
            "• {input_raw} - Fichier d'entrée brut (sans guillemets)\n"
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
