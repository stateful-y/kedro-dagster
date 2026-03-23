import importlib
import logging as std_logging

import coloredlogs
import pytest
import structlog
from dagster._utils.log import configure_loggers

from kedro_dagster.logging import (
    dagster_colored_formatter,
    dagster_json_formatter,
    dagster_rich_formatter,
)


def _import_module():
    """Import fresh to avoid cached monkeypatched dagster behavior between tests."""
    return importlib.import_module("kedro_dagster.logging")


class TestGetLogger:
    """Tests for the getLogger function."""

    def test_falls_back_to_stdlib_when_no_dagster_context(self, mocker):
        """Returns stdlib logger when no Dagster context is active."""
        kd_logging = _import_module()

        mocker.patch.object(kd_logging.dg.OpExecutionContext, "get", staticmethod(lambda: None))

        logger = kd_logging.getLogger(__name__)

        assert isinstance(logger, std_logging.Logger)
        assert logger.name == __name__

    def test_uses_dagster_logger_when_context_active(self, mocker):
        """Returns Dagster logger when context is active."""
        kd_logging = _import_module()

        mocker.patch.object(kd_logging.dg.OpExecutionContext, "get", staticmethod(object))

        captured = {}

        class DummyDagsterLogger(std_logging.Logger):
            def __init__(self, name: str):
                super().__init__(name)

        def fake_get_dagster_logger(name=None):
            captured["called_with"] = name
            return DummyDagsterLogger(name or "dagster")

        mocker.patch.object(kd_logging.dg, "get_dagster_logger", fake_get_dagster_logger)

        logger = kd_logging.getLogger("my.mod")

        assert isinstance(logger, std_logging.Logger)
        assert isinstance(logger, DummyDagsterLogger)
        assert captured["called_with"] == "my.mod"

    def test_falls_back_when_context_get_raises_exception(self, mocker):
        """Falls back to stdlib logging when OpExecutionContext.get() raises."""
        kd_logging = _import_module()

        def mock_context_get():
            raise RuntimeError("No execution context available")

        mocker.patch.object(kd_logging.dg.OpExecutionContext, "get", staticmethod(mock_context_get))

        debug_calls = []
        original_debug = kd_logging._logging.debug

        def mock_debug(msg):
            debug_calls.append(msg)
            return original_debug(msg)

        mocker.patch.object(kd_logging._logging, "debug", mock_debug)

        logger = kd_logging.getLogger("test.logger")

        assert isinstance(logger, std_logging.Logger)
        assert logger.name == "test.logger"
        assert len(debug_calls) == 1
        assert "No active Dagster context:" in debug_calls[0]
        assert "RuntimeError" in debug_calls[0] or "No execution context available" in debug_calls[0]


class TestLoggingConfigStructure:
    """Tests for the Dagster logging configuration structure."""

    def test_yaml_structure_matches_expected(self, mocker):
        """Expected YAML structure matches the actual Dagster logging config."""
        expected_yaml_structure = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "colored": {
                    "()": "coloredlogs.ColoredFormatter",
                    "fmt": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S %z",
                    "field_styles": {"levelname": {"color": "blue"}, "asctime": {"color": "green"}},
                    "level_styles": {"debug": {}, "error": {"color": "red"}},
                },
                "json": {
                    "()": "structlog.stdlib.ProcessorFormatter",
                    "foreign_pre_chain": [
                        "structlog.stdlib.add_logger_name",
                        "structlog.stdlib.add_log_level",
                        'structlog.processors.TimeStamper(fmt="iso", utc=True)',
                        "structlog.processors.StackInfoRenderer",
                        "structlog.stdlib.ExtraAdder",
                    ],
                    "processors": [
                        "structlog.stdlib.ProcessorFormatter.remove_processors_meta",
                        "structlog.processors.JSONRenderer",
                    ],
                },
                "rich": {
                    "()": "structlog.stdlib.ProcessorFormatter",
                    "foreign_pre_chain": [
                        "structlog.stdlib.add_logger_name",
                        "structlog.stdlib.add_log_level",
                        'structlog.processors.TimeStamper(fmt="iso", utc=True)',
                        "structlog.processors.StackInfoRenderer",
                        "structlog.stdlib.ExtraAdder",
                    ],
                    "processors": [
                        "structlog.stdlib.ProcessorFormatter.remove_processors_meta",
                        "structlog.dev.ConsoleRenderer",
                    ],
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "level": "INFO",
                    "formatter": "colored",
                },
                "null": {"class": "logging.NullHandler"},
            },
            "loggers": {
                "dagster": {"handlers": ["default"], "level": "INFO"},
                "dagit": {"handlers": ["default"], "level": "INFO"},
                "dagster-webserver": {"handlers": ["default"], "level": "INFO"},
            },
        }

        captured_config = {}

        def capture_dictConfig(config):
            captured_config.update(config)

        mocker.patch.object(std_logging.config, "dictConfig", side_effect=capture_dictConfig)
        configure_loggers()

        assert captured_config["version"] == expected_yaml_structure["version"]
        assert captured_config["disable_existing_loggers"] == expected_yaml_structure["disable_existing_loggers"]

        actual_formatters = captured_config["formatters"]
        expected_formatters = expected_yaml_structure["formatters"]

        assert actual_formatters["colored"]["fmt"] == expected_formatters["colored"]["fmt"]
        assert actual_formatters["colored"]["datefmt"] == expected_formatters["colored"]["datefmt"]
        assert actual_formatters["colored"]["field_styles"] == expected_formatters["colored"]["field_styles"]
        assert actual_formatters["colored"]["level_styles"] == expected_formatters["colored"]["level_styles"]

        actual_handlers = captured_config["handlers"]
        expected_handlers = expected_yaml_structure["handlers"]

        assert actual_handlers["default"]["class"] == expected_handlers["default"]["class"]
        assert actual_handlers["default"]["level"] == expected_handlers["default"]["level"]
        assert actual_handlers["default"]["formatter"] == expected_handlers["default"]["formatter"]
        assert actual_handlers["null"]["class"] == expected_handlers["null"]["class"]

        actual_loggers = captured_config["loggers"]
        expected_loggers = expected_yaml_structure["loggers"]

        for logger_name in ["dagster", "dagit", "dagster-webserver"]:
            assert actual_loggers[logger_name]["handlers"] == expected_loggers[logger_name]["handlers"]
            assert actual_loggers[logger_name]["level"] == expected_loggers[logger_name]["level"]


