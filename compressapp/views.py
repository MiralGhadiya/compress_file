from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UploadedFile
from .serializers import ImageUploadSerializer,PdfUploadSerializer,DocxUploadSerializer,ZipUploadSerializer,VideoUploadSerializer
from PIL import Image
from PyPDF2 import PdfWriter, PdfReader
from docx2pdf import convert
import zipfile
import shutil
import os
import ffmpeg
import io
import platform
import subprocess
import tempfile

class ImageCompressView(APIView):
    def save_file(self, file_data, filename):
        directory = 'compressed_files'
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return filepath

    def compress_image(self, uploaded_image):
        image = Image.open(uploaded_image)
        
        # Check if the image is a GIF
        if image.format == 'GIF':
            # Convert GIF to PNG
            png_image = Image.new("RGB", image.size, (255, 255, 255))
            png_image.paste(image)
            output = io.BytesIO()
            png_image.save(output, format='PNG')
            output.seek(0)
            return output.getvalue()
        
        # For other image formats, compress as JPEG with 100% quality
        else:
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=100)
            output.seek(0)
            return output.getvalue()

    def post(self, request, format=None):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_image = serializer.validated_data['file']
            compressed_image_data = self.compress_image(uploaded_image)
            compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{uploaded_image.name}')
            return Response({'compressed_image': compressed_image_path}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class PdfCompressView(APIView):
    def save_file(self, file_data, filename):
        directory = 'compressed_files'
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return filepath

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
            return Response({'compressed_pdf': compressed_pdf_path}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocxCompressView(APIView):
    def save_file(self, file_data, filename):
        directory = 'compressed_files'
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return filepath

    def convert_docx_to_pdf(self, docx_path):
        platform_system = platform.system()
        if platform_system == 'Windows':
            convert(docx_path)
        elif platform_system == 'Linux':
            # Implement conversion using LibreOffice or other tools for Linux
            # Example:
            # subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path])
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

            # Continue with compression process...

            # Compress the converted DOCX file
            compressed_docx_path = self.save_file(open(temp_docx_path, 'rb').read(), f'compressed_docx_{uploaded_docx.name}')
            os.remove(temp_docx_path)  # Clean up temporary file

            # Return the path of the compressed DOCX file in the response
            return Response({'compressed_docx': compressed_docx_path}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

class ZipCompressView(APIView):
    def save_file(self, file_data, filename):
        directory = 'compressed_files'
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return filepath

    def post(self, request, format=None):
        serializer = ZipUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_zip = serializer.validated_data['file']
            temp_zip_path = 'temp.zip'
            temp_output_zip = 'temp_output.zip'
            with open(temp_zip_path, 'wb') as temp_file:
                for chunk in uploaded_zip.chunks():
                    temp_file.write(chunk)
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall('temp_extracted')
            shutil.make_archive(temp_output_zip.split('.')[0], 'zip', 'temp_extracted')
            compressed_zip_path = self.save_file(open(temp_output_zip, 'rb').read(), f'compressed_zip_{uploaded_zip.name}')
            os.remove(temp_zip_path)
            shutil.rmtree('temp_extracted')
            os.remove(temp_output_zip)
            return Response({'compressed_zip': compressed_zip_path}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VideoCompressView(APIView):
    def compress_video(self, input_path, output_path):
        # Compress the video using ffmpeg
        ffmpeg.input(input_path).output(output_path).run(overwrite_output=True)

    def save_file(self, file_data, filename):
        directory = 'compressed_files'
        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return filepath

    def post(self, request, format=None):
        serializer = VideoUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_video = serializer.validated_data['file']
            input_filepath = self.save_file(uploaded_video.read(), uploaded_video.name)
            output_filepath = os.path.join('compressed_files', f'compressed_{uploaded_video.name}')
            try:
                self.compress_video(input_filepath, output_filepath)
                return Response({'compressed_video': output_filepath}, status=status.HTTP_200_OK)
            except ffmpeg.Error as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
