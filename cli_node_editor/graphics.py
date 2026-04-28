"""Graphics scene components for CLI Node Editor."""

import math
import uuid

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QLineF, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QPainterPath, QPainterPathStroker, QFont, QTransform
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QMessageBox,
)

from .core import (
    DEBUG_NODE_NAME,
    GLOBAL_VARIABLES_MAX_SLOTS,
    GLOBAL_VARIABLES_NODE_NAME,
    INPUT_VARIABLES_MAX_SLOTS,
    INPUT_VARIABLES_NODE_NAME,
    LIST_INPUT_NODE_NAME,
    MERGE_MAX_INPUTS,
    MERGE_NODE_NAME,
    MULTI_FILE_MAX_SLOTS,
    MULTI_FILE_NODE_NAME,
    SWITCH_MAX_CONDITIONS,
    SWITCH_NODE_NAME,
    SYSTEM_SOURCE_NODE_NAMES,
    get_display_category,
    get_display_node_name,
    normalize_output_extension,
    remove_connection_safely,
)
from .dialogs import NodeConfigDialog, ParameterWidget

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
        self.runtime_state = "idle"
        
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
            DEBUG_NODE_NAME,
            LIST_INPUT_NODE_NAME,
            MULTI_FILE_NODE_NAME,
            SWITCH_NODE_NAME,
            MERGE_NODE_NAME,
            GLOBAL_VARIABLES_NODE_NAME,
            INPUT_VARIABLES_NODE_NAME
        ]:
            return False
        if not self.node_data.get('outputs'):
            return False
        return bool(self.output_extension or self.output_extension_choices)
    
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

    def set_runtime_state(self, state):
        """Met a jour l'etat visuel d'execution du noeud."""
        self.runtime_state = state or "idle"
        self.update()
    
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
        border_color = QColor('#2C3E50')
        border_width = 2
        if self.runtime_state == "running":
            border_color = QColor('#F1C40F')
            border_width = 4
        elif self.runtime_state == "success":
            border_color = QColor('#27AE60')
            border_width = 3
        elif self.runtime_state == "error":
            border_color = QColor('#C0392B')
            border_width = 3
        painter.setPen(QPen(border_color, border_width))
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

class NodeEditorScene(QGraphicsScene):
    """Scène contenant les noeuds"""
    
    executionOrderChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.base_scene_rect = QRectF(-50000, -50000, 100000, 100000)
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
        self.setSceneRect(self.base_scene_rect)

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

        padding = 2000
        padded = bounds.adjusted(-padding, -padding, padding, padding).united(self.base_scene_rect)
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
