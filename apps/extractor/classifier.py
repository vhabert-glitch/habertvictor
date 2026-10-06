"""
Pipeline de classification : associe les données extraites aux secteurs et types de formation.
"""

from data.reference import SECTORS, TRAINING_TYPES, COMPANY_SIZES

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


# ── Détection taille d'entreprise ─────────────────────────────────────────

# Table de référence : entreprise connue → taille
KNOWN_COMPANIES = {
    # Grandes entreprises (GE, 5000+ salariés)
    'thales': 'ge', 'capgemini': 'ge', 'atos': 'ge', 'sopra steria': 'ge',
    'orange': 'ge', 'dassault': 'ge', 'airbus': 'ge', 'safran': 'ge',
    'sanofi': 'ge', 'totalenergies': 'ge', 'total energies': 'ge',
    'edf': 'ge', 'engie': 'ge', 'renault': 'ge', 'stellantis': 'ge',
    'société générale': 'ge', 'bnp paribas': 'ge', 'crédit agricole': 'ge',
    'axa': 'ge', 'lvmh': 'ge', 'l\'oréal': 'ge', 'loreal': 'ge',
    'schneider electric': 'ge', 'schneider': 'ge', 'saint-gobain': 'ge',
    'michelin': 'ge', 'valeo': 'ge', 'bouygues': 'ge', 'vinci': 'ge',
    'accenture': 'ge', 'ibm': 'ge', 'microsoft': 'ge', 'google': 'ge',
    'amazon': 'ge', 'meta': 'ge', 'apple': 'ge', 'oracle': 'ge', 'sap': 'ge',
    'deloitte': 'ge', 'ey': 'ge', 'kpmg': 'ge', 'pwc': 'ge', 'mckinsey': 'ge',
    'bcg': 'ge', 'bain': 'ge', 'cgi': 'ge', 'alten': 'ge', 'altran': 'ge',
    'carrefour': 'ge', 'auchan': 'ge', 'decathlon': 'ge', 'danone': 'ge',
    'psa': 'ge', 'faurecia': 'ge', 'forvia': 'ge', 'veolia': 'ge',
    'siemens': 'ge', 'bosch': 'ge', 'continental': 'ge', 'nokia': 'ge',
    'salesforce': 'ge', 'nvidia': 'ge', 'intel': 'ge', 'cisco': 'ge',
    'hp': 'ge', 'dell': 'ge', 'vmware': 'ge', 'broadcom': 'ge',
    'worldline': 'ge', 'amadeus': 'ge', 'dassault systèmes': 'ge',
    'ubisoft': 'ge', 'vivendi': 'ge', 'publicis': 'ge', 'criteo': 'ge',
    'orano': 'ge', 'framatome': 'ge', 'naval group': 'ge', 'mbda': 'ge',
    'nexter': 'ge', 'knds': 'ge', 'servier': 'ge', 'ipsen': 'ge',
    'biomerieux': 'ge', 'biomérieux': 'ge', 'pfizer': 'ge', 'roche': 'ge',
    'novartis': 'ge', 'astrazeneca': 'ge', 'bayer': 'ge', 'abbvie': 'ge',
    'johnson & johnson': 'ge', 'medtronic': 'ge', 'philips': 'ge',
    'enedis': 'ge', 'rte': 'ge', 'grdf': 'ge', 'cea': 'ge',
    'la poste': 'ge', 'sncf': 'ge', 'ratp': 'ge', 'air france': 'ge',
    'société générale': 'ge', 'natixis': 'ge', 'hsbc': 'ge',
    # ETI (250-4999 salariés)
    'ovhcloud': 'eti', 'ovh': 'eti', 'scaleway': 'eti', 'docaposte': 'eti',
    'devoteam': 'eti', 'sword': 'eti', 'aubay': 'eti', 'neurones': 'eti',
    'sqli': 'eti', 'inetum': 'eti', 'gfi': 'eti', 'sii': 'eti',
    'assystem': 'eti', 'akka': 'eti', 'segula': 'eti', 'expleo': 'eti',
    'berger-levrault': 'eti', 'cegid': 'eti', 'talend': 'eti',
    'murex': 'eti', 'ivalua': 'eti', 'sinequa': 'eti', 'shift technology': 'eti',
    'iqvia': 'eti', 'sagemcom': 'eti', 'efi automotive': 'eti',
    'stmicroelectronics': 'eti', 'soitec': 'eti',
    # PME (10-249 salariés)
    'dataiku': 'pme', 'mistral ai': 'pme', 'mistral': 'pme',
    'hugging face': 'pme', 'lighton': 'pme', 'nabla': 'pme',
    'deepki': 'pme', 'craft ai': 'pme', 'prevision.io': 'pme',
    'kernix': 'pme', 'sicara': 'pme', 'artefact': 'pme',
    'eleven labs': 'pme', 'cohere': 'pme', 'anthropic': 'pme',
    'labelbox': 'pme', 'weights & biases': 'pme', 'wandb': 'pme',
    'snorkel': 'pme', 'anyscale': 'pme', 'determined ai': 'pme',
    'heuritech': 'pme', 'lifen': 'pme', 'owkin': 'pme', 'incepto': 'pme',
    'preligens': 'pme', 'earthcube': 'pme',
}

