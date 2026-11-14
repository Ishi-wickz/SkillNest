from django.contrib.auth import authenticate, login, logout, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import emails
from .email_serializers import EmailOnlySerializer, ResetConfirmSerializer, TokenSerializer
from .models import Profile
from .serializers import LoginSerializer, MeSerializer, ProfileSerializer, SignupSerializer

RESET_ASKED = ("If an account exists for that email, we've sent a link to reset the password. "
               "It works for 1 hour. Check your spam folder if it doesn't arrive.")


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """The front end calls this once on page load so the browser receives the csrftoken cookie."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        emails.send_verification_email(user)  # never raises: a mail outage can't break signup
        login(request, user)
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class MyProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]  # no PUT

    def get_object(self):
        return get_object_or_404(Profile.objects.prefetch_related("skills"), user=self.request.user)


# ---------- Email verification ----------
class VerifyEmailSendView(APIView):
    """A logged-in user asks for another verification email."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email"

    def post(self, request):
        if request.user.email_verified:
            return Response({"detail": "Your email is already verified."})
        emails.send_verification_email(request.user)
        return Response({"detail": "Verification email sent. Check your inbox and spam folder."})


class VerifyEmailConfirmView(APIView):
    """The link in the email lands on a page that posts the token here. No login needed."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        data = TokenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = emails.user_from_verify_token(data.validated_data["token"])
        if user is None:
            raise ValidationError({"detail": "This verification link is invalid or has expired. "
                                             "Log in and ask for a new one."})
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return Response({"detail": "Your email is verified."})  # clicking twice is harmless


# ---------- Password reset ----------
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email"

    def post(self, request):
        data = EmailOnlySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        emails.send_password_reset(data.validated_data["email"])
        return Response({"detail": RESET_ASKED})  # identical for known and unknown addresses


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        data = ResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = emails.user_from_reset_link(v["uid"], v["token"])
        if user is None:
            raise ValidationError({"detail": "This reset link is invalid or has expired. "
                                             "Please request a new one."})
        try:
            password_validation.validate_password(v["password"], user)  # same rules as signup
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)})
        user.set_password(v["password"])
        user.email_verified = True  # they just proved they own this inbox
        user.save(update_fields=["password", "email_verified"])
        # Changing the password signs out every other session automatically
        return Response({"detail": "Your password has been changed. You can log in now."})