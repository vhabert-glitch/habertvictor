"""
Management command : backfill company_size sur les offres existantes.
"""
from django.core.management.base import BaseCommand
from apps.extractor.models import JobPosting
from apps.extractor.classifier import classify_company_size


class Command(BaseCommand):
    help = 'Backfill le champ company_size sur les offres existantes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Ré-écraser les valeurs déjà renseignées',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']

        if overwrite:
            qs = JobPosting.objects.all()
        else:
            qs = JobPosting.objects.filter(company_size='')

        total = qs.count()
        self.stdout.write(f'{total} offres à traiter...')

        updated = 0
        for job in qs.iterator():
            size = classify_company_size(job.company, job.raw_description)
            if size and size != job.company_size:
                job.company_size = size
                job.save(update_fields=['company_size'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Terminé : {updated}/{total} offres enrichies avec company_size.'
        ))
