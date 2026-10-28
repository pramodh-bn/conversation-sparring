from pathlib import Path

from fastapi.testclient import TestClient

from app import server
from app.character import ScriptedCharacter, MetaSparkClient


def test_dotenv_runs_once_at_startup_from_working_directory(
    mock_startup_dotenv, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    mock_startup_dotenv.assert_not_called()
    with TestClient(server.app) as client:
        client.post('/sessions')
        client.post('/sessions')
        mock_startup_dotenv.assert_called_once_with(
            dotenv_path=Path.cwd() / '.env', override=False
        )


def test_missing_dotenv_keeps_startup_scripted(mock_startup_dotenv, monkeypatch):
    monkeypatch.delenv('META_MODEL_API_KEY', raising=False)
    monkeypatch.delenv('META_MODEL_API_BASE', raising=False)
    with TestClient(server.app):
        assert isinstance(server.get_character(), ScriptedCharacter)
    mock_startup_dotenv.assert_called_once()


def test_startup_selects_live_config_after_loader(mock_startup_dotenv, monkeypatch):
    def configured(**kwargs):
        # Simulate presence, not a real credential or file read.
        monkeypatch.setenv('META_MODEL_API_KEY', 'placeholder')
        monkeypatch.setenv('META_MODEL_API_BASE', 'https://model.invalid/v1')
        return True

    mock_startup_dotenv.side_effect = configured
    with TestClient(server.app):
        assert isinstance(server.get_character(), MetaSparkClient)
    mock_startup_dotenv.assert_called_once()
