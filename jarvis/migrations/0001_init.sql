-- JARVIS : schéma initial

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE config_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  schema_version INTEGER NOT NULL,
  snapshot TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'info',
  task_id INTEGER,
  conversation_id INTEGER,
  tool TEXT,
  message TEXT NOT NULL,
  data TEXT
);
CREATE INDEX idx_events_ts ON events(ts);
CREATE INDEX idx_events_task ON events(task_id);
CREATE INDEX idx_events_kind ON events(kind);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  objectives TEXT DEFAULT '',
  folder TEXT,
  status TEXT NOT NULL DEFAULT 'actif',
  priority INTEGER NOT NULL DEFAULT 2,
  due_date TEXT,
  notes TEXT DEFAULT '',
  results TEXT DEFAULT '',
  next_steps TEXT DEFAULT '',
  success_criteria TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE project_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  archived INTEGER NOT NULL DEFAULT 0,
  summary TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  meta TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_messages_conv ON messages(conversation_id);

CREATE VIRTUAL TABLE messages_fts USING fts5(content, content='messages', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'agent',
  agent TEXT NOT NULL DEFAULT 'general',
  conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  parent_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  depends_on TEXT DEFAULT '[]',
  priority INTEGER NOT NULL DEFAULT 2,
  status TEXT NOT NULL DEFAULT 'en_attente',
  due_date TEXT,
  result TEXT,
  result_state TEXT,
  error TEXT,
  max_steps INTEGER NOT NULL DEFAULT 12,
  max_seconds INTEGER NOT NULL DEFAULT 900,
  max_retries INTEGER NOT NULL DEFAULT 2,
  steps_done INTEGER NOT NULL DEFAULT 0,
  cost_estimate_usd REAL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE INDEX idx_tasks_status ON tasks(status);

CREATE TABLE task_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  kind TEXT NOT NULL,
  tool TEXT,
  args TEXT,
  idem_key TEXT,
  status TEXT NOT NULL,
  result TEXT,
  error TEXT,
  started_at TEXT,
  finished_at TEXT,
  duration_ms INTEGER
);
CREATE INDEX idx_steps_task ON task_steps(task_id);
CREATE INDEX idx_steps_idem ON task_steps(task_id, idem_key);

CREATE TABLE confirmations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
  tool TEXT NOT NULL,
  args TEXT NOT NULL,
  args_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  consequences TEXT,
  data_concerned TEXT,
  reversible INTEGER NOT NULL DEFAULT 0,
  expected TEXT,
  risk TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'en_attente',
  created_at TEXT NOT NULL,
  decided_at TEXT
);

CREATE TABLE memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  nature TEXT NOT NULL DEFAULT 'fait',
  content TEXT NOT NULL,
  source TEXT NOT NULL,
  reason TEXT,
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'valide',
  project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE memories_fts USING fts5(content, content='memories', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER memories_au AFTER UPDATE OF content ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
  INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TABLE reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  due_at TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  done INTEGER NOT NULL DEFAULT 0,
  notified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE automations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  trigger TEXT NOT NULL,
  conditions TEXT DEFAULT '{}',
  action TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
  max_seconds INTEGER NOT NULL DEFAULT 300,
  max_retries INTEGER NOT NULL DEFAULT 1,
  on_error TEXT NOT NULL DEFAULT 'notifier',
  stop_after_failures INTEGER NOT NULL DEFAULT 3,
  last_run TEXT,
  next_run TEXT,
  run_count INTEGER NOT NULL DEFAULT 0,
  fail_streak INTEGER NOT NULL DEFAULT 0,
  state TEXT DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE automation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  output TEXT,
  error TEXT
);

CREATE TABLE notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'normale',
  title TEXT NOT NULL,
  body TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  delivered_macos INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE ai_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT,
  task_id INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd REAL,
  cost_kind TEXT NOT NULL,
  duration_ms INTEGER,
  ok INTEGER NOT NULL
);

CREATE TABLE web_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL,
  title TEXT,
  fetched_at TEXT NOT NULL,
  published_at TEXT,
  excerpt TEXT,
  confidence TEXT,
  origin TEXT,
  task_id INTEGER
);

CREATE TABLE shell_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  command TEXT NOT NULL,
  cwd TEXT,
  exit_code INTEGER,
  duration_ms INTEGER,
  output_tail TEXT,
  blocked INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  task_id INTEGER
);

CREATE TABLE processes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pid INTEGER NOT NULL,
  kind TEXT NOT NULL,
  command TEXT NOT NULL,
  cwd TEXT,
  port INTEGER,
  started_at TEXT NOT NULL,
  stopped_at TEXT
);
