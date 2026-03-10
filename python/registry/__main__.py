"""Allow running as `python -m registry`."""
import sys
from registry.cli import main

sys.exit(main())
