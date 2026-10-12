-- JARVIS 0.2 : prochaine action des tâches, mémoire temporaire, sessions du navigateur piloté

ALTER TABLE tasks ADD COLUMN next_action TEXT;
ALTER TABLE memories ADD COLUMN expires_at TEXT;
CREATE INDEX idx_memories_expires ON memories(expires_at);

CREATE TABLE browser_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  task_id INTEGER,
  action TEXT NOT NULL,
  url TEXT,
  detail TEXT,
  ok INTEGER NOT NULL
);
