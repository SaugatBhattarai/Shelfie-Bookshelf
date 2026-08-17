from django.contrib import admin

from .models import LibraryEntry, Scan


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ("id", "image", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(LibraryEntry)
class LibraryEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "catalog_id", "source_scan", "confirmed_at")
    list_filter = ("source_scan",)
    search_fields = ("title", "author", "catalog_id")
    ordering = ("-confirmed_at",)
    readonly_fields = ("confirmed_at",)
