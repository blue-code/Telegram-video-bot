import zipfile
import xml.etree.ElementTree as ET
import os
import logging

logger = logging.getLogger(__name__)

NAMESPACES = {
    'n': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'pkg': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/'
}

def get_epub_metadata(epub_path):
    """
    Extract title, author, and cover image from an EPUB file.
    Returns dict: {'title': str, 'author': str, 'cover_bytes': bytes or None, 'cover_ext': str}
    """
    metadata = {'title': None, 'author': None, 'cover_bytes': None, 'cover_ext': None}
    
    try:
        if not zipfile.is_zipfile(epub_path):
            return metadata

        with zipfile.ZipFile(epub_path, 'r') as z:
            # 1. Find rootfile (content.opf) in META-INF/container.xml
            try:
                container_xml = z.read('META-INF/container.xml')
                root = ET.fromstring(container_xml)
                rootfile_path = root.find('.//n:rootfile', NAMESPACES).attrib['full-path']
            except Exception:
                # Fallback: search for .opf file
                opf_files = [f for f in z.namelist() if f.endswith('.opf')]
                if not opf_files:
                    return metadata
                rootfile_path = opf_files[0]

            # 2. Parse content.opf
            opf_content = z.read(rootfile_path)
            opf_root = ET.fromstring(opf_content)
            
            # Extract Title
            title_elem = opf_root.find('.//dc:title', NAMESPACES)
            if title_elem is not None:
                metadata['title'] = title_elem.text

            # Extract Author
            author_elem = opf_root.find('.//dc:creator', NAMESPACES)
            if author_elem is not None:
                metadata['author'] = author_elem.text

            # 3. Find Cover Image
            cover_href = None
            
            # Method A: <meta name="cover" content="cover-id" />
            meta_cover = opf_root.find('.//pkg:meta[@name="cover"]', NAMESPACES)
            if meta_cover is not None:
                cover_id = meta_cover.attrib['content']
                # Find item with this id
                item = opf_root.find(f'.//pkg:item[@id="{cover_id}"]', NAMESPACES)
                if item is not None:
                    cover_href = item.attrib['href']

            # Method B: Search manifest for properties="cover-image" (EPUB 3)
            if not cover_href:
                item = opf_root.find('.//pkg:item[@properties="cover-image"]', NAMESPACES)
                if item is not None:
                    cover_href = item.attrib['href']
            
            # Method C: Look for item with id="cover" or id="cover-image"
            if not cover_href:
                for cid in ['cover', 'cover-image', 'cover-jpg', 'cover-png']:
                    item = opf_root.find(f'.//pkg:item[@id="{cid}"]', NAMESPACES)
                    if item is not None:
                        cover_href = item.attrib['href']
                        break

            # 4. Extract Cover Bytes
            if cover_href:
                # Resolve relative path
                opf_dir = os.path.dirname(rootfile_path)
                cover_path = os.path.join(opf_dir, cover_href).replace('\\', '/')
                # Normalize path (handle ../)
                cover_path = os.path.normpath(cover_path).replace('\\', '/')
                
                try:
                    metadata['cover_bytes'] = z.read(cover_path)
                    _, ext = os.path.splitext(cover_path)
                    metadata['cover_ext'] = ext.lower() or '.jpg'
                except KeyError:
                    # Try finding file case-insensitively or just name match
                    for name in z.namelist():
                        if name.endswith(cover_href):
                            metadata['cover_bytes'] = z.read(name)
                            _, ext = os.path.splitext(name)
                            metadata['cover_ext'] = ext.lower()
                            break
                            
    except Exception as e:
        logger.error(f"Error parsing EPUB metadata: {e}")

    return metadata
