"""
Project Entity Selector Dialog - Diálogo para seleccionar entidades

Permite seleccionar entidades existentes (tags, items, categorías, listas, tablas, procesos)
o crear nuevas directamente desde el diálogo.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QTextEdit, QWidget, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
import logging

logger = logging.getLogger(__name__)


class ProjectEntitySelector(QDialog):
    """Diálogo para seleccionar una entidad para agregar al proyecto"""

    entity_selected = pyqtSignal(str, int, str)  # entity_type, entity_id, description

    def __init__(self, entity_type: str, db_manager, project_id: int = None, parent=None):
        """
        Args:
            entity_type: Tipo de entidad ('tag', 'item', 'category', 'list', 'table', 'process')
            db_manager: Instancia de DBManager
            project_id: ID del proyecto (opcional, para auto-agregar items creados)
            parent: Parent widget
        """
        super().__init__(parent)

        self.entity_type = entity_type
        self.db = db_manager
        self.project_id = project_id  # Guardar project_id
        self.selected_entity_id = None
        self.selected_entity = None

        # Configurar títulos según el tipo
        self.titles = {
            'tag': ('🏷️ Seleccionar Tag', 'Tags disponibles'),
            'item': ('📄 Seleccionar Item', 'Items disponibles'),
            'category': ('📂 Seleccionar Categoría', 'Categorías disponibles'),
            'list': ('📋 Seleccionar Lista', 'Listas disponibles'),
            'table': ('📊 Seleccionar Tabla', 'Tablas disponibles'),
            'process': ('⚙️ Seleccionar Proceso', 'Procesos disponibles'),
        }

        self.init_ui()
        self.load_entities()

    def init_ui(self):
        """Inicializa la interfaz"""
        title, list_title = self.titles.get(self.entity_type, ('Seleccionar', 'Elementos'))
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel(title)
        header.setStyleSheet("""
            QLabel {
                font-size: 14pt;
                font-weight: bold;
                color: #00ff88;
                padding: 10px;
            }
        """)
        layout.addWidget(header)

        # Búsqueda
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Buscar:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Buscar {self.entity_type}...")
        self.search_input.textChanged.connect(self.filter_entities)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Lista de entidades
        list_label = QLabel(list_title)
        list_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(list_label)

        self.entities_list = QListWidget()
        self.entities_list.itemClicked.connect(self.on_entity_clicked)
        self.entities_list.itemDoubleClicked.connect(self.on_entity_double_clicked)
        layout.addWidget(self.entities_list)

        # Descripción/comentario
        desc_label = QLabel("💬 Descripción/Comentario (opcional):")
        desc_label.setStyleSheet("font-weight: bold; color: #ffffff; margin-top: 10px;")
        layout.addWidget(desc_label)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Agrega un comentario o descripción para este elemento en el proyecto...")
        self.description_input.setMaximumHeight(80)
        layout.addWidget(self.description_input)

        # Preview del elemento seleccionado
        self.preview_frame = QFrame()
        self.preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.preview_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #00ff88;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        self.preview_frame.setVisible(False)

        preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_label = QLabel("Vista previa del elemento seleccionado")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #ffffff;")
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(self.preview_frame)

        # Botones
        buttons_layout = QHBoxLayout()

        # Botón crear nuevo
        create_btn = QPushButton(f"➕ Crear Nuevo {self.entity_type.title()}")
        create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        create_btn.setStyleSheet(self._get_button_style("#3498db"))
        create_btn.clicked.connect(self.on_create_new)
        buttons_layout.addWidget(create_btn)

        buttons_layout.addStretch()

        # Botón agregar
        self.add_btn = QPushButton("✅ Agregar al Proyecto")
        self.add_btn.setEnabled(False)
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.setStyleSheet(self._get_button_style("#00ff88"))
        self.add_btn.clicked.connect(self.on_add_clicked)
        buttons_layout.addWidget(self.add_btn)

        # Botón cancelar
        cancel_btn = QPushButton("❌ Cancelar")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        # Styling general
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
            }
            QTextEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #00ff88;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)

    def _get_button_style(self, color: str) -> str:
        """Retorna estilo para botones"""
        return f"""
            QPushButton {{
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid {color};
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #000000;
            }}
            QPushButton:disabled {{
                background-color: #1e1e1e;
                color: #555555;
                border-color: #3d3d3d;
            }}
        """

    def load_entities(self):
        """Carga las entidades disponibles según el tipo"""
        self.entities_list.clear()
        self.all_entities = []

        try:
            if self.entity_type == 'tag':
                self.all_entities = self.db.get_all_tags()
                for tag in self.all_entities:
                    item = QListWidgetItem(f"🏷️ {tag['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, tag)
                    self.entities_list.addItem(item)

            elif self.entity_type == 'item':
                # Obtener todos los items de todas las categorías
                categories = self.db.get_categories()
                for category in categories:
                    items = self.db.get_items_by_category(category['id'])
                    for item in items:
                        self.all_entities.append({
                            'id': item['id'],
                            'label': item['label'],
                            'content': item.get('content', ''),
                            'item_type': item.get('item_type', 'TEXT'),
                            'category_name': category['name']
                        })

                        list_item = QListWidgetItem(
                            f"📄 {item['label']} ({item.get('item_type', 'TEXT')}) - {category['name']}"
                        )
                        list_item.setData(Qt.ItemDataRole.UserRole, self.all_entities[-1])
                        self.entities_list.addItem(list_item)

            elif self.entity_type == 'category':
                categories = self.db.get_categories()
                for category in categories:
                    self.all_entities.append(category)
                    item = QListWidgetItem(f"{category.get('icon', '📂')} {category['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, category)
                    self.entities_list.addItem(item)

            elif self.entity_type == 'list':
                # Obtener listas de todas las categorías
                categories = self.db.get_categories()
                for category in categories:
                    lists_in_cat = self.db.get_listas_by_category_new(category['id'])
                    for lst in lists_in_cat:
                        self.all_entities.append(lst)
                        item = QListWidgetItem(f"📋 {lst['name']}")
                        item.setData(Qt.ItemDataRole.UserRole, lst)
                        self.entities_list.addItem(item)

            elif self.entity_type == 'table':
                tables = self.db.get_all_tables()
                for table in tables:
                    self.all_entities.append(table)
                    item = QListWidgetItem(f"📊 {table['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, table)
                    self.entities_list.addItem(item)

            elif self.entity_type == 'process':
                processes = self.db.get_all_processes()
                for process in processes:
                    self.all_entities.append(process)
                    item = QListWidgetItem(f"⚙️ {process['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, process)
                    self.entities_list.addItem(item)

            logger.info(f"Loaded {len(self.all_entities)} {self.entity_type}s")

        except Exception as e:
            logger.error(f"Error loading {self.entity_type}s: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Error al cargar {self.entity_type}s:\n{str(e)}"
            )

    def filter_entities(self, text: str):
        """Filtra la lista de entidades según el texto de búsqueda"""
        text = text.lower()

        for i in range(self.entities_list.count()):
            item = self.entities_list.item(i)
            item_text = item.text().lower()
            item.setHidden(text not in item_text)

    def on_entity_clicked(self, item: QListWidgetItem):
        """Al hacer clic en una entidad"""
        self.selected_entity = item.data(Qt.ItemDataRole.UserRole)
        self.selected_entity_id = self.selected_entity['id']
        self.add_btn.setEnabled(True)

        # Mostrar preview
        self._show_preview()

    def on_entity_double_clicked(self, item: QListWidgetItem):
        """Al hacer doble clic en una entidad - agregar directamente"""
        self.on_entity_clicked(item)
        self.on_add_clicked()

    def _show_preview(self):
        """Muestra preview del elemento seleccionado"""
        if not self.selected_entity:
            return

        self.preview_frame.setVisible(True)

        # Construir preview según el tipo
        preview_text = ""

        if self.entity_type == 'tag':
            preview_text = f"🏷️ Tag: {self.selected_entity['name']}\n"
            preview_text += f"ID: {self.selected_entity['id']}"

        elif self.entity_type == 'item':
            preview_text = f"📄 Item: {self.selected_entity['label']}\n"
            preview_text += f"Tipo: {self.selected_entity['item_type']}\n"
            preview_text += f"Categoría: {self.selected_entity['category_name']}\n"
            content = self.selected_entity.get('content', '')
            if content:
                preview_text += f"Contenido: {content[:100]}{'...' if len(content) > 100 else ''}"

        elif self.entity_type == 'category':
            preview_text = f"{self.selected_entity.get('icon', '📂')} Categoría: {self.selected_entity['name']}\n"
            preview_text += f"ID: {self.selected_entity['id']}"

        elif self.entity_type == 'list':
            preview_text = f"📋 Lista: {self.selected_entity['name']}\n"
            # Obtener la lista completa para acceder a category_id
            lista = self.db.get_lista(self.selected_entity['id'])
            if lista:
                items = self.db.get_list_items(lista['category_id'], lista['name'])
                preview_text += f"Items: {len(items)}"
            else:
                preview_text += f"Items: 0"

        elif self.entity_type == 'table':
            preview_text = f"📊 Tabla: {self.selected_entity['name']}\n"
            preview_text += f"ID: {self.selected_entity['id']}"

        elif self.entity_type == 'process':
            preview_text = f"⚙️ Proceso: {self.selected_entity['name']}\n"
            preview_text += f"ID: {self.selected_entity['id']}"

        self.preview_label.setText(preview_text)

    def on_add_clicked(self):
        """Al hacer clic en agregar"""
        if not self.selected_entity_id:
            QMessageBox.warning(self, "Error", "Selecciona un elemento primero")
            return

        description = self.description_input.toPlainText().strip()

        # Emitir señal con la selección
        self.entity_selected.emit(self.entity_type, self.selected_entity_id, description)

        logger.info(f"Selected {self.entity_type} ID: {self.selected_entity_id}")
        self.accept()

    def on_create_new(self):
        """Al hacer clic en crear nuevo"""
        try:
            # Abrir el diálogo apropiado según el tipo
            if self.entity_type == 'item':
                self._create_new_item()
            elif self.entity_type == 'category':
                self._create_new_category()
            elif self.entity_type == 'list':
                self._create_new_list()
            elif self.entity_type == 'table':
                self._create_new_table()
            elif self.entity_type == 'tag':
                self._create_new_tag()
            elif self.entity_type == 'process':
                self._create_new_process()

        except Exception as e:
            logger.error(f"Error creating new {self.entity_type}: {e}")
            QMessageBox.critical(self, "Error", f"Error al crear:\n{str(e)}")

    def _create_new_item(self):
        """Crea un nuevo item"""
        from views.dialogs.quick_create_dialog import QuickCreateDialog

        dialog = QuickCreateDialog(self.db, parent=self)

        # Conectar señal para auto-agregar al proyecto si existe
        if self.project_id:
            dialog.item_created_signal.connect(self._on_new_item_created)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Recargar lista
            self.load_entities()

    def _on_new_item_created(self, item_id: int, category_id: int):
        """Agrega automáticamente el item recién creado al proyecto"""
        if not self.project_id:
            return

        try:
            logger.info(f"Auto-adding item {item_id} to project {self.project_id}")

            # Agregar el item al proyecto automáticamente
            success = self.db.add_project_relation(
                project_id=self.project_id,
                entity_type='item',
                entity_id=item_id,
                description='Item creado desde gestor de proyectos',
                order_index=None  # Se calculará automáticamente
            )

            if success:
                logger.info(f"Item {item_id} auto-added to project {self.project_id}")
                # Seleccionar automáticamente el item recién creado
                self.selected_entity_id = item_id
                # Buscar el item en la lista y seleccionarlo
                for i in range(self.entity_list.count()):
                    item = self.entity_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == item_id:
                        self.entity_list.setCurrentItem(item)
                        break
            else:
                logger.error(f"Failed to auto-add item {item_id} to project")

        except Exception as e:
            logger.error(f"Error auto-adding item to project: {e}")

    def _create_new_category(self):
        """Crea una nueva categoría"""
        from views.dialogs.category_form_dialog import CategoryFormDialog

        dialog = CategoryFormDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_entities()

    def _create_new_list(self):
        """Crea una nueva lista"""
        from views.dialogs.list_creator_dialog import ListCreatorDialog

        dialog = ListCreatorDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_entities()

    def _create_new_table(self):
        """Crea una nueva tabla"""
        from views.dialogs.table_creator_wizard import TableCreatorWizard

        wizard = TableCreatorWizard(self.db, parent=self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self.load_entities()

    def _create_new_tag(self):
        """Crea un nuevo tag"""
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self,
            "Nuevo Tag",
            "Nombre del tag:",
        )

        if ok and name:
            tag_id = self.db.add_tag(name)
            if tag_id:
                QMessageBox.information(self, "Éxito", f"Tag '{name}' creado")
                self.load_entities()
            else:
                QMessageBox.warning(self, "Error", "No se pudo crear el tag")

    def _create_new_process(self):
        """Crea un nuevo proceso"""
        QMessageBox.information(
            self,
            "Crear Proceso",
            "Para crear un proceso, usa el botón 'Crear Proceso' del Menu"
        )
