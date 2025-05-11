# EPUB Illustrator

![](illustration.png "Example illustration")

EPUB Illustrator is a Python tool that automatically enhances EPUB books with AI-generated illustrations based on the content.

## Features

- Analyzes EPUB content to identify appropriate places for illustrations
- Uses Gemini AI to generate illustration descriptions
- Creates illustrations using Stability AI
- Caches generated illustrations for reuse
- Respects EPUB structure and maintains file integrity
- Command-line interface for easy use

## Requirements

- Python 3.8+
- API keys for:
  - Gemini Pro (Google AI)
  - Stability AI (optional, for image generation)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/beinoriusju/epub-illustrator.git
   cd epub-illustrator
   ```

2. Install the required packages:
   ```
   python -m venv venv
   source ./venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with your API keys:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   STABILITY_API_KEY=your_stability_api_key_here
   ```

## Usage

The basic usage is:

```
python image_gen.py path/to/your/book.epub
```

### Command-line Options

- `epub_path`: Path to the input EPUB file (required)
- `--output` or `-o`: Path for the output illustrated EPUB (default: `inputname_illustrated.epub`)
- `--max-files` or `-m`: Maximum number of files to process (for testing)

### Examples

Process an entire EPUB file:
```
python image_gen.py my_book.epub
```

Specify a custom output path:
```
python image_gen.py my_book.epub -o illustrated_book.epub
```

Process only the first 5 files (for testing):
```
python image_gen.py my_book.epub -m 5
```

## How It Works

1. The tool extracts the EPUB file to a temporary directory
2. It analyzes the content using Gemini AI to identify suitable places for illustrations
3. For each illustration opportunity, it generates an image using Stability AI
4. The images are placed into the EPUB structure
5. The modified EPUB is reassembled and saved

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.