from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from users.api.serializers import UserSerializer
from users.models import User


class SelfView(GenericAPIView):
    serializer_class = UserSerializer

    def get(self, request):
        user = self.get_object()
        serializer = self.get_serializer(user)

        return Response(serializer.data)

    def get_object(self) -> User:
        return User.objects.get(pk=self.request.user.pk)
