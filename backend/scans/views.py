from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from rest_framework.reverse import reverse
from .models import Scan, LibraryEntry
from .serializers import LibraryEntrySerializer
from .pipeline.run import run_pipeline


class IndexView(APIView):
    """Root route. Confirms the backend is up and lists the endpoints the app uses."""

    def get(self, request):
        return Response({
            "service": "shelfie-api",
            "status": "ok",
            "endpoints": {
                "scan": reverse("scan", request=request),
                "library": reverse("library", request=request),
            },
        })

class ScanView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            return Response({"detail": "No image supplied."},
                            status=status.HTTP_400_BAD_REQUEST)

        scan = Scan.objects.create(image=image)

        try:
            detections, errors, timings = run_pipeline(scan.image.path)
        except Exception as exc:
            return Response(
                {"scan_id": scan.id, "detections": [],
                 "errors": [{"stage": "pipeline", "detail": str(exc)}],
                 "timings_ms": {}},
                status=status.HTTP_200_OK,
            )

        return Response({
            "scan_id": scan.id,
            "detections": detections,
            "errors": errors,
            "timings_ms": timings,
        })


class LibraryView(APIView):
    def get(self, request):
        return Response(LibraryEntrySerializer(LibraryEntry.objects.all(), many=True).data)

    def post(self, request):
        books = request.data.get("books", [])
        created = [
            LibraryEntry.objects.create(
                catalog_id=b.get("catalog_id") or "",
                title=b.get("title", ""),
                author=b.get("author") or "",
                source_scan_id=request.data.get("scan_id"),
            )
            for b in books
        ]
        return Response(LibraryEntrySerializer(created, many=True).data,
                        status=status.HTTP_201_CREATED)