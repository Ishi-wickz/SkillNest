from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.marketplace.models import Category, Skill

CATEGORIES = [
    "Web Development", "Mobile Development", "UI/UX Design", "Graphic Design",
    "Writing & Translation", "Digital Marketing", "Data & Analytics", "Video & Animation",
]

SKILLS = [
    "Python", "Django", "FastAPI", "JavaScript", "TypeScript", "React", "Node.js",
    "HTML", "CSS", "PostgreSQL", "MySQL", "REST APIs", "Flutter", "React Native",
    "Figma", "Adobe Photoshop", "Adobe Illustrator", "Logo Design", "Copywriting",
    "Content Writing", "SEO", "Social Media Marketing", "Google Ads", "Data Analysis",
    "Excel", "Power BI", "Video Editing", "Motion Graphics", "WordPress", "Git",
]


class Command(BaseCommand):
    help = "Seed categories and skills. Safe to run repeatedly."

    @transaction.atomic  # all-or-nothing: no half-seeded database
    def handle(self, *args, **options):
        for name in CATEGORIES:
            # get_or_create: running seed twice never makes duplicates
            Category.objects.get_or_create(slug=slugify(name), defaults={"name": name})
        for name in SKILLS:
            Skill.objects.get_or_create(slug=slugify(name), defaults={"name": name})
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Category.objects.count()} categories, {Skill.objects.count()} skills."
        ))