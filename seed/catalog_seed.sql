-- Dynasty Archives — catalog seed (dynasties, rulers, reigns, territories, events, links)
-- Apply sql/schema.sql first. BCE dates use PostgreSQL '... BC'::date literals.
-- Usage: psql -h HOST -U USER -d DATABASE -f seed/catalog_seed.sql
--
-- image_url values are web paths served from repo `images/` as /images/<path>.
-- Expected assets: images/dynasty.jpg; images/dyansties/*; images/persons/*;
-- images/events/*; images/territories/* (see seed/README.md).

BEGIN;

-- ============================================================
-- DYNASTIES
-- ============================================================
INSERT INTO Dynasty (name, start_year, end_year, description, image_url) VALUES
('Roman Empire',        27,   476,  'The dominant power of the ancient Mediterranean world, ruling from Rome across Europe, North Africa, and the Middle East.', '/images/dynasty.jpg'),
('Ottoman Empire',      1299, 1922, 'One of the longest-lasting empires, spanning three continents and ruling over a diverse population for over six centuries.', '/images/dyansties/ottoman_empire.jpg'),
('Mongol Empire',       1206, 1368, 'The largest contiguous land empire in history, founded by Genghis Khan and stretching from the Pacific to Eastern Europe.', '/images/dyansties/mongol_empire.png'),
('Byzantine Empire',    330,  1453, 'The eastern continuation of the Roman Empire, centered at Constantinople, preserving Greco-Roman culture for a thousand years.', '/images/dyansties/byzantine_empire.png'),
('Abbasid Caliphate',   750,  1258, 'The third caliphate to succeed the Prophet Muhammad, presiding over the Islamic Golden Age of science, culture, and trade.', '/images/dyansties/abbasid_caliphate.jpg');

-- ============================================================
-- PERSONS (RULERS)
-- ============================================================
INSERT INTO Person (full_name, birth_date, death_date, biography, dynasty_id, image_url) VALUES
('Augustus Caesar',          DATE '0063-09-23 BC', DATE '0014-08-19', 'The first Roman Emperor, born Gaius Octavius. He transformed Rome from a republic into an empire and presided over a golden age of peace known as the Pax Romana.', 1, '/images/persons/augustus_caesar.jpg'),
('Julius Caesar',            DATE '0100-07-12 BC', DATE '0044-03-15 BC', 'Roman general and statesman who played a critical role in the demise of the Roman Republic. Assassinated on the Ides of March by senators fearing his ambition.', 1, '/images/persons/julius_caesar.jpg'),
('Nero',                     DATE '0037-12-15', DATE '0068-06-09', 'Infamous Roman Emperor known for his tyranny, artistic pretensions, and alleged role in the Great Fire of Rome in 64 AD.', 1, '/images/persons/nero.jpg'),
('Suleiman the Magnificent', DATE '1494-11-06', DATE '1566-09-06', 'The longest-reigning sultan of the Ottoman Empire. Under his rule the empire reached its apex of power, wealth, and cultural influence.', 2, '/images/persons/suleiman_the_magnificent.jpg'),
('Mehmed II',                DATE '1432-03-30', DATE '1481-05-03', 'Known as the Conqueror, he captured Constantinople in 1453 ending the Byzantine Empire and transforming the city into the Ottoman capital.', 2, '/images/persons/mehmed_ii.jpg'),
('Genghis Khan',             DATE '1162-04-16', DATE '1227-08-18', 'Born Temujin, he united the Mongol tribes and founded the Mongol Empire, conquering vast swaths of Asia and Eastern Europe through brilliant military strategy.', 3, '/images/persons/genghis_khan.jpg'),
('Kublai Khan',              DATE '1215-09-23', DATE '1294-02-18', 'Grandson of Genghis Khan, he completed the conquest of China, founded the Yuan dynasty, and was the first non-Chinese ruler to conquer all of China.', 3, '/images/persons/kublai_khan.jpg'),
('Justinian I',              DATE '0482-05-11', DATE '0565-11-14', 'Byzantine Emperor who nearly reconquered the western Roman Empire. Commissioned the Hagia Sophia and codified Roman law in the Corpus Juris Civilis.', 4, '/images/persons/justinian_i.jpg'),
('Theodora',                 DATE '0497-01-01', DATE '0548-06-28', 'Empress consort of Justinian I and one of the most powerful women in Byzantine history, she co-ruled the empire and championed the rights of women.', 4, '/images/persons/theodora.jpg'),
('Harun al-Rashid',          DATE '0763-03-17', DATE '0809-03-24', 'Abbasid Caliph during whose reign the Islamic Golden Age reached its peak. His court in Baghdad was the most sophisticated in the world, immortalized in One Thousand and One Nights.', 5, '/images/persons/harun_al_rashid.jpg');

-- ============================================================
-- REIGNS
-- ============================================================
INSERT INTO Reign (person_id, title, capital, start_date, end_date) VALUES
(1,  'Emperor',   'Rome',           DATE '0027-01-16 BC', DATE '0014-08-19'),
(2,  'Dictator',  'Rome',           DATE '0049-01-01 BC', DATE '0044-03-15 BC'),
(3,  'Emperor',   'Rome',           DATE '0054-10-13', DATE '0068-06-09'),
(4,  'Sultan',    'Constantinople', DATE '1520-09-30', DATE '1566-09-06'),
(5,  'Sultan',    'Edirne',         DATE '1444-08-01', DATE '1446-09-01'),
(5,  'Sultan',    'Constantinople', DATE '1451-02-18', DATE '1481-05-03'),
(6,  'Great Khan','Karakorum',      DATE '1206-03-01', DATE '1227-08-18'),
(7,  'Great Khan','Khanbaliq',      DATE '1260-05-05', DATE '1294-02-18'),
(8,  'Emperor',   'Constantinople', DATE '0527-08-01', DATE '0565-11-14'),
(9,  'Empress',   'Constantinople', DATE '0527-08-01', DATE '0548-06-28'),
(10, 'Caliph',    'Baghdad',        DATE '0786-09-14', DATE '0809-03-24');

-- ============================================================
-- TERRITORIES
-- ============================================================
INSERT INTO Territory (name, region, modern_name, description, image_url) VALUES
('Anatolia',          'Middle East',  'Turkey',               'The peninsula bridging Europe and Asia, controlled by multiple empires throughout history.', '/images/territories/anatolia.jpg'),
('Mesopotamia',       'Middle East',  'Iraq',                 'The land between the Tigris and Euphrates rivers, cradle of civilization.', '/images/territories/mesopotamia.jpg'),
('Gaul',              'Europe',       'France/Belgium',       'Roman province covering modern France, Belgium, and parts of Switzerland.', '/images/territories/gaul.jpg'),
('Egypt',             'Africa',       'Egypt',                'Ancient land of the Nile, prized for its agricultural wealth and strategic position.', '/images/territories/egypt.jpg'),
('Persia',            'Middle East',  'Iran',                 'Ancient heartland of successive Persian empires, rich in culture and resources.', '/images/territories/persia.jpg'),
('Balkans',           'Europe',       'Southeast Europe',     'The southeastern European peninsula, contested by Rome, Byzantium, and the Ottomans.', '/images/territories/balkans.jpg'),
('Central Asia',      'Asia',         'Kazakhstan/Uzbekistan','The vast steppe heartland of the Mongol Empire and homeland of nomadic peoples.', '/images/territories/central_asia.jpg'),
('North Africa',      'Africa',       'Libya/Tunisia/Algeria','The fertile coastal strip of North Africa bordering the Mediterranean.', '/images/territories/north_africa.jpg'),
('Syria-Palestine',   'Middle East',  'Syria/Israel/Jordan',  'The Levantine corridor connecting Africa, Asia, and Europe.', '/images/territories/syria_palestine.jpg'),
('Constantinople',    'Europe',       'Istanbul, Turkey',     'The greatest city of the medieval world, capital of both Byzantine and Ottoman empires.', '/images/territories/constantinople.png');

-- ============================================================
-- DYNASTY TERRITORIES
-- ============================================================
INSERT INTO Dynasty_Territory (dynasty_id, territory_id, start_year, end_year) VALUES
(1, 3,   50,   410),
(1, 4,   30,   395),
(1, 8,   30,   430),
(1, 6,   146,  395),
(2, 1,   1299, 1922),
(2, 6,   1453, 1878),
(2, 9,   1516, 1918),
(2, 4,   1517, 1798),
(3, 7,   1206, 1368),
(3, 2,   1258, 1335),
(3, 5,   1220, 1370),
(4, 1,   330,  1453),
(4, 6,   330,  1453),
(4, 10,  330,  1453),
(5, 2,   750,  1258),
(5, 5,   750,  1258),
(5, 9,   750,  1258);

-- ============================================================
-- EVENTS
-- ============================================================
INSERT INTO Event (name, type, event_date, end_date, location, description, dynasty_id, image_url) VALUES
('Battle of Actium',              'battle',           DATE '0031-09-02 BC', NULL,                 'Actium, Greece',        'Naval battle where Octavian defeated Mark Antony and Cleopatra, establishing his supremacy over Rome.',                              1, '/images/events/battle_of_actium.jpg'),
('Assassination of Julius Caesar','death',            DATE '0044-03-15 BC', NULL,                 'Rome, Italy',           'Julius Caesar was stabbed 23 times by a group of senators led by Brutus and Cassius in the Theatre of Pompey.',                    1, '/images/events/assassination_of_julius_caesar.jpg'),
('Great Fire of Rome',            'natural_disaster', DATE '0064-07-18', DATE '0064-07-25', 'Rome, Italy',           'A great fire broke out destroying large portions of Rome. Emperor Nero was controversially blamed for starting it.',                 1, '/images/events/great_fire_of_rome.jpg'),
('Fall of Constantinople',        'battle',           DATE '1453-05-29', NULL,                 'Constantinople',        'Mehmed II leads the Ottoman army to breach the walls of Constantinople after a 53-day siege, ending the Byzantine Empire.',         2, '/images/events/fall_of_constantinople.jpg'),
('Battle of Mohacs',              'battle',           DATE '1526-08-29', NULL,                 'Mohacs, Hungary',       'Suleiman the Magnificent defeats the Kingdom of Hungary, opening Central Europe to Ottoman expansion.',                             2, '/images/events/battle_of_mohacs.jpg'),
('Mongol Invasion of Persia',     'war',              DATE '1219-01-01', DATE '1221-12-31', 'Persia',                'Genghis Khan leads a devastating campaign against the Khwarazmian Empire, destroying major cities including Samarkand and Bukhara.', 3, '/images/events/mongol_invasion_of_persia.jpg'),
('Battle of Ain Jalut',           'battle',           DATE '1260-09-03', NULL,                 'Ain Jalut, Palestine',  'The Mamluks of Egypt halt the Mongol advance into Africa, marking the first major defeat of the Mongol army.',                      3, '/images/events/battle_of_ain_jalut.jpg'),
('Nika Riots',                    'political',        DATE '0532-01-13', DATE '0532-01-18', 'Constantinople',        'A massive revolt against Emperor Justinian I that nearly toppled his rule. Empress Theodora famously urged him to stand firm.',     4, '/images/events/nika_riots.jpg'),
('Construction of Hagia Sophia', 'political',        DATE '0532-02-23', DATE '0537-12-27', 'Constantinople',        'Justinian I commissioned the great cathedral of Hagia Sophia, completed in just five years, a marvel of Byzantine architecture.',  4, '/images/events/construction_of_hagia_sophia.jpg'),
('House of Wisdom Founded',       'political',        DATE '0830-01-01', NULL,                 'Baghdad, Iraq',         'Harun al-Rashid established the House of Wisdom in Baghdad, the greatest center of learning in the medieval world.',               5, '/images/events/house_of_wisdom_founded.jpg');

-- ============================================================
-- PERSON EVENTS
-- ============================================================
INSERT INTO Person_Event (person_id, event_id, role) VALUES
(1,  1,  'Commander'),
(2,  2,  'Victim'),
(3,  3,  'Emperor'),
(5,  4,  'Commander'),
(4,  5,  'Commander'),
(6,  6,  'Commander'),
(8,  8,  'Emperor'),
(9,  8,  'Empress'),
(8,  9,  'Commissioner'),
(10, 10, 'Caliph');

-- ============================================================
-- SUCCESSIONS
-- ============================================================
INSERT INTO Succession (predecessor_id, successor_id, type, year, notes) VALUES
(2,  1,  'conquest',    44,   'After Caesar''s assassination Augustus eventually emerged as sole ruler following years of civil war.'),
(1,  3,  'normal',      14,   'Augustus was succeeded after a chain of emperors; Nero came to power through Claudius.'),
(5,  4,  'normal',      1451, 'Mehmed II''s first reign ended; he returned to power after his father Murad II died.'),
(6,  7,  'normal',      1227, 'Kublai Khan eventually became Great Khan after a succession struggle following Genghis Khan''s death.'),
(8,  9,  'normal',      527,  'Justinian and Theodora co-ruled jointly from the start of his reign.');

-- ============================================================
-- PARENT CHILD
-- ============================================================
INSERT INTO Parent_Child (parent_id, child_id) VALUES
(6, 7),
(2, 1),
(8, 9);

COMMIT;
