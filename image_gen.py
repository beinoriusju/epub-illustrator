import argparse
import os
import json
import time
import html
import zipfile
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from pydantic import BaseModel

# Import functions from utils
from utils import extract_epub_spine_items, extract_illustrations

# Try importing optional dependencies, with error handling
try:
    from stability_sdk import client
    import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
    STABILITY_AVAILABLE = True
except ImportError:
    STABILITY_AVAILABLE = False
    print("Stability SDK not available. Stability image generation will be disabled.")

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Google Generative AI not available. Gemini prompting will be disabled.")

# Class for Gemini response schema
class EpubIllustrator(BaseModel):
    content: str

def setup_stability_api():
    """Initialize and return the Stability API client."""
    if not STABILITY_AVAILABLE:
        return None
    
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        print("Warning: STABILITY_API_KEY not found in environment variables.")
        return None
    
    return client.StabilityInference(key=api_key)

def setup_gemini_client():
    """Initialize and return the Gemini API client."""
    if not GEMINI_AVAILABLE:
        return None
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Warning: GOOGLE_API_KEY not found in environment variables.")
        return None
    
    return genai.Client(api_key=api_key)

def generate_illustration(prompt, path, stability_api):
    """
    Generates an illustration based on the given prompt using Stability AI.
    
    Args:
        prompt (str): The description for the image generation
        path (str): Path to save the generated image
        stability_api: The Stability API client
    """
    if not stability_api:
        print(f"Skipping illustration generation for: {prompt} (Stability AI not available)")
        return False
    
    try:
        answers = stability_api.generate(prompt=prompt, steps=30)
        for resp in answers:
            for artifact in resp.artifacts:
                if artifact.finish_reason == generation.FILTER:
                    print("Filtered content.")
                if artifact.type == generation.ARTIFACT_IMAGE:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(artifact.binary)
                    return True
    except Exception as e:
        print(f"Error generating illustration: {e}")
    
    return False

