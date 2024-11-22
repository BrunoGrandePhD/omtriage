# Photo Importer

A Python tool for organizing photos and videos from camera SD cards into a structured directory layout.

## Features

- Organizes media files by date and session (AM/PM)
- Supports multiple file formats:
  - Images: ORF, ORI, JPG, JPEG
  - Videos: MOV, MP4
- Groups related files (e.g., RAW+JPEG pairs)
- Tracks imported files to avoid duplicates
- Extracts and uses capture time metadata
- Beautiful progress bars and logging

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/photo-importer.git
cd photo-importer

# Install using Poetry
poetry install
```

## Usage

```bash
# Basic usage
photo-import <input_dir> <output_dir>

# Example with options
photo-import /Volumes/SD_CARD ~/Pictures/Camera \
    --session-gap 4.0 \
    --log-level DEBUG \
    --dry-run

# Show help
photo-import --help
```

### Command-line Options

- `input_dir`: Directory containing media files to import
- `output_dir`: Directory to store organized media files
- `--session-gap HOURS`: Hours between sessions (default: 3.0)
- `--force-reimport`: Ignore previous import history
- `--dry-run`: Show what would be done without making changes
- `--log-level`: Set logging level (DEBUG/INFO/WARNING/ERROR)
- `--version`: Show version number

## Output Structure

```
output_dir/
├── 2024-01-15-AM/
│   ├── images/
│   │   ├── DSC001.ORF
│   │   └── DSC001.JPG
│   └── videos/
│       └── MOV001.MP4
└── 2024-01-15-PM-1/
    └── images/
        ├── DSC002.ORF
        └── DSC002.JPG
```

## Requirements

- Python 3.12 or later
- ExifTool (for metadata extraction)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
