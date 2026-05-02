"""
Pytest tests for book_service.

Run from the book_service directory:
    pytest test_book_service.py -v

DB and httpx are mocked. Service Bus is stubbed at import time
and left for integration tests.
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Make sure the book_service directory is on sys.path ─────────────────────
# Works on any OS regardless of where pytest is invoked from.
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Stub heavy imports before app loads ─────────────────────────────────────

sys.modules.setdefault("pyodbc", MagicMock())

for _mod in ["azure", "azure.servicebus", "azure.servicebus.aio", "azure.servicebus._base_handler"]:
    sys.modules.setdefault(_mod, MagicMock())

# ── Minimal env vars ─────────────────────────────────────────────────────────

os.environ.setdefault("DB_SERVER",   "test-server")
os.environ.setdefault("DB_DATABASE", "test-db")
os.environ.setdefault("DB_USERNAME", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-pass")
os.environ.setdefault("USER_SERVICE",    "http://user-service")
os.environ.setdefault("MEETING_SERVICE", "http://meeting-service")
os.environ.setdefault("BOOK_SERVICE",    "http://book-service")

import schemas  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_cursor(rows=None, one_row=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows if rows is not None else []
    cursor.fetchone.return_value = one_row
    return cursor


@contextmanager
def mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    yield conn


@pytest.fixture()
def client():
    with patch("book_service.get_connection") as patched_conn, \
         patch("book_service.get_api_urls", return_value={
             "user":    "http://user-service",
             "meeting": "http://meeting-service",
             "book":    "http://book-service",
         }):
        import book_service as bs
        bs._mock_conn = patched_conn
        from fastapi.testclient import TestClient
        yield TestClient(bs.app)


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestSchemas:
    def test_book_out_valid(self):
        b = schemas.BookOut(id=1, name="Dune", genre="Sci-Fi", author="Frank Herbert")
        assert b.id == 1
        assert b.name == "Dune"
        assert b.genre == "Sci-Fi"
        assert b.author == "Frank Herbert"

    def test_book_out_genre_optional(self):
        b = schemas.BookOut(id=2, name="Unknown", genre=None, author="Someone")
        assert b.genre is None

    def test_book_comment_in_valid(self):
        c = schemas.BookCommentIn(user_id=5, text="Great read!")
        assert c.user_id == 5
        assert c.text == "Great read!"

    def test_comment_out_valid(self):
        c = schemas.CommentOut(id=10, user_id=3, text="Nice")
        assert c.id == 10

    def test_user_out_valid(self):
        u = schemas.UserOut(id=1, username="alice", email="alice@example.com")
        assert u.username == "alice"

    def test_user_register_rejects_invalid_email(self):
        with pytest.raises(Exception):
            schemas.UserRegister(username="bob", email="not-an-email", password="pw")


# ── Utility tests ─────────────────────────────────────────────────────────────

class TestUtility:
    def test_get_api_urls_returns_all_keys(self):
        from utility import get_api_urls
        urls = get_api_urls()
        assert "user" in urls
        assert "meeting" in urls
        assert "book" in urls

    def test_get_api_urls_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("USER_SERVICE", "http://my-users")
        from utility import get_api_urls
        assert get_api_urls()["user"] == "http://my-users"


# ── GET /book/{title} ─────────────────────────────────────────────────────────

class TestGetBook:
    def test_returns_book_when_found(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(
            make_cursor(rows=[(1, "Dune", "Sci-Fi", "Herbert")])
        )
        resp = client.get("/book/Dune")
        assert resp.status_code == 200
        assert resp.json() == {"id": 1, "name": "Dune", "genre": "Sci-Fi", "author": "Herbert"}

    def test_returns_404_when_not_found(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(make_cursor(rows=[]))
        resp = client.get("/book/NonExistent")
        assert resp.status_code == 404
        assert "No books found" in resp.json()["detail"]

    def test_partial_title_match(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(
            make_cursor(rows=[(5, "Harry Potter", "Fantasy", "Rowling")])
        )
        resp = client.get("/book/Potter")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Harry Potter"

    def test_returns_first_row_when_multiple_match(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(
            make_cursor(rows=[(1, "Book A", "G1", "A1"), (2, "Book B", "G2", "A2")])
        )
        assert client.get("/book/Book").json()["id"] == 1


# ── GET /book/id/{id} ─────────────────────────────────────────────────────────

class TestGetBookById:
    def test_returns_book_when_found(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(
            make_cursor(one_row=(7, "Foundation", "Sci-Fi", "Asimov"))
        )
        resp = client.get("/book/id/7")
        assert resp.status_code == 200
        assert resp.json()["author"] == "Asimov"

    def test_returns_404_when_not_found(self, client):
        import book_service as bs
        bs._mock_conn.return_value = mock_connection(make_cursor(one_row=None))
        resp = client.get("/book/id/999")
        assert resp.status_code == 404
        assert "Book not found" in resp.json()["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/book/id/not-a-number").status_code == 422



# ── _call helper ──────────────────────────────────────────────────────────────

class TestCallHelper:
    def test_wraps_request_error_as_502(self):
        import book_service as bs
        import httpx
        from fastapi import HTTPException

        with patch("httpx.request", side_effect=httpx.RequestError("timeout")):
            with pytest.raises(HTTPException) as exc:
                bs._call("GET", "http://fake-url")

        assert exc.value.status_code == 502
        assert "Downstream service unreachable" in exc.value.detail

    def test_returns_response_on_success(self):
        import book_service as bs

        with patch("httpx.request", return_value=MagicMock(status_code=200)):
            assert bs._call("GET", "http://fake-url").status_code == 200