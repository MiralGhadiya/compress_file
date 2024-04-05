from rest_framework import serializers
from .models import UploadedFile
from PIL import Image
import imghdr
import os

class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = ['id', 'file']

class CustomImageField(serializers.ImageField):
    default_error_messages = {
        'invalid_image': 'Only "jpg", "jpeg", "png", "webp", "gif", "bmp", "ico", "tiff" image files are allowed.'
    }

class ImageUploadSerializer(serializers.Serializer):
    file = CustomImageField()

class PdfUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        valid_extensions = ['pdf']
        if value.name.split('.')[-1].lower() not in valid_extensions:
            raise serializers.ValidationError("Only PDF files are allowed.")
        return value
    

class DocxUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        valid_extensions = ['doc', 'docx', 'odt']
        if value.name.split('.')[-1].lower() not in valid_extensions:
            raise serializers.ValidationError("Only .doc, .docx, .odt files are allowed.")
        return value
    
    
class ZipUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        valid_extensions = ['zip']
        if value.name.split('.')[-1].lower() not in valid_extensions:
            raise serializers.ValidationError("Only ZIP files are allowed.")
        return value


class VideoUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        valid_extensions = ['mp4', 'avi', 'mov', 'mkv', 'wmv']
        if value.name.split('.')[-1].lower() not in valid_extensions:
            raise serializers.ValidationError("Only MP4, AVI, MOV, MKV, WMV files are allowed.")
        return value