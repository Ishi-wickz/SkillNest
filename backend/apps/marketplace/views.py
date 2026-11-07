from decimal import Decimal, InvalidOperation

from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Category, Job, Proposal, Skill
from .permissions import IsClient, IsFreelancer, IsJobOwner
from .serializers import (CategorySerializer, JobSerializer, ProposalCreateSerializer,
                          ProposalSerializer, SkillSerializer)


def job_queryset():
    # select_related / prefetch_related / annotate avoid one extra query per job (the N+1 problem)
    return (
        Job.objects.select_related("category", "client__profile")
        .prefetch_related("skills")
        .annotate(proposal_count=Count("proposals", distinct=True))
    )


def _money(raw, name):
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValidationError({name: "Must be a number."})
    if not value.is_finite():
        raise ValidationError({name: "Must be a number."})
    return value


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None  # short lists, no paging needed
    queryset = Category.objects.order_by("name")
    serializer_class = CategorySerializer


class SkillListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Skill.objects.order_by("name")
    serializer_class = SkillSerializer


class JobListCreateView(generics.ListCreateAPIView):
    """GET = public job feed (open jobs only). POST = clients post a job."""
    serializer_class = JobSerializer

    def get_permissions(self):
        return [IsClient()] if self.request.method == "POST" else [AllowAny()]

    def get_queryset(self):
        qs = job_queryset().filter(status=Job.Status.OPEN)
        p = self.request.query_params
        q = p.get("q", "").strip()[:100]  # cap the length
        if q:
            # icontains escapes % and _ itself, so user input can't break the query
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(skills__name__icontains=q)
            ).distinct()
        if p.get("category"):
            qs = qs.filter(category__slug=p["category"])
        if p.get("skill"):
            qs = qs.filter(skills__slug=p["skill"])
        if p.get("min"):
            qs = qs.filter(budget_amount__gte=_money(p["min"], "min"))
        if p.get("max"):
            qs = qs.filter(budget_amount__lte=_money(p["max"], "max"))
        return qs.order_by("-created_at", "-id")

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)  # the client comes from the session, never from the body


class MyJobsView(generics.ListAPIView):
    permission_classes = [IsClient]
    serializer_class = JobSerializer

    def get_queryset(self):
        return job_queryset().filter(client=self.request.user).order_by("-created_at", "-id")  # every status


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]  # no PUT

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsClient(), IsJobOwner()]

    def get_queryset(self):
        user = self.request.user
        qs = job_queryset()
        if user.is_authenticated:
            # Visible if open, or yours, or you have a proposal on it
            mine = Exists(Proposal.objects.filter(job=OuterRef("pk"), freelancer=user))
            return qs.annotate(has_proposal=mine).filter(
                Q(status=Job.Status.OPEN) | Q(client=user) | Q(has_proposal=True)
            )
        return qs.filter(status=Job.Status.OPEN)

    def perform_update(self, serializer):
        if serializer.instance.status != Job.Status.OPEN:
            raise ValidationError({"detail": "Only open jobs can be edited."})
        serializer.save()

    def perform_destroy(self, instance):
        # Soft delete: keep the row, because proposals and reviews point at it
        if instance.status != Job.Status.OPEN:
            raise ValidationError({"detail": "Only open jobs can be cancelled here."})
        instance.status = Job.Status.CANCELLED
        instance.save(update_fields=["status", "updated_at"])


class JobProposalsView(generics.ListCreateAPIView):
    """GET = the job owner sees proposals received. POST = a freelancer submits one."""
    serializer_class = ProposalSerializer

    def get_permissions(self):
        return [IsFreelancer()] if self.request.method == "POST" else [IsClient()]

    def get_queryset(self):
        # 404 unless this client owns the job
        job = get_object_or_404(Job, pk=self.kwargs["job_id"], client=self.request.user)
        return job.proposals.select_related("job", "freelancer__profile")

    def create(self, request, *args, **kwargs):
        data = ProposalCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        proposal = services.submit_proposal(
            job_id=kwargs["job_id"], freelancer=request.user, **data.validated_data
        )
        return Response(ProposalSerializer(proposal).data, status=status.HTTP_201_CREATED)


class MyProposalsView(generics.ListAPIView):
    permission_classes = [IsFreelancer]
    serializer_class = ProposalSerializer

    def get_queryset(self):
        return Proposal.objects.filter(freelancer=self.request.user).select_related(
            "job", "freelancer__profile"
        )


class AcceptProposalView(APIView):
    permission_classes = [IsClient]

    def post(self, request, pk):
        proposal = services.accept_proposal(proposal_id=pk, client=request.user)
        return Response(ProposalSerializer(proposal).data)


class RejectProposalView(APIView):
    permission_classes = [IsClient]

    def post(self, request, pk):
        proposal = services.reject_proposal(proposal_id=pk, client=request.user)
        return Response(ProposalSerializer(proposal).data)
