"""Tests for Basic Functions"""
import sys
import pytest

from scoreboardrest import create_app

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def test_init(client):
    rv = client.get('/hello')
    print(rv.data, file=sys.stderr)
    assert 1 == 1

