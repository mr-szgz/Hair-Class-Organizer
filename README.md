# Hair Class Organizer

Hair Class Organizer is a Windows desktop application for classifying hair color in images and videos with
[`electblake/hair_color_classifier`](https://huggingface.co/electblake/hair_color_classifier). It uses the Hugging Face
`transformers` image-classification pipeline and moves reviewed originals into folders named after the model classes.

The published ConvNeXt model recognizes `black`, `blonde`, `blue`, `brown`, `pink`, `red`, and `silver` hair. It was
trained on face-aligned images, so face-centered inputs that show the hair clearly produce the most representative results.

## Features

- Scans a folder or one selected image/video.
- Downloads and caches the model through the Hugging Face pipeline on first use.
- Uses the first available accelerator automatically, or an explicitly selected CPU/CUDA device.
- Extracts one configurable video frame using Spectra's FFmpeg-backed OpenCV method.
- Shows every prediction and confidence before changing files.
- Filters moves by confidence and class selection.
- Copies, flushes, preserves metadata, and then removes the original without overwriting existing files.
- Records every completed move in a CSV journal under the user application-data directory.
- Saves settings between launches.
- Accepts an input path on the command line and provides optional File Explorer context-menu integration in Setup.

## Development

Python 3.12 and [uv](https://docs.astral.sh/uv/) are used for the local environment.

```powershell
uv sync
uv run python -m app
```

Open a folder or file immediately:

```powershell
uv run python -m app "D:\Media\Portraits"
uv run python -m app "D:\Media\Portraits\photo.jpg"
```

Run checks:

```powershell
uv run ruff check .
uv run pytest
```

## How video classification works

For each supported video, the app opens it with OpenCV's FFmpeg backend, seeks to the configured percentage of the
reported frame count, saves that frame as a lossless PNG in `.hair_class_organizer_video_grabs`, and classifies the PNG.
The temporary frame is removed after a successful scan. If you approve the move, the original video—not the temporary
PNG—is moved into its predicted class folder.

Supported images: BMP, GIF, JPEG, PNG, TIFF, and WebP. Supported videos: AVI, GIF, M4V, MKV, MOV, MP4, MPEG, MPG, and WebM.

## Build Setup.exe

Install Inno Setup 6, then run:

```powershell
pwsh -File packaging\build-setup.ps1
```

The build script verifies the lock file, downloads the pinned `uv` bootstrap executable with a fixed SHA-256 checksum,
and creates `dist\Hair-Class-Organizer-<version>-windows-amd64-Setup.exe`.

Setup installs the application source and bootstrap tool, then provisions a private Python 3.12 runtime and virtual
environment below the installation directory from `uv.lock`. An internet connection is required during installation.
The optional “Add to File Explorer context menu” task adds commands for both folders and individual files.

## Data locations

Model downloads, settings, and move journals are stored in the per-user Hair Class Organizer application-data
directory. They are not written into the source-media folder, apart from class output folders and the temporary video
frame directory used during a scan.
