from django.conf import settings
from django.db import models
from django.db.models import Q

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Job(models.Model):
    class BudgetType(models.TextChoices):
        FIXED = "fixed", "Fixed price"
        HOURLY = "hourly", "Hourly"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name="jobs")
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL, related_name="jobs")
    title = models.CharField(max_length=150)
    description = models.TextField(max_length=10000)
    budget_type = models.CharField(max_length=10, choices=BudgetType.choices)
    budget_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    skills = models.ManyToManyField(Skill, blank=True, related_name="jobs")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(budget_amount__gt=0), name="job_budget_positive"),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="job_feed_idx"),
            models.Index(fields=["category", "status"], name="job_category_idx"),
            models.Index(fields=["client", "-created_at"], name="job_client_idx"),
        ]

    def __str__(self):
        return self.title


class Proposal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="proposals")
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proposals")
    bid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.PositiveSmallIntegerField()
    cover_letter = models.TextField(max_length=5000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "freelancer"], name="one_proposal_per_job"),
            models.UniqueConstraint(
                fields=["job"], condition=Q(status="accepted"), name="one_accepted_per_job"
            ),
            models.CheckConstraint(condition=Q(bid_amount__gt=0), name="proposal_bid_positive"),
            models.CheckConstraint(condition=Q(delivery_days__gt=0), name="proposal_days_positive"),
        ]
        indexes = [
            models.Index(fields=["freelancer", "-created_at"], name="proposal_freelancer_idx"),
        ]


class Review(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_given")
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "reviewer"], name="one_review_per_party"),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"),
            models.CheckConstraint(condition=~Q(reviewer=models.F("reviewee")), name="no_self_review"),
        ]
        indexes = [models.Index(fields=["reviewee"], name="review_reviewee_idx")]