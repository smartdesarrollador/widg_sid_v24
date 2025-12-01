"""
Main Window View
"""
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QScreen, QShortcut, QKeySequence
import sys
import logging
import traceback
from pathlib import Path
import ctypes
from ctypes import wintypes

sys.path.insert(0, str(Path(__file__).parent.parent))
from views.sidebar import Sidebar
from views.floating_panel import FloatingPanel
from views.global_search_panel import GlobalSearchPanel
from views.advanced_search import AdvancedSearchWindow
from views.favorites_floating_panel import FavoritesFloatingPanel
from views.stats_floating_panel import StatsFloatingPanel
from views.settings_window import SettingsWindow
from views.pinned_panels_window import PinnedPanelsWindow
from views.pinned_panels_manager_window import PinnedPanelsManagerWindow
from views.dialogs.popular_items_dialog import PopularItemsDialog
from views.dialogs.forgotten_items_dialog import ForgottenItemsDialog
from views.dialogs.suggestions_dialog import FavoriteSuggestionsDialog
from views.dialogs.stats_dashboard import StatsDashboard
from views.dialogs.panel_config_dialog import PanelConfigDialog
from views.dialogs.quick_create_dialog import QuickCreateDialog
from views.dialogs.table_creator_wizard import TableCreatorWizard
from views.item_editor_dialog import ItemEditorDialog
from views.category_filter_window import CategoryFilterWindow
from models.item import Item
from core.hotkey_manager import HotkeyManager
from core.tray_manager import TrayManager
from core.session_manager import SessionManager
from core.notification_manager import NotificationManager

# Get logger
logger = logging.getLogger(__name__)

# ===========================================================================
# Windows AppBar API Constants and Structures
# ===========================================================================
ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003
ABE_RIGHT = 2


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", wintypes.RECT),
        ("lParam", wintypes.LPARAM),
    ]


