"""
scroll_config.py
---------------
Configuración y utilidades para el scroll sincronizado con mouse wheel
"""


class ScrollConfig:
    """Configuración global para el comportamiento del scroll wheel"""

    # Sensibilidades por tipo de tab (segundos por notch de wheel)
    VIEWER_TAB_SENSITIVITY = 5.0  # ViewerTab: navegación general
    TILT_TAB_SENSITIVITY = 3.0  # TiltTab: navegación de eventos
    # ANALYSIS_TAB_SENSITIVITY removido - sin scroll wheel

    # Dirección del scroll (True = natural, False = tradicional)
    NATURAL_SCROLLING = True

    # Umbral mínimo para activar scroll (evita micro-movimientos)
    SCROLL_THRESHOLD = 0.1

    @classmethod
    def get_scroll_amount(cls, delta, tab_type):
        """
        Calcular cantidad de scroll basada en delta y tipo de tab

        Args:
            delta: Delta del evento de wheel
            tab_type: 'viewer' o 'tilt' (analysis sin scroll)

        Returns:
            float: Cantidad de scroll en segundos
        """
        sensitivities = {
            "viewer": cls.VIEWER_TAB_SENSITIVITY,
            "tilt": cls.TILT_TAB_SENSITIVITY,
        }

        base_amount = delta / 120.0 * sensitivities.get(tab_type, 3.0)

        # Aplicar dirección natural si está habilitada
        if cls.NATURAL_SCROLLING:
            base_amount = -base_amount

        return base_amount

    @classmethod
    def should_scroll(cls, amount):
        """
        Determinar si el scroll debe aplicarse basado en el umbral

        Args:
            amount: Cantidad de scroll calculada

        Returns:
            bool: True si debe aplicarse el scroll
        """
        return abs(amount) > cls.SCROLL_THRESHOLD


def create_wheel_event_handler(target_widget, tab_type, update_callback):
    """
    Factory para crear handlers de wheel events consistentes

    Args:
        target_widget: Widget que recibe el scroll (scrollbar, spinbox, etc.)
        tab_type: Tipo de tab ('viewer', 'tilt', 'analysis')
        update_callback: Función para ejecutar después del scroll

    Returns:
        function: Handler de wheel event configurado
    """

    def wheel_handler(ev):
        try:
            # Calcular scroll amount
            delta = ev.delta()
            scroll_amount = ScrollConfig.get_scroll_amount(delta, tab_type)

            # Verificar umbral
            if not ScrollConfig.should_scroll(scroll_amount):
                ev.accept()
                return

            # Obtener valor actual del widget objetivo
            if hasattr(target_widget, "value"):
                current_value = target_widget.value()
                new_value = current_value + scroll_amount

                # Aplicar límites si existen
                if hasattr(target_widget, "minimum") and hasattr(
                    target_widget, "maximum"
                ):
                    min_val = target_widget.minimum()
                    max_val = target_widget.maximum()
                    new_value = max(min_val, min(max_val, new_value))

                # Actualizar solo si hay cambio significativo
                if abs(new_value - current_value) > ScrollConfig.SCROLL_THRESHOLD:
                    target_widget.setValue(int(new_value))

                    # Ejecutar callback si se proporciona
                    if update_callback:
                        update_callback()

            ev.accept()

        except Exception as e:
            # Fallar silenciosamente para no interrumpir la UI
            ev.ignore()

    return wheel_handler
