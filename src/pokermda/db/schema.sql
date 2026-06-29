CREATE TABLE IF NOT EXISTS import_files (
    import_file_id TEXT PRIMARY KEY,
    source_site TEXT DEFAULT 'bovada',
    raw_file_path TEXT NOT NULL,
    raw_file_realpath TEXT,
    raw_file_size_bytes BIGINT,
    raw_file_mtime_ns BIGINT,
    sha256 TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imported_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'discovered',
    parser_version TEXT,
    hands_detected INTEGER DEFAULT 0,
    hands_imported INTEGER DEFAULT 0,
    hands_failed INTEGER DEFAULT 0,
    error_message TEXT,

    -- Backward-compatible aliases used by early MVP code/tests.
    file_hash TEXT,
    source_path TEXT,
    file_size_bytes BIGINT,
    modified_time TEXT,
    hands_seen INTEGER DEFAULT 0,
    hands_inserted INTEGER DEFAULT 0,

    UNIQUE (sha256, raw_file_path)
);

CREATE TABLE IF NOT EXISTS raw_hand_blocks (
    raw_hand_block_id TEXT PRIMARY KEY,
    import_file_id TEXT,
    source_site TEXT DEFAULT 'bovada',
    raw_hand_hash TEXT UNIQUE NOT NULL,
    site_hand_no TEXT,
    hand_start_line INTEGER,
    hand_end_line INTEGER,
    raw_text TEXT NOT NULL,
    parse_status TEXT DEFAULT 'pending',
    parse_error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Backward-compatible aliases.
    raw_hand_id TEXT UNIQUE,
    hand_hash TEXT,
    file_hash TEXT,
    source_path TEXT,
    block_index INTEGER,
    bovada_hand_number TEXT,
    parse_error TEXT
);

CREATE TABLE IF NOT EXISTS hands (
    hand_id TEXT PRIMARY KEY,
    source_site TEXT DEFAULT 'bovada',
    site_hand_no TEXT UNIQUE,
    raw_hand_hash TEXT UNIQUE NOT NULL,
    import_file_id TEXT,
    played_at TEXT,
    game_type TEXT,
    stake TEXT,
    table_name TEXT,
    table_size INTEGER,
    button_seat INTEGER,
    sb_amount DOUBLE,
    bb_amount DOUBLE,
    board_flop TEXT,
    board_turn TEXT,
    board_river TEXT,
    final_pot_bb DOUBLE,
    rake_bb DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Backward-compatible aliases.
    bovada_hand_number TEXT UNIQUE,
    hand_hash TEXT,
    raw_hand_id TEXT,
    source_file_hash TEXT,
    stakes TEXT,
    started_at_text TEXT,
    board TEXT,
    hero_name TEXT,
    parser_version TEXT
);

