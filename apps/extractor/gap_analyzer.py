"""
Moteur de recommandation de cours : analyse l'écart entre compétences
demandées (offres d'emploi) et compétences couvertes (formations existantes).
"""
from collections import Counter, defaultdict
from apps.extractor.models import JobPosting, FormationCatalog
from apps.extractor.classifier import extract_skills


# Rôles émergents à mapper
EMERGING_ROLES = [
    'chief ai officer',
    'ai product manager',
    'ai ethics officer',
    'context engineer',
    'ai solution architect',
    'ai reliability engineer',
    'ingénieur rag',
    'responsable ia générative',
    'ai governance',
    'prompt engineer',
    'ai agents',
    'vector database',
]


def compute_skill_demand():
    """Compte les skills demandés dans toutes les offres d'emploi.

    Returns:
        Counter: {skill_name: count}
    """
    demand = Counter()
    for job in JobPosting.objects.all():
        for skill in job.skills:
            demand[skill] += 1
    return demand


def compute_skill_supply():
    """Compte les skills couverts par les formations existantes.

    Returns:
        Counter: {skill_name: count}
    """
    supply = Counter()
    for formation in FormationCatalog.objects.all():
        skills = formation.skills_covered
        if not skills:
            # Fallback: extract from text
            text = f"{formation.name} {formation.description}"
            skills = extract_skills(text)
        for skill in skills:
            supply[skill] += 1
    return supply


def compute_gap_analysis():
    """Calcule le ratio demande/offre par skill → gap_score + gap_level.

    Returns:
        list[dict]: Sorted by gap_score descending.
            Each dict: {skill, demand, supply, gap_score, gap_level}
    """
    demand = compute_skill_demand()
    supply = compute_skill_supply()

    all_skills = set(demand.keys()) | set(supply.keys())
    results = []

    for skill in all_skills:
        d = demand.get(skill, 0)
        s = supply.get(skill, 0)

        # gap_score: ratio of unmet demand
        # Higher = more critical gap
        if d == 0 and s == 0:
            continue
        if s == 0:
            gap_score = d * 2.0  # No supply at all → very critical
        else:
            gap_score = d / s

        if gap_score >= 5.0:
            gap_level = 'critical'
        elif gap_score >= 3.0:
            gap_level = 'high'
        elif gap_score >= 1.5:
            gap_level = 'medium'
        else:
            gap_level = 'low'

        results.append({
            'skill': skill,
            'demand': d,
            'supply': s,
            'gap_score': round(gap_score, 2),
            'gap_level': gap_level,
        })

    results.sort(key=lambda x: x['gap_score'], reverse=True)
    return results


def compute_role_competency_map():
    """Mappe les rôles émergents → compétences requises.

    Agrège les skills des offres matchant chaque rôle.

    Returns:
        list[dict]: {role, job_count, skills: [{name, count}]}
    """
    role_map = []

    for role_keyword in EMERGING_ROLES:
        # Find matching jobs
        matching_jobs = []
        for job in JobPosting.objects.all():
            text = f"{job.title} {job.raw_description}".lower()
            if role_keyword in text:
                matching_jobs.append(job)

        if not matching_jobs:
            continue

        # Aggregate skills
        skill_counter = Counter()
        for job in matching_jobs:
            for skill in job.skills:
                skill_counter[skill] += 1

        top_skills = [
            {'name': name, 'count': count}
            for name, count in skill_counter.most_common(8)
        ]

        # Format role name nicely
        role_display = role_keyword.replace('ia générative', 'IA Générative').title()

        role_map.append({
            'role': role_display,
            'job_count': len(matching_jobs),
            'skills': top_skills,
        })

    role_map.sort(key=lambda x: x['job_count'], reverse=True)
    return role_map


