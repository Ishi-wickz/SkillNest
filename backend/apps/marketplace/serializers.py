from decimal import Decimal

from rest_framework import serializers

from .models import Category, Job, Proposal, Review, Skill


def full_name(user):
    # Superusers made in the terminal have no profile, so fall back to None
    profile = getattr(user, "profile", None)
    return profile.full_name if profile else None


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "slug"]


class JobSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )
    skills = SkillSerializer(many=True, read_only=True)
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="skills", many=True, write_only=True, required=False
    )
    budget_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(choices=["USD", "LKR"], default="USD")
    proposal_count = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    reviewed = serializers.SerializerMethodField()  # has the logged-in user already reviewed this job?

    class Meta:
        model = Job
        fields = [
            "id", "title", "description", "budget_type", "budget_amount", "currency",
            "status", "created_at", "category", "category_id", "skills", "skill_ids",
            "proposal_count", "client_name", "reviewed",
        ]
        read_only_fields = ["status", "created_at"]

    def get_proposal_count(self, job):
        count = getattr(job, "proposal_count", None)
        return count if count is not None else job.proposals.count()

    def get_client_name(self, job):
        return full_name(job.client)

    def get_reviewed(self, job):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return any(r.reviewer_id == request.user.id for r in job.reviews.all())


class ProposalSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    job_status = serializers.CharField(source="job.status", read_only=True)
    freelancer = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = ["id", "job", "job_title", "job_status", "freelancer", "bid_amount",
                  "delivery_days", "cover_letter", "status", "created_at"]
        read_only_fields = fields

    def get_freelancer(self, proposal):
        user = proposal.freelancer
        profile = getattr(user, "profile", None)
        rate = profile.hourly_rate if profile else None
        return {"id": user.id, "full_name": full_name(user),
                "hourly_rate": str(rate) if rate is not None else None}


class ProposalCreateSerializer(serializers.Serializer):
    bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    delivery_days = serializers.IntegerField(min_value=1, max_value=365)
    cover_letter = serializers.CharField(min_length=20, max_length=5000)


class ReviewSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    reviewer_name = serializers.SerializerMethodField()  # never the reviewer's email

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "created_at", "job_title", "reviewer_name"]
        read_only_fields = fields

    def get_reviewer_name(self, review):
        return full_name(review.reviewer)


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)