-- FITTRACK PRO Relational Database Schema (SQLite / PostgreSQL compatible)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    friend_code TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    theme TEXT NOT NULL DEFAULT 'dark',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT '',
    avatar_url TEXT DEFAULT '',
    height_cm REAL DEFAULT 174,
    weight_kg REAL DEFAULT 74,
    age INTEGER DEFAULT 24,
    sex TEXT DEFAULT 'prefer_not_to_say',
    activity_level TEXT DEFAULT 'moderate',
    fitness_goal TEXT DEFAULT 'recomp',
    dietary_pref TEXT DEFAULT 'vegetarian',
    units TEXT DEFAULT 'metric',
    calorie_goal INTEGER DEFAULT 2250,
    protein_goal INTEGER DEFAULT 150,
    carbs_goal INTEGER DEFAULT 240,
    fat_goal INTEGER DEFAULT 65,
    water_goal_ml INTEGER DEFAULT 3000,
    step_goal INTEGER DEFAULT 9000,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    streak_days INTEGER DEFAULT 0,
    league TEXT DEFAULT 'Bronze',
    privacy_public_profile INTEGER DEFAULT 0,
    privacy_share_workouts INTEGER DEFAULT 1,
    privacy_share_steps INTEGER DEFAULT 1,
    privacy_share_photos INTEGER DEFAULT 0,
    onboarding_completed INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast','lunch','snacks','dinner')),
    name TEXT NOT NULL,
    serving_size TEXT DEFAULT '1 serving',
    calories REAL NOT NULL,
    protein_g REAL NOT NULL DEFAULT 0,
    carbs_g REAL NOT NULL DEFAULT 0,
    fat_g REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    is_estimate INTEGER NOT NULL DEFAULT 0,
    confidence TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS custom_foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    serving_size TEXT NOT NULL DEFAULT '100g',
    calories REAL NOT NULL,
    protein_g REAL NOT NULL DEFAULT 0,
    carbs_g REAL NOT NULL DEFAULT 0,
    fat_g REAL NOT NULL DEFAULT 0,
    barcode TEXT DEFAULT '',
    is_veg INTEGER NOT NULL DEFAULT 1,
    is_budget INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS supplements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    timing TEXT DEFAULT 'Post-Workout',
    taken INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workout_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_index INTEGER NOT NULL,
    day_label TEXT NOT NULL,
    title TEXT NOT NULL,
    exercises_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, day_index)
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    title TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 45,
    total_volume_kg REAL NOT NULL DEFAULT 0,
    warmup_done INTEGER NOT NULL DEFAULT 0,
    cooldown_done INTEGER NOT NULL DEFAULT 0,
    soreness_score INTEGER DEFAULT 3,
    notes TEXT DEFAULT '',
    exercises_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS personal_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_name TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    reps INTEGER NOT NULL DEFAULT 1,
    estimated_1rm REAL NOT NULL,
    achieved_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    activity_type TEXT NOT NULL DEFAULT 'walking',
    steps INTEGER NOT NULL DEFAULT 0,
    distance_km REAL NOT NULL DEFAULT 0,
    duration_min INTEGER NOT NULL DEFAULT 0,
    active_minutes INTEGER NOT NULL DEFAULT 0,
    calories_burned REAL NOT NULL DEFAULT 0,
    pace_min_km REAL DEFAULT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    verified INTEGER NOT NULL DEFAULT 0,
    gps_route_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS body_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    waist_cm REAL DEFAULT NULL,
    hip_cm REAL DEFAULT NULL,
    chest_cm REAL DEFAULT NULL,
    arm_cm REAL DEFAULT NULL,
    thigh_cm REAL DEFAULT NULL,
    body_fat_pct REAL DEFAULT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    angle TEXT NOT NULL DEFAULT 'front',
    weight_kg REAL DEFAULT NULL,
    notes TEXT DEFAULT '',
    is_private INTEGER NOT NULL DEFAULT 1,
    image_data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sleep_water_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    sleep_hours REAL NOT NULL DEFAULT 7.5,
    sleep_quality INTEGER NOT NULL DEFAULT 4,
    water_ml INTEGER NOT NULL DEFAULT 0,
    mood TEXT DEFAULT 'Focused',
    soreness INTEGER DEFAULT 2,
    journal_note TEXT DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, log_date)
);

CREATE TABLE IF NOT EXISTS friendships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending','accepted','blocked')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, friend_id)
);

CREATE TABLE IF NOT EXISTS friend_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invite_code TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL REFERENCES friend_groups(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS group_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES friend_groups(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    challenge_type TEXT NOT NULL CHECK (challenge_type IN ('1v1','group')),
    metric TEXT NOT NULL CHECK (metric IN ('steps','distance_km','workouts')),
    duration_days INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    target_value REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS challenge_participants (
    challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_value REAL NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (challenge_id, user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notification_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    workout_reminders INTEGER NOT NULL DEFAULT 1,
    meal_reminders INTEGER NOT NULL DEFAULT 1,
    water_reminders INTEGER NOT NULL DEFAULT 1,
    step_reminders INTEGER NOT NULL DEFAULT 1,
    social_alerts INTEGER NOT NULL DEFAULT 1,
    leaderboard_alerts INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workout_logs(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_activity_user_date ON activity_logs(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_body_user_date ON body_metrics(user_id, log_date);
