CREATE TABLE sectors (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    industry    text NOT NULL,
    description text
);

CREATE TABLE hosts (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sector_id   integer NOT NULL REFERENCES sectors (id),
    hostname    text NOT NULL,
    ip          inet NOT NULL,
    os          text NOT NULL,
    is_critical boolean NOT NULL DEFAULT false,
    UNIQUE (sector_id, hostname)
);

CREATE TABLE teams (
    id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    text NOT NULL UNIQUE,
    country text NOT NULL,
    members integer NOT NULL CHECK (members > 0),
    score   integer NOT NULL DEFAULT 0
);

CREATE TABLE reports (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id      integer NOT NULL REFERENCES teams (id),
    host_id      integer NOT NULL REFERENCES hosts (id),
    event        text NOT NULL,
    severity     text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status       text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'accepted', 'rejected')),
    points       integer CHECK (points >= 0),
    submitted_at timestamptz NOT NULL DEFAULT now()
);
