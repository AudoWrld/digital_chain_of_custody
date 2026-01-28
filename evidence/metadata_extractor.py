import hashlib
import io
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
import struct


class MetadataExtractor:
    """Extracts comprehensive metadata from evidence files for chain of custody."""
    
    @staticmethod
    def extract_all_metadata(file_obj, original_filename: str) -> Dict[str, Any]:
        """Extract all metadata from an evidence file."""
        file_obj.seek(0)
        file_content = file_obj.read()
        file_obj.seek(0)
        
        metadata = {
            'file_level': MetadataExtractor._extract_file_level_metadata(file_content, original_filename),
            'exif': {},
            'authenticity': {}
        }
        
        try:
            image = Image.open(io.BytesIO(file_content))
            metadata['exif'] = MetadataExtractor._extract_exif_metadata(image)
            metadata['authenticity'] = MetadataExtractor._validate_authenticity(image, metadata['exif'])
        except Exception as e:
            metadata['exif']['error'] = str(e)
            metadata['authenticity']['error'] = str(e)
        
        return metadata
    
    @staticmethod
    def _extract_file_level_metadata(file_content: bytes, original_filename: str) -> Dict[str, Any]:
        """Extract file-level metadata."""
        file_size = len(file_content)
        file_format = MetadataExtractor._detect_file_format(file_content)
        
        hashes = {
            'md5': hashlib.md5(file_content).hexdigest(),
            'sha256': hashlib.sha256(file_content).hexdigest()
        }
        
        return {
            'original_filename': original_filename,
            'file_format': file_format,
            'file_size': file_size,
            'file_size_human': MetadataExtractor._human_readable_size(file_size),
            'hashes': hashes,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _detect_file_format(file_content: bytes) -> str:
        """Detect file format from magic bytes."""
        if file_content.startswith(b'\xFF\xD8\xFF'):
            return 'JPG'
        elif file_content.startswith(b'\x89PNG\r\n\x1A\n'):
            return 'PNG'
        elif file_content.startswith(b'RIFF') and file_content[8:12] == b'WEBP':
            return 'WEBP'
        elif file_content.startswith(b'II*\x00') or file_content.startswith(b'MM\x00*'):
            return 'TIFF'
        elif file_content.startswith(b'ftyp'):
            return 'HEIC'
        elif file_content.startswith(b'GIF8'):
            return 'GIF'
        elif file_content.startswith(b'BM'):
            return 'BMP'
        else:
            return 'Unknown'
    
    @staticmethod
    def _human_readable_size(size: int) -> str:
        """Convert file size to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    @staticmethod
    def _extract_exif_metadata(image: Image.Image) -> Dict[str, Any]:
        """Extract EXIF metadata from image."""
        exif_data = {
            'basic': {},
            'camera': {},
            'gps': {},
            'image_properties': {},
            'software': {}
        }
        
        try:
            exif = image._getexif()
            if exif is None:
                exif_data['basic']['note'] = 'No EXIF data found'
                return exif_data
            
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                
                if tag_name == 'DateTimeOriginal':
                    exif_data['basic']['date_time_original'] = str(value)
                elif tag_name == 'DateTime':
                    exif_data['basic']['date_time'] = str(value)
                elif tag_name == 'DateTimeDigitized':
                    exif_data['basic']['date_time_digitized'] = str(value)
                elif tag_name == 'Make':
                    exif_data['camera']['make'] = str(value)
                elif tag_name == 'Model':
                    exif_data['camera']['model'] = str(value)
                elif tag_name == 'SerialNumber':
                    exif_data['camera']['serial_number'] = str(value)
                elif tag_name == 'Software':
                    exif_data['software']['name'] = str(value)
                elif tag_name == 'Orientation':
                    exif_data['image_properties']['orientation'] = str(value)
                elif tag_name == 'XResolution':
                    exif_data['image_properties']['x_resolution'] = str(value)
                elif tag_name == 'YResolution':
                    exif_data['image_properties']['y_resolution'] = str(value)
                elif tag_name == 'ResolutionUnit':
                    exif_data['image_properties']['resolution_unit'] = str(value)
                elif tag_name == 'ColorSpace':
                    exif_data['image_properties']['color_space'] = str(value)
                elif tag_name == 'ExifImageWidth':
                    exif_data['image_properties']['width'] = str(value)
                elif tag_name == 'ExifImageHeight':
                    exif_data['image_properties']['height'] = str(value)
                elif tag_name == 'GPSInfo':
                    gps_data = MetadataExtractor._extract_gps_data(value)
                    exif_data['gps'] = gps_data
            
            exif_data['image_properties']['format'] = image.format
            exif_data['image_properties']['mode'] = image.mode
            exif_data['image_properties']['size'] = str(image.size)
            
        except Exception as e:
            exif_data['error'] = str(e)
        
        return exif_data
    
    @staticmethod
    def _extract_gps_data(gps_info: Dict) -> Dict[str, Any]:
        """Extract GPS coordinates from EXIF."""
        gps_data = {}
        
        try:
            def convert_to_degrees(value):
                d, m, s = value
                return d + (m / 60.0) + (s / 3600.0)
            
            gps_tags = {}
            for key, value in gps_info.items():
                tag_name = GPSTAGS.get(key, key)
                gps_tags[tag_name] = value
            
            if 'GPSLatitude' in gps_tags and 'GPSLatitudeRef' in gps_tags:
                lat = convert_to_degrees(gps_tags['GPSLatitude'])
                if gps_tags['GPSLatitudeRef'] == 'S':
                    lat = -lat
                gps_data['latitude'] = lat
            
            if 'GPSLongitude' in gps_tags and 'GPSLongitudeRef' in gps_tags:
                lon = convert_to_degrees(gps_tags['GPSLongitude'])
                if gps_tags['GPSLongitudeRef'] == 'W':
                    lon = -lon
                gps_data['longitude'] = lon
            
            if 'GPSAltitude' in gps_tags:
                altitude = gps_tags['GPSAltitude']
                if isinstance(altitude, tuple):
                    altitude = altitude[0] / altitude[1] if len(altitude) > 1 else altitude[0]
                gps_data['altitude'] = float(altitude)
            
            if 'GPSDateStamp' in gps_tags:
                gps_data['date_stamp'] = str(gps_tags['GPSDateStamp'])
            
            if 'GPSTimeStamp' in gps_tags:
                gps_data['time_stamp'] = str(gps_tags['GPSTimeStamp'])
            
        except Exception as e:
            gps_data['error'] = str(e)
        
        return gps_data
    
    @staticmethod
    def _validate_authenticity(image: Image.Image, exif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authenticity indicators."""
        authenticity = {
            'metadata_consistency': True,
            'signs_of_editing': [],
            'missing_exif': [],
            'thumbnail_check': {},
            'warnings': []
        }
        
        try:
            exif = image._getexif()
            
            if exif is None:
                authenticity['missing_exif'].append('All EXIF data')
                authenticity['warnings'].append('No EXIF data found - file may have been stripped')
                authenticity['metadata_consistency'] = False
            else:
                basic = exif_data.get('basic', {})
                
                if 'date_time_original' not in basic:
                    authenticity['missing_exif'].append('DateTimeOriginal')
                    authenticity['warnings'].append('Original capture date missing')
                
                if 'date_time' not in basic:
                    authenticity['missing_exif'].append('DateTime')
                
                if 'date_time_digitized' not in basic:
                    authenticity['missing_exif'].append('DateTimeDigitized')
                
                if 'make' not in exif_data.get('camera', {}):
                    authenticity['missing_exif'].append('Camera Make')
                
                if 'model' not in exif_data.get('camera', {}):
                    authenticity['missing_exif'].append('Camera Model')
                
                if len(authenticity['missing_exif']) > 3:
                    authenticity['warnings'].append('Multiple EXIF fields missing - possible editing or stripping')
                    authenticity['metadata_consistency'] = False
                
                if 'date_time_original' in basic and 'date_time' in basic:
                    try:
                        dt_original = datetime.strptime(basic['date_time_original'], '%Y:%m:%d %H:%M:%S')
                        dt_modified = datetime.strptime(basic['date_time'], '%Y:%m:%d %H:%M:%S')
                        
                        if dt_modified < dt_original:
                            authenticity['signs_of_editing'].append('Modification date before original capture date')
                            authenticity['metadata_consistency'] = False
                    except Exception:
                        pass
                
                if 'software' in exif_data and exif_data['software']:
                    software_name = exif_data['software'].get('name', '').lower()
                    editing_software = ['photoshop', 'gimp', 'lightroom', 'snapseed', 'vsco', 'instagram']
                    for sw in editing_software:
                        if sw in software_name:
                            authenticity['signs_of_editing'].append(f'Edited with {sw}')
                            authenticity['warnings'].append(f'Image may have been edited with {sw}')
                            break
            
            try:
                if hasattr(image, 'thumbnail'):
                    thumb_io = io.BytesIO()
                    image.thumbnail((128, 128))
                    image.save(thumb_io, format='JPEG')
                    thumb_size = len(thumb_io.getvalue())
                    authenticity['thumbnail_check']['thumbnail_generated'] = True
                    authenticity['thumbnail_check']['thumbnail_size'] = thumb_size
            except Exception as e:
                authenticity['thumbnail_check']['error'] = str(e)
            
            if not authenticity['signs_of_editing'] and not authenticity['missing_exif']:
                authenticity['status'] = 'Likely Authentic'
            elif authenticity['signs_of_editing']:
                authenticity['status'] = 'Signs of Editing Detected'
            elif authenticity['missing_exif']:
                authenticity['status'] = 'Missing Metadata'
            else:
                authenticity['status'] = 'Unknown'
        
        except Exception as e:
            authenticity['error'] = str(e)
            authenticity['status'] = 'Validation Error'
        
        return authenticity
    
    @staticmethod
    def validate_metadata_integrity(metadata: Dict[str, Any]) -> Tuple[bool, list]:
        """Validate metadata integrity and return status with issues."""
        issues = []
        is_valid = True
        
        file_level = metadata.get('file_level', {})
        exif = metadata.get('exif', {})
        authenticity = metadata.get('authenticity', {})
        
        if not file_level.get('hashes', {}).get('sha256'):
            issues.append('SHA-256 hash missing')
            is_valid = False
        
        if not file_level.get('file_format'):
            issues.append('File format not detected')
            is_valid = False
        
        if authenticity.get('status') == 'Signs of Editing Detected':
            issues.append('Signs of editing detected in metadata')
            is_valid = False
        
        if authenticity.get('signs_of_editing'):
            for sign in authenticity['signs_of_editing']:
                issues.append(f'Editing sign: {sign}')
        
        if authenticity.get('missing_exif'):
            missing_count = len(authenticity['missing_exif'])
            if missing_count > 3:
                issues.append(f'{missing_count} EXIF fields missing - possible stripping')
        
        if authenticity.get('warnings'):
            for warning in authenticity['warnings']:
                issues.append(f'Warning: {warning}')
        
        return is_valid, issues