from django.urls import path
from .views import IndexView, ScanView, LibraryView

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("scans/", ScanView.as_view(), name="scan"),
    path("library/", LibraryView.as_view(), name="library"),
]
