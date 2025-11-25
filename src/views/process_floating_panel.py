"""
Process Floating Panel - Displays all items and lists from a process
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QScrollArea, QPushButton, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QTimer
from PyQt6.QtGui import QFont, QCursor
import sys
import logging
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.process import Process
from models.item import Item
from views.widgets.item_widget import ItemButton
from views.widgets.list_widget import ListWidget
from views.widgets.search_bar import SearchBar
from styles.futuristic_theme import get_theme
from styles.panel_styles import PanelStyles
from utils.panel_resizer import PanelResizer

# Get logger
logger = logging.getLogger(__name__)


class ProcessFloatingPanel(QWidget):
    """Floating panel to display all items and lists from a process"""

    # Signals
    item_clicked = pyqtSignal(object)  # Item object
    window_closed = pyqtSignal()
    pin_state_changed = pyqtSignal(bool)  # True = pinned, False = unpinned
    process_executed = pyqtSignal(int)  # Process ID when executing all steps
    customization_requested = pyqtSignal()

    def __init__(self, process_controller, config_manager, parent=None, main_window=None):
        super().__init__(parent)
        self.current_process = None
        self.process_controller = process_controller
        self.config_manager = config_manager
        self.main_window = main_window

        # Panel state
        self.is_pinned = False
        self.is_minimized = False
        self.normal_height = None
        self.normal_width = None

        # Items and lists from process
        self.all_items = []
        self.all_lists = []
        self.all_steps = []  # Store all steps for filtering

        # Search state
        self.search_query = ""

        # Theme
        self.theme = get_theme()

        # Get panel width from config (or use new default)
        if config_manager:
            self.panel_width = config_manager.get_setting('panel_width', PanelStyles.PANEL_WIDTH_DEFAULT)
        else:
            self.panel_width = PanelStyles.PANEL_WIDTH_DEFAULT

        # Panel resizer (will be initialized in init_ui)
        self.panel_resizer = None

        # Drag handling
        self.drag_position = QPoint()

        # Panel persistence attributes
        self.panel_id = None

        # Flag para animación de entrada (primera vez)
        self._first_show = True

        # AUTO-UPDATE: Timer for debounced panel state updates
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._save_panel_state_to_db)
        self.update_delay_ms = 1000

        self.init_ui()

    def init_ui(self):
        """Initialize the floating panel UI with new optimized design"""
        # Window properties
        self.setWindowTitle("Proceso - Items y Listas")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )

        # Set window size with new optimized dimensions
        self.setMinimumWidth(PanelStyles.PANEL_WIDTH_MIN)
        self.setMaximumWidth(PanelStyles.PANEL_WIDTH_MAX)
        self.setMinimumHeight(PanelStyles.PANEL_HEIGHT_MIN)
        self.setMaximumHeight(PanelStyles.PANEL_HEIGHT_MAX)
        self.resize(self.panel_width, PanelStyles.PANEL_HEIGHT_DEFAULT)

        # Enable mouse tracking for resizer
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Set window opacity
        self.setWindowOpacity(0.98)

        # Apply new panel styles
        self.setStyleSheet(PanelStyles.get_panel_style())

        # Initialize panel resizer
        self.panel_resizer = PanelResizer(
            widget=self,
            min_width=PanelStyles.PANEL_WIDTH_MIN,
            max_width=PanelStyles.PANEL_WIDTH_MAX,
            min_height=PanelStyles.PANEL_HEIGHT_MIN,
            max_height=PanelStyles.PANEL_HEIGHT_MAX,
            handle_size=PanelStyles.RESIZE_HANDLE_SIZE
        )
        # Connect resize signal
        self.panel_resizer.resized.connect(self.on_panel_resized)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        self.header_widget = self.create_header()
        main_layout.addWidget(self.header_widget)

        # Action bar (below header)
        self.action_bar = self.create_action_bar()
        main_layout.addWidget(self.action_bar)

        # Display options row with checkboxes
        self.display_options_widget = QWidget()
        self.display_options_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme.get_color('background_mid')};
                border-bottom: 1px solid {self.theme.get_color('surface')};
            }}
        """)
        display_options_layout = QHBoxLayout(self.display_options_widget)
        display_options_layout.setContentsMargins(15, 5, 15, 5)
        display_options_layout.setSpacing(15)

        # Label for the section
        display_label = QLabel("Mostrar:")
        display_label.setStyleSheet(f"""
            QLabel {{
                color: {self.theme.get_color('text_secondary')};
                font-size: 9pt;
                font-weight: bold;
            }}
        """)
        display_options_layout.addWidget(display_label)

        # Checkbox: Mostrar Labels (checked by default)
        self.show_labels_checkbox = QCheckBox("Labels")
        self.show_labels_checkbox.setChecked(True)  # Default: ON
        self.show_labels_checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.show_labels_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {self.theme.get_color('text_primary')};
                font-size: 9pt;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self.theme.get_color('primary')};
                border-radius: 3px;
                background-color: {self.theme.get_color('background_deep')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.theme.get_color('primary')};
                border-color: {self.theme.get_color('primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.theme.get_color('accent')};
            }}
        """)
        self.show_labels_checkbox.stateChanged.connect(self.on_display_options_changed)
        display_options_layout.addWidget(self.show_labels_checkbox)

        # Checkbox: Mostrar Tags
        self.show_tags_checkbox = QCheckBox("Tags")
        self.show_tags_checkbox.setChecked(False)  # Default: OFF
        self.show_tags_checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.show_tags_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {self.theme.get_color('text_primary')};
                font-size: 9pt;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self.theme.get_color('primary')};
                border-radius: 3px;
                background-color: {self.theme.get_color('background_deep')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.theme.get_color('primary')};
                border-color: {self.theme.get_color('primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.theme.get_color('accent')};
            }}
        """)
        self.show_tags_checkbox.stateChanged.connect(self.on_display_options_changed)
        display_options_layout.addWidget(self.show_tags_checkbox)

        # Checkbox: Mostrar Contenido
        self.show_content_checkbox = QCheckBox("Contenido")
        self.show_content_checkbox.setChecked(False)  # Default: OFF
        self.show_content_checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.show_content_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {self.theme.get_color('text_primary')};
                font-size: 9pt;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self.theme.get_color('primary')};
                border-radius: 3px;
                background-color: {self.theme.get_color('background_deep')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.theme.get_color('primary')};
                border-color: {self.theme.get_color('primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.theme.get_color('accent')};
            }}
        """)
        self.show_content_checkbox.stateChanged.connect(self.on_display_options_changed)
        display_options_layout.addWidget(self.show_content_checkbox)

        # Checkbox: Mostrar Descripción
        self.show_description_checkbox = QCheckBox("Descripción")
        self.show_description_checkbox.setChecked(False)  # Default: OFF
        self.show_description_checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.show_description_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {self.theme.get_color('text_primary')};
                font-size: 9pt;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self.theme.get_color('primary')};
                border-radius: 3px;
                background-color: {self.theme.get_color('background_deep')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.theme.get_color('primary')};
                border-color: {self.theme.get_color('primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.theme.get_color('accent')};
            }}
        """)
        self.show_description_checkbox.stateChanged.connect(self.on_display_options_changed)
        display_options_layout.addWidget(self.show_description_checkbox)

        # Add stretch to push checkboxes to the left
        display_options_layout.addStretch()

        main_layout.addWidget(self.display_options_widget)

        # Content area (scrollable) with new optimized spacing
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(PanelStyles.get_body_style())
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(
            PanelStyles.BODY_PADDING,
            PanelStyles.BODY_PADDING,
            PanelStyles.BODY_PADDING,
            PanelStyles.BODY_PADDING
        )
        self.content_layout.setSpacing(PanelStyles.ITEM_SPACING)
        self.content_layout.addStretch()

        # Scroll area with new optimized scrollbars
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            {PanelStyles.get_scroll_area_style()}
            {PanelStyles.get_scrollbar_style()}
        """)
        main_layout.addWidget(scroll_area)

    def create_header(self):
        """Create header with title and control buttons - New optimized design"""
        header = QWidget()
        header.setStyleSheet(PanelStyles.get_header_style())
        header.setFixedHeight(PanelStyles.HEADER_HEIGHT)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(
            PanelStyles.HEADER_PADDING_H,
            PanelStyles.HEADER_PADDING_V,
            PanelStyles.HEADER_PADDING_H,
            PanelStyles.HEADER_PADDING_V
        )
        layout.setSpacing(6)

        # Title with process icon
        title_label = QLabel("⚙️ PROCESO")
        title_label.setStyleSheet(PanelStyles.get_header_title_style())
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title_label)

        # Process name badge (compact)
        self.process_name_label = QLabel()
        self.process_name_label.setStyleSheet(PanelStyles.get_badge_style('default'))
        self.process_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.process_name_label)

        layout.addStretch()

        # "Copiar Todos" button (compact, no text)
        self.copy_all_button = QPushButton("📋")
        self.copy_all_button.setCheckable(True)
        self.copy_all_button.setFixedSize(PanelStyles.CLOSE_BUTTON_SIZE, PanelStyles.CLOSE_BUTTON_SIZE)
        self.copy_all_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_all_button.setStyleSheet(PanelStyles.get_close_button_style())
        self.copy_all_button.setToolTip("Copiar todos los items")
        self.copy_all_button.clicked.connect(self.on_copy_all_clicked)
        layout.addWidget(self.copy_all_button)

        # Edit/Config button
        edit_button = QPushButton("⚙")
        edit_button.setFixedSize(PanelStyles.CLOSE_BUTTON_SIZE, PanelStyles.CLOSE_BUTTON_SIZE)
        edit_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit_button.setStyleSheet(PanelStyles.get_close_button_style())
        edit_button.setToolTip("Editar proceso")
        edit_button.clicked.connect(self.on_edit_process_clicked)
        layout.addWidget(edit_button)

        # Pin button
        self.pin_button = QPushButton("📌")
        self.pin_button.setFixedSize(PanelStyles.CLOSE_BUTTON_SIZE, PanelStyles.CLOSE_BUTTON_SIZE)
        self.pin_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pin_button.setStyleSheet(PanelStyles.get_close_button_style())
        self.pin_button.setToolTip("Anclar panel")
        self.pin_button.clicked.connect(self.on_pin_clicked)
        layout.addWidget(self.pin_button)

        # Minimize button (only visible when pinned)
        self.minimize_button = QPushButton("−")
        self.minimize_button.setFixedSize(PanelStyles.CLOSE_BUTTON_SIZE, PanelStyles.CLOSE_BUTTON_SIZE)
        self.minimize_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.minimize_button.setStyleSheet(PanelStyles.get_close_button_style())
        self.minimize_button.setToolTip("Minimizar")
        self.minimize_button.clicked.connect(self.on_minimize_clicked)
        self.minimize_button.setVisible(False)
        layout.addWidget(self.minimize_button)

        # Close button
        close_button = QPushButton("✕")
        close_button.setFixedSize(PanelStyles.CLOSE_BUTTON_SIZE, PanelStyles.CLOSE_BUTTON_SIZE)
        close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_button.setStyleSheet(PanelStyles.get_close_button_style())
        close_button.setToolTip("Cerrar")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        return header

    def create_action_bar(self):
        """Create action bar below header"""
        action_bar = QWidget()
        action_bar.setFixedHeight(50)
        action_bar.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3d3d3d;
            }
        """)

        layout = QHBoxLayout(action_bar)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # Steps counter label
        self.steps_label = QLabel("0 pasos")
        self.steps_label.setStyleSheet("""
            QLabel {
                color: #00ff88;
                font-size: 9pt;
                font-weight: bold;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.steps_label)

        # Search bar
        self.search_bar = SearchBar(placeholder="Buscar en pasos...")
        self.search_bar.setFixedWidth(250)
        self.search_bar.search_changed.connect(self.on_search_changed)
        layout.addWidget(self.search_bar)

        layout.addStretch()

        return action_bar

    def load_process(self, process: Process):
        """Load process and all its items/lists"""
        try:
            logger.info(f"Loading process: {process.name} (ID: {process.id})")
            self.current_process = process

            # Update header
            self.process_name_label.setText(process.name)

            # Get all steps
            steps = self.process_controller.get_process_steps(process.id)
            logger.info(f"Found {len(steps)} steps")

            # Store all steps for filtering
            self.all_steps = steps

            # Update steps counter
            self.steps_label.setText(f"{len(steps)} paso{'s' if len(steps) != 1 else ''}")

            # Clear existing content
            self.clear_content()

            # Extract and display items/lists from steps
            self.all_items = []
            self.all_lists = []

            # Display steps (apply current search if any)
            self.apply_search_filter()

            # Show panel
            self.show()

        except Exception as e:
            logger.error(f"Error loading process: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar proceso:\n{str(e)}"
            )

    def display_step(self, step, step_number=None):
        """Display a single step with its item or list

        Args:
            step: ProcessStep object
            step_number: Display number for the step (1-based). If None, uses step.step_order + 1
        """
        # Create step container
        step_widget = QWidget()
        step_layout = QVBoxLayout(step_widget)
        step_layout.setContentsMargins(0, 0, 0, 10)
        step_layout.setSpacing(5)

        # Determine step number to display
        if step_number is None:
            step_number = step.step_order + 1

        # Check if this step is a component
        is_component = getattr(step, 'is_component', False) or (
            hasattr(step, 'item_id') and step.item_id
        )

        # Display item for this step
        if step.item_id:
            item_dict = self.config_manager.db.get_item(step.item_id)
            if item_dict:
                # Check if item is a component
                is_component = item_dict.get('is_component', False)

                if is_component:
                    # Render as component (no step header for components)
                    component_type = item_dict.get('name_component')
                    component_config = item_dict.get('component_config', '{}')
                    label = item_dict.get('label', '')
                    content = item_dict.get('content', '')

                    # Import component widgets
                    from views.widgets.component_widgets import create_component_widget

                    # Create component widget
                    component_widget = create_component_widget(
                        component_type=component_type,
                        config=component_config,
                        label=label,
                        content=content,
                        parent=step_widget
                    )
                    step_layout.addWidget(component_widget)
                else:
                    # Step header for regular items
                    step_header = QLabel(f"Paso {step_number}")
                    step_header.setStyleSheet("""
                        QLabel {
                            color: #00ff88;
                            font-size: 10pt;
                            font-weight: bold;
                            padding: 5px;
                            border-bottom: 1px solid #3d3d3d;
                            background-color: transparent;
                        }
                    """)
                    step_layout.addWidget(step_header)

                    # Create horizontal layout for item and action buttons
                    item_row_widget = QWidget()
                    item_row_layout = QHBoxLayout(item_row_widget)
                    item_row_layout.setContentsMargins(0, 0, 0, 0)
                    item_row_layout.setSpacing(8)

                    # Convert dict to Item object and display as regular item
                    item = Item.from_dict(item_dict)
                    self.all_items.append(item)

                    # Get display options from checkboxes
                    show_labels = self.show_labels_checkbox.isChecked()
                    show_tags = self.show_tags_checkbox.isChecked()
                    show_content = self.show_content_checkbox.isChecked()
                    show_description = self.show_description_checkbox.isChecked()

                    item_widget = ItemButton(
                        item,
                        show_category=False,
                        show_labels=show_labels,
                        show_tags=show_tags,
                        show_content=show_content,
                        show_description=show_description,
                        parent=self
                    )
                    item_widget.item_clicked.connect(lambda i=item: self.on_item_clicked(i))
                    item_row_layout.addWidget(item_widget, stretch=1)

                    # Add action buttons based on item type
                    item_type = step.item_type  # Get item type from ProcessStep

                    if item_type == "URL":
                        # Open in embedded browser button
                        embedded_url_button = QPushButton("🌐")
                        embedded_url_button.setFixedSize(35, 35)
                        embedded_url_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                        embedded_url_button.setStyleSheet("""
                            QPushButton {
                                background-color: #007acc;
                                color: #ffffff;
                                border: none;
                                border-radius: 4px;
                                font-size: 16pt;
                            }
                            QPushButton:hover {
                                background-color: #005a9e;
                            }
                            QPushButton:pressed {
                                background-color: #004578;
                            }
                        """)
                        embedded_url_button.setToolTip("Abrir en navegador embebido")
                        embedded_url_button.clicked.connect(lambda checked, content=step.item_content: self.on_embedded_url_button_clicked(content))
                        item_row_layout.addWidget(embedded_url_button)

                        # Open in system browser button
                        external_url_button = QPushButton("🔗")
                        external_url_button.setFixedSize(35, 35)
                        external_url_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                        external_url_button.setStyleSheet("""
                            QPushButton {
                                background-color: #0078d4;
                                color: #ffffff;
                                border: none;
                                border-radius: 4px;
                                font-size: 16pt;
                            }
                            QPushButton:hover {
                                background-color: #106ebe;
                            }
                            QPushButton:pressed {
                                background-color: #005a9e;
                            }
                        """)
                        external_url_button.setToolTip("Abrir en navegador predeterminado del sistema")
                        external_url_button.clicked.connect(lambda checked, content=step.item_content: self.on_external_url_button_clicked(content))
                        item_row_layout.addWidget(external_url_button)

                    elif item_type == "CODE":
                        # CODE button - execute command
                        code_button = QPushButton("▶️")
                        code_button.setFixedSize(32, 32)
                        code_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                        code_button.setStyleSheet("""
                            QPushButton {
                                background-color: #3d3d3d;
                                color: #00ff88;
                                border: 1px solid #555555;
                                border-radius: 16px;
                                font-size: 12pt;
                            }
                            QPushButton:hover {
                                background-color: #00ff88;
                                color: #000000;
                                border-color: #00ff88;
                            }
                        """)
                        code_button.setToolTip(f"Ejecutar comando: {step.item_content}")
                        code_button.clicked.connect(lambda checked, content=step.item_content: self.on_code_button_clicked(content))
                        item_row_layout.addWidget(code_button)

                    elif item_type == "PATH":
                        # PATH button - open file/folder
                        path_button = QPushButton("📁")
                        path_button.setFixedSize(32, 32)
                        path_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                        path_button.setStyleSheet("""
                            QPushButton {
                                background-color: #3d3d3d;
                                color: #ff6b00;
                                border: 1px solid #555555;
                                border-radius: 16px;
                                font-size: 12pt;
                            }
                            QPushButton:hover {
                                background-color: #ff6b00;
                                color: #000000;
                                border-color: #ff6b00;
                            }
                        """)
                        path_button.setToolTip(f"Abrir ruta: {step.item_content}")
                        path_button.clicked.connect(lambda checked, content=step.item_content: self.on_path_button_clicked(content))
                        item_row_layout.addWidget(path_button)

                    step_layout.addWidget(item_row_widget)
            else:
                logger.warning(f"Item {step.item_id} not found for step {step.id}")

        # Add to main content
        self.content_layout.insertWidget(self.content_layout.count() - 1, step_widget)

    def clear_content(self):
        """Clear all content widgets"""
        while self.content_layout.count() > 1:  # Keep the stretch
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.all_items = []
        self.all_lists = []

    def on_item_clicked(self, item: Item):
        """Handle item click"""
        logger.info(f"Item clicked: {item.label}")
        self.item_clicked.emit(item)

    def on_copy_all_clicked(self, checked: bool):
        """Copy all items from the process to clipboard"""
        if not self.current_process:
            return

        try:
            logger.info(f"Executing process: {self.current_process.name}")

            # Execute process (copy all steps)
            success = self.process_controller.executor.execute_process(self.current_process.id)

            if success:
                logger.info("Process executed successfully")
                # Show visual feedback
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"✓ Proceso '{self.current_process.name}' ejecutado\nTodo copiado al portapapeles"
                )
                # Emit signal
                self.process_executed.emit(self.current_process.id)
            else:
                logger.error("Process execution failed")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"✗ Error al ejecutar proceso '{self.current_process.name}'"
                )

        except Exception as e:
            logger.error(f"Exception executing process: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al ejecutar proceso:\n{str(e)}"
            )
        finally:
            # Uncheck button
            self.copy_all_button.setChecked(False)

    def on_pin_clicked(self):
        """Toggle pin state"""
        self.is_pinned = not self.is_pinned

        # Update button icon and tooltip
        if self.is_pinned:
            self.pin_button.setText("📍")
            self.pin_button.setToolTip("Desanclar panel")
            # Update header color
            self.header_widget.setStyleSheet("""
                QWidget {
                    background-color: #ff8800;
                    border-top-left-radius: 10px;
                    border-top-right-radius: 10px;
                }
            """)
            # Show minimize button
            self.minimize_button.setVisible(True)
        else:
            self.pin_button.setText("📌")
            self.pin_button.setToolTip("Anclar panel")
            # Restore header color
            self.header_widget.setStyleSheet("""
                QWidget {
                    background-color: #007acc;
                    border-top-left-radius: 10px;
                    border-top-right-radius: 10px;
                }
            """)
            # Hide minimize button
            self.minimize_button.setVisible(False)
            # Restore if minimized
            if self.is_minimized:
                self.on_minimize_clicked()

        # Emit signal
        self.pin_state_changed.emit(self.is_pinned)

        logger.info(f"Panel pin state: {self.is_pinned}")

        # Save to database if pinned, delete if unpinned
        if self.is_pinned:
            self.schedule_panel_update()
        else:
            self.delete_from_database()

    def on_minimize_clicked(self):
        """Toggle minimize state (only if pinned)"""
        if not self.is_pinned:
            return

        self.is_minimized = not self.is_minimized

        if self.is_minimized:
            # Save current size
            self.normal_height = self.height()
            self.normal_width = self.width()

            # Minimize to header only - hide all content widgets
            self.content_widget.hide()
            self.action_bar.hide()
            self.display_options_widget.hide()
            self.setFixedHeight(60)
            self.minimize_button.setText("□")
            self.minimize_button.setToolTip("Restaurar")
        else:
            # Restore size - show all content widgets
            self.content_widget.show()
            self.action_bar.show()
            self.display_options_widget.show()
            # Remove ALL height constraints first
            self.setMinimumHeight(0)  # Remove minimum temporarily
            self.setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX
            self.setFixedHeight(16777215)  # Remove fixed height
            # Set proper minimum height
            self.setMinimumHeight(400)
            self.setMaximumHeight(16777215)
            # Restore to original size
            if self.normal_height:
                self.resize(self.normal_width, self.normal_height)
            self.minimize_button.setText("−")
            self.minimize_button.setToolTip("Minimizar")

        logger.info(f"Panel minimized: {self.is_minimized}")

        # Save state change to database
        self.schedule_panel_update()

    def on_edit_process_clicked(self):
        """Open ProcessBuilderWindow to edit current process"""
        if not self.current_process:
            return

        try:
            logger.info(f"Editing process: {self.current_process.name}")

            # Import ProcessBuilderWindow
            from views.process_builder_window import ProcessBuilderWindow

            # Create and show edit window (pass process_id, not process object)
            edit_window = ProcessBuilderWindow(
                config_manager=self.config_manager,
                process_controller=self.process_controller,
                process_id=self.current_process.id,
                parent=self.main_window
            )

            # Connect save signal to reload panel
            edit_window.process_saved.connect(self.on_process_edited)

            # Show window
            edit_window.show()

        except Exception as e:
            logger.error(f"Error opening process editor: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir editor de proceso:\n{str(e)}"
            )

    def on_process_edited(self, process_id: int):
        """Handle process edited - reload panel"""
        try:
            logger.info(f"Process {process_id} was edited, reloading panel")

            # Get updated process
            process = self.process_controller.get_process(process_id)
            if process:
                # Reload panel with updated process
                self.load_process(process)
            else:
                logger.warning(f"Process {process_id} not found after edit")

        except Exception as e:
            logger.error(f"Error reloading process after edit: {e}", exc_info=True)

    def showEvent(self, event):
        """Handler al mostrar ventana - aplicar animación de entrada"""
        super().showEvent(event)

        if self._first_show:
            self._first_show = False
            # Aplicar animación de fade-in con las nuevas animaciones de PanelStyles
            animation = PanelStyles.create_fade_in_animation(self, duration=200)
            animation.start()
            # Guardar referencia para que no se destruya
            self._show_animation = animation

    def closeEvent(self, event):
        """Handle window close event"""
        # Si ya estamos cerrando con animación, aceptar y salir
        if hasattr(self, '_closing_with_animation') and self._closing_with_animation:
            logger.info("Process panel closing (animation complete)")
            self.window_closed.emit()
            event.accept()
            return

        # Primera vez: iniciar animación
        event.ignore()
        logger.info("Process panel closing (starting animation)")

        # Marcar que estamos en proceso de cierre
        self._closing_with_animation = True

        # Crear y ejecutar animación de fade-out
        animation = PanelStyles.create_fade_out_animation(self, duration=150)

        # Cuando termine la animación, cerrar realmente
        def on_animation_finished():
            # Usar QWidget.close() directamente para evitar recursión
            QWidget.close(self)

        animation.finished.connect(on_animation_finished)
        animation.start()

        # Guardar referencia para que no se destruya
        self._close_animation = animation

    # Search functionality
    def on_search_changed(self, query: str):
        """Handle search query change"""
        self.search_query = query.lower().strip()
        logger.info(f"Search query changed: '{self.search_query}'")
        self.apply_search_filter()

    def on_display_options_changed(self):
        """Handle changes in display options checkboxes - refresh item widgets"""
        logger.info("Display options changed - refreshing items")

        # Get current display state
        show_labels = self.show_labels_checkbox.isChecked()
        show_tags = self.show_tags_checkbox.isChecked()
        show_content = self.show_content_checkbox.isChecked()
        show_description = self.show_description_checkbox.isChecked()

        logger.debug(f"Display options: labels={show_labels}, tags={show_tags}, content={show_content}, description={show_description}")

        # Re-render all items with new display options
        self.apply_search_filter()

    def apply_search_filter(self):
        """Apply search filter to steps"""
        # Clear current content
        while self.content_layout.count() > 1:  # Keep the stretch
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.all_items = []
        self.all_lists = []

        # If no search query, show all steps with consecutive numbering
        if not self.search_query:
            step_counter = 1
            for step in self.all_steps:
                # Only increment counter for non-component steps
                item_dict = self.config_manager.db.get_item(step.item_id) if step.item_id else None
                is_component = item_dict.get('is_component', False) if item_dict else False

                if is_component:
                    # Components don't get numbered
                    self.display_step(step, step_number=None)
                else:
                    # Regular items get consecutive numbering
                    self.display_step(step, step_number=step_counter)
                    step_counter += 1
            return

        # Filter steps based on search query with consecutive numbering
        step_counter = 1
        for step in self.all_steps:
            if self.step_matches_search(step):
                # Check if it's a component
                item_dict = self.config_manager.db.get_item(step.item_id) if step.item_id else None
                is_component = item_dict.get('is_component', False) if item_dict else False

                if is_component:
                    # Components don't get numbered
                    self.display_step(step, step_number=None)
                else:
                    # Regular items get consecutive numbering
                    self.display_step(step, step_number=step_counter)
                    step_counter += 1

    def step_matches_search(self, step) -> bool:
        """Check if step matches search query"""
        if not self.search_query:
            return True

        # Search in step group name
        if step.group_name and self.search_query in step.group_name.lower():
            return True

        # Search in custom label
        if step.custom_label and self.search_query in step.custom_label.lower():
            return True

        # Search in item if this step has an item
        if step.item_id:
            item_dict = self.config_manager.db.get_item(step.item_id)
            if item_dict:
                # Search in item label (dict access)
                if item_dict.get('label') and self.search_query in item_dict.get('label', '').lower():
                    return True
                # Search in item content (dict access)
                if item_dict.get('content') and self.search_query in item_dict.get('content', '').lower():
                    return True

        return False

    # Panel persistence methods
    def _save_panel_state_to_db(self):
        """Save panel state to database (called after debounce timer)"""
        if not self.is_pinned or not self.current_process:
            return

        try:
            if self.panel_id:
                # Update existing panel
                self.config_manager.db.update_pinned_process_panel(
                    self.panel_id,
                    x_position=self.x(),
                    y_position=self.y(),
                    width=self.width(),
                    height=self.height(),
                    is_minimized=self.is_minimized
                )
                logger.debug(f"Process panel state updated in DB: {self.panel_id}")
            else:
                # Create new panel entry
                self.panel_id = self.config_manager.db.save_pinned_process_panel(
                    process_id=self.current_process.id,
                    x_pos=self.x(),
                    y_pos=self.y(),
                    width=self.width(),
                    height=self.height(),
                    is_minimized=self.is_minimized
                )
                logger.info(f"Process panel saved to DB with ID: {self.panel_id}")

        except Exception as e:
            logger.error(f"Error saving process panel state: {e}", exc_info=True)

    def schedule_panel_update(self):
        """Schedule a debounced panel state update"""
        if not self.is_pinned:
            return
        self.update_timer.start(self.update_delay_ms)

    def delete_from_database(self):
        """Delete panel from database"""
        if self.panel_id:
            try:
                self.config_manager.db.delete_pinned_process_panel(self.panel_id)
                logger.info(f"Process panel {self.panel_id} deleted from database")
                self.panel_id = None
            except Exception as e:
                logger.error(f"Error deleting process panel from database: {e}", exc_info=True)

    # ========== ACTION BUTTON HANDLERS ==========

    def on_embedded_url_button_clicked(self, url: str):
        """Handle embedded browser button click - open URL in embedded browser"""
        try:
            # Ensure URL has proper protocol
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    url = 'https://' + url

            # Use main window's method (same as floating panel does)
            if self.main_window and hasattr(self.main_window, 'on_url_open_in_browser'):
                self.main_window.on_url_open_in_browser(url)
                logger.info(f"Opening URL in embedded browser: {url}")
            else:
                logger.warning("Main window does not have on_url_open_in_browser method")
                QMessageBox.warning(
                    self,
                    "No disponible",
                    "El navegador embebido no está disponible"
                )
        except Exception as e:
            logger.error(f"Error opening URL in embedded browser: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Error",
                f"No se pudo abrir la URL:\n{url}\n\nError: {str(e)}"
            )

    def on_external_url_button_clicked(self, url: str):
        """Handle external URL button click - open in system default browser"""
        try:
            import webbrowser

            # Ensure URL has proper protocol
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    url = 'https://' + url

            webbrowser.open(url)
            logger.info(f"Opening URL in system browser: {url}")
        except Exception as e:
            logger.error(f"Error opening URL {url}: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Error",
                f"No se pudo abrir la URL:\n{url}\n\nError: {str(e)}"
            )

    def on_code_button_clicked(self, command: str):
        """Handle CODE button click - execute command"""
        try:
            import subprocess

            # Confirmation dialog
            reply = QMessageBox.question(
                self,
                "Ejecutar Comando",
                f"¿Ejecutar el siguiente comando?\n\n{command}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Execute command in shell
                if command.strip():
                    # Run command in background without waiting
                    subprocess.Popen(
                        command,
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    logger.info(f"Executing command: {command}")

                    # Show feedback
                    QMessageBox.information(
                        self,
                        "Comando Ejecutado",
                        f"Comando ejecutado:\n{command}"
                    )
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo ejecutar el comando:\n{command}\n\nError: {str(e)}"
            )

    def on_path_button_clicked(self, path: str):
        """Handle PATH button click - open file or folder"""
        try:
            import os
            import subprocess

            # Check if path exists
            if not os.path.exists(path):
                QMessageBox.warning(
                    self,
                    "Ruta No Encontrada",
                    f"La ruta no existe:\n{path}"
                )
                return

            # Open with default application
            if os.name == 'nt':  # Windows
                os.startfile(path)
            elif os.name == 'posix':  # Linux/Mac
                subprocess.Popen(['xdg-open', path])

            logger.info(f"Opening path: {path}")

        except Exception as e:
            logger.error(f"Error opening path {path}: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo abrir la ruta:\n{path}\n\nError: {str(e)}"
            )

    def on_panel_resized(self, width: int, height: int):
        """Handle panel resize completion from PanelResizer"""
        logger.info(f"Process Panel resized to: {width}x{height}")

        # Save new dimensions to config
        if self.config_manager:
            self.config_manager.set_setting('panel_width', width)
            self.config_manager.set_setting('panel_height', height)

            # Save to panel_settings table if db_manager is available
            if hasattr(self.config_manager, 'db_manager') and self.config_manager.db_manager:
                self.config_manager.db_manager.save_panel_settings(
                    panel_name='process_floating_panel',
                    width=width,
                    height=height,
                    x=self.x(),
                    y=self.y()
                )

        # Trigger auto-save for pinned panels
        if self.is_pinned and self.panel_id:
            self.schedule_panel_update()

    def smooth_scroll_to(self, value: int, duration: int = 300):
        """
        Anima el scroll vertical hacia un valor específico

        Args:
            value: Valor objetivo del scroll (0 = arriba, max = abajo)
            duration: Duración de la animación en milisegundos (default: 300ms)
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        animation = PanelStyles.create_smooth_scroll_animation(scroll_bar, value, duration)
        animation.start()
        # Guardar referencia para que no se destruya
        self._scroll_animation = animation

    def smooth_scroll_to_top(self, duration: int = 300):
        """Anima el scroll hacia arriba"""
        self.smooth_scroll_to(0, duration)

    def smooth_scroll_to_bottom(self, duration: int = 300):
        """Anima el scroll hacia abajo"""
        scroll_bar = self.scroll_area.verticalScrollBar()
        self.smooth_scroll_to(scroll_bar.maximum(), duration)

    def moveEvent(self, event):
        """Handle window move - schedule panel state update"""
        super().moveEvent(event)
        self.schedule_panel_update()
