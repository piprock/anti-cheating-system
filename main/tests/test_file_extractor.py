import io
import sys
import pytest
from types import SimpleNamespace

from main.services import FileExtractor

@pytest.fixture
def extractor():
    return FileExtractor()

class DummyUploaded:
    def __init__(self, data: bytes, name: str):
        self._bio = io.BytesIO(data)
        self.name = name
    def read(self):
        return self._bio.read()
    def seek(self, pos):
        self._bio.seek(pos)

@pytest.fixture(autouse=True)
def mock_pdf(monkeypatch):
    class DummyPage:
        def __init__(self, text):
            self._text = text
        def extract_text(self):
            return self._text
    class DummyReader:
        def __init__(self, *a, **k):
            self.pages = [DummyPage('Page1'), DummyPage('Page2')]
    monkeypatch.setitem(sys.modules, 'PyPDF2', SimpleNamespace(PdfReader=DummyReader))

@pytest.fixture(autouse=True)
def mock_docx(monkeypatch):
    class DummyPara:
        def __init__(self, t):
            self.text = t
    class DummyDoc:
        def __init__(self, *a, **k):
            self.paragraphs = [DummyPara('Para1'), DummyPara('Para2')]
    monkeypatch.setitem(sys.modules, 'docx', SimpleNamespace(Document=DummyDoc))

@pytest.fixture(autouse=True)
def mock_rtf(monkeypatch):
    class DummyStrip:
        @staticmethod
        def rtf_to_text(content):
            return 'RTF_TEXT'
    monkeypatch.setitem(sys.modules, 'striprtf.striprtf', SimpleNamespace(rtf_to_text=DummyStrip.rtf_to_text))

@pytest.mark.parametrize('ext,expected_contains', [
    ('txt', 'hello'),
    ('csv', '1,2,3'),
])
def test_extract_text_and_csv(extractor, ext, expected_contains):
    data = expected_contains.encode('utf-8')
    up = DummyUploaded(data, f'name.{ext}')
    out = extractor.extract(up, up.name)
    assert expected_contains in out

@pytest.mark.django_db
def test_extract_pdf(extractor):
    up = DummyUploaded(b'PDFDATA', 'file.pdf')
    out = extractor.extract(up, up.name)
    assert 'Page1' in out and 'Page2' in out

@pytest.mark.django_db
def test_extract_docx(extractor):
    up = DummyUploaded(b'DOCXDATA', 'file.docx')
    out = extractor.extract(up, up.name)
    assert 'Para1' in out and 'Para2' in out

@pytest.mark.django_db
def test_extract_rtf(extractor):
    up = DummyUploaded(b'{\\rtf}', 'file.rtf')
    out = extractor.extract(up, up.name)
    assert out == 'RTF_TEXT'

@pytest.mark.django_db
def test_unsupported_extension(extractor):
    up = DummyUploaded(b'data', 'file.bin')
    with pytest.raises(ValueError):
        extractor.extract(up, up.name)
