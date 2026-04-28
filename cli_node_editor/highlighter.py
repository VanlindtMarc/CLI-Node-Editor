"""Syntax highlighting helpers for CLI Node Editor."""

from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter

class BatchSyntaxHighlighter(QSyntaxHighlighter):
    """Coloration syntaxique légère pour la prévisualisation Batch."""

    def __init__(self, document):
        super().__init__(document)
        self.comment_format = self._make_format("#6A9955")
        self.label_format = self._make_format("#C586C0", bold=True)
        self.keyword_format = self._make_format("#569CD6", bold=True)
        self.variable_format = self._make_format("#4EC9B0")
        self.string_format = self._make_format("#CE9178")
        self.command_format = self._make_format("#DCDCAA")
        self.error_format = self._make_format("#F44747", bold=True)

        self.keywords = {
            "if", "else", "for", "set", "setlocal", "endlocal", "goto", "call",
            "shift", "exit", "pause", "copy", "del", "mkdir", "echo", "timeout",
            "not", "exist", "neq", "gtr"
        }
        self.commands = {"ffmpeg", "sox", "magick", "curl", "pandoc", "robocopy", "powershell"}

    def _make_format(self, color, bold=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def highlightBlock(self, text):
        stripped = text.lstrip()
        if not stripped:
            return

        if stripped.upper().startswith("REM"):
            self.setFormat(0, len(text), self.comment_format)
            return

        if stripped.startswith("::") or stripped.startswith(":"):
            self.setFormat(0, len(text), self.label_format)
            return

        for start_token, end_token in [('"', '"')]:
            start = text.find(start_token)
            while start != -1:
                end = text.find(end_token, start + 1)
                if end == -1:
                    end = len(text) - 1
                self.setFormat(start, end - start + 1, self.string_format)
                start = text.find(start_token, end + 1)

        idx = 0
        while idx < len(text):
            if text[idx] == "%":
                end = text.find("%", idx + 1)
                if end != -1:
                    self.setFormat(idx, end - idx + 1, self.variable_format)
                    idx = end + 1
                    continue
            if text[idx] == "!":
                end = text.find("!", idx + 1)
                if end != -1:
                    self.setFormat(idx, end - idx + 1, self.variable_format)
                    idx = end + 1
                    continue
            idx += 1

        words = text.replace("(", " ").replace(")", " ").replace("=", " ").split()
        cursor = 0
        for word in words:
            start = text.find(word, cursor)
            if start == -1:
                continue
            lower_word = word.lower()
            if lower_word in self.keywords:
                self.setFormat(start, len(word), self.keyword_format)
            elif lower_word in self.commands or word.startswith('"') and lower_word.strip('"') in self.commands:
                self.setFormat(start, len(word), self.command_format)
            elif "erreur" in lower_word:
                self.setFormat(start, len(word), self.error_format)
            cursor = start + len(word)


