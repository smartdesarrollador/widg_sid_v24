"""
Quick Access Panel - Small floating window with quick access buttons

Shows buttons for:
- Statistics (📊)
- Tables Manager (📋)
- Favorites (⭐)
- Dashboard (📊)
- Browser (🌐)
- Category Filter (📂)
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class QuickAccessPanel(QWidget):
    """Small floating panel with quick access buttons"""

    # Signals for each action
    stats_clicked = pyqtSignal()
    tables_manager_clicked = pyqtSignal()
    favorites_clicked = pyqtSignal()
    dashboard_clicked = pyqtSignal()
    browser_clicked = pyqtSignal()
    category_filter_clicked = pyqtSignal()
    category_manager_clicked = pyqtSignal()  # NEW: Gestión de categorías
    table_creator_clicked = pyqtSignal()
    create_process_clicked = pyqtSignal()
    view_processes_clicked = pyqtSignal()
    ai_bulk_clicked = pyqtSignal()
    ai_table_clicked = pyqtSignal()
    pinned_panels_clicked = pyqtSignal()
    advanced_search_clicked = pyqtSignal()
    component_manager_clicked = pyqtSignal()
    web_static_create_clicked = pyqtSignal()
    image_gallery_clicked = pyqtSignal()  # NEW: Image Gallery
    projects_clicked = pyqtSignal()  # NEW: Projects Manager
    close_app_clicked = pyqtSignal()  # NEW: Close application

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        # Window properties
        self.setWindowTitle("Menu")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )

        # Fixed size for panel (adjusted for vertical layout)
        self.setFixedSize(220, 750)

        # Window opacity
        self.setWindowOpacity(0.95)

        # Don't close app when closing this window
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        # Styling
        self.setStyleSheet("""
            QuickAccessPanel {
                background-color: #1e1e1e;
                border: 2px solid #00ff88;
                border-radius: 8px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Header with title and small close button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("☰ Menu")
        header.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11pt;
                font-weight: bold;
                background-color: transparent;
                padding: 5px;
            }
        """)
        header_layout.addWidget(header)

        # Small close button (only closes the Menu panel)
        small_close_btn = QPushButton("✕")
        small_close_btn.setFixedSize(25, 25)
        small_close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        small_close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e4475b;
                border-color: #e4475b;
            }
        """)
        small_close_btn.clicked.connect(self.hide)
        header_layout.addWidget(small_close_btn)

        main_layout.addLayout(header_layout)

        # Buttons config (icon, label, handler)
        buttons_config = [
            ("🔍⚡", "Búsqueda Avanzada", self.on_advanced_search_clicked),
            ("📁", "Proyectos", self.on_projects_clicked),  # NEW: Projects Manager
            ("🖼️", "Galería de Imágenes", self.on_image_gallery_clicked),
            ("🤖", "IA Bulk", self.on_ai_bulk_clicked),
            ("🤖📊", "IA Tabla", self.on_ai_table_clicked),
            ("⚙️➕", "Crear Proceso", self.on_create_process_clicked),
            ("⚙️📋", "Ver Procesos", self.on_view_processes_clicked),
            ("📊", "Crear Tabla", self.on_table_creator_clicked),
            ("📋", "Gestor de Tablas", self.on_tables_manager_clicked),
            ("📱", "Web Estático", self.on_web_static_create_clicked),
            ("⭐", "Favoritos", self.on_favorites_clicked),
            ("📊", "Estadísticas", self.on_stats_clicked),
            ("🧩", "Componentes", self.on_component_manager_clicked),
            ("📂", "Categorías", self.on_category_manager_clicked),
            ("📁", "Filtros", self.on_category_filter_clicked),
            ("🗂️", "Dashboard", self.on_dashboard_clicked),
            ("📌", "Paneles Anclados", self.on_pinned_panels_clicked),
        ]

        # Create buttons in rows
        for icon, label, handler in buttons_config:
            row_widget = self.create_action_row(icon, label, handler)
            main_layout.addWidget(row_widget)

        # Add spacer to push close button to bottom
        main_layout.addStretch()

        # Close button at the bottom
        close_btn = QPushButton("✕  Cerrar")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #4d4d4d;
                border-radius: 4px;
                font-size: 10pt;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #e4475b;
                border-color: #e4475b;
            }
            QPushButton:pressed {
                background-color: #c03545;
            }
        """)
        close_btn.clicked.connect(self.on_close_clicked)
        main_layout.addWidget(close_btn)

    def create_action_row(self, icon: str, label: str, handler):
        """Create a button with icon and text"""
        # Button with icon and text
        button = QPushButton(f"{icon}  {label}")
        button.setFixedHeight(36)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 10pt;
                text-align: left;
                padding-left: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff88,
                    stop:1 #00ccff
                );
                border-color: #00ff88;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
        """)
        button.clicked.connect(handler)
        return button

    # Handlers
    def on_table_creator_clicked(self):
        """Handle table creator button click"""
        self.table_creator_clicked.emit()
        self.hide()

    def on_tables_manager_clicked(self):
        """Handle tables manager button click"""
        self.tables_manager_clicked.emit()
        self.hide()

    def on_favorites_clicked(self):
        """Handle favorites button click"""
        self.favorites_clicked.emit()
        self.hide()

    def on_stats_clicked(self):
        """Handle stats button click"""
        self.stats_clicked.emit()
        self.hide()

    def on_browser_clicked(self):
        """Handle browser button click"""
        self.browser_clicked.emit()
        self.hide()

    def on_category_filter_clicked(self):
        """Handle category filter button click"""
        self.category_filter_clicked.emit()
        self.hide()

    def on_category_manager_clicked(self):
        """Handle category manager button click"""
        self.category_manager_clicked.emit()
        self.hide()

    def on_dashboard_clicked(self):
        """Handle dashboard button click"""
        self.dashboard_clicked.emit()
        self.hide()

    def on_create_process_clicked(self):
        """Handle create process button click"""
        self.create_process_clicked.emit()
        self.hide()

    def on_view_processes_clicked(self):
        """Handle view processes button click"""
        self.view_processes_clicked.emit()
        self.hide()

    def on_ai_bulk_clicked(self):
        """Handle AI bulk creation button click"""
        self.ai_bulk_clicked.emit()
        self.hide()

    def on_ai_table_clicked(self):
        """Handle AI table creation button click"""
        self.ai_table_clicked.emit()
        self.hide()

    def on_pinned_panels_clicked(self):
        """Handle pinned panels manager button click"""
        self.pinned_panels_clicked.emit()
        self.hide()

    def on_advanced_search_clicked(self):
        """Handle advanced search button click"""
        self.advanced_search_clicked.emit()
        self.hide()

    def on_component_manager_clicked(self):
        """Handle component manager button click"""
        self.component_manager_clicked.emit()
        self.hide()

    def on_web_static_create_clicked(self):
        """Handle web static create button click"""
        self.web_static_create_clicked.emit()
        self.hide()

    def on_image_gallery_clicked(self):
        """Handle image gallery button click"""
        self.image_gallery_clicked.emit()
        self.hide()

    def on_projects_clicked(self):
        """Handle projects button click"""
        self.projects_clicked.emit()
        self.hide()

    def on_close_clicked(self):
        """Handle close button click - closes the application"""
        self.close_app_clicked.emit()

    def position_near_button(self, button_widget):
        """Position panel near the quick access button"""
        if not button_widget:
            return

        # Get button global position
        button_pos = button_widget.mapToGlobal(button_widget.rect().topLeft())

        # Position to the left of the button
        panel_x = button_pos.x() - self.width() - 10

        # Position panel higher up (align with top of screen with margin)
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            # Position at top with small margin
            panel_y = screen_geom.top() + 50
        else:
            # Fallback: align with button but offset upwards
            panel_y = max(50, button_pos.y() - 200)

        self.move(panel_x, panel_y)
