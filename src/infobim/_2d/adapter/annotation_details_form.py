from typing import ClassVar, Dict, Optional

from ezdxf.addons.xqt import QtWidgets as qw


class AnnotationDetailsForm(qw.QDialog):
    """
    The form that asks for the details of an annotation: title, text, author.

    The title is required: the form cannot be accepted without one. The text
    and the author are optional, and an empty one is left out of the answer.
    """

    TITLE_KEY: ClassVar[str] = "title"
    TEXT_KEY: ClassVar[str] = "text"
    AUTHOR_KEY: ClassVar[str] = "author"
    WINDOW_TITLE: ClassVar[str] = "New annotation"

    def __init__(self, parent: Optional[qw.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(480, 360)

        self._title: qw.QLineEdit = qw.QLineEdit()
        self._text: qw.QPlainTextEdit = qw.QPlainTextEdit()
        self._author: qw.QLineEdit = qw.QLineEdit()

        form: qw.QFormLayout = qw.QFormLayout()
        form.addRow("Title *", self._title)
        form.addRow("Text", self._text)
        form.addRow("Author", self._author)

        self._buttons: qw.QDialogButtonBox = qw.QDialogButtonBox(
            qw.QDialogButtonBox.StandardButton.Ok
            | qw.QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout: qw.QVBoxLayout = qw.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._buttons)

        self._title.textChanged.connect(self._update_accept)
        self._update_accept()
        self._title.setFocus()

    def set_values(self, title: str = "", text: str = "", author: str = "") -> None:
        self._title.setText(title)
        self._text.setPlainText(text)
        self._author.setText(author)

    def details(self) -> Dict[str, str]:
        """
        What was filled in, by key; the text and the author only when not empty.
        """
        details: Dict[str, str] = {self.TITLE_KEY: self._title.text().strip()}
        text: str = self._text.toPlainText().strip()
        if text:
            details[self.TEXT_KEY] = text
        author: str = self._author.text().strip()
        if author:
            details[self.AUTHOR_KEY] = author

        return details

    def _update_accept(self) -> None:
        self._buttons.button(qw.QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self._title.text().strip())
        )