CREATE TABLE IF NOT EXISTS participants (
    participant_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    seat_no INTEGER NOT NULL,
    player_name_raw TEXT NOT NULL,
    anonymized_player_label TEXT,
    position TEXT,
    is_hero BOOLEAN DEFAULT FALSE,
    is_pool BOOLEAN DEFAULT TRUE,
    starting_stack_bb DOUBLE,
    ending_stack_bb DOUBLE,
    net_bb DOUBLE,
    hole_card_1 TEXT,
    hole_card_2 TEXT,
    hole_combo_1326 TEXT,
    hole_class_169 TEXT,
    vpip BOOLEAN,
    pfr BOOLEAN,
    three_bet BOOLEAN,
    saw_flop BOOLEAN,
    saw_turn BOOLEAN,
    saw_river BOOLEAN,
    went_showdown BOOLEAN,
    allin BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Backward-compatible aliases.
    player_name TEXT,
    stack DOUBLE,
    hole_cards TEXT,
    net_result DOUBLE,

    UNIQUE (hand_id, seat_no)
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    participant_id TEXT,
    street TEXT NOT NULL,
    action_no_global INTEGER NOT NULL,
    action_no_street INTEGER,
    action_type TEXT NOT NULL,
    amount_bb DOUBLE,
    pot_before_bb DOUBLE,
    stack_before_bb DOUBLE,
    facing_bet_bb DOUBLE,
    amount_to_call_bb DOUBLE,
    is_allin BOOLEAN DEFAULT FALSE,
    aggressor_participant_id TEXT,
    raw_action_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Backward-compatible aliases.
    sequence_no INTEGER,
    actor TEXT,
    amount DOUBLE,
    raise_to DOUBLE,
    raw_line TEXT
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
    participant_id TEXT,
    hand_id TEXT NOT NULL,
    player_name TEXT,
    seat_no INTEGER,
    is_hero BOOLEAN,
    is_pool BOOLEAN,
    position TEXT,
    hole_combo_1326 TEXT,
    hole_class_169 TEXT,
    preflop_actor_line TEXT,
    flop_actor_line TEXT,
    turn_actor_line TEXT,
    river_actor_line TEXT,
    public_line_key TEXT,
    actor_line_key TEXT,
    final_street_reached TEXT,
    final_action TEXT,
    net_bb DOUBLE,
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
    raw_hand_hash TEXT,
    file_hash TEXT,
    import_file_id TEXT,
    source_path TEXT,
    raw_file_path TEXT,
    block_index INTEGER,
    error_code TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_excerpt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_instances (
    decision_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    participant_id TEXT,
    is_hero BOOLEAN,
    is_pool BOOLEAN,
    street TEXT,
    action_no_global INTEGER,
    spot_id TEXT,
    node_key_before_action TEXT,
    public_line_key_before_action TEXT,
    actor_line_key_before_action TEXT,
    position TEXT,
    villain_position TEXT,
    position_config TEXT,
    is_ip BOOLEAN,
    is_pfa BOOLEAN,
    preflop_pot_type TEXT,
    num_players_street INTEGER,
    effective_stack_bb DOUBLE,
    spr_before_action DOUBLE,
    board_cards TEXT,
    board_bucket TEXT,
    flop_bucket TEXT,
    turn_bucket TEXT,
    river_bucket TEXT,
    is_paired_board BOOLEAN,
    river_pairs_board BOOLEAN,
    river_pair_rank_bucket TEXT,
    flush_completed BOOLEAN,
    straight_completed BOOLEAN,
    facing_or_proactive TEXT,
    facing_action_type TEXT,
    facing_size_pct_pot DOUBLE,
    facing_size_bucket TEXT,
    pot_odds DOUBLE,
    action_taken TEXT,
    action_amount_bb DOUBLE,
    action_size_pct_pot DOUBLE,
    action_size_bucket TEXT,
    hole_combo_1326 TEXT,
    hole_class_169 TEXT,
    made_hand_bucket TEXT,
    draw_bucket TEXT,
    blocker_bucket TEXT,
    net_result_bb DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Early MVP aliases.
    player_name TEXT,
    opportunity_type TEXT,
    amount DOUBLE,
    pot_before DOUBLE,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS review_candidates (
    candidate_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    hero_participant_id TEXT,
    review_score DOUBLE,
    reason_tags TEXT,
    hero_net_bb DOUBLE,
    pot_bb DOUBLE,
    street_reached TEXT,
    line_key TEXT,
    spot_ids TEXT,
    score_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_queue (
    queue_id TEXT PRIMARY KEY,
    hand_id TEXT UNIQUE NOT NULL,
    hero_participant_id TEXT,
    source TEXT DEFAULT 'local_scorer',
    priority_score DOUBLE DEFAULT 0,
    priority_bucket TEXT,
    reason_tags TEXT,
    queue_status TEXT DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date DATE,
    reviewed_at TIMESTAMP,
    archived_at TIMESTAMP,

    -- Backward-compatible aliases.
    reason TEXT,
    score DOUBLE DEFAULT 0,
    priority INTEGER DEFAULT 50,
    status TEXT DEFAULT 'queued',
    tags TEXT,
    due_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gtowizard_export_batches (
    export_batch_id TEXT PRIMARY KEY,
    tool_name TEXT DEFAULT 'gtowizard',
    export_name TEXT,
    export_format TEXT,
    export_file_path TEXT,
    export_file_sha256 TEXT,
    manifest_csv_path TEXT,
    manifest_json_path TEXT,
    n_hands INTEGER DEFAULT 0,
    filter_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP,
    upload_status TEXT DEFAULT 'not_uploaded',
    gtow_upload_name TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS gtowizard_export_hands (
    export_hand_id TEXT PRIMARY KEY,
    export_batch_id TEXT NOT NULL,
    hand_id TEXT NOT NULL,
    hero_participant_id TEXT,
    original_site_hand_no TEXT,
    exported_hand_no TEXT,
    hand_fingerprint TEXT,
    file_order INTEGER,
    file_offset_start INTEGER,
    file_offset_end INTEGER,
    sanitized_export_hash TEXT,
    export_status TEXT DEFAULT 'exported',
    upload_result_status TEXT DEFAULT 'unknown',
    gtowizard_hand_url TEXT,
    gtowizard_session_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (export_batch_id, hand_id)
);

CREATE TABLE IF NOT EXISTS gtowizard_review_results (
    result_id TEXT PRIMARY KEY,
    hand_id TEXT,
    export_hand_id TEXT,
    export_batch_id TEXT,
    gtow_status TEXT,
    gtow_ev_loss_bb DOUBLE,
    gtow_accuracy_score DOUBLE,
    biggest_mistake_street TEXT,
    biggest_mistake_action_no INTEGER,
    biggest_mistake_ev_loss_bb DOUBLE,
    gtow_label TEXT,
    solution_match_notes TEXT,
    result_source TEXT DEFAULT 'manual',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by_user BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMP,
    user_takeaway TEXT
);

CREATE TABLE IF NOT EXISTS review_notes (
    note_id TEXT PRIMARY KEY,
    hand_id TEXT,
    export_id TEXT,
    source_tool TEXT,
    reviewed_at TIMESTAMP,
    mistake_category TEXT,
    concept_tag TEXT,
    severity TEXT,
    repeat_leak BOOLEAN,
    user_note TEXT,
    correction_rule TEXT,
    drill_recommendation TEXT,
    note_text TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS node_definitions (
    node_def_id TEXT PRIMARY KEY,
    node_name TEXT,
    node_family TEXT,
    street TEXT,
    actor_role TEXT,
    facing_or_proactive TEXT,
    description TEXT,
    filter_json TEXT,
    abstraction_level TEXT,
    min_sample INTEGER,
    version TEXT DEFAULT 'v1',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Early MVP aliases.
    node_id TEXT,
    spec_path TEXT,
    spec_json TEXT,
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS node_instances (
    node_instance_id TEXT PRIMARY KEY,
    node_def_id TEXT,
    decision_id TEXT,
    hand_id TEXT NOT NULL,
    participant_id TEXT,
    node_key_exact TEXT,
    node_key_bucketed TEXT,
    node_family_key TEXT,
    abstraction_level TEXT,
    action_taken TEXT,
    hole_class_169 TEXT,
    hole_combo_1326 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Early MVP aliases.
    node_id TEXT,
    player_name TEXT,
    street TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS node_aggregates (
    aggregate_id TEXT PRIMARY KEY,
    node_def_id TEXT,
    node_key TEXT,
    node_family_key TEXT,
    abstraction_level TEXT,
    pool_scope TEXT,
    stake TEXT,
    game_type TEXT,
    street TEXT,
    n_opportunities INTEGER,
    n_fold INTEGER,
    n_call INTEGER,
    n_raise INTEGER,
    n_check INTEGER,
    n_bet INTEGER,
    fold_freq DOUBLE,
    call_freq DOUBLE,
    raise_freq DOUBLE,
    bet_freq DOUBLE,
    check_freq DOUBLE,
    ci_low DOUBLE,
    ci_high DOUBLE,
    avg_pot_bb DOUBLE,
    avg_spr DOUBLE,
    avg_net_result_bb DOUBLE,
    last_updated_at TIMESTAMP,
    node_def_version TEXT
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
    aggregate_id TEXT PRIMARY KEY,
    node_def_id TEXT,
    node_key TEXT,
    pool_scope TEXT,
    stake TEXT,
    game_type TEXT,
    position_config TEXT,
    street TEXT,
    board_bucket TEXT,
    facing_size_bucket TEXT,
    action_taken TEXT,
    hole_class_169 TEXT,
    n_reached_node INTEGER,
    n_took_action INTEGER,
    action_freq_with_hand DOUBLE,
    range_weight_after_action DOUBLE,
    last_updated_at TIMESTAMP,
    spot_def_version TEXT,

    -- Early MVP aliases.
    range_aggregate_id TEXT,
    node_id TEXT,
    player_group TEXT,
    combo TEXT,
    weight DOUBLE,
    samples INTEGER,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS node_deviation_candidates (
    candidate_id TEXT PRIMARY KEY,
    node_def_id TEXT,
    node_key TEXT,
    node_family_key TEXT,
    stake TEXT,
    game_type TEXT,
    pool_scope TEXT,
    metric_name TEXT,
    observed_value DOUBLE,
    baseline_value DOUBLE,
    deviation DOUBLE,
    z_score DOUBLE,
    confidence_score DOUBLE,
    n_opportunities INTEGER,
    exploit_direction TEXT,
    exploit_summary TEXT,
    recommended_adjustment TEXT,
    sample_hand_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backward-compatible GTOWizard MVP tables.
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

CREATE INDEX IF NOT EXISTS idx_import_files_status ON import_files(status);
CREATE INDEX IF NOT EXISTS idx_import_files_sha256 ON import_files(sha256);
CREATE INDEX IF NOT EXISTS idx_raw_hand_blocks_hash ON raw_hand_blocks(raw_hand_hash);
CREATE INDEX IF NOT EXISTS idx_hands_site_hand_no ON hands(site_hand_no);
CREATE INDEX IF NOT EXISTS idx_actions_hand_street ON actions(hand_id, street);
CREATE INDEX IF NOT EXISTS idx_study_queue_status ON study_queue(queue_status);
CREATE INDEX IF NOT EXISTS idx_gtowizard_batches_status ON gtowizard_export_batches(upload_status);
