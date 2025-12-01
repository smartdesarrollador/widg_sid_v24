"""
Sidebar View - Vertical sidebar with category buttons and scroll navigation
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont
from typing import List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.category import Category
from views.widgets.button_widget import CategoryButton
from styles.futuristic_theme import get_theme
from styles.effects import ScanLineEffect


class Sidebar(QWidget):
    """Vertical sidebar with category buttons and scroll navigation"""

    # Signal emitted when a category button is clicked
    category_clicked = pyqtSignal(str)  # category_id

    # Signal emitted when settings button is clicked
    settings_clicked = pyqtSignal()

    # Signal emitted when component manager button is clicked
    component_manager_clicked = pyqtSignal()

    # Signal emitted when table creator button is clicked
    table_creator_clicked = pyqtSignal()

    # Signal emitted when tables manager button is clicked
    tables_manager_clicked = pyqtSignal()

    # Signal emitted when favorites button is clicked
    favorites_clicked = pyqtSignal()

    # Signal emitted when stats button is clicked
    stats_clicked = pyqtSignal()

    # Signal emitted when dashboard button is clicked
    dashboard_clicked = pyqtSignal()

    # Signal emitted when category filter button is clicked
    category_filter_clicked = pyqtSignal()

    # Signal emitted when category manager button is clicked
    category_manager_clicked = pyqtSignal()  # NEW

    # Signal emitted when global search button is clicked
    global_search_clicked = pyqtSignal()

    # Signal emitted when advanced search button is clicked
    advanced_search_clicked = pyqtSignal()

    # Signal emitted when image gallery button is clicked
    image_gallery_clicked = pyqtSignal()

    # Signal emitted when pinned panels manager button is clicked
    pinned_panels_manager_clicked = pyqtSignal()

    # Signal emitted when notebook button is clicked
    notebook_clicked = pyqtSignal()

    # Signal emitted when browser button is clicked
    browser_clicked = pyqtSignal()

    # Signal emitted when screenshot button is clicked
    screenshot_clicked = pyqtSignal()

    # Signal emitted when AI Bulk button is clicked
    ai_bulk_clicked = pyqtSignal()

    # Signal emitted when AI Table button is clicked
    ai_table_clicked = pyqtSignal()

    # Signal emitted when refresh button is clicked
    refresh_clicked = pyqtSignal()

    # Signal emitted when quick create button is clicked
    quick_create_clicked = pyqtSignal()

    # Signal emitted when create process button is clicked
    create_process_clicked = pyqtSignal()

    # Signal emitted when view processes button is clicked
    view_processes_clicked = pyqtSignal()

    # Signal emitted when a process button is clicked
    process_clicked = pyqtSignal(int)  # process_id

    # Signal emitted when web static create button is clicked
    web_static_create_clicked = pyqtSignal()

    # Signal emitted when projects button is clicked
    projects_clicked = pyqtSignal()

    # Signal emitted when close app button is clicked from menu
    close_app_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_buttons = {}
        self.active_button = None
        self.scroll_area = None
        self.theme = get_theme()  # Obtener tema futurista
        self.notebook_window = None  # Reference to notebook window
        self.controller = None  # Will be set later

        # Process buttons
        self.process_buttons = {}  # Dict: process_id -> ProcessButton
        self.active_process_button = None

        self.init_ui()

    def init_ui(self):
        """Initialize sidebar UI"""
        # Set fixed width
        self.setFixedWidth(70)
        self.setMinimumHeight(400)

        # Set background con tema futurista
        self.setStyleSheet(self.theme.get_sidebar_style())

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # App title/logo
        title_label = QLabel("WS")
        title_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_primary')};
                padding: 10px;
                font-size: 13pt;
                font-weight: bold;
                border-bottom: 3px solid {self.theme.get_color('accent')};
                letter-spacing: 3px;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Refresh button (🔄) - Recargar datos
        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setFixedSize(70, 35)
        self.refresh_button.setToolTip("Refrescar categorías e items")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_primary')};
                border: none;
                border-bottom: 2px solid {self.theme.get_color('background_deep')};
                font-size: 12pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('accent')},
                    stop:1 {self.theme.get_color('secondary')}
                );
                border-bottom: 2px solid {self.theme.get_color('accent')};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                transform: scale(0.95);
            }}
        """)
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        main_layout.addWidget(self.refresh_button)

        # Scroll up button
        self.scroll_up_button = QPushButton("▲")
        self.scroll_up_button.setFixedSize(70, 30)
        self.scroll_up_button.setToolTip("Desplazar arriba")
        self.scroll_up_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scroll_up_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_mid')};
                color: {self.theme.get_color('primary')};
                border: none;
                border-bottom: 1px solid {self.theme.get_color('surface')};
                font-size: 12pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.theme.get_color('surface')};
                color: {self.theme.get_color('accent')};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('primary')};
                color: {self.theme.get_color('text_primary')};
            }}
            QPushButton:disabled {{
                color: {self.theme.get_color('text_secondary')};
                background-color: {self.theme.get_color('background_deep')};
            }}
        """)
        self.scroll_up_button.clicked.connect(self.scroll_up)
        main_layout.addWidget(self.scroll_up_button)

        # Global Search button (BG - Búsqueda Global)
        self.global_search_button = QPushButton("🔍")
        self.global_search_button.setFixedSize(70, 40)
        self.global_search_button.setToolTip("Búsqueda Global")
        self.global_search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.global_search_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_primary')};
                border: none;
                border-bottom: 2px solid {self.theme.get_color('background_deep')};
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('accent')},
                    stop:1 {self.theme.get_color('primary')}
                );
                border-bottom: 2px solid {self.theme.get_color('accent')};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                transform: scale(0.95);
            }}
        """)
        self.global_search_button.clicked.connect(self.on_global_search_clicked)
        main_layout.addWidget(self.global_search_button)

        # Screenshot button
        self.screenshot_button = QPushButton("📸")
        self.screenshot_button.setFixedSize(70, 40)
        self.screenshot_button.setToolTip("Captura de Pantalla (Ctrl+Alt+W)")
        self.screenshot_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.screenshot_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_primary')};
                border: none;
                border-bottom: 2px solid {self.theme.get_color('background_deep')};
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b6b,
                    stop:1 #feca57
                );
                border-bottom: 2px solid #ff6b6b;
                color: #000000;
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                transform: scale(0.95);
            }}
        """)
        self.screenshot_button.clicked.connect(self.on_screenshot_clicked)
        main_layout.addWidget(self.screenshot_button)

        # MOVED TO QUICK ACCESS PANEL: Advanced Search button
        # self.advanced_search_button = QPushButton("🔍⚡")
        # ... (moved to QuickAccessPanel)

        # Notebook button
        self.notebook_button = QPushButton("📓")
        self.notebook_button.setFixedSize(70, 40)
        self.notebook_button.setToolTip("Bloc de Notas (Ctrl+Shift+N)")
        self.notebook_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notebook_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_primary')};
                border: none;
                border-bottom: 2px solid {self.theme.get_color('background_deep')};
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('primary')},
                    stop:1 {self.theme.get_color('secondary')}
                );
                border-bottom: 2px solid {self.theme.get_color('accent')};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                transform: scale(0.95);
            }}
        """)
        self.notebook_button.clicked.connect(self.on_notebook_clicked)
        main_layout.addWidget(self.notebook_button)

        # MOVED TO QUICK ACCESS PANEL: Create Process button
        # self.create_process_button = QPushButton("⚙️➕")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: View Processes button
        # self.view_processes_button = QPushButton("⚙️📋")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Category Filter button (FC)
        # self.category_filter_button = QPushButton("📂")
        # ... (moved to QuickAccessPanel)

        # Scroll area for category buttons
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)

        # Container widget for buttons
        buttons_container = QWidget()
        self.buttons_layout = QVBoxLayout(buttons_container)
        self.buttons_layout.setContentsMargins(0, 5, 0, 5)
        self.buttons_layout.setSpacing(5)
        self.buttons_layout.addStretch()

        self.scroll_area.setWidget(buttons_container)
        main_layout.addWidget(self.scroll_area)

        # Quick Create button (➕)
        self.quick_create_button = QPushButton("➕")
        self.quick_create_button.setFixedSize(70, 40)
        self.quick_create_button.setToolTip("Crear Item o Categoría")
        self.quick_create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_create_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: #00d4ff;
                border: none;
                border-top: 2px solid {self.theme.get_color('surface')};
                font-size: 16pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff,
                    stop:1 #00ff88
                );
                color: #000000;
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                color: #00d4ff;
            }}
        """)
        self.quick_create_button.clicked.connect(self.on_quick_create_clicked)
        main_layout.addWidget(self.quick_create_button)

        # Menu button (☰)
        self.quick_access_button = QPushButton("☰")
        self.quick_access_button.setFixedSize(70, 40)
        self.quick_access_button.setToolTip("Menu")
        self.quick_access_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_access_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: #ffaa00;
                border: none;
                border-top: 2px solid {self.theme.get_color('surface')};
                border-bottom: 2px solid {self.theme.get_color('surface')};
                font-size: 18pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff88,
                    stop:1 #00ccff
                );
                color: #000000;
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('surface')};
                color: #ffaa00;
            }}
        """)
        self.quick_access_button.clicked.connect(self.on_quick_access_clicked)
        main_layout.addWidget(self.quick_access_button)

        # Scroll down button
        self.scroll_down_button = QPushButton("▼")
        self.scroll_down_button.setFixedSize(70, 30)
        self.scroll_down_button.setToolTip("Desplazar abajo")
        self.scroll_down_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scroll_down_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('primary')};
                border: none;
                border-top: 1px solid {self.theme.get_color('surface')};
                font-size: 12pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.theme.get_color('surface')};
                color: {self.theme.get_color('accent')};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('primary')};
                color: {self.theme.get_color('text_primary')};
            }}
            QPushButton:disabled {{
                color: {self.theme.get_color('text_secondary')};
                background-color: {self.theme.get_color('background_deep')};
            }}
        """)
        self.scroll_down_button.clicked.connect(self.scroll_down)
        main_layout.addWidget(self.scroll_down_button)

        # MOVED TO QUICK ACCESS PANEL: Table Creator button
        # self.table_creator_button = QPushButton("📊")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Tables Manager button
        # self.tables_manager_button = QPushButton("📋")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Favorites button
        # self.favorites_button = QPushButton("⭐")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Stats button
        # self.stats_button = QPushButton("📊")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: AI Bulk Creation button
        # self.ai_bulk_button = QPushButton("🤖")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: AI Table Creation button
        # self.ai_table_button = QPushButton("🤖📊")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Browser button
        # self.browser_button = QPushButton("🌐")
        # ... (moved to QuickAccessPanel)

        # MOVED TO QUICK ACCESS PANEL: Dashboard button
        # self.dashboard_button = QPushButton("🗂️")
        # ... (moved to QuickAccessPanel)

        # Pinned Panels Manager button
        self.pinned_panels_button = QPushButton("📌")
        self.pinned_panels_button.setFixedSize(70, 45)
        self.pinned_panels_button.setToolTip("Gestión de Paneles Anclados (Ctrl+Shift+P)")
        self.pinned_panels_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pinned_panels_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_secondary')};
                border: none;
                border-top: 2px solid {self.theme.get_color('surface')};
                font-size: 16pt;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('accent')},
                    stop:1 {self.theme.get_color('secondary')}
                );
                color: {self.theme.get_color('text_primary')};
            }}
            QPushButton:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('secondary')},
                    stop:1 {self.theme.get_color('accent')}
                );
                color: {self.theme.get_color('background_deep')};
            }}
        """)
        # MOVED TO QUICK ACCESS PANEL
        # self.pinned_panels_button.clicked.connect(self.on_pinned_panels_manager_clicked)
        # main_layout.addWidget(self.pinned_panels_button)
        # self.component_manager_button - MOVED TO QUICK ACCESS PANEL

        # Browser button (moved from Quick Access Panel)
        self.browser_button = QPushButton("🌐")
        self.browser_button.setFixedSize(70, 45)
        self.browser_button.setToolTip("Navegador")
        self.browser_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browser_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_secondary')};
                border: none;
                border-top: 2px solid {self.theme.get_color('surface')};
                font-size: 16pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme.get_color('surface')};
                color: {self.theme.get_color('primary')};
            }}
            QPushButton:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('primary')},
                    stop:1 {self.theme.get_color('accent')}
                );
                color: {self.theme.get_color('text_primary')};
            }}
        """)
        self.browser_button.clicked.connect(self.on_browser_clicked)
        main_layout.addWidget(self.browser_button)

        # Settings button at the bottom
        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedSize(70, 45)
        self.settings_button.setToolTip("Configuración")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.get_color('background_deep')};
                color: {self.theme.get_color('text_secondary')};
                border: none;
                border-top: 2px solid {self.theme.get_color('surface')};
                font-size: 16pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme.get_color('surface')};
                color: {self.theme.get_color('primary')};
            }}
            QPushButton:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme.get_color('primary')},
                    stop:1 {self.theme.get_color('accent')}
                );
                color: {self.theme.get_color('text_primary')};
            }}
        """)
        self.settings_button.clicked.connect(self.on_settings_clicked)
        main_layout.addWidget(self.settings_button)

        # Update scroll button states
        self.update_scroll_buttons()

        # Aplicar efecto scanlines (muy sutil)
        self.scanline_effect = ScanLineEffect(self, line_spacing=6, speed=1.0)
        self.scanline_effect.setGeometry(self.rect())
        self.scanline_effect.lower()

    def scroll_up(self):
        """Scroll the category list up"""
        scrollbar = self.scroll_area.verticalScrollBar()
        current_value = scrollbar.value()
        new_value = max(0, current_value - 50)  # Scroll by button height (45px + spacing)

        # Animate scroll
        self.animate_scroll(current_value, new_value)

    def scroll_down(self):
        """Scroll the category list down"""
        scrollbar = self.scroll_area.verticalScrollBar()
        current_value = scrollbar.value()
        new_value = min(scrollbar.maximum(), current_value + 50)  # Scroll by button height (45px + spacing)

        # Animate scroll
        self.animate_scroll(current_value, new_value)

    def animate_scroll(self, start_value, end_value):
        """Animate scroll movement"""
        scrollbar = self.scroll_area.verticalScrollBar()

        # Create animation
        self.scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self.scroll_animation.setDuration(200)
        self.scroll_animation.setStartValue(start_value)
        self.scroll_animation.setEndValue(end_value)
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.scroll_animation.finished.connect(self.update_scroll_buttons)
        self.scroll_animation.start()

    def update_scroll_buttons(self):
        """Update scroll button enabled/disabled state"""
        if not self.scroll_area:
            return

        scrollbar = self.scroll_area.verticalScrollBar()

        # Disable up button if at top
        self.scroll_up_button.setEnabled(scrollbar.value() > 0)

        # Disable down button if at bottom
        self.scroll_down_button.setEnabled(scrollbar.value() < scrollbar.maximum())

    def load_categories(self, categories: List[Category]):
        """Load and create buttons for categories"""
        # Clear existing buttons
        self.clear_buttons()

        # Create button for each category
        for category in categories:
            if not category.is_active:
                continue

            button = CategoryButton(category.id, category.name)
            button.clicked.connect(lambda checked, cat_id=category.id: self.on_category_clicked(cat_id))

            self.category_buttons[category.id] = button
            # Insert before the stretch
            self.buttons_layout.insertWidget(self.buttons_layout.count() - 1, button)

        # Update scroll buttons after loading
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_scroll_buttons)
        self.update_scroll_buttons()

    def clear_buttons(self):
        """Clear all category buttons"""
        for button in self.category_buttons.values():
            button.deleteLater()
        self.category_buttons.clear()
        self.active_button = None

    def load_active_processes(self, processes):
        """Load and create buttons for active processes"""
        from views.widgets.process_button import ProcessButton

        # Clear existing process buttons
        self.clear_process_buttons()

        # Filter only active processes
        active_processes = [p for p in processes if p.is_active]

        # Create button for each active process
        for process in active_processes:
            # Get step count for this process
            step_count = 0
            if self.controller and self.controller.process_controller:
                steps = self.controller.process_controller.get_process_steps(process.id)
                step_count = len(steps)

            button = ProcessButton(process.id, process.name, step_count, self)
            button.clicked.connect(self.on_process_clicked)

            self.process_buttons[process.id] = button
            # Insert before the stretch
            self.buttons_layout.insertWidget(self.buttons_layout.count() - 1, button)

        # Update scroll buttons
        self.update_scroll_buttons()

    def clear_process_buttons(self):
        """Clear all process buttons"""
        for button in self.process_buttons.values():
            button.deleteLater()
        self.process_buttons.clear()
        self.active_process_button = None

    def on_process_clicked(self, process_id: int):
        """Handle process button click"""
        # Update active button
        if self.active_process_button:
            self.active_process_button.set_active(False)

        clicked_button = self.process_buttons.get(process_id)
        if clicked_button:
            clicked_button.set_active(True)
            self.active_process_button = clicked_button

        # Emit signal
        self.process_clicked.emit(process_id)

    def refresh_active_processes(self):
        """Refresh active processes from controller"""
        if self.controller:
            processes = self.controller.process_controller.get_all_processes(
                include_archived=False,
                include_inactive=False
            )
            self.load_active_processes(processes)

    def set_active_process(self, process_id: int):
        """Set active process programmatically"""
        if self.active_process_button:
            self.active_process_button.set_active(False)

        button = self.process_buttons.get(process_id)
        if button:
            button.set_active(True)
            self.active_process_button = button

    def clear_active_process(self):
        """Clear active process button"""
        if self.active_process_button:
            self.active_process_button.set_active(False)
            self.active_process_button = None

    def on_category_clicked(self, category_id: str):
        """Handle category button click"""
        # Update active button
        if self.active_button:
            self.active_button.set_active(False)

        clicked_button = self.category_buttons.get(category_id)
        if clicked_button:
            clicked_button.set_active(True)
            self.active_button = clicked_button

        # Emit signal
        self.category_clicked.emit(category_id)

    def set_active_category(self, category_id: str):
        """Set active category programmatically"""
        if self.active_button:
            self.active_button.set_active(False)

        button = self.category_buttons.get(category_id)
        if button:
            button.set_active(True)
            self.active_button = button

    def on_table_creator_clicked(self):
        """Handle table creator button click"""
        self.table_creator_clicked.emit()

    def on_tables_manager_clicked(self):
        """Handle tables manager button click"""
        self.tables_manager_clicked.emit()

    def on_favorites_clicked(self):
        """Handle favorites button click"""
        self.favorites_clicked.emit()

    def on_stats_clicked(self):
        """Handle stats button click"""
        self.stats_clicked.emit()

    def on_ai_bulk_clicked(self):
        """Handle AI bulk creation button click"""
        self.ai_bulk_clicked.emit()

    def on_ai_table_clicked(self):
        """Handle AI table creation button click"""
        self.ai_table_clicked.emit()

    def on_browser_clicked(self):
        """Handle browser button click"""
        self.browser_clicked.emit()

    def on_settings_clicked(self):
        """Handle settings button click"""
        self.settings_clicked.emit()

    def on_component_manager_clicked(self):
        """Handle component manager button click"""
        self.component_manager_clicked.emit()

    def on_category_filter_clicked(self):
        """Handle category filter button click"""
        self.category_filter_clicked.emit()

    def on_global_search_clicked(self):
        """Handle global search button click"""
        self.global_search_clicked.emit()

    def on_screenshot_clicked(self):
        """Handle screenshot button click"""
        self.screenshot_clicked.emit()

    def on_advanced_search_clicked(self):
        """Handle advanced search button click"""
        self.advanced_search_clicked.emit()

    def on_notebook_clicked(self):
        """Handle notebook button click"""
        self.toggle_notebook()

    def on_create_process_clicked(self):
        """Handle create process button click"""
        self.create_process_clicked.emit()

    def on_view_processes_clicked(self):
        """Handle view processes button click"""
        self.view_processes_clicked.emit()

    def on_dashboard_clicked(self):
        """Handle dashboard button click"""
        self.dashboard_clicked.emit()

    def on_refresh_clicked(self):
        """Handle refresh button click"""
        self.refresh_clicked.emit()

    def on_quick_create_clicked(self):
        """Handle quick create button click"""
        self.quick_create_clicked.emit()

    def on_quick_access_clicked(self):
        """Handle quick access button click - show/hide quick access panel"""
        if not hasattr(self, 'quick_access_panel') or self.quick_access_panel is None:
            from views.quick_access_panel import QuickAccessPanel
            self.quick_access_panel = QuickAccessPanel(self)

            # Connect signals if controller is available
            if self.controller:
                self.quick_access_panel.advanced_search_clicked.connect(lambda: self.advanced_search_clicked.emit())
                self.quick_access_panel.stats_clicked.connect(lambda: self.stats_clicked.emit())
                self.quick_access_panel.tables_manager_clicked.connect(lambda: self.tables_manager_clicked.emit())
                self.quick_access_panel.favorites_clicked.connect(lambda: self.favorites_clicked.emit())
                self.quick_access_panel.dashboard_clicked.connect(lambda: self.dashboard_clicked.emit())
                self.quick_access_panel.category_filter_clicked.connect(lambda: self.category_filter_clicked.emit())
                self.quick_access_panel.category_manager_clicked.connect(lambda: self.category_manager_clicked.emit())  # NEW
                self.quick_access_panel.table_creator_clicked.connect(lambda: self.table_creator_clicked.emit())
                self.quick_access_panel.create_process_clicked.connect(lambda: self.create_process_clicked.emit())
                self.quick_access_panel.view_processes_clicked.connect(lambda: self.view_processes_clicked.emit())
                self.quick_access_panel.ai_bulk_clicked.connect(lambda: self.ai_bulk_clicked.emit())
                self.quick_access_panel.ai_table_clicked.connect(lambda: self.ai_table_clicked.emit())
                self.quick_access_panel.pinned_panels_clicked.connect(lambda: self.pinned_panels_manager_clicked.emit())
                self.quick_access_panel.component_manager_clicked.connect(lambda: self.component_manager_clicked.emit())
                self.quick_access_panel.web_static_create_clicked.connect(lambda: self.web_static_create_clicked.emit())
                self.quick_access_panel.image_gallery_clicked.connect(lambda: self.image_gallery_clicked.emit())
                self.quick_access_panel.projects_clicked.connect(lambda: self.projects_clicked.emit())
                self.quick_access_panel.close_app_clicked.connect(lambda: self.close_app_requested.emit())

        # Toggle visibility
        if self.quick_access_panel.isVisible():
            self.quick_access_panel.hide()
        else:
            self.quick_access_panel.position_near_button(self.quick_access_button)
            self.quick_access_panel.show()

    def on_pinned_panels_manager_clicked(self):
        """Handle pinned panels manager button click"""
        self.pinned_panels_manager_clicked.emit()

    def set_controller(self, controller):
        """Set the main controller reference"""
        self.controller = controller

    def toggle_notebook(self):
        """Abrir/cerrar ventana de notebook"""
        if not self.controller:
            print("Error: Controller not set")
            return

        if not hasattr(self, 'notebook_window') or self.notebook_window is None:
            # Crear ventana
            from views.notebook_window import NotebookWindow
            self.notebook_window = NotebookWindow(self.controller)

            # Posicionar al lado del sidebar
            self.position_notebook_window()

            # Conectar señales
            self.notebook_window.closed.connect(self.on_notebook_closed)
            self.notebook_window.tab_saved_as_item.connect(self.on_item_saved_from_notebook)

            # El AppBar se registra automáticamente en showEvent del NotebookWindow
            self.notebook_window.show()
        else:
            if self.notebook_window.isVisible():
                # El AppBar se desregistra automáticamente en hideEvent
                self.notebook_window.hide()
            else:
                self.notebook_window.show()
                self.position_notebook_window()
                # El AppBar se registra automáticamente en showEvent

    def position_notebook_window(self):
        """Posicionar notebook al lado del sidebar"""
        if not hasattr(self, 'notebook_window') or self.notebook_window is None:
            return

        # Obtener geometría de la ventana principal (main window)
        main_window = self.window()
        if not main_window:
            return

        main_geo = main_window.geometry()

        # Constantes del notebook
        NOTEBOOK_WIDTH = 450

        # Posicionar a la izquierda del sidebar
        x = main_geo.x() - NOTEBOOK_WIDTH - 10  # 10px de separación
        y = main_geo.y()
        height = main_geo.height()

        self.notebook_window.setGeometry(x, y, NOTEBOOK_WIDTH, height)

    def on_notebook_closed(self):
        """Cuando se cierra/oculta la ventana de notebook"""
        # El AppBar se desregistra automáticamente en hideEvent del NotebookWindow
        # NO destruir la referencia - la ventana solo está oculta, no cerrada
        # self.notebook_window = None  # Comentado: mantener instancia para reutilizar
        pass

    def on_item_saved_from_notebook(self, data):
        """Cuando se guarda un item desde el notebook"""
        # Refrescar la vista si es necesario
        # Esto se puede conectar con el main window para refrescar la categoría actual
        pass

    # NOTA: Estos métodos ya no se usan - el Notebook ahora usa AppBar directamente
    # def reserve_workarea_space(self):
    #     """Reservar espacio en el escritorio de Windows para el notebook"""
    #     # Ya no se usa - AppBar se registra automáticamente en NotebookWindow.showEvent()
    #     pass
    #
    # def restore_workarea_space(self):
    #     """Restaurar el área de trabajo original"""
    #     # Ya no se usa - AppBar se desregistra automáticamente en NotebookWindow.hideEvent()
    #     pass
