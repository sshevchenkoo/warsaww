"""Ingestion entrypoint. In k8s each source is its own CronJob:
python -m app.ingestion.runner --source=places
"""

import argparse
import logging

from app.ingestion import pipeline
from app.ingestion.adapters import ADAPTERS


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs every request line (incl. the full URL) at INFO — defense in
    # depth against leaking secrets that ride in a URL (see facebook_events).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Parse a source into the DB")
    parser.add_argument("--source", required=True, choices=sorted(ADAPTERS))
    args = parser.parse_args()
    pipeline.run(args.source)


if __name__ == "__main__":
    main()
