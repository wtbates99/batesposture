from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel
import json

from settings import CUSTOMIZABLE_SETTINGS, save_user_settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customizable Settings")
        self.layout = QFormLayout()

        # Create QLineEdit widgets for each customizable setting.
        self.fields = {}

        for key, value in CUSTOMIZABLE_SETTINGS.items():
            # For dictionary values, we convert to a JSON string representation.
            if isinstance(value, dict):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            widget = QLineEdit(value_str)
            self.fields[key] = widget
            self.layout.addRow(QLabel(key), widget)

        # Set up OK/Cancel buttons.
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)

        self.setLayout(self.layout)

    def accept(self):
        # Update the customizable settings from the input fields.
        for key, widget in self.fields.items():
            text = widget.text()
            old_value = CUSTOMIZABLE_SETTINGS[key]
            try:
                if isinstance(old_value, int):
                    CUSTOMIZABLE_SETTINGS[key] = int(text)
                elif isinstance(old_value, float):
                    CUSTOMIZABLE_SETTINGS[key] = float(text)
                elif isinstance(old_value, dict):
                    # Parse the JSON dictionary string.
                    CUSTOMIZABLE_SETTINGS[key] = json.loads(text)
                else:
                    CUSTOMIZABLE_SETTINGS[key] = text
            except Exception as e:
                print(f"Error parsing value for {key}: {e}")
                CUSTOMIZABLE_SETTINGS[key] = text
        save_user_settings()  # Save these settings persistently.
        super().accept()
