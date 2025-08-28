"""
Context Menu utilities for Aurora UI components.
Centralized context menu creation and management.
"""

from typing import List, Callable
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction


class PlotContextMenu:
    """Utility class for creating context menus for plot widgets."""
    
    @staticmethod
    def create_plot_menu(
        parent_widget,
        available_signals: List[str], 
        current_signal: str,
        on_color_change: Callable,
        on_signal_change: Callable,
        on_remove: Callable
    ) -> QMenu:
        """
        Create plot context menu with standard options.
        
        Args:
            parent_widget: Parent widget for the menu
            available_signals: List of available signal names
            current_signal: Currently selected signal name
            on_color_change: Callback for color change
            on_signal_change: Callback for signal change (receives signal_name)
            on_remove: Callback for plot removal
            
        Returns:
            QMenu: Configured context menu
        """
        menu = QMenu(parent_widget)
        
        # Color action
        color_action = QAction("Change Color", parent_widget)
        color_action.triggered.connect(on_color_change)
        menu.addAction(color_action)
        
        # Signal change action with submenu
        if available_signals and len(available_signals) > 1:
            signal_action = QAction("Change Signal", parent_widget)
            signal_submenu = QMenu("Select Signal", parent_widget)
            
            for signal in available_signals:
                if signal != current_signal:  # Don't show current signal
                    action = QAction(signal, parent_widget)
                    action.triggered.connect(lambda checked, s=signal: on_signal_change(s))
                    signal_submenu.addAction(action)
            
            signal_action.setMenu(signal_submenu)
            menu.addAction(signal_action)
        
        menu.addSeparator()
        
        # Remove action
        remove_action = QAction("Remove Plot", parent_widget)
        remove_action.triggered.connect(on_remove)
        menu.addAction(remove_action)
        
        return menu
    
    @staticmethod
    def show_menu(menu: QMenu, parent_widget, position):
        """
        Show context menu at the specified position.
        
        Args:
            menu: QMenu to display
            parent_widget: Parent widget for position mapping
            position: Local position to show menu
        """
        global_pos = parent_widget.mapToGlobal(position)
        menu.exec(global_pos)