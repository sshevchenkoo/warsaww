"""Ingestion entrypoint. In k8s each source is its own CronJob:
python -m app.ingestion.runner --source=places
"""

import argparse

from app.ingestion import pipeline
from app.ingestion.adapters import ADAPTERS


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a source into the DB")
    parser.add_argument("--source", required=True, choices=sorted(ADAPTERS))
    args = parser.parse_args()
    pipeline.run(args.source)


if __name__ == "__main__":
    main()
