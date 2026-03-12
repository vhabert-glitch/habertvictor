"""
Pipeline de classification : associe les données extraites aux secteurs et types de formation.
"""

from data.reference import SECTORS, TRAINING_TYPES

# Mapping mots-clés → type de formation
TRAINING_KEYWORDS = {
    'fondamentaux_ia': [
        'machine learning', 'intelligence artificielle', 'deep learning',
        'réseau de neurones', 'algorithme', 'ia', 'ml', 'ai',
    ],
    'data_science': [
        'data science', 'data scientist', 'analyse de données', 'data analyst',
        'statistiques', 'big data', 'données massives',
    ],
    'nlp': [
        'nlp', 'traitement du langage', 'chatbot', 'llm', 'gpt',
        'ia générative', 'genai', 'prompt engineering', 'transformers',
        'langage naturel',
    ],
    'computer_vision': [
        'vision par ordinateur', 'computer vision', 'reconnaissance d\'image',
        'détection d\'objets', 'opencv', 'yolo',
    ],
    'ia_decisionnelle': [
        'aide à la décision', 'business intelligence', 'prédictif',
        'scoring', 'recommandation', 'analytique',
    ],
    'ethique_ia': [
        'éthique', 'biais', 'ia responsable', 'équité', 'transparence',
        'explicabilité',
    ],
    'ia_reglementaire': [
        'ai act', 'réglementation', 'conformité', 'rgpd', 'régulation',
        'certification',
    ],
    'deploiement_mlops': [
        'mlops', 'déploiement', 'production', 'devops', 'docker',
        'kubernetes', 'pipeline ml', 'mlflow',
    ],
    'ia_metier': [
        'use case', 'cas d\'usage', 'application métier', 'automatisation',
        'rpa', 'processus',
    ],
    'management_ia': [
        'management ia', 'transformation digitale', 'stratégie ia',
        'chef de projet ia', 'conduite du changement', 'gouvernance',
    ],
}

SECTOR_KEYWORDS = {
    'sante': ['santé', 'médical', 'hôpital', 'pharma', 'clinique', 'médecin', 'patient'],
    'finance': ['finance', 'banque', 'assurance', 'fintech', 'crédit', 'investissement'],
    'industrie': ['industrie', 'manufacturing', 'usine', 'production', 'automobile', 'aéronautique'],
    'retail': ['retail', 'commerce', 'e-commerce', 'distribution', 'vente', 'client'],
    'education': ['éducation', 'formation', 'enseignement', 'université', 'école', 'edtech'],
    'energie': ['énergie', 'environnement', 'renouvelable', 'nucléaire', 'transition'],
    'transport': ['transport', 'logistique', 'mobilité', 'supply chain', 'livraison'],
    'administration': ['administration', 'service public', 'gouvernement', 'collectivité'],
}


def classify_training_type(text):
    """Détermine le type de formation le plus pertinent pour un texte donné."""
    text_lower = text.lower()
    scores = {}
    for training_code, keywords in TRAINING_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[training_code] = score
    if scores:
        return max(scores, key=scores.get)
    return ''


def classify_sector(text):
    """Détermine le secteur le plus pertinent pour un texte donné."""
    text_lower = text.lower()
    scores = {}
    for sector_code, keywords in SECTOR_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[sector_code] = score
    if scores:
        return max(scores, key=scores.get)
    return ''


def classify_sectors_multi(text):
    """Retourne tous les secteurs détectés dans un texte."""
    text_lower = text.lower()
    detected = []
    for sector_code, keywords in SECTOR_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(sector_code)
    return detected


def compute_relevance_score(text):
    """Calcule un score de pertinence (0-1) basé sur la densité de mots-clés IA."""
    text_lower = text.lower()
    all_keywords = []
    for keywords in TRAINING_KEYWORDS.values():
        all_keywords.extend(keywords)
    matches = sum(1 for kw in all_keywords if kw in text_lower)
    return min(matches / 5.0, 1.0)


def extract_skills(text):
    """Extrait les compétences IA mentionnées dans un texte."""
    text_lower = text.lower()
    skills = set()
    skill_keywords = {
        'Python': ['python'],
        'TensorFlow': ['tensorflow'],
        'PyTorch': ['pytorch'],
        'Scikit-learn': ['scikit-learn', 'sklearn'],
        'NLP': ['nlp', 'traitement du langage'],
        'LLM': ['llm', 'large language model', 'gpt'],
        'Computer Vision': ['computer vision', 'vision par ordinateur'],
        'MLOps': ['mlops'],
        'SQL': ['sql'],
        'Deep Learning': ['deep learning'],
        'Data Engineering': ['data engineering', 'etl', 'pipeline de données'],
        'Cloud ML': ['aws sagemaker', 'azure ml', 'google cloud ai', 'vertex ai'],
        'Spark': ['spark', 'pyspark'],
        'Docker': ['docker', 'conteneurisation'],
    }
    for skill_name, keywords in skill_keywords.items():
        if any(kw in text_lower for kw in keywords):
            skills.add(skill_name)
    return list(skills)
