-- Cours gratuits (vague 3, 2026-10-19) — actualisation du catalogue EmploiCentral.
-- 1) Désactive les cours FUN-MOOC dont aucune session n'est plus ouverte (dernière
--    clôture des inscriptions entre 2016 et juillet 2026 d'après les données de la page).
--    is_active=false plutôt que DELETE : réversible, et l'historique des déblocages reste cohérent.
-- 2) Ajoute des remplaçants vérifiés (titre de page confirmé, accès libre, sans date de fin
--    pour OpenClassrooms / British Council ; inscriptions ouvertes jusqu'en 2027 pour FUN-MOOC).
-- Idempotent : rejouable sans risque. À exécuter sur la base Neon de production
-- (endpoint ep-long-leaf-as2k2n73, voir le piège de branche Neon).

UPDATE training_courses SET is_active = false
WHERE is_active = true AND url IN (
  'https://www.fun-mooc.fr/en/cours/la-compta-pour-tous/',
  'https://www.fun-mooc.fr/en/cours/lanalyse-financiere-pour-tous/',
  'https://www.fun-mooc.fr/en/cours/createur-dune-micro-entreprise/',
  'https://www.fun-mooc.fr/en/cours/entrepreneuriat-et-croissance-attitude/',
  'https://www.fun-mooc.fr/en/cours/langlais-pour-tous-spice-up-your-english/',
  'https://www.fun-mooc.fr/en/cours/conduite-de-reunion-en-anglais/',
  'https://www.fun-mooc.fr/en/cours/risques-psychosociaux/'
);

INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'OpenClassrooms', 'Initiez-vous à la comptabilité', 'Les fondamentaux de la comptabilité : bilan, compte de résultat et premières écritures, sans prérequis.', 'Gestion & business', 'Débutant', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://openclassrooms.com/fr/courses/4801106-initiez-vous-a-la-comptabilite', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://openclassrooms.com/fr/courses/4801106-initiez-vous-a-la-comptabilite');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'OpenClassrooms', 'Pilotez la performance financière de l''entreprise', 'Analyser le bilan et le compte de résultat, puis construire un tableau de bord financier pour piloter l''activité.', 'Gestion & business', 'Intermédiaire', '~4 h', NULL, true, 'En ligne', 'En ligne', 'https://openclassrooms.com/fr/courses/8971306-pilotez-la-performance-financiere-de-l-entreprise', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://openclassrooms.com/fr/courses/8971306-pilotez-la-performance-financiere-de-l-entreprise');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'OpenClassrooms', 'Gérez votre trésorerie', 'Tableau de cash-flow, plan et prévision de trésorerie pour sécuriser la santé financière d''une entreprise.', 'Gestion & business', 'Intermédiaire', '~10 h', NULL, true, 'En ligne', 'En ligne', 'https://openclassrooms.com/fr/courses/5149176-gerez-votre-tresorerie', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://openclassrooms.com/fr/courses/5149176-gerez-votre-tresorerie');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'OpenClassrooms', 'Construisez un business plan', 'Préparer le business plan de son projet et bâtir les projections financières qui l''accompagnent.', 'Gestion & business', 'Débutant', '~10 h', NULL, true, 'En ligne', 'En ligne', 'https://openclassrooms.com/fr/courses/5191546-construisez-un-business-plan', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://openclassrooms.com/fr/courses/5191546-construisez-un-business-plan');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'OpenClassrooms', 'Gérez votre comptabilité d''indépendant', 'Obligations fiscales, facturation et gestion de trésorerie pour freelances et micro-entrepreneurs.', 'Gestion & business', 'Débutant', '~10 h', NULL, true, 'En ligne', 'En ligne', 'https://openclassrooms.com/fr/courses/5185316-gerez-votre-comptabilite-d-independant', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://openclassrooms.com/fr/courses/5185316-gerez-votre-comptabilite-d-independant');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'FUN-MOOC (Cnam)', 'Jouez l''innovation', 'Comprendre et pratiquer l''innovation en entreprise par le jeu et les mises en situation.', 'Gestion & business', 'Débutant', '~7 h', NULL, true, 'En ligne', 'En ligne', 'https://www.fun-mooc.fr/fr/cours/jouez-linnovation/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.fun-mooc.fr/fr/cours/jouez-linnovation/');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'British Council — LearnEnglish', 'Business English', 'Ressources gratuites d''anglais professionnel : e-mails, réunions, podcasts et série vidéo sur la recherche d''emploi.', 'Anglais & soft skills', 'Intermédiaire', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://learnenglish.britishcouncil.org/business-english', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://learnenglish.britishcouncil.org/business-english');
INSERT INTO training_courses (partner_name, title, description, domain, level, duration, price, is_free, format, location, url, is_active)
SELECT 'FUN-MOOC (IMT)', 'Les essentiels de la cybersécurité : du risque à la résilience', 'Identifier les risques numériques, adopter les bons réflexes et comprendre comment une organisation devient résiliente.', 'Cybersécurité', 'Débutant', 'Libre', NULL, true, 'En ligne', 'En ligne', 'https://www.fun-mooc.fr/fr/cours/les-essentiels-de-la-cybersecurite-du-risque-a-la-resilience/', true
WHERE NOT EXISTS (SELECT 1 FROM training_courses WHERE url = 'https://www.fun-mooc.fr/fr/cours/les-essentiels-de-la-cybersecurite-du-risque-a-la-resilience/');
