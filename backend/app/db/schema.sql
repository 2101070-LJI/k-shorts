CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_url TEXT NOT NULL,
  source_video_id TEXT NOT NULL,
  start_time REAL NOT NULL,
  end_time REAL NOT NULL,
  title TEXT,
  reason TEXT,
  template_id TEXT NOT NULL,
  llm_model TEXT NOT NULL,
  llm_score REAL,
  weights_snapshot TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  yt_video_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_clips_source ON clips(source_video_id);
CREATE INDEX IF NOT EXISTS idx_clips_yt ON clips(yt_video_id);

CREATE TABLE IF NOT EXISTS clip_signals (
  clip_id INTEGER PRIMARY KEY REFERENCES clips(id),
  retention_avg REAL,
  laughter_peak REAL,
  volume_peak REAL,
  emotion_joy_peak REAL,
  emotion_surprise_peak REAL,
  tempo_change REAL,
  clip_duration REAL,
  whisper_text TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clip_id INTEGER NOT NULL REFERENCES clips(id),
  label INTEGER NOT NULL CHECK (label IN (-1, 1)),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics (
  clip_id INTEGER NOT NULL REFERENCES clips(id),
  collected_at TIMESTAMP NOT NULL,
  views INTEGER,
  likes INTEGER,
  comments INTEGER,
  avg_view_duration REAL,
  avg_view_percentage REAL,
  impressions INTEGER,
  swipe_away_rate REAL,
  PRIMARY KEY (clip_id, collected_at)
);

CREATE TABLE IF NOT EXISTS weight_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  effective_from TIMESTAMP NOT NULL,
  w_retention REAL NOT NULL,
  w_laughter REAL NOT NULL,
  w_volume REAL NOT NULL,
  w_emotion REAL NOT NULL,
  w_tempo REAL NOT NULL,
  update_reason TEXT NOT NULL,
  trigger_clip_count INTEGER,
  notes TEXT
);

INSERT INTO weight_history (effective_from, w_retention, w_laughter, w_volume, w_emotion, w_tempo, update_reason, trigger_clip_count, notes)
SELECT CURRENT_TIMESTAMP, 0.35, 0.25, 0.15, 0.15, 0.10, 'initial', NULL, 'spec 3.3 initial hypothesis'
WHERE NOT EXISTS (SELECT 1 FROM weight_history);
