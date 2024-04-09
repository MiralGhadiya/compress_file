from django.urls import path
from .views import ImageCompressView, PdfCompressView, DocxCompressView, VideoCompressView

urlpatterns = [
    path('compress/image/', ImageCompressView.as_view(), name='image_compress'),
    path('compress/pdf/', PdfCompressView.as_view(), name='pdf_compress'),
    path('compress/docx/', DocxCompressView.as_view(), name='docx_compress'),
    path('compress/video/', VideoCompressView.as_view(), name='video_compress'),
]