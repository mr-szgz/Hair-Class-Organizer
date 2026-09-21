"""Application entry point."""

from app.arguments import build_parser
from app.config import AppSettings, configure_runtime


def main() -> None:
    arguments = vars(build_parser().parse_args())
    configure_runtime()
    settings = AppSettings.load()
    if "input_path" in arguments and arguments["input_path"] is not None:
        settings.source = arguments["input_path"]
    if "confidence" in arguments:
        settings.confidence = arguments["confidence"]
    if "device" in arguments:
        settings.device = arguments["device"]
    if "videos" in arguments:
        settings.include_videos = arguments["videos"]
    if "frame_percentage" in arguments:
        settings.frame_percentage = arguments["frame_percentage"]

    from app.main import run

    run(settings)


if __name__ == "__main__":
    main()
