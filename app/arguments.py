"""Command-line launch arguments for direct and File Explorer launches."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hair-class-organizer",
        description="Classify hair color and organize the original images and videos.",
        argument_default=argparse.SUPPRESS,
    )
    parser.add_argument("input_path", nargs="?", help="Image, video, or media folder to open")
    parser.add_argument("--confidence", type=float, help="Minimum confidence used when planning moves")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda:0"), help="Inference device")
    parser.add_argument("--videos", action=argparse.BooleanOptionalAction, help="Include supported videos")
    parser.add_argument("--frame-percentage", type=int, help="Video frame position from 0 through 100")
    return parser
