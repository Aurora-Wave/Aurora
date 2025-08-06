import pyqtgraph as pg
from PySide6.QtCore import Qt
from Pyside.ui.utils.scroll_config import ScrollConfig


class SelectableViewBox(pg.ViewBox):
    """
    Custom ViewBox that supports synchronized region selection across multiple plots.
    """

    def __init__(self, viewer_tab, plot_index):
        """
        Args:
            viewer_tab (ViewerTab): Reference to the ViewerTab that contains this plot.
            plot_index (int): Index of this plot within viewer_tab.
        """
        super().__init__()
        self.viewer_tab = viewer_tab
        self.plot_index = plot_index
        self.setMouseMode(self.PanMode)
        self.region = None
        self._dragging = False
        self._drag_start = None

    def wheelEvent(self, ev, axis=None):
        """
        Manejar scroll del mouse para navegación sincronizada en ViewerTab.
        """
        # Verificar que el scrollbar esté disponible
        if (
            not hasattr(self.viewer_tab, "scrollbar")
            or self.viewer_tab.scrollbar is None
        ):
            ev.ignore()
            return

        # Usar configuración centralizada para scroll
        delta = ev.delta()
        scroll_amount = ScrollConfig.get_scroll_amount(delta, "viewer")

        # Verificar umbral mínimo
        if not ScrollConfig.should_scroll(scroll_amount):
            ev.accept()
            return

        # Obtener posición actual del scrollbar
        current_pos = self.viewer_tab.scrollbar.value()
        new_pos = current_pos + scroll_amount

        # Aplicar límites del scrollbar
        min_val = self.viewer_tab.scrollbar.minimum()
        max_val = self.viewer_tab.scrollbar.maximum()
        new_pos = max(min_val, min(max_val, new_pos))

        # Solo actualizar si hay cambio significativo
        if abs(int(new_pos) - current_pos) >= 1:
            # Actualizar scrollbar (esto triggereará automáticamente la actualización de todos los plots)
            self.viewer_tab.scrollbar.setValue(int(new_pos))

        ev.accept()

    def mouseDragEvent(self, ev, axis=None):
        """
        Allows synchronized vertical region selection across all plots.
        """
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return

        if ev.isStart():
            self._dragging = True
            self._drag_start = self.mapToView(ev.buttonDownPos())
            for i, p in enumerate(self.viewer_tab.plots):
                if self.viewer_tab._regions[i] is not None:
                    p.removeItem(self.viewer_tab._regions[i])
                region = pg.LinearRegionItem(
                    [self._drag_start.x(), self._drag_start.x()],
                    orientation=pg.LinearRegionItem.Vertical,
                )
                region.setZValue(10)
                p.addItem(region)
                self.viewer_tab._regions[i] = region

        elif ev.isFinish():
            self._dragging = False
            self._drag_start = None

        elif self._dragging and self._drag_start is not None:
            pos = self.mapToView(ev.pos())
            x0 = self._drag_start.x()
            x1 = pos.x()
            for region in self.viewer_tab._regions:
                if region is not None:
                    region.setRegion([x0, x1])
        ev.accept()

    def mouseClickEvent(self, ev):
        """
        Clears all selected regions on left click.
        """
        if ev.button() == Qt.LeftButton:
            if any(region is not None for region in self.viewer_tab._regions):
                for i, p in enumerate(self.viewer_tab.plots):
                    if self.viewer_tab._regions[i] is not None:
                        p.removeItem(self.viewer_tab._regions[i])
                        self.viewer_tab._regions[i] = None
                ev.accept()
                return
        super().mouseClickEvent(ev)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    window = QMainWindow()
    menu_bar = window.menuBar()
    file_menu = menu_bar.addMenu("File")

    window.show()
    sys.exit(app.exec())
