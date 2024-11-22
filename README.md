# OMTriage

A powerful tool for organizing photos and videos from camera SD cards with a focus on Olympus camera formats.

## Features

- Automatically organizes media files by date and session
- Handles both images (ORF, JPG) and videos (MOV)
- Smart session detection based on time gaps between photos
- Separates morning (AM) and afternoon (PM) sessions
- Handles Olympus RAW formats (ORF and ORI)
- Maintains an import history to prevent duplicates
- Supports dry run mode for testing
- Progress tracking and detailed logging

## Installation

OMTriage requires Python 3.12 or later. Install using Poetry:

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

## Usage

The basic command to import media files:

```bash
poetry run omtriage /path/to/sd/card /path/to/output/directory
```

### Options

- `--session-gap HOURS`: Set the time gap (in hours) between sessions (default: 3)
- `--dry-run`: Preview what would be imported without making changes
- `--force-reimport`: Force reimport of previously imported files
- `--log-level {DEBUG,INFO,WARNING,ERROR}`: Set logging verbosity

### Output Structure

```
output_directory/
├── 2024-01-15-AM/
│   ├── images/
│   │   ├── P1150001.ORF
│   │   └── P1150001.JPG
│   └── videos/
│       └── P1150002.MOV
├── 2024-01-15-PM/
│   └── images/
│       ├── P1150003.ORF
│       └── P1150003.JPG
└── .import_history.db
```

- Files are organized by date and session (AM/PM)
- Images and videos are separated into different folders
- Multiple sessions on the same day are numbered (e.g., AM-1, AM-2)
- Import history is maintained in a SQLite database

## Development

### Setup

1. Clone the repository:
```bash
git clone https://github.com/brunograndephd/omtriage.git
cd omtriage
```

2. Install development dependencies:
```bash
poetry install
```

### Testing

Run the test suite:

```bash
poetry run pytest
```

For coverage report:

```bash
poetry run pytest --cov=omtriage
```

### Project Structure

- `omtriage/`: Main package directory
  - `cli.py`: Command-line interface
  - `models.py`: Data models (MediaFile, Session, etc.)
  - `metadata.py`: EXIF metadata extraction
  - `organizer.py`: File organization logic
  - `database.py`: Import history tracking

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
