CREATE TABLE IF NOT EXISTS import_files (
    file_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    modified_time TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imported_at TIMESTAMP,
    status TEXT NOT NULL,
    hands_seen INTEGER DEFAULT 0,
    hands_inserted INTEGER DEFAULT 0,
    error_message TEXT,
    PRIMARY KEY (file_hash, source_path)
);

CREATE TABLE IF NOT EXISTS bronze_raw_hand_blocks (
    raw_hand_id TEXT PRIMARY KEY,
    hand_hash TEXT UNIQUE NOT NULL,
    file_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    bovada_hand_number TEXT,
    raw_text TEXT NOT NULL,
    parse_status TEXT DEFAULT 'pending',
    parse_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hands (
    hand_id TEXT PRIMARY KEY,
    bovada_hand_number TEXT UNIQUE,
    hand_hash TEXT UNIQUE NOT NULL,
    raw_hand_id TEXT,
    source_file_hash TEXT,
    source_site TEXT DEFAULT 'bovada',
    game_type TEXT,
    stakes TEXT,
    table_name TEXT,
    button_seat INTEGER,
    started_at_text TEXT,
    board TEXT,
    hero_name TEXT,
    parser_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participants (
    hand_id TEXT NOT NULL,
    seat_no INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    stack DOUBLE,
    is_hero BOOLEAN DEFAULT FALSE,
    hole_cards TEXT,
    position TEXT,
    net_result DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (hand_id, seat_no)
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    street TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    actor TEXT,
    action_type TEXT NOT NULL,
    amount DOUBLE,
    raise_to DOUBLE,
    raw_line TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS results (
    result_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    player_name TEXT,
    amount DOUBLE,
    raw_line TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_hand_facts (
    fact_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    seat_no INTEGER,
    position TEXT,
    vpip BOOLEAN,
    pfr BOOLEAN,
    saw_flop BOOLEAN,
    went_to_showdown BOOLEAN,
    won_hand BOOLEAN,
    net_result DOUBLE,
    facts_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parse_errors (
    error_id TEXT PRIMARY KEY,
    hand_hash TEXT,
    file_hash TEXT,
    source_path TEXT,
    block_index INTEGER,
    error_code TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_excerpt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_queue (
    queue_id TEXT PRIMARY KEY,
    hand_id TEXT UNIQUE NOT NULL,
    reason TEXT,
    score DOUBLE DEFAULT 0,
    priority INTEGER DEFAULT 50,
    status TEXT DEFAULT 'queued',
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_at TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gtowizard_exports (
    export_id TEXT PRIMARY KEY,
    export_path TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    export_format TEXT NOT NULL,
    sanitizer_version TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP,
    manual_result_path TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS gtowizard_export_items (
    export_id TEXT NOT NULL,
    hand_id TEXT NOT NULL,
    hand_hash TEXT,
    file_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (export_id, hand_id)
);

CREATE TABLE IF NOT EXISTS review_notes (
    note_id TEXT PRIMARY KEY,
    hand_id TEXT,
    export_id TEXT,
    note_text TEXT NOT NULL,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS node_definitions (
    node_id TEXT PRIMARY KEY,
    version TEXT DEFAULT 'v1',
    spec_path TEXT,
    spec_json TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_instances (
    decision_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    player_name TEXT,
    street TEXT,
    opportunity_type TEXT,
    action_taken TEXT,
    amount DOUBLE,
    pot_before DOUBLE,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS node_instances (
    node_instance_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    decision_id TEXT,
    hand_id TEXT NOT NULL,
    player_name TEXT,
    street TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stat_aggregates (
    aggregate_id TEXT PRIMARY KEY,
    node_id TEXT,
    metric_name TEXT NOT NULL,
    numerator DOUBLE,
    denominator DOUBLE,
    value DOUBLE,
    filters_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS range_aggregates (
    range_aggregate_id TEXT PRIMARY KEY,
    node_id TEXT,
    player_group TEXT,
    combo TEXT,
    weight DOUBLE,
    samples INTEGER,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_import_files_status ON import_files(status);
CREATE INDEX IF NOT EXISTS idx_bronze_file_hash ON bronze_raw_hand_blocks(file_hash);
CREATE INDEX IF NOT EXISTS idx_hands_hand_number ON hands(bovada_hand_number);
CREATE INDEX IF NOT EXISTS idx_actions_hand_street ON actions(hand_id, street);
CREATE INDEX IF NOT EXISTS idx_study_queue_status ON study_queue(status);
CREATE INDEX IF NOT EXISTS idx_gtowizard_exports_status ON gtowizard_exports(status);

