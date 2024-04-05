from django.urls import path
from .views import ImageCompressView, PdfCompressView, DocxCompressView, ZipCompressView, VideoCompressView

urlpatterns = [
    # path('compress/', FileCompressView.as_view(), name='compress_file'),
    path('compress/image/', ImageCompressView.as_view(), name='image_compress'),
    path('compress/pdf/', PdfCompressView.as_view(), name='pdf_compress'),
    path('compress/docx/', DocxCompressView.as_view(), name='docx_compress'),
    path('compress/zip/', ZipCompressView.as_view(), name='zip_compress'),
    path('compress/video/', VideoCompressView.as_view(), name='video_compress'),
]