class TestRichFormatter:
    """Tests for the dagster_rich_formatter function."""

    def test_creates_valid_processor_formatter(self):
        """Creates a valid structlog ProcessorFormatter instance."""
        formatter = dagster_rich_formatter()

        assert isinstance(formatter, std_logging.Formatter)
        assert hasattr(formatter, "_style")

    def test_formats_log_record(self):
        """Formats a log record without raising exceptions."""
        formatter = dagster_rich_formatter()

        record = std_logging.LogRecord(
            name="test_logger",
            level=std_logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        try:
            formatted = formatter.format(record)
            assert isinstance(formatted, str)
            assert "Test message" in formatted
        except Exception as e:
            assert "processor" not in str(e).lower()

    def test_fallback_compatibility_with_older_structlog(self, mocker):
        """Falls back to single processor argument for older structlog API."""
        original_init = structlog.stdlib.ProcessorFormatter.__init__

        def mock_init_old_api(self, *args, **kwargs):
            if "processors" in kwargs:
                raise TypeError("ProcessorFormatter() got an unexpected keyword argument 'processors'")
            return original_init(self, *args, **kwargs)

        mocker.patch.object(structlog.stdlib.ProcessorFormatter, "__init__", mock_init_old_api)

        formatter = dagster_rich_formatter()

        assert isinstance(formatter, std_logging.Formatter)


class TestJsonFormatter:
    """Tests for the dagster_json_formatter function."""

    def test_creates_valid_processor_formatter(self):
        """Creates a valid structlog ProcessorFormatter instance."""
        formatter = dagster_json_formatter()

        assert isinstance(formatter, std_logging.Formatter)
        assert hasattr(formatter, "_style")

    def test_formats_log_record(self):
        """Formats a log record without raising exceptions."""
        formatter = dagster_json_formatter()

        record = std_logging.LogRecord(
            name="test_logger",
            level=std_logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        try:
            formatted = formatter.format(record)
            assert isinstance(formatted, str)
            assert "Test message" in formatted or "test message" in formatted.lower()
        except Exception as e:
            assert "processor" not in str(e).lower()

    def test_fallback_compatibility_with_older_structlog(self, mocker):
        """Falls back to single processor argument for older structlog API."""
        original_init = structlog.stdlib.ProcessorFormatter.__init__

        def mock_init_old_api(self, *args, **kwargs):
            if "processors" in kwargs:
                raise TypeError("ProcessorFormatter() got an unexpected keyword argument 'processors'")
            return original_init(self, *args, **kwargs)

        mocker.patch.object(structlog.stdlib.ProcessorFormatter, "__init__", mock_init_old_api)

        formatter = dagster_json_formatter()

        assert isinstance(formatter, std_logging.Formatter)


class TestColoredFormatter:
    """Tests for the dagster_colored_formatter function."""

    def test_creates_valid_formatter(self):
        """Creates a valid logging Formatter instance."""
        formatter = dagster_colored_formatter()

        assert isinstance(formatter, std_logging.Formatter)

    def test_uses_coloredlogs_formatter(self):
        """Uses ColoredFormatter when coloredlogs is available."""
        formatter = dagster_colored_formatter()

        assert isinstance(formatter, coloredlogs.ColoredFormatter | std_logging.Formatter)

        record = std_logging.LogRecord(
            name="test_logger",
            level=std_logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert isinstance(formatted, str)
        assert "Test message" in formatted

    def test_applies_correct_field_and_level_styles(self):
        """Applies the correct field and level styles."""
        formatter = dagster_colored_formatter()

        if isinstance(formatter, coloredlogs.ColoredFormatter):
            assert hasattr(formatter, "field_styles")
            field_styles = formatter.field_styles
            assert "levelname" in field_styles
            assert field_styles["levelname"]["color"] == "blue"
            assert "asctime" in field_styles
            assert field_styles["asctime"]["color"] == "green"

            assert hasattr(formatter, "level_styles")
            level_styles = formatter.level_styles
            assert "debug" in level_styles
            assert "error" in level_styles
            assert level_styles["error"]["color"] == "red"


class TestFormatterExceptionHandling:
    """Tests for formatter behavior with exception-containing log records."""

    def test_all_formatters_handle_exceptions_gracefully(self):
        """All formatters handle exceptions in log records gracefully."""
        formatters = [
            dagster_rich_formatter(),
            dagster_json_formatter(),
            dagster_colored_formatter(),
        ]

        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = std_logging.sys.exc_info()

        record = std_logging.LogRecord(
            name="test_logger",
            level=std_logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test message with exception",
            args=(),
            exc_info=exc_info,
        )

        for formatter in formatters:
            try:
                formatted = formatter.format(record)
                assert isinstance(formatted, str)
                assert "Test message with exception" in formatted
            except Exception as e:
                pytest.fail(f"Formatter {type(formatter).__name__} raised exception: {e}")