class MainWindow(QMainWindow):
    """Main application window - frameless, always-on-top sidebar"""

    # Signals
    category_selected = pyqtSignal(str)  # category_id
    item_selected = pyqtSignal(object)  # Item

    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.config_manager = controller.config_manager if controller else None
        self.sidebar = None
        self.floating_panel = None  # Panel flotante activo (no anclado) - compatibility
        self.pinned_panels = []  # Lista de paneles anclados
        self.pinned_global_search_panels = []  # Lista de paneles de búsqueda global anclados
        self.pinned_panels_window = None  # Ventana de gestión de paneles anclados
        self.global_search_panel = None  # Ventana flotante para búsqueda global
        self.advanced_search_window = None  # Ventana de búsqueda avanzada
        self.favorites_panel = None  # Ventana flotante para favoritos
        self.stats_panel = None  # Ventana flotante para estadísticas
        self.structure_dashboard = None  # Dashboard de estructura (no-modal)
        self.category_filter_window = None  # Ventana de filtros de categorías
        self.current_category_id = None  # Para el toggle

        # Process panels
        self.current_process_panel = None  # Panel flotante activo (no anclado) para procesos
        self.pinned_process_panels = []  # Lista de paneles de procesos anclados
        self.current_process_id = None  # Para el toggle de procesos

        self.hotkey_manager = None
        self.tray_manager = None
        self.notification_manager = NotificationManager()
        self.is_visible = True

        # Panel shortcuts management
        self.panel_shortcuts = {}  # Dict[panel_id, QShortcut] - Track keyboard shortcuts for panels
        self.panel_by_shortcut = {}  # Dict[shortcut_str, panel] - Quick lookup panel by shortcut

        # Minimizar/Maximizar estado
        self.is_minimized = False
        self.normal_height = None  # Se guardará después de calcular
        self.minimized_height = 75  # Altura cuando está minimizada (title bar 30px + WS label ~45px)

        # AppBar state (para reservar espacio en Windows)
        self.appbar_registered = False

        self.init_ui()
        self.position_window()
        self.register_appbar()  # Registrar como AppBar para reservar espacio
        self.setup_hotkeys()
        self.setup_tray()
        self.check_notifications_delayed()

        # AUTO-RESTORE: Restore pinned panels from database on startup
        self.restore_pinned_panels_on_startup()
        self.restore_pinned_global_search_panels()
        self.restore_pinned_process_panels()

        # Connect process state change signal for auto-refresh
        if self.controller and self.controller.process_controller:
            self.controller.process_controller.process_state_changed.connect(
                self.on_process_state_changed
            )

    def init_ui(self):
        """Initialize the user interface"""
        # Window properties
        self.setWindowTitle("Widget Sidebar")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # Calculate window height: 100% of screen height (toda la altura disponible menos barra de tareas)
        screen = self.screen()
        if screen:
            screen_height = screen.availableGeometry().height()
            window_height = screen_height  # 100% de la altura disponible (menos barra de tareas)
        else:
            window_height = 600  # Fallback

        # Guardar altura normal para minimizar/maximizar
        self.normal_height = window_height

        # Set window size (starts with sidebar only)
        self.setFixedWidth(70)  # Just sidebar initially
        self.setMinimumHeight(400)
        self.resize(70, window_height)

        # Set window opacity
        self.setWindowOpacity(0.95)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (vertical: title bar + sidebar)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar removed - close button now in Menu panel
        # title_bar = QWidget()
        # title_bar.setFixedHeight(30)
        # title_bar.setStyleSheet("""
        #     QWidget {
        #         background-color: #1e1e1e;
        #         border-bottom: 1px solid #007acc;
        #     }
        # """)
        # title_bar_layout = QHBoxLayout(title_bar)
        # title_bar_layout.setContentsMargins(5, 0, 5, 0)
        # title_bar_layout.setSpacing(5)
        #
        # # Spacer
        # title_bar_layout.addStretch()
        #
        # # Close button
        # self.close_button = QPushButton("✕")
        # self.close_button.setFixedSize(25, 25)
        # self.close_button.setStyleSheet("""
        #     QPushButton {
        #         background-color: #2d2d2d;
        #         color: #cccccc;
        #         border: 1px solid #3d3d3d;
        #         border-radius: 3px;
        #         font-size: 12pt;
        #         font-weight: bold;
        #     }
        #     QPushButton:hover {
        #         background-color: #c42b1c;
        #         border: 1px solid #e81123;
        #         color: #ffffff;
        #     }
        # """)
        # self.close_button.clicked.connect(self.close_window)
        # title_bar_layout.addWidget(self.close_button)
        #
        # main_layout.addWidget(title_bar)

        # Create sidebar only (no embedded panel)
        self.sidebar = Sidebar()
        self.sidebar.set_controller(self.controller)  # Set controller reference for notebook
        self.sidebar.category_clicked.connect(self.on_category_clicked)
        self.sidebar.global_search_clicked.connect(self.on_global_search_clicked)
        self.sidebar.screenshot_clicked.connect(self.on_screenshot_clicked)
        self.sidebar.advanced_search_clicked.connect(self.on_advanced_search_clicked)
        self.sidebar.image_gallery_clicked.connect(self.on_image_gallery_clicked)
        self.sidebar.projects_clicked.connect(self.on_projects_clicked)
        self.sidebar.table_creator_clicked.connect(self.on_table_creator_clicked)
        self.sidebar.tables_manager_clicked.connect(self.on_tables_manager_clicked)
        self.sidebar.favorites_clicked.connect(self.on_favorites_clicked)
        self.sidebar.stats_clicked.connect(self.on_stats_clicked)
        self.sidebar.ai_bulk_clicked.connect(self.on_ai_bulk_clicked)
        self.sidebar.ai_table_clicked.connect(self.on_ai_table_clicked)
        self.sidebar.browser_clicked.connect(self.on_browser_clicked)
        self.sidebar.dashboard_clicked.connect(self.open_structure_dashboard)
        self.sidebar.settings_clicked.connect(self.open_settings)
        self.sidebar.component_manager_clicked.connect(self.open_component_manager)
        self.sidebar.category_filter_clicked.connect(self.on_category_filter_clicked)
        self.sidebar.category_manager_clicked.connect(self.on_category_manager_clicked)  # NEW
        self.sidebar.refresh_clicked.connect(self.on_refresh_clicked)
        self.sidebar.quick_create_clicked.connect(self.on_quick_create_clicked)
        self.sidebar.web_static_create_clicked.connect(self.on_web_static_create_clicked)
        self.sidebar.pinned_panels_manager_clicked.connect(self.show_pinned_panels_manager)
        self.sidebar.create_process_clicked.connect(self.on_create_process_clicked)
        self.sidebar.view_processes_clicked.connect(self.on_view_processes_clicked)
        self.sidebar.process_clicked.connect(self.on_process_clicked)
        self.sidebar.close_app_requested.connect(self.close_window)
        main_layout.addWidget(self.sidebar)

    def load_categories(self, categories):
        """Load categories into sidebar"""
        if self.sidebar:
            self.sidebar.load_categories(categories)

    def load_processes_to_sidebar(self):
        """Load active processes into sidebar"""
        if self.controller and self.sidebar:
            processes = self.controller.process_controller.get_all_processes(
                include_archived=False,
                include_inactive=False
            )
            self.sidebar.load_active_processes(processes)

    def on_category_clicked(self, category_id: str):
        """Handle category button click - toggle floating panel"""
        try:
            logger.info(f"Category clicked: {category_id}")

            # Toggle: Si se hace clic en la misma categoría Y el panel NO está anclado, ocultarlo
            if (self.current_category_id == category_id and
                self.floating_panel and
                self.floating_panel.isVisible() and
                not self.floating_panel.is_pinned):
                logger.info(f"Toggling off - hiding floating panel for category: {category_id}")
                self.floating_panel.hide()
                self.current_category_id = None
                return

            # Get category from controller
            if self.controller:
                logger.debug(f"Getting category {category_id} from controller...")
                category = self.controller.get_category(category_id)

                if category:
                    logger.info(f"Category found: {category.name} with {len(category.items)} items")

                    # Si el panel actual está anclado, agregarlo a la lista de pinned
                    if self.floating_panel and self.floating_panel.is_pinned:
                        logger.info(f"Current panel is pinned, adding to pinned_panels list")
                        if self.floating_panel not in self.pinned_panels:
                            self.pinned_panels.append(self.floating_panel)
                        self.floating_panel = None  # Clear current panel

                    # Create floating panel if it doesn't exist or current one is pinned
                    if not self.floating_panel:
                        self.floating_panel = FloatingPanel(
                            config_manager=self.config_manager,
                            list_controller=self.controller.list_controller if self.controller else None,
                            main_window=self
                        )
                        self.floating_panel.item_clicked.connect(self.on_item_clicked)
                        self.floating_panel.window_closed.connect(self.on_floating_panel_closed)
                        self.floating_panel.pin_state_changed.connect(self.on_panel_pin_changed)
                        self.floating_panel.customization_requested.connect(self.on_panel_customization_requested)
                        self.floating_panel.url_open_requested.connect(self.on_url_open_in_browser)
                        logger.debug("New floating panel created")

                    # Load category into floating panel
                    self.floating_panel.load_category(category)

                    # Position near sidebar (con offset si hay paneles anclados)
                    self.position_new_panel(self.floating_panel)

                    # Update current category
                    self.current_category_id = category_id

                    logger.debug("Category loaded into floating panel")
                else:
                    logger.warning(f"Category {category_id} not found")

            # Emit signal
            self.category_selected.emit(category_id)
            logger.debug("Category selected signal emitted")

        except Exception as e:
            logger.error(f"Error in on_category_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar categoría:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_floating_panel_closed(self):
        """Handle floating panel closed"""
        logger.info("Floating panel closed")

        # Determinar qué panel se cerró
        sender_panel = self.sender()

        # Si es el panel actual (no anclado)
        if sender_panel == self.floating_panel:
            logger.info("Closing active (non-pinned) panel")
            self.current_category_id = None  # Reset para el toggle
            if self.floating_panel:
                self.floating_panel.deleteLater()
                self.floating_panel = None
        else:
            # Es un panel anclado
            logger.info("Closing pinned panel")
            if sender_panel in self.pinned_panels:
                self.pinned_panels.remove(sender_panel)
                sender_panel.deleteLater()
                logger.info(f"Pinned panel removed. Remaining pinned panels: {len(self.pinned_panels)}")

    def on_url_open_in_browser(self, url: str):
        """Handle URL open request - open in embedded browser"""
        logger.info(f"Opening URL in embedded browser: {url}")

        if self.controller and hasattr(self.controller, 'browser_manager'):
            try:
                # Show browser if not visible or doesn't exist
                browser_manager = self.controller.browser_manager

                if not browser_manager.browser_window or not browser_manager.browser_window.isVisible():
                    browser_manager.show_browser()
                    logger.info("Browser opened")

                # Load URL in browser
                if browser_manager.browser_window:
                    browser_manager.browser_window.load_url(url)
                    logger.info(f"URL loaded successfully: {url}")
                else:
                    logger.warning("Browser window not available")

            except Exception as e:
                logger.error(f"Error opening URL in browser: {e}", exc_info=True)
        else:
            logger.warning("Browser manager not available")

    def on_panel_pin_changed(self, is_pinned):
        """Handle when a panel's pin state changes"""
        sender_panel = self.sender()
        logger.info(f"Panel pin state changed: is_pinned={is_pinned}")

        if is_pinned:
            # Panel was just pinned
            if sender_panel == self.floating_panel:
                logger.info("Active panel was pinned - will create new panel on next category click")

            # AUTO-SAVE: Save panel to database when pinned
            if sender_panel.current_category and self.controller:
                try:
                    category_id = sender_panel.current_category.id

                    # Save panel state to database
                    panel_id = self.controller.pinned_panels_manager.save_panel_state(
                        panel_widget=sender_panel,
                        category_id=category_id,
                        custom_name=sender_panel.custom_name,
                        custom_color=sender_panel.custom_color
                    )

                    # Store panel_id in the FloatingPanel instance
                    sender_panel.panel_id = panel_id
                    logger.info(f"[SHORTCUT DEBUG] Panel anchored with panel_id: {panel_id}")

                    # Register keyboard shortcut if one was assigned
                    logger.info(f"[SHORTCUT DEBUG] Retrieving panel data to check for keyboard shortcut")
                    panel_data = self.controller.pinned_panels_manager.get_panel_by_id(panel_id)
                    logger.info(f"[SHORTCUT DEBUG] Panel data retrieved: {panel_data}")

                    if panel_data:
                        shortcut = panel_data.get('keyboard_shortcut')
                        logger.info(f"[SHORTCUT DEBUG] Keyboard shortcut from database: '{shortcut}'")
                        if shortcut:
                            logger.info(f"[SHORTCUT DEBUG] Registering shortcut '{shortcut}' for newly pinned panel {panel_id}")
                            self.register_panel_shortcut(sender_panel, shortcut)
                        else:
                            logger.info(f"[SHORTCUT DEBUG] No keyboard shortcut assigned to panel {panel_id}")
                    else:
                        logger.warning(f"[SHORTCUT DEBUG] Could not retrieve panel data for panel_id {panel_id}")

                    logger.info(f"Panel auto-saved to database with ID: {panel_id} (Category: {sender_panel.current_category.name})")

                except Exception as e:
                    logger.error(f"Error auto-saving panel: {e}", exc_info=True)
        else:
            # Panel was unpinned
            if sender_panel in self.pinned_panels:
                # Remove from pinned list and make it the active panel
                self.pinned_panels.remove(sender_panel)
                if self.floating_panel:
                    # Current active panel becomes pinned
                    if self.floating_panel.is_pinned:
                        self.pinned_panels.append(self.floating_panel)
                self.floating_panel = sender_panel
                logger.info(f"Panel unpinned and became active panel. Remaining pinned: {len(self.pinned_panels)}")

            # Archive panel in database (mark as inactive) instead of deleting
            if sender_panel.panel_id and self.controller:
                try:
                    # Unregister keyboard shortcut before archiving
                    self.unregister_panel_shortcut(sender_panel)

                    self.controller.pinned_panels_manager.archive_panel(sender_panel.panel_id)
                    logger.info(f"Panel {sender_panel.panel_id} archived (marked as inactive) on unpin")
                    # Clear panel_id so it won't try to auto-save anymore
                    sender_panel.panel_id = None
                except Exception as e:
                    logger.error(f"Error archiving panel from database on unpin: {e}", exc_info=True)

    def position_new_panel(self, panel):
        """Position a new panel always at the same initial position (next to sidebar)"""
        # Calculate base position (next to sidebar) - always the same position
        panel.position_near_sidebar(self)
        logger.info(f"Panel positioned at initial position next to sidebar")

    def on_global_search_clicked(self):
        """Handle global search button click - toggle global search panel"""
        try:
            logger.info("Global search button clicked")

            if not self.controller:
                logger.error("No controller available")
                return

            # TOGGLE BEHAVIOR: If panel exists and is visible (not pinned), close it
            if self.global_search_panel and not self.global_search_panel.is_pinned and self.global_search_panel.isVisible():
                logger.debug("Global search panel is visible - closing it (toggle)")
                self.global_search_panel.close()
                return

            # Create global search panel if it doesn't exist OR if the existing one is pinned
            # Similar to FloatingPanel behavior: pinned panels don't block creating new ones
            if not self.global_search_panel or (self.global_search_panel and self.global_search_panel.is_pinned):
                # Get db_manager from controller's config_manager
                db_manager = self.config_manager.db if self.config_manager else None
                self.global_search_panel = GlobalSearchPanel(
                    db_manager=db_manager,
                    config_manager=self.config_manager,
                    list_controller=self.controller.list_controller,
                    parent=self
                )
                self.global_search_panel.item_clicked.connect(self.on_item_clicked)
                self.global_search_panel.window_closed.connect(self.on_global_search_panel_closed)
                # Conectar señal de cambio de estado de pin
                self.global_search_panel.pin_state_changed.connect(self.on_global_search_pin_state_changed)
                self.global_search_panel.url_open_requested.connect(self.on_url_open_in_browser)
                logger.debug("Global search panel created (new or replacing pinned one)")

            # Load all items
            self.global_search_panel.load_all_items()

            # Position near sidebar
            self.global_search_panel.position_near_sidebar(self)

            logger.debug("Global search panel loaded and positioned")

        except Exception as e:
            logger.error(f"Error in on_global_search_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir búsqueda global:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_global_search_panel_closed(self):
        """Handle global search panel closed"""
        logger.info("Global search panel closed")
        if self.global_search_panel:
            self.global_search_panel.deleteLater()
            self.global_search_panel = None

    def on_global_search_pin_state_changed(self, is_pinned: bool):
        """Handle global search panel pin state change via signal"""
        panel = self.sender()  # Get the panel that emitted the signal
        if is_pinned:
            self.on_global_search_panel_pinned(panel)
        else:
            self.on_global_search_panel_unpinned(panel)

    def on_restored_global_search_panel_closed(self, panel):
        """Handle when a restored global search panel is closed"""
        logger.info(f"Restored global search panel {panel.panel_id} closed")
        if panel in self.pinned_global_search_panels:
            self.pinned_global_search_panels.remove(panel)
        panel.deleteLater()

    def on_screenshot_clicked(self):
        """Handle screenshot button click - start screenshot capture"""
        try:
            logger.info("Screenshot button clicked")

            if not self.controller:
                logger.error("No controller available")
                return

            # Iniciar captura de pantalla
            if hasattr(self.controller, 'screenshot_controller'):
                self.controller.screenshot_controller.start_screenshot()
            else:
                logger.error("Screenshot controller not available")

        except Exception as e:
            logger.error(f"Error starting screenshot: {e}", exc_info=True)

    def on_advanced_search_clicked(self):
        """Handle advanced search button click - toggle advanced search window"""
        try:
            logger.info("Advanced search button clicked")

            if not self.controller:
                logger.error("No controller available")
                return

            # TOGGLE BEHAVIOR: If window exists and is visible, close it
            if self.advanced_search_window and self.advanced_search_window.isVisible():
                logger.debug("Advanced search window is visible - closing it (toggle)")
                self.advanced_search_window.close()
                return

            # Create advanced search window if it doesn't exist
            if not self.advanced_search_window:
                # Get db_manager from controller's config_manager
                db_manager = self.config_manager.db if self.config_manager else None
                self.advanced_search_window = AdvancedSearchWindow(
                    db_manager=db_manager,
                    config_manager=self.config_manager,
                    parent=self
                )
                self.advanced_search_window.item_clicked.connect(self.on_item_clicked)
                self.advanced_search_window.window_closed.connect(self.on_advanced_search_window_closed)
                self.advanced_search_window.url_open_requested.connect(self.on_url_open_in_browser)
                self.advanced_search_window.item_edit_requested.connect(self.on_item_edit_requested_from_search)

            # Show the window
            self.advanced_search_window.show()
            self.advanced_search_window.activateWindow()
            logger.info("Advanced search window opened")

        except Exception as e:
            logger.error(f"Error opening advanced search: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir búsqueda avanzada:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_advanced_search_window_closed(self):
        """Handle advanced search window closed"""
        logger.info("Advanced search window closed")
        if self.advanced_search_window:
            self.advanced_search_window.deleteLater()
            self.advanced_search_window = None

    def on_image_gallery_clicked(self):
        """Handle image gallery button click - toggle image gallery window"""
        try:
            logger.info("Image gallery button clicked")

            if not self.controller:
                logger.error("No controller available")
                return

            # TOGGLE BEHAVIOR: If window exists and is visible, close it
            if hasattr(self, 'image_gallery_window') and self.image_gallery_window and self.image_gallery_window.isVisible():
                logger.debug("Image gallery window is visible - closing it (toggle)")
                self.image_gallery_window.close()
                return

            # Create image gallery window if it doesn't exist
            if not hasattr(self, 'image_gallery_window') or not self.image_gallery_window:
                from controllers.image_gallery_controller import ImageGalleryController
                from views.image_gallery import ImageGalleryWindow

                # Get db_manager from controller's config_manager
                db_manager = self.config_manager.db if self.config_manager else None

                # Create gallery controller
                gallery_controller = ImageGalleryController(
                    db_manager=db_manager,
                    main_controller=self.controller
                )

                # Create gallery window
                self.image_gallery_window = ImageGalleryWindow(
                    controller=gallery_controller,
                    parent=self
                )
                self.image_gallery_window.closed.connect(self.on_image_gallery_window_closed)

            # Show the window
            self.image_gallery_window.show()
            self.image_gallery_window.activateWindow()
            logger.info("Image gallery window opened")

        except Exception as e:
            logger.error(f"Error opening image gallery: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir galería de imágenes:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_image_gallery_window_closed(self):
        """Handle image gallery window closed"""
        logger.info("Image gallery window closed")
        if hasattr(self, 'image_gallery_window') and self.image_gallery_window:
            self.image_gallery_window.deleteLater()
            self.image_gallery_window = None

    def on_projects_clicked(self):
        """Handle projects button click - toggle projects window"""
        try:
            logger.info("Projects button clicked")

            if not self.controller:
                logger.error("No controller available")
                return

            # TOGGLE BEHAVIOR: If window exists and is visible, close it
            if hasattr(self, 'projects_window') and self.projects_window and self.projects_window.isVisible():
                logger.debug("Projects window is visible - closing it (toggle)")
                self.projects_window.close()
                return

            # Create projects window if it doesn't exist
            if not hasattr(self, 'projects_window') or not self.projects_window:
                from views.projects_window import ProjectsWindow

                # Get db_manager from controller's config_manager
                db_manager = self.config_manager.db if self.config_manager else None

                if not db_manager:
                    logger.error("No database manager available")
                    QMessageBox.warning(
                        self,
                        "Error",
                        "No se pudo acceder a la base de datos"
                    )
                    return

                # Create projects window
                self.projects_window = ProjectsWindow(
                    db_manager=db_manager,
                    parent=self
                )
                self.projects_window.closed.connect(self.on_projects_window_closed)

            # Show the window
            self.projects_window.show()
            self.projects_window.activateWindow()
            logger.info("Projects window opened")

        except Exception as e:
            logger.error(f"Error opening projects window: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir ventana de proyectos:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_projects_window_closed(self):
        """Handle projects window closed"""
        logger.info("Projects window closed")
        if hasattr(self, 'projects_window') and self.projects_window:
            self.projects_window.deleteLater()
            self.projects_window = None

    def on_item_edit_requested_from_search(self, item):
        """Handle item edit request from Advanced Search Window"""
        try:
            logger.info(f"Edit requested for item: {item.label} (ID: {item.id})")

            # Open ItemEditorDialog with controller
            dialog = ItemEditorDialog(
                item=item,
                category_id=item.category_id if hasattr(item, 'category_id') else None,
                controller=self.controller,
                parent=self
            )

            # Connect signals to refresh search results
            dialog.item_updated.connect(lambda item_id, cat_id: self._refresh_search_results())
            dialog.item_created.connect(lambda cat_id: self._refresh_search_results())

            result = dialog.exec()

            if result:
                logger.info(f"Item '{item.label}' edited successfully from search")
            else:
                logger.info("Item edit dialog cancelled")

        except Exception as e:
            logger.error(f"Error opening item editor from search: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir editor de item:\n{str(e)}"
            )

    def _refresh_search_results(self):
        """Refresh search results after item edit"""
        try:
            if self.advanced_search_window and self.advanced_search_window.isVisible():
                logger.info("Refreshing search results after item edit")
                # Trigger a refresh in the advanced search window
                self.advanced_search_window._on_refresh()
        except Exception as e:
            logger.error(f"Error refreshing search results: {e}", exc_info=True)

    def on_favorites_clicked(self):
        """Handle favorites button click - show favorites panel"""
        try:
            logger.info("Favorites button clicked")

            # Toggle: Si ya está visible, ocultarlo
            if self.favorites_panel and self.favorites_panel.isVisible():
                logger.info("Hiding favorites panel")
                self.favorites_panel.hide()
                return

            # Crear panel si no existe
            if not self.favorites_panel:
                self.favorites_panel = FavoritesFloatingPanel()
                self.favorites_panel.favorite_executed.connect(self.on_favorite_executed)
                self.favorites_panel.window_closed.connect(self.on_favorites_panel_closed)
                logger.debug("Favorites panel created")

            # Posicionar cerca del sidebar
            self.favorites_panel.position_near_sidebar(self)

            # Mostrar panel
            self.favorites_panel.show()
            self.favorites_panel.refresh()

            logger.info("Favorites panel shown")

        except Exception as e:
            logger.error(f"Error in on_favorites_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar favoritos:\n{str(e)}"
            )

    def on_refresh_clicked(self):
        """Handle refresh button click - reload all categories and items from database"""
        try:
            logger.info("Refresh button clicked - reloading all data from database")

            # Llamar al método refresh_ui del controller
            if self.controller and hasattr(self.controller, 'refresh_ui'):
                self.controller.refresh_ui()
                logger.info("UI refreshed successfully")
            else:
                logger.warning("Controller not available or refresh_ui method not found")

        except Exception as e:
            logger.error(f"Error in on_refresh_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al refrescar la UI:\n{str(e)}"
            )

    def on_favorites_panel_closed(self):
        """Handle favorites panel closed"""
        logger.info("Favorites panel closed")
        if self.favorites_panel:
            self.favorites_panel.deleteLater()
            self.favorites_panel = None

    def on_favorite_executed(self, item_id: int):
        """Handle favorite item executed"""
        try:
            logger.info(f"Favorite item executed: {item_id}")

            # Buscar el item y ejecutarlo
            if self.controller:
                # Aquí deberías tener una forma de obtener el item por ID
                # Por ahora solo hacemos log
                logger.info(f"Executing favorite item {item_id}")

        except Exception as e:
            logger.error(f"Error executing favorite: {e}", exc_info=True)

    def on_stats_clicked(self):
        """Handle stats button click - show stats panel"""
        try:
            logger.info("Stats button clicked")

            # Toggle: Si ya está visible, ocultarlo
            if self.stats_panel and self.stats_panel.isVisible():
                logger.info("Hiding stats panel")
                self.stats_panel.hide()
                return

            # Crear panel si no existe
            if not self.stats_panel:
                self.stats_panel = StatsFloatingPanel()
                self.stats_panel.window_closed.connect(self.on_stats_panel_closed)
                logger.debug("Stats panel created")

            # Posicionar cerca del sidebar
            self.stats_panel.position_near_sidebar(self)

            # Mostrar panel
            self.stats_panel.show()
            self.stats_panel.refresh()

            logger.info("Stats panel shown")

        except Exception as e:
            logger.error(f"Error in on_stats_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar estadísticas:\n{str(e)}"
            )

    def on_stats_panel_closed(self):
        """Handle stats panel closed"""
        logger.info("Stats panel closed")
        if self.stats_panel:
            self.stats_panel.deleteLater()
            self.stats_panel = None

    def on_ai_bulk_clicked(self):
        """Handle AI Bulk creation button click - open wizard"""
        try:
            logger.info("AI Bulk button clicked")

            # Import dialog aquí para evitar circular imports
            from views.dialogs.ai_bulk_wizard import AIBulkWizard

            # Obtener DBManager del controller
            if not self.controller or not hasattr(self.controller, 'config_manager'):
                logger.error("Controller or config_manager not available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al gestor de base de datos."
                )
                return

            db_manager = self.controller.config_manager.db

            # Crear y mostrar wizard
            wizard = AIBulkWizard(db_manager, self)
            wizard.items_created.connect(self.on_bulk_items_created)

            logger.debug("Opening AI Bulk wizard")
            wizard.exec()

        except Exception as e:
            logger.error(f"Error in on_ai_bulk_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir el wizard de creación masiva:\n{str(e)}"
            )

    def on_ai_table_clicked(self):
        """Handle AI Table creation button click - open wizard"""
        try:
            logger.info("AI Table button clicked")

            # Import dialog aquí para evitar circular imports
            from views.dialogs.ai_table_wizard import AITableCreatorWizard

            # Obtener DBManager del controller
            if not self.controller or not hasattr(self.controller, 'config_manager'):
                logger.error("Controller or config_manager not available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al gestor de base de datos."
                )
                return

            db_manager = self.controller.config_manager.db

            # Crear y mostrar wizard
            wizard = AITableCreatorWizard(db_manager, self.controller, self)
            wizard.table_created.connect(self.on_ai_table_created)

            logger.debug("Opening AI Table wizard")
            wizard.exec()

        except Exception as e:
            logger.error(f"Error in on_ai_table_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir el wizard de creación de tabla con IA:\n{str(e)}"
            )

    def on_ai_table_created(self, table_name: str, items_count: int):
        """Callback when AI table is created"""
        try:
            logger.info(f"AI Table created: {table_name} with {items_count} items")

            # Refresh categories
            if self.controller:
                self.controller.load_categories()
                self.controller.invalidate_filter_cache()

            # Show success notification
            QMessageBox.information(
                self,
                "Tabla Creada",
                f"Tabla '{table_name}' creada exitosamente con {items_count} items."
            )

        except Exception as e:
            logger.error(f"Error in on_ai_table_created: {e}", exc_info=True)

    def on_table_creator_clicked(self):
        """Handle Table Creator button click - open wizard"""
        try:
            logger.info("Table Creator button clicked")

            # Obtener DBManager del controller
            if not self.controller or not hasattr(self.controller, 'config_manager'):
                logger.error("Controller or config_manager not available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al gestor de base de datos."
                )
                return

            db_manager = self.controller.config_manager.db

            # Crear y mostrar wizard
            wizard = TableCreatorWizard(db_manager, self.controller, self)
            wizard.table_created.connect(self.on_table_created)

            logger.debug("Opening Table Creator wizard")
            wizard.exec()

        except Exception as e:
            logger.error(f"Error in on_table_creator_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir el creador de tablas:\n{str(e)}"
            )

    def on_table_created(self, table_name: str, items_created: int):
        """
        Callback después de crear una tabla.

        Args:
            table_name: Nombre de la tabla creada
            items_created: Número de items creados
        """
        try:
            logger.info(f"Table created: {table_name} with {items_created} items")

            # Refresh UI - recargar categorías
            if self.controller:
                self.controller.load_categories()
                logger.debug("Categories reloaded after table creation")

                # Refresh sidebar para mostrar categorías actualizadas
                if hasattr(self, 'sidebar'):
                    self.sidebar.load_categories(self.controller.categories)
                    logger.debug("Sidebar categories refreshed")

            logger.info(f"Table '{table_name}' created successfully with {items_created} items")

        except Exception as e:
            logger.error(f"Error after table creation: {e}", exc_info=True)

    def on_tables_manager_clicked(self):
        """Handle Tables Manager button click - open centralized tables management window"""
        try:
            logger.info("Tables Manager button clicked")

            # Obtener DBManager del controller
            if not self.controller or not hasattr(self.controller, 'config_manager'):
                logger.error("Controller or config_manager not available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al gestor de base de datos."
                )
                return

            db_manager = self.controller.config_manager.db

            # Importar TablesManagerWindow
            from views.tables_manager_window import TablesManagerWindow

            # Crear y mostrar ventana de gestión
            tables_manager = TablesManagerWindow(db_manager, self.controller, self)
            tables_manager.tables_changed.connect(self.on_tables_changed)

            logger.debug("Opening Tables Manager window")
            tables_manager.show()

        except Exception as e:
            logger.error(f"Error in on_tables_manager_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir el gestor de tablas:\n{str(e)}"
            )

    def on_tables_changed(self):
        """Callback when tables are modified in the manager"""
        try:
            logger.info("Tables changed - refreshing UI")

            # Refresh UI - recargar categorías
            if self.controller:
                self.controller.load_categories()
                logger.debug("Categories reloaded after tables change")

                # Refresh sidebar para mostrar categorías actualizadas
                if hasattr(self, 'sidebar'):
                    self.sidebar.load_categories(self.controller.categories)
                    logger.debug("Sidebar categories refreshed")

                # Si hay un panel flotante abierto, recargarlo
                if hasattr(self, 'current_panel') and self.current_panel:
                    self.current_panel.refresh_items()
                    logger.debug("Current panel refreshed")

        except Exception as e:
            logger.error(f"Error after tables change: {e}", exc_info=True)

    def on_bulk_items_created(self, count: int):
        """
        Callback después de crear items bulk.

        Args:
            count: Número de items creados
        """
        try:
            logger.info(f"Bulk items created: {count}")

            # Refresh UI - recargar categorías
            if self.controller:
                self.controller.load_categories()
                logger.debug("Categories reloaded after bulk creation")

            # Mostrar notificación de éxito
            QMessageBox.information(
                self,
                "Éxito",
                f"Se crearon {count} items exitosamente."
            )

        except Exception as e:
            logger.error(f"Error in on_bulk_items_created: {e}", exc_info=True)

    def on_browser_clicked(self):
        """Handle browser button click - toggle browser window"""
        try:
            logger.info("Browser button clicked")

            # Mostrar cursor de espera mientras se carga el navegador
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # Delegar al controller para toggle del navegador
            if self.controller:
                self.controller.toggle_browser()
            else:
                logger.warning("Controller not available")

            # Restaurar cursor normal
            QApplication.restoreOverrideCursor()

        except Exception as e:
            # Restaurar cursor en caso de error
            QApplication.restoreOverrideCursor()
            logger.error(f"Error in on_browser_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir navegador:\n{str(e)}"
            )

    def open_structure_dashboard(self):
        """Open the structure dashboard"""
        try:
            logger.info("Opening structure dashboard...")

            if not self.controller:
                logger.error("No controller available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No hay controlador disponible"
                )
                return

            from views.dashboard.structure_dashboard import StructureDashboard

            # Create dashboard as non-modal window
            dashboard = StructureDashboard(
                db_manager=self.controller.config_manager.db,
                parent=self
            )

            # Store reference to keep it alive
            self.structure_dashboard = dashboard

            # Show as non-modal (allows interaction with main sidebar)
            dashboard.show()

            logger.info("Structure dashboard opened (non-modal)")

        except Exception as e:
            logger.error(f"Error opening structure dashboard: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir dashboard de estructura:\n{str(e)}"
            )

    def on_category_filter_clicked(self):
        """Handle category filter button click - show filter window"""
        try:
            logger.info("Category filter button clicked")

            # Toggle: Si ya está visible, ocultarlo
            if self.category_filter_window and self.category_filter_window.isVisible():
                logger.info("Hiding category filter window")
                self.category_filter_window.hide()
                return

            # Crear ventana si no existe
            if not self.category_filter_window:
                self.category_filter_window = CategoryFilterWindow(self)
                self.category_filter_window.filters_changed.connect(self.on_category_filters_changed)
                self.category_filter_window.filters_cleared.connect(self.on_category_filters_cleared)
                self.category_filter_window.window_closed.connect(self.on_category_filter_window_closed)
                logger.debug("Category filter window created")

            # Posicionar a la IZQUIERDA del sidebar
            sidebar_rect = self.geometry()
            filter_window_width = self.category_filter_window.width()
            window_x = sidebar_rect.left() - filter_window_width - 10
            window_y = sidebar_rect.top()
            self.category_filter_window.move(window_x, window_y)

            # Mostrar ventana
            self.category_filter_window.show()

            logger.info("Category filter window shown")

        except Exception as e:
            logger.error(f"Error in on_category_filter_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar filtros de categorías:\n{str(e)}"
            )

    def on_category_manager_clicked(self):
        """Handle category manager button click - show category manager window"""
        try:
            logger.info("Category manager button clicked")

            # Toggle: Si ya está visible, ocultarlo
            if hasattr(self, 'category_manager_window') and self.category_manager_window and self.category_manager_window.isVisible():
                logger.info("Hiding category manager window")
                self.category_manager_window.hide()
                return

            # Crear ventana si no existe
            if not hasattr(self, 'category_manager_window') or not self.category_manager_window:
                from views.dialogs.category_manager_window import CategoryManagerWindow
                self.category_manager_window = CategoryManagerWindow(
                    controller=self.controller,
                    parent=None  # Sin parent para que sea ventana independiente
                )
                self.category_manager_window.categories_changed.connect(self.on_categories_changed_from_manager)
                logger.debug("Category manager window created")

            # Posicionar a la IZQUIERDA del sidebar
            sidebar_rect = self.geometry()
            manager_window_width = self.category_manager_window.width()
            window_x = sidebar_rect.left() - manager_window_width - 10
            window_y = sidebar_rect.top()
            self.category_manager_window.move(window_x, window_y)

            # Mostrar ventana
            self.category_manager_window.show()
            self.category_manager_window.activateWindow()

            logger.info("Category manager window shown")

        except Exception as e:
            logger.error(f"Error in on_category_manager_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al mostrar gestor de categorías:\n{str(e)}"
            )

    def on_categories_changed_from_manager(self):
        """Handle categories changed from category manager - reload sidebar"""
        try:
            logger.info("Categories changed from manager, reloading sidebar")

            # Invalidar caché de filtros
            if self.controller and hasattr(self.controller, 'invalidate_filter_cache'):
                self.controller.invalidate_filter_cache()
                logger.debug("Filter cache invalidated")

            # Recargar categorías en el sidebar
            if self.controller:
                categories = self.controller.get_categories()
                self.load_categories(categories)
                logger.info(f"Sidebar reloaded with {len(categories)} categories")

        except Exception as e:
            logger.error(f"Error reloading categories: {e}", exc_info=True)

    def on_category_filters_changed(self, filters: dict):
        """Handle category filters changed"""
        try:
            logger.info(f"Category filters changed: {filters}")

            # Aplicar filtros a través del controller
            if self.controller:
                self.controller.apply_category_filters(filters)

        except Exception as e:
            logger.error(f"Error applying category filters: {e}", exc_info=True)

    def on_category_filters_cleared(self):
        """Handle category filters cleared"""
        try:
            logger.info("Category filters cleared")

            # Recargar todas las categorías
            if self.controller:
                self.controller.load_all_categories()

        except Exception as e:
            logger.error(f"Error clearing category filters: {e}", exc_info=True)

    def on_category_filter_window_closed(self):
        """Handle category filter window closed"""
        logger.info("Category filter window closed")
        # No eliminamos la ventana, solo la ocultamos para reutilizarla

    def on_quick_create_clicked(self):
        """Handle quick create button click - show quick create dialog"""
        try:
            logger.info("Quick create button clicked")

            if not self.controller:
                logger.error("No controller available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al controlador."
                )
                return

            # Create and show quick create dialog
            quick_create_dialog = QuickCreateDialog(
                controller=self.controller,
                parent=self
            )

            # Connect data_changed signal to reload categories
            quick_create_dialog.data_changed.connect(self.on_quick_create_data_changed)

            # Show dialog (modal)
            quick_create_dialog.exec()

            logger.info("Quick create dialog closed")

        except Exception as e:
            logger.error(f"Error in on_quick_create_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir creación rápida:\n{str(e)}"
            )

    def on_web_static_create_clicked(self):
        """Handle web static create button click - show WEB_STATIC wizard"""
        try:
            print("=" * 60)
            print("DEBUG: on_web_static_create_clicked LLAMADO")
            print("=" * 60)
            logger.info("Web static create button clicked")

            if not self.controller:
                logger.error("No controller available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al controlador."
                )
                return

            # Open the WEB_STATIC wizard via controller
            print("DEBUG: Abriendo wizard...")
            self.controller.open_create_web_static_wizard(parent=self)
            print("DEBUG: Wizard cerrado")

            logger.info("Web static wizard closed")

        except Exception as e:
            logger.error(f"Error in on_web_static_create_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir wizard WEB_STATIC:\n{str(e)}"
            )

    def on_quick_create_data_changed(self):
        """Handle data changed from quick create dialog - reload categories"""
        try:
            logger.info("Quick create data changed, reloading categories")

            if self.controller:
                # Reload categories from database
                categories = self.controller.config_manager.get_categories()
                self.load_categories(categories)
                logger.info("Categories reloaded successfully")

        except Exception as e:
            logger.error(f"Error reloading categories after quick create: {e}", exc_info=True)

    def on_create_process_clicked(self):
        """Handle create process button click - open ProcessBuilderWindow"""
        try:
            logger.info("Create process button clicked")

            if not self.controller:
                logger.error("No controller available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al controlador."
                )
                return

            # Check if ProcessController is initialized
            if not hasattr(self.controller, 'process_controller') or not self.controller.process_controller:
                logger.error("ProcessController not initialized")
                QMessageBox.warning(
                    self,
                    "Error",
                    "ProcessController no esta inicializado."
                )
                return

            # Import ProcessBuilderWindow
            from views.process_builder_window import ProcessBuilderWindow

            # Create and show process builder window
            builder_window = ProcessBuilderWindow(
                config_manager=self.controller.config_manager,
                process_controller=self.controller.process_controller,
                process_id=None,  # None = create new process
                list_controller=self.controller.list_controller,
                component_manager=self.controller.component_manager,
                parent=self
            )

            # Connect process_saved signal
            builder_window.process_saved.connect(self.on_process_saved)

            # Show window
            builder_window.show()

            logger.info("ProcessBuilderWindow opened")

        except Exception as e:
            logger.error(f"Error opening ProcessBuilderWindow: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir ventana de procesos:\n{str(e)}"
            )

    def on_process_saved(self, process_id: int):
        """Handle process saved event"""
        try:
            logger.info(f"Process saved: {process_id}")
            # Process saved successfully, could show notification or refresh something

        except Exception as e:
            logger.error(f"Error handling process saved: {e}", exc_info=True)

    def on_view_processes_clicked(self):
        """Handle view processes button click - open ProcessesFloatingPanel"""
        try:
            logger.info("View processes button clicked")

            if not self.controller:
                logger.error("No controller available")
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo acceder al controlador."
                )
                return

            # Check if ProcessController is initialized
            if not hasattr(self.controller, 'process_controller') or not self.controller.process_controller:
                logger.error("ProcessController not initialized")
                QMessageBox.warning(
                    self,
                    "Error",
                    "ProcessController no esta inicializado."
                )
                return

            # Import ProcessesFloatingPanel
            from views.processes_floating_panel import ProcessesFloatingPanel

            # Check if panel already exists and is not pinned
            if hasattr(self, 'processes_panel') and self.processes_panel and not self.processes_panel.is_pinned:
                # Reuse existing panel
                self.processes_panel.show()
                self.processes_panel.raise_()
                self.processes_panel.activateWindow()
                logger.info("Reusing existing processes panel")
                return

            # Create new panel
            self.processes_panel = ProcessesFloatingPanel(
                db_manager=self.controller.config_manager.db,
                config_manager=self.controller.config_manager,
                process_controller=self.controller.process_controller,
                parent=self,
                main_window=self
            )

            # Position near sidebar
            self.processes_panel.position_near_sidebar(self)

            # Load all processes
            self.processes_panel.load_all_processes()

            # Connect signals
            self.processes_panel.process_executed.connect(self.on_process_executed_from_panel)
            self.processes_panel.process_edited.connect(self.on_process_edit_requested)
            self.processes_panel.pin_state_changed.connect(self.on_processes_panel_pin_changed)
            self.processes_panel.window_closed.connect(self.on_processes_panel_closed)

            # Show panel
            self.processes_panel.show()

            logger.info("ProcessesFloatingPanel opened")

        except Exception as e:
            logger.error(f"Error opening ProcessesFloatingPanel: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir panel de procesos:\n{str(e)}"
            )

    def on_process_clicked(self, process_id: int):
        """Handle process button click from sidebar - show floating panel for specific process"""
        try:
            logger.info(f"Process button clicked: {process_id}")

            # Toggle: if same process and panel not pinned, hide it
            if (self.current_process_id == process_id and
                self.current_process_panel and
                self.current_process_panel.isVisible() and
                not self.current_process_panel.is_pinned):
                logger.info(f"Toggling off - hiding process panel: {process_id}")
                self.current_process_panel.hide()
                self.current_process_id = None
                return

            # Get process from controller
            if not self.controller or not self.controller.process_controller:
                logger.error("ProcessController not available")
                return

            process = self.controller.process_controller.get_process(process_id)

            if not process:
                logger.warning(f"Process {process_id} not found")
                return

            logger.info(f"Process found: {process.name}")

            # If current panel is pinned, add to pinned list
            if self.current_process_panel and self.current_process_panel.is_pinned:
                logger.info("Current process panel is pinned, adding to pinned_process_panels list")
                if self.current_process_panel not in self.pinned_process_panels:
                    self.pinned_process_panels.append(self.current_process_panel)
                self.current_process_panel = None

            # Create new panel if needed
            if not self.current_process_panel:
                from views.process_floating_panel import ProcessFloatingPanel

                self.current_process_panel = ProcessFloatingPanel(
                    process_controller=self.controller.process_controller,
                    config_manager=self.config_manager,
                    main_window=self,
                    parent=self
                )
                self.current_process_panel.item_clicked.connect(self.on_item_clicked)
                self.current_process_panel.window_closed.connect(self.on_process_panel_closed)
                self.current_process_panel.pin_state_changed.connect(self.on_process_panel_pin_changed)
                logger.debug("New process floating panel created")

            # Load process into panel
            self.current_process_panel.load_process(process)

            # Position near sidebar (with offset if pinned panels exist)
            self.position_process_panel(self.current_process_panel)

            # Update current process
            self.current_process_id = process_id

            logger.debug("Process loaded into floating panel")

        except Exception as e:
            logger.error(f"Error in on_process_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar proceso:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def on_process_panel_closed(self):
        """Handle process panel closed"""
        logger.info("Process panel closed")

        sender_panel = self.sender()

        # If it's the current (non-pinned) panel
        if sender_panel == self.current_process_panel:
            logger.info("Closing active (non-pinned) process panel")
            self.current_process_id = None
            self.current_process_panel = None
            # Clear active process button in sidebar
            if self.sidebar:
                self.sidebar.clear_active_process()
        # If it's a pinned panel
        elif sender_panel in self.pinned_process_panels:
            logger.info("Closing pinned process panel")
            self.pinned_process_panels.remove(sender_panel)

    def on_process_panel_pin_changed(self, is_pinned: bool):
        """Handle process panel pin state changed"""
        logger.info(f"Process panel pin state changed: {is_pinned}")
        # Panel state is managed in on_process_clicked

    def on_process_state_changed(self, process_id: int, is_active: bool):
        """Handle process state change - refresh sidebar"""
        logger.info(f"Process state changed: {process_id} -> is_active={is_active}")
        # Refresh sidebar to show/hide process button
        self.load_processes_to_sidebar()

    def position_process_panel(self, panel):
        """Position process panel near sidebar with offset for pinned panels"""
        # Position to the left of sidebar
        panel_x = self.x() - panel.width()

        # Calculate offset based on number of pinned process panels
        offset = len(self.pinned_process_panels) * 20

        panel.move(panel_x - offset, self.y())
        panel.show()

    def on_process_executed_from_panel(self, process_id: int):
        """Handle process execution from panel"""
        try:
            logger.info(f"Process {process_id} executed from panel")
            # Could show notification or update stats
        except Exception as e:
            logger.error(f"Error handling process execution: {e}", exc_info=True)

    def on_process_edit_requested(self, process_id: int):
        """Handle process edit request from panel"""
        try:
            logger.info(f"Edit requested for process {process_id}")

            # Import ProcessBuilderWindow
            from views.process_builder_window import ProcessBuilderWindow

            # Create builder window in edit mode
            builder_window = ProcessBuilderWindow(
                config_manager=self.controller.config_manager,
                process_controller=self.controller.process_controller,
                process_id=process_id,  # Edit mode
                list_controller=self.controller.list_controller,
                component_manager=self.controller.component_manager,
                parent=self
            )

            # Connect process_saved signal
            builder_window.process_saved.connect(self.on_process_updated)

            # Show window
            builder_window.show()

        except Exception as e:
            logger.error(f"Error opening process editor: {e}", exc_info=True)

    def on_process_updated(self, process_id: int):
        """Handle process updated event"""
        try:
            logger.info(f"Process {process_id} updated")

            # Reload processes panel if exists
            if hasattr(self, 'processes_panel') and self.processes_panel:
                self.processes_panel.reload_processes()

        except Exception as e:
            logger.error(f"Error handling process update: {e}", exc_info=True)

    def on_processes_panel_pin_changed(self, is_pinned: bool):
        """Handle processes panel pin state change"""
        try:
            logger.info(f"Processes panel pin state changed to: {is_pinned}")
            # Could track pinned panels
        except Exception as e:
            logger.error(f"Error handling pin state change: {e}", exc_info=True)

    def on_processes_panel_closed(self):
        """Handle processes panel closed"""
        try:
            logger.info("Processes panel closed")
            # Cleanup if needed
        except Exception as e:
            logger.error(f"Error handling panel close: {e}", exc_info=True)

    def on_item_clicked(self, item: Item):
        """Handle item button click"""
        try:
            logger.info(f"Item clicked: {item.label}")

            # Copy to clipboard via controller
            if self.controller:
                logger.debug(f"Copying item to clipboard: {item.content[:50]}...")
                self.controller.copy_item_to_clipboard(item)
                logger.info("Item copied to clipboard successfully")

            # Emit signal
            self.item_selected.emit(item)

        except Exception as e:
            logger.error(f"Error in on_item_clicked: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al copiar item:\n{str(e)}\n\nRevisa widget_sidebar_error.log"
            )

    def position_window(self):
        """Position window on the right edge of the screen, ocupando toda la altura"""
        # Get primary screen
        screen = self.screen()
        if screen is None:
            return

        screen_geometry = screen.availableGeometry()

        # Position on right edge, arriba del todo (y=0)
        x = screen_geometry.width() - self.width()
        y = screen_geometry.y()  # Arriba del todo (puede ser 0 o el offset si hay barra superior)

        self.move(x, y)

    def register_appbar(self):
        """Registrar la ventana como AppBar de Windows para reservar espacio permanentemente"""
        try:
            if sys.platform != 'win32':
                logger.warning("AppBar solo funciona en Windows")
                return

            # Get window handle
            hwnd = int(self.winId())
            if not hwnd:
                logger.error("No se pudo obtener el window handle")
                return

            # Get screen geometry
            screen = self.screen()
            if not screen:
                return

            screen_geometry = screen.availableGeometry()

            # Create APPBARDATA structure
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            abd.hWnd = hwnd
            abd.uCallbackMessage = 0
            abd.uEdge = ABE_RIGHT  # Lado derecho

            # Set the rectangle for the AppBar (right edge)
            abd.rc.left = screen_geometry.width() - self.width()
            abd.rc.top = screen_geometry.y()
            abd.rc.right = screen_geometry.width()
            abd.rc.bottom = screen_geometry.y() + screen_geometry.height()

            # Register the AppBar
            result = ctypes.windll.shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd))
            if result:
                logger.info("AppBar registrada exitosamente - espacio reservado en el escritorio")
                self.appbar_registered = True

                # Query and set position to reserve space
                ctypes.windll.shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
                ctypes.windll.shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))
            else:
                logger.warning("No se pudo registrar AppBar")

        except Exception as e:
            logger.error(f"Error al registrar AppBar: {e}")
            logger.debug(traceback.format_exc())

    def unregister_appbar(self):
        """Desregistrar la ventana como AppBar al cerrar"""
        try:
            if not self.appbar_registered:
                return

            if sys.platform != 'win32':
                return

            hwnd = int(self.winId())
            if not hwnd:
                return

            # Create APPBARDATA structure
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            abd.hWnd = hwnd

            # Unregister the AppBar
            ctypes.windll.shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
            self.appbar_registered = False
            logger.info("AppBar desregistrada")

        except Exception as e:
            logger.error(f"Error al desregistrar AppBar: {e}")

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def setup_hotkeys(self):
        """Setup global hotkeys"""
        self.hotkey_manager = HotkeyManager()

        # Register Ctrl+Shift+V to toggle window visibility
        self.hotkey_manager.register_hotkey("ctrl+shift+v", self.toggle_visibility)

        # Register Ctrl+Shift+N to toggle notebook
        self.hotkey_manager.register_hotkey("ctrl+shift+n", self.toggle_notebook)

        # Register Ctrl+Shift+P to open pinned panels manager
        self.hotkey_manager.register_hotkey("ctrl+shift+p", self.show_pinned_panels_manager)

        # Start listening for hotkeys
        self.hotkey_manager.start()

        print("Hotkeys registered: Ctrl+Shift+V (toggle window), Ctrl+Shift+N (toggle notebook), Ctrl+Shift+P (panels manager)")

    def setup_tray(self):
        """Setup system tray icon"""
        self.tray_manager = TrayManager()

        # Connect tray signals
        self.tray_manager.show_window_requested.connect(self.show_window)
        self.tray_manager.hide_window_requested.connect(self.hide_window)
        self.tray_manager.settings_requested.connect(self.show_settings)
        self.tray_manager.stats_dashboard_requested.connect(self.show_stats_dashboard)
        self.tray_manager.popular_items_requested.connect(self.show_popular_items)
        self.tray_manager.forgotten_items_requested.connect(self.show_forgotten_items)
        self.tray_manager.pinned_panels_requested.connect(self.open_pinned_panels_window)
        self.tray_manager.logout_requested.connect(self.logout_session)
        self.tray_manager.quit_requested.connect(self.quit_application)

        # Setup tray icon
        self.tray_manager.setup_tray(self)

        print("System tray icon created")

    def toggle_visibility(self):
        """Toggle window visibility"""
        if self.is_visible:
            self.hide_window()
        else:
            self.show_window()

    def toggle_notebook(self):
        """Toggle notebook window visibility (called by hotkey)"""
        if self.sidebar:
            self.sidebar.toggle_notebook()

    def show_window(self):
        """Show the window"""
        self.show()
        self.activateWindow()
        self.raise_()

    def minimize_window(self):
        """Toggle minimize/maximize sidebar height"""
        if self.is_minimized:
            # Maximizar - restaurar altura normal
            logger.info("Maximizing sidebar to normal height")
            self.is_minimized = False

            # Mostrar el sidebar
            if self.sidebar:
                self.sidebar.show()

            # Cambiar altura a normal
            self.setMinimumHeight(400)
            self.resize(70, self.normal_height)

            # Cambiar icono a minimizar (línea horizontal)
            self.minimize_button.setText("─")

            logger.info(f"Sidebar maximized to height: {self.normal_height}")
        else:
            # Minimizar - reducir altura para mostrar solo header "WS"
            logger.info("Minimizing sidebar to compact height")
            self.is_minimized = True

            # Ocultar el sidebar (todo excepto el title bar)
            if self.sidebar:
                self.sidebar.hide()

            # Cambiar altura a mínima (solo title bar)
            self.setMinimumHeight(self.minimized_height)
            self.resize(70, self.minimized_height)

            # Cambiar icono a maximizar (cuadrado)
            self.minimize_button.setText("□")

            logger.info(f"Sidebar minimized to height: {self.minimized_height}")

    def close_window(self):
        """Close the application"""
        logger.info("Closing application from close button")
        self.quit_application()

    def hide_window(self):
        """Hide the window"""
        self.hide()
        self.is_visible = False
        if self.tray_manager:
            self.tray_manager.update_window_state(False)
        print("Window hidden")

    def open_settings(self):
        """Open settings window"""
        print("Opening settings window...")
        settings_window = SettingsWindow(controller=self.controller, parent=self)
        settings_window.settings_changed.connect(self.on_settings_changed)

        if settings_window.exec() == QMessageBox.DialogCode.Accepted:
            print("Settings saved")

    def show_settings(self):
        """Show settings dialog (called from tray)"""
        self.open_settings()

    def open_component_manager(self):
        """Open component manager dialog"""
        print("Opening component manager...")
        from views.dialogs.component_manager_dialog import ComponentManagerDialog

        dialog = ComponentManagerDialog(
            component_manager=self.controller.component_manager,
            parent=self
        )
        dialog.component_types_changed.connect(self.on_component_types_changed)
        dialog.exec()

    def on_component_types_changed(self):
        """Handle component types changes"""
        print("Component types changed")
        # Invalidar caché del component manager
        self.controller.component_manager.invalidate_cache()

    def on_settings_changed(self):
        """Handle settings changes"""
        print("Settings changed - reloading...")

        # Reload categories in sidebar
        if self.controller:
            categories = self.controller.get_categories()
            self.sidebar.load_categories(categories)

        # Apply appearance settings (opacity, etc.)
        if self.config_manager:
            opacity = self.config_manager.get_setting("opacity", 0.95)
            self.setWindowOpacity(opacity)

        print("Settings applied")

    def logout_session(self):
        """Logout current session"""
        logger.info("Logging out...")

        # Confirm logout
        reply = QMessageBox.question(
            self,
            "Cerrar Sesión",
            "¿Estás seguro que deseas cerrar sesión?\n\nDeberás ingresar tu contraseña nuevamente al abrir la aplicación.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Invalidate session
            session_manager = SessionManager()
            session_manager.invalidate_session()
            logger.info("Session invalidated")

            # Show notification
            if self.tray_manager:
                self.tray_manager.show_message(
                    "Sesión Cerrada",
                    "Has cerrado sesión exitosamente. La aplicación se cerrará."
                )

            # Quit application
            self.quit_application()

    def quit_application(self):
        """Quit the application"""
        print("Quitting application...")

        # Unregister AppBar
        self.unregister_appbar()

        # Stop hotkey manager
        if self.hotkey_manager:
            self.hotkey_manager.stop()

        # Cleanup tray
        if self.tray_manager:
            self.tray_manager.cleanup()

        # Close window
        self.close()

        # Exit application
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def check_notifications_delayed(self):
        """Verificar notificaciones 10 segundos después de abrir"""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10000, self.check_notifications)  # 10 segundos

    def check_notifications(self):
        """Verificar y mostrar notificaciones pendientes"""
        try:
            notifications = self.notification_manager.get_pending_notifications()

            if not notifications:
                logger.info("No pending notifications")
                return

            # Mostrar solo las 2 primeras notificaciones (no saturar)
            priority_notifications = notifications[:2]

            logger.info(f"Found {len(notifications)} notifications, showing {len(priority_notifications)}")

            # Por ahora, solo mostramos un diálogo simple con la primera notificación de alta prioridad
            for notification in priority_notifications:
                if notification.get('priority') == 'high':
                    self.show_notification_message(notification)
                    break

        except Exception as e:
            logger.error(f"Error checking notifications: {e}")

    def show_notification_message(self, notification: dict):
        """Mostrar mensaje de notificación"""
        title = notification.get('title', 'Notificación')
        message = notification.get('message', '')
        action = notification.get('action', '')

        reply = QMessageBox.question(
            self,
            title,
            f"{message}\n\n¿Deseas verlo ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.handle_notification_action(action)

    def handle_notification_action(self, action: str):
        """Manejar acción de notificación"""
        try:
            if action == 'show_favorite_suggestions':
                self.show_favorite_suggestions()

            elif action == 'show_cleanup_suggestions':
                self.show_forgotten_items()

            elif action == 'show_abandoned_items':
                self.show_forgotten_items()

            elif action == 'show_failing_items':
                # TODO: Crear diálogo específico para items con errores
                QMessageBox.information(
                    self,
                    "Items con Errores",
                    "Funcionalidad en desarrollo"
                )

            elif action == 'show_slow_items':
                # TODO: Crear diálogo específico para items lentos
                QMessageBox.information(
                    self,
                    "Items Lentos",
                    "Funcionalidad en desarrollo"
                )

            elif action == 'show_shortcut_suggestions':
                # TODO: Crear diálogo para asignar atajos
                QMessageBox.information(
                    self,
                    "Sugerencias de Atajos",
                    "Funcionalidad en desarrollo"
                )

        except Exception as e:
            logger.error(f"Error handling notification action '{action}': {e}")

    def show_popular_items(self):
        """Mostrar diálogo de items populares"""
        try:
            dialog = PopularItemsDialog(self)
            dialog.item_selected.connect(self.on_popular_item_selected)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error showing popular items: {e}")
            QMessageBox.critical(self, "Error", f"Error al mostrar items populares:\n{str(e)}")

    def show_forgotten_items(self):
        """Mostrar diálogo de items olvidados"""
        try:
            dialog = ForgottenItemsDialog(self)
            if dialog.exec():
                # Recargar categorías si se eliminaron items
                if self.controller:
                    categories = self.controller.get_categories()
                    self.sidebar.load_categories(categories)
        except Exception as e:
            logger.error(f"Error showing forgotten items: {e}")
            QMessageBox.critical(self, "Error", f"Error al mostrar items olvidados:\n{str(e)}")

    def show_stats_dashboard(self):
        """Mostrar dashboard completo de estadísticas"""
        try:
            dialog = StatsDashboard(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error showing stats dashboard: {e}")
            QMessageBox.critical(self, "Error", f"Error al mostrar dashboard de estadísticas:\n{str(e)}")

    def show_favorite_suggestions(self):
        """Mostrar diálogo de sugerencias de favoritos"""
        try:
            dialog = FavoriteSuggestionsDialog(self)
            if dialog.exec():
                # Refrescar panel de favoritos si existe
                if self.favorites_panel:
                    self.favorites_panel.refresh()
        except Exception as e:
            logger.error(f"Error showing favorite suggestions: {e}")
            QMessageBox.critical(self, "Error", f"Error al mostrar sugerencias:\n{str(e)}")

    def on_popular_item_selected(self, item_id: int):
        """Handler cuando se selecciona un item popular"""
        logger.info(f"Popular item selected: {item_id}")
        # TODO: Abrir el item o mostrarlo en la lista principal

    def on_panel_customization_requested(self):
        """Handle customization request from a pinned panel"""
        sender_panel = self.sender()
        logger.info(f"Customization requested for panel: {sender_panel.get_display_name()}")

        # Get current values
        current_name = sender_panel.custom_name or ""
        current_color = sender_panel.custom_color or "#007acc"
        category_name = sender_panel.current_category.name if sender_panel.current_category else ""

        # Get current keyboard shortcut from database if panel is saved
        current_shortcut = ""
        if sender_panel.panel_id and self.controller:
            panel_data = self.controller.pinned_panels_manager.get_panel_by_id(sender_panel.panel_id)
            if panel_data:
                current_shortcut = panel_data.get('keyboard_shortcut', '')

        # Open config dialog
        dialog = PanelConfigDialog(
            current_name=current_name,
            current_color=current_color,
            current_shortcut=current_shortcut,
            category_name=category_name,
            parent=self
        )

        # Connect save signal
        dialog.config_saved.connect(lambda name, color, shortcut: self.on_panel_customized(sender_panel, name, color, shortcut))

        # Show dialog
        dialog.exec()

    def on_panel_customized(self, panel, custom_name: str, custom_color: str, keyboard_shortcut: str):
        """Handle panel customization save"""
        logger.info(f"[SHORTCUT DEBUG] on_panel_customized called with shortcut: '{keyboard_shortcut}'")
        logger.info(f"Applying customization - Name: '{custom_name}', Color: {custom_color}, Shortcut: '{keyboard_shortcut}'")
        logger.info(f"[SHORTCUT DEBUG] Panel has panel_id: {panel.panel_id}")

        # Update panel appearance
        panel.update_customization(custom_name=custom_name, custom_color=custom_color)

        # If panel has panel_id (saved in database), update there too
        if panel.panel_id and self.controller:
            logger.info(f"[SHORTCUT DEBUG] Updating panel {panel.panel_id} in database with shortcut: '{keyboard_shortcut}'")
            self.controller.pinned_panels_manager.update_panel_customization(
                panel_id=panel.panel_id,
                custom_name=custom_name if custom_name else None,
                custom_color=custom_color,
                keyboard_shortcut=keyboard_shortcut if keyboard_shortcut else None
            )
            logger.info(f"Updated panel {panel.panel_id} in database")

            # Update keyboard shortcut registration
            logger.info(f"[SHORTCUT DEBUG] About to unregister old shortcut for panel {panel.panel_id}")
            self.unregister_panel_shortcut(panel)  # Remove old shortcut if exists
            if keyboard_shortcut:  # Register new shortcut if provided
                logger.info(f"[SHORTCUT DEBUG] About to register new shortcut '{keyboard_shortcut}' for panel {panel.panel_id}")
                self.register_panel_shortcut(panel, keyboard_shortcut)
            else:
                logger.info(f"[SHORTCUT DEBUG] No shortcut to register (empty string)")

    def register_panel_shortcut(self, panel, shortcut_str: str):
        """
        Register a keyboard shortcut for a panel to toggle minimize/maximize

        Args:
            panel: FloatingPanel instance
            shortcut_str: Keyboard shortcut string (e.g., 'Ctrl+Shift+1')
        """
        logger.info(f"[SHORTCUT DEBUG] register_panel_shortcut called with: '{shortcut_str}', panel_id: {panel.panel_id}")

        if not shortcut_str:
            logger.warning(f"[SHORTCUT DEBUG] Empty shortcut_str, not registering")
            return

        if not panel.panel_id:
            logger.warning(f"[SHORTCUT DEBUG] Panel has no panel_id, not registering")
            return

        try:
            # Remove old shortcut if panel already has one
            logger.info(f"[SHORTCUT DEBUG] Removing old shortcut if exists")
            self.unregister_panel_shortcut(panel)

            # Create QShortcut
            logger.info(f"[SHORTCUT DEBUG] Creating QShortcut for '{shortcut_str}'")
            key_sequence = QKeySequence(shortcut_str)
            logger.info(f"[SHORTCUT DEBUG] QKeySequence created: {key_sequence.toString()}")

            shortcut = QShortcut(key_sequence, self)
            # CRITICAL: Set context to ApplicationShortcut so it works even when panel is minimized
            from PyQt6.QtCore import Qt
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            logger.info(f"[SHORTCUT DEBUG] QShortcut object created with ApplicationShortcut context")
            logger.info(f"[SHORTCUT DEBUG] Connecting to activation handler")
            shortcut.activated.connect(lambda: self.on_panel_shortcut_activated(panel))

            # Store references
            self.panel_shortcuts[panel.panel_id] = shortcut
            self.panel_by_shortcut[shortcut_str] = panel

            logger.info(f"[SHORTCUT DEBUG] Successfully registered shortcut {shortcut_str} for panel {panel.panel_id}")
            logger.info(f"[SHORTCUT DEBUG] Total registered shortcuts: {len(self.panel_shortcuts)}")
            logger.info(f"[SHORTCUT DEBUG] Shortcuts dict: {list(self.panel_shortcuts.keys())}")
        except Exception as e:
            logger.error(f"[SHORTCUT DEBUG] Failed to register shortcut {shortcut_str}: {e}", exc_info=True)

    def unregister_panel_shortcut(self, panel):
        """
        Unregister keyboard shortcut for a panel

        Args:
            panel: FloatingPanel instance
        """
        if not panel.panel_id:
            return

        try:
            # Find and remove shortcut
            if panel.panel_id in self.panel_shortcuts:
                shortcut = self.panel_shortcuts[panel.panel_id]

                # Find shortcut string to remove from lookup dict
                shortcut_str = None
                for key, value in self.panel_by_shortcut.items():
                    if value == panel:
                        shortcut_str = key
                        break

                # Disconnect and delete shortcut
                shortcut.setEnabled(False)
                shortcut.activated.disconnect()
                del self.panel_shortcuts[panel.panel_id]

                if shortcut_str:
                    del self.panel_by_shortcut[shortcut_str]

                logger.info(f"Unregistered shortcut for panel {panel.panel_id}")
        except Exception as e:
            logger.error(f"Failed to unregister shortcut for panel {panel.panel_id}: {e}", exc_info=True)

    def on_panel_shortcut_activated(self, panel):
        """
        Handle keyboard shortcut activation - toggle panel minimize/maximize

        Args:
            panel: FloatingPanel instance
        """
        try:
            logger.info(f"[SHORTCUT DEBUG] ========== SHORTCUT ACTIVATED ==========")
            logger.info(f"[SHORTCUT DEBUG] Shortcut activated for panel {panel.panel_id}")
            logger.info(f"[SHORTCUT DEBUG] Panel minimized state: {panel.is_minimized}")
            logger.info(f"[SHORTCUT DEBUG] Panel visible: {panel.isVisible()}")

            # Toggle minimize/maximize state
            logger.info(f"[SHORTCUT DEBUG] Calling panel.toggle_minimize()")
            panel.toggle_minimize()
            logger.info(f"[SHORTCUT DEBUG] After toggle, minimized state: {panel.is_minimized}")

            # Make sure panel is visible and on top
            if not panel.isVisible():
                logger.info(f"[SHORTCUT DEBUG] Panel not visible, showing it")
                panel.show()
            logger.info(f"[SHORTCUT DEBUG] Raising panel to front")
            panel.raise_()
            panel.activateWindow()
            logger.info(f"[SHORTCUT DEBUG] ========== SHORTCUT ACTIVATION COMPLETE ==========")

        except Exception as e:
            logger.error(f"[SHORTCUT DEBUG] Error handling shortcut activation for panel {panel.panel_id}: {e}", exc_info=True)

    def open_pinned_panels_window(self):
        """Open the pinned panels management window"""
        # Usar el nuevo método show_pinned_panels_manager()
        self.show_pinned_panels_manager()

    def restore_pinned_panels_on_startup(self):
        """AUTO-RESTORE: Restore active pinned panels from database on application startup"""
        if not self.controller:
            logger.warning("No controller available - skipping panel restoration")
            return

        try:
            # Get all active panels from database
            active_panels = self.controller.pinned_panels_manager.restore_panels_on_startup()

            if not active_panels:
                logger.info("No active panels to restore")
                return

            logger.info(f"Restoring {len(active_panels)} active panels from database...")

            # Restore each panel
            for panel_data in active_panels:
                try:
                    panel_id = panel_data['id']
                    category_id = panel_data['category_id']

                    # IMPORTANTE: Skip panels without category_id (those are global search panels)
                    if category_id is None:
                        logger.debug(f"Skipping panel {panel_id} - no category_id (global search panel)")
                        continue

                    # Get category
                    category = self.controller.get_category(str(category_id))
                    if not category:
                        logger.warning(f"Category {category_id} not found for panel {panel_id} - skipping")
                        continue

                    # Create new floating panel with saved configuration
                    restored_panel = FloatingPanel(
                        config_manager=self.config_manager,
                        list_controller=self.controller.list_controller if self.controller else None,
                        panel_id=panel_id,
                        custom_name=panel_data.get('custom_name'),
                        custom_color=panel_data.get('custom_color'),
                        main_window=self
                    )

                    # Connect signals
                    restored_panel.item_clicked.connect(self.on_item_clicked)
                    restored_panel.window_closed.connect(self.on_floating_panel_closed)
                    restored_panel.pin_state_changed.connect(self.on_panel_pin_changed)
                    restored_panel.customization_requested.connect(self.on_panel_customization_requested)
                    restored_panel.url_open_requested.connect(self.on_url_open_in_browser)

                    # Load category
                    restored_panel.load_category(category)

                    # Restore position and size
                    restored_panel.move(panel_data['x_position'], panel_data['y_position'])
                    restored_panel.resize(panel_data['width'], panel_data['height'])

                    # Apply custom styling
                    restored_panel.apply_custom_styling()

                    # Set as pinned
                    restored_panel.is_pinned = True
                    restored_panel.pin_button.setText("📍")
                    restored_panel.minimize_button.setVisible(True)
                    restored_panel.config_button.setVisible(True)

                    # Restore minimized state if needed
                    if panel_data.get('is_minimized'):
                        restored_panel.toggle_minimize()

                    # Restore filter configuration if available
                    if panel_data.get('filter_config'):
                        filter_config = self.controller.pinned_panels_manager._deserialize_filter_config(
                            panel_data['filter_config']
                        )
                        if filter_config:
                            restored_panel.apply_filter_config(filter_config)
                            logger.debug(f"Applied saved filters to panel {panel_id}")

                    # Add to pinned panels list
                    self.pinned_panels.append(restored_panel)

                    # Update last_opened in database
                    self.controller.pinned_panels_manager.mark_panel_opened(panel_id)

                    # Register keyboard shortcut if one is assigned
                    if panel_data.get('keyboard_shortcut'):
                        self.register_panel_shortcut(restored_panel, panel_data['keyboard_shortcut'])

                    # Show panel
                    restored_panel.show()

                    logger.info(f"Panel {panel_id} (Category: {category.name}) restored successfully")

                except Exception as e:
                    logger.error(f"Error restoring panel {panel_data.get('id', 'unknown')}: {e}", exc_info=True)
                    continue

            logger.info(f"Panel restoration complete: {len(self.pinned_panels)}/{len(active_panels)} panels restored")

        except Exception as e:
            logger.error(f"Error during panel restoration on startup: {e}", exc_info=True)

    def restore_pinned_global_search_panels(self):
        """Restaurar paneles de búsqueda global anclados desde la BD"""
        logger.info("=== [GLOBAL SEARCH RESTORE] Starting restore_pinned_global_search_panels() ===")

        if not self.controller:
            logger.warning("[GLOBAL SEARCH RESTORE] No controller available - skipping global search panels restoration")
            return

        try:
            logger.info("[GLOBAL SEARCH RESTORE] Calling get_global_search_panels(active_only=True)...")
            global_panels_data = self.controller.pinned_panels_manager.get_global_search_panels(active_only=True)
            logger.info(f"[GLOBAL SEARCH RESTORE] Retrieved {len(global_panels_data)} panels from database")

            if not global_panels_data:
                logger.info("[GLOBAL SEARCH RESTORE] No active global search panels to restore")
                return

            logger.info(f"[GLOBAL SEARCH RESTORE] Restoring {len(global_panels_data)} global search panels...")

            for panel_data in global_panels_data:
                try:
                    # Extraer configuración del panel
                    config = self.controller.pinned_panels_manager.restore_global_search_panel(panel_data)

                    # Crear nuevo panel de búsqueda global
                    from views.global_search_panel import GlobalSearchPanel
                    restored_panel = GlobalSearchPanel(
                        db_manager=self.config_manager.db if self.config_manager else None,
                        config_manager=self.config_manager,
                        list_controller=self.controller.list_controller if self.controller else None,
                        parent=self  # Conectar como hijo de MainWindow para señales
                    )

                    # Conectar señales
                    restored_panel.item_clicked.connect(self.on_item_clicked)
                    restored_panel.window_closed.connect(lambda p=restored_panel: self.on_restored_global_search_panel_closed(p))
                    restored_panel.pin_state_changed.connect(self.on_global_search_pin_state_changed)
                    restored_panel.url_open_requested.connect(self.on_url_open_in_browser)

                    # Restaurar propiedades
                    restored_panel.panel_id = config['panel_id']
                    restored_panel.panel_name = config['custom_name']
                    restored_panel.panel_color = config['custom_color']
                    restored_panel.is_pinned = True

                    # Restaurar posición y tamaño
                    restored_panel.move(config['position'][0], config['position'][1])
                    restored_panel.resize(config['size'][0], config['size'][1])

                    # Restaurar título
                    restored_panel.setWindowTitle(f"🔍 {config['custom_name']}")

                    # Restaurar filtros si existen
                    if config['search_query']:
                        restored_panel.search_bar.search_input.setText(config['search_query'])
                        restored_panel.pending_search_query = config['search_query']

                    if config['advanced_filters']:
                        restored_panel.current_filters = config['advanced_filters']

                    if config['state_filter']:
                        restored_panel.current_state_filter = config['state_filter']
                        # Establecer combo box de estado
                        index = restored_panel.state_filter_combo.findData(config['state_filter'])
                        if index >= 0:
                            restored_panel.state_filter_combo.setCurrentIndex(index)

                    # Actualizar UI
                    restored_panel.update_pin_button_style()
                    restored_panel.update_filter_badge()

                    # IMPORTANTE: Cargar todos los items primero
                    restored_panel.load_all_items()

                    # Realizar búsqueda inicial si hay query (después de cargar items)
                    if config['search_query']:
                        restored_panel._perform_search()

                    # Agregar a lista
                    self.pinned_global_search_panels.append(restored_panel)

                    # Actualizar last_opened en BD
                    self.controller.pinned_panels_manager.mark_panel_opened(config['panel_id'])

                    # IMPORTANTE: Mostrar panel ANTES de minimizar (si no, el estado minimizado no se mantiene)
                    restored_panel.show()

                    # Restaurar estado minimizado (DESPUÉS de show() para que funcione correctamente)
                    if config['is_minimized']:
                        restored_panel.is_minimized = False  # Asegurar que empieza en False
                        restored_panel.toggle_minimize()

                    logger.info(f"Global search panel {config['panel_id']} ({config['custom_name']}) restored successfully")

                except Exception as e:
                    logger.error(f"Failed to restore global search panel {panel_data.get('id', 'unknown')}: {e}", exc_info=True)
                    continue

            logger.info(f"Global search panel restoration complete: {len(self.pinned_global_search_panels)} panels restored")

        except Exception as e:
            logger.error(f"Failed to restore pinned global search panels: {e}", exc_info=True)

    def restore_pinned_process_panels(self):
        """Restore pinned process panels from database on startup"""
        logger.info("=== [PROCESS PANELS RESTORE] Starting restore_pinned_process_panels() ===")

        if not self.controller or not self.controller.process_controller:
            logger.warning("[PROCESS PANELS RESTORE] ProcessController not available - skipping restoration")
            return

        try:
            # Get all active process panels from database
            db = self.controller.config_manager.db
            active_panels = db.get_pinned_process_panels(active_only=True)

            if not active_panels:
                logger.info("[PROCESS PANELS RESTORE] No active process panels to restore")
                return

            logger.info(f"[PROCESS PANELS RESTORE] Restoring {len(active_panels)} process panels...")

            # Restore each panel
            for panel_data in active_panels:
                try:
                    panel_id = panel_data['id']
                    process_id = panel_data['process_id']

                    logger.info(f"[PROCESS PANELS RESTORE] Restoring panel {panel_id} for process {process_id}")

                    # Get process
                    process = self.controller.process_controller.get_process(process_id)
                    if not process:
                        logger.warning(f"Process {process_id} not found for panel {panel_id} - skipping")
                        continue

                    # Create new process floating panel
                    from views.process_floating_panel import ProcessFloatingPanel

                    restored_panel = ProcessFloatingPanel(
                        process_controller=self.controller.process_controller,
                        config_manager=self.config_manager,
                        main_window=self,
                        parent=self
                    )

                    # Set panel_id for persistence
                    restored_panel.panel_id = panel_id

                    # Connect signals
                    restored_panel.item_clicked.connect(self.on_item_clicked)
                    restored_panel.window_closed.connect(self.on_process_panel_closed)
                    restored_panel.pin_state_changed.connect(self.on_process_panel_pin_changed)

                    # Load process
                    restored_panel.load_process(process)

                    # Restore position and size
                    restored_panel.move(panel_data['x_position'], panel_data['y_position'])
                    restored_panel.resize(panel_data['width'], panel_data['height'])

                    # Set as pinned
                    restored_panel.is_pinned = True
                    restored_panel.pin_button.setText("📌")
                    restored_panel.pin_button.setToolTip("Desanclar panel")
                    restored_panel.minimize_button.setVisible(True)
                    # Update header color for pinned state
                    restored_panel.header_widget.setStyleSheet("""
                        QWidget {
                            background-color: #ff8800;
                            border-top-left-radius: 10px;
                            border-top-right-radius: 10px;
                        }
                    """)

                    # Restore minimized state if needed
                    if panel_data.get('is_minimized'):
                        restored_panel.is_minimized = False  # Start as not minimized
                        restored_panel.on_minimize_clicked()  # Toggle to minimized

                    # Add to pinned panels list
                    self.pinned_process_panels.append(restored_panel)

                    # Update last_opened in database
                    db.update_process_panel_last_opened(panel_id)

                    # Show panel
                    restored_panel.show()

                    logger.info(f"[PROCESS PANELS RESTORE] Panel {panel_id} for process '{process.name}' restored successfully")

                except Exception as e:
                    logger.error(f"Failed to restore process panel {panel_data.get('id', 'unknown')}: {e}", exc_info=True)
                    continue

            logger.info(f"[PROCESS PANELS RESTORE] Restoration complete: {len(self.pinned_process_panels)} panels restored")

        except Exception as e:
            logger.error(f"Error during process panels restoration: {e}", exc_info=True)

    def on_restore_panel_requested(self, panel_id: int):
        """Handle request to restore/open a saved panel"""
        logger.info(f"[MAIN WINDOW] Restore panel requested: {panel_id}")

        if not self.controller:
            logger.error("[MAIN WINDOW] No controller available")
            return

        # Get panel data from database
        panel_data = self.controller.pinned_panels_manager.get_panel_by_id(panel_id)
        logger.debug(f"[MAIN WINDOW] Panel data retrieved: {panel_data is not None}")

        if not panel_data:
            logger.error(f"[MAIN WINDOW] Panel {panel_id} not found in database")
            QMessageBox.warning(
                self,
                "Error",
                f"Panel {panel_id} no encontrado en la base de datos"
            )
            return

        # IMPORTANTE: Detectar tipo de panel (category vs global_search)
        panel_type = panel_data.get('panel_type', 'category')
        logger.debug(f"[MAIN WINDOW] Panel type: {panel_type}")

        if panel_type == 'global_search':
            # ===== PANEL DE BÚSQUEDA GLOBAL =====
            logger.info(f"[MAIN WINDOW] Restoring global search panel {panel_id}")

            # Check if panel is already open in pinned_global_search_panels
            for existing_panel in self.pinned_global_search_panels:
                if existing_panel.panel_id == panel_id:
                    logger.info(f"[MAIN WINDOW] Global search panel {panel_id} already open, focusing")
                    existing_panel.show()
                    existing_panel.raise_()
                    existing_panel.activateWindow()
                    return

            # Create new global search panel
            from views.global_search_panel import GlobalSearchPanel
            restored_panel = GlobalSearchPanel(
                db_manager=self.config_manager.db if self.config_manager else None,
                config_manager=self.config_manager,
                list_controller=self.controller.list_controller if self.controller else None,
                parent=self
            )

            # Set panel properties
            restored_panel.panel_id = panel_id
            restored_panel.panel_name = panel_data.get('custom_name', 'Búsqueda Global')
            restored_panel.panel_color = panel_data.get('custom_color', '#ff6b00')
            restored_panel.is_pinned = True

            # Connect signals
            restored_panel.item_clicked.connect(self.on_item_clicked)
            restored_panel.window_closed.connect(lambda p=restored_panel: self.on_restored_global_search_panel_closed(p))
            restored_panel.pin_state_changed.connect(self.on_global_search_pin_state_changed)
            restored_panel.url_open_requested.connect(self.on_url_open_in_browser)

            # Restore position and size
            restored_panel.move(panel_data['x_position'], panel_data['y_position'])
            restored_panel.resize(panel_data['width'], panel_data['height'])

            # Update UI
            restored_panel.update_pin_button_style()
            restored_panel.setWindowTitle(f"🔍 {restored_panel.panel_name}")

            # Load all items
            restored_panel.load_all_items()

            # Restore minimized state if needed
            if panel_data.get('is_minimized'):
                restored_panel.is_minimized = False  # Ensure starts as False
                restored_panel.toggle_minimize()

            # Add to pinned global search panels list
            self.pinned_global_search_panels.append(restored_panel)
            logger.debug(f"[MAIN WINDOW] Global search panel {panel_id} added to list. Total: {len(self.pinned_global_search_panels)}")

            # Update last_opened in database
            self.controller.pinned_panels_manager.mark_panel_opened(panel_id)

            # Show panel
            logger.info(f"[MAIN WINDOW] Showing global search panel {panel_id}")
            restored_panel.show()
            restored_panel.raise_()
            restored_panel.activateWindow()

            logger.info(f"[MAIN WINDOW] Global search panel {panel_id} restored successfully")

        else:
            # ===== PANEL DE CATEGORÍA (FLOATING PANEL) =====
            logger.info(f"[MAIN WINDOW] Restoring category panel {panel_id}")

            # Get category
            category = self.controller.get_category(str(panel_data['category_id']))
            logger.debug(f"[MAIN WINDOW] Category retrieved: {category is not None}")

            if not category:
                logger.error(f"[MAIN WINDOW] Category {panel_data['category_id']} not found")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Categoría {panel_data['category_id']} no encontrada"
                )
                return

            # Create new floating panel with saved configuration
            restored_panel = FloatingPanel(
                config_manager=self.config_manager,
                list_controller=self.controller.list_controller if self.controller else None,
                panel_id=panel_id,
                custom_name=panel_data.get('custom_name'),
                custom_color=panel_data.get('custom_color'),
                main_window=self
            )

            # Connect signals
            restored_panel.item_clicked.connect(self.on_item_clicked)
            restored_panel.window_closed.connect(self.on_floating_panel_closed)
            restored_panel.pin_state_changed.connect(self.on_panel_pin_changed)
            restored_panel.customization_requested.connect(self.on_panel_customization_requested)

            # Load category
            restored_panel.load_category(category)

            # Restore position and size
            restored_panel.move(panel_data['x_position'], panel_data['y_position'])
            restored_panel.resize(panel_data['width'], panel_data['height'])

            # Apply custom styling
            restored_panel.apply_custom_styling()

            # Set as pinned
            restored_panel.is_pinned = True
            restored_panel.pin_button.setText("📍")
            restored_panel.minimize_button.setVisible(True)
            restored_panel.config_button.setVisible(True)

            # Restore minimized state if needed
            if panel_data.get('is_minimized'):
                restored_panel.toggle_minimize()

            # Restore filter configuration if available
            if panel_data.get('filter_config'):
                filter_config = self.controller.pinned_panels_manager._deserialize_filter_config(
                    panel_data['filter_config']
                )
                if filter_config:
                    restored_panel.apply_filter_config(filter_config)
                    logger.debug(f"Applied saved filters to panel {panel_id}")

            # Add to pinned panels list
            self.pinned_panels.append(restored_panel)
            logger.debug(f"[MAIN WINDOW] Panel {panel_id} added to pinned_panels list. Total panels: {len(self.pinned_panels)}")

            # Update last_opened in database
            self.controller.pinned_panels_manager.mark_panel_opened(panel_id)

            # Show panel
            logger.info(f"[MAIN WINDOW] Showing panel {panel_id}")
            restored_panel.show()
            restored_panel.raise_()
            restored_panel.activateWindow()

            logger.info(f"[MAIN WINDOW] Panel {panel_id} restored and shown successfully")

    def on_panel_deleted_from_window(self, panel_id: int):
        """Handle panel deletion from management window"""
        logger.info(f"Panel {panel_id} deleted from window - checking if currently open")

        # Check if this panel is currently open and close it
        for panel in self.pinned_panels[:]:
            if panel.panel_id == panel_id:
                logger.info(f"Closing currently open panel {panel_id}")
                self.pinned_panels.remove(panel)
                panel.close()
                panel.deleteLater()
                break

    def on_panel_updated_from_window(self, panel_id: int, custom_name: str, custom_color: str):
        """Handle panel update from management window"""
        logger.info(f"Panel {panel_id} updated from window")

        # Update currently open panel if found
        for panel in self.pinned_panels:
            if panel.panel_id == panel_id:
                logger.info(f"Updating currently open panel {panel_id}")
                panel.update_customization(custom_name=custom_name, custom_color=custom_color)
                break

    def show_pinned_panels_manager(self):
        """Mostrar ventana de gestión de paneles anclados"""
        try:
            # Crear ventana si no existe
            if not hasattr(self, 'panels_manager_window') or not self.panels_manager_window:
                self.panels_manager_window = PinnedPanelsManagerWindow(
                    config_manager=self.config_manager,
                    pinned_panels_manager=self.controller.pinned_panels_manager,
                    main_window=self,
                    parent=None  # Sin parent para que sea ventana independiente
                )

                # Conectar señales
                self.panels_manager_window.panel_open_requested.connect(self.on_restore_panel_requested)
                self.panels_manager_window.panel_deleted.connect(self.on_panel_deleted_from_manager)
                self.panels_manager_window.panel_updated.connect(self.on_panel_updated_from_manager)

            # Refrescar y mostrar
            self.panels_manager_window.refresh_panel_list()
            self.panels_manager_window.show()
            self.panels_manager_window.raise_()
            self.panels_manager_window.activateWindow()

            logger.info("Pinned Panels Manager Window opened")

        except Exception as e:
            logger.error(f"Error opening panels manager window: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error al abrir gestor de paneles: {e}")

    def on_panel_deleted_from_manager(self, panel_id: int):
        """Handle cuando un panel es eliminado desde el manager"""
        try:
            # Remover panel de la lista si está abierto
            for i, panel in enumerate(self.pinned_panels):
                if panel.panel_id == panel_id:
                    panel.close()
                    self.pinned_panels.pop(i)
                    logger.info(f"Closed panel {panel_id} after deletion")
                    break
        except Exception as e:
            logger.error(f"Error handling panel deletion: {e}")

    def on_panel_updated_from_manager(self, panel_id: int):
        """Handle cuando un panel es actualizado desde el manager"""
        try:
            # Actualizar panel si está abierto
            for panel in self.pinned_panels:
                if panel.panel_id == panel_id:
                    # Recargar datos del panel
                    panel_data = self.controller.pinned_panels_manager.get_panel_by_id(panel_id)
                    if panel_data:
                        panel.custom_name = panel_data.get('custom_name')
                        panel.custom_color = panel_data.get('custom_color')
                        panel.apply_custom_styling()
                        logger.info(f"Updated panel {panel_id} styling")
                    break
        except Exception as e:
            logger.error(f"Error handling panel update: {e}")

    def on_global_search_panel_pinned(self, panel):
        """Callback cuando se ancla un panel de búsqueda global"""
        if panel not in self.pinned_global_search_panels:
            self.pinned_global_search_panels.append(panel)
            logger.info(f"Added global search panel {panel.panel_id} to pinned list")

            # IMPORTANTE: Limpiar self.global_search_panel para permitir crear nuevos paneles flotantes
            # Similar al comportamiento de FloatingPanel
            if self.global_search_panel == panel:
                self.global_search_panel = None
                logger.debug("Cleared self.global_search_panel reference after pinning")

            # Actualizar gestor de paneles si está abierto
            if hasattr(self, 'pinned_panels_window') and self.pinned_panels_window and self.pinned_panels_window.isVisible():
                self.pinned_panels_window.refresh_panels_list()

    def on_global_search_panel_unpinned(self, panel):
        """Callback cuando se desancla un panel de búsqueda global"""
        if panel in self.pinned_global_search_panels:
            self.pinned_global_search_panels.remove(panel)
            logger.info(f"Removed global search panel {panel.panel_id} from pinned list")

            # Actualizar gestor de paneles si está abierto
            if hasattr(self, 'pinned_panels_window') and self.pinned_panels_window and self.pinned_panels_window.isVisible():
                self.pinned_panels_window.refresh_panels_list()

    def closeEvent(self, event):
        """Override close event to minimize to tray instead of closing"""
        # Minimize to tray instead of closing
        event.ignore()
        self.hide_window()

        # Show notification on first minimize
        if self.tray_manager and self.is_visible:
            self.tray_manager.show_message(
                "Widget Sidebar",
                "La aplicación sigue ejecutándose en la bandeja del sistema"
            )
