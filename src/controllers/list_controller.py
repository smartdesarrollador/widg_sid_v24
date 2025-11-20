"""
List Controller
Gestiona la lógica de negocio de listas avanzadas
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.db_manager import DBManager
from core.clipboard_manager import ClipboardManager

logger = logging.getLogger(__name__)


class ListController(QObject):
    """
    Controlador para gestionar listas avanzadas

    Responsabilidades:
    - Validaciones de negocio
    - Orquestación de operaciones complejas
    - Emisión de señales PyQt6
    - Logging de operaciones
    """

    # Señales PyQt6
    list_created = pyqtSignal(str, int)  # (list_group, category_id)
    list_updated = pyqtSignal(str, int)  # (list_group, category_id)
    list_deleted = pyqtSignal(str, int)  # (list_group, category_id)
    list_renamed = pyqtSignal(str, str, int)  # (old_name, new_name, category_id)

    # Señales de ejecución secuencial
    execution_started = pyqtSignal(str, int)  # (list_group, total_items)
    execution_step = pyqtSignal(int, str)  # (step_number, label)
    execution_completed = pyqtSignal(str)  # (list_group)
    execution_cancelled = pyqtSignal()

    # Señales de error
    error_occurred = pyqtSignal(str)  # (error_message)

    def __init__(self, db_manager: DBManager, clipboard_manager: ClipboardManager = None):
        """
        Inicializa el controlador de listas

        Args:
            db_manager: Gestor de base de datos
            clipboard_manager: Gestor de portapapeles (opcional)
        """
        super().__init__()
        self.db = db_manager
        self.clipboard_manager = clipboard_manager or ClipboardManager()

        # Estado de ejecución secuencial
        self._execution_timer = None
        self._execution_items = []
        self._execution_index = 0
        self._execution_list_name = ""

        logger.info("ListController initialized")

    # ========== VALIDACIONES ==========

    def validate_list_data(self, list_name: str, items_data: List[Dict[str, Any]],
                          category_id: int = None, exclude_list: str = None) -> tuple[bool, str]:
        """
        Valida los datos de una lista antes de crear/actualizar

        Args:
            list_name: Nombre de la lista
            items_data: Lista de datos de items
            category_id: ID de categoría (para validar nombre único)
            exclude_list: Nombre de lista a excluir (para edición)

        Returns:
            Tuple (is_valid, error_message)
        """
        # Validar nombre de lista
        if not list_name or not list_name.strip():
            return False, "El nombre de la lista no puede estar vacío"

        if len(list_name) > 100:
            return False, "El nombre de la lista es demasiado largo (máximo 100 caracteres)"

        # Validar unicidad del nombre
        if category_id is not None:
            if not self.db.is_list_name_unique(category_id, list_name, exclude_list=exclude_list):
                return False, f"Ya existe una lista con el nombre '{list_name}' en esta categoría"

        # Validar items
        if not items_data or len(items_data) == 0:
            return False, "La lista debe tener al menos un paso/item"

        if len(items_data) > 50:
            return False, "La lista no puede tener más de 50 pasos"

        # Validar cada item
        for i, item in enumerate(items_data, 1):
            if not item.get('label'):
                return False, f"El paso #{i} debe tener un nombre/label"

            if len(item.get('label', '')) > 200:
                return False, f"El nombre del paso #{i} es demasiado largo"

        return True, ""

    # ========== OPERACIONES CRUD ==========

    def create_list_from_items(self, list_name: str, category_id: int, item_ids: List[int]) -> tuple[bool, str, List[int]]:
        """
        Crea una nueva lista a partir de items existentes (por sus IDs)

        Automáticamente agrega los tags ["lista", "nombre_de_la_lista"] a cada item

        Args:
            list_name: Nombre de la lista
            category_id: ID de la categoría destino
            item_ids: Lista de IDs de items existentes

        Returns:
            Tuple (success, message, new_item_ids)
        """
        try:
            # Crear tags automáticos para la lista: ["lista", "nombre_de_la_lista"]
            auto_tags = ["lista"]
            if list_name:
                auto_tags.append(list_name)

            # Obtener datos de los items existentes
            items_data = []
            for item_id in item_ids:
                # Obtener item de la BD
                item = self.db.get_item(item_id)
                if item:
                    # Obtener tags existentes del item
                    existing_tags = item.get('tags', [])
                    if isinstance(existing_tags, str):
                        # Parsear si viene como string
                        try:
                            import json
                            existing_tags = json.loads(existing_tags)
                        except:
                            existing_tags = [tag.strip() for tag in existing_tags.split(',') if tag.strip()]

                    # Combinar tags automáticos con tags existentes (sin duplicados)
                    combined_tags = auto_tags.copy()
                    for tag in existing_tags:
                        if tag and tag not in combined_tags:
                            combined_tags.append(tag)

                    # Crear dict con los datos necesarios para la lista
                    item_data = {
                        'label': item.get('label', ''),
                        'content': item.get('content', ''),
                        'type': item.get('type', 'text'),
                        'icon': item.get('icon'),
                        'description': item.get('description'),
                        'is_sensitive': item.get('is_sensitive', False),
                        'tags': combined_tags  # Agregar tags automáticos + existentes
                    }
                    items_data.append(item_data)
                else:
                    logger.warning(f"Item {item_id} not found - skipping")

            if not items_data:
                error_msg = "No se encontraron items válidos para crear la lista"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False, error_msg, []

            # Usar create_list con los datos obtenidos
            return self.create_list(category_id, list_name, items_data)

        except Exception as e:
            error_msg = f"Error al crear lista desde items: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False, error_msg, []

    def create_list(self, category_id: int, list_name: str,
                   items_data: List[Dict[str, Any]]) -> tuple[bool, str, List[int]]:
        """
        Crea una nueva lista con validaciones

        Args:
            category_id: ID de la categoría
            list_name: Nombre de la lista
            items_data: Lista de datos de items

        Returns:
            Tuple (success, message, item_ids)
        """
        # Validar datos
        is_valid, error_msg = self.validate_list_data(list_name, items_data, category_id)
        if not is_valid:
            logger.warning(f"Validación fallida al crear lista '{list_name}': {error_msg}")
            self.error_occurred.emit(error_msg)
            return False, error_msg, []

        try:
            # Crear lista en la base de datos
            item_ids = self.db.create_list(category_id, list_name, items_data)

            logger.info(f"Lista creada exitosamente: '{list_name}' ({len(item_ids)} items)")
            self.list_created.emit(list_name, category_id)

            return True, f"Lista '{list_name}' creada con {len(item_ids)} pasos", item_ids

        except Exception as e:
            error_msg = f"Error al crear lista: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False, error_msg, []

    def update_list(self, category_id: int, old_list_group: str,
                   new_list_group: str = None, items_data: List[Dict[str, Any]] = None) -> tuple[bool, str]:
        """
        Actualiza una lista existente

        Args:
            category_id: ID de la categoría
            old_list_group: Nombre actual de la lista
            new_list_group: Nuevo nombre (opcional)
            items_data: Nuevos datos de items (opcional)

        Returns:
            Tuple (success, message)
        """
        try:
            # Si se está renombrando, validar nuevo nombre
            if new_list_group and new_list_group != old_list_group:
                is_valid, error_msg = self.validate_list_data(
                    new_list_group, items_data or [], category_id, exclude_list=old_list_group
                )
                if not is_valid and "al menos un" not in error_msg:  # Ignorar error de items vacíos si solo renombramos
                    self.error_occurred.emit(error_msg)
                    return False, error_msg

            # Si se están actualizando items, validar
            if items_data is not None:
                final_name = new_list_group if new_list_group else old_list_group
                is_valid, error_msg = self.validate_list_data(final_name, items_data, category_id, exclude_list=old_list_group)
                if not is_valid:
                    self.error_occurred.emit(error_msg)
                    return False, error_msg

            # Actualizar en la base de datos
            success = self.db.update_list(category_id, old_list_group, new_list_group, items_data)

            if success:
                final_name = new_list_group if new_list_group else old_list_group
                logger.info(f"Lista actualizada exitosamente: '{old_list_group}' -> '{final_name}'")

                if new_list_group and new_list_group != old_list_group:
                    self.list_renamed.emit(old_list_group, new_list_group, category_id)
                else:
                    self.list_updated.emit(final_name, category_id)

                return True, f"Lista '{final_name}' actualizada exitosamente"
            else:
                return False, "Error al actualizar lista"

        except Exception as e:
            error_msg = f"Error al actualizar lista: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False, error_msg

    def delete_list(self, category_id: int, list_group: str) -> tuple[bool, str]:
        """
        Elimina una lista completa

        Args:
            category_id: ID de la categoría
            list_group: Nombre de la lista

        Returns:
            Tuple (success, message)
        """
        try:
            # Eliminar de la base de datos
            success = self.db.delete_list(category_id, list_group)

            if success:
                logger.info(f"Lista eliminada exitosamente: '{list_group}'")
                self.list_deleted.emit(list_group, category_id)
                return True, f"Lista '{list_group}' eliminada"
            else:
                return False, "Error al eliminar lista"

        except Exception as e:
            error_msg = f"Error al eliminar lista: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False, error_msg

    def rename_list(self, category_id: int, old_name: str, new_name: str) -> tuple[bool, str]:
        """
        Renombra una lista (wrapper conveniente de update_list)

        Args:
            category_id: ID de la categoría
            old_name: Nombre actual
            new_name: Nuevo nombre

        Returns:
            Tuple (success, message)
        """
        return self.update_list(category_id, old_name, new_list_group=new_name)

    # ========== CONSULTAS ==========

    def get_lists(self, category_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene todas las listas de una categoría

        Args:
            category_id: ID de la categoría

        Returns:
            Lista de diccionarios con info de listas
        """
        try:
            return self.db.get_lists_by_category(category_id)
        except Exception as e:
            logger.error(f"Error al obtener listas: {e}", exc_info=True)
            return []

    def get_list_items(self, category_id: int, list_group: str) -> List[Dict[str, Any]]:
        """
        Obtiene los items de una lista específica

        Args:
            category_id: ID de la categoría
            list_group: Nombre de la lista

        Returns:
            Lista de items ordenados
        """
        try:
            return self.db.get_list_items(category_id, list_group)
        except Exception as e:
            logger.error(f"Error al obtener items de lista: {e}", exc_info=True)
            return []

    def get_list_count(self, category_id: int) -> int:
        """
        Obtiene el número total de listas en una categoría

        Args:
            category_id: ID de la categoría

        Returns:
            Número de listas
        """
        listas = self.get_lists(category_id)
        return len(listas)

    # ========== OPERACIONES DE CLIPBOARD ==========

    def copy_all_list_items(self, category_id: int, list_group: str, separator: str = '\n') -> tuple[bool, str]:
        """
        Copia todo el contenido de una lista al clipboard

        Args:
            category_id: ID de la categoría
            list_group: Nombre de la lista
            separator: Separador entre items (por defecto salto de línea)

        Returns:
            Tuple (success, message)
        """
        try:
            items = self.get_list_items(category_id, list_group)

            if not items:
                return False, "La lista está vacía"

            # Concatenar contenidos
            contents = [item['content'] for item in items]
            combined_content = separator.join(contents)

            # Copiar al clipboard
            success = self.clipboard_manager.copy_text(combined_content)

            if success:
                logger.info(f"Contenido completo de lista '{list_group}' copiado al clipboard ({len(items)} items)")
                return True, f"Copiados {len(items)} pasos de '{list_group}'"
            else:
                return False, "Error al copiar al clipboard"

        except Exception as e:
            error_msg = f"Error al copiar lista: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False, error_msg

    # ========== EJECUCIÓN SECUENCIAL ==========

    def execute_list_sequentially(self, category_id: int, list_group: str, delay_ms: int = 500) -> bool:
        """
        Ejecuta una lista secuencialmente, copiando cada item al clipboard con delay

        Args:
            category_id: ID de la categoría
            list_group: Nombre de la lista
            delay_ms: Delay entre cada paso en milisegundos (default 500ms)

        Returns:
            bool: True si se inició la ejecución
        """
        try:
            # Obtener items de la lista
            items = self.get_list_items(category_id, list_group)

            if not items:
                self.error_occurred.emit("La lista está vacía")
                return False

            # Cancelar ejecución previa si existe
            self.cancel_execution()

            # Configurar ejecución
            self._execution_items = items
            self._execution_index = 0
            self._execution_list_name = list_group

            # Crear y configurar timer
            self._execution_timer = QTimer()
            self._execution_timer.timeout.connect(self._execute_next_step)

            # Emitir señal de inicio
            self.execution_started.emit(list_group, len(items))
            logger.info(f"Iniciando ejecución secuencial de lista '{list_group}' ({len(items)} pasos, {delay_ms}ms delay)")

            # Ejecutar primer paso inmediatamente
            self._execute_next_step()

            # Iniciar timer para siguientes pasos
            if len(items) > 1:
                self._execution_timer.start(delay_ms)

            return True

        except Exception as e:
            error_msg = f"Error al ejecutar lista: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False

    def _execute_next_step(self):
        """Ejecuta el siguiente paso de la lista (método interno)"""
        if self._execution_index >= len(self._execution_items):
            # Ejecución completada
            self._finish_execution()
            return

        # Obtener item actual
        item = self._execution_items[self._execution_index]
        step_number = self._execution_index + 1

        try:
            # Copiar contenido al clipboard
            self.clipboard_manager.copy_text(item['content'])

            # Emitir señal de paso ejecutado
            self.execution_step.emit(step_number, item['label'])
            logger.debug(f"Paso {step_number}/{len(self._execution_items)} ejecutado: {item['label']}")

            # Incrementar índice
            self._execution_index += 1

        except Exception as e:
            logger.error(f"Error al ejecutar paso {step_number}: {e}")
            self._finish_execution()

    def _finish_execution(self):
        """Finaliza la ejecución secuencial"""
        if self._execution_timer:
            self._execution_timer.stop()
            self._execution_timer = None

        list_name = self._execution_list_name
        self._execution_items = []
        self._execution_index = 0
        self._execution_list_name = ""

        self.execution_completed.emit(list_name)
        logger.info(f"Ejecución secuencial de lista '{list_name}' completada")

    def cancel_execution(self):
        """Cancela la ejecución secuencial actual"""
        if self._execution_timer and self._execution_timer.isActive():
            self._execution_timer.stop()
            self._execution_timer = None
            self._execution_items = []
            self._execution_index = 0
            self._execution_list_name = ""

            self.execution_cancelled.emit()
            logger.info("Ejecución secuencial cancelada")

    def is_executing(self) -> bool:
        """Retorna True si hay una ejecución secuencial en curso"""
        return self._execution_timer is not None and self._execution_timer.isActive()
