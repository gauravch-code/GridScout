import argparse
import json
import logging

from .settings import ROOT


def main():
    parser = argparse.ArgumentParser(prog="gridscout")
    commands = parser.add_subparsers(dest="command", required=True)
    pipeline = commands.add_parser("pipeline", help="Clean public/local source data")
    pipeline.add_argument("--download", action="store_true")
    pipeline.add_argument("--raw-dir", default=str(ROOT / "data/raw"))
    pipeline.add_argument("--output-dir", default=str(ROOT / "data/processed"))
    features = commands.add_parser("features", help="Create 5 km candidates and spatial features")
    features.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    features.add_argument("--cell-size", type=float, default=5000)
    commands.add_parser("demo", help="Generate reproducible synthetic demo")
    commands.add_parser("verify-sources", help="Check live public download endpoints")
    memo = commands.add_parser("memos", help="Write memos for top prospects")
    memo.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    memo.add_argument("--top", type=int, default=3)
    memo.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "pipeline":
        from .pipeline import run_pipeline
        run_pipeline(args.raw_dir, args.output_dir, args.download)
    elif args.command == "features":
        from .features import build_features
        build_features(args.data_dir, args.cell_size)
    elif args.command == "demo":
        from .demo import build_demo
        build_demo(ROOT / "data/demo")
    elif args.command == "verify-sources":
        from .sources import verify_sources
        print(json.dumps(verify_sources(), indent=2))
    elif args.command == "memos":
        from .memos import generate_top_memos
        generate_top_memos(args.data_dir, args.top, args.llm)


if __name__ == "__main__":
    main()
