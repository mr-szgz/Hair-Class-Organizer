from app.arguments import build_parser


def test_direct_path_and_launch_overrides():
    arguments = build_parser().parse_args(
        ["C:/media/portrait.jpg", "--confidence", "0.7", "--device", "cpu", "--no-videos", "--frame-percentage", "25"]
    )
    assert arguments.input_path == "C:/media/portrait.jpg"
    assert arguments.confidence == 0.7
    assert arguments.device == "cpu"
    assert arguments.videos is False
    assert arguments.frame_percentage == 25