def generate_course_recommendations():
    """Synthèse → recommandations concrètes de cours.

    Returns:
        list[dict]: {title, priority, skills, rationale}
    """
    gap = compute_gap_analysis()
    role_map = compute_role_competency_map()

    recommendations = []

    # 1. Recommandations basées sur les gaps critiques/high
    critical_skills = [g for g in gap if g['gap_level'] in ('critical', 'high')][:8]

    # Group related skills into courses
    skill_groups = _group_skills_for_courses(critical_skills)

    priority_order = 1
    for group in skill_groups:
        skills_list = [s['skill'] for s in group]
        avg_gap = sum(s['gap_score'] for s in group) / len(group)

        if avg_gap >= 5.0:
            priority = 'critical'
        elif avg_gap >= 3.0:
            priority = 'high'
        else:
            priority = 'medium'

        title = _generate_course_title(skills_list)

        recommendations.append({
            'title': title,
            'priority': priority,
            'priority_order': priority_order,
            'skills': skills_list,
            'rationale': _generate_rationale(group),
        })
        priority_order += 1

    # 2. Recommandations basées sur les rôles émergents
    for role in role_map[:4]:
        role_skills = [s['name'] for s in role['skills'][:5]]
        # Check if these skills are already in gap recommendations
        already_covered = any(
            set(role_skills) & set(r['skills']) for r in recommendations
        )
        if not already_covered and role_skills:
            recommendations.append({
                'title': f"Formation {role['role']}",
                'priority': 'high' if role['job_count'] >= 3 else 'medium',
                'priority_order': priority_order,
                'skills': role_skills,
                'rationale': f"{role['job_count']} offres détectées pour le rôle {role['role']}. "
                             f"Compétences clés : {', '.join(role_skills[:3])}.",
            })
            priority_order += 1

    return recommendations[:10]


def _group_skills_for_courses(gap_items):
    """Regroupe les skills liés en "cours potentiels"."""
    # Simple grouping by affinity
    groups = {
        'GenAI & LLM': ['LLM', 'RAG', 'LangChain', 'Fine-tuning', 'Prompt Engineering',
                         'Hugging Face', 'AI Agents', 'Vector DB'],
        'MLOps & Infra': ['MLOps', 'Docker', 'Kubernetes', 'Terraform', 'Cloud ML', 'Spark'],
        'Data & ML': ['Python', 'TensorFlow', 'PyTorch', 'Scikit-learn', 'Deep Learning',
                       'Data Engineering', 'SQL', 'NLP', 'Computer Vision'],
        'Gouvernance IA': ['AI Governance', 'AI Safety', 'AI Strategy', 'Data Governance',
                            'AI Ethics'],
        'Transverse': ['Agile', 'R&D'],
    }

    result = []
    used = set()

    for group_name, group_skills in groups.items():
        matching = [g for g in gap_items if g['skill'] in group_skills and g['skill'] not in used]
        if matching:
            result.append(matching)
            for m in matching:
                used.add(m['skill'])

    # Add ungrouped skills
    remaining = [g for g in gap_items if g['skill'] not in used]
    if remaining:
        result.append(remaining)

    return result


def _generate_course_title(skills):
    """Génère un titre de cours basé sur les skills."""
    if len(skills) == 1:
        return f"Maîtriser {skills[0]}"

    # Detect category
    genai_skills = {'LLM', 'RAG', 'LangChain', 'Fine-tuning', 'Prompt Engineering',
                    'Hugging Face', 'AI Agents', 'Vector DB'}
    mlops_skills = {'MLOps', 'Docker', 'Kubernetes', 'Terraform', 'Cloud ML'}
    gov_skills = {'AI Governance', 'AI Safety', 'AI Strategy', 'Data Governance'}

    skill_set = set(skills)

    if skill_set & genai_skills:
        return "IA Générative avancée : RAG, Agents & LLM en production"
    elif skill_set & mlops_skills:
        return "MLOps & Infrastructure IA : du prototype à la production"
    elif skill_set & gov_skills:
        return "Gouvernance IA & Conformité AI Act"
    else:
        return f"Formation : {', '.join(skills[:3])}"


def _generate_rationale(gap_items):
    """Génère une explication pour la recommandation."""
    parts = []
    for item in gap_items[:3]:
        if item['supply'] == 0:
            parts.append(f"{item['skill']} : {item['demand']} offres, aucune formation existante")
        else:
            parts.append(
                f"{item['skill']} : {item['demand']} offres vs {item['supply']} formations "
                f"(ratio {item['gap_score']}x)"
            )
    return '. '.join(parts) + '.'


def get_opportunities_data():
    """Point d'entrée principal : retourne toutes les données d'opportunités.

    Returns:
        dict: {gap_analysis, role_map, recommendations}
    """
    return {
        'gap_analysis': compute_gap_analysis()[:15],
        'role_map': compute_role_competency_map(),
        'recommendations': generate_course_recommendations(),
    }


# ═══════════════════════════════════════════════════════════════════════
#  Analyse par taille d'entreprise (TPE / PME / ETI / GE)
# ═══════════════════════════════════════════════════════════════════════

SIZE_LABELS = {
    'tpe': 'TPE (< 10)',
    'pme': 'PME (10-249)',
    'eti': 'ETI (250-4999)',
    'ge': 'GE (5000+)',
}