def gemini_illustrate_file(section_file, epub_filename, gemini_client, max_retries=5, sleep_seconds=5):
    """
    Illustrates a file using Gemini, with retry logic on server errors.
    
    Args:
        section_file (str): Path to the EPUB section file
        epub_filename (str): Name of the EPUB file for context
        gemini_client: The Gemini API client
        max_retries (int): Maximum number of retry attempts
        sleep_seconds (int): Time to wait between retries
        
    Returns:
        str: Illustrated content with <!-- illustration: ... --> tags
    """
    if not gemini_client:
        print(f"Skipping Gemini illustration for: {section_file} (Gemini not available)")
        return ""
    
    for attempt in range(max_retries):
        try:
            with open(section_file, 'r', encoding='utf-8') as file:
                content = file.read()
                
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-pro-preview-05-06',
                    contents=[
                        f"Given a content from an epub file {section_file} for a book {epub_filename} "
                        f"find best places to insert illustrations. Illustrations should be inserted as "
                        f"<!-- illustration: string --> Describe illustrations in vivid language in exactly "
                        f"one sentence. Illustrations should be helpful for the reader and provide valuable "
                        f"insight into the subject.",
                        content,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema=EpubIllustrator,
                    ),
                )
                data = json.loads(response.text)
                return data['content']
        except Exception as e:
            if '503' in str(e) or 'overloaded' in str(e):
                print(f"Gemini server overloaded, retrying in {sleep_seconds} seconds... (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_seconds)
            else:
                print(f"Gemini error: {e}")
                break
    
    print("Gemini failed after multiple retries.")
    return ""

def zip_epub(epub_dir, output_epub):
    """
    Create an EPUB file by zipping the contents of a directory.
    
    Args:
        epub_dir (str): Directory containing the extracted EPUB
        output_epub (str): Path for the output EPUB file
    """
    mimetype_path = Path(epub_dir) / 'mimetype'
    with zipfile.ZipFile(output_epub, 'w') as epub_zip:
        # Add mimetype file first, uncompressed
        if mimetype_path.exists():
            epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
        
        # Add the rest of the files
        for folder, _, files in os.walk(epub_dir):
            for file in files:
                file_path = Path(folder) / file
                rel_path = file_path.relative_to(epub_dir)
                if rel_path.as_posix() == 'mimetype':
                    continue
                epub_zip.write(file_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)

def process_epub(epub_path, output_path=None, max_files=None):
    """
    Process an EPUB file to add illustrations.
    
    Args:
        epub_path (str): Path to the input EPUB file
        output_path (str, optional): Path for the output illustrated EPUB
        max_files (int, optional): Maximum number of files to process (for testing)
    """
    # Load environment variables
    load_dotenv()
    
    # Set up API clients
    stability_api = setup_stability_api()
    gemini_client = setup_gemini_client()
    
    if not gemini_client and not stability_api:
        print("Error: Neither Gemini nor Stability API is available. Please check your API keys.")
        return
    
    # Get the EPUB filename for use in prompts
    epub_filename = os.path.basename(epub_path)
    
    # Extract the EPUB
    print(f"Extracting EPUB: {epub_path}")
    result = extract_epub_spine_items(epub_path)
    temp_dir = result[0]
    spine_items = result[1]
    
    print(f"Extracted EPUB to: {temp_dir}")
    print(f"Found {len(spine_items)} spine items")
    
    # Initialize a global illustration counter
    illustration_counter = 0
    
    # Create Images directory if it does not exist
    OEBPS_path = os.path.join(temp_dir, "OEBPS")
    images_dir = os.path.join(OEBPS_path, "Images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Limit the number of files to process if specified
    if max_files and max_files > 0:
        spine_items = spine_items[:max_files]
        print(f"Processing only the first {max_files} files (test mode)")
    
    # Process each spine item
    for file_path in spine_items:
        print(f"Processing file: {file_path}")
        
        # Read the content
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Skip small files
        if len(content) < 400:
            print(f"Skipping {file_path} (less than 400 characters)")
            continue
        
        # Generate illustrations with Gemini
        illustrated_content = gemini_illustrate_file(file_path, epub_filename, gemini_client)
        
        # If Gemini failed or is not available, use the original content
        if not illustrated_content:
            illustrated_content = content
            continue
        
        # Extract illustration prompts
        illustrations = extract_illustrations(illustrated_content)
        
        if not illustrations:
            print(f"No illustrations found in {file_path}")
            continue
        
        # Get the relative path to the images directory from the file
        img_rel_path = os.path.relpath(images_dir, start=os.path.dirname(file_path))
        
        # Process each illustration
        for illustration in illustrations:
            print(f"Generating illustration for: {illustration}")
            
            # Generate filename and paths
            illustration_filename = f"illustration_{illustration_counter}.png"
            illustration_counter += 1
            
            local_cache_dir = "./illustrations"
            os.makedirs(local_cache_dir, exist_ok=True)
            
            src_illustration_path = os.path.join(local_cache_dir, illustration_filename)
            dest_illustration_path = os.path.join(images_dir, illustration_filename)
            
            # Check if we already have the illustration cached
            if os.path.exists(src_illustration_path):
                print(f"Copying existing illustration: {src_illustration_path}")
                shutil.copy(src_illustration_path, dest_illustration_path)
            else:
                # Generate new illustration
                success = generate_illustration(illustration, dest_illustration_path, stability_api)
                if success:
                    # Cache the generated illustration
                    shutil.copy(dest_illustration_path, src_illustration_path)
                    print(f"Saved illustration to cache: {src_illustration_path}")
            
            # Replace the illustration tag with an image tag
            illustrated_content = illustrated_content.replace(
                f"<!-- illustration: {illustration} -->",
                f"<p><img src='{img_rel_path}/{illustration_filename}' alt='{html.escape(illustration)}' /></p>"
            )
        
        # Save the illustrated content back to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(illustrated_content)
            print(f"Updated {file_path} with illustrations.")
    
    # Determine output path if not specified
    if not output_path:
        output_path = os.path.splitext(epub_path)[0] + '_illustrated.epub'
    
    # Zip the illustrated files back into an EPUB
    zip_epub(temp_dir, output_path)
    print(f"Created illustrated EPUB: {output_path}")
    return output_path

def main():
    """Main entry point for the EPUB Illustrator CLI."""
    parser = argparse.ArgumentParser(description="EPUB Illustrator - Add AI-generated illustrations to EPUB files")
    parser.add_argument("epub_path", help="Path to the input EPUB file")
    parser.add_argument("--output", "-o", help="Path for the output illustrated EPUB (default: inputname_illustrated.epub)")
    parser.add_argument("--max-files", "-m", type=int, help="Maximum number of files to process (for testing)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.epub_path):
        print(f"Error: EPUB file not found: {args.epub_path}")
        return
    
    process_epub(args.epub_path, args.output, args.max_files)

if __name__ == "__main__":
    main()