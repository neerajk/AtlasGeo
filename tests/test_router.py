from unittest.mock import MagicMock, patch

from atlas.models.router import _load_config, _resolve_model_id, get_llm


def setup_function():
    _load_config.cache_clear()


def test_default_model_is_ollama():
    _load_config.cache_clear()
    assert _resolve_model_id("planner").startswith("ollama/")


def test_unknown_agent_falls_back_to_default():
    _load_config.cache_clear()
    assert _resolve_model_id("does_not_exist") == "ollama/nemotron-3-nano:30b-cloud"


def test_ollama_prefix_instantiates_chat_ollama():
    mock_ollama_module = MagicMock()
    mock_cls = MagicMock()
    mock_ollama_module.ChatOllama = mock_cls
    with patch("atlas.models.router._resolve_model_id", return_value="ollama/nemotron-3-nano:30b-cloud"):
        with patch.dict("sys.modules", {"langchain_ollama": mock_ollama_module}):
            get_llm("planner")
            mock_cls.assert_called_once()
            assert mock_cls.call_args.kwargs["model"] == "nemotron-3-nano:30b-cloud"


def test_anthropic_prefix_instantiates_chat_anthropic():
    with patch("atlas.models.router._resolve_model_id", return_value="anthropic/claude-sonnet-4-6"):
        with patch("langchain_anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_llm("planner")
            mock_cls.assert_called_once()
            assert mock_cls.call_args.kwargs["model"] == "claude-sonnet-4-6"


def test_openrouter_prefix_uses_openai_with_correct_base_url():
    with patch("atlas.models.router._resolve_model_id", return_value="openrouter/meta-llama/llama-3.3-70b-instruct:free"):
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_llm("planner")
            mock_cls.assert_called_once()
            kwargs = mock_cls.call_args.kwargs
            assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
            assert kwargs["model"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_groq_prefix_instantiates_chat_groq():
    mock_groq_module = MagicMock()
    mock_cls = MagicMock()
    mock_groq_module.ChatGroq = mock_cls
    with patch("atlas.models.router._resolve_model_id", return_value="groq/llama3-70b-8192"):
        with patch.dict("sys.modules", {"langchain_groq": mock_groq_module}):
            get_llm("planner")
            mock_cls.assert_called_once()
            assert mock_cls.call_args.kwargs["model"] == "llama3-70b-8192"
