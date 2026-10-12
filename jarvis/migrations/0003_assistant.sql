-- JARVIS 0.4 : souvenirs propres à une conversation, notification d'échéance des tâches

ALTER TABLE memories ADD COLUMN conversation_id INTEGER;
CREATE INDEX idx_memories_conv ON memories(conversation_id);
ALTER TABLE tasks ADD COLUMN notified_due INTEGER NOT NULL DEFAULT 0;
