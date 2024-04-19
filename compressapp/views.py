from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UploadedFile
from docx import Document
# import win32com.client as win32

from subprocess import run


from .serializers import ImageUploadSerializer,PdfUploadSerializer,DocxUploadSerializer,VideoUploadSerializer
from PIL import Image
from PyPDF2 import PdfWriter, PdfReader
import shutil
from docx2pdf import convert
import os
from docx import Document
from docx2txt import process as extract_text
import zipfile
import ffmpeg 
from docx.shared import Pt, RGBColor
from io import BytesIO
from moviepy.editor import VideoFileClip
import magic 
import io
import platform
import subprocess
import tempfile
from django.conf import settings
from django.utils.text import slugify
import fitz 
from django.http import JsonResponse

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
        
        # Check if it's a favicon file (ICO format)
        if image.format == 'ICO':
            # For favicon files, keep the background same, just resize
            max_size = (32, 32)  # Adjust the maximum size for favicon as needed
            image.thumbnail(max_size, Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format='ICO')
            output.seek(0)
            return output.getvalue()
        
        # For other image formats, compress as JPEG with varying quality
        else:
            # Ensure transparency is preserved
            if image.mode in ['RGBA', 'LA']:
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # Ensure transparency is applied
                image = background
            
            # Resize the image
            max_size = (800, 800)  # Adjust the maximum size as needed
            image.thumbnail(max_size, Image.LANCZOS)
            
            # Convert RGBA to RGB if necessary
            if image.mode in ['RGBA', 'P']:
                image = image.convert('RGB')
            
            # Compress the image with varying quality to reduce file size
            for quality in range(95, 0, -5):
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=quality)
                compressed_data = output.getvalue()
                
                # Check if compressed size is smaller than original size
                if len(compressed_data) < uploaded_image.size:
                    return compressed_data  # Return compressed image data
            else:
                # If no compressed image is smaller, return original image data
                return uploaded_image.read()

    def post(self, request, format=None):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_image = serializer.validated_data['file']
            compressed_image_data = self.compress_image(uploaded_image)
            compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{uploaded_image.name}')
            return Response({'compressed_image': compressed_image_path}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
# class ImageCompressView(BaseCompressView):

#     def compress_image(self, uploaded_image):
#         image = Image.open(uploaded_image)
        
#         # Convert GIF to PNG
#         if image.format == 'GIF':
#             # png_image = Image.new("RGB", image.size, (255, 255, 255))
#             png_image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
#             png_image.paste(image)
#             output = io.BytesIO()
#             png_image.save(output, format='PNG')
#             output.seek(0)
#             return output.getvalue()
        
#         # For other image formats, compress as JPEG with 100% quality
#         else:
#             # Resize the image
#             max_size = (800, 800)  # Adjust the maximum size as needed
#             image.thumbnail(max_size, Image.LANCZOS)
            
#             # Convert RGBA to RGB if necessary
#             if image.mode in ['RGBA', 'P']:
#                 image = image.convert('RGB')
            
#             # Compress the image as JPEG
#             output = io.BytesIO()
#             image.save(output, format='JPEG', quality=95)
#             output.seek(0)
#             return output.getvalue()

#     def post(self, request, format=None):
#         serializer = ImageUploadSerializer(data=request.data)
#         if serializer.is_valid():
#             uploaded_image = serializer.validated_data['file']
#             file_name = uploaded_image.name
#             print("File Name:", file_name)
#             file_type = uploaded_image.content_type
#             print("File Type:", file_type)
#             compressed_image_data = self.compress_image(uploaded_image)
#             compressed_image_path = self.save_file(compressed_image_data, f'compressed_image_{uploaded_image.name}')
#             base_url = request.build_absolute_uri('/').rstrip('/')
#             full_image_url = base_url + compressed_image_path
#             return Response({'compressed_image': full_image_url,
#                              'file_name':file_name,
#                              'file_type':file_type}, status=status.HTTP_200_OK)
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PdfCompressView(BaseCompressView):
    def post(self, request, format=None):
        serializer = PdfUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_pdf = serializer.validated_data['file']

            # Get file name and file type
            file_name = uploaded_pdf.name
            print("File Name:", file_name)

            file_type = uploaded_pdf.content_type
            print("File Type:", file_type)

            output_pdf = io.BytesIO()
            pdf_reader = PdfReader(uploaded_pdf)
            pdf_writer = PdfWriter()

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]  # Use reader.pages[page_num]
                pdf_writer.add_page(page)

            # Write PDF to output buffer
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)

            # Compress PDF using PyMuPDF (fitz)
            compressed_pdf = io.BytesIO()
            pdf_document = fitz.open("pdf", output_pdf.getvalue())
            pdf_document.save(compressed_pdf, garbage=4, deflate=True)
            pdf_document.close()

            compressed_pdf.seek(0)

            # Save compressed PDF
            compressed_pdf_name = f'compressed_pdf_{uploaded_pdf.name}'
            compressed_pdf_path = self.save_file(compressed_pdf.getvalue(), compressed_pdf_name)
            print("Compressed PDF Path:", compressed_pdf_path)

            # Create full PDF URL
            base_url = request.build_absolute_uri('/').rstrip('/') 
            full_pdf_url = base_url + compressed_pdf_path
            print("Full PDF URL:", full_pdf_url)
            
            # Return response with compressed PDF URL, file name, and file type
            return Response({
                'compressed_pdf': full_pdf_url,
                'file_name': file_name,
                'file_type': file_type,
            }, status=status.HTTP_200_OK)
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
            # Open the ODT file as a zip archive
            with zipfile.ZipFile(odt_path, 'r') as odt_zip:
                # Create a new zip archive for compressed content
                with zipfile.ZipFile(f'{odt_path}.compressed.odt', 'w') as compressed_odt:
                    # Iterate over each file in the original archive
                    for item in odt_zip.infolist():
                        # Exclude mimetype and settings.xml files
                        if item.filename not in ['mimetype', 'settings.xml']:
                            # Add the file to the new archive with compression
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
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            temp_file_path = 'temp_file'

           
            with open(temp_file_path, 'wb') as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)

            # Convert DOCX to PDF
            if file_extension == '.docx':
                try:
                    self.convert_docx_to_pdf(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path)  
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.compress_docx(temp_file_path)
            # Compress ODT
            elif file_extension == '.odt':
                try:
                    self.compress_odt(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path) 
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # Compress DOC
            elif file_extension == '.doc':
                try:
                    self.compress_doc(temp_file_path)
                except Exception as e:
                    os.remove(temp_file_path)  
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                os.remove(temp_file_path)  
                return Response({'error': 'Unsupported file format'}, status=status.HTTP_400_BAD_REQUEST)

            compressed_file_path = self.save_file(open(temp_file_path, 'rb').read(), f'compressed_{uploaded_file.name}')
            os.remove(temp_file_path)  
            base_url = request.build_absolute_uri('/').rstrip('/')
            full_file_url = base_url + compressed_file_path
            return Response({'compressed_file': full_file_url}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VideoCompressView(BaseCompressView):
    def compress_video(self, input_path, output_path, crf=28):
        ffmpeg.input(input_path).output(output_path, crf=crf).run(overwrite_output=True)

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
                
                return Response({'compressed_video': full_video_url}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                os.unlink(input_filepath)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)










# class VideoCompressView(BaseCompressView):
#     def compress_video(self, input_path, output_path):
#         try:
#             path="C:\\ffmpeg\\bin\\ffmpeg.exe"
#             # Update FFmpeg command with compression settings (-crf)  
#             ffmpeg.input(input_path).output(output_path).run(cmd=path,overwrite_output=True)
#         except ffmpeg.Error as e:
#             raise e

#     def post(self, request, format=None):
#         serializer = VideoUploadSerializer(data=request.data)
#         if serializer.is_valid():
#             uploaded_video = serializer.validated_data['file']
#         if not uploaded_video:
#             return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
#         # Create a temporary file to store the uploaded video
#         with tempfile.NamedTemporaryFile(delete=False) as temp_video:
#             for chunk in uploaded_video.chunks():
#                 temp_video.write(chunk)
#             input_filepath = temp_video.name

#         # Compressed file name and path
#         output_filename = f'compressed_{uploaded_video.name}'
#         output_filepath = os.path.join(settings.MEDIA_ROOT, output_filename)

#         try:
#             self.compress_video(input_filepath, output_filepath)
            
#             # Get sizes of input and output files for debugging
#             input_file_size = os.path.getsize(input_filepath)
#             output_file_size = os.path.getsize(output_filepath)
#             print(f"Input File Size: {input_file_size} bytes")
#             print(f"Output File Size: {output_file_size} bytes")
            
#             # Generate the full video URL
#             base_url = request.build_absolute_uri('/').rstrip('/')
#             full_video_url = base_url + settings.MEDIA_URL + output_filename
            
#             return Response({
#                 'compressed_video': full_video_url,
#                 'input_file_size': input_file_size,
#                 'output_file_size': output_file_size
#             }, status=status.HTTP_200_OK)
#         except ffmpeg.Error as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#         finally:
#             os.unlink(input_filepath)