def compute_skill_demand_by_size():
    """Compte les skills demandés par taille d'entreprise.

    Returns:
        dict: {tpe: Counter, pme: Counter, eti: Counter, ge: Counter}
    """
    result = {size: Counter() for size in SIZE_LABELS}
    for job in JobPosting.objects.exclude(company_size=''):
        if job.company_size in result:
            for skill in job.skills:
                result[job.company_size][skill] += 1
    return result


def compute_gap_by_size():
    """Gap analysis filtré par company_size.

    Returns:
        dict: {tpe: list[gap_dict], pme: ..., eti: ..., ge: ...}
    """
    demand_by_size = compute_skill_demand_by_size()
    supply = compute_skill_supply()

    result = {}
    for size_code, demand in demand_by_size.items():
        all_skills = set(demand.keys()) | set(supply.keys())
        gaps = []
        for skill in all_skills:
            d = demand.get(skill, 0)
            s = supply.get(skill, 0)
            if d == 0:
                continue
            gap_score = d * 2.0 if s == 0 else d / s
            if gap_score >= 5.0:
                gap_level = 'critical'
            elif gap_score >= 3.0:
                gap_level = 'high'
            elif gap_score >= 1.5:
                gap_level = 'medium'
            else:
                gap_level = 'low'
            gaps.append({
                'skill': skill,
                'demand': d,
                'supply': s,
                'gap_score': round(gap_score, 2),
                'gap_level': gap_level,
            })
        gaps.sort(key=lambda x: x['gap_score'], reverse=True)
        result[size_code] = gaps[:10]

    return result


def _generate_size_recommendations(demand_by_size, supply):
    """Génère des recommandations ciblées par taille."""
    size_recos = {
        'tpe': {
            'label': 'TPE / Startups',
            'focus': 'Formations courtes et pratiques',
        },
        'pme': {
            'label': 'PME',
            'focus': 'Montée en compétences progressive',
        },
        'eti': {
            'label': 'ETI',
            'focus': 'Certifications et spécialisations',
        },
        'ge': {
            'label': 'Grandes entreprises',
            'focus': 'MLOps, gouvernance et déploiement à l\'échelle',
        },
    }

    recommendations = []
    for size_code, info in size_recos.items():
        demand = demand_by_size.get(size_code, Counter())
        top_skills = demand.most_common(5)
        if not top_skills:
            continue

        # Find skills with worst supply gap
        unmet = []
        for skill, count in top_skills:
            s = supply.get(skill, 0)
            if s == 0 or count / max(s, 1) >= 2.0:
                unmet.append(skill)

        recommendations.append({
            'size': size_code,
            'size_label': info['label'],
            'focus': info['focus'],
            'top_skills': [s for s, _ in top_skills],
            'unmet_skills': unmet[:3],
            'job_count': sum(demand.values()),
        })

    return recommendations


def get_size_comparison_data():
    """Point d'entrée : compare les besoins entre tailles d'entreprise.

    Returns:
        dict: {
            job_counts: {tpe: N, pme: N, eti: N, ge: N},
            skills_by_size: {skill: {tpe: N, pme: N, eti: N, ge: N}},
            gap_by_size: {tpe: [...], pme: [...], ...},
            recommendations: [...]
        }
    """
    demand_by_size = compute_skill_demand_by_size()
    supply = compute_skill_supply()

    # Job counts per size
    job_counts = {}
    for size_code in SIZE_LABELS:
        job_counts[size_code] = JobPosting.objects.filter(
            company_size=size_code
        ).count()

    # Top 10 skills across all sizes for comparison chart
    all_demand = Counter()
    for demand in demand_by_size.values():
        all_demand += demand
    top_skills = [s for s, _ in all_demand.most_common(10)]

    # Build comparison matrix: skill × size
    skills_by_size = {}
    for skill in top_skills:
        skills_by_size[skill] = {
            size_code: demand_by_size[size_code].get(skill, 0)
            for size_code in SIZE_LABELS
        }

    # Gap by size
    gap_by_size = {}
    for size_code, demand in demand_by_size.items():
        gaps = []
        for skill in top_skills:
            d = demand.get(skill, 0)
            s = supply.get(skill, 0)
            gaps.append({
                'skill': skill,
                'demand': d,
                'supply': s,
            })
        gap_by_size[size_code] = gaps

    # Recommendations
    recommendations = _generate_size_recommendations(demand_by_size, supply)

    return {
        'job_counts': job_counts,
        'size_labels': SIZE_LABELS,
        'skills_by_size': skills_by_size,
        'gap_by_size': gap_by_size,
        'recommendations': recommendations,
    }
