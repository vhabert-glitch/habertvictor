"""
Management command : backfill skills_covered pour les FormationCatalog existantes.
"""
from django.core.management.base import BaseCommand
from apps.extractor.models import FormationCatalog
from apps.extractor.classifier import extract_skills


class Command(BaseCommand):
    help = 'Backfill skills_covered pour les formations existantes'

    def handle(self, *args, **options):
        formations = FormationCatalog.objects.filter(skills_covered=[])
        count = 0
        for f in formations:
            text = f"{f.name} {f.description}"
            skills = extract_skills(text)
            if skills:
                f.skills_covered = skills
                f.save(update_fields=['skills_covered'])
                count += 1
        self.stdout.write(self.style.SUCCESS(
            f'{count} formations mises à jour avec skills_covered.'
        ))
