from django.db import models


class Scan(models.Model):
    image = models.ImageField(upload_to="scans/")
    created_at = models.DateTimeField(auto_now_add=True)


class LibraryEntry(models.Model):
    catalog_id = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    source_scan = models.ForeignKey(Scan, null=True, blank=True, on_delete=models.SET_NULL)
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confirmed_at"]