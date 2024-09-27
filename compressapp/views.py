from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from docx import Document
from subprocess import run
from .serializers import ImageUploadSerializer,PdfUploadSerializer,DocxUploadSerializer,VideoUploadSerializer
from PIL import Image
import os
from docx import Document
import zipfile
import io
import platform
import tempfile 
import subprocess
from django.conf import settings
import logging
from io import BytesIO
from django.http import JsonResponse
logger = logging.getLogger(__name__)
import traceback 

class BaseCompressView(APIView):
    def save_file(self, file_data, filename):
        media_directory = settings.MEDIA_ROOT
        filename = filename.replace(' ', '_')
        filepath = os.path.join(media_directory, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        return os.path.join(settings.MEDIA_URL, filename)

class ImageCompressView(BaseCompressView):
    def compress_image(self, uploaded_image, image_size_kb):
        with Image.open(uploaded_image) as image:

            if image.mode == 'RGBA':
                background = Image.new("RGBA", image.size, (255, 255, 255, 0))
                background.paste(image, (0, 0), image)
                image = background

            # Convert image to RGB if it's not in RGB or RGBA mode
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')

            output = io.BytesIO()

            # Choose format based on image mode
            format = 'PNG' if image.mode == 'RGBA' else 'JPEG'

            if image_size_kb < 1000:
                quality = 75
            else:
                quality = 85 

            # Compress the image and save it to output
            image.save(output, format=format, optimize=True, quality=quality)

            return output.getvalue()

    def post(self, request, format=None):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_image = serializer.validated_data['file']
            file_name = uploaded_image.name
            file_type = uploaded_image.content_type

            # Check the size of the uploaded image in kilobytes (KB)
            uploaded_image.seek(0, io.SEEK_END)
            image_size_kb = uploaded_image.tell() / 1024
            uploaded_image.seek(0)

            compressed_image_data = self.compress_image(uploaded_image, image_size_kb)

            compressed_size_kb = len(compressed_image_data) / 1024
            if compressed_size_kb >= image_size_kb:

                return Response({
                    'message': 'Sorry, Your Image is already very well compressed.',
                }, status=status.HTTP_400_BAD_REQUEST)

            compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{file_name}')
            # base_url = request.build_absolute_uri('/').rstrip('/')
            base_url="https://api.compressvideo.in"
            full_image_url = base_url + compressed_image_path

            return Response({
                'compressed_image': full_image_url,
                'file_name': file_name,
                'file_type': file_type,
                'original_size_kb': image_size_kb,
                'compressed_size_kb': compressed_size_kb
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PdfCompressView(BaseCompressView):
    def compress_pdf(self, input_path, output_path):
        system = platform.system()
        if system == 'Windows':
            gs_cmd = "C:\\Program Files\\gs\\gs10.03.1\\bin\\gswin64c.exe"  
        else:
            gs_cmd = 'gs'
        command = [
            gs_cmd,
            '-q', 
            '-dNOPAUSE', 
            '-dBATCH', 
            '-dSAFER',  
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/ebook',
            '-dEmbedAllFonts=true',  
            '-dSubsetFonts=true',  
            '-dCompressFonts=true',
            '-dColorImageDownsampleType=/Bicubic',
            '-dColorImageResolution=150',
            '-dGrayImageDownsampleType=/Bicubic',  
            '-dGrayImageResolution=150',  
            '-dMonoImageDownsampleType=/Bicubic', 
            '-dMonoImageResolution=150', 
            f'-sOutputFile={output_path}',
            input_path
        ]
            
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            logger.info(f"Ghostscript command executed with return code: {result.returncode}")
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8')
                logger.error(f"error_msg: {error_msg}")
                raise Exception(f'Error compressing PDF: {error_msg}')
            traceback.print_exc()
        except Exception as e:
            logger.exception(f'Error compressing PDF: {str(e)}')
            raise e


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

            output_filename = f'compressed_pdf_{uploaded_file.name.replace(" ", "_")}' 
            logger.info(f"output_filename: {output_filename}")
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)
            logger.info(f"output_filepath: {output_filepath}")
            traceback.print_exc()
            try:
                self.compress_pdf(input_filepath, output_filepath)
                traceback.print_exc()

                original_size = os.path.getsize(input_filepath)
                compressed_size = os.path.getsize(output_filepath)

                if compressed_size >= original_size:
                    os.remove(output_filepath)  # Remove the ineffective compressed file
                    return Response({
                        'message': "Sorry, Your PDF file is already very well compressed."
                    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

                # base_url = request.build_absolute_uri('/').rstrip('/')
                base_url = "https://api.compressvideo.in"
                logger.info({"base_url": base_url})
                
                full_pdf_url = base_url + settings.MEDIA_URL + output_filename
                logger.info({"full_pdf_url": full_pdf_url})

                return Response({'compressed_pdf': full_pdf_url, "file_name": file_name, "file_type": file_type}, status=status.HTTP_200_OK)
            except Exception as e:
                logger.exception({'error': str(e)})
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DocxCompressView(APIView):
    def compress_images(self, temp_dir):
        media_folder = os.path.join(temp_dir, 'word', 'media')
        if os.path.exists(media_folder):
            for filename in os.listdir(media_folder):
                file_path = os.path.join(media_folder, filename)
                if filename.endswith(('png', 'jpeg', 'jpg')):
                    with Image.open(file_path) as img:
                        img_io = BytesIO()
                        img.save(img_io, format=img.format, quality=60)  
                        img_io.seek(0)
                        
                        with open(file_path, 'wb') as f:
                            f.write(img_io.read())

    def compress_docx(self, input_path, output_path):

        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_ref.extractall(temp_dir)
                self.compress_images(temp_dir)

                # Recompress the contents into a new .docx (zip) file
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as compressed_zip:
                    for foldername, subfolders, filenames in os.walk(temp_dir):
                        for filename in filenames:
                            file_path = os.path.join(foldername, filename)
                            arcname = os.path.relpath(file_path, temp_dir)  
                            compressed_zip.write(file_path, arcname)

    def compress_doc(self, input_path, output_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_doc_path = os.path.join(temp_dir, os.path.basename(input_path))
            with open(input_path, 'rb') as src_file:
                with open(temp_doc_path, 'wb') as dest_file:
                    dest_file.write(src_file.read())
            
            # Create a new ZIP file containing the .doc file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(temp_doc_path, os.path.basename(input_path))


    def post(self, request, format=None):
        serializer = DocxUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            file_name = uploaded_file.name

            with tempfile.NamedTemporaryFile(delete=False) as temp_doc:
                for chunk in uploaded_file.chunks():
                    temp_doc.write(chunk)
                input_filepath = temp_doc.name

            if file_name.endswith('.docx') and uploaded_file.size < 247808: 
                return Response({
                    'message': "Sorry, Your Docx file is already very well compressed."
                }, status=status.HTTP_400_BAD_REQUEST)

            output_filename = f'compressed_{uploaded_file.name.replace(" ", "_")}'
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)

            try:
                if file_name.endswith('.docx'):
                    self.compress_docx(input_filepath, output_filepath)
                elif file_name.endswith('.doc'):
                    self.compress_doc(input_filepath, output_filepath)

                original_size = os.path.getsize(input_filepath)
                compressed_size = os.path.getsize(output_filepath)

                if compressed_size >= original_size:
                    os.remove(output_filepath)
                    return Response({'message': "Sorry, Your Doc or Docx file is already very well compressed."}, status=status.HTTP_400_BAD_REQUEST)
                # base_url = request.build_absolute_uri('/').rstrip('/')
                base_url = "https://api.compressvideo.in"
                full_doc_url = base_url + settings.MEDIA_URL + output_filename

                return Response({'compressed_doc': full_doc_url, "file_name": file_name, "file_type": uploaded_file.content_type}, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VideoCompressView(BaseCompressView):
    def compress_video(self, input_path, output_path, crf=28):
        system = platform.system()
        if system == 'Windows':
            ffmpeg_cmd = 'C:\\ffmpeg\\bin\\ffmpeg.exe'
        else:
            ffmpeg_cmd = 'ffmpeg'
        subprocess.run([ffmpeg_cmd, '-i', input_path, '-crf', str(crf), '-y', output_path])

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

            if uploaded_video.size < 132096:
                return Response({
                    'message': "Sorry, Your Video is already very well compressed."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            output_filename = f'compressed_{uploaded_video.name.replace(" ", "_")}'
            output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)
            try:
                self.compress_video(input_filepath, output_filepath)
                original_size = os.path.getsize(input_filepath)
                compressed_size = os.path.getsize(output_filepath)
                if compressed_size >= original_size:
                    os.remove(output_filepath)
                    return Response({'message': "Sorry, Your Video is already very well compressed."}, status=status.HTTP_400_BAD_REQUEST)

                # base_url = request.build_absolute_uri('/').rstrip('/')
                base_url = "https://api.compressvideo.in"
                full_video_url = base_url + settings.MEDIA_URL + output_filename
                
                return Response({'compressed_video': full_video_url,"file_name":file_name,"file_type":file_type}, status=status.HTTP_200_OK)
            except Exception as e:
                
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
