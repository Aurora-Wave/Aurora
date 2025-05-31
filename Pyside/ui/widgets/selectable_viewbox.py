"""
selectable_viewbox.py
--------------------
ViewBox personalizado para selección sincronizada de regiones en múltiples gráficos.
Permite seleccionar y limpiar regiones de interés de forma coordinada.
"""

import pyqtgraph as pg
from PySide6.QtCore import Qt

class SelectableViewBox(pg.ViewBox):
    """
    ViewBox personalizado para selección sincronizada de regiones en múltiples gráficos.
    Permite seleccionar una región con arrastre y limpiar con click.
    """
    def __init__(self, main_window, plot_index):
        """
        Args:
            main_window (QMainWindow): Referencia a la ventana principal.
            plot_index (int): Índice del gráfico asociado.
        """
        super().__init__()
        self.main_window = main_window
        self.plot_index = plot_index
        self.setMouseMode(self.PanMode)  # Deshabilita zoom con mouse
        self.region = None
        self._dragging = False
        self._drag_start = None

    def mouseDragEvent(self, ev, axis=None):
        """
        Permite seleccionar una región vertical sincronizada en todos los gráficos.
        Args:
            ev: Evento de arrastre de mouse.
            axis: Eje (no usado).
        """
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return
        viewer_tab = self.main_window.viewer_tab
        if ev.isStart():
            self._dragging = True
            self._drag_start = self.mapToView(ev.buttonDownPos())
            for i, p in enumerate(viewer_tab.plots):
                if viewer_tab._regions[i] is not None:
                    p.removeItem(viewer_tab._regions[i])
                region = pg.LinearRegionItem([self._drag_start.x(), self._drag_start.x()], orientation=pg.LinearRegionItem.Vertical)
                region.setZValue(10)
                p.addItem(region)
                viewer_tab._regions[i] = region
        elif ev.isFinish():
            self._dragging = False
            self._drag_start = None
        elif self._dragging and self._drag_start is not None:
            pos = self.mapToView(ev.pos())
            x0 = self._drag_start.x()
            x1 = pos.x()
            for region in viewer_tab._regions:
                if region is not None:
                    region.setRegion([x0, x1])
        ev.accept()

    def mouseClickEvent(self, ev):
        """
        Limpia todas las regiones seleccionadas con un click izquierdo.
        Args:
            ev: Evento de click de mouse.
        """
        if ev.button() == Qt.LeftButton:
            viewer_tab = self.main_window.viewer_tab
            if any(region is not None for region in viewer_tab._regions):
                for i, p in enumerate(viewer_tab.plots):
                    if viewer_tab._regions[i] is not None:
                        p.removeItem(viewer_tab._regions[i])
                        viewer_tab._regions[i] = None
                ev.accept()
                return
        super().mouseClickEvent(ev)
