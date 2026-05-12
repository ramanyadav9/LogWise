"""Format-aware parser layer.

Concrete parsers transform `AsyncIterator[str]` (from logwise.sources) into
`AsyncIterator[LogEntry]`. AutoDetector wraps the priority chain and is what
the CLI uses by default.
"""

from logwise.parsers.auto_detect import AutoDetector
from logwise.parsers.base import Parser
from logwise.parsers.json_parser import JSONParser
from logwise.parsers.nginx import NginxParser
from logwise.parsers.plain import PlainParser

__all__ = ["AutoDetector", "JSONParser", "NginxParser", "Parser", "PlainParser"]
