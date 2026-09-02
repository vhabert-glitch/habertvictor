"""
Données de référence : secteurs, types de formation, enjeux critiques.
Basé sur l'analyse des besoins IA en France.
"""

SECTORS = [
    ('sante', 'Santé'),
    ('finance', 'Finance & Assurance'),
    ('industrie', 'Industrie & Manufacturing'),
    ('retail', 'Retail & E-commerce'),
    ('education', 'Éducation & Formation'),
    ('energie', 'Énergie & Environnement'),
    ('transport', 'Transport & Logistique'),
    ('administration', 'Administration publique'),
    ('cyberdefense', 'Cyberdéfense & Défense'),
    ('autre', 'Autre'),
]

TRAINING_TYPES = [
    ('fondamentaux_ia', 'Fondamentaux de l\'IA et du Machine Learning'),
    ('data_science', 'Data Science & Analyse de données'),
    ('nlp', 'Traitement du langage naturel (NLP) & IA générative'),
    ('computer_vision', 'Vision par ordinateur'),
    ('ia_decisionnelle', 'IA décisionnelle & aide à la décision'),
    ('ethique_ia', 'Éthique de l\'IA & IA responsable'),
    ('ia_reglementaire', 'Réglementation IA (AI Act) & conformité'),
    ('deploiement_mlops', 'Déploiement & MLOps'),
    ('ia_metier', 'IA appliquée au métier (use cases sectoriels)'),
    ('management_ia', 'Management de projets IA & transformation'),
    ('innovation_digital', 'Innovation digitale & rôles IA émergents'),
]

CRITICAL_ISSUES = [
    ('competences', 'Pénurie de compétences IA'),
    ('donnees', 'Qualité et accès aux données'),
    ('ethique', 'Éthique et biais algorithmiques'),
    ('reglementation', 'Conformité réglementaire (AI Act)'),
    ('investissement', 'Coûts d\'investissement et ROI'),
    ('resistance', 'Résistance au changement'),
    ('souverainete', 'Souveraineté numérique'),
    ('cybersecurite', 'Cybersécurité liée à l\'IA'),
    ('environnement', 'Impact environnemental de l\'IA'),
    ('emploi', 'Transformation des emplois'),
]

COMPANY_SIZES = [
    ('tpe', 'TPE (< 10 salariés)'),
    ('pme', 'PME (10-249 salariés)'),
    ('eti', 'ETI (250-4999 salariés)'),
    ('ge', 'Grande entreprise (5000+ salariés)'),
]

AI_MATURITY_LEVELS = [
    ('not_started', 'Pas commencé'),
    ('exploring', 'Phase d\'exploration'),
    ('pilot', 'Projets pilotes en cours'),
    ('deployed', 'IA déployée en production'),
]

NEED_LEVELS = [
    ('none', 'Aucun'),
    ('low', 'Faible'),
    ('moderate', 'Modéré'),
    ('high', 'Élevé'),
    ('critical', 'Critique'),
]

URGENCY_LEVELS = [
    ('3months', 'Moins de 3 mois'),
    ('3_6months', '3 à 6 mois'),
    ('6_12months', '6 à 12 mois'),
    ('12months_plus', 'Plus de 12 mois'),
]

FORMAT_CHOICES = [
    ('presentiel', 'Présentiel'),
    ('distanciel', 'Distanciel'),
    ('hybride', 'Hybride'),
    ('elearning', 'E-learning'),
]

BUDGET_RANGES = [
    ('less_5k', 'Moins de 5 000 €'),
    ('5k_20k', '5 000 € - 20 000 €'),
    ('20k_50k', '20 000 € - 50 000 €'),
    ('50k_100k', '50 000 € - 100 000 €'),
    ('100k_plus', 'Plus de 100 000 €'),
    ('unknown', 'Non défini'),
]

AI_SKILLS = [
    ('python', 'Python'),
    ('r', 'R'),
    ('sql', 'SQL'),
    ('tensorflow', 'TensorFlow'),
    ('pytorch', 'PyTorch'),
    ('scikit_learn', 'Scikit-learn'),
    ('nlp_tools', 'Outils NLP (spaCy, Hugging Face)'),
    ('llm', 'LLM & Prompt Engineering'),
    ('cloud_ml', 'Cloud ML (AWS/GCP/Azure)'),
    ('mlops', 'MLOps (MLflow, Kubeflow)'),
    ('data_viz', 'Data Visualization'),
    ('statistics', 'Statistiques avancées'),
    ('deep_learning', 'Deep Learning'),
    ('computer_vision_skill', 'Computer Vision (OpenCV, YOLO)'),
    ('data_engineering', 'Data Engineering'),
    ('ai_ethics', 'Éthique de l\'IA'),
    ('ai_strategy', 'Stratégie IA'),
    ('rag', 'RAG (Retrieval Augmented Generation)'),
    ('langchain', 'LangChain & Frameworks agents'),
    ('fine_tuning', 'Fine-tuning & RLHF'),
    ('prompt_engineering', 'Prompt Engineering'),
    ('ai_governance', 'AI Governance & Conformité'),
    ('ai_safety', 'AI Safety & Alignement'),
    ('hugging_face', 'Hugging Face & Transformers'),
    ('vector_db', 'Vector Databases'),
    ('ai_agents', 'AI Agents & Systèmes autonomes'),
    ('kubernetes', 'Kubernetes & Orchestration'),
    ('terraform', 'Terraform & IaC'),
]
