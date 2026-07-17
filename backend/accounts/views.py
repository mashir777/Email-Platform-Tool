from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts import services
from accounts.permissions import IsEmailVerified
from accounts.serializers import (
    AvatarUploadSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from core.responses import error_response, success_response


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        tags=["Authentication"],
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User registered successfully."),
        },
        summary="Register a new user",
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            user = services.register_user_and_notify(
                email=data["email"],
                password=data["password"],
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                phone=data.get("phone", ""),
                company_name=data.get("company_name", ""),
                timezone=data.get("timezone", "UTC"),
            )
            tokens = services.get_tokens_for_user(user)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Registration failed")
            return error_response(
                {"detail": ["Registration failed. Check server logs."]},
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            data={
                "user": UserSerializer(user, context={"request": request}).data,
                "tokens": tokens,
            },
            message="Registration successful. Please verify your email.",
            status_code=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        tags=["Authentication"],
        request=LoginSerializer,
        summary="Login with email and password",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            user = services.authenticate_user(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_401_UNAUTHORIZED)

        tokens = services.get_tokens_for_user(user)
        return success_response(
            data={
                "user": UserSerializer(user, context={"request": request}).data,
                "tokens": tokens,
            },
            message="Login successful.",
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        request=LogoutSerializer,
        summary="Logout and blacklist refresh token",
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            services.logout_user(refresh_token=serializer.validated_data["refresh"])
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(message="Logout successful.")


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"

    @extend_schema(
        tags=["Authentication"],
        request=LogoutSerializer,
        summary="Refresh access token",
    )
    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.serializers import TokenRefreshSerializer

        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            return error_response(
                {"refresh": [str(exc)]},
                status.HTTP_401_UNAUTHORIZED,
            )

        return success_response(data={"tokens": serializer.validated_data})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["Authentication"],
        request=ForgotPasswordSerializer,
        summary="Request password reset email",
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        services.request_password_reset(email=serializer.validated_data["email"])
        return success_response(
            message="If an account exists with that email, a reset link has been sent.",
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["Authentication"],
        request=ResetPasswordSerializer,
        summary="Reset password with token",
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            services.reset_password(
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["password"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(message="Password reset successful.")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(
        tags=["Authentication"],
        request=ChangePasswordSerializer,
        summary="Change password for authenticated user",
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            services.change_password(
                user=request.user,
                old_password=serializer.validated_data["old_password"],
                new_password=serializer.validated_data["password"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(message="Password changed successfully.")


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verify"

    @extend_schema(
        tags=["Authentication"],
        request=VerifyEmailSerializer,
        summary="Verify email address with token",
    )
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            user = services.verify_email(token=serializer.validated_data["token"])
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"user": UserSerializer(user, context={"request": request}).data},
            message="Email verified successfully.",
        )


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Resend email verification link",
    )
    def post(self, request):
        try:
            services.resend_verification_email(user=request.user)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(message="Verification email sent.")


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        responses={200: UserSerializer},
        summary="Get current user profile",
    )
    def get(self, request):
        return success_response(
            data={"user": UserSerializer(request.user, context={"request": request}).data},
        )

    @extend_schema(
        tags=["Profile"],
        request=ProfileUpdateSerializer,
        summary="Update current user profile",
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        user = services.update_user_profile(
            user=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data={"user": UserSerializer(user, context={"request": request}).data},
            message="Profile updated successfully.",
        )


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Profile"],
        request=AvatarUploadSerializer,
        summary="Upload or replace user avatar",
    )
    def post(self, request):
        serializer = AvatarUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        user = services.upload_user_avatar(
            user=request.user,
            avatar_file=serializer.validated_data["avatar"],
        )
        return success_response(
            data={"user": UserSerializer(user, context={"request": request}).data},
            message="Avatar uploaded successfully.",
        )

    @extend_schema(
        tags=["Profile"],
        summary="Delete user avatar",
    )
    def delete(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete(save=True)
        return success_response(message="Avatar removed successfully.")


class RolesListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        summary="List available user roles",
    )
    def get(self, request):
        return success_response(data={"roles": RoleSerializer.get_roles()})