# Mots-clés heuristiques dans la description
SIZE_KEYWORDS = {
    'ge': [
        'groupe international', 'multinationale', 'leader mondial',
        'leader européen', 'présent dans plus de', 'filiale du groupe',
        'fortune 500', 'fortune500', 'cac 40', 'cac40',
        'cotée en bourse', 'cotée au', 'sbf 120',
        'nos 50 000', 'nos 100 000', 'plus de 10 000',
        'plus de 5 000', '5000 collaborateurs', '10000 collaborateurs',
        'grande entreprise', 'grand groupe', 'grands comptes',
    ],
    'eti': [
        'eti', 'entreprise de taille intermédiaire',
        '250 collaborateurs', '500 collaborateurs', '1000 collaborateurs',
        '2000 collaborateurs', '3000 collaborateurs',
        'acteur majeur', 'leader national', 'leader français',
        'présent en france et', 'filiale française',
    ],
    'pme': [
        'pme', 'petite et moyenne', 'tpe/pme', 'tpe-pme',
        '50 collaborateurs', '100 collaborateurs', '200 collaborateurs',
        'équipe de 20', 'équipe de 30', 'équipe de 50',
        'nous sommes une pme',
    ],
    'tpe': [
        'startup', 'start-up', 'start up', 'jeune pousse',
        'early stage', 'seed', 'série a', 'série b',
        'lève de fonds', 'levée de fonds',
        'équipe de 5', 'équipe de 10', 'petite équipe',
        'nous sommes une startup', 'micro-entreprise', 'tpe',
        'freelance', 'indépendant',
    ],
}


def classify_company_size(company_name, description=''):
    """Détermine la taille d'entreprise (tpe/pme/eti/ge) par heuristique.

    1. Table de référence ~150 entreprises connues
    2. Mots-clés heuristiques dans la description
    3. Fallback vide si incertain
    """
    # 1. Table de référence
    if company_name:
        company_lower = company_name.lower().strip()
        # Exact match
        if company_lower in KNOWN_COMPANIES:
            return KNOWN_COMPANIES[company_lower]
        # Partial match (company name contains a known name)
        for known, size in KNOWN_COMPANIES.items():
            if known in company_lower or company_lower in known:
                return size

    # 2. Heuristique textuelle
    text_lower = f"{company_name} {description}".lower()
    scores = {}
    for size_code, keywords in SIZE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[size_code] = score

    if scores:
        return max(scores, key=scores.get)

    return ''


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
        # OPIIEC + extended skills
        'Power BI': ['power bi', 'powerbi', 'tableau', 'qlik', 'looker', 'data visualization'],
        'DevOps': ['devops', 'ci/cd', 'cicd', 'jenkins', 'gitlab ci', 'github actions'],
        'API / Microservices': ['api rest', 'microservices', 'api gateway', 'graphql', 'fastapi'],
        'Cybersecurity': ['cybersécurité', 'cyber sécurité', 'pentest', 'soc', 'siem', 'threat intelligence'],
        'Cloud': ['aws', 'azure', 'gcp', 'google cloud', 'cloud computing', 'iaas', 'paas'],
        'NoSQL': ['mongodb', 'cassandra', 'nosql', 'redis', 'elasticsearch'],
        'Java': ['java ', 'spring boot', 'jvm'],
        'Scala': ['scala', 'akka'],
        'R': [' r ', 'rstudio', 'cran', 'tidyverse', 'shiny'],
        'Git': ['git', 'github', 'gitlab', 'version control'],
        'Tableau de bord': ['dashboard', 'reporting', 'kpi', 'indicateur'],
        'IoT': ['iot', 'internet of things', 'objets connectés', 'mqtt', 'edge computing'],
        'Blockchain': ['blockchain', 'smart contract', 'web3', 'solidity'],
        'RPA': ['rpa', 'uipath', 'automation anywhere', 'blue prism', 'robotic process'],
        'Project Management': ['gestion de projet', 'project management', 'prince2', 'pmp', 'safe'],
    }
    for skill_name, keywords in skill_keywords.items():
        if any(kw in text_lower for kw in keywords):
            skills.add(skill_name)
    return list(skills)
