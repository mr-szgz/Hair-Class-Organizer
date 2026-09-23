# Hair Class Organizer

Hair Class Organizer is a Windows desktop application for classifying hair color in images and videos with
[`electblake/hair_color_classifier`](https://huggingface.co/electblake/hair_color_classifier). It uses the Hugging Face
`transformers` image-classification pipeline and moves reviewed originals into folders named after the model classes.

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
