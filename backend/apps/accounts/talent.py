from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, Q
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from apps.marketplace.models import Review
from apps.marketplace.serializers import ReviewSerializer, SkillSerializer

from .models import Profile, User


class TalentSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Profile
        fields = ["id", "full_name", "bio", "hourly_rate", "skills", "avg_rating", "review_count"]
        read_only_fields = fields

    def get_avg_rating(self, profile):
        value = getattr(profile, "avg_rating", None)
        return round(value, 1) if value is not None else None


def talent_queryset():
    return (
        Profile.objects.filter(user__role=User.Role.FREELANCER, user__is_active=True)
        .prefetch_related("skills")
        .annotate(
            avg_rating=Avg("user__reviews_received__rating"),
            review_count=Count("user__reviews_received", distinct=True),
        )
    )


def _money(raw, name):
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValidationError({name: "Must be a number."})
    if not value.is_finite():
        raise ValidationError({name: "Must be a number."})
    return value


class TalentListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TalentSerializer

    def get_queryset(self):
        qs = talent_queryset()
        p = self.request.query_params
        q = p.get("q", "").strip()[:100]
        if q:
            by_skill = Profile.objects.filter(skills__name__icontains=q).values("id")
            qs = qs.filter(Q(full_name__icontains=q) | Q(bio__icontains=q) | Q(id__in=by_skill))
        if p.get("skill"):
            qs = qs.filter(id__in=Profile.objects.filter(skills__slug=p["skill"]).values("id"))
        if p.get("min"):
            qs = qs.filter(hourly_rate__gte=_money(p["min"], "min"))
        if p.get("max"):
            qs = qs.filter(hourly_rate__lte=_money(p["max"], "max"))
        return qs.order_by("-created_at", "-id")


class TalentDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = TalentSerializer

    def get_queryset(self):
        return talent_queryset()


class TalentReviewsView(generics.ListAPIView):
    """Public: the reviews a freelancer has received."""
    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return (
            Review.objects.filter(reviewee__profile__id=self.kwargs["pk"],
                                  reviewee__role=User.Role.FREELANCER)
            .select_related("job", "reviewer__profile")
            .order_by("-created_at", "-id")
        )