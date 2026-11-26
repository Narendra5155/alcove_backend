from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = request.user.notifications.all()
        if request.query_params.get("unread"):
            qs = qs.filter(is_read=False)
        limit = min(int(request.query_params.get("limit", 20) or 20), 100)
        return Response({
            "unread": request.user.notifications.filter(is_read=False).count(),
            "results": [n.as_dict() for n in qs[:limit]],
        })


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        ids = request.data.get("ids")
        if ids != "all":
            qs = qs.filter(pk__in=ids or [])
        updated = qs.update(is_read=True)
        return Response({"updated": updated, "unread": request.user.notifications.filter(is_read=False).count()})
