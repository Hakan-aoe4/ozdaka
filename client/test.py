import sys
from PyQt6.QtWidgets import QApplication, QLabel
app = QApplication(sys.argv)
l = QLabel("OzdAka OK")
l.show()
sys.exit(app.exec())