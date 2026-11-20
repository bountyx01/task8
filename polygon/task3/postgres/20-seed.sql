INSERT INTO sectors (name, industry, description) VALUES
    ('Nord Oil',     'нефтегаз',    'Добыча и транспортировка нефти'),
    ('City F',       'город',       'Городская инфраструктура и ЖКХ'),
    ('Cloud F',      'IT',          'Облачный провайдер и госуслуги'),
    ('SteelWorks F', 'металлургия', 'Металлургический комбинат');

INSERT INTO hosts (sector_id, hostname, ip, os, is_critical) VALUES
    (1, 'scada-01.oil.f',      '10.10.1.10', 'Windows Server 2019', true),
    (1, 'hmi-02.oil.f',        '10.10.1.11', 'Windows 10',          false),
    (1, 'mail.oil.f',          '10.10.1.25', 'Ubuntu 22.04',        false),
    (2, 'traffic-ctl.city.f',  '10.20.1.10', 'Debian 12',           true),
    (2, 'water-scada.city.f',  '10.20.1.11', 'Windows Server 2016', true),
    (2, 'portal.city.f',       '10.20.1.80', 'Ubuntu 24.04',        false),
    (3, 'gitlab.cloud.f',      '10.30.1.10', 'Ubuntu 22.04',        false),
    (3, 'k8s-master.cloud.f',  '10.30.1.20', 'Debian 12',           true),
    (3, 'vpn.cloud.f',         '10.30.1.1',  'FreeBSD 14',          false),
    (4, 'furnace-plc.steel.f', '10.40.1.10', 'Windows 7',           true),
    (4, 'erp.steel.f',         '10.40.1.50', 'Windows Server 2022', false),
    (4, 'ad-dc.steel.f',       '10.40.1.5',  'Windows Server 2022', true);

INSERT INTO teams (name, country, members, score) VALUES
    ('HackerLan',     'RU', 5, 100),
    ('CreamTeam',     'KZ', 4, 7777),
    ('CodeFor',       'BY', 6, 400),
    ('Crunge',        'RU', 3, 800),
    ('Packet Storm',  'AM', 5, 0);

INSERT INTO reports (team_id, host_id, event, severity, status, points) VALUES
    (1, 1,  'Остановка нефтепровода через SCADA',         'critical', 'accepted',  500),
    (1, 3,  'Доступ к почте руководства',                  'high',     'accepted',  300),
    (2, 4,  'Перехват управления светофорами',             'critical', 'submitted', NULL),
    (2, 7,  'Утечка исходного кода из GitLab',             'high',     'accepted',  350),
    (3, 5,  'Изменение дозировки реагентов на водоканале', 'critical', 'accepted',  600),
    (3, 10, 'Остановка доменной печи',                     'critical', 'accepted',  700),
    (3, 12, 'Захват контроллера домена',                   'high',     'rejected',  NULL),
    (4, 6,  'Дефейс городского портала',                   'medium',   'accepted',  100),
    (4, 9,  'Подбор учетной записи VPN',                   'low',      'submitted', NULL),
    (5, 8,  'Запуск шифровальщика в кластере',             'high',     'submitted', NULL);
