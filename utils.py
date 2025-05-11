import tempfile
import zipfile
import os
import xml.etree.ElementTree as ET

def extract_epub_spine_items(epub_path):
    """
    Extracts the epub to a temp directory and returns a list of full paths to the spine items (in reading order).
    """
    temp_dir = tempfile.mkdtemp(prefix="epub_extract_")
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Step 1: Find the OPF file via META-INF/container.xml
    container_path = os.path.join(temp_dir, "META-INF", "container.xml")
    tree = ET.parse(container_path)
    root = tree.getroot()
    ns = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
    opf_rel_path = root.find('.//c:rootfile', ns).attrib['full-path']
    opf_path = os.path.join(temp_dir, opf_rel_path)

    # Step 2: Parse OPF for manifest and spine
    opf_tree = ET.parse(opf_path)
    opf_root = opf_tree.getroot()
    # Get namespace for OPF
    nsmap = {'opf': opf_root.tag.split('}')[0].strip('{')}
    manifest = {}
    for item in opf_root.find('opf:manifest', nsmap):
        manifest[item.attrib['id']] = item.attrib['href']
    spine_items = []
    for itemref in opf_root.find('opf:spine', nsmap):
        idref = itemref.attrib['idref']
        href = manifest[idref]
        # OPF path may be in a subdir, so join accordingly
        spine_items.append(os.path.normpath(os.path.join(os.path.dirname(opf_path), href)))
    return temp_dir, spine_items

def extract_illustrations(content):
    """
    Extracts illustrations from the content.
    """
    illustrations = []
    for line in content.split('\n'):
        if '<!-- illustration:' in line:
            start = line.index('<!-- illustration:') + len('<!-- illustration:')
            end = line.index('-->', start)
            illustrations.append(line[start:end].strip())
    return illustrations