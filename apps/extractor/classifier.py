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
    'innovation_digital': [
        'innovation', 'directeur innovation', 'responsable innovation',
        'chief digital officer', 'cdo', 'chief data officer',
        'chief ai officer', 'head of ai', 'vp innovation',
        'transformation numérique', 'digital transformation',
        'r&d', 'recherche et développement', 'open innovation',
        'lab innovation', 'incubateur', 'accélérateur',
        'digital factory', 'hub digital', 'poc', 'proof of concept',
        'veille technologique', 'disruption', 'agilité',
        'rag', 'retrieval augmented generation', 'agentic', 'ai agents',
        'context engineer', 'ai product manager', 'ai ethics officer',
        'ai solution architect', 'ai reliability engineer',
        'ai governance', 'ia générative responsable', 'ai safety',
        'langchain', 'vector database', 'fine-tuning', 'fine tuning',
        'hugging face', 'responsable ia générative',
    ],
}

SECTOR_KEYWORDS = {
    'sante': [
        'santé', 'médical', 'hôpital', 'pharma', 'clinique', 'médecin', 'patient',
        'sanofi', 'gsk', 'iqvia', 'servier', 'ipsen', 'biomerieux', 'biomérieux',
        'medtronic', 'johnson & johnson', 'pfizer', 'roche', 'novartis', 'astrazeneca',
        'bayer', 'abbvie', 'amgen', 'biotech', 'biotechnologie', 'thérapie',
        'imagerie médicale', 'dispositif médical', 'healthtech', 'health tech',
        'e-santé', 'esanté', 'télémédecine', 'diagnostic', 'oncologie',
        'radiologie', 'cardiologie', 'neurologie', 'génomique', 'bioinformatique',
        'essai clinique', 'clinical trial', 'pharmacovigilance', 'drug discovery',
        'ap-hp', 'inserm', 'chu', 'hôpitaux',
    ],
    'finance': ['finance', 'banque', 'assurance', 'fintech', 'crédit', 'investissement'],
    'industrie': [
        'industrie', 'manufacturing', 'usine', 'production', 'automobile', 'aéronautique',
        'robotique', 'roboticien', 'automatisme', 'automaticien', 'automate',
        'siemens', 'schneider', 'bosch', 'abb', 'fanuc', 'kuka',
        'renault', 'stellantis', 'psa', 'valeo', 'faurecia', 'forvia',
        'safran', 'airbus', 'dassault', 'thales', 'knds',
        'maintenance prédictive', 'jumeau numérique', 'digital twin',
        'plc', 'scada', 'iot industriel', 'industrie 4.0',
        'qualité industrielle', 'lean', 'supply chain',
        'capteur', 'embarqué', 'logiciel embarqué', 'système embarqué',
        'mécatronique', 'électrotechnique', 'contrôle commande',
        'sagemcom', 'efi automotive', 'continental',
    ],
    'retail': ['retail', 'commerce', 'e-commerce', 'distribution', 'vente', 'client',
               'decathlon', 'carrefour', 'auchan', 'leclerc', 'lvmh', 'dior', 'kering'],
    'education': ['éducation', 'formation', 'enseignement', 'université', 'école', 'edtech',
                  'enseignant', 'isen', 'ionis', 'cesi', 'epitech'],
    'energie': [
        'énergie', 'énergétique', 'environnement', 'renouvelable', 'nucléaire',
        'transition énergétique', 'transition écologique',
        'edf', 'engie', 'totalenergies', 'total energies', 'orano', 'framatome',
        'cea', 'iter', 'rte', 'erdf', 'enedis', 'grdf',
        'centrale nucléaire', 'réacteur', 'fission', 'fusion', 'tokamak',
        'démantèlement', 'radioprotection', 'sûreté nucléaire', 'asn',
        'smart grid', 'réseau électrique', 'réseau intelligent',
        'photovoltaïque', 'éolien', 'solaire', 'hydrogène', 'batterie',
        'stockage énergie', 'efficacité énergétique',
        'maintenance prédictive énergie', 'gestion de réseau',
        'carbon', 'carbone', 'décarbonation', 'émissions', 'co2',
        'pétrole', 'gaz naturel', 'raffinerie', 'pipeline',
        'irsn', 'andra', 'commissariat énergie atomique',
    ],
    'transport': ['transport', 'logistique', 'mobilité', 'supply chain', 'livraison'],
    'administration': ['administration', 'service public', 'gouvernement', 'collectivité'],
    'cyberdefense': [
        'cyberdéfense', 'cyber défense', 'cybersécurité', 'cyber sécurité',
        'défense', 'militaire', 'armée', 'dga', 'otan', 'nato',
        'sécurité nationale', 'renseignement', 'anssi', 'comcyber',
        'soc', 'csirt', 'cert', 'pentest', 'threat intelligence',
        'guerre informatique', 'cyberattaque', 'cyber menace',
        'sécurité informatique', 'infosec', 'red team', 'blue team',
    ],
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
        'AI Strategy': ['stratégie ia', 'ai strategy', 'innovation', 'transformation digitale'],
        'Data Governance': ['gouvernance données', 'data governance', 'data management'],
        'Agile': ['agile', 'scrum', 'design thinking', 'lean startup'],
        'R&D': ['r&d', 'recherche', 'innovation', 'poc', 'proof of concept'],
        'RAG': ['rag', 'retrieval augmented generation', 'retrieval-augmented'],
        'LangChain': ['langchain', 'langgraph', 'langsmith'],
        'Fine-tuning': ['fine-tuning', 'fine tuning', 'finetuning', 'rlhf', 'lora', 'qlora'],
        'Prompt Engineering': ['prompt engineering', 'prompt design', 'prompt tuning'],
        'AI Governance': ['ai governance', 'ia governance', 'gouvernance ia', 'ai act'],
        'AI Safety': ['ai safety', 'ia safety', 'alignement ia', 'ai alignment'],
        'Hugging Face': ['hugging face', 'huggingface', 'transformers'],
        'Vector DB': ['vector database', 'vector db', 'pinecone', 'weaviate', 'chromadb', 'qdrant', 'faiss'],
        'AI Agents': ['ai agents', 'agent ia', 'agentic', 'autonomous agent', 'multi-agent'],
        'Kubernetes': ['kubernetes', 'k8s', 'openshift'],
        'Terraform': ['terraform', 'infrastructure as code', 'iac'],
    }
    for skill_name, keywords in skill_keywords.items():
        if any(kw in text_lower for kw in keywords):
            skills.add(skill_name)
    return list(skills)
