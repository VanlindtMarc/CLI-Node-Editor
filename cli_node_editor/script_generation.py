"""Workflow parameter resolution and script generation mixin."""

from PyQt6.QtWidgets import QInputDialog, QMessageBox

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
    get_display_node_name,
    normalize_output_extension,
    quote_shell_string,
    replace_indexed_placeholders,
)


class ScriptGenerationMixin:
    def _is_debug_enabled(self):
        return bool(getattr(self, 'debug_enabled', False))

    def _is_debug_pause_enabled(self):
        if self._is_ui_execution_instrumented():
            return False
        return self._is_debug_enabled() and bool(getattr(self, 'debug_pause_enabled', False))

    def _is_debug_node(self, node):
        return node.node_data['name'] == DEBUG_NODE_NAME

    def _ps_quote_inline(self, value):
        return '"' + str(value or '').replace('`', '``').replace('"', '`"') + '"'

    def _escape_double_quotes(self, value):
        return str(value or '').replace('"', '\\"')

    def _escape_powershell_double_quotes(self, value):
        return str(value or '').replace('"', '`"')

    def _is_ui_execution_instrumented(self):
        return bool(getattr(self, '_ui_execution_instrumented', False))

    def _append_batch_node_marker(self, lines, event_name, node):
        if self._is_ui_execution_instrumented():
            lines.append(f'echo __NODE_{event_name}__:{node.node_uid}')

    def _append_bash_node_marker(self, lines, event_name, node):
        if self._is_ui_execution_instrumented():
            lines.append(f'echo "__NODE_{event_name}__:{node.node_uid}"')

    def _append_powershell_node_marker(self, lines, event_name, node):
        if self._is_ui_execution_instrumented():
            lines.append(f'Write-Host "__NODE_{event_name}__:{node.node_uid}"')

    def _get_debug_node_mode(self, rendered_params):
        mode = str(rendered_params.get('Mode sortie', 'Console + fichier') or 'Console + fichier').strip()
        return mode if mode in ['Console', 'Fichier', 'Console + fichier'] else 'Console + fichier'

    def _append_batch_debug_node(self, lines, node, input_files, rendered_params, output_var_name):
        message = str(rendered_params.get('Message', 'Point de debug') or 'Point de debug')
        log_filename = str(rendered_params.get('Nom fichier log', 'workflow_debug.log') or 'workflow_debug.log')
        log_dir = str(rendered_params.get('Dossier log', '') or '').strip()
        mode = self._get_debug_node_mode(rendered_params)

        if input_files:
            lines.append(f'set "{output_var_name}={self._strip_wrapping_quotes(input_files[0])}"')
        else:
            lines.append(f'set "{output_var_name}="')

        if mode in ['Fichier', 'Console + fichier']:
            target_dir = log_dir or '!INPUT_PATH!'
            lines.append(f'set "DEBUG_LOG_DIR_{node.execution_order or 0}={target_dir}"')
            lines.append(f'if not exist "!DEBUG_LOG_DIR_{node.execution_order or 0}!" mkdir "!DEBUG_LOG_DIR_{node.execution_order or 0}!" >nul 2>&1')
            lines.append(f'set "DEBUG_LOG_FILE_{node.execution_order or 0}=!DEBUG_LOG_DIR_{node.execution_order or 0}!\\{log_filename}"')
        if mode in ['Console', 'Console + fichier']:
            lines.append(f'echo [DEBUG NODE] Etape {node.execution_order or 0}: {message}')
            if input_files:
                lines.append(f'echo [DEBUG NODE] Input: {self._strip_wrapping_quotes(input_files[0])}')
            else:
                lines.append('echo [DEBUG NODE] Aucun input')
        if mode in ['Fichier', 'Console + fichier']:
            lines.append(f'>> "!DEBUG_LOG_FILE_{node.execution_order or 0}!" echo [DEBUG NODE] Etape {node.execution_order or 0}: {message}')
            if input_files:
                lines.append(f'>> "!DEBUG_LOG_FILE_{node.execution_order or 0}!" echo [DEBUG NODE] Input: {self._strip_wrapping_quotes(input_files[0])}')
            else:
                lines.append(f'>> "!DEBUG_LOG_FILE_{node.execution_order or 0}!" echo [DEBUG NODE] Aucun input')

    def _append_bash_debug_node(self, lines, node, input_files, rendered_params, output_var_name):
        message = str(rendered_params.get('Message', 'Point de debug') or 'Point de debug').replace('"', '\\"')
        log_filename = str(rendered_params.get('Nom fichier log', 'workflow_debug.log') or 'workflow_debug.log').replace('"', '\\"')
        log_dir = str(rendered_params.get('Dossier log', '') or '').strip()
        mode = self._get_debug_node_mode(rendered_params)

        if input_files:
            lines.append(f'{output_var_name}={input_files[0]}')
        else:
            lines.append(f'{output_var_name}=""')

        if mode in ['Fichier', 'Console + fichier']:
            if log_dir:
                lines.append(f'debug_log_dir_{node.execution_order or 0}={quote_shell_string(log_dir)}')
                lines.append(f'eval "debug_log_dir_{node.execution_order or 0}=${{debug_log_dir_{node.execution_order or 0}}}"')
            else:
                lines.append(f'debug_log_dir_{node.execution_order or 0}="$INPUT_PATH"')
            lines.append(f'mkdir -p "$debug_log_dir_{node.execution_order or 0}"')
            lines.append(f'debug_log_file_{node.execution_order or 0}="$debug_log_dir_{node.execution_order or 0}/{log_filename}"')
        if mode in ['Console', 'Console + fichier']:
            lines.append(f'echo "[DEBUG NODE] Etape {node.execution_order or 0}: {message}"')
            if input_files:
                safe_input = self._escape_double_quotes(self._strip_wrapping_quotes(input_files[0]))
                lines.append(f'echo "[DEBUG NODE] Input: {safe_input}"')
            else:
                lines.append('echo "[DEBUG NODE] Aucun input"')
        if mode in ['Fichier', 'Console + fichier']:
            lines.append(f'printf "%s\\n" "[DEBUG NODE] Etape {node.execution_order or 0}: {message}" >> "$debug_log_file_{node.execution_order or 0}"')
            if input_files:
                safe_input = self._escape_double_quotes(self._strip_wrapping_quotes(input_files[0]))
                lines.append(f'printf "%s\\n" "[DEBUG NODE] Input: {safe_input}" >> "$debug_log_file_{node.execution_order or 0}"')
            else:
                lines.append(f'printf "%s\\n" "[DEBUG NODE] Aucun input" >> "$debug_log_file_{node.execution_order or 0}"')

    def _append_powershell_debug_node(self, lines, node, input_files, rendered_params, output_var_name):
        message = str(rendered_params.get('Message', 'Point de debug') or 'Point de debug').replace('"', '`"')
        log_filename = str(rendered_params.get('Nom fichier log', 'workflow_debug.log') or 'workflow_debug.log').replace('"', '`"')
        log_dir = str(rendered_params.get('Dossier log', '') or '').strip()
        mode = self._get_debug_node_mode(rendered_params)

        if input_files:
            lines.append(f'{output_var_name} = {input_files[0]}')
        else:
            lines.append(f'{output_var_name} = $null')

        if mode in ['Fichier', 'Console + fichier']:
            if log_dir:
                lines.append(f'$DebugLogDir{node.execution_order or 0} = $ExecutionContext.InvokeCommand.ExpandString({self._ps_quote_inline(log_dir)})')
            else:
                lines.append(f'$DebugLogDir{node.execution_order or 0} = $INPUT_PATH')
            lines.append(f'New-Item -ItemType Directory -Force -Path $DebugLogDir{node.execution_order or 0} | Out-Null')
            lines.append(f'$DebugLogFile{node.execution_order or 0} = Join-Path $DebugLogDir{node.execution_order or 0} {self._ps_quote_inline(log_filename)}')
        if mode in ['Console', 'Console + fichier']:
            lines.append(f'Write-Host "[DEBUG NODE] Etape {node.execution_order or 0}: {message}"')
            if input_files:
                safe_input = self._escape_powershell_double_quotes(self._strip_wrapping_quotes(input_files[0]))
                lines.append(f'Write-Host "[DEBUG NODE] Input: {safe_input}"')
            else:
                lines.append('Write-Host "[DEBUG NODE] Aucun input"')
        if mode in ['Fichier', 'Console + fichier']:
            lines.append(f'Add-Content -LiteralPath $DebugLogFile{node.execution_order or 0} -Value "[DEBUG NODE] Etape {node.execution_order or 0}: {message}"')
            if input_files:
                safe_input = self._escape_powershell_double_quotes(self._strip_wrapping_quotes(input_files[0]))
                lines.append(f'Add-Content -LiteralPath $DebugLogFile{node.execution_order or 0} -Value "[DEBUG NODE] Input: {safe_input}"')
            else:
                lines.append(f'Add-Content -LiteralPath $DebugLogFile{node.execution_order or 0} -Value "[DEBUG NODE] Aucun input"')

    def _append_batch_debug_step(self, lines, node, input_files, rendered_params):
        if not self._is_debug_enabled():
            return
        lines.append(f'echo [DEBUG] Etape {node.execution_order or 0}: {node.node_data["name"]}')
        if input_files:
            for index, input_file in enumerate(input_files, start=1):
                lines.append(f'echo [DEBUG] Input {index}: {self._strip_wrapping_quotes(input_file)}')
        else:
            lines.append('echo [DEBUG] Aucun input connecte')
        for param_name, param_value in rendered_params.items():
            safe_name = str(param_name).replace(":", " ")
            lines.append(f'echo [DEBUG] Param {safe_name}: {param_value}')
        if self._is_debug_pause_enabled():
            lines.append('echo [DEBUG] Appuyez sur une touche pour executer cette etape...')
            lines.append('pause >nul')

    def _append_bash_debug_step(self, lines, node, input_files, rendered_params):
        if not self._is_debug_enabled():
            return
        lines.append(f'echo "[DEBUG] Etape {node.execution_order or 0}: {node.node_data["name"]}"')
        if input_files:
            for index, input_file in enumerate(input_files, start=1):
                lines.append(f'echo "[DEBUG] Input {index}: {self._strip_wrapping_quotes(input_file)}"')
        else:
            lines.append('echo "[DEBUG] Aucun input connecte"')
        for param_name, param_value in rendered_params.items():
            safe_name = str(param_name).replace('"', "'")
            safe_value = str(param_value).replace('"', '\\"')
            lines.append(f'echo "[DEBUG] Param {safe_name}: {safe_value}"')
        if self._is_debug_pause_enabled():
            lines.append('read -r -p "[DEBUG] Appuyez sur Entree pour executer cette etape..." _debug_step')

    def _append_powershell_debug_step(self, lines, node, input_files, rendered_params):
        if not self._is_debug_enabled():
            return
        lines.append(f'Write-Host "[DEBUG] Etape {node.execution_order or 0}: {node.node_data["name"]}"')
        if input_files:
            for index, input_file in enumerate(input_files, start=1):
                safe_input = self._strip_wrapping_quotes(input_file).replace('"', '`"')
                lines.append(f'Write-Host "[DEBUG] Input {index}: {safe_input}"')
        else:
            lines.append('Write-Host "[DEBUG] Aucun input connecte"')
        for param_name, param_value in rendered_params.items():
            safe_name = str(param_name).replace('"', '`"')
            safe_value = str(param_value).replace('"', '`"')
            lines.append(f'Write-Host "[DEBUG] Param {safe_name}: {safe_value}"')
        if self._is_debug_pause_enabled():
            lines.append('Read-Host "[DEBUG] Appuyez sur Entree pour executer cette etape" | Out-Null')

    def get_node_by_uid(self, node_uid):
        cached_node = getattr(self, 'node_index_by_uid', {}).get(node_uid)
        if cached_node is not None and cached_node.scene() is self.scene:
            return cached_node

        if hasattr(self, 'rebuild_node_index'):
            self.rebuild_node_index()
            return getattr(self, 'node_index_by_uid', {}).get(node_uid)

        for item in self.scene.items():
            if isinstance(item, self.node_class) and item.node_uid == node_uid:
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
        cache = getattr(self, '_resolved_params_cache', None)
        if cache is not None and node.node_uid in cache:
            return dict(cache[node.node_uid])

        resolved = {
            param['name']: self.resolve_node_parameter_value(node, param['name'])
            for param in node.node_data.get('parameters', [])
        }
        if cache is not None:
            cache[node.node_uid] = dict(resolved)
        return resolved

    def refresh_all_parameter_links(self):
        for node in self.get_canvas_nodes():
            node.refresh_parameter_widgets()

    def prompt_parameter_link(self, target_node, target_param_name):
        candidates = []
        for item in self.get_canvas_nodes():
            if item is target_node:
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

    def _is_list_input_node(self, node):
        return node.node_data['name'] == LIST_INPUT_NODE_NAME

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

    def _render_batch_global_value(self, lines, node, slot_index, value, input_files, global_values, runtime_index, indent=""):
        runtime_var = f"GLOBAL_EXPR_{node.execution_order or 0}_{slot_index}_{runtime_index}"
        lines.append(f'{indent}set "{runtime_var}="')

        for part_type, part_value in self._split_brace_placeholders(value):
            if part_type == "text":
                text = str(part_value).replace('%INPUT_NAME%', '!INPUT_NAME!')
                text = text.replace('%INPUT_PATH%', '!INPUT_PATH!')
                text = text.replace('%INPUT_EXT%', '!INPUT_EXT!')
                text = text.replace('"', '^"')
                lines.append(f'{indent}set "{runtime_var}=!{runtime_var}!{text}"')
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
                    lines.append(f'{indent}for /f "usebackq delims=" %%A in ({input_files[input_index]}) do set "{runtime_var}=!{runtime_var}!%%A"')
            else:
                rendered_value = global_values.get(placeholder, f"{{{placeholder}}}")
                lines.append(f'{indent}set "{runtime_var}=!{runtime_var}!{rendered_value}"')

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

    def _append_batch_switch_test(self, lines, switch_value_var, compare_value, operator, test_var):
        escaped_value = str(compare_value).replace("^", "^^").replace('"', '^"')

        if operator == "==":
            lines.append(f'if /I "!{switch_value_var}!"=="{escaped_value}" (set "{test_var}=1") else set "{test_var}=0"')
            return

        if operator == "!=":
            lines.append(f'if /I "!{switch_value_var}!"=="{escaped_value}" (set "{test_var}=0") else set "{test_var}=1"')
            return

        ps_value = str(compare_value).replace("'", "''")
        compare_operator = self._get_switch_batch_ps_operator(operator)
        lines.append(
            f'for /f %%R in (\'powershell -NoProfile -Command "$left = $env:{switch_value_var}; $right = \'{ps_value}\'; if ($left {compare_operator} $right) {{ \'1\' }} else {{ \'0\' }}"\') do set "{test_var}=%%R"'
        )

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

    def _get_list_input_node(self, execution_order):
        for node in execution_order:
            if self._is_list_input_node(node):
                return node
        return None
    
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
        nodes_list = self.get_canvas_nodes()
        if not nodes_list:
            if hasattr(self, 'node_index_by_uid'):
                self.node_index_by_uid = {}
            self._resolved_params_cache = {}
            return [], []

        resolved_params_map = {
            node: self.get_resolved_node_parameters(node)
            for node in nodes_list
        }
        self._resolved_params_cache = {
            node.node_uid: dict(params)
            for node, params in resolved_params_map.items()
        }
        if hasattr(self, 'node_index_by_uid'):
            self.node_index_by_uid = {
                node.node_uid: node
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

            builtin_placeholders = {"input", "input_raw", "output", "output_raw"}
            builtin_placeholders.update(f"input{i}" for i in range(2, 11))
            builtin_placeholders.update(f"input{i}_raw" for i in range(2, 11))
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
        list_input_node = self._get_list_input_node(execution_order)
        uses_list_input = list_input_node is not None
        is_single_flow = self.workflow_mode == "single_flow" and not uses_list_input
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        if uses_list_input and any(node.node_data['name'] == 'Fichier Input' for node in execution_order):
            warnings.append("Le noeud 'Liste' remplace les arguments classiques. Evitez de le combiner avec 'Fichier Input'.")
        if uses_list_input and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Liste' n'est pas compatible avec 'Multi-fichiers'.")

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
                self._append_batch_node_marker(lines, "START", node)

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(
                        replace_indexed_placeholders(
                            replace_indexed_placeholders(
                                str(param_value).replace('%INPUT_NAME%', '!INPUT_NAME!').replace('%INPUT_PATH%', '!INPUT_PATH!').replace('%INPUT_EXT%', '!INPUT_EXT!'),
                                input_files,
                                lambda v: v if v else '""'
                            ),
                            input_files,
                            self._strip_wrapping_quotes,
                            "_raw"
                        ),
                        global_values
                    )
                    for param_name, param_value in resolved_params.items()
                }
                self._append_batch_debug_step(lines, node, input_files, rendered_params)
                output_var_name = self._make_runtime_output_var_name(node, 0)
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source'] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
                    lines.append(f'set "{output_var_name}="')
                if node.node_data['name'] == GLOBAL_VARIABLES_NODE_NAME:
                    for var_name, _var_value, _slot_index in self._get_global_variable_entries(node, resolved_params):
                        env_name = f"GLOBAL_{self._sanitize_global_name(var_name)}"
                        lines.append(f'set "{env_name}="')
                should_guard_inputs = bool(node.input_ports) and not self._is_merge_node(node)
                if should_guard_inputs:
                    lines.append('set "NODE_READY=1"')
                    lines.extend(self._build_batch_node_input_guard(input_files))
                    lines.append('if "!NODE_READY!"=="1" (')

                if node.node_data['name'] == 'Fichier Input':
                    if mode == "single_flow":
                        input_node_index += 1
                        node_outputs[self._make_output_key(node, 0)] = f'"%~f{input_node_index}"'
                    else:
                        node_outputs[self._make_output_key(node, 0)] = '"!INPUT_FULL!"'

                elif self._is_list_input_node(node):
                    node_outputs[self._make_output_key(node, 0)] = '"!INPUT_FULL!"'

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
                        compare_value = str(rendered_params.get(f'Valeur {spec_index}', spec['value']) or '')
                        lines.append(f'set "{out_var}="')
                        lines.append(f'set "{test_var}=0"')
                        self._append_batch_switch_test(
                            lines,
                            switch_value_var,
                            compare_value,
                            spec['operator'],
                            test_var
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

                elif self._is_debug_node(node):
                    self._append_batch_debug_node(lines, node, input_files, rendered_params, output_var_name)
                    node_outputs[self._make_output_key(node, 0)] = f'"!{output_var_name}!"'

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
                    output_file = f'!CLI_NODE_TEMP_ROOT!\\cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = f'"!{output_var}!"'
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'set "{output_var}={output_file}"')

                    if template:
                        cmd = template
                        cmd = replace_indexed_placeholders(cmd, input_files, lambda v: v if v else '""')
                        cmd = replace_indexed_placeholders(cmd, input_files, self._strip_wrapping_quotes, "_raw")
                        cmd = cmd.replace('{output}', f'"{output_file}"')
                        cmd = cmd.replace('{output_raw}', output_file)

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
                    lines.append(")")
                self._append_batch_node_marker(lines, "END", node)
                lines.append("")

            if temp_files:
                lines.append("REM Nettoyage temporaires")
                for temp_file in temp_files:
                    lines.append(f'if exist "{temp_file}" del "{temp_file}"')
                lines.append("")

        bat_lines = []
        bat_lines.append("@echo off")
        if uses_list_input:
            ignore_empty = True
        bat_lines.append("setlocal enabledelayedexpansion")
        bat_lines.append("chcp 65001 >nul")
        bat_lines.append('if not defined CLI_NODE_TEMP_ROOT set "CLI_NODE_TEMP_ROOT=%TEMP%\\cline_run_%RANDOM%_%RANDOM%"')
        bat_lines.append('if not exist "!CLI_NODE_TEMP_ROOT!" mkdir "!CLI_NODE_TEMP_ROOT!" >nul 2>&1')
        bat_lines.append("REM ============================================================")
        bat_lines.append("REM Script généré par CLI Node Editor")
        bat_lines.append("REM Compatible SendTo - Supporte plusieurs fichiers")
        bat_lines.append("REM ============================================================")
        bat_lines.append("")
        bat_lines.append("REM Vérification des arguments")
        if uses_list_input:
            bat_lines.append('if "%~1"=="" (')
            bat_lines.append("    echo ERREUR: Aucun fichier liste specifie")
            bat_lines.append("    echo.")
            bat_lines.append("    echo Deposez votre fichier liste sur ce script")
            bat_lines.append("    pause")
            bat_lines.append("    exit /b 1")
            bat_lines.append(")")
            bat_lines.append('set "LIST_FILE=%~f1"')
            bat_lines.append('if not exist "%LIST_FILE%" (')
            bat_lines.append('    echo ERREUR: Fichier liste introuvable: %LIST_FILE%')
            bat_lines.append('    pause')
            bat_lines.append('    exit /b 1')
            bat_lines.append(')')
            bat_lines.append("")
        bat_lines.append('if "%~1"=="" (')
        bat_lines.append("    echo ERREUR: Aucun fichier specifie")
        bat_lines.append("    echo.")
        bat_lines.append("    echo Usage: %~nx0 fichier1.ext [fichier2.ext] [...]")
        bat_lines.append("    echo Ou glissez-deposez des fichiers sur ce script")
        bat_lines.append("    pause")
        bat_lines.append("    exit /b 1")
        bat_lines.append(")")
        bat_lines.append("")

        if uses_list_input:
            bat_lines.append(":SKIP_ARG_CHECK")
            bat_lines.append("")
        bat_lines.append("set TOTAL_FILES=0")
        bat_lines.append("set SUCCESS_COUNT=0")
        bat_lines.append("set ERROR_COUNT=0")
        bat_lines.append("")

        bat_lines.append("REM Comptage des fichiers")
        bat_lines.append("for %%A in (%*) do set /a TOTAL_FILES+=1")
        if uses_list_input:
            bat_lines.append("set TOTAL_FILES=0")
            if ignore_empty:
                bat_lines.append('for /f "usebackq delims=" %%A in ("%LIST_FILE%") do if not "%%A"=="" set /a TOTAL_FILES+=1')
            else:
                bat_lines.append('for /f "usebackq delims=" %%A in ("%LIST_FILE%") do set /a TOTAL_FILES+=1')
            bat_lines.append("if %TOTAL_FILES% leq 0 (")
            bat_lines.append('    echo ERREUR: Le fichier liste ne contient aucune entree exploitable')
            bat_lines.append('    pause')
            bat_lines.append('    exit /b 1')
            bat_lines.append(")")
        bat_lines.append("echo.")
        bat_lines.append("echo ============================================================")
        if uses_list_input:
            list_flow_lines = []
            append_flow_body(list_flow_lines, "per_file")
            bat_lines.append("REM ============================================================")
            bat_lines.append("REM BOUCLE SUR LA LISTE")
            bat_lines.append("REM ============================================================")
            bat_lines.append(f'for /f "usebackq delims=" %%A in ("%LIST_FILE%") do (')
            if ignore_empty:
                bat_lines.append('    if not "%%A"=="" (')
                list_indent = "        "
            else:
                list_indent = "    "
            bat_lines.append(f'{list_indent}set "CURRENT_FILE=%%A"')
            bat_lines.append(f'{list_indent}set "INPUT_FULL=%%A"')
            bat_lines.append(f'{list_indent}if exist "%%A" (')
            bat_lines.append(f'{list_indent}    for %%F in ("%%A") do (')
            bat_lines.append(f'{list_indent}        set "INPUT_NAME=%%~nF"')
            bat_lines.append(f'{list_indent}        set "INPUT_EXT=%%~xF"')
            bat_lines.append(f'{list_indent}        set "INPUT_DRIVE=%%~dF"')
            bat_lines.append(f'{list_indent}        set "INPUT_PATH=%%~dpF"')
            bat_lines.append(f'{list_indent}        set "INPUT_FULL=%%~fF"')
            bat_lines.append(f'{list_indent}    )')
            bat_lines.append(f'{list_indent}) else (')
            bat_lines.append(f'{list_indent}    set "INPUT_NAME=%%A"')
            bat_lines.append(f'{list_indent}    set "INPUT_EXT="')
            bat_lines.append(f'{list_indent}    set "INPUT_DRIVE="')
            bat_lines.append(f'{list_indent}    set "INPUT_PATH="')
            bat_lines.append(f'{list_indent})')
            bat_lines.append(f'{list_indent}echo ------------------------------------------------------------')
            bat_lines.append(f'{list_indent}echo Traitement: !CURRENT_FILE!')
            bat_lines.append(f'{list_indent}echo ------------------------------------------------------------')
            bat_lines.append(f'{list_indent}echo.')
            for line in list_flow_lines:
                bat_lines.append((list_indent + line) if line else "")
            bat_lines.append(f'{list_indent}echo   [OK] Termine avec succes')
            bat_lines.append(f'{list_indent}set /a SUCCESS_COUNT+=1')
            if ignore_empty:
                bat_lines.append('    )')
            bat_lines.append(")")
            bat_lines.append("goto END_LIST_LOOP")
            bat_lines.append(":FLOW_ERROR")
            bat_lines.append("echo   [ERREUR] Echec du traitement")
            bat_lines.append("set /a ERROR_COUNT+=1")
            bat_lines.append(":END_LIST_LOOP")
        elif is_single_flow:
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
        elif not uses_list_input:
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
        bat_lines.append('if exist "!CLI_NODE_TEMP_ROOT!" rmdir /s /q "!CLI_NODE_TEMP_ROOT!" >nul 2>&1')
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
        list_input_node = self._get_list_input_node(execution_order)
        uses_list_input = list_input_node is not None
        is_single_flow = self.workflow_mode == "single_flow" and not uses_list_input
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        if uses_list_input and any(node.node_data['name'] == 'Fichier Input' for node in execution_order):
            warnings.append("Le noeud 'Liste' remplace les arguments classiques. Evitez de le combiner avec 'Fichier Input'.")
        if uses_list_input and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Liste' n'est pas compatible avec 'Multi-fichiers'.")

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
                self._append_bash_node_marker(lines, "START", node)

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(
                        replace_indexed_placeholders(
                            replace_indexed_placeholders(
                                bashify_value(param_value),
                                input_files,
                                lambda v: v if v else '""'
                            ),
                            input_files,
                            self._strip_wrapping_quotes,
                            "_raw"
                        ),
                        global_values
                    )
                    for param_name, param_value in resolved_params.items()
                }
                self._append_bash_debug_step(lines, node, input_files, rendered_params)
                output_var_name = f"node_out_{node.execution_order or 0}_0"
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source', LIST_INPUT_NODE_NAME] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
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

                elif self._is_list_input_node(node):
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

                elif self._is_debug_node(node):
                    self._append_bash_debug_node(lines, node, input_files, rendered_params, output_var_name)
                    node_outputs[self._make_output_key(node, 0)] = f'"${{{output_var_name}}}"'

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
                    output_file = f'${{CLI_NODE_TEMP_ROOT}}/cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = f'"${{{output_var}}}"'
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'{output_var}="{output_file}"')

                    if template:
                        cmd = template
                        cmd = replace_indexed_placeholders(cmd, input_files, lambda v: v if v else '""')
                        cmd = replace_indexed_placeholders(cmd, input_files, self._strip_wrapping_quotes, "_raw")
                        cmd = cmd.replace('{output}', f'"{output_file}"')
                        cmd = cmd.replace('{output_raw}', output_file)

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
                self._append_bash_node_marker(lines, "END", node)
                lines.append("")

            if temp_files:
                lines.append("# Nettoyage temporaires")
                for temp_file in temp_files:
                    lines.append(f'rm -f "{temp_file}"')
                lines.append("")

        sh_lines = []
        sh_lines.append("#!/usr/bin/env bash")
        sh_lines.append("set -u")
        sh_lines.append('if [ -z "${CLI_NODE_TEMP_ROOT:-}" ]; then CLI_NODE_TEMP_ROOT="${TMPDIR:-/tmp}/cline_run_$$-$(date +%s)"; fi')
        sh_lines.append('mkdir -p "$CLI_NODE_TEMP_ROOT"')
        sh_lines.append("")
        sh_lines.append("# ============================================================")
        sh_lines.append("# Script généré par CLI Node Editor")
        sh_lines.append("# Compatible Bash - Supporte plusieurs fichiers")
        sh_lines.append("# ============================================================")
        sh_lines.append("")
        if uses_list_input:
            ignore_empty = True
            sh_lines.append('if [ "$#" -eq 0 ]; then')
            sh_lines.append('    echo "ERREUR: Aucun fichier liste specifie"')
            sh_lines.append('    echo "Deposez votre fichier liste sur ce script"')
            sh_lines.append('    exit 1')
            sh_lines.append("fi")
            sh_lines.append('LIST_FILE="$1"')
            sh_lines.append('if [ ! -f "$LIST_FILE" ]; then')
            sh_lines.append('    echo "ERREUR: Fichier liste introuvable: $LIST_FILE"')
            sh_lines.append('    exit 1')
            sh_lines.append("fi")
            sh_lines.append("")
        else:
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
        if uses_list_input:
            sh_lines.append("TOTAL_FILES=0")
            sh_lines.append("resolved_inputs=()")
            sh_lines.append('while IFS= read -r line || [ -n "$line" ]; do')
            if ignore_empty:
                sh_lines.append('    [ -z "$line" ] && continue')
            sh_lines.append('    resolved_inputs+=("$line")')
            sh_lines.append('    TOTAL_FILES=$((TOTAL_FILES + 1))')
            sh_lines.append('done < "$LIST_FILE"')
            sh_lines.append('if [ "$TOTAL_FILES" -le 0 ]; then')
            sh_lines.append('    echo "ERREUR: Le fichier liste ne contient aucune entree exploitable"')
            sh_lines.append('    exit 1')
            sh_lines.append("fi")
        else:
            sh_lines.append('resolved_inputs=("$@")')
        sh_lines.append("")
        sh_lines.append('echo "============================================================"')
        if uses_list_input:
            sh_lines.append('echo "   Traitement via fichier liste"')
            sh_lines.append('echo "   Entrees trouvees: $TOTAL_FILES"')
        elif is_single_flow:
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
        elif uses_list_input:
            sh_lines.append('for CURRENT_FILE in "${resolved_inputs[@]}"; do')
            sh_lines.append('    if [ -e "$CURRENT_FILE" ]; then')
            sh_lines.append('        INPUT_FULL="$(realpath "$CURRENT_FILE" 2>/dev/null || printf "%s" "$CURRENT_FILE")"')
            sh_lines.append('        INPUT_NAME="$(basename "${INPUT_FULL%.*}")"')
            sh_lines.append('        INPUT_EXT="${INPUT_FULL##*.}"')
            sh_lines.append('        if [ "$INPUT_EXT" = "$INPUT_FULL" ]; then INPUT_EXT=""; else INPUT_EXT=".$INPUT_EXT"; fi')
            sh_lines.append('        INPUT_PATH="$(dirname "$INPUT_FULL")/"')
            sh_lines.append("    else")
            sh_lines.append('        INPUT_FULL="$CURRENT_FILE"')
            sh_lines.append('        INPUT_NAME="$CURRENT_FILE"')
            sh_lines.append('        INPUT_EXT=""')
            sh_lines.append('        INPUT_PATH=""')
            sh_lines.append("    fi")
            sh_lines.append('    flow_error=0')
            sh_lines.append('    echo "------------------------------------------------------------"')
            sh_lines.append('    echo "Traitement: $CURRENT_FILE"')
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
        sh_lines.append('rm -rf "$CLI_NODE_TEMP_ROOT"')
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
        list_input_node = self._get_list_input_node(execution_order)
        uses_list_input = list_input_node is not None
        is_single_flow = self.workflow_mode == "single_flow" and not uses_list_input
        if self.workflow_mode != "single_flow" and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Multi-fichiers' est prévu pour le mode flux unique.")

        if uses_list_input and any(node.node_data['name'] == 'Fichier Input' for node in execution_order):
            warnings.append("Le noeud 'Liste' remplace les arguments classiques. Evitez de le combiner avec 'Fichier Input'.")
        if uses_list_input and any(self._is_multi_file_node(n) for n in execution_order):
            warnings.append("Le noeud 'Liste' n'est pas compatible avec 'Multi-fichiers'.")

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
                self._append_powershell_node_marker(lines, "START", node)

                input_files = self._resolve_node_input_files(node, node_outputs)
                resolved_params = self.get_resolved_node_parameters(node)
                rendered_params = {
                    param_name: self._replace_global_placeholders_in_text(
                        replace_indexed_placeholders(
                            replace_indexed_placeholders(
                                psify_value(param_value),
                                input_files,
                                lambda v: v if v else '""'
                            ),
                            input_files,
                            self._strip_wrapping_quotes,
                            "_raw"
                        ),
                        global_values
                    )
                    for param_name, param_value in resolved_params.items()
                }
                self._append_powershell_debug_step(lines, node, input_files, rendered_params)
                output_var_name = f'$NodeOut{node.execution_order or 0}_0'
                if node.output_ports and node.node_data['name'] not in ['Fichier Input', 'Fichier Source', LIST_INPUT_NODE_NAME] and not self._is_multi_file_node(node) and not self._is_switch_node(node):
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

                elif self._is_list_input_node(node):
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

                elif self._is_debug_node(node):
                    self._append_powershell_debug_node(lines, node, input_files, rendered_params, output_var_name)
                    node_outputs[self._make_output_key(node, 0)] = output_var_name

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
                    output_file = f'$CLI_NODE_TEMP_ROOT\\cline_temp_{temp_counter}{temp_ext}'
                    output_var = output_var_name
                    node_outputs[self._make_output_key(node, 0)] = output_var
                    temp_files.append(output_file)

                    template = node.node_data.get('template', '')
                    command_name = node.node_data.get('command', '')
                    command_path = self.dep_manager.get(command_name) if command_name else command_name
                    lines.append(f'{output_var} = $ExecutionContext.InvokeCommand.ExpandString({ps_quote(output_file)})')

                    if template:
                        cmd = template
                        cmd = replace_indexed_placeholders(cmd, input_files, lambda v: v if v else '""')
                        cmd = replace_indexed_placeholders(cmd, input_files, self._strip_wrapping_quotes, "_raw")
                        cmd = cmd.replace('{output}', output_file)
                        cmd = cmd.replace('{output_raw}', output_file)

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
                self._append_powershell_node_marker(lines, "END", node)
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
        ps_lines.append('if ($env:CLI_NODE_TEMP_ROOT) { $CLI_NODE_TEMP_ROOT = $env:CLI_NODE_TEMP_ROOT } else { $CLI_NODE_TEMP_ROOT = Join-Path $env:TEMP ("cline_run_{0}_{1}" -f $PID, [DateTimeOffset]::Now.ToUnixTimeMilliseconds()) }')
        ps_lines.append('New-Item -ItemType Directory -Force -Path $CLI_NODE_TEMP_ROOT | Out-Null')
        ps_lines.append("")
        ps_lines.append("# ============================================================")
        ps_lines.append("# Script généré par CLI Node Editor")
        ps_lines.append("# Compatible PowerShell - Supporte plusieurs fichiers")
        ps_lines.append("# ============================================================")
        ps_lines.append("")
        if uses_list_input:
            ignore_empty = True
            ps_lines.append("if (-not $InputFiles -or $InputFiles.Count -eq 0) {")
            ps_lines.append('    Write-Host "ERREUR: Aucun fichier liste specifie"')
            ps_lines.append('    Write-Host "Deposez votre fichier liste sur ce script"')
            ps_lines.append("    exit 1")
            ps_lines.append("}")
            ps_lines.append("$LIST_FILE = $InputFiles[0]")
            ps_lines.append("if (-not (Test-Path -LiteralPath $LIST_FILE)) {")
            ps_lines.append('    Write-Host "ERREUR: Fichier liste introuvable: $LIST_FILE"')
            ps_lines.append("    exit 1")
            ps_lines.append("}")
            ps_lines.append("")
        else:
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
        if uses_list_input:
            ps_lines.append("$resolvedInputs = @()")
            ps_lines.append('$listEntries = Get-Content -LiteralPath $LIST_FILE')
            if ignore_empty:
                ps_lines.append('$listEntries = @($listEntries | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })')
            ps_lines.append('$resolvedInputs = @($listEntries | ForEach-Object { $item = $_.Trim(); if (Test-Path -LiteralPath $item) { (Resolve-Path -LiteralPath $item -ErrorAction SilentlyContinue)?.Path ?? $item } else { $item } })')
            ps_lines.append("$TOTAL_FILES = $resolvedInputs.Count")
            ps_lines.append("if ($TOTAL_FILES -le 0) {")
            ps_lines.append('    Write-Host "ERREUR: Le fichier liste ne contient aucune entree exploitable"')
            ps_lines.append("    exit 1")
            ps_lines.append("}")
        else:
            ps_lines.append("$resolvedInputs = @($InputFiles | ForEach-Object { (Resolve-Path $_ -ErrorAction SilentlyContinue)?.Path ?? $_ })")
        ps_lines.append("")
        ps_lines.append('Write-Host "============================================================"')
        if uses_list_input:
            ps_lines.append('Write-Host "   Traitement via fichier liste"')
            ps_lines.append('Write-Host "   Entrees trouvees: $TOTAL_FILES"')
        elif is_single_flow:
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
        elif uses_list_input:
            ps_lines.append("foreach ($CURRENT_FILE in $resolvedInputs) {")
            ps_lines.append("    if (Test-Path -LiteralPath $CURRENT_FILE) {")
            ps_lines.append("        $INPUT_FULL = (Resolve-Path -LiteralPath $CURRENT_FILE -ErrorAction SilentlyContinue)?.Path ?? $CURRENT_FILE")
            ps_lines.append("        $INPUT_NAME = [System.IO.Path]::GetFileNameWithoutExtension($INPUT_FULL)")
            ps_lines.append("        $INPUT_EXT = [System.IO.Path]::GetExtension($INPUT_FULL)")
            ps_lines.append("        $INPUT_PATH = [System.IO.Path]::GetDirectoryName($INPUT_FULL)")
            ps_lines.append('        if (-not [string]::IsNullOrEmpty($INPUT_PATH)) { $INPUT_PATH += [System.IO.Path]::DirectorySeparatorChar }')
            ps_lines.append("    } else {")
            ps_lines.append("        $INPUT_FULL = $CURRENT_FILE")
            ps_lines.append("        $INPUT_NAME = $CURRENT_FILE")
            ps_lines.append('        $INPUT_EXT = ""')
            ps_lines.append('        $INPUT_PATH = ""')
            ps_lines.append("    }")
            ps_lines.append("    $flowError = $false")
            ps_lines.append('    Write-Host "------------------------------------------------------------"')
            ps_lines.append('    Write-Host "Traitement: $CURRENT_FILE"')
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
        ps_lines.append('if (Test-Path -LiteralPath $CLI_NODE_TEMP_ROOT) { Remove-Item -LiteralPath $CLI_NODE_TEMP_ROOT -Recurse -Force -ErrorAction SilentlyContinue }')
        ps_lines.append("")
        ps_lines.append("if ($ERROR_COUNT -gt 0) {")
        ps_lines.append('    Write-Host "Certains fichiers ont echoue."')
        ps_lines.append("    exit 1")
        ps_lines.append("}")
        ps_lines.append("")
        ps_lines.append('Write-Host "Tous les fichiers ont ete traites avec succes!"')
        ps_lines.append("exit 0")

        return "\n".join(ps_lines), warnings
