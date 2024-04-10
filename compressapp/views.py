from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UploadedFile
from .serializers import ImageUploadSerializer,PdfUploadSerializer,DocxUploadSerializer,VideoUploadSerializer
from PIL import Image
from PyPDF2 import PdfWriter, PdfReader
from docx2pdf import convert
import os
import ffmpeg
import io
import platform
import subprocess
import tempfile
from django.conf import settings

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
        
        if image.format == 'GIF':
            # Convert GIF to PNG
            png_image = Image.new("RGB", image.size, (255, 255, 255))
            png_image.paste(image)
            output = io.BytesIO()
            png_image.save(output, format='PNG')
            output.seek(0)
            return output.getvalue()
        
        # For other image formats, compress as JPEG with 70% quality
        else:
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=70)
            output.seek(0)
            return output.getvalue()

    def post(self, request, format=None):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_image = serializer.validated_data['file']
            compressed_image_data = self.compress_image(uploaded_image)
            compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{uploaded_image.name}')
            base_url = request.build_absolute_uri('/').rstrip('/')
            full_image_url = base_url + compressed_image_path
            return Response({'compressed_image': full_image_url}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class PdfCompressView(BaseCompressView):
    def post(self, request, format=None):
        serializer = PdfUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_pdf = serializer.validated_data['file']
            output_pdf = io.BytesIO()
            input_pdf_reader = PdfReader(uploaded_pdf)
            output_pdf_writer = PdfWriter()
            for page_num in range(len(input_pdf_reader.pages)):
                page = input_pdf_reader.pages[page_num]
                page.compress_content_streams()
                output_pdf_writer.add_page(page)
            output_pdf_writer.write(output_pdf)
            compressed_pdf_path = self.save_file(output_pdf.getvalue(), f'compressed_pdf_{uploaded_pdf.name}')
            base_url = request.build_absolute_uri('/').rstrip('/')
            full_pdf_url = base_url + compressed_pdf_path
            return Response({'compressed_image': full_pdf_url}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DocxCompressView(BaseCompressView):
    def convert_docx_to_pdf(self, docx_path):
        platform_system = platform.system()
        if platform_system == 'Windows':
            convert(docx_path)
        elif platform_system == 'Linux':
            pass
        else:
            raise Exception("Unsupported platform for DOCX to PDF conversion")
        
    def convert_odt_to_pdf(self, odt_path):
        platform_system = platform.system()
        if platform_system == 'Linux':
            try:
                subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', odt_path])
            except Exception as e:
                raise Exception(f"Error converting ODT to PDF: {e}")
        else:
            raise Exception("Unsupported platform for ODT to PDF conversion")

    def post(self, request, format=None):
        serializer = DocxUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_docx = serializer.validated_data['file']
            temp_docx_path = 'temp_file'

            # Save uploaded file
            with open(temp_docx_path, 'wb') as temp_file:
                for chunk in uploaded_docx.chunks():
                    temp_file.write(chunk)

            # Convert DOCX to PDF
            try:
                self.convert_docx_to_pdf(temp_docx_path)
            except Exception as e:
                os.remove(temp_docx_path)  # Clean up temporary file
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Compress the converted DOCX file
            compressed_docx_path = self.save_file(open(temp_docx_path, 'rb').read(), f'compressed_docx_{uploaded_docx.name}')
            os.remove(temp_docx_path)  # Clean up temporary file
            base_url = request.build_absolute_uri('/').rstrip('/')
            full_docx_url = base_url + compressed_docx_path
            return Response({'compressed_image': full_docx_url}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class VideoCompressView(BaseCompressView):
    def compress_video(self, input_path, output_path):
        ffmpeg.input(input_path).output(output_path).run(overwrite_output=True)

    def post(self, request, format=None):
        serializer = VideoUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_video = serializer.validated_data['file']
            with tempfile.NamedTemporaryFile(delete=False) as temp_video:
                for chunk in uploaded_video.chunks():
                    temp_video.write(chunk)
                input_filepath = temp_video.name
            output_filename = f'compressed_{uploaded_video.name}'
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)
            try:
                self.compress_video(input_filepath, output_filepath)
                
                # Dynamically generate the full video URL
                base_url = request.build_absolute_uri('/').rstrip('/')
                full_video_url = base_url + settings.MEDIA_URL + output_filename
                
                return Response({'compressed_video': full_video_url}, status=status.HTTP_200_OK)
            except ffmpeg.Error as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)