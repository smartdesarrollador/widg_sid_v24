"""
List Creator Dialog
Ventana dedicada para crear listas avanzadas
"""

import logging
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QScrollArea,
    QWidget, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

# Importar el widget de paso
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from views.widgets.step_item_widget import StepItemWidget
from views.widgets.tag_group_selector import TagGroupSelector
from controllers.list_controller import ListController

logger = logging.getLogger(__name__)


class ListCreatorDialog(QDialog):
    """
    Diálogo dedicado para crear listas avanzadas

    Características:
    - Nombre de lista obligatorio con validación en tiempo real
    - Selector de categoría
    - Descripción opcional
    - Pasos dinámicos con StepItemWidget
    - Botón "Agregar Paso"
    - Reordenamiento de pasos (botones ↑↓)
    - Validación completa antes de crear
    - Contador de pasos en botón "Crear Lista"
    """

    # Señal emitida cuando se crea la lista exitosamente
    list_created = pyqtSignal(str, int, list)  # (list_name, category_id, item_ids)

    def __init__(self, list_controller: ListController, categories: list,
                 db_path: str = None, selected_category_id: int = None, parent=None):
        """
        Inicializa el diálogo de creación de listas

        Args:
            list_controller: Controlador de listas
            categories: Lista de categorías disponibles
            db_path: Path a la base de datos para TagGroupSelector
            selected_category_id: ID de categoría preseleccionada
            parent: Widget padre
        """
        super().__init__(parent)
        self.list_controller = list_controller
        self.categories = categories
        self.db_path = db_path
        self.selected_category_id = selected_category_id

        self.step_widgets: List[StepItemWidget] = []

        self.setWindowTitle("📝 Crear Lista de Pasos")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        self.setup_ui()
        self.apply_styles()

        # Agregar 2 pasos iniciales
        self.add_step()
        self.add_step()

        # Conectar señales del controlador
        self.list_controller.list_created.connect(self.on_list_created_signal)
        self.list_controller.error_occurred.connect(self.on_error_signal)

        logger.info("[LIST_CREATOR] Dialog opened")

    def setup_ui(self):
        """Configura la interfaz del diálogo"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create main scroll area for all form content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        # Container widget for scroll area
        scroll_container = QWidget()
        scroll_container.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        form_layout = QVBoxLayout(scroll_container)
        form_layout.setSpacing(15)
        form_layout.setContentsMargins(20, 20, 20, 20)

        # === HEADER ===
        header_label = QLabel("Crea una lista de pasos secuenciales")
        header_font = QFont()
        header_font.setPointSize(11)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #aaaaaa;")
        form_layout.addWidget(header_label)

        # === NOMBRE DE LA LISTA ===
        name_label = QLabel("Nombre de la lista:*")
        name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        form_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Deploy a Producción, Tutorial Git Básico...")
        self.name_input.textChanged.connect(self.on_name_changed)
        form_layout.addWidget(self.name_input)

        # Label de validación del nombre
        self.name_validation_label = QLabel("")
        self.name_validation_label.setStyleSheet("color: #ff6666; font-size: 11px;")
        form_layout.addWidget(self.name_validation_label)

        # === CATEGORÍA ===
        category_layout = QHBoxLayout()
        category_label = QLabel("Categoría:*")
        category_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        category_label.setFixedWidth(150)
        category_layout.addWidget(category_label)

        self.category_combo = QComboBox()
        for cat in self.categories:
            cat_id = cat.get('id') if isinstance(cat, dict) else cat.id
            cat_name = cat.get('name') if isinstance(cat, dict) else cat.name
            cat_icon = cat.get('icon') if isinstance(cat, dict) else cat.icon
            self.category_combo.addItem(f"{cat_icon} {cat_name}", cat_id)

        # Seleccionar categoría preseleccionada
        if self.selected_category_id:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == self.selected_category_id:
                    self.category_combo.setCurrentIndex(i)
                    break

        category_layout.addWidget(self.category_combo)
        form_layout.addLayout(category_layout)

        # === DESCRIPCIÓN (OPCIONAL) ===
        desc_label = QLabel("Descripción (opcional):")
        desc_label.setStyleSheet("font-size: 12px; margin-top: 10px;")
        form_layout.addWidget(desc_label)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Descripción de la lista, contexto, notas...")
        self.description_input.setMaximumHeight(60)
        form_layout.addWidget(self.description_input)

        # === TAGS COMUNES (se aplican a todos los pasos) ===
        tags_label = QLabel("Tags comunes (opcional - se aplican a todos los pasos):")
        tags_label.setStyleSheet("font-size: 12px; margin-top: 10px;")
        form_layout.addWidget(tags_label)

        self.common_tags_input = QLineEdit()
        self.common_tags_input.setPlaceholderText("Ej: python, git, produccion...")
        form_layout.addWidget(self.common_tags_input)

        # Tag Group Selector (optional) - wrapped in scroll area
        if self.db_path:
            try:
                self.tag_group_selector = TagGroupSelector(self.db_path, self)
                self.tag_group_selector.tags_changed.connect(self.on_tag_group_changed)

                # Create scroll area for tag group selector
                tags_scroll_area = QScrollArea()
                tags_scroll_area.setWidget(self.tag_group_selector)
                tags_scroll_area.setWidgetResizable(True)
                tags_scroll_area.setFixedHeight(120)  # Fixed height with scroll
                tags_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                tags_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                tags_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
                tags_scroll_area.setStyleSheet("""
                    QScrollArea {
                        border: 1px solid #3d3d3d;
                        border-radius: 4px;
                        background-color: #2d2d2d;
                    }
                    QScrollBar:vertical {
                        background-color: #2d2d2d;
                        width: 12px;
                        border-radius: 6px;
                    }
                    QScrollBar::handle:vertical {
                        background-color: #5a5a5a;
                        border-radius: 6px;
                        min-height: 20px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background-color: #007acc;
                    }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                    }
                """)

                form_layout.addWidget(tags_scroll_area)
            except Exception as e:
                logger.warning(f"Could not initialize TagGroupSelector: {e}")
                self.tag_group_selector = None
        else:
            self.tag_group_selector = None

        # === SEPARADOR ===
        separator_label = QLabel("──────── Pasos del Proceso ────────")
        separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator_label.setStyleSheet("color: #666666; margin: 10px 0;")
        form_layout.addWidget(separator_label)

        # === CONTENEDOR PARA PASOS (sin scroll separado) ===
        self.steps_container = QWidget()
        self.steps_container.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setSpacing(10)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)

        form_layout.addWidget(self.steps_container)

        # === BOTÓN AGREGAR PASO ===
        add_step_button = QPushButton("+ Agregar Paso")
        add_step_button.setFixedWidth(150)
        add_step_button.clicked.connect(self.add_step)
        form_layout.addWidget(add_step_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Add stretch at the end of form (inside scroll)
        form_layout.addStretch()

        # Set scroll widget and add to main layout
        scroll_area.setWidget(scroll_container)
        main_layout.addWidget(scroll_area)

        # === BOTONES DE ACCIÓN (FUERA DEL SCROLL, FIJOS EN LA PARTE INFERIOR) ===
        buttons_container = QWidget()
        buttons_container.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        buttons_container_layout = QVBoxLayout(buttons_container)
        buttons_container_layout.setContentsMargins(20, 10, 20, 20)
        buttons_container_layout.setSpacing(0)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.setFixedWidth(120)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        # Add spacing between buttons
        buttons_layout.addSpacing(15)

        self.create_button = QPushButton("Crear Lista")
        self.create_button.setFixedWidth(150)
        self.create_button.clicked.connect(self.create_list)
        buttons_layout.addWidget(self.create_button)

        buttons_container_layout.addLayout(buttons_layout)
        main_layout.addWidget(buttons_container)

        # Actualizar contador inicial
        self.update_create_button_text()

    def apply_styles(self):
        """Aplica estilos al diálogo"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QTextEdit {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #4a9eff;
            }
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                color: #e0e0e0;
            }
            QComboBox:hover {
                border: 1px solid #4a9eff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #e0e0e0;
                selection-background-color: #4a9eff;
                border: 1px solid #3a3a3a;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 16px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #5a5a5a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #007acc;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Estilo especial para el botón crear
        self.create_button.setStyleSheet("""
            QPushButton {
                background-color: #2a5a2a;
                border: 1px solid #3a7a3a;
                border-radius: 4px;
                padding: 8px 16px;
                color: #e0e0e0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a7a3a;
                border: 1px solid #4a9a4a;
            }
            QPushButton:pressed {
                background-color: #1a4a1a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #666666;
            }
        """)

    def add_step(self):
        """Agrega un nuevo paso a la lista"""
        step_number = len(self.step_widgets) + 1
        step_widget = StepItemWidget(step_number)

        # Conectar señales
        step_widget.delete_requested.connect(lambda: self.delete_step(step_widget))
        step_widget.move_up_requested.connect(lambda: self.move_step_up(step_widget))
        step_widget.move_down_requested.connect(lambda: self.move_step_down(step_widget))
        step_widget.data_changed.connect(self.update_create_button_text)

        # Agregar al layout y lista
        self.steps_layout.addWidget(step_widget)
        self.step_widgets.append(step_widget)

        # Actualizar números y botones
        self.update_step_numbers()
        self.update_create_button_text()

        logger.debug(f"[LIST_CREATOR] Added step {step_number}, total: {len(self.step_widgets)}")

    def delete_step(self, step_widget: StepItemWidget):
        """
        Elimina un paso de la lista

        Args:
            step_widget: Widget del paso a eliminar
        """
        # Mínimo 1 paso
        if len(self.step_widgets) <= 1:
            QMessageBox.warning(self, "Advertencia", "Debe haber al menos 1 paso en la lista")
            return

        # Eliminar widget
        self.steps_layout.removeWidget(step_widget)
        self.step_widgets.remove(step_widget)
        step_widget.deleteLater()

        # Actualizar números
        self.update_step_numbers()
        self.update_create_button_text()

        logger.debug(f"[LIST_CREATOR] Deleted step, remaining: {len(self.step_widgets)}")

    def move_step_up(self, step_widget: StepItemWidget):
        """Mueve un paso hacia arriba"""
        index = self.step_widgets.index(step_widget)
        if index == 0:
            return  # Ya está al principio

        # Intercambiar en la lista
        self.step_widgets[index], self.step_widgets[index - 1] = \
            self.step_widgets[index - 1], self.step_widgets[index]

        # Actualizar UI
        self.rebuild_steps_layout()
        self.update_step_numbers()

    def move_step_down(self, step_widget: StepItemWidget):
        """Mueve un paso hacia abajo"""
        index = self.step_widgets.index(step_widget)
        if index >= len(self.step_widgets) - 1:
            return  # Ya está al final

        # Intercambiar en la lista
        self.step_widgets[index], self.step_widgets[index + 1] = \
            self.step_widgets[index + 1], self.step_widgets[index]

        # Actualizar UI
        self.rebuild_steps_layout()
        self.update_step_numbers()

    def rebuild_steps_layout(self):
        """Reconstruye el layout de pasos después de reordenar"""
        # Limpiar layout
        while self.steps_layout.count():
            self.steps_layout.takeAt(0)

        # Re-agregar en nuevo orden
        for widget in self.step_widgets:
            self.steps_layout.addWidget(widget)

    def update_step_numbers(self):
        """Actualiza los números de los pasos y los botones de movimiento"""
        for i, widget in enumerate(self.step_widgets):
            widget.set_step_number(i + 1)
            # Habilitar/deshabilitar botones de movimiento
            widget.enable_move_buttons(
                enable_up=(i > 0),
                enable_down=(i < len(self.step_widgets) - 1)
            )

    def update_create_button_text(self):
        """Actualiza el texto del botón crear con el contador de pasos"""
        non_empty_steps = sum(1 for w in self.step_widgets if not w.is_empty())
        total_steps = len(self.step_widgets)
        self.create_button.setText(f"Crear Lista ({total_steps} pasos)")

    def on_name_changed(self, text: str):
        """Callback cuando cambia el nombre de la lista"""
        if not text.strip():
            self.name_validation_label.setText("⚠ El nombre no puede estar vacío")
            return

        if len(text) > 100:
            self.name_validation_label.setText("⚠ El nombre es demasiado largo (máx 100 caracteres)")
            return

        # Validar unicidad (si hay categoría seleccionada)
        category_id = self.category_combo.currentData()
        if category_id and text.strip():
            if not self.list_controller.db.is_list_name_unique(category_id, text.strip()):
                self.name_validation_label.setText("⚠ Ya existe una lista con este nombre en la categoría")
                return

        # Todo OK
        self.name_validation_label.setText("")

    def validate_form(self) -> tuple[bool, str]:
        """
        Valida el formulario completo

        Returns:
            Tuple (is_valid, error_message)
        """
        # Validar nombre
        list_name = self.name_input.text().strip()
        if not list_name:
            return False, "El nombre de la lista no puede estar vacío"

        if len(list_name) > 100:
            return False, "El nombre es demasiado largo (máximo 100 caracteres)"

        # Validar categoría
        category_id = self.category_combo.currentData()
        if not category_id:
            return False, "Debe seleccionar una categoría"

        # Validar pasos
        valid_steps = [w for w in self.step_widgets if w.has_label()]
        if len(valid_steps) == 0:
            return False, "Debe haber al menos 1 paso con nombre"

        return True, ""

    def on_tag_group_changed(self, tags: list):
        """Handle tag group selector changes"""
        try:
            # Actualizar el campo de tags comunes con los tags seleccionados
            if tags:
                self.common_tags_input.setText(", ".join(tags))
            else:
                self.common_tags_input.setText("")
            logger.debug(f"Common tags updated from tag group selector: {tags}")
        except Exception as e:
            logger.error(f"Error updating common tags from tag group selector: {e}")

    def get_steps_data(self) -> List[dict]:
        """
        Obtiene los datos de todos los pasos y les agrega los tags comunes

        Automáticamente agrega los tags ["lista", "nombre_de_la_lista"] a cada item

        Returns:
            Lista de diccionarios con datos de cada paso
        """
        # Obtener tags comunes del input
        common_tags_str = self.common_tags_input.text().strip()

        # Convertir tags comunes de string a lista
        common_tags_list = []
        if common_tags_str:
            # Parsear tags separados por coma
            common_tags_list = [tag.strip() for tag in common_tags_str.split(',') if tag.strip()]

        # Obtener nombre de la lista para agregar como tag
        list_name = self.name_input.text().strip()

        # Crear lista de tags automáticos: ["lista", "nombre_de_la_lista"]
        auto_tags = ["lista"]
        if list_name:
            auto_tags.append(list_name)

        # Combinar tags automáticos con tags comunes (sin duplicados)
        final_tags = auto_tags.copy()
        for tag in common_tags_list:
            if tag not in final_tags:
                final_tags.append(tag)

        steps_data = []
        for widget in self.step_widgets:
            data = widget.get_step_data()
            # Solo incluir pasos que tengan al menos label
            if data['label']:
                # Agregar lista de tags a este paso (como lista, no string)
                data['tags'] = final_tags.copy()
                steps_data.append(data)
        return steps_data

    def create_list(self):
        """Crea la lista usando el controlador"""
        # Validar formulario
        is_valid, error_msg = self.validate_form()
        if not is_valid:
            QMessageBox.warning(self, "Validación", error_msg)
            return

        # Obtener datos
        list_name = self.name_input.text().strip()
        category_id = self.category_combo.currentData()
        steps_data = self.get_steps_data()

        # Crear lista a través del controlador
        success, message, item_ids = self.list_controller.create_list(
            category_id=category_id,
            list_name=list_name,
            items_data=steps_data
        )

        if success:
            QMessageBox.information(self, "Éxito", message)
            self.list_created.emit(list_name, category_id, item_ids)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)

    def on_list_created_signal(self, list_name: str, category_id: int):
        """Callback cuando el controlador emite señal de lista creada"""
        logger.info(f"[LIST_CREATOR] List created signal received: {list_name}")

    def on_error_signal(self, error_message: str):
        """Callback cuando el controlador emite señal de error"""
        logger.error(f"[LIST_CREATOR] Error signal received: {error_message}")
