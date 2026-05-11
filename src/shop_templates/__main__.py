"""Allow `python3 -m shop_templates ...` to invoke the CLI."""
import sys

from shop_templates.cli import main

if __name__ == "__main__":
    sys.exit(main())
