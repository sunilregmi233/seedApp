from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('process/', views.process_image, name='process_image'),
    path('results/<int:image_id>/', views.show_results, name='show_results'),
    path('export/<int:image_id>/', views.export_csv, name='export_csv'),
]