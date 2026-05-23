"""Allow `python -m orchestrator` to invoke the CLI."""
from .main import main
import sys

sys.exit(main())
