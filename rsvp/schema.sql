DROP TABLE IF EXISTS responses;
DROP TABLE IF EXISTS guests;

CREATE TABLE guests (
  id    INTEGER PRIMARY KEY,
  name  TEXT NOT NULL,
  label TEXT,
  kid   INTEGER NOT NULL DEFAULT 0,
  age   INTEGER,
  norm  TEXT NOT NULL
);

-- uma linha por convidado que já respondeu (sim/não)
-- by_id = quem preencheu (o próprio convidado ou quem o incluiu como acompanhante)
CREATE TABLE responses (
  guest_id INTEGER PRIMARY KEY REFERENCES guests(id),
  status   TEXT NOT NULL CHECK (status IN ('yes', 'no')),
  by_id    INTEGER NOT NULL,
  note     TEXT,
  at       TEXT NOT NULL
);

CREATE INDEX responses_by ON responses(by_id);
