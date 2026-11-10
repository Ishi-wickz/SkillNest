from decimal import Decimal
from apps.marketplace.models import Skill
from apps.marketplace.serializers import SkillSerializer

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers

from .models import Profile, User


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    full_name = serializers.CharField(max_length=120)
    # Only these two roles are allowed. "admin" is rejected automatically.
    role = serializers.ChoiceField(choices=[User.Role.CLIENT, User.Role.FREELANCER])

    def validate_email(self, value):
        value = value.lower()  # emails are stored lowercase, so A@x.com and a@x.com are one account
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        # Run Django's password rules (length 10+, not common, not similar to the email)
        try:
            password_validation.validate_password(attrs["password"], User(email=attrs["email"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    @transaction.atomic  # user and profile are saved together or not at all
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
        )
        Profile.objects.create(user=user, full_name=validated_data["full_name"])
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        return value.lower()


class MeSerializer(serializers.ModelSerializer):
    # Only safe fields: never the password hash
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name"]

    def get_full_name(self, user):
        profile = getattr(user, "profile", None)  # superusers made in the terminal have no profile
        return profile.full_name if profile else None
    
class ProfileSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)           # read: nested objects
    skill_ids = serializers.PrimaryKeyRelatedField(               # write: plain ids
        queryset=Skill.objects.all(), source="skills", many=True, write_only=True, required=False
    )
    hourly_rate = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = ["full_name", "bio", "hourly_rate", "skills", "skill_ids"]  # never the user or email

    def validate(self, attrs):
        # The role comes from the session, never from the request body
        if self.context["request"].user.role != User.Role.FREELANCER:
            if attrs.get("hourly_rate") is not None:
                raise serializers.ValidationError({"hourly_rate": "Only freelancers have an hourly rate."})
            if attrs.get("skills"):
                raise serializers.ValidationError({"skill_ids": "Only freelancers can add skills."})
        return attrs