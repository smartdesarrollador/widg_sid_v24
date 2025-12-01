"""
Speed Dial Dialog - Dialog para agregar/editar accesos rápidos
Author: Widget Sidebar Team
Date: 2025-11-02
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QColorDialog, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)


class SpeedDialDialog(QDialog):
    """Dialog para agregar o editar un Speed Dial."""

    speed_dial_added = pyqtSignal(dict)  # Emite datos del speed dial creado

    def __init__(self, db_manager, speed_dial_data=None, parent=None):
        """
        Inicializa el dialog.

        Args:
            db_manager: Instancia de DBManager
            speed_dial_data: Datos del speed dial a editar (None para nuevo)
            parent: Widget padre
        """
        super().__init__(parent)
        self.db = db_manager
        self.speed_dial_data = speed_dial_data
        self.is_edit_mode = speed_dial_data is not None

        self.selected_color = '#16213e'  # Color por defecto

        self._setup_ui()
        self._apply_styles()

        if self.is_edit_mode:
            self._load_data()

    def _setup_ui(self):
        """Configura la interfaz del dialog."""
        title = "Editar Item de Menu" if self.is_edit_mode else "Nuevo Item de Menu"
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(450, 350)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header_label = QLabel(f"⚡ {title}")
        header_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                font-size: 20px;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(header_label)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Título
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Ej: Google, YouTube, GitHub...")
        form_layout.addRow("Título:", self.title_input)

        # URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.ejemplo.com")
        form_layout.addRow("URL:", self.url_input)

        # Icono (emoji)
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("🌐")
        self.icon_input.setMaxLength(2)
        self.icon_input.setFixedWidth(80)
        form_layout.addRow("Icono:", self.icon_input)

        # Color de fondo
        color_layout = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(40, 40)
        self.color_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {self.selected_color};
                border: 2px solid #00d4ff;
                border-radius: 5px;
            }}
        """)
        color_layout.addWidget(self.color_preview)

        self.color_btn = QPushButton("Elegir Color")
        self.color_btn.setFixedWidth(120)
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()

        form_layout.addRow("Color:", color_layout)

        main_layout.addLayout(form_layout)

        # Botones de acción
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        save_text = "Guardar" if self.is_edit_mode else "Agregar"
        self.save_btn = QPushButton(save_text)
        self.save_btn.setFixedWidth(100)
        self.save_btn.clicked.connect(self._save_speed_dial)
        button_layout.addWidget(self.save_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _apply_styles(self):
        """Aplica estilos al dialog."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                border: 2px solid #00d4ff;
                border-radius: 10px;
            }

            QLabel {
                color: #00d4ff;
                font-size: 13px;
            }

            QLineEdit {
                background-color: #16213e;
                color: #00d4ff;
                border: 1px solid #0f3460;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }

            QLineEdit:focus {
                border: 2px solid #00d4ff;
            }

            QPushButton {
                background-color: #0f3460;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #16213e;
                border: 2px solid #00d4ff;
            }

            QPushButton:pressed {
                background-color: #00d4ff;
                color: #1a1a2e;
            }
        """)

    def _load_data(self):
        """Carga los datos del speed dial en modo edición."""
        if not self.speed_dial_data:
            return

        self.title_input.setText(self.speed_dial_data.get('title', ''))
        self.url_input.setText(self.speed_dial_data.get('url', ''))
        self.icon_input.setText(self.speed_dial_data.get('icon', '🌐'))

        color = self.speed_dial_data.get('background_color', '#16213e')
        self.selected_color = color
        self.color_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border: 2px solid #00d4ff;
                border-radius: 5px;
            }}
        """)

    def _choose_color(self):
        """Abre el selector de color."""
        color = QColorDialog.getColor(
            QColor(self.selected_color),
            self,
            "Elegir color de fondo"
        )

        if color.isValid():
            self.selected_color = color.name()
            self.color_preview.setStyleSheet(f"""
                QLabel {{
                    background-color: {self.selected_color};
                    border: 2px solid #00d4ff;
                    border-radius: 5px;
                }}
            """)
            logger.debug(f"Color seleccionado: {self.selected_color}")

    def _save_speed_dial(self):
        """Guarda el speed dial en la base de datos."""
        # Validar campos
        title = self.title_input.text().strip()
        url = self.url_input.text().strip()
        icon = self.icon_input.text().strip() or '🌐'

        if not title:
            logger.warning("Título vacío")
            self.title_input.setFocus()
            return

        if not url:
            logger.warning("URL vacía")
            self.url_input.setFocus()
            return

        # Asegurar que la URL tenga protocolo
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            if self.is_edit_mode:
                # Actualizar existente
                speed_dial_id = self.speed_dial_data['id']
                success = self.db.update_speed_dial(
                    speed_dial_id,
                    title=title,
                    url=url,
                    icon=icon,
                    background_color=self.selected_color
                )

                if success:
                    logger.info(f"Speed dial actualizado: {title}")
                    self.accept()
                else:
                    logger.error("Error al actualizar speed dial")

            else:
                # Crear nuevo
                speed_dial_id = self.db.add_speed_dial(
                    title=title,
                    url=url,
                    icon=icon,
                    background_color=self.selected_color
                )

                if speed_dial_id:
                    logger.info(f"Speed dial creado: {title}")

                    # Emitir señal con los datos
                    self.speed_dial_added.emit({
                        'id': speed_dial_id,
                        'title': title,
                        'url': url,
                        'icon': icon,
                        'background_color': self.selected_color
                    })

                    self.accept()
                else:
                    logger.error("Error al crear speed dial")

        except Exception as e:
            logger.error(f"Error al guardar speed dial: {e}")
