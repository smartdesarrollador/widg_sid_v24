"""
Processes Floating Panel - Panel flotante para listar, buscar y ejecutar procesos

Layout:
- Header con contador y botones (pin, minimize, config, close)
- Barra de acciones (filtros avanzados, ejecutar todos, estado)
- Barra de busqueda
- Lista de procesos (scroll area)
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                             QPushButton, QComboBox, QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.process import Process
from views.widgets.search_bar import SearchBar
from core.pinned_panels_manager import PinnedPanelsManager

# Get logger
logger = logging.getLogger(__name__)


class ProcessesFloatingPanel(QWidget):
    """Floating panel for viewing, searching and executing processes"""

    # Signals
    process_executed = pyqtSignal(int)  # process_id
    process_edited = pyqtSignal(int)    # process_id
    process_deleted = pyqtSignal(int)   # process_id
    window_closed = pyqtSignal()
    pin_state_changed = pyqtSignal(bool)  # True = pinned, False = unpinned

    def __init__(self, db_manager=None, config_manager=None, process_controller=None,
                 parent=None, main_window=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.process_controller = process_controller
        self.main_window = main_window

        # Store all processes
        self.all_processes = []
        self.visible_processes = []

        # Current filters
        self.current_search_query = ""
        self.current_state_filter = "normal"  # normal, archived, inactive, all

        # Search timer for debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        self.pending_search_query = ""

        # Auto-save timer
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._save_panel_state_to_db)
        self.update_delay_ms = 1000  # 1 second delay

        # Pinned panel properties
        self.is_pinned = False
        self.panel_id = None
        self.panel_name = "Procesos"
        self.panel_color = "#ff6b00"  # Orange color

        # Minimized state
        self.is_minimized = False
        self.normal_height = None
        self.normal_width = None
        self.normal_position = None

        # Pinned panels manager
        self.panels_manager = None
        if self.db_manager:
            self.panels_manager = PinnedPanelsManager(self.db_manager)

        # Get panel width from config
        if config_manager:
            self.panel_width = config_manager.get_setting('panel_width', 500)
        else:
            self.panel_width = 500

        # Resize handling
        self.resizing = False
        self.resize_start_x = 0
        self.resize_start_width = 0
        self.resize_edge_width = 15

        self.init_ui()

    def init_ui(self):
        """Initialize the floating panel UI"""
        # Window properties
        self.setWindowTitle("Widget Sidebar - Procesos")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )

        # Calculate window height: 80% of screen height
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_height = screen.availableGeometry().height()
            window_height = int(screen_height * 0.8)
        else:
            window_height = 600

        # Set window size
        self.setMinimumWidth(300)
        self.setMaximumWidth(1000)
        self.setMinimumHeight(400)
        self.resize(self.panel_width, window_height)

        # Enable mouse tracking for resize
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Set window opacity
        self.setWindowOpacity(0.95)

        # Don't close application when closing this window
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        # Set background - orange border for processes
        self.setStyleSheet("""
            ProcessesFloatingPanel {
                background-color: #252525;
                border: 2px solid #ff6b00;
                border-left: 5px solid #ff6b00;
                border-radius: 8px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== HEADER ==========
        self.create_header(main_layout)

        # ========== ACTION BAR ==========
        self.create_action_bar(main_layout)

        # ========== SEARCH BAR ==========
        self.create_search_bar(main_layout)

        # ========== PROCESSES LIST ==========
        self.create_processes_list(main_layout)

    def create_header(self, parent_layout):
        """Create header with title, counter and buttons"""
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("""
            QWidget {
                background-color: #252525;
                border-radius: 6px 6px 0 0;
            }
        """)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(15, 10, 10, 10)
        header_layout.setSpacing(5)

        # Title with counter
        self.header_label = QLabel("⚙️ Procesos (0)")
        self.header_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.header_label)

        # Filter badge (shows number of active filters)
        self.filter_badge = QLabel()
        self.filter_badge.setVisible(False)
        self.filter_badge.setStyleSheet("""
            QLabel {
                background-color: #ff6b00;
                color: white;
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        self.filter_badge.setToolTip("Filtros activos")
        header_layout.addWidget(self.filter_badge)

        # Pin button
        self.pin_button = QPushButton("📍")
        self.pin_button.setFixedSize(32, 32)
        self.pin_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pin_button.setToolTip("Anclar panel")
        self.pin_button.clicked.connect(self.toggle_pin)
        self.pin_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14pt;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """)
        header_layout.addWidget(self.pin_button)

        # Minimize button (only visible when pinned)
        self.minimize_button = QPushButton("➖")
        self.minimize_button.setFixedSize(32, 32)
        self.minimize_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.minimize_button.setToolTip("Minimizar panel")
        self.minimize_button.clicked.connect(self.toggle_minimize)
        self.minimize_button.setVisible(False)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """)
        header_layout.addWidget(self.minimize_button)

        # Config button (only visible when pinned)
        self.config_button = QPushButton("⚙️")
        self.config_button.setFixedSize(32, 32)
        self.config_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.config_button.setToolTip("Configurar panel")
        self.config_button.clicked.connect(self.show_panel_configuration)
        self.config_button.setVisible(False)
        self.config_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """)
        header_layout.addWidget(self.config_button)

        # Close button
        close_button = QPushButton("✕")
        close_button.setFixedSize(24, 24)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                font-size: 12pt;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
            }
        """)
        close_button.clicked.connect(self.hide)
        header_layout.addWidget(close_button)

        parent_layout.addWidget(self.header_widget)

    def create_action_bar(self, parent_layout):
        """Create action bar with filters, execute all, and state combo"""
        self.action_widget = QWidget()
        self.action_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        action_layout = QHBoxLayout(self.action_widget)
        action_layout.setContentsMargins(8, 5, 8, 5)
        action_layout.setSpacing(8)

        # Advanced filters button
        self.filters_button = QPushButton("🔍 Filtros Avanzados")
        self.filters_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.filters_button.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b00,
                    stop:1 #ff8c00
                );
            }
            QPushButton:pressed {
                background-color: #252525;
            }
        """)
        self.filters_button.clicked.connect(self.on_advanced_filters_clicked)
        action_layout.addWidget(self.filters_button)

        # Execute all button
        self.execute_all_button = QPushButton("📋 Ejecutar Todos")
        self.execute_all_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.execute_all_button.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff88,
                    stop:1 #00ccff
                );
            }
            QPushButton:pressed {
                background-color: #252525;
            }
        """)
        self.execute_all_button.setToolTip("Ejecutar todos los procesos visibles secuencialmente")
        self.execute_all_button.clicked.connect(self.on_execute_all_clicked)
        action_layout.addWidget(self.execute_all_button)

        # State filter combo
        self.state_filter_combo = QComboBox()
        self.state_filter_combo.addItem("📄 Normal", "normal")
        self.state_filter_combo.addItem("📦 Archivados", "archived")
        self.state_filter_combo.addItem("⏸️ Inactivos", "inactive")
        self.state_filter_combo.addItem("📋 Todos", "all")
        self.state_filter_combo.setCurrentIndex(0)
        self.state_filter_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.state_filter_combo.setStyleSheet("""
            QComboBox {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 10pt;
                min-width: 120px;
            }
            QComboBox:hover {
                background-color: #3d3d3d;
                border-color: #ff6b00;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid white;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #ff6b00;
                selection-color: #ffffff;
                border: 1px solid #3d3d3d;
                outline: none;
            }
        """)
        self.state_filter_combo.currentIndexChanged.connect(self.on_state_filter_changed)
        action_layout.addWidget(self.state_filter_combo)

        parent_layout.addWidget(self.action_widget)

    def create_search_bar(self, parent_layout):
        """Create search bar"""
        self.search_widget = QWidget()
        self.search_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        search_layout = QVBoxLayout(self.search_widget)
        search_layout.setContentsMargins(8, 5, 8, 5)
        search_layout.setSpacing(0)

        # Search bar
        self.search_bar = SearchBar()
        self.search_bar.setPlaceholderText("🔍 Buscar proceso...")
        self.search_bar.search_changed.connect(self.on_search_triggered)
        search_layout.addWidget(self.search_bar)

        parent_layout.addWidget(self.search_widget)

    def create_processes_list(self, parent_layout):
        """Create scrollable processes list"""
        # Scroll area for processes
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #ff6b00;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #2d2d2d;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555555;
                border-radius: 6px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #ff6b00;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        # Container for process widgets
        self.processes_container = QWidget()
        self.processes_layout = QVBoxLayout(self.processes_container)
        self.processes_layout.setContentsMargins(8, 8, 8, 8)
        self.processes_layout.setSpacing(8)
        self.processes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.processes_container)
        parent_layout.addWidget(self.scroll_area)

    # ========== SEARCH AND FILTER ==========

    def on_search_triggered(self, query: str):
        """Handle search input with debouncing"""
        self.pending_search_query = query
        self.search_timer.start(300)  # 300ms debounce

    def _perform_search(self):
        """Perform the actual search"""
        self.current_search_query = self.pending_search_query
        self.apply_filters()

    def on_state_filter_changed(self, index: int):
        """Handle state filter change"""
        self.current_state_filter = self.state_filter_combo.currentData()
        self.apply_filters()

    def apply_filters(self):
        """Apply all active filters and update display"""
        # Start with all processes
        filtered = self.all_processes[:]

        # Apply state filter
        filtered = self.filter_by_state(filtered)

        # Apply search filter
        if self.current_search_query:
            filtered = self.search_processes(self.current_search_query, filtered)

        # Update visible processes
        self.visible_processes = filtered

        # Update UI
        self.update_processes_display()
        self.update_header_counter()

    def filter_by_state(self, processes: list) -> list:
        """Filter processes by state"""
        if self.current_state_filter == "normal":
            return [p for p in processes if p.is_active and not p.is_archived]
        elif self.current_state_filter == "archived":
            return [p for p in processes if p.is_archived]
        elif self.current_state_filter == "inactive":
            return [p for p in processes if not p.is_active]
        else:  # "all"
            return processes

    def search_processes(self, query: str, processes: list) -> list:
        """Search processes by text"""
        query_lower = query.lower()
        results = []

        for process in processes:
            # Search in name
            if query_lower in process.name.lower():
                results.append(process)
                continue

            # Search in description
            if process.description and query_lower in process.description.lower():
                results.append(process)
                continue

            # Search in tags
            if process.tags and any(query_lower in tag.lower() for tag in process.tags):
                results.append(process)
                continue

            # Search in step labels
            if process.steps and any(query_lower in step.item_label.lower() for step in process.steps):
                results.append(process)
                continue

        return results

    # ========== DISPLAY UPDATES ==========

    def update_processes_display(self):
        """Update the processes list display"""
        # Clear existing widgets
        while self.processes_layout.count():
            item = self.processes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add process widgets
        if not self.visible_processes:
            # Show empty state
            empty_label = QLabel("No se encontraron procesos")
            empty_label.setStyleSheet("""
                QLabel {
                    color: #888888;
                    font-size: 11pt;
                    padding: 40px;
                }
            """)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.processes_layout.addWidget(empty_label)
        else:
            # Import here to avoid circular import
            from views.widgets.process_widget import ProcessWidget

            for process in self.visible_processes:
                process_widget = ProcessWidget(process, parent=self)

                # Connect signals
                process_widget.process_executed.connect(self.on_process_executed)
                process_widget.process_edited.connect(self.on_process_edited)
                process_widget.process_deleted.connect(self.on_process_deleted)
                process_widget.process_pinned.connect(self.on_process_pinned)
                process_widget.copy_all_requested.connect(self.on_copy_all_requested)

                self.processes_layout.addWidget(process_widget)

    def update_header_counter(self):
        """Update process counter in header"""
        total = len(self.all_processes)
        visible = len(self.visible_processes)

        if visible == total:
            self.header_label.setText(f"⚙️ Procesos ({total})")
        else:
            self.header_label.setText(f"⚙️ Procesos ({visible}/{total})")

    # ========== ACTIONS ==========

    def on_advanced_filters_clicked(self):
        """Open advanced filters window"""
        # TODO: Implement advanced filters window for processes
        logger.info("Advanced filters not yet implemented")

    def on_execute_all_clicked(self):
        """Execute all visible processes sequentially"""
        if not self.visible_processes:
            QMessageBox.warning(self, "Sin Procesos", "No hay procesos visibles para ejecutar")
            return

        # Confirmation
        reply = QMessageBox.question(
            self,
            "Ejecutar Todos",
            f"¿Ejecutar {len(self.visible_processes)} proceso(s) secuencialmente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Execute each process
        for process in self.visible_processes:
            try:
                success = self.process_controller.execute_process(process.id)
                if not success:
                    logger.error(f"Failed to execute process {process.id}")
                    # Ask if continue
                    continue_reply = QMessageBox.question(
                        self,
                        "Error",
                        f"Error al ejecutar '{process.name}'. ¿Continuar con los siguientes?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if continue_reply != QMessageBox.StandardButton.Yes:
                        break
            except Exception as e:
                logger.error(f"Exception executing process {process.id}: {e}")
                break

        # Reload processes to update stats
        self.reload_processes()

    def on_process_executed(self, process_id: int):
        """Handle process execution request"""
        logger.info(f"Executing process {process_id}")

        if not self.process_controller:
            logger.error("No ProcessController available")
            return

        try:
            success = self.process_controller.execute_process(process_id)

            if success:
                # Reload to update stats
                self.reload_processes()

                # Feedback
                process = next((p for p in self.all_processes if p.id == process_id), None)
                if process:
                    QMessageBox.information(
                        self,
                        "Proceso Completado",
                        f"Proceso '{process.name}' ejecutado exitosamente"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Error al ejecutar proceso"
                )
        except Exception as e:
            logger.error(f"Exception executing process: {e}")
            QMessageBox.critical(self, "Error", f"Error al ejecutar proceso: {str(e)}")

    def on_process_edited(self, process_id: int):
        """Handle process edit request"""
        self.process_edited.emit(process_id)

    def on_process_deleted(self, process_id: int):
        """Handle process delete request"""
        process = next((p for p in self.all_processes if p.id == process_id), None)
        if not process:
            return

        # Confirmation
        reply = QMessageBox.question(
            self,
            "Eliminar Proceso",
            f"¿Eliminar proceso '{process.name}'?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                success, msg = self.process_controller.delete_process(process_id)

                if success:
                    logger.info(f"Process {process_id} deleted")
                    self.reload_processes()
                else:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar el proceso: {msg}")
            except Exception as e:
                logger.error(f"Exception deleting process: {e}")
                QMessageBox.critical(self, "Error", f"Error al eliminar proceso: {str(e)}")

    def on_process_pinned(self, process_id: int, is_pinned: bool):
        """Handle process pin/unpin"""
        try:
            # Update in database
            success = self.process_controller.update_process_pin(process_id, is_pinned)

            if success:
                # Reload to reflect changes
                self.reload_processes()
            else:
                QMessageBox.warning(self, "Error", "No se pudo actualizar el estado de anclado")
        except Exception as e:
            logger.error(f"Exception updating pin state: {e}")

    def on_copy_all_requested(self, process_id: int):
        """Copy all steps content to clipboard"""
        process = next((p for p in self.all_processes if p.id == process_id), None)
        if not process or not process.steps:
            return

        # Build content
        content_parts = []
        for step in process.steps:
            step_label = step.custom_label or step.item_label
            content_parts.append(f"{step.step_order}. {step_label}: {step.item_content}")

        full_content = "\n".join(content_parts)

        # Copy to clipboard
        import pyperclip
        pyperclip.copy(full_content)

        logger.info(f"Copied {len(process.steps)} steps from process '{process.name}'")

    # ========== PIN/MINIMIZE ==========

    def toggle_pin(self):
        """Toggle pin state"""
        self.is_pinned = not self.is_pinned

        # Update button
        if self.is_pinned:
            self.pin_button.setText("📌")
            self.pin_button.setToolTip("Desanclar panel")
            self.minimize_button.setVisible(True)
            self.config_button.setVisible(True)
        else:
            self.pin_button.setText("📍")
            self.pin_button.setToolTip("Anclar panel")
            self.minimize_button.setVisible(False)
            self.config_button.setVisible(False)

        # Save to database
        self._save_panel_state_to_db()

        # Emit signal
        self.pin_state_changed.emit(self.is_pinned)

    def toggle_minimize(self):
        """Toggle minimize state"""
        if not self.is_pinned:
            return

        self.is_minimized = not self.is_minimized

        if self.is_minimized:
            # Save current size and position
            self.normal_height = self.height()
            self.normal_width = self.width()
            self.normal_position = self.pos()

            # Hide content widgets
            self.scroll_area.hide()
            self.search_widget.hide()
            self.action_widget.hide()

            # Hide display options widget if it exists
            if hasattr(self, 'display_options_widget'):
                self.display_options_widget.setVisible(False)

            # Resize to compact size with better button visibility (height: 50px, width: 250px)
            minimized_height = 50  # Good height for button visibility
            minimized_width = 250  # Width to show all buttons
            self.resize(minimized_width, minimized_height)

            # Set fixed size to prevent unwanted resizing
            self.setFixedSize(minimized_width, minimized_height)

            self.minimize_button.setText("🔼")
            self.minimize_button.setToolTip("Restaurar panel")
        else:
            # Restore content widgets
            self.scroll_area.show()
            self.search_widget.show()
            self.action_widget.show()

            # Restore display options widget if it exists
            if hasattr(self, 'display_options_widget'):
                self.display_options_widget.setVisible(True)

            # CRITICAL: Remove fixed size constraint first (set to maximum QWidget size)
            self.setFixedSize(16777215, 16777215)  # Maximum allowed size for QWidget

            # CRITICAL: Restore proper size constraints for normal resizing
            self.setMinimumWidth(300)
            self.setMinimumHeight(400)
            self.setMaximumWidth(16777215)  # No maximum width limit
            self.setMaximumHeight(16777215)  # No maximum height limit

            # Restore original size
            if self.normal_height:
                self.resize(self.normal_width, self.normal_height)
            if self.normal_position:
                self.move(self.normal_position)

            self.minimize_button.setText("➖")
            self.minimize_button.setToolTip("Minimizar panel")

    def show_panel_configuration(self):
        """Show panel configuration dialog"""
        # TODO: Implement configuration dialog
        logger.info("Panel configuration not yet implemented")

    # ========== PERSISTENCE ==========

    def _save_panel_state_to_db(self):
        """Save panel state to database"""
        if not self.is_pinned or not self.panels_manager:
            return

        try:
            # Build filter config
            filter_config = {
                "search_query": self.current_search_query,
                "state_filter": self.current_state_filter
            }

            # Save or update
            if self.panel_id:
                self.panels_manager.update_panel(
                    self.panel_id,
                    x=self.x(),
                    y=self.y(),
                    width=self.width(),
                    height=self.height(),
                    is_minimized=self.is_minimized,
                    filter_config=filter_config
                )
            else:
                self.panel_id = self.panels_manager.save_panel(
                    panel_type="processes",
                    custom_name=self.panel_name,
                    custom_color=self.panel_color,
                    x=self.x(),
                    y=self.y(),
                    width=self.width(),
                    height=self.height(),
                    is_minimized=self.is_minimized,
                    filter_config=filter_config
                )

            logger.debug(f"Panel state saved to DB (id={self.panel_id})")
        except Exception as e:
            logger.error(f"Error saving panel state: {e}")

    # ========== DATA LOADING ==========

    def load_all_processes(self):
        """Load all processes from database"""
        try:
            if self.process_controller:
                self.all_processes = self.process_controller.get_all_processes()
                logger.info(f"Loaded {len(self.all_processes)} processes")
                self.apply_filters()
            else:
                logger.error("No process controller available")
        except Exception as e:
            logger.error(f"Error loading processes: {e}")

    def reload_processes(self):
        """Reload processes and refresh display"""
        self.load_all_processes()

    # ========== POSITIONING ==========

    def position_near_sidebar(self, main_window):
        """Position panel near the sidebar"""
        if not main_window:
            return

        # Position to the left of the sidebar
        sidebar_geo = main_window.geometry()
        panel_x = sidebar_geo.x() - self.width() - 10
        panel_y = sidebar_geo.y()

        self.move(panel_x, panel_y)

    # ========== WINDOW EVENTS ==========

    def is_on_left_edge(self, pos):
        """Check if mouse position is on the left edge for resizing"""
        return pos.x() <= self.resize_edge_width

    def event(self, event):
        """Override event to handle hover for cursor changes"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QCursor

        if event.type() == QEvent.Type.HoverMove:
            pos = event.position().toPoint()
            if self.is_on_left_edge(pos):
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        return super().event(event)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging or resizing"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_on_left_edge(event.pos()):
                # Start resizing
                self.resizing = True
                self.resize_start_x = event.globalPosition().toPoint().x()
                self.resize_start_width = self.width()
                event.accept()
            else:
                # Start dragging
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging or resizing"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.resizing:
                # Calculate new width
                current_x = event.globalPosition().toPoint().x()
                delta_x = current_x - self.resize_start_x
                new_width = self.resize_start_width - delta_x  # Subtract because we're dragging from left edge

                # Apply constraints
                new_width = max(self.minimumWidth(), min(new_width, self.maximumWidth()))

                # Resize and reposition
                old_width = self.width()
                old_x = self.x()
                self.resize(new_width, self.height())

                # Adjust position to keep right edge fixed
                width_diff = self.width() - old_width
                self.move(old_x - width_diff, self.y())

                event.accept()
            else:
                # Dragging
                self.move(event.globalPosition().toPoint() - self.drag_position)
                event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end resizing"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.resizing:
                self.resizing = False
                # Save new width to config
                if self.config_manager:
                    self.config_manager.set_setting('panel_width', self.width())
                event.accept()

    def closeEvent(self, event):
        """Handle window close"""
        self.window_closed.emit()
        event.accept()
