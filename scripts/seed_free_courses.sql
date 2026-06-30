-- Cours gratuits à ajouter au catalogue EmploiCentral (training_courses).
-- Idempotent : n'insère une ligne que si son URL n'existe pas déjà.
-- À exécuter sur la base Neon de production.

INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Kaggle Learn', 'Python (les bases pour la data)', 'Cours interactif gratuit : apprendre Python pas à pas, orienté analyse de données.', 'Data / IA', 'Débutant', '~5 h', NULL, true, 'En ligne', 'En ligne', 'https://www.kaggle.com/learn/python', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.kaggle.com/learn/python');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Kaggle Learn', 'Introduction au Machine Learning', 'Construire et évaluer ses premiers modèles de machine learning, en pratique.', 'Data / IA', 'Intermédiaire', '~3 h', NULL, true, 'En ligne', 'En ligne', 'https://www.kaggle.com/learn/intro-to-machine-learning', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.kaggle.com/learn/intro-to-machine-learning');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Kaggle Learn', 'Introduction au SQL', 'Interroger des bases de données avec SQL, exercices guidés gratuits.', 'Data / IA', 'Débutant', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://www.kaggle.com/learn/intro-to-sql', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.kaggle.com/learn/intro-to-sql');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Kaggle Learn', 'Pandas (manipulation de données)', 'Nettoyer et transformer des données avec la bibliothèque Pandas.', 'Data / IA', 'Intermédiaire', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://www.kaggle.com/learn/pandas', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.kaggle.com/learn/pandas');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'freeCodeCamp', 'Responsive Web Design (HTML & CSS)', 'Certification gratuite : créer des pages web modernes et adaptatives.', 'Développement web', 'Débutant', '~30 h', NULL, true, 'En ligne', 'En ligne', 'https://www.freecodecamp.org/learn/2022/responsive-web-design/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.freecodecamp.org/learn/2022/responsive-web-design/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'freeCodeCamp', 'JavaScript — Algorithmes et structures de données', 'Maîtriser JavaScript et les fondamentaux de la programmation.', 'Développement web', 'Intermédiaire', '~40 h', NULL, true, 'En ligne', 'En ligne', 'https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'W3Schools', 'Apprendre Python', 'Tutoriel complet et gratuit du langage Python, avec exercices.', 'Développement web', 'Débutant', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://www.w3schools.com/python/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.w3schools.com/python/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'W3Schools', 'Apprendre le SQL', 'Les bases du SQL pour interroger et gérer des bases de données.', 'Data / IA', 'Débutant', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://www.w3schools.com/sql/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.w3schools.com/sql/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'W3Schools', 'Apprendre le HTML', 'Le langage de structure des pages web, du débutant à l''avancé.', 'Développement web', 'Débutant', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://www.w3schools.com/html/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.w3schools.com/html/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'W3Schools', 'Maîtriser Excel', 'Tutoriel Excel gratuit : formules, fonctions et tableaux.', 'Bureautique', 'Débutant', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://www.w3schools.com/excel/index.php', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.w3schools.com/excel/index.php');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'HubSpot Academy', 'Marketing digital', 'Certification gratuite couvrant les fondamentaux du marketing en ligne.', 'Marketing digital', 'Débutant', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://academy.hubspot.com/courses/digital-marketing', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://academy.hubspot.com/courses/digital-marketing');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'HubSpot Academy', 'Marketing de contenu', 'Créer une stratégie de contenu efficace, certification gratuite.', 'Marketing digital', 'Intermédiaire', '~6 h', NULL, true, 'En ligne', 'En ligne', 'https://academy.hubspot.com/courses/content-marketing', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://academy.hubspot.com/courses/content-marketing');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'HubSpot Academy', 'Marketing des réseaux sociaux', 'Développer sa présence sur les réseaux sociaux, certifiant et gratuit.', 'Marketing digital', 'Débutant', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://academy.hubspot.com/courses/social-media', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://academy.hubspot.com/courses/social-media');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Cisco Networking Academy', 'Python Essentials 1', 'Introduction gratuite à la programmation Python, certifiante.', 'Développement web', 'Débutant', '~30 h', NULL, true, 'En ligne', 'En ligne', 'https://www.netacad.com/courses/python-essentials-1', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.netacad.com/courses/python-essentials-1');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'Cisco Networking Academy', 'Introduction à la cybersécurité', 'Comprendre les menaces et les bases de la cybersécurité, gratuit.', 'Cybersécurité', 'Débutant', '~15 h', NULL, true, 'En ligne', 'En ligne', 'https://www.netacad.com/courses/cybersecurity/introduction-cybersecurity', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.netacad.com/courses/cybersecurity/introduction-cybersecurity');
