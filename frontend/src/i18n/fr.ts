import { LIBRARY_FR } from './library'
import { SCREENS_FR } from './screens'

/** French. Keys are the English text (see ./index.ts). Numbers keep their decimal point, like the
 * course and the coach's facts. */
export const FR: Record<string, string> = {
  ...SCREENS_FR,
  // Shell and navigation
  Conversation: 'Conversation',
  Study: 'Étudier',
  'Your course': 'Ton cours',
  'For teachers': 'Pour les enseignants',
  'Behind the scenes': 'Dans les coulisses',
  Documents: 'Documents',
  Practice: 'Exercices',
  Coach: 'Coach',
  'Concept map': 'Carte des notions',
  Progress: 'Progrès',
  Insights: 'Observations',
  Experiments: 'Expériences',
  Agent: 'Agent',
  Memory: 'Mémoire',
  'AI collaboration': "Collaboration avec l'IA",
  'Under the hood': 'Sous le capot',
  'Class view': 'Vue de la classe',
  Settings: 'Paramètres',
  Language: 'Langue',
  'Your subjects and chapters, with answers grounded in your own course pages.':
    'Tes matières et tes chapitres, avec des réponses tirées de tes propres pages de cours.',
  'A quiz and an explain-it-back for every concept of the course.':
    'Un quiz et un « explique-le » pour chaque notion du cours.',
  'Four coaches, one set of facts. Pick the voice you like.':
    'Quatre coachs, les mêmes faits. Choisis la voix qui te plaît.',
  'What Lodestar has learned about how you study, each with its range.':
    'Ce que Lodestar a appris sur ta façon d’étudier, chaque fois avec sa marge.',
  'What Lodestar remembers about you. Forget anything, any time.':
    'Ce dont Lodestar se souvient sur toi. Efface ce que tu veux, quand tu veux.',
  'The architecture, the models, how they were tested, and the rules.':
    'L’architecture, les modèles, comment ils ont été testés, et les règles.',
  'Every concept of the course, what it builds on, and how sure Lodestar is about you.':
    'Chaque notion du cours, ce sur quoi elle repose, et à quel point Lodestar est sûr de ton niveau.',
  'Your exam goals and how each concept has moved.':
    'Tes objectifs d’examen et l’évolution de chaque notion.',
  'Test one change to how you study and see if it helps you.':
    'Teste un changement dans ta façon d’étudier et vois si ça t’aide.',
  'What Lodestar did, step by step, and why.':
    'Ce que Lodestar a fait, étape par étape, et pourquoi.',
  'How you work with AI: checking, trying first, and taking breaks.':
    'Comment tu travailles avec l’IA : vérifier, essayer d’abord, faire des pauses.',
  'The whole class, as counts: what it finds hard and the mix-ups behind it.':
    'Toute la classe, en chiffres : ce qui lui pose problème et les confusions derrière.',
  'Privacy, voice, your AI provider and your data.':
    'Confidentialité, voix, ton fournisseur d’IA et tes données.',
  'Lodestar uses the model on this server': 'Lodestar utilise le modèle de ce serveur',
  'Local mode': 'Mode local',
  "Couldn't load your data:": 'Impossible de charger tes données :',
  'Loading…': 'Chargement…',
  'Loading the course…': 'Chargement du cours…',
  'Everything is deleted': 'Tout est supprimé',
  'Lodestar keeps only a receipt with these counts, not who you were.':
    'Lodestar ne garde qu’un reçu avec ces chiffres, pas qui tu étais.',
  'Start again': 'Recommencer',

  // Concept map page
  'Ask about the course': 'Pose une question sur le cours',
  Thinking: 'Je réfléchis',
  'e.g. what is a random variable? or: what do I keep getting wrong?':
    'ex. c’est quoi une variable aléatoire ? ou : qu’est-ce que je rate tout le temps ?',
  'Your question about the course': 'Ta question sur le cours',
  Ask: 'Demander',
  'All concepts at a glance': 'Toutes les notions en un coup d’œil',
  Goals: 'Objectifs',
  'Each concept over time': 'Chaque notion dans le temps',
  'Line: estimate. Shaded: the 80% range. Dashed: the forecast for the next sessions. Orange strips: what you told Lodestar about your days.':
    'Ligne : estimation. Zone grisée : la marge à 80%. Pointillés : la prévision pour les prochaines séances. Bandes orange : ce que tu as dit à Lodestar sur tes journées.',
  'Change by week': 'Évolution par semaine',
  'When you do best': 'Quand tu réussis le mieux',
  'days to the exam': 'jours avant l’examen',
  'of {n} concepts solid': 'notions solides sur {n}',
  'not sticking yet': 'ne rentrent pas encore',
  'The gap:': 'Le trou :',
  "{concept} won't stick while {prereq}, which it builds on, is still shaky. That's where Lodestar starts.":
    '« {concept} » ne rentrera pas tant que « {prereq} », sur laquelle elle repose, reste fragile. C’est par là que Lodestar commence.',
  'Not checked yet': 'Pas encore vérifiée',
  'Gap under {names}': 'Trou sous {names}',
  Plateau: 'Plateau',
  'Review due': 'À réviser',
  '1 mix-up': '1 confusion',
  '{n} mix-ups': '{n} confusions',
  'Mastery is the chance of getting a typical question on the concept right, with its 80% range. A line means the lower concept builds on the upper one. Tap a concept for its curve, its notes and what Lodestar plans next.':
    'La maîtrise est la chance de réussir une question typique sur la notion, avec sa marge à 80%. Une ligne veut dire que la notion du bas repose sur celle du haut. Touche une notion pour voir sa courbe, ses notes et ce que Lodestar prévoit.',
  Solid: 'Solide',
  Shaky: 'Fragile',
  'Not sticking yet': 'Ne rentre pas encore',
  'Not checked': 'Pas vérifiée',

  // Home and conversation
  'Good morning': 'Bonjour',
  'Good afternoon': 'Bon après-midi',
  'Good evening': 'Bonsoir',
  "I'm Lodestar, your study coach. Bring your C++, probability or other course notes. I help you understand the ideas, check what sticks, and work through the mix-ups behind your answers.":
    'Je suis Lodestar, ton coach d’études. Apporte tes cours de C++, de probabilités ou d’autres matières. Je t’aide à comprendre les idées, à vérifier ce qui reste, et à corriger les confusions derrière tes réponses.',
  'Your week': 'Ta semaine',
  'day streak': 'jours d’affilée',
  'exercises this week': 'exercices cette semaine',
  'concepts checked': 'notions vérifiées',
  'Upload your course': 'Importe ton cours',
  'Add subjects and chapters, then learn from your own pages':
    'Ajoute des matières et des chapitres, puis apprends à partir de tes propres pages',
  'Start studying': 'Commencer à étudier',
  'The concept that needs you most, at your level':
    'La notion qui a le plus besoin de toi, à ton niveau',
  'The mix-ups behind your wrong answers, and the fix for each':
    'Les confusions derrière tes erreurs, et la correction de chacune',
  'What do I keep getting wrong?': 'Qu’est-ce que je rate tout le temps ?',
  'My mistakes': 'Mes erreurs',
  'What I keep getting wrong, and how to fix it':
    'Ce que je rate tout le temps, et comment corriger',
  'Try asking': 'Essaie de demander',
  'Talk to Lodestar': 'Parle à Lodestar',
  'Say something to Lodestar': 'Dis quelque chose à Lodestar',
  'Ask about the course, or say what you want to study':
    'Pose une question sur le cours, ou dis ce que tu veux étudier',
  'Reply to Lodestar': 'Réponds à Lodestar',
  Send: 'Envoyer',
  'Another exercise': 'Un autre exercice',
  Mood: 'Humeur',
  'How did that feel?': 'Comment ça s’est passé ?',
  Good: 'Bien',
  OK: 'Moyen',
  Tough: 'Dur',
  'I thought that one was hard for you. Was I right?':
    'Je pensais que celui-là était dur pour toi. J’avais raison ?',
  Yes: 'Oui',
  No: 'Non',
  Open: 'Ouvrir',
  'See this concept': 'Voir cette notion',
  'See every concept': 'Voir toutes les notions',
  'Open charts': 'Ouvrir les graphiques',
  'No experiments yet.': 'Pas encore d’expérience.',
  'Open the lab': 'Ouvrir le labo',
  'Your concepts': 'Tes notions',
  Lab: 'Labo',
  Offered: 'Proposé :',
  'Up next': 'Ensuite',
  'Your exercise': 'Ton exercice',
  'From {name}': 'Sur « {name} »',
  'Why this exercise': 'Pourquoi cet exercice',
  'See every option': 'Voir toutes les options',
  'Next exercise': 'Exercice suivant',
  "Let's go": 'C’est parti',
  "This exercise isn't ready in the browser yet.":
    'Cet exercice n’est pas encore prêt dans le navigateur.',
  Round: 'Exercice',
  'Not counted': 'Non compté',
  '/ {total} right': '/ {total} juste(s)',
  'likely {low}–{high}%': 'probablement {low}–{high}%',
  'your coach': 'ton coach',
  'Looking at your answers': 'Je regarde tes réponses',
  'How I worked this out': 'Comment j’ai calculé ça',
  'Session done': 'Séance terminée',
  "Nice work. Come back whenever you like; I'll pick up from here.":
    'Beau travail. Reviens quand tu veux ; je reprendrai d’ici.',
  'Start another session': 'Commencer une autre séance',
  'Welcome back': 'Bon retour',
  'You were in the middle of {name}. Resume or skip?':
    'Tu étais en plein milieu de « {name} ». Reprendre ou passer ?',
  Resume: 'Reprendre',
  Skip: 'Passer',
  'Lodestar asks': 'Lodestar demande',
  'Choosing your first exercise': 'Je choisis ton premier exercice',
  "Couldn't reach Lodestar:": 'Impossible de joindre Lodestar :',

  // Exercises
  Quiz: 'Quiz',
  'Explain it back': 'Explique-le',
  'Pick the answer you think is right, then say how sure you are. A wrong answer shows how it went wrong and how to fix it. Hints are there if you need them, but an answer found with a hint counts a little less.':
    'Choisis la réponse que tu crois juste, puis dis à quel point tu es sûr. Une mauvaise réponse montre ce qui n’a pas marché et comment corriger. Les indices sont là si tu en as besoin, mais une réponse trouvée avec un indice compte un peu moins.',
  'Click an answer or press 1 to 4.': 'Clique sur une réponse ou appuie sur 1 à 4.',
  'Explain the idea in your own words, as if to a classmate. Lodestar checks which key ideas you covered and shows you the ones you missed.':
    'Explique l’idée avec tes mots, comme à un camarade. Lodestar vérifie quelles idées clés tu as couvertes et te montre celles qui manquent.',
  'Type or say your explanation, then Done.': 'Écris ou dis ton explication, puis Terminé.',
  'Question {n} of {of}': 'Question {n} sur {of}',
  Hint: 'Indice',
  'How sure are you?': 'Tu es sûr à quel point ?',
  Guessing: 'Au hasard',
  'Fairly sure': 'Plutôt sûr',
  Sure: 'Sûr',
  'Right.': 'Juste.',
  'Not quite.': 'Pas tout à fait.',
  'A common mix-up, and you were sure:': 'Une confusion fréquente, et tu étais sûr :',
  'A common mix-up:': 'Une confusion fréquente :',
  'Notes {id}, {title}': 'Notes {id}, {title}',
  Finish: 'Terminer',
  Next: 'Suivant',
  'Explain it back: {name}': 'Explique-le : {name}',
  'Your explanation': 'Ton explication',
  'In your own words, with one example': 'Avec tes mots, et un exemple',
  'Say it': 'Dis-le',
  Done: 'Terminé',
  'You covered {got} of the {total} key ideas.': 'Tu as couvert {got} idées clés sur {total}.',
  'The ones without a tick are worth a second look: Notes {id}, {title}.':
    'Celles sans coche méritent un deuxième regard : Notes {id}, {title}.',
  Concepts: 'Notions',
  'The first {n} are practice.': 'Les {n} premiers sont pour s’entraîner.',
  'Ready. Go!': 'Prêt. C’est parti !',
  Start: 'Commencer',
  'Easier?': 'Plus facile ?',
  'That looked tough. Want it a bit easier?': 'Ça avait l’air dur. Tu veux un peu plus facile ?',
  'Yes, easier': 'Oui, plus facile',
  'Keep going': 'Continuer',
  Pause: 'Pause',
  'Too hard?': 'Trop dur ?',
  Quit: 'Quitter',

  // Practice panel
  '{n} concepts': '{n} notions',
  'to practise': 'à travailler',
  Chapter: 'Chapitre',
  All: 'Toutes',
  'Chapter 1 · Counting and events': 'Chapitre 1 · Dénombrement et événements',
  'Chapter 2 · Conditional probability': 'Chapitre 2 · Probabilité conditionnelle',
  'Chapter 3 · Random variables': 'Chapitre 3 · Variables aléatoires',
  'Chapter 4 · Continuous distributions': 'Chapitre 4 · Lois continues',
  Other: 'Autre',

  // Coach cards
  'Advanced track': 'Parcours avancé',
  'Foundation track': 'Parcours des bases',
  'New format': 'Nouveau format',
  'level {n}/10': 'niveau {n}/10',
  'stays at {value}%, range {low}-{high}% →': 'reste à {value}%, marge {low}-{high}% →',
  'Round not counted': 'Exercice non compté',
  'Round flagged': 'Exercice signalé',
  "That round didn't count": 'Cet exercice n’a pas compté',
  "Those answers came too fast to tell me anything about you, so I'm not treating it as a drop in skill.":
    'Ces réponses sont arrivées trop vite pour m’apprendre quoi que ce soit sur toi, donc je ne le compte pas comme une baisse de niveau.',
  'typical answer': 'réponse typique',
  right: 'justes',
  'points of change to your estimate': 'points de changement sur ton estimation',
  "Instead, I'm less sure about you for now:":
    'À la place, je suis moins sûr de ton niveau pour l’instant :',
  'What happened?': 'Qu’est-ce qui s’est passé ?',
  'I was rushing': 'J’étais pressé',
  'I got distracted': 'J’ai été distrait',
  'I was just trying it out': 'Je testais juste',
  'Thanks, noted. Take a breath; the next one can count.':
    'Merci, c’est noté. Respire ; le prochain pourra compter.',
  'Back to Lodestar': 'Retour à Lodestar',
  'Plateau spotted': 'Plateau repéré',
  'has stayed near {value}% (likely {low}-{high}%) for {days} days of practice.':
    'est restée vers {value}% (probablement {low}-{high}%) pendant {days} jours d’entraînement.',
  'Next, try a new format: {name}.': 'Ensuite, essaie un nouveau format : {name}.',
  'Try a new format': 'Essayer un nouveau format',
  'See the curve': 'Voir la courbe',
  Dismiss: 'Fermer',
  'Not now': 'Pas maintenant',
  'Plateau · {days} days': 'Plateau · {days} jours',
  "Your estimate has stayed near {value}% (likely {low}-{high}%) over {answers} answers. More of the same probably won't move it, so I'll change things.":
    'Ton estimation est restée vers {value}% (probablement {low}-{high}%) sur {answers} réponses. Faire plus de la même chose ne la fera sans doute pas bouger, donc je change d’approche.',
  'New format:': 'Nouveau format :',
  ', from the same family of skills.': ', de la même famille de notions.',
  'New approach:': 'Nouvelle approche :',
  'Split profile · {gap} points apart': 'Profil partagé · {gap} points d’écart',
  "These two concepts are far apart, so I don't use one difficulty for both. Exercises take turns between two tracks.":
    'Ces deux notions sont très éloignées, donc je n’utilise pas une seule difficulté pour les deux. Les exercices alternent entre deux parcours.',
  '{value}%, likely {low}-{high}%': '{value}%, probablement {low}-{high}%',
  'Level {n} of 10': 'Niveau {n} sur 10',
  ', aiming for {p}% right': ', avec un objectif de {p}% de réussite',
  'Next up: {name}': 'Ensuite : {name}',
  'Play this plan': 'Suivre ce plan',
  'Course sources': 'Sources du cours',
  'page {n}': 'page {n}',
  'From your course pages': 'D’après tes pages de cours',
  'From your notes': 'D’après tes notes',
  'Where you are:': 'Où tu en es :',
  '{value}% (likely {low}-{high}%)': '{value}% (probablement {low}-{high}%)',
  'Your usual mix-up ({count} times):': 'Ta confusion habituelle ({count} fois) :',
  'Builds on {name}': 'Repose sur « {name} »',
  ', which I haven’t checked yet.': ', que je n’ai pas encore vérifiée.',
  ', still shaky: {now}% (likely {low}-{high}%). Notes {section}.':
    ', encore fragile : {now}% (probablement {low}-{high}%). Notes {section}.',
  'The mix-ups behind your wrong answers': 'Les confusions derrière tes erreurs',
  '{n} times': '{n} fois',
  '{n} while sure': '{n} en étant sûr',
  'The data behind my pick': 'Les données derrière mon choix',
  'See every option I weighed': 'Voir toutes les options que j’ai pesées',
  'Your history': 'Ton historique',
  'not counted': 'non compté',
  '{n}% right': '{n}% juste',
  'Why?': 'Pourquoi ?',
  'A range, not a promise': 'Une marge, pas une promesse',
  'If you keep your current pace ({n} more sessions). No single number: every forecast is an 80% range.':
    'Si tu gardes ton rythme actuel ({n} séances de plus). Pas de chiffre unique : chaque prévision est une marge à 80%.',
  'Today {low}-{high}%': 'Aujourd’hui {low}-{high}%',
  'Ranges like these held {n}% of the time on real learners the model never saw.':
    'Des marges comme celles-ci ont tenu {n}% du temps sur de vrais apprenants que le modèle n’avait jamais vus.',
  'Pushback accepted': 'Contestation acceptée',
  'AI Collaboration Score': 'Score de collaboration avec l’IA',
  '(likely {low}-{high}). Critical verification and iteration both went up.':
    '(probablement {low}-{high}). La vérification critique et l’itération ont toutes deux augmenté.',

  // Class view
  'Loading the class…': 'Chargement de la classe…',
  'The class': 'La classe',
  students: 'étudiants',
  'studied this week': 'ont étudié cette semaine',
  'gone quiet': 'ne donnent plus de nouvelles',
  'What to revisit in class': 'À revoir en cours',
  'Where the class is, concept by concept': 'Où en est la classe, notion par notion',
  Concept: 'Notion',
  'Median mastery': 'Maîtrise médiane',
  'Not sticking': 'Ne rentre pas',
  '{n} of {total}': '{n} sur {total}',
  'Mix-ups': 'Confusions',
  'The mix-ups behind wrong answers': 'Les confusions derrière les erreurs',
  '{n} students': '{n} étudiants',
  '{n} answers': '{n} réponses',
  '{n}% while sure': '{n}% en étant sûr',
  "Counts only: no names and no single student's answers. In a school deployment this page is for the course's teachers.":
    'Uniquement des chiffres : aucun nom et aucune réponse individuelle. Dans un établissement, cette page est réservée aux enseignants du cours.',

  // Onboarding and demo
  'Opening the demo…': 'Ouverture de la démo…',
  'Look around as Alex, a demo person': 'Visiter en tant qu’Alex, un profil de démo',
  'Demo person': 'Profil de démo',
  'Showing Alex, a demo person. Switch off for your own data.':
    'Tu vois Alex, un profil de démo. Désactive pour retrouver tes données.',
  'Show a demo person': 'Afficher un profil de démo',
  'Demo: Alex': 'Démo : Alex',
  "Couldn't reach Lodestar. Try again in a moment.":
    'Impossible de joindre Lodestar. Réessaie dans un instant.',
  'Welcome to Lodestar': 'Bienvenue sur Lodestar',
  "Lodestar is a study coach for your course. It finds which concepts aren't sticking and why, explains them from your notes, quizzes you at the right level, and explains every choice it makes.":
    'Lodestar est un coach d’études pour ton cours. Il trouve quelles notions ne rentrent pas et pourquoi, te les explique à partir de tes notes, t’interroge au bon niveau, et justifie chacun de ses choix.',
  'Lodestar measures what you know about the course, nothing else. It never labels you, and every number comes with how sure it is.':
    'Lodestar mesure ce que tu sais du cours, rien d’autre. Il ne te colle jamais d’étiquette, et chaque chiffre vient avec son degré de certitude.',
  'Get started': 'Commencer',
  'How old are you?': 'Quel âge as-tu ?',
  'This prototype is for people aged {n} and over.':
    'Ce prototype est pour les personnes de {n} ans et plus.',
  "I'm {n} or older": 'J’ai {n} ans ou plus',
  "I'm younger": 'Je suis plus jeune',
  'Not yet, sorry': 'Pas encore, désolé',
  "Lodestar needs a parent or guardian's consent for younger people, and this prototype can't ask for it yet. Nothing about you has been stored.":
    'Lodestar a besoin de l’accord d’un parent ou d’un tuteur pour les plus jeunes, et ce prototype ne sait pas encore le demander. Rien sur toi n’a été enregistré.',
  'What Lodestar may do': 'Ce que Lodestar peut faire',
  'You can change these later in Settings.': 'Tu pourras changer ça plus tard dans les Paramètres.',
  '(needed)': '(nécessaire)',
  Details: 'Détails',
  Continue: 'Continuer',
  'Pick a coach': 'Choisis un coach',
  'They all say the same facts, in their own way.':
    'Ils disent tous les mêmes faits, chacun à sa façon.',
  "Let's start": 'C’est parti',
  'A calm mentor': 'Un mentor calme',
  'Steady work today. One step at a time.':
    'Du bon travail régulier aujourd’hui. Un pas après l’autre.',
  'An energetic trainer': 'Un entraîneur énergique',
  'Faster than last time! Ready for the next one?':
    'Plus rapide que la dernière fois ! Prêt pour le suivant ?',
  'A factual analyst': 'Un analyste factuel',
  'Estimate up, range narrower. That is the update.':
    'Estimation en hausse, marge plus étroite. Voilà le point.',
  'A casual friend': 'Un pote décontracté',
  'Nice one. Another?': 'Bien joué. Un autre ?',

  // Settings and consent
  Privacy: 'Confidentialité',
  Voice: 'Voix',
  'AI provider': 'Fournisseur d’IA',
  'Memory & data': 'Mémoire et données',
  Terminal: 'Terminal',
  'The interface and the coach. In Derja, the course itself stays in French, the way it is taught in Tunisia.':
    'L’interface et le coach. En derja, le cours lui-même reste en français, comme il est enseigné en Tunisie.',
  'Core practice data': 'Données d’entraînement de base',
  'Your results and profile, kept on this server.':
    'Tes résultats et ton profil, gardés sur ce serveur.',
  "Your game results, your skill profile and the notes Lodestar keeps about you, stored on this server. Lodestar can't work without it. To stop it, delete your data.":
    'Tes résultats d’exercices, ton profil de notions et les notes que Lodestar garde sur toi, stockés sur ce serveur. Lodestar ne peut pas fonctionner sans. Pour arrêter, supprime tes données.',
  'Cloud AI': 'IA dans le cloud',
  'Send short summaries to your own AI provider.':
    'Envoyer de courts résumés à ton propre fournisseur d’IA.',
  'Lets Lodestar send short, de-identified summaries (no name, no raw answers) to the AI provider you pick, with your own key. The provider and where it processes data are shown before you turn this on. Off means Lodestar uses the local model on this server.':
    'Permet à Lodestar d’envoyer de courts résumés anonymisés (sans nom, sans réponses brutes) au fournisseur d’IA que tu choisis, avec ta propre clé. Le fournisseur et le lieu où il traite les données sont affichés avant que tu l’actives. Désactivé, Lodestar utilise le modèle local de ce serveur.',
  Microphone: 'Micro',
  'Talk to Lodestar instead of typing.': 'Parler à Lodestar au lieu d’écrire.',
  "Voice commands. Your browser's speech recognition may send the audio to its maker (for Chrome, Google). Audio is not kept.":
    'Commandes vocales. La reconnaissance vocale de ton navigateur peut envoyer l’audio à son éditeur (pour Chrome, Google). L’audio n’est pas conservé.',
  'Voice tone': 'Ton de la voix',
  'Hear when you might need a break.': 'Entendre quand tu as peut-être besoin d’une pause.',
  'Speaking speed and pauses, worked out on this device, to suggest a break. Never changes your profile or scores.':
    'La vitesse de parole et les pauses, calculées sur cet appareil, pour proposer une pause. Ne change jamais ton profil ni tes scores.',
  'Research export': 'Export pour la recherche',
  'Share anonymised results with the team.': 'Partager des résultats anonymisés avec l’équipe.',
  'Lets the team include your anonymised results in its evaluation of Lodestar.':
    'Permet à l’équipe d’inclure tes résultats anonymisés dans son évaluation de Lodestar.',

  // The student's own material (dashboard/OwnMaterial.tsx)
  'The concept map is drawn from a course with its concepts and prerequisites. You study from your own documents, so ask about them or take a quiz made from their pages.':
    'La carte des notions se dessine à partir d’un cours avec ses notions et ses prérequis. Tu étudies à partir de tes propres documents : pose des questions dessus ou fais un quiz tiré de leurs pages.',
  'Your practice comes from your own documents: every question is made from one of your pages and cites it.':
    'Tes exercices viennent de tes propres documents : chaque question est tirée d’une de tes pages et la cite.',
  'The class view counts a whole class on the same course. Your account studies its own documents, so there is no class to show yet.':
    'La vue de la classe compte toute une classe sur le même cours. Ton compte étudie ses propres documents, il n’y a donc pas encore de classe à afficher.',
  'Quiz me on my notes': 'Interroge-moi sur mes notes',
  'Open Documents': 'Ouvrir Documents',
  'A quiz made from your own pages': 'Un quiz tiré de tes propres pages',
  ...LIBRARY_FR,
}
