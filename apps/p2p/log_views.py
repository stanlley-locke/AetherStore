from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.conf import settings
from pathlib import Path
import os

class SystemLogView(APIView):
    """Admin endpoint to retrieve the last N lines of the system log file"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not getattr(request.user, 'is_network_admin', False):
            return Response({'error': 'Admin privileges required'}, status=403)

        lines_count = int(request.query_params.get('lines', 100))
        log_path = Path(settings.BASE_DIR) / 'logs' / 'aether_system.log'

        if not log_path.exists():
            return Response({'logs': [], 'message': 'Log file not found'}, status=200)

        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to near the end for performance on large files
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                # Basic tail: read last 64KB and take lines (usually enough for 100 lines)
                buffer_size = 64 * 1024 
                f.seek(max(0, file_size - buffer_size))
                content = f.read()
                lines = content.splitlines()
                
                # Return the last N lines
                tail = lines[-lines_count:]
                
                return Response({
                    'count': len(tail),
                    'logs': tail
                })
        except Exception as e:
            return Response({'error': str(e)}, status=500)
