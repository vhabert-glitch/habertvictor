"""
Récupère le nom de l'entreprise dans les descriptions fabriquées, puis les vide.

Le scraper LinkedIn stockait `"<titre> - <entreprise>"` dans `raw_description`,
faute de champ où mettre l'entreprise. Ce n'était pas le texte de l'annonce :
le classifieur y cherchait des mots-clés métier qu'il ne pouvait pas trouver, et
`relevance_score` était calculé sur cette chaîne.

On extrait donc l'entreprise vers son nouveau champ, puis on vide la description
— une description vide est exacte, une description fabriquée ne l'est pas.
Seules les lignes dont la description correspond exactement au motif sont
touchées ; les vraies descriptions (Adzuna, France Travail, WTTJ) sont intactes.
"""
from django.db import migrations


def extraire_entreprise(apps, schema_editor):
    JobPosting = apps.get_model('extractor', 'JobPosting')

    recuperees, videes = 0, 0
    for offre in JobPosting.objects.exclude(raw_description='').iterator():
        desc = offre.raw_description.strip()
        titre = offre.title.strip()

        if desc == titre:
            # description = le titre recopié, aucune information
            offre.raw_description = ''
            offre.save(update_fields=['raw_description'])
            videes += 1
        elif desc.startswith(f'{titre} - '):
            offre.company = desc[len(titre) + 3:].strip()[:300]
            offre.raw_description = ''
            offre.save(update_fields=['company', 'raw_description'])
            recuperees += 1
            videes += 1

    if recuperees or videes:
        print(f"\n    {recuperees} entreprise(s) récupérée(s), "
              f"{videes} fausse(s) description(s) vidée(s).")


def noop(apps, schema_editor):
    """Irréversible : la fausse description n'avait aucune valeur à restaurer."""


class Migration(migrations.Migration):

    dependencies = [
        ('extractor', '0006_jobposting_company'),
    ]

    operations = [
        migrations.RunPython(extraire_entreprise, noop),
    ]
