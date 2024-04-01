
from django.urls import path
from myapp import views
from django.views.generic.base import RedirectView


urlpatterns = [
    path('', views.home, name='home'),
     path('search/', views.search_results, name='search_results'),
    path('details/<str:yayin_id>/', views.view_details, name='view_details'),
    path('download-pdf/<str:yayin_id>/', views.download_pdf, name='download_pdf'),
     path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico')),
]
