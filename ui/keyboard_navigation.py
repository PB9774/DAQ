"""Five-key navigation for every visible control in the BMS dashboard.

Arrow keys move focus through controls in visual reading order. Enter activates
buttons, opens combo boxes, edits sliders, and opens selected log records. The
bottom navigation bar uses Left/Right to choose pages and Enter to open them.
"""
from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import (
    QApplication, QAbstractButton, QAbstractItemView, QComboBox,
    QDoubleSpinBox, QLineEdit, QListWidget, QSlider, QSpinBox,
    QTableWidget, QTreeWidget, QWidget,
)

CONTROL_TYPES = (QAbstractButton, QComboBox, QSlider, QSpinBox,
                 QDoubleSpinBox, QTableWidget, QListWidget, QTreeWidget,
                 QLineEdit)
ARROWS = (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)
ENTER_KEYS = (Qt.Key_Return, Qt.Key_Enter)


class FiveKeyNavigation(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.adjusting = False
        self.tab_selection_active = False

    def eventFilter(self, watched, event):
        if event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        if key not in ARROWS + ENTER_KEYS:
            return False
        if event.isAutoRepeat() and key in ENTER_KEYS:
            return True

        # Native popup lists need the same arrows/Enter to choose their items.
        if QApplication.activePopupWidget() is not None:
            return False
        focus = self.window.focusWidget()
        if isinstance(focus, QComboBox) and focus.view().isVisible():
            return False
        modal = QApplication.activeModalWidget()
        if modal is not None:
            if key in ARROWS:
                self._move_focus(modal, key)
                return True
            self._activate(focus, modal)
            return True

        nav_buttons = getattr(self.window.nav, '_buttons', [])
        on_nav = focus in nav_buttons
        if self.window._shells.currentIndex() == 0:
            # Driver page: all controls are reachable; Right switches to engineer view.
            if key == Qt.Key_Right:
                self.window.set_mode_from_keyboard_engineering()
                return True
            if key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Down):
                self._move_focus(self.window._driver, key)
                return True
            self._activate(focus, self.window._driver)
            return True

        # When the bottom bar has focus, Left/Right select pages; Enter opens it.
        if on_nav and key in (Qt.Key_Left, Qt.Key_Right):
            self.adjusting = False
            self.window.keyboard_move_tab(-1 if key == Qt.Key_Left else 1)
            self.tab_selection_active = True
            return True
        if key in ARROWS:
            if isinstance(focus, QTableWidget) and key in (Qt.Key_Up, Qt.Key_Down):
                return False  # keep native row selection in the logs table
            if self.adjusting and isinstance(focus, QSlider):
                step = max(1, focus.singleStep())
                focus.setValue(focus.value() + (step if key in (Qt.Key_Up, Qt.Key_Right) else -step))
                return True
            self.tab_selection_active = False
            # Navigate the complete engineering shell, not just the page body.
            # This includes the status/header controls, page-specific top controls,
            # and the bottom navigation bar.
            self._move_focus(self.window._shells.widget(1), key)
            return True

        if self.tab_selection_active or on_nav:
            self.adjusting = False
            self.tab_selection_active = False
            self.window.keyboard_activate_tab()
        elif isinstance(focus, QSlider):
            self.adjusting = not self.adjusting
            focus.setToolTip('Adjustment mode: arrows change value; Enter finishes' if self.adjusting else 'Press Enter to adjust')
        else:
            self.adjusting = False
            self._activate(focus, self.window.stack.currentWidget())
        return True

    def _controls(self, root):
        if root is None:
            return []
        candidates = []
        if isinstance(root, CONTROL_TYPES):
            candidates.append(root)
        candidates.extend(root.findChildren(QWidget))
        controls = []
        for widget in candidates:
            if not isinstance(widget, CONTROL_TYPES):
                continue
            if not widget.isVisible() or not widget.isEnabled() or widget.width() <= 0 or widget.height() <= 0:
                continue
            if isinstance(widget, QLineEdit) and widget.isReadOnly():
                continue
            widget.setFocusPolicy(Qt.StrongFocus)
            controls.append(widget)
        # Remove duplicate object references, then sort in screen reading order.
        controls = list(dict.fromkeys(controls))
        controls.sort(key=lambda w: (w.mapToGlobal(w.rect().center()).y(),
                                     w.mapToGlobal(w.rect().center()).x()))
        return controls

    def _move_focus(self, root, key):
        controls = self._controls(root)
        if not controls:
            return
        current = self.window.focusWidget()
        if current not in controls:
            target = controls[-1] if key in (Qt.Key_Up, Qt.Key_Left) else controls[0]
        else:
            index = controls.index(current)
            step = -1 if key in (Qt.Key_Up, Qt.Key_Left) else 1
            target = controls[(index + step) % len(controls)]
        target.setFocus(Qt.TabFocusReason)

    def _activate(self, focus, root):
        if focus is None:
            # If focus was lost, first arrow/Enter should still enter the page.
            self._move_focus(root, Qt.Key_Down)
            return
        if isinstance(focus, QAbstractButton):
            if focus.isEnabled():
                focus.click()
        elif isinstance(focus, QComboBox):
            focus.showPopup()
        elif isinstance(focus, QSlider):
            self.adjusting = not self.adjusting
        elif isinstance(focus, QTableWidget):
            page = focus
            while page is not None:
                if hasattr(page, '_view_selected'):
                    page._view_selected()
                    return
                page = page.parentWidget()
        elif isinstance(focus, (QListWidget, QTreeWidget, QSpinBox, QDoubleSpinBox, QLineEdit)):
            focus.setFocus()
