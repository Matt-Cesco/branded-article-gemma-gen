"""Command-line entry point for external topic discovery research."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.topic_discovery_crawler import main


if __name__ == "__main__":
    main()
