from __future__ import annotations

import argparse
import asyncio
import json

from services.psd import PSDCrawler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incrementally discover and optionally download PBS PSD documents.")
    parser.add_argument("--output-dir", default="data/psd", help="Directory for the manifest and downloaded files.")
    parser.add_argument(
        "--download-documents",
        action="store_true",
        help="Download discovered PDF/Word files. By default the task only discovers URLs and metadata.",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=None,
        help="Limit the number of documents downloaded in one run.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.5,
        help="Minimum delay between HTTP requests.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Maximum concurrent HTML page fetches.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    crawler = PSDCrawler(
        output_dir=args.output_dir,
        delay_seconds=args.delay_seconds,
        max_concurrency=args.max_concurrency,
    )
    try:
        return await crawler.crawl(
            download_documents=args.download_documents,
            max_documents=args.max_documents,
        )
    finally:
        await crawler.aclose()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
