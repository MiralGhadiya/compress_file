from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from docx import Document
from subprocess import run
from .serializers import ImageUploadSerializer,PdfUploadSerializer,DocxUploadSerializer,VideoUploadSerializer
from PIL import Image
import os
from docx import Document
from docx2txt import process as extract_text
import zipfile
import ffmpeg 
import io
import platform
import tempfile 
import subprocess
from django.conf import settings
from django.utils.text import slugify

class BaseCompressView(APIView):
    def save_file(self, file_data, filename):
        media_directory = settings.MEDIA_ROOT
        filename = filename.replace(' ', '_')
        filepath = os.path.join(media_directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return os.path.join(settings.MEDIA_URL, filename)
class ImageCompressView(BaseCompressView):
    def compress_image(self, uploaded_image):
        image = Image.open(uploaded_image)
        # Convert GIF to PNG while preserving transparency
        if image.format == 'GIF':
            png_image = Image.new("RGBA", image.size, (255, 255, 255, 0))
            png_image.paste(image, (0, 0), image.convert('RGBA'))
            output = io.BytesIO()
            png_image.save(output, format='PNG')
            output.seek(0)
            return output.getvalue()

        if image.format == 'ICO':
            max_size = (32, 32)
            image.thumbnail(max_size, Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format='ICO')
            output.seek(0)
            return output.getvalue()
        else:
            if image.mode in ['RGBA', 'LA']:
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, (0, 0), image)
                # background.paste(image, mask=image.split()[3])
                image = background

            max_size = (800, 800) 
            image.thumbnail(max_size, Image.LANCZOS)      
            # Convert RGBA to RGB if necessary
            if image.mode in ['RGBA', 'P']:
                image = image.convert('RGB')
            # Compress the image with varying quality to reduce file size
            for quality in range(95, 0, -5):
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=quality)
                compressed_data = output.getvalue()
                
                if len(compressed_data) < uploaded_image.size:
                    return compressed_data 
            else:
                return uploaded_image.read()
    def post(self, request, format=None):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_image = serializer.validated_data['file']
            file_name = uploaded_image.name
            file_type = uploaded_image.content_type
            compressed_image_data = self.compress_image(uploaded_image)
            compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{uploaded_image.name}')
            base_url = request.build_absolute_uri('/').rstrip('/') 
            full_image_url = base_url + compressed_image_path
            return Response({
                'compressed_image': full_image_url,
                'file_name': file_name,
                'file_type': file_type,
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class PdfCompressView(BaseCompressView):
    def compress_pdf(self, input_path, output_path):
        system = platform.system()
        if system == 'Windows':
            gs_cmd = "C:\\Program Files\\gs\\gs10.03.0\\bin\\gswin64c.exe"  
        else:
            gs_cmd = 'gs'
        command = [gs_cmd, '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', '-dPDFSETTINGS=/screen',
                   '-dNOPAUSE', '-dQUIET', '-dBATCH', f'-sOutputFile={output_path}', input_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8')
            raise Exception(f'Error compressing PDF: {error_msg}')

    def post(self, request, format=None):
        serializer = PdfUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            file_name = uploaded_file.name
            file_type = uploaded_file.content_type
            with tempfile.NamedTemporaryFile(delete=False) as temp_pdf:
                for chunk in uploaded_file.chunks():
                    temp_pdf.write(chunk)
                input_filepath = temp_pdf.name
            output_filename = f'compressed_pdf{uploaded_file.name.replace(" ", "_")}'
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)
            try:
                self.compress_pdf(input_filepath, output_filepath)
                original_size = os.path.getsize(input_filepath)
                compressed_size = os.path.getsize(output_filepath)
                if compressed_size >= original_size:
                    # If the compressed file size is not smaller, delete the compressed file
                    os.remove(output_filepath)
                    return Response({'error': "Compression did not reduce file size."}, status=status.HTTP_400_BAD_REQUEST)
                base_url = request.build_absolute_uri('/').rstrip('/')
                full_pdf_url = base_url + settings.MEDIA_URL + output_filename

                return Response({'compressed_pdf': full_pdf_url, "file_name": file_name, "file_type": file_type}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DocxCompressView(BaseCompressView):
    def convert_docx_to_pdf(self, docx_path):
        platform_system = platform.system()
        if platform_system == 'Windows':
            run(['start', '/wait', 'soffice', '--headless', '--convert-to', 'pdf', docx_path], shell=True)
        elif platform_system == 'Linux':
            run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path])
        else:
            raise Exception("Unsupported platform for DOCX to PDF conversion")
        
    def compress_docx(self, docx_path):
        try:
            doc = Document(docx_path)
            doc.save(f'{docx_path}.compressed.docx')
            os.remove(docx_path)
            os.rename(f'{docx_path}.compressed.docx', docx_path)
        except Exception as e:
            raise Exception(f"Error compressing DOCX: {e}")
    
    def compress_odt(self, odt_path):
        try:
            with zipfile.ZipFile(odt_path, 'r') as odt_zip:
                with zipfile.ZipFile(f'{odt_path}.compressed.odt', 'w') as compressed_odt:
                    for item in odt_zip.infolist():
                        if item.filename not in ['mimetype', 'settings.xml']:
                            data = odt_zip.read(item.filename)
                            compressed_odt.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)
            os.remove(odt_path)
            os.rename(f'{odt_path}.compressed.odt', odt_path)
        except Exception as e:
            raise Exception(f"Error compressing ODT: {e}")
        
    def compress_doc(self, doc_path):
        try:
            with zipfile.ZipFile(doc_path, 'r') as doc_zip:
                with zipfile.ZipFile(f'{doc_path}.compressed.doc', 'w') as compressed_doc:
                    for item in doc_zip.infolist():
                        data = doc_zip.read(item.filename)
                        compressed_doc.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)
            os.remove(doc_path)
            os.rename(f'{doc_path}.compressed.doc', doc_path)
        except Exception as e:
            raise Exception(f"Error compressing DOC: {e}")
    def post(self, request, format=None):
        serializer = DocxUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            file_name = uploaded_file.name
            file_type = uploaded_file.content_type
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            temp_file_path = 'temp_file'

            with open(temp_file_path, 'wb') as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)

            if file_extension == '.docx':
                try:
                    self.convert_docx_to_pdf(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path)  
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.compress_docx(temp_file_path)
            elif file_extension == '.odt':
                try:
                    self.compress_odt(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path) 
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            elif file_extension == '.doc':
                try:
                    self.compress_doc(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path)  
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                os.remove(temp_file_path)  
                return Response({'error': 'Unsupported file format'}, status=status.HTTP_400_BAD_REQUEST)

            compressed_docx_path = self.save_file(open(temp_file_path, 'rb').read(), f'compressed_{uploaded_file.name}')
            os.remove(temp_file_path)  
            base_url = request.build_absolute_uri('/').rstrip('/')
            full_docx_url = base_url + compressed_docx_path
            return Response({'compressed_docx': full_docx_url,"file_name":file_name,"file_type":file_type}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VideoCompressView(BaseCompressView):
    def compress_video(self, input_path, output_path, crf=28):
        system = platform.system()
        if system == 'Windows':
            ffmpeg_cmd = 'C:\\ffmpeg\\bin\\ffmpeg.exe'
        else:
            ffmpeg_cmd = 'ffmpeg'
        subprocess.run([ffmpeg_cmd, '-i', input_path, '-crf', str(crf), output_path])

    def post(self, request, format=None):
        serializer = VideoUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_video = serializer.validated_data['file']
            file_name=uploaded_video.name
            file_type=uploaded_video.content_type
            with tempfile.NamedTemporaryFile(delete=False) as temp_video:
                for chunk in uploaded_video.chunks():
                    temp_video.write(chunk)
                input_filepath = temp_video.name
            output_filename = f'compressed_{uploaded_video.name.replace(" ", "_")}'
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)
            try:
                self.compress_video(input_filepath, output_filepath)
                # Check if compressed file size is smaller than original file size
                original_size = os.path.getsize(input_filepath)
                compressed_size = os.path.getsize(output_filepath)
                if compressed_size >= original_size:
                    # If the compressed file size is not smaller, delete the compressed file
                    os.remove(output_filepath)
                    return Response({'error': "Compression did not reduce file size."}, status=status.HTTP_400_BAD_REQUEST)
                
                # Dynamically generate the full video URL
                base_url = request.build_absolute_uri('/').rstrip('/')
                full_video_url = base_url + settings.MEDIA_URL + output_filename
                
                return Response({'compressed_video': full_video_url,"file_name":file_name,"file_type":file_type}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